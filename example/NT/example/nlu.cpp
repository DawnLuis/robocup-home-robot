// nlu.cpp
#include "nlu.h"
#include "instruction_parser.hpp"
#include <sstream>
#include <regex>
#include <algorithm>
#include <map>
#include <cctype>
#include <set>
#include <iostream>

namespace {
    std::string to_lower(const std::string& s) {
        std::string result = s;
        std::transform(result.begin(), result.end(), result.begin(), ::tolower);
        return result;
    }

    bool contains(const std::string& str, const std::string& substr) {
        return str.find(substr) != std::string::npos;
    }

    std::string trim(const std::string& s) {
        size_t start = s.find_first_not_of(" \t\n\r");
        size_t end = s.find_last_not_of(" \t\n\r");
        return (start == std::string::npos) ? "" : s.substr(start, end - start + 1);
    }

    std::vector<std::string> split_sentences(const std::string& text) {
        std::vector<std::string> result;
        std::regex re(R"([.!?]+(?:\s+|$))");
        std::sregex_token_iterator it(text.begin(), text.end(), re, -1);
        std::sregex_token_iterator end;

        for (; it != end; ++it) {
            std::string sentence = trim(it->str());
            if (!sentence.empty()) {
                result.push_back(sentence);
            }
        }
        return result;
    }

    bool word_contains(const std::string& text, const std::string& word) {
        if (word.empty()) return false;
        size_t pos = 0;
        while ((pos = text.find(word, pos)) != std::string::npos) {
            bool left_ok = (pos == 0) || !std::isalnum(text[pos - 1]);
            bool right_ok = (pos + word.length() >= text.length()) || !std::isalnum(text[pos + word.length()]);
            if (left_ok && right_ok) return true;
            pos++;
        }
        return false;
    }

    std::vector<std::string> extract_objects_by_map(const std::string& sent,
                                                    const std::map<std::string, std::string>& map) {
        std::vector<std::string> results;
        for (const auto& kv : map) {
            if (word_contains(sent, kv.first)) {
                results.push_back(kv.second);
            }
        }
        std::sort(results.begin(), results.end());
        results.erase(std::unique(results.begin(), results.end()), results.end());
        return results;
    }

    // 新的条件生成函数，生成目标格式
    std::string generate_conds_str_target(const std::vector<Condition>& conds) {
        if (conds.empty()) return "";
        
        std::ostringstream oss;
        oss << "(:cond";
        for (const auto& cond : conds) {
            oss << " (" << cond.attr << " " << cond.var << " " << cond.value << ")";
        }
        oss << ")";
        return oss.str();
    }

    // 生成完整的谓词表达式
    std::string generate_predicate_target(const std::string& pred_name, 
                                        const std::vector<std::string>& args,
                                        const std::vector<Condition>& conds) {
        std::ostringstream oss;
        
        // 生成谓词部分，如 (on X Y)
        oss << "(" << pred_name;
        for (const auto& arg : args) {
            oss << " " << arg;
        }
        oss << ")";
        
        // 生成条件部分
        std::string conds_str = generate_conds_str_target(conds);
        if (!conds_str.empty()) {
            oss << " " << conds_str;
        }
        
        return oss.str();
    }
}

std::string SimpleNLU::parse(const std::string& input) {
    std::ostringstream ins_stream;
    ins_stream << "(:ins";

    if (input.empty()) {
        ins_stream << ")";
        return ins_stream.str();
    }

    std::vector<std::string> sentences = split_sentences(input);

    // 物体类别映射
    std::map<std::string, std::string> sort_map = {
        // 小物体
        {"book", "book"}, {"can", "can"}, {"remotecontrol", "remotecontrol"},
        {"bottle", "bottle"}, {"cup", "cup"},
        // 大物体  
        {"human", "human"}, {"plant", "plant"}, {"couch", "couch"},
        {"chair", "chair"}, {"sofa", "sofa"}, {"bed", "bed"}, 
        {"table", "table"}, {"workspace", "workspace"}, {"worktable", "worktable"},
        {"teapoy", "teapoy"}, {"desk", "desk"}, {"television", "television"},
        {"airconditioner", "airconditioner"}, {"washmachine", "washmachine"},
        // 容器
        {"closet", "closet"}, {"cupboard", "cupboard"}, 
        {"refrigerator", "refrigerator"}, {"microwave", "microwave"}
    };

    // 颜色映射
    std::map<std::string, std::string> color_map = {
        {"red", "red"}, {"blue", "blue"}, {"green", "green"},
        {"white", "white"}, {"yellow", "yellow"}, {"black", "black"}
    };

    // 关系映射
    std::map<std::string, std::string> relation_map = {
        {"on", "on"}, {"in", "inside"}, {"inside", "inside"},
        {"near", "near"}, {"next to", "near"}, {"beside", "near"},
        {"opened", "opened"}, {"open", "opened"},
        {"closed", "closed"}, {"close", "closed"}
    };

    for (const auto& sent : sentences) {
        std::string lower_sent = to_lower(sent);
        std::string rule_type; // :info, :task, :cons_not, :cons_notnot
        std::string predicate_name;
        std::vector<std::string> predicate_args;
        std::vector<Condition> conditions;

        bool is_negated = contains(lower_sent, "not") || 
                          contains(lower_sent, "don't") || 
                          contains(lower_sent, "do not");
        bool is_required = contains(lower_sent, "must") || 
                          contains(lower_sent, "should") ||
                          contains(lower_sent, "always");

        // === 提取物体和颜色 ===
        std::vector<std::string> objects = extract_objects_by_map(lower_sent, sort_map);
        std::vector<std::string> colors_found;
        
        for (const auto& color_pair : color_map) {
            if (word_contains(lower_sent, color_pair.first)) {
                colors_found.push_back(color_pair.first);
            }
        }

        // === 确定规则类型和谓词 ===
        
        // 1. 信息类规则 (描述状态)
        if (contains(lower_sent, "there is") || contains(lower_sent, "is on") || 
            contains(lower_sent, "is in") || contains(lower_sent, "is near") ||
            contains(lower_sent, "is opened") || contains(lower_sent, "is closed")) {
            
            rule_type = ":info";
            
            // 提取关系
            for (const auto& rel : relation_map) {
                if (contains(lower_sent, rel.first)) {
                    predicate_name = rel.second;
                    break;
                }
            }
            
            if (predicate_name.empty()) {
                predicate_name = "on"; // 默认关系
            }
            
            // 设置参数
            if (predicate_name == "opened" || predicate_name == "closed") {
                predicate_args = {"X"};
            } else {
                predicate_args = {"X", "Y"};
            }
            
        } 
        // 2. 任务类规则 (指令)
        else if (contains(lower_sent, "put") || contains(lower_sent, "place") ||
                 contains(lower_sent, "take") || contains(lower_sent, "pick") ||
                 contains(lower_sent, "give") || contains(lower_sent, "move") ||
                 contains(lower_sent, "go") || contains(lower_sent, "open") ||
                 contains(lower_sent, "close")) {
            
            rule_type = ":task";
            
            // 确定任务类型
            if ((contains(lower_sent, "put") || contains(lower_sent, "place")) && 
                (contains(lower_sent, " in ") || contains(lower_sent, " into "))) {
                predicate_name = "putin";
                predicate_args = {"X", "Y"};
            }
            else if ((contains(lower_sent, "put") || contains(lower_sent, "place")) && 
                     (contains(lower_sent, " on ") || contains(lower_sent, " onto "))) {
                predicate_name = "puton";
                predicate_args = {"X", "Y"};
            }
            else if (contains(lower_sent, "take out") || contains(lower_sent, "get out") ||
                     (contains(lower_sent, "take") && contains(lower_sent, " from "))) {
                predicate_name = "takeout";
                predicate_args = {"X", "Y"};
            }
            else if (contains(lower_sent, "pick up") || contains(lower_sent, "pickup")) {
                predicate_name = "pickup";
                predicate_args = {"X"};
            }
            else if (contains(lower_sent, "give") || contains(lower_sent, "hand")) {
                predicate_name = "give";
                predicate_args = {"human", "X"};
            }
            else if (contains(lower_sent, "go to") || contains(lower_sent, "move to")) {
                predicate_name = "goto";
                predicate_args = {"X"};
            }
            else if (contains(lower_sent, "open")) {
                predicate_name = "opened";
                predicate_args = {"X"};
            }
            else if (contains(lower_sent, "close")) {
                predicate_name = "closed";
                predicate_args = {"X"};
            }
            else {
                predicate_name = "puton"; // 默认任务
                predicate_args = {"X", "Y"};
            }
        }

        // === 构建条件 ===
        
        // 物体类型条件
        if (!objects.empty()) {
            // 第一个物体作为 X
            Condition cond_x;
            cond_x.var = "X";
            cond_x.attr = "sort";
            cond_x.value = objects[0];
            conditions.push_back(cond_x);
            
            // 如果有颜色，添加到 X
            if (!colors_found.empty()) {
                Condition color_cond;
                color_cond.var = "X";
                color_cond.attr = "color";
                color_cond.value = colors_found[0];
                conditions.push_back(color_cond);
            }
            
            // 第二个物体作为 Y（如果有）
            if (objects.size() > 1 && predicate_args.size() > 1) {
                Condition cond_y;
                cond_y.var = "Y";
                cond_y.attr = "sort";
                cond_y.value = objects[1];
                conditions.push_back(cond_y);
            }
        }

        // === 处理否定和必须 ===
        if (is_required && is_negated) {
            // must not → :cons_not
            rule_type = ":cons_not";
        } else if (is_required && !is_negated) {
            // must → :cons_notnot  
            rule_type = ":cons_notnot";
        } else if (is_negated) {
            // should not → :cons_not
            rule_type = ":cons_not";
        }

        // === 生成输出 ===
        if (!rule_type.empty() && !predicate_name.empty()) {
            std::string predicate_expr = generate_predicate_target(predicate_name, predicate_args, conditions);
            
            if (rule_type == ":info" || rule_type == ":task") {
                ins_stream << " (" << rule_type << " " << predicate_expr << ")";
            } else if (rule_type == ":cons_not" || rule_type == ":cons_notnot") {
                // 对于约束，需要确定内部规则类型
                std::string inner_rule_type = contains(lower_sent, "put") || contains(lower_sent, "take") || 
                                             contains(lower_sent, "pick") || contains(lower_sent, "give") ? 
                                             ":task" : ":info";
                std::string inner_predicate_expr = generate_predicate_target(predicate_name, predicate_args, conditions);
                ins_stream << " (" << rule_type << " (" << inner_rule_type << " " << inner_predicate_expr << "))";
            }
        }
    }

    ins_stream << ")";
    std::string result = ins_stream.str();
    
    // 调试输出
    std::cout << "[NLU] Input: " << input << std::endl;
    std::cout << "[NLU] Output: " << result << std::endl;
    
    return result;
}