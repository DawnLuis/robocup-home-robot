#include "devil.hpp"
#include <iostream>
#include <stack>
#include <queue>
#include <algorithm>
#include "environment_manager.hpp"
#include "instruction_parser.hpp"
#include "nlu.h"

using namespace _home;
using namespace std;



//////////////////////////////////////////////////////////////////////////
Devil::Devil() :
    Plug("Dawnluis")
{      
}

//////////////////////////////////////////////////////////////////////////
Color Devil::get_color_from_string(const std::string& color_str) const {
    if (color_str == "white") return Color::White;
    if (color_str == "black") return Color::Black;
    if (color_str == "yellow") return Color::Yellow;
    if (color_str == "blue") return Color::Blue;
    if (color_str == "green") return Color::Green;
    if (color_str == "red") return Color::Red;
    return Color::Unknown;
}




void Devil::Plan()
{
    // 环境与解析器
    EnvironmentManager env;
    InstructionParser ins_parser;

    string envDes = GetEnvDes(); // 获取场景描述
    cout << "=== 当前环境描述 (Environment Description) ===" << endl;
    cout << envDes << endl;
    cout << "=============================================" << endl;
    env.parse_from_domain_string(envDes);
    env.print_all();

    //string taskDes = GetTaskDes(); // 获取任务描述
    std::string natural_lang = GetTaskDes(); // 获取自然语言任务描述
    std::string  taskDes= SimpleNLU().parse(natural_lang);
    cout << "=== 当前任务描述 (Task Description) ===" << endl;
    cout << natural_lang << endl;
    cout << "转换为结构化任务描述:" << endl;
    cout << taskDes << endl;
    cout << "=============================================" << endl;
    
    ins_parser.parse_instructions(taskDes);
    ins_parser.print_rules();

    cout << "\n=== 开始任务规划与执行 ===" << endl;

    // 任务分组和优先级排序
    vector<Rule> tasks;
    vector<Rule> state_tasks; // opened/closed 状态任务
    
    for (const auto& rule : ins_parser.get_rules()) {
        if (rule.type == RuleType::TaskAllowed) {
            // 将状态任务分开处理
            if (rule.head.name == "opened" || rule.head.name == "closed") {
                state_tasks.push_back(rule);
            } else {
                tasks.push_back(rule);
            }
        }
    }

    // 执行状态任务（优先执行）
    for (const auto& rule : state_tasks) {
        execute_state_task(env, rule);
    }

    // 执行主要任务
    for (const auto& rule : tasks) {
        if (!execute_task_with_constraints(env, ins_parser, rule)) {
            cout << "任务 '" << rule.head.name << "' 执行失败。" << endl;
        }
    }

    cout << "所有任务执行完成。" << endl;
}

// 执行状态任务（opened/closed）
bool Devil::execute_state_task(EnvironmentManager& env, const Rule& rule) {
    const Predicate& task = rule.head;
    cout << "执行状态任务: " << task.name << "(";
    for (size_t i = 0; i < task.args.size(); ++i) {
        if (i > 0) cout << ",";
        cout << task.args[i];
    }
    cout << ")" << endl;

    int container_id = -1;
    for (const auto& cond : task.conds) {
        if (cond.var == "X") {
            ObjectType type = ins_parser.str_to_object_type(cond.value);
            container_id = find_object_by_type(env, type);
            break;
        }
    }
    
    if (container_id == -1) {
        cout << "  错误: 无法找到容器。" << endl;
        return false;
    }

    const Object* container = env.get_object(container_id);
    if (!container || !container->is_container) {
        cout << "  错误: 物体 #" << container_id << " 不是容器。" << endl;
        return false;
    }

    // 移动到容器位置
    int container_loc = env.get_object_location(container_id);
    if (container_loc == -1) {
        cout << "  错误: 无法确定容器位置。" << endl;
        return false;
    }
    
    int robot_loc = env.get_robot_location();
    if (robot_loc != container_loc) {
        cout << "  移动机器人到容器位置 " << container_loc << endl;
        if (!Move(container_loc)) {
            cout << "  移动失败！" << endl;
            return false;
        }
        env.update_after_move(container_loc);
    }

    // 确保空手
    if (env.is_holding()) {
        int held_id = env.get_held_object();
        cout << "  机器人手持物体 #" << held_id << "，先放下。" << endl;
        PutDown(held_id);
        env.update_after_putdown(held_id);
    }

    bool success = false;
    if (task.name == "opened") {
        ContainerState state = env.get_container_state(container_id);
        if (state == ContainerState::Opened) {
            cout << "  容器 #" << container_id << " 已经打开。" << endl;
            success = true;
        } else {
            success = Open(container_id);
            if (success) {
                cout << "  成功打开容器 #" << container_id << endl;
                env.update_after_open(container_id);
            } else {
                cout << "  打开容器失败！" << endl;
            }
        }
    }
    else if (task.name == "closed") {
        ContainerState state = env.get_container_state(container_id);
        if (state == ContainerState::Closed) {
            cout << "  容器 #" << container_id << " 已经关闭。" << endl;
            success = true;
        } else {
            success = Close(container_id);
            if (success) {
                cout << "  成功关闭容器 #" << container_id << endl;
                env.update_after_close(container_id);
            } else {
                cout << "  关闭容器失败！" << endl;
            }
        }
    }
    
    return success;
}

// 带约束检查的任务执行
bool Devil::execute_task_with_constraints(EnvironmentManager& env, InstructionParser& ins_parser, const Rule& rule) {
    const Predicate& task = rule.head;

    cout << "分析任务: " << task.name << "(";
    for (size_t i = 0; i < task.args.size(); ++i) {
        if (i > 0) cout << ",";
        cout << task.args[i];
    }
    cout << ")" << endl;

    // 检查约束
    if (!check_constraints(env, ins_parser, task)) {
        cout << "  任务违反约束，跳过执行。" << endl;
        return false;
    }

    // 根据任务类型执行
    if (task.name == "pickup") {
        return execute_pickup_task(env, task);
    }
    else if (task.name == "putdown") {
        return execute_putdown_task(env, task);
    }
    else if (task.name == "puton") {
        return execute_puton_task(env, task);
    }
    else if (task.name == "putin") {
        return execute_putin_task(env, task);
    }
    else if (task.name == "goto") {
        return execute_goto_task(env, task);
    }
    else if (task.name == "give") {
        return execute_give_task(env, task);
    }
    else if (task.name == "takeout") {
        return execute_takeout_task(env, task);
    }
    else if (task.name == "close") {
        return execute_close_task(env, task);
    }
    else if (task.name == "opened") {
        return execute_state_task(env, rule);
    }
    else if (task.name == "closed") {
        return execute_state_task(env, rule);
    }

    cout << "  未知任务类型: " << task.name << endl;
    return false;
}

// 约束检查
bool Devil::check_constraints(EnvironmentManager& env, InstructionParser& ins_parser, const Predicate& task) {
    // 检查所有禁止性约束
    for (const auto& rule : ins_parser.get_rules()) {
        if (rule.type == RuleType::TaskForbidden) {
            // 检查任务类型和参数是否匹配禁止的约束
            if (rule.head.name == task.name) {
                bool matches = true;
                for (const auto& cond : rule.head.conds) {
                    // 这里简化约束检查，实际应该更详细
                    if (!check_condition_match(env, task, cond)) {
                        matches = false;
                        break;
                    }
                }
                if (matches) {
                    cout << "  违反禁止约束: " << rule.head.name << endl;
                    return false;
                }
            }
        }
    }
    return true;
}

// 条件匹配检查
bool Devil::check_condition_match(EnvironmentManager& env, const Predicate& task, const Condition& cond) {
    // 简化实现，实际应该根据任务参数和条件进行详细匹配
    // 这里返回true表示条件匹配，需要在实际使用中完善
    return true;
}

// 优化后的任务执行函数
bool Devil::execute_pickup_task(EnvironmentManager& env, const Predicate& task) {
    int obj_id = -1;

    cout << "  解析pickup任务条件:" << endl;
    
    // 收集条件
    ObjectType x_type = ObjectType::Unknown;
    Color x_color = Color::Unknown;
    
    for (const auto& cond : task.conds) {
        cout << "    条件: var=" << cond.var << ", attr=" << cond.attr << ", value=" << cond.value << endl;
        
        if (cond.var == "X") {
            if (cond.attr == "sort") {
                x_type = ins_parser.str_to_object_type(cond.value);
                cout << "    X类型: " << cond.value << " -> " << static_cast<int>(x_type) << endl;
            } else if (cond.attr == "color") {
                x_color = get_color_from_string(cond.value);
                cout << "    X颜色: " << cond.value << " -> " << static_cast<int>(x_color) << endl;
            }
        }
    }

    // 使用组合条件查找物体
    if (x_type != ObjectType::Unknown) {
        cout << "    使用组合条件查找X: type=" << static_cast<int>(x_type) << ", color=" << static_cast<int>(x_color) << endl;
        obj_id = find_object_by_conditions(env, x_type, x_color);
    }
    
    if (obj_id == -1) {
        cout << "  错误: 未找到可拿起的物体。" << endl;
        return false;
    }

    return execute_pickup(env, obj_id);
}

bool Devil::execute_putdown_task(EnvironmentManager& env, const Predicate& task) {
    int target_obj_id = -1;
    for (const auto& cond : task.conds) {
        if (cond.var == "X") {
            ObjectType type = ins_parser.str_to_object_type(cond.value);
            target_obj_id = find_object_by_type(env, type);
            break;
        }
    }

    if (target_obj_id == -1) {
        cout << "  错误: 未找到目标物体。" << endl;
        return false;
    }

    int held_id = env.get_held_object();
    if (held_id == target_obj_id) {
        bool success = PutDown(held_id);
        if (success) {
            cout << "  成功放下物体 #" << held_id << endl;
            env.update_after_putdown(held_id);
        }
        return success;
    } else {
        cout << "  机器人没有拿着目标物体，任务自动完成。" << endl;
        return true;
    }
}

// 改进的puton任务执行
bool Devil::execute_puton_task(EnvironmentManager& env, const Predicate& task) {
    int small_obj_id = -1;
    int big_obj_id = -1;

    cout << "  解析puton任务条件:" << endl;
    
    // 先收集所有X的条件
    ObjectType x_type = ObjectType::Unknown;
    Color x_color = Color::Unknown;
    
    // 先收集所有Y的条件
    ObjectType y_type = ObjectType::Unknown;
    
    for (const auto& cond : task.conds) {
        cout << "    条件: var=" << cond.var << ", attr=" << cond.attr << ", value=" << cond.value << endl;
        
        if (cond.var == "X") {
            if (cond.attr == "sort") {
                x_type = ins_parser.str_to_object_type(cond.value);
                cout << "    X类型: " << cond.value << " -> " << static_cast<int>(x_type) << endl;
            } else if (cond.attr == "color") {
                x_color = get_color_from_string(cond.value);
                cout << "    X颜色: " << cond.value << " -> " << static_cast<int>(x_color) << endl;
            }
        }
        else if (cond.var == "Y" && cond.attr == "sort") {
            y_type = ins_parser.str_to_object_type(cond.value);
            cout << "    Y类型: " << cond.value << " -> " << static_cast<int>(y_type) << endl;
        }
    }

    // 使用组合条件查找物体
    if (x_type != ObjectType::Unknown) {
        cout << "    使用组合条件查找X: type=" << static_cast<int>(x_type) << ", color=" << static_cast<int>(x_color) << endl;
        small_obj_id = find_object_by_conditions(env, x_type, x_color);
    }
    
    if (y_type != ObjectType::Unknown) {
        cout << "    查找Y: type=" << static_cast<int>(y_type) << endl;
        big_obj_id = find_object_by_type(env, y_type);
    }

    if (small_obj_id == -1) {
        cout << "  错误: 无法找到小物体 X。" << endl;
        return false;
    }
    if (big_obj_id == -1) {
        cout << "  错误: 无法找到大物体 Y。" << endl;
        // 额外调试：列出所有物体
        cout << "  所有物体: " << endl;
        for (const auto& pair : env.get_objects()) {
            if (pair.second.id != 0) { // 跳过机器人
                cout << "    #" << pair.first << ": type=" << static_cast<int>(pair.second.type);
                switch(pair.second.type) {
                    case ObjectType::Worktable: cout << "(worktable)"; break;
                    case ObjectType::Table: cout << "(table)"; break;
                    case ObjectType::Closet: cout << "(closet)"; break;
                    case ObjectType::Microwave: cout << "(microwave)"; break;
                    case ObjectType::Sofa: cout << "(sofa)"; break;
                    case ObjectType::Human: cout << "(human)"; break;
                    case ObjectType::Teapoy: cout << "(teapoy)"; break;
                    default: cout << "(unknown)"; break;
                }
                cout << ", loc=" << (pair.second.valid_at ? std::to_string(pair.second.at) : "N/A") << endl;
            }
        }
        return false;
    }

    cout << "  执行 puton: 将物体 #" << small_obj_id << " 放到 #" << big_obj_id << " 上" << endl;

    // 检查小物体是否在容器中
    const Object* small_obj = env.get_object(small_obj_id);
    if (small_obj->valid_inside) {
        cout << "  物体 #" << small_obj_id << " 在容器 #" << small_obj->inside << " 中，需要先取出" << endl;
        if (!execute_takeout(env, small_obj_id, small_obj->inside)) {
            cout << "  取出物体失败，无法执行 puton" << endl;
            return false;
        }
    }

    // 如果机器人已经拿着目标物体，直接执行放置
    int held_id = env.get_held_object();
    if (held_id != small_obj_id) {
        // 先放下当前手持物体（如果有）
        if (env.is_holding()) {
            cout << "  放下当前手持物体 #" << held_id << endl;
            PutDown(held_id);
            env.update_after_putdown(held_id);
        }
        
        // 拿起目标物体
        if (!execute_pickup(env, small_obj_id)) {
            return false;
        }
    }

    // 移动到目标位置
    int target_loc = env.get_object_location(big_obj_id);
    if (target_loc == -1) {
        cout << "  错误: 无法确定目标位置。" << endl;
        return false;
    }

    int robot_loc = env.get_robot_location();
    if (robot_loc != target_loc) {
        cout << "  移动机器人到位置 " << target_loc << endl;
        if (!Move(target_loc)) {
            return false;
        }
        env.update_after_move(target_loc);
    }

    // 确保机器人确实移动到了正确位置
    robot_loc = env.get_robot_location();
    if (robot_loc != target_loc) {
        cout << "  错误: 机器人位置 (" << robot_loc << ") 与目标位置 (" << target_loc << ") 不匹配！" << endl;
        return false;
    }

    // 执行放置
    bool success = PutDown(small_obj_id);
    if (success) {
        env.update_after_puton(small_obj_id, big_obj_id);
        cout << "  成功完成 puton 任务。" << endl;
    } else {
        cout << "  PutOn 失败！" << endl;
    }
    return success;
}
// 改进的putin任务执行
bool Devil::execute_putin_task(EnvironmentManager& env, const Predicate& task) {
    int obj_id = -1;
    int container_id = -1;

    cout << "  解析putin任务条件:" << endl;
    
    // 先收集所有条件
    ObjectType x_type = ObjectType::Unknown;
    Color x_color = Color::Unknown;
    ObjectType y_type = ObjectType::Unknown;
    
    for (const auto& cond : task.conds) {
        cout << "    条件: var=" << cond.var << ", attr=" << cond.attr << ", value=" << cond.value << endl;
        
        if (cond.var == "X") {
            if (cond.attr == "sort") {
                x_type = ins_parser.str_to_object_type(cond.value);
                cout << "    X类型: " << cond.value << " -> " << static_cast<int>(x_type) << endl;
            } else if (cond.attr == "color") {
                x_color = get_color_from_string(cond.value);
                cout << "    X颜色: " << cond.value << " -> " << static_cast<int>(x_color) << endl;
            }
        }
        else if (cond.var == "Y" && cond.attr == "sort") {
            y_type = ins_parser.str_to_object_type(cond.value);
            cout << "    Y类型: " << cond.value << " -> " << static_cast<int>(y_type) << endl;
        }
    }

    // 使用组合条件查找物体
    if (x_type != ObjectType::Unknown) {
        cout << "    使用组合条件查找X: type=" << static_cast<int>(x_type) << ", color=" << static_cast<int>(x_color) << endl;
        obj_id = find_object_by_conditions(env, x_type, x_color);
    }
    
    if (y_type != ObjectType::Unknown) {
        cout << "    查找Y: type=" << static_cast<int>(y_type) << endl;
        container_id = find_object_by_type(env, y_type);
    }

    if (obj_id == -1) {
        cout << "  错误: 无法找到要放入的物体 X。" << endl;
        // 额外调试：列出所有罐头
        cout << "  所有罐头物体: ";
        for (const auto& pair : env.get_objects()) {
            if (pair.second.type == ObjectType::Can) {
                cout << "#" << pair.first << "(color=" << static_cast<int>(pair.second.color) << ") ";
            }
        }
        cout << endl;
        return false;
    }
    if (container_id == -1) {
        cout << "  错误: 无法找到容器 Y。" << endl;
        return false;
    }

    cout << "  执行 putin: 将物体 #" << obj_id << " 放入 #" << container_id << endl;

    // 检查物体是否在容器中
    const Object* obj = env.get_object(obj_id);
    if (obj->valid_inside) {
        cout << "  物体 #" << obj_id << " 已在容器 #" << obj->inside << " 中" << endl;
        if (obj->inside == container_id) {
            cout << "  物体已在目标容器中，任务完成" << endl;
            return true;
        } else {
            cout << "  需要先从当前容器取出" << endl;
            if (!execute_takeout(env, obj_id, obj->inside)) {
                return false;
            }
        }
    }

    // 确保机器人拿着目标物体
    int held_id = env.get_held_object();
    if (held_id != obj_id) {
        if (env.is_holding()) {
            PutDown(held_id);
            env.update_after_putdown(held_id);
        }
        if (!execute_pickup(env, obj_id)) {
            return false;
        }
    }

    // 移动到容器位置
    int container_loc = env.get_object_location(container_id);
    if (container_loc == -1) {
        cout << "  错误: 无法确定容器位置。" << endl;
        return false;
    }

    int robot_loc = env.get_robot_location();
    if (robot_loc != container_loc) {
        cout << "  移动机器人到位置 " << container_loc << endl;
        if (!Move(container_loc)) {
            return false;
        }
        env.update_after_move(container_loc);
    }

    // 检查并打开容器
    const Object* container = env.get_object(container_id);
    if (container->state != ContainerState::Opened) {
        // 放下物体以打开容器
        if (env.is_holding()) {
            PutDown(env.get_held_object());
            env.update_after_putdown(env.get_held_object());
        }
        
        if (!Open(container_id)) {
            cout << "  打开容器失败！" << endl;
            return false;
        }
        env.update_after_open(container_id);
        
        // 重新拿起物体
        if (!execute_pickup(env, obj_id)) {
            return false;
        }
    }

    // 执行放入
    bool success = PutIn(obj_id, container_id);
    if (success) {
        env.update_after_putin(obj_id, container_id);
        cout << "  成功完成 putin 任务。" << endl;
    } else {
        cout << "  PutIn 失败，可能位置不匹配或容器已满。" << endl;
    }
    return success;
}

bool Devil::execute_goto_task(EnvironmentManager& env, const Predicate& task) {
    int target_obj_id = -1;
    for (const auto& cond : task.conds) {
        if (cond.var == "X") {
            ObjectType type = ins_parser.str_to_object_type(cond.value);
            target_obj_id = find_object_by_type(env, type);
            break;
        }
    }
    
    if (target_obj_id == -1) {
        cout << "  错误: 无法找到目标物体。" << endl;
        return false;
    }
    
    int target_loc = env.get_object_location(target_obj_id);
    if (target_loc == -1) {
        cout << "  错误: 无法确定目标位置。" << endl;
        return false;
    }

    return execute_move(env, target_loc);
}

bool Devil::execute_give_task(EnvironmentManager& env, const Predicate& task) {
    int obj_id = -1;
    for (const auto& cond : task.conds) {
        if (cond.var == "X") {
            ObjectType type = ins_parser.str_to_object_type(cond.value);
            Color color = Color::Unknown;
            for (const auto& c : task.conds) {
                if (c.var == "X" && c.attr == "color") {
                    color = env.str_to_color(c.value);
                    break;
                }
            }
            obj_id = find_object_by_conditions(env, type, color);
            break;
        }
    }

    if (obj_id == -1) {
        cout << "  错误: 无法找到要给予的物体。" << endl;
        return false;
    }

    cout << "  执行 give: 将物体 #" << obj_id << " 交给 human" << endl;

    // 确保机器人拿着目标物体
    int held_id = env.get_held_object();
    if (held_id != obj_id) {
        if (env.is_holding()) {
            PutDown(held_id);
            env.update_after_putdown(held_id);
        }
        if (!execute_pickup(env, obj_id)) {
            return false;
        }
    }

    // 移动到human位置
    int human_loc = env.get_entity_location("human");
    int robot_loc = env.get_robot_location();
    if (robot_loc != human_loc) {
        cout << "  移动机器人到用户位置 " << human_loc << endl;
        if (!Move(human_loc)) {
            return false;
        }
        env.update_after_move(human_loc);
    }

    // 执行给予（放下）
    bool success = PutDown(obj_id);
    if (success) {
        env.update_after_putdown(obj_id);
        cout << "  成功完成 give 任务。" << endl;
    }
    return success;
}

bool Devil::execute_takeout_task(EnvironmentManager& env, const Predicate& task) {
    int obj_id = -1;
    int container_id = -1;

    for (const auto& cond : task.conds) {
        if (cond.var == "X") {
            ObjectType type = ins_parser.str_to_object_type(cond.value);
            Color color = Color::Unknown;
            for (const auto& c : task.conds) {
                if (c.var == "X" && c.attr == "color") {
                    color = env.str_to_color(c.value);
                    break;
                }
            }
            obj_id = find_object_by_conditions(env, type, color);
        }
        else if (cond.var == "Y") {
            ObjectType type = ins_parser.str_to_object_type(cond.value);
            container_id = find_object_by_type(env, type);
        }
    }

    if (obj_id == -1 || container_id == -1) {
        cout << "  错误: 无法找到任务所需的物体。" << endl;
        return false;
    }

    return execute_takeout(env, obj_id, container_id);
}

bool Devil::execute_close_task(EnvironmentManager& env, const Predicate& task) {
    int container_id = -1;
    for (const auto& cond : task.conds) {
        if (cond.var == "X") {
            ObjectType type = ins_parser.str_to_object_type(cond.value);
            container_id = find_object_by_type(env, type);
            break;
        }
    }
    
    if (container_id == -1) {
        cout << "  错误: 无法找到容器。" << endl;
        return false;
    }

    const Object* container = env.get_object(container_id);
    if (!container || !container->is_container) {
        cout << "  错误: 物体 #" << container_id << " 不是容器。" << endl;
        return false;
    }

    // 移动到容器位置
    int container_loc = env.get_object_location(container_id);
    if (container_loc == -1) {
        cout << "  错误: 无法确定容器位置。" << endl;
        return false;
    }
    
    int robot_loc = env.get_robot_location();
    if (robot_loc != container_loc) {
        cout << "  移动机器人到容器位置 " << container_loc << endl;
        if (!Move(container_loc)) {
            cout << "  移动失败！" << endl;
            return false;
        }
        env.update_after_move(container_loc);
    }

    // 确保空手
    if (env.is_holding()) {
        int held_id = env.get_held_object();
        cout << "  机器人手持物体 #" << held_id << "，先放下。" << endl;
        PutDown(held_id);
        env.update_after_putdown(held_id);
    }

    ContainerState state = env.get_container_state(container_id);
    if (state == ContainerState::Closed) {
        cout << "  容器 #" << container_id << " 已经关闭。" << endl;
        return true;
    } else {
        bool success = Close(container_id);
        if (success) {
            cout << "  成功关闭容器 #" << container_id << endl;
            env.update_after_close(container_id);
        } else {
            cout << "  关闭容器失败！" << endl;
        }
        return success;
    }
}

// 改进的物体查找函数 - 修复颜色映射问题
int Devil::find_object_by_conditions(EnvironmentManager& env, ObjectType type, Color color) {
    cout << "  查找物体: type=" << static_cast<int>(type) << ", color=" << static_cast<int>(color) << endl;
    
    for (const auto& pair : env.get_objects()) {
        const Object& obj = pair.second;
        if (obj.id == 0) continue; // 跳过机器人
        
        // 跳过机器人手持的物体（除非我们就是要找手持的物体）
        if (obj.held_by_robot && obj.id != env.get_held_object()) continue;
        
        cout << "    检查物体 #" << obj.id << ": type=" << static_cast<int>(obj.type) 
             << ", color=" << static_cast<int>(obj.color) 
             << ", inside=" << (obj.valid_inside ? std::to_string(obj.inside) : "N/A")
             << ", held=" << (obj.held_by_robot ? "yes" : "no") << endl;
        
        // 类型匹配检查
        bool type_match = (obj.type == type);
        
        // 颜色匹配检查
        bool color_match = (color == Color::Unknown || obj.color == color);
        
        if (type_match && color_match) {
            cout << "    找到匹配物体 #" << obj.id << endl;
            return obj.id;
        }
    }
    cout << "  未找到匹配物体" << endl;
    return -1;
}

// 以下保留原有的辅助函数，但移除重复的Fini函数

// --- 辅助函数 ---

// 在环境中根据类型查找物体ID
int Devil::find_object_by_type(EnvironmentManager& env, ObjectType type) {
    cout << "  按类型查找: " << static_cast<int>(type) << endl;
    
    for (const auto& pair : env.get_objects()) {
        const Object& obj = pair.second;
        if (obj.id == 0) continue; // 跳过机器人
        
        cout << "    检查物体 #" << obj.id << ": type=" << static_cast<int>(obj.type) 
             << ", name=";
        
        // 添加类型名称输出以便调试
        switch(obj.type) {
            case ObjectType::Worktable: cout << "worktable"; break;
            case ObjectType::Closet: cout << "closet"; break;
            case ObjectType::Microwave: cout << "microwave"; break;
            case ObjectType::Sofa: cout << "sofa"; break;
            case ObjectType::Human: cout << "human"; break;
            case ObjectType::Teapoy: cout << "teapoy"; break;
            case ObjectType::Cup: cout << "cup"; break;
            case ObjectType::Bottle: cout << "bottle"; break;
            case ObjectType::Book: cout << "book"; break;
            case ObjectType::Plant: cout << "plant"; break;
            default: cout << "unknown(" << static_cast<int>(obj.type) << ")"; break;
        }
        cout << endl;
        
        if (obj.type == type) {
            cout << "    找到匹配物体 #" << obj.id << endl;
            return obj.id;
        }
    }
    cout << "  未找到类型为 " << static_cast<int>(type) << " 的物体" << endl;
    return -1;
}

// 执行 pickup 动作的完整流程
// 改进的pickup函数 - 添加更多调试信息
bool Devil::execute_pickup(EnvironmentManager& env, int obj_id) {
    const Object* obj = env.get_object(obj_id);
    if (!obj) {
        cout << "  错误: 物体 #" << obj_id << " 不存在。" << endl;
        return false;
    }

    cout << "  执行 pickup 物体 #" << obj_id << " (type=" << static_cast<int>(obj->type) 
         << ", color=" << static_cast<int>(obj->color) 
         << ", at=" << (obj->valid_at ? std::to_string(obj->at) : "N/A")
         << ", inside=" << (obj->valid_inside ? std::to_string(obj->inside) : "N/A") << ")" << endl;

    // 如果手持物体，先放下
    if (env.is_holding()) {
        int held_id = env.get_held_object();
        cout << "  机器人已持物 #" << held_id << "，执行 PutDown" << endl;
        bool putdown_success = PutDown(held_id);
        if (putdown_success) {
            env.update_after_putdown(held_id);
            cout << "  成功放下物体 #" << held_id << endl;
        } else {
            cout << "  放下物体失败！" << endl;
            return false;
        }
    }

    // 检查物体是否在容器中
    int container_id = env.get_object_container_id(obj_id);
    if (container_id != -1) {
        cout << "  物体 #" << obj_id << " 在容器 #" << container_id << " 中" << endl;
        const Object* container = env.get_object(container_id);
        if (!container || !container->is_container) {
            cout << "  错误: 物体 #" << obj_id << " 所在容器 #" << container_id << " 无效。" << endl;
            return false;
        }

        // 获取容器所在位置
        int container_loc = env.get_object_location(container_id);
        if (container_loc == -1) {
            cout << "  容器 #" << container_id << " 位置未知。" << endl;
            return false;
        }

        // 移动到容器位置
        int robot_loc = env.get_robot_location();
        if (robot_loc != container_loc) {
            cout << "  移动机器人到位置 " << container_loc << " 以访问容器 #" << container_id << endl;
            if (!Move(container_loc)) {
                cout << "  移动失败！" << endl;
                return false;
            }
            env.update_after_move(container_loc);
        }

        // 打开容器（如需要）
        ContainerState state = env.get_container_state(container_id);
        if (state == ContainerState::Closed) {
            cout << "  打开容器 #" << container_id << endl;
            if (!Open(container_id)) {
                cout << "  打开容器失败！" << endl;
                return false;
            }
            env.update_after_open(container_id);
        }

        // 执行 TakeOut
        cout << "  执行 TakeOut: 从容器 #" << container_id << " 中取出 #" << obj_id << endl;
        bool success = TakeOut(obj_id, container_id);
        if (success) {
            env.update_after_takeout(obj_id, container_id);
            cout << "  成功取出物体 #" << obj_id << endl;
            return true;
        } else {
            cout << "  TakeOut 失败！" << endl;
            return false;
        }
    }

    // 物体在地面上
    int loc = env.get_object_location(obj_id);
    if (loc == -1) {
        cout << "  物体位置未知，使用 AskLoc 查询..." << endl;
        string loc_info = AskLoc(obj_id);
        if (loc_info == "not_known" || loc_info.empty()) {
            cout << "  AskLoc 返回未知位置。" << endl;
            return false;
        }
        env.update_from_askloc(loc_info);
        loc = env.get_object_location(obj_id);
        if (loc == -1) {
            cout << "  仍然无法确定物体位置。" << endl;
            return false;
        }
    }

    cout << "  物体 #" << obj_id << " 在位置 " << loc << endl;
    int robot_loc = env.get_robot_location();
    if (robot_loc != loc) {
        cout << "  移动机器人到位置 " << loc << " (当前在 " << robot_loc << ")" << endl;
        if (!Move(loc)) {
            cout << "  移动失败！" << endl;
            return false;
        }
        env.update_after_move(loc);
    }

    cout << "  执行 PickUp 操作..." << endl;
    bool success = PickUp(obj_id);
    if (success) {
        env.update_after_pickup(obj_id);
        cout << "  成功拿起物体 #" << obj_id << endl;
    } else {
        cout << "  PickUp 操作失败！" << endl;
        // 额外调试信息
        cout << "  调试信息 - 机器人位置: " << env.get_robot_location() 
             << ", 物体位置: " << loc 
             << ", 是否手持: " << (env.is_holding() ? "是" : "否") << endl;
    }
    return success;
}

// 执行 move 动作
bool Devil::execute_move(EnvironmentManager& env, int target_loc) {
    int robot_loc = env.get_robot_location();
    if (robot_loc == target_loc) {
        cout << "  机器人已在目标位置 " << target_loc << "。" << endl;
        return true;
    }

    cout << "  执行 Move 机器人到位置 " << target_loc << endl;
    return Move(target_loc);
}

// 执行 takeout 动作
bool Devil::execute_takeout(EnvironmentManager& env, int small_obj_id, int container_id) {
    const Object* container = env.get_object(container_id);
    if (!container || !container->is_container) return false;

    cout << "  执行 TakeOut: 从容器 #" << container_id << " 中取出 #" << small_obj_id << endl;

    // 检查物体是否真的在容器中
    if (!env.is_inside_container(small_obj_id, container_id)) {
        cout << "  错误: 物体 #" << small_obj_id << " 不在容器 #" << container_id << " 中！" << endl;
        return false;
    }

    // 检查容器状态
    ContainerState state = env.get_container_state(container_id);
    if (state != ContainerState::Opened) {
        cout << "  错误: 容器 #" << container_id << " 未打开！当前状态: " << (state == ContainerState::Closed ? "closed" : "unknown") << endl;
        return false;
    }

    bool success = TakeOut(small_obj_id, container_id);
    if (success) {
        env.update_after_takeout(small_obj_id, container_id);
        cout << "  成功取出物体 #" << small_obj_id << endl;
    } else {
        cout << "  TakeOut 失败！可能物体不在容器中或机械臂无法到达。" << endl;
        
        // 额外调试：显示容器内所有物体
        cout << "  调试信息 - 容器 #" << container_id << " 内的物体: ";
        for (const auto& obj_pair : env.get_objects()) {
            if (obj_pair.second.valid_inside && obj_pair.second.inside == container_id) {
                cout << "#" << obj_pair.first << " ";
            }
        }
        cout << endl;
    }

    return success;
}

void Devil::Fini()
{
    cout << "#(Dawnluis): Fini" << endl;
}