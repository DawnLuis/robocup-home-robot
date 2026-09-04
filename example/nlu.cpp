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
        // 按在句子中的出现位置排序，而非字母序（避免X/Y颠倒）
        std::vector<std::pair<size_t, std::string>> pos_pairs;
        for (const auto& obj : results) {
            size_t pos = sent.find(obj);
            pos_pairs.push_back({pos, obj});
        }
        std::sort(pos_pairs.begin(), pos_pairs.end());
        results.clear();
        for (const auto& p : pos_pairs) {
            if (std::find(results.begin(), results.end(), p.second) == results.end()) {
                results.push_back(p.second);
            }
        }
        return results;
    }

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

    std::string generate_predicate_target(const std::string& pred_name,
                                        const std::vector<std::string>& args,
                                        const std::vector<Condition>& conds) {
        std::ostringstream oss;
        oss << "(" << pred_name;
        for (const auto& arg : args) {
            oss << " " << arg;
        }
        oss << ")";
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

    // 关系映射 (顺序重要：长词优先匹配)
    std::map<std::string, std::string> relation_map = {
        {"next to", "near"}, {"beside", "near"},
        {"near", "near"}, {"inside", "inside"}, {"in", "inside"},
        {"on", "on"}, {"onto", "on"},
        {"opened", "opened"}, {"open", "opened"},
        {"closed", "closed"}, {"close", "closed"}
    };

    for (const auto& sent : sentences) {
        std::string lower_sent = to_lower(sent);
        std::string rule_type; // :info, :task, :cons_not, :cons_notnot
        std::string predicate_name;
        std::vector<std::string> predicate_args;
        std::vector<Condition> conditions;
        bool is_task_origin = false; // 该句本质上是任务(动词)还是信息(状态)

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

        // 0. 必须成立的事实 (cons_notnot): "there must be", "must be on/in/near", "must in the plate"
        if (is_required && !is_negated &&
            (contains(lower_sent, "there must be") || contains(lower_sent, "must be") ||
             contains(lower_sent, "must on") || contains(lower_sent, "must in") ||
             contains(lower_sent, "must near") || contains(lower_sent, "must plate"))) {

            rule_type = ":cons_notnot";

            // plate 特殊检测: "on the plate", "in the plate", "must plate"
            if (contains(lower_sent, "plate")) {
                predicate_name = "plate";
                predicate_args = {"X"};
                is_task_origin = false;
            } else {
                for (const auto& rel : relation_map) {
                    if (word_contains(lower_sent, rel.first)) {
                        predicate_name = rel.second;
                        break;
                    }
                }
                if (predicate_name.empty()) {
                    predicate_name = "on"; // 默认关系
                }
                if (predicate_name == "opened" || predicate_name == "closed") {
                    predicate_args = {"X"};
                } else {
                    predicate_args = {"X", "Y"};
                }
                is_task_origin = false;
            }
        }
        // 1. 信息类规则 (描述状态) — 用精确句式匹配，避免 "close door of" 被抢走
        //    "is closed/is opened/is in/is on/is near/there is/is not opened/is not closed"
        else if (contains(lower_sent, "is closed") || contains(lower_sent, "is opened") ||
                 contains(lower_sent, "is in") || contains(lower_sent, "is on") ||
                 contains(lower_sent, "is near") || contains(lower_sent, "there is") ||
                 contains(lower_sent, "is not opened") || contains(lower_sent, "is not closed") ||
                 (is_negated && (contains(lower_sent, "not opened") || contains(lower_sent, "not closed")))) {

            rule_type = ":info";
            is_task_origin = false;

            // plate 特殊检测: "on the plate", "in the plate"
            if (contains(lower_sent, "plate")) {
                predicate_name = "plate";
                predicate_args = {"X"};
            } else if (contains(lower_sent, "not opened")) {
                // "X is not opened" → closed
                predicate_name = "closed";
                predicate_args = {"X"};
            } else if (contains(lower_sent, "not closed")) {
                // "X is not closed" → opened
                predicate_name = "opened";
                predicate_args = {"X"};
            } else if (contains(lower_sent, "is opened") || word_contains(lower_sent, "opened")) {
                predicate_name = "opened";
                predicate_args = {"X"};
            } else if (contains(lower_sent, "is closed") || word_contains(lower_sent, "closed")) {
                predicate_name = "closed";
                predicate_args = {"X"};
            } else {
                for (const auto& rel : relation_map) {
                    if (word_contains(lower_sent, rel.first)) {
                        predicate_name = rel.second;
                        break;
                    }
                }
                if (predicate_name.empty()) {
                    predicate_name = "on"; // 默认关系
                }
                if (predicate_name == "opened" || predicate_name == "closed") {
                    predicate_args = {"X"};
                } else {
                    predicate_args = {"X", "Y"};
                }
            }
            // 清除否定标记，避免后续被转为 cons_not
            is_negated = false;
        }
        // 2. 任务类规则 (指令)
        // ★ "must ... (not) be ..." 是约束句(cons_not/cons_notnot), 不是任务指令
        //   (77/90: "There must not be refrigerator is opened" 曾误入task变cons_not(task open))
        else if (!contains(lower_sent, "opened") && !contains(lower_sent, "closed") &&
                 !is_required &&
                 (contains(lower_sent, "put") || contains(lower_sent, "place") ||
                 contains(lower_sent, "take") || contains(lower_sent, "pick") ||
                 contains(lower_sent, "give") || contains(lower_sent, "move") ||
                 contains(lower_sent, "go") || contains(lower_sent, "open") ||
                 contains(lower_sent, "close"))) {

            rule_type = ":task";
            is_task_origin = true;

            // 确定任务类型
            // ★ takeout 必须先于 puton/putin 判断: "Take the bottle out of the refrigerator"
            //   同时含 put(误) / "out of"+"take"(正)。指南允许 take...out 句式,
            //   out 后既可跟 of 也可跟 from。放在 puton 之后会被默认 puton 吞掉(96.xml实锤)
            if (contains(lower_sent, "take out") || contains(lower_sent, "get out") ||
                (contains(lower_sent, "take") &&
                 (contains(lower_sent, " out of ") || contains(lower_sent, " out from ") ||
                  contains(lower_sent, " from ")))) {
                predicate_name = "takeout";
                predicate_args = {"X", "Y"};
            }
            else if ((contains(lower_sent, "put") || contains(lower_sent, "place")) &&
                     (contains(lower_sent, " in ") || contains(lower_sent, " into "))) {
                predicate_name = "putin";
                predicate_args = {"X", "Y"};
            }
            else if (word_contains(lower_sent, "put down") || word_contains(lower_sent, "putdown") ||
                     (contains(lower_sent, "put") && word_contains(lower_sent, "down") &&
                      !contains(lower_sent, " on ") && !contains(lower_sent, " onto "))) {
                predicate_name = "putdown";
                predicate_args = {"X"};
            }
            else if ((contains(lower_sent, "put") || contains(lower_sent, "place")) &&
                     (contains(lower_sent, " on ") || contains(lower_sent, " onto "))) {
                predicate_name = "puton";
                predicate_args = {"X", "Y"};
            }
            else if (contains(lower_sent, "pick")) {
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
            else if (word_contains(lower_sent, "open") && !contains(lower_sent, "opened")) {
                predicate_name = "open";
                predicate_args = {"X"};
            }
            else if (word_contains(lower_sent, "close") && !contains(lower_sent, "closed")) {
                predicate_name = "close";
                predicate_args = {"X"};
            }
            else {
                predicate_name = "puton"; // 默认任务
                predicate_args = {"X", "Y"};
            }
        }
        // 3. 否定约束句（无动作词）: "X must not be in/on Y", "do not be in/on", "must not be opened/closed"
        else if (is_negated &&
                 (contains(lower_sent, "be in") || contains(lower_sent, "be on") ||
                  contains(lower_sent, "be near") || contains(lower_sent, "in the") ||
                  contains(lower_sent, "on the") || contains(lower_sent, "plate") ||
                  (contains(lower_sent, "opened") || contains(lower_sent, "closed")))) {
            rule_type = ":info"; // 先标记为info，后面否定逻辑转为cons_not
            is_task_origin = false;

            // 状态词优先: "must not be opened/closed" → opened/closed
            if (contains(lower_sent, "plate")) {
                predicate_name = "plate";
                predicate_args = {"X"};
            } else if (contains(lower_sent, "opened")) {
                predicate_name = "opened";
                predicate_args = {"X"};
            } else if (contains(lower_sent, "closed")) {
                predicate_name = "closed";
                predicate_args = {"X"};
            } else {
                for (const auto& rel : relation_map) {
                    if (word_contains(lower_sent, rel.first)) {
                        predicate_name = rel.second;
                        break;
                    }
                }
                if (predicate_name.empty()) {
                    predicate_name = "inside"; // 默认关系
                }
                if (predicate_name == "opened" || predicate_name == "closed") {
                    predicate_args = {"X"};
                } else {
                    predicate_args = {"X", "Y"};
                }
            }
        }

        // === 构建条件 ===

        // 对 give 特殊处理: "give human X" 中 human 是固定参数，不是变量
        std::vector<std::string> effective_objects = objects;
        if (predicate_name == "give") {
            effective_objects.clear();
            for (const auto& obj : objects) {
                if (obj != "human") effective_objects.push_back(obj);
            }
            if (effective_objects.empty()) effective_objects = objects; // fallback
        }

        // 物体类型条件
        if (!effective_objects.empty()) {
            Condition cond_x;
            cond_x.var = "X";
            cond_x.attr = "sort";
            cond_x.value = effective_objects[0];
            conditions.push_back(cond_x);

            if (!colors_found.empty()) {
                Condition color_cond;
                color_cond.var = "X";
                color_cond.attr = "color";
                color_cond.value = colors_found[0];
                conditions.push_back(color_cond);
            }

            if (effective_objects.size() > 1 && predicate_args.size() > 1) {
                Condition cond_y;
                cond_y.var = "Y";
                cond_y.attr = "sort";
                cond_y.value = effective_objects[1];
                conditions.push_back(cond_y);
            }
        }

        // === 容器 type 条件 ===
        // 容器任务 putin/takeout 的 Y、open/close 的 X 若是容器类物体，补 (type X/Y container)
        // 出题要求容器类任务必须带 (type * container)
        static const std::set<std::string> container_sorts = {
            "closet", "cupboard", "refrigerator", "microwave", "washmachine"
        };
        if (!effective_objects.empty() &&
            (predicate_name == "open" || predicate_name == "close")) {
            if (container_sorts.count(effective_objects[0])) {
                Condition type_cond;
                type_cond.var = "X";
                type_cond.attr = "type";
                type_cond.value = "container";
                conditions.push_back(type_cond);
            }
        }
        if (effective_objects.size() > 1 && predicate_args.size() > 1 &&
            (predicate_name == "putin" || predicate_name == "takeout" ||
             predicate_name == "inside")) {
            if (container_sorts.count(effective_objects[1])) {
                Condition type_cond;
                type_cond.var = "Y";
                type_cond.attr = "type";
                type_cond.value = "container";
                conditions.push_back(type_cond);
            }
        }

        // === 处理否定和必须 ===
        if (rule_type == ":cons_notnot") {
            // 已在分支0中确定
        } else if (is_required && is_negated && rule_type != ":cons_notnot") {
            if (rule_type == ":task" || rule_type == ":info") rule_type = ":cons_not";
        } else if (is_negated && rule_type == ":task") {
            rule_type = ":cons_not";
        }

        // === 生成输出 ===
        if (!rule_type.empty() && !predicate_name.empty()) {
            std::string predicate_expr = generate_predicate_target(predicate_name, predicate_args, conditions);

            if (rule_type == ":info" || rule_type == ":task") {
                ins_stream << " (" << rule_type << " " << predicate_expr << ")";
            } else if (rule_type == ":cons_not" || rule_type == ":cons_notnot") {
                std::string inner_rule_type = is_task_origin ? ":task" : ":info";
                std::string inner_predicate_expr = generate_predicate_target(predicate_name, predicate_args, conditions);
                ins_stream << " (" << rule_type << " (" << inner_rule_type << " " << inner_predicate_expr << "))";
            }
        }
    }

    ins_stream << ")";
    return ins_stream.str();
}
