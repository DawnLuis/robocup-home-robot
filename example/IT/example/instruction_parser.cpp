// instruction_parser.cpp
#include "instruction_parser.hpp"
#include <iostream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <map>
#include <iomanip>

// 工具函数：去除首尾空格
std::string InstructionParser::trim(const std::string& s) {
    auto start = s.begin();
    while (start != s.end() && std::isspace(*start)) start++;
    auto end = s.end();
    if (start != end) {
        do { end--; } while (std::distance(start, end) > 0 && std::isspace(*end));
    }
    return std::string(start, end + 1);
}

// 按括号层级分割字符串，返回每个顶层括号内的内容（含括号）
std::vector<std::string> InstructionParser::split_parentheses(const std::string& s) {
    std::vector<std::string> result;
    int depth = 0;
    std::string current;

    for (char c : s) {
        if (c == '(') {
            depth++;
            current += c;
        } else if (c == ')') {
            current += c;
            depth--;
            if (depth == 0) {
                result.push_back(current);
                current.clear();
            }
        } else if (depth > 0) {
            current += c;
        }
    }
    return result;
}

// 解析谓词，如 (puton X Y) 或 (closed X)
Predicate InstructionParser::parse_predicate(const std::string& pred_str) {
    Predicate pred;
    std::string s = trim(pred_str);
    if (s.empty() || s[0] != '(' || s.back() != ')') return pred;

    s = s.substr(1, s.size() - 2); // 去掉外层 ()
    std::istringstream iss(s);
    std::string token;
    iss >> token;
    if (token.empty()) return pred;

    pred.name = token;

    while (iss >> token) {
        pred.args.push_back(token);
    }

    return pred;
}

// 解析条件，如 (:cond (sort X book) (color X green))
std::vector<Condition> InstructionParser::parse_conditions(const std::string& cond_str) {
    std::vector<Condition> conds;
    std::string s = trim(cond_str);
    if (s.size() < 6 || s.substr(0, 6) != "(:cond") return conds;

    s = s.substr(6); // 去掉 (:cond
    if (!s.empty() && s.back() == ')') s.pop_back();
    s = trim(s);

    // 使用 split_parentheses 解析内部多个 (attr var value)
    std::vector<std::string> cond_tokens = split_parentheses(s);
    for (const std::string& token : cond_tokens) {
        if (token.size() < 3 || token[0] != '(' || token.back() != ')') continue;
        std::string inner = token.substr(1, token.size() - 2);
        std::istringstream iss(inner);
        std::string attr, var, value;
        iss >> attr >> var >> value;
        if (!attr.empty() && !var.empty() && !value.empty()) {
            Condition cond;
            cond.attr = attr;
            cond.var = var;
            cond.value = value;
            conds.push_back(cond);
        }
    }

    return conds;
}

// 字符串转 ObjectType
ObjectType InstructionParser::str_to_object_type(const std::string& s) const {
    static std::map<std::string, ObjectType> m = {
        {"robot", ObjectType::Robot}, {"human", ObjectType::Human},
        {"book", ObjectType::Book}, {"can", ObjectType::Can},
        {"remotecontrol", ObjectType::RemoteControl},
        {"bottle", ObjectType::Bottle}, {"cup", ObjectType::Cup},
        {"desk", ObjectType::Desk}, {"television", ObjectType::Television},
        {"chair", ObjectType::Chair}, {"bed", ObjectType::Bed},
        {"refrigerator", ObjectType::Refrigerator},
        {"closet", ObjectType::Closet}, {"cupboard", ObjectType::Cupboard},
        {"microwave", ObjectType::Microwave}, {"sofa", ObjectType::Sofa},
        {"table", ObjectType::Table},
        {"plant", ObjectType::Plant}, {"couch", ObjectType::Couch},
        {"workspace", ObjectType::Workspace}, {"worktable", ObjectType::Worktable},
        {"teapoy", ObjectType::Teapoy}, {"airconditioner", ObjectType::Airconditioner},
        {"washmachine", ObjectType::Washmachine}
    };
    auto it = m.find(s);
    return it != m.end() ? it->second : ObjectType::Unknown;
}

// 字符串转 Color
Color InstructionParser::str_to_color(const std::string& s) const {
    static std::map<std::string, Color> m = {
        {"white", Color::White}, {"black", Color::Black},
        {"yellow", Color::Yellow}, {"blue", Color::Blue},
        {"green", Color::Green}, {"red", Color::Red}
    };
    auto it = m.find(s);
    return it != m.end() ? it->second : Color::Unknown;
}

// 字符串转 ObjSize
ObjSize InstructionParser::str_to_size(const std::string& s) const {
    if (s == "small") return ObjSize::Small;
    if (s == "big") return ObjSize::Big;
    return ObjSize::Small;
}


// 解析单条规则
void InstructionParser::parse_rule(const std::string& rule_str, bool is_negated, bool is_double_neg) {
    std::string cleaned = trim(rule_str);
    if (cleaned.empty()) return;

    Rule rule;
    if (cleaned.find("(:info") == 0) {
        rule.type = RuleType::Info;
    } else if (cleaned.find("(:task") == 0) {
        rule.type = is_negated ? RuleType::TaskForbidden : RuleType::TaskAllowed;
    } else if (is_double_neg) {
        rule.type = RuleType::FactRequired;
    } else {
        return;
    }

    size_t pos = cleaned.find(' ');
    if (pos == std::string::npos) return;
    std::string content = cleaned.substr(pos + 1);
    if (!content.empty() && content.back() == ')') content.pop_back();
    content = trim(content);

    //  修复：直接对 content 调用 split_parentheses，不要加额外括号！
    std::vector<std::string> parts = split_parentheses(content);  // 不要 "(" + content + ")"

    if (!parts.empty()) {
        rule.head = parse_predicate(parts[0]);
    }
    if (parts.size() > 1) {
        rule.head.conds = parse_conditions(parts[1]);
    }

    if (is_double_neg) {
        rule.head.is_negated = true;
    }

    rules.push_back(rule);
}
// 解析整个指令字符串
void InstructionParser::parse_instructions(const std::string& ins_str) {
    rules.clear();
    std::string content = ins_str;
    size_t start = content.find(' ');
    size_t end = content.rfind(')');
    if (start == std::string::npos || end == std::string::npos || start >= end) return;

    content = content.substr(start + 1, end - start - 1);
    content = trim(content);

    std::vector<std::string> tokens = split_parentheses(content);

    for (const auto& token : tokens) {
        if (token.find("(:cons_not") == 0) {
            std::string inner = token.substr(10); // 去掉 (:cons_not
            if (!inner.empty() && inner.back() == ')') inner.pop_back();
            inner = trim(inner);

            if (inner.find("(:cons_not") == 0) {
                // 双重否定
                std::string inner2 = inner.substr(10);
                if (!inner2.empty() && inner2.back() == ')') inner2.pop_back();
                inner2 = trim(inner2);
                parse_rule(inner2, false, true);  // is_double_neg = true
            } else {
                // 单重否定 → 标记为禁止
                parse_rule(inner, true, false);   // is_negated = true
            }
        } else {
            // 普通规则 → 允许
            parse_rule(token, false, false);
        }
    }
}

// 检查任务是否被允许
bool InstructionParser::is_task_allowed(const std::string& task_name,
                                        const Object* obj,
                                        const Object* target,
                                        const Object* human) const {
    for (const auto& rule : rules) {
        if (rule.type == RuleType::TaskForbidden && rule.head.name == task_name) {
            bool matches = true;
            for (const auto& cond : rule.head.conds) {
                const Object* o = nullptr;
                if (cond.var == "X") o = obj;
                else if (cond.var == "Y") o = target;
                else if (cond.var == "human") o = human;
                else continue;

                if (!o) { matches = false; break; }

                if (cond.attr == "sort" && str_to_object_type(cond.value) != o->type) {
                    matches = false; break;
                } else if (cond.attr == "color" && str_to_color(cond.value) != o->color) {
                    matches = false; break;
                } else if (cond.attr == "size" && str_to_size(cond.value) != o->size) {
                    matches = false; break;
                }
            }
            if (matches) return false; // 找到匹配的禁止规则
        }
    }
    return true; // 没有禁止规则 → 允许
}

// 检查事实是否必须成立
bool InstructionParser::is_fact_required(const std::string& fact_name,
                                         const Object* obj,
                                         const Object* target) const {
    for (const auto& rule : rules) {
        if (rule.type == RuleType::FactRequired && rule.head.name == fact_name) {
            bool matches = true;
            for (const auto& cond : rule.head.conds) {
                const Object* o = (cond.var == "X") ? obj : (cond.var == "Y") ? target : nullptr;
                if (!o) { matches = false; break; }

                if (cond.attr == "sort" && str_to_object_type(cond.value) != o->type)
                    matches = false;
                else if (cond.attr == "color" && str_to_color(cond.value) != o->color)
                    matches = false;
            }
            if (matches) return true;
        }
    }
    return false;
}




// 打印所有规则（用于调试）
void InstructionParser::print_rules() const {
    std::cout << "\n=== Loaded Rules ===\n";

    const int tag_width = 10;
    const int action_width = 20;

    for (const auto& rule : rules) {
        std::string tag;
        switch (rule.type) {
            case RuleType::Info:
                tag = "INFO";
                break;
            case RuleType::InfoForbidden:
                tag = "INFO_FORBID";
                break;
            case RuleType::TaskAllowed:
                tag = "ALLOW";
                break;
            case RuleType::TaskForbidden:
                tag = "FORBID";
                break;
            case RuleType::FactRequired:
                tag = "REQUIRE";
                break;
            default:
                tag = "UNKNOWN";
                break;
        }

        // 修复：使用 rule.head.args 构造动作
        std::string action = rule.head.name + "(";
        for (size_t i = 0; i < rule.head.args.size(); ++i) {
            action += rule.head.args[i];
            if (i < rule.head.args.size() - 1) {
                action += ", ";
            }
        }
        action += ")";

        // 构造条件部分
        std::string condition;
        for (size_t i = 0; i < rule.head.conds.size(); ++i) {
            const auto& cond = rule.head.conds[i];
            // 这里可以优化：用 cond.var 而不是硬编码 X/Y
            condition += cond.attr + "(" + cond.var + ", " + cond.value + ")";
            if (i < rule.head.conds.size() - 1) {
                condition += ", ";
            }
        }

        // 输出对齐
        std::cout << "[" << std::left << std::setw(tag_width) << tag << "] "
                  << std::left << std::setw(action_width) << action
                  << " IF " << condition << "\n";
    }
}