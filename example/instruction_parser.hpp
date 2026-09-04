// instruction_parser.hpp
#ifndef INSTRUCTION_PARSER_HPP_
#define INSTRUCTION_PARSER_HPP_

#include "environment_manager.hpp"
#include <string>
#include <vector>
#include <map>
#include <regex>
#include <functional>

// 表示一个物体属性条件，例如 (sort X book) 或 (color X green)
struct Condition {
    std::string var;        // 变量名，如 "X", "Y"
    std::string attr;       // 属性：sort, color, size 等
    std::string value;      // 值：book, green, big 等
};

// 表示一个规则中的谓词，如 (puton X Y) 或 (opened X)
struct Predicate {
    std::string name;               // 动作或状态名：puton, pickup, opened 等
    std::vector<std::string> args;  // 参数列表：["X", "Y"]
    std::vector<Condition> conds;   // 条件集合
    bool is_negated = false;        // 是否被 :cons_not 否定
};

// 规则类型
enum class RuleType {
    Info,           // 环境常识
    TaskAllowed,    // 允许的任务
    InfoForbidden,    
    TaskForbidden,  // 禁止的任务（来自 :cons_not）
    FactRequired    // 必须成立的事实（来自 :cons_notnot）
    
};

// 完整规则
struct Rule {
    RuleType type;
    Predicate head;
};

class InstructionParser {
private:
    std::vector<Rule> rules;

    // 工具函数
    std::string trim(const std::string& s);
    std::vector<std::string> split_parentheses(const std::string& s);
    void parse_rule(const std::string& rule_str, bool is_negated = false, bool is_double_neg = false);

    // 解析 (predicate X Y) 部分
    Predicate parse_predicate(const std::string& pred_str);
    // 解析 (:cond ...) 条件部分
    std::vector<Condition> parse_conditions(const std::string& cond_str);

    // 字符串转枚举
    
    Color str_to_color(const std::string& s) const;
    ObjSize str_to_size(const std::string& s) const;

public:
    InstructionParser() = default;
    ObjectType str_to_object_type(const std::string& s) const;

    // 主接口：解析整个 (:ins ...) 字符串
    void parse_instructions(const std::string& ins_str);

    // 查询接口
    bool is_task_allowed(const std::string& task_name,
                         const Object* obj = nullptr,
                         const Object* target = nullptr,
                         const Object* human = nullptr) const;

    bool is_fact_required(const std::string& fact_name,
                          const Object* obj = nullptr,
                          const Object* target = nullptr) const;

    // 应用常识规则到环境（如 refrigerator → closed）
    void apply_commonsense(EnvironmentManager& env_mgr) const;

    const std::vector<Rule>& get_rules() const {
    return rules;
}

    // 调试打印
    void print_rules() const;

    // ★ 约束感知: 若把物体X(属性给定)放到位置Y(sort/color), 是否违反某条
    //   cons_not(info on/inside X Y)? rel 传 "on"(puton用) 或 "inside"(putin用)。
    //   任务谓词与禁令谓词不必同名(08.xml: 禁令是info inside, 任务却是putin)。
    bool violates_info_constraint(ObjectType x_type, Color x_color,
                                  ObjectType y_type, const std::string& rel) const;

    // ★ cons_notnot 感知: 把物体X从位置 old_loc 搬走是否破坏某条 FactRequired
    //   (must be on/inside 锁定)? 若任务目标就是锁定位置则允许(new_loc==锁定)。
    bool breaks_required_fact(ObjectType x_type, Color x_color,
                              ObjectType new_loc_type) const;
};

#endif // INSTRUCTION_PARSER_H