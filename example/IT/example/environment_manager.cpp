#include "environment_manager.hpp"
#include <iostream>
#include <algorithm>
#include "cserver/plug.hpp"

// 声明 AskLoc 函数（如果未在 plug.hpp 中声明）


void Object::print() const {
    std::cout << "Obj(id=" << id
              << ", type=";
    switch (type) {
        case ObjectType::Book: std::cout << "book"; break;
        case ObjectType::Can: std::cout << "can"; break;
        case ObjectType::Bottle: std::cout << "bottle"; break;
        case ObjectType::Cup: std::cout << "cup"; break;
        case ObjectType::RemoteControl: std::cout << "remote"; break;
        case ObjectType::Desk: std::cout << "desk"; break;
        case ObjectType::Television: std::cout << "television"; break;
        case ObjectType::Chair: std::cout << "chair"; break;
        case ObjectType::Bed: std::cout << "bed"; break;
        case ObjectType::Refrigerator: std::cout << "refrigerator"; break;
        case ObjectType::Closet: std::cout << "closet"; break;
        case ObjectType::Cupboard: std::cout << "cupboard"; break;
        case ObjectType::Microwave: std::cout << "microwave"; break;
        case ObjectType::Sofa: std::cout << "sofa"; break;
        case ObjectType::Table: std::cout << "table"; break;
        case ObjectType::Robot: std::cout << "robot"; break;
        case ObjectType::Human: std::cout << "human"; break;
        case ObjectType::Plant: std::cout << "plant"; break;
        case ObjectType::Couch: std::cout << "couch"; break;
        case ObjectType::Workspace: std::cout << "workspace"; break;
        case ObjectType::Worktable: std::cout << "worktable"; break;
        case ObjectType::Teapoy: std::cout << "teapoy"; break;
        case ObjectType::Airconditioner: std::cout << "aerconditioner"; break;
        case ObjectType::Washmachine: std::cout << "washmachine"; break;
        default: std::cout << "unknown"; break;
    }
    std::cout << ", size=" << (size == ObjSize::Small ? "small" : "big")
              << ", loc=" << (valid_at ? std::to_string(at) : "N/A")
              << ", inside=" << (valid_inside ? std::to_string(inside) : "N/A")
              << ", color=" << color_to_str(color)
              << ", container=" << (is_container ? (state == ContainerState::Opened ? "opened" : "closed") : "no")
              << ", held=" << (held_by_robot ? "yes" : "no")
              << ")\n";
}

std::string color_to_str(Color c) {
    switch (c) {
        case Color::Red: return "red";
        case Color::Green: return "green";
        case Color::Blue: return "blue";
        case Color::Yellow: return "yellow";
        case Color::White: return "white";
        case Color::Black: return "black";
        default: return "unknown";
    }
}

ObjectType EnvironmentManager::str_to_type(const std::string& s) {
    if (s == "robot") return ObjectType::Robot;
    else if (s == "human") return ObjectType::Human;
    else if (s == "book") return ObjectType::Book;
    else if (s == "can") return ObjectType::Can;
    else if (s == "remotecontrol") return ObjectType::RemoteControl;
    else if (s == "bottle") return ObjectType::Bottle;
    else if (s == "cup") return ObjectType::Cup;
    else if (s == "desk") return ObjectType::Desk;
    else if (s == "television") return ObjectType::Television;
    else if (s == "chair") return ObjectType::Chair;
    else if (s == "bed") return ObjectType::Bed;
    else if (s == "refrigerator") return ObjectType::Refrigerator;
    else if (s == "closet") return ObjectType::Closet;
    else if (s == "cupboard") return ObjectType::Cupboard;
    else if (s == "microwave") return ObjectType::Microwave;
    else if (s == "sofa") return ObjectType::Sofa;
    else if (s == "table") return ObjectType::Table;
    else if (s == "plant") return ObjectType::Plant;
    else if (s == "couch") return ObjectType::Couch;
    else if (s == "workspace") return ObjectType::Workspace;
    else if (s == "worktable") return ObjectType::Worktable;
    else if (s == "teapoy") return ObjectType::Teapoy;
    else if (s == "airconditioner") return ObjectType::Airconditioner;
    else if (s == "washmachine") return ObjectType::Washmachine;
    return ObjectType::Unknown;
}

Color EnvironmentManager::str_to_color(const std::string& s) {
    if (s == "red") return Color::Red;
    else if (s == "green") return Color::Green;
    else if (s == "blue") return Color::Blue;
    else if (s == "yellow") return Color::Yellow;
    else if (s == "white") return Color::White;
    else if (s == "black") return Color::Black;
    return Color::Unknown;
}

ObjSize EnvironmentManager::str_to_size(const std::string& s) {
    return s == "small" ? ObjSize::Small : ObjSize::Big;
}

void EnvironmentManager::init_robot() {
    Object rob;
    rob.id = 0;
    rob.type = ObjectType::Robot;
    rob.size = ObjSize::Big;
    objects[0] = rob;
}

std::vector<std::string> EnvironmentManager::tokenize(const std::string& s) {
    std::vector<std::string> tokens;
    std::string token;
    for (char c : s) {
        if (c == '(' || c == ')' || std::isspace(c)) {
            if (!token.empty()) {
                tokens.push_back(token);
                token.clear();
            }
        } else {
            token += c;
        }
    }
    if (!token.empty()) {
        tokens.push_back(token);
    }
    return tokens;
}

std::vector<std::string> extract_parentheses_expressions(const std::string& input) {
    // std::cout << "[EXTRACT-FUNCTION] INPUT = \"" << input.substr(0, 50) << "...\"\n";
    std::vector<std::string> expressions;
    int depth = 0;
    size_t start = std::string::npos;

    for (size_t i = 0; i < input.length(); ++i) {
        char c = input[i];
        if (c == '(') {
            if (depth == 0) {
                start = i; // 记录最外层 '(' 的位置
            }
            depth++;
        } else if (c == ')') {
            if (depth > 0) {
                depth--;
                if (depth == 0 && start != std::string::npos) {
                    // 提取从 start 到当前 ')' 的完整表达式
                    expressions.push_back(input.substr(start, i - start + 1));
                    start = std::string::npos;
                }
            }
        }
    }

    return expressions;
}


void EnvironmentManager::parse_predicate(const std::vector<std::string>& tokens) {
    if (tokens.empty()) return;
    std::string pred = tokens[0];

    if (pred == "sort" && tokens.size() >= 3) {
        int id = std::stoi(tokens[1]);
        ObjectType type = str_to_type(tokens[2]);

        if (objects.find(id) == objects.end()) {
        Object obj;
        obj.id = id;
        obj.type = type;
        obj.size = ObjSize::Small;
        obj.color = Color::Unknown;
        obj.is_container = false;
        obj.state = ContainerState::Unknown;
        obj.valid_at = false;
        obj.valid_inside = false;
        obj.on_plate = false;

        //  关键修复：如果这个物体是机器人当前手持的，标记它
        if (id == held_object) {
            obj.held_by_robot = true;
        } else {
            obj.held_by_robot = false;
        }

        objects[id] = obj;
        } else {
            objects[id].type = type;
        }
    }

    else if (pred == "size" && tokens.size() >= 3) {
        int id = std::stoi(tokens[1]);
        ObjSize size = str_to_size(tokens[2]);
        if (objects.find(id) != objects.end()) {
            objects[id].size = size;
        }
    }

    else if (pred == "at" && tokens.size() >= 3) {
        int id = std::stoi(tokens[1]);
        int loc = std::stoi(tokens[2]);
        if (id == 0) {
            robot_location = loc;
        } else {
            auto& obj = objects[id];
            obj.at = loc;
            obj.valid_at = true;
        }
    }

    else if (pred == "inside" && tokens.size() >= 3) {
        int obj_id = std::stoi(tokens[1]);
        int container_id = std::stoi(tokens[2]);
        auto& obj = objects[obj_id];
        obj.inside = container_id;
        obj.valid_inside = true;
    }

    else if (pred == "color" && tokens.size() >= 3) {
        int id = std::stoi(tokens[1]);
        Color color = str_to_color(tokens[2]);
        if (objects.find(id) != objects.end()) {
            objects[id].color = color;
        }
    }

   else if (pred == "hold" && tokens.size() >= 2) {
    int obj_id = std::stoi(tokens[1]);

    // 🔧 修复：如果 obj_id == 0，表示手上没东西，设置为 -1
    if (obj_id == 0) {
        //cout << "[HOLD] hold(0) detected: robot is not holding anything." << endl;
        held_object = -1;  //  用 -1 表示“空手”
        
        // 可选：遍历所有物体，清除 held_by_robot 标记
        for (auto& pair : objects) {
            if (pair.first != 0) {  // 排除机器人自己
                pair.second.held_by_robot = false;
            }
        }
    }
    else {
        //cout << "[HOLD] robot is holding object #" << obj_id << endl;
        held_object = obj_id;

        auto it = objects.find(obj_id);
        if (it != objects.end()) {
            it->second.held_by_robot = true;
        } else {
            //cout << "[WARNING] Object #" << obj_id << " not found, cannot set held_by_robot." << endl;
        }

        // 可选：清除其他物体的 held_by_robot 标记
        for (auto& pair : objects) {
            if (pair.first != obj_id && pair.first != 0) {
                pair.second.held_by_robot = false;
            }
        }
    }
}

    else if (pred == "plate" && tokens.size() >= 2) {
        int obj_id = std::stoi(tokens[1]);
        plate_objects.push_back(obj_id);
        if (objects.find(obj_id) != objects.end()) {
            objects[obj_id].on_plate = true;
        }
    }

    else if (pred == "type" && tokens.size() >= 3 && tokens[2] == "container") {
        int id = std::stoi(tokens[1]);
        if (objects.find(id) != objects.end()) {
            objects[id].is_container = true;
        }
    }

    else if (pred == "closed" && tokens.size() >= 2) {
        int id = std::stoi(tokens[1]);
        if (objects.find(id) != objects.end() && objects[id].is_container) {
            objects[id].state = ContainerState::Closed;
        }
    }

    else if (pred == "opened" && tokens.size() >= 2) {
        int id = std::stoi(tokens[1]);
        if (objects.find(id) != objects.end() && objects[id].is_container) {
            objects[id].state = ContainerState::Opened;
        }
    }

    


}

void EnvironmentManager::parse_from_domain_string(const std::string& input) {
    // std::cout << "[DEBUG] parse_from_domain_string received input:\n";
    // std::cout << "=== BEGIN INPUT ===\n" << input << "\n=== END INPUT ===\n";

    objects.clear();
    init_robot();
    robot_location = 0;
    held_object = -1;
    plate_objects.clear();

    // 剥离外层 (:domain ...) 包装
    std::string cleaned = input;
    // 如果以 (:domain 开头，找到第一个 '(' 后的内容
if (cleaned.find("(:domain") == 0) {
    int depth = 0;
    for (size_t i = 0; i < cleaned.length(); ++i) {
        if (cleaned[i] == '(') {
            depth++;
        } else if (cleaned[i] == ')') {
            depth--;
            if (depth == 0) {
                // 找到最外层 ')'，提取内部内容（跳过最外层括号）
                cleaned = cleaned.substr(1, i - 1); // 从索引 1 开始，长度为 i-1
                break;
            }
        }
    }
}

    // std::cout << "[CLEANED] After stripping domain: " << cleaned << "\n";

    // 提取所有最外层括号表达式
    auto expressions = extract_parentheses_expressions(cleaned);

    // std::cout << "[EXTRACT] Extracted " << expressions.size() << " expressions:\n";
    for (size_t i = 0; i < expressions.size(); ++i) {
       // std::cout << "  [" << i << "] " << expressions[i] << "\n";
    }

    for (const auto& expr : expressions) {
        auto tokens = tokenize(expr);

        // std::cout << "[TOKENIZE] '" << expr << "' -> ";
        for (const auto& t : tokens) {
            // std::cout << t << " ";
        }
        // std::cout << "\n";

        if (!tokens.empty()) {
            parse_predicate(tokens);
        }
    }

    // std::cout << "[STATE] After parsing: held_object = " << held_object << "\n";
}

// 查询接口实现
const Object* EnvironmentManager::get_object(int id) const {
    auto it = objects.find(id);
    return it != objects.end() ? &(it->second) : nullptr;
}

int EnvironmentManager::get_object_location(int id) const {
    const Object* obj = get_object(id);
    if (!obj) return -1;
    if (obj->valid_inside) return obj->inside;
    if (obj->valid_at) return obj->at;
    return -1;
}

bool EnvironmentManager::is_inside_container(int obj_id, int container_id) const {
    const Object* obj = get_object(obj_id);
    return obj && obj->valid_inside && obj->inside == container_id;
}

ContainerState EnvironmentManager::get_container_state(int container_id) const {
    const Object* obj = get_object(container_id);
    if (obj && obj->is_container) {
        return obj->state;
    }
    return ContainerState::Unknown;
}

Color EnvironmentManager::get_object_color(int id) const {
    const Object* obj = get_object(id);
    return obj ? obj->color : Color::Unknown;
}

void EnvironmentManager::print_all() const {
    std::cout << "[print_all] held_object = " << held_object << "\n";
    std::cout << "=== Environment State ===\n";
    std::cout << "Robot: loc=" << robot_location
              << ", hold=" << (held_object != -1 ? std::to_string(held_object) : "none")
              << ", plate=[";
    for (size_t i = 0; i < plate_objects.size(); ++i) {
        if (i > 0) std::cout << ",";
        std::cout << plate_objects[i];
    }
    std::cout << "]\n";

    for (const auto& [id, obj] : objects) {
        if (id == 0) continue; // robot 已打印
        obj.print();
    }
}

void EnvironmentManager::print_object(int id) const {
    const Object* obj = get_object(id);
    if (obj) obj->print();
    else std::cout << "Object " << id << " not found.\n";
}

void EnvironmentManager::update_from_askloc(const std::string& result) {
    if (result == "not_known" || result.empty()) {
        std::cout << "[Env] AskLoc 返回 unknown 或空，跳过。\n";
        return;
    }

    std::string s = result;
    // 去除首尾空格（可选）
    auto start = s.find_first_not_of(" \t\r\n");
    auto end = s.find_last_not_of(" \t\r\n");
    if (start == std::string::npos) return;
    s = s.substr(start, end - start + 1);

    // 检查是否以 "at(" 开头，以 ")" 结尾
    if (s.length() < 5 || s.substr(0, 3) != "at(" || s.back() != ')') {
        std::cout << "[Env] 格式错误，期望 at(id1,id2)：'" << result << "'" << std::endl;
        return;
    }

    // 去掉 "at(" 和 ")"
    std::string body = s.substr(3, s.length() - 4); // 从第3个字符开始，长度为总长-4

    // 查找逗号
    auto comma = body.find(',');
    if (comma == std::string::npos) {
        std::cout << "[Env] 缺少逗号：'" << result << "'" << std::endl;
        return;
    }

    std::string str_obj_id = body.substr(0, comma);
    std::string str_loc_id = body.substr(comma + 1);

   // 去除空格的 lambda，显式返回 std::string
auto trim = [](const std::string& str) -> std::string {
    auto start = str.find_first_not_of(" \t");
    auto end = str.find_last_not_of(" \t");
    if (start == std::string::npos) return "";
    return str.substr(start, end - start + 1);
};


    str_obj_id = trim(str_obj_id);
    str_loc_id = trim(str_loc_id);

    // 转数字
    int obj_id, loc_id;
    try {
        obj_id = std::stoi(str_obj_id);
        loc_id = std::stoi(str_loc_id);
    } catch (...) {
        std::cout << "[Env] 数字解析失败：obj_id='" << str_obj_id << "', loc_id='" << str_loc_id << "'" << std::endl;
        return;
    }

    // 查找物体
    auto it = objects.find(obj_id);
    if (it == objects.end()) {
        std::cout << "[Env] 错误：未找到物体 " << obj_id << std::endl;
        return;
    }

    Object& obj = it->second;
    obj.at = loc_id;
    obj.valid_at = true;

    std::cout << "[Env] 成功更新: obj" << obj_id << " 的位置为 " << loc_id << std::endl;
    obj.print();
}

// environment_manager.cpp

void EnvironmentManager::update_after_pickup(int obj_id) {
    auto it = objects.find(obj_id);
    if (it != objects.end()) {
        it->second.valid_inside = false;  // 不再在容器内
        it->second.valid_at = false;     // 不再在某个位置
        it->second.held_by_robot = true;
    }
    held_object = obj_id;
}

void EnvironmentManager::update_after_putdown(int obj_id) {
    auto it = objects.find(obj_id);
    if (it != objects.end()) {
        it->second.at = robot_location;
        it->second.valid_at = true;
        it->second.held_by_robot = false;
    }
    held_object = -1;
}

void EnvironmentManager::update_after_puton(int obj_id, int surface_id) {
    auto it = objects.find(obj_id);
    if (it != objects.end()) {
        it->second.at = get_object_location(surface_id);  // 放在 surface 上
        it->second.valid_at = true;
        it->second.held_by_robot = false;
    }
    held_object = -1;
}

void EnvironmentManager::update_after_putin(int obj_id, int container_id) {
    auto it = objects.find(obj_id);
    if (it != objects.end()) {
        it->second.inside = container_id;
        it->second.valid_inside = true;
        it->second.held_by_robot = false;
    }
    held_object = -1;
}

void EnvironmentManager::update_after_takeout(int obj_id, int container_id) {
    auto it = objects.find(obj_id);
    if (it != objects.end()) {
        it->second.inside = -1;
        it->second.valid_inside = false;
        it->second.held_by_robot = true;
    }
    held_object = obj_id;
}

void EnvironmentManager::update_after_move(int loc) {
    robot_location = loc;
}

void EnvironmentManager::update_after_open(int container_id) {
    auto it = objects.find(container_id);
    if (it != objects.end() && it->second.is_container) {
        it->second.state = ContainerState::Opened;
    }
}

void EnvironmentManager::update_after_close(int container_id) {
    auto it = objects.find(container_id);
    if (it != objects.end() && it->second.is_container) {
        it->second.state = ContainerState::Closed;
    }
}

int EnvironmentManager::get_object_container_id(int obj_id) const {
    auto it = objects.find(obj_id);
    if (it != objects.end()) {
        return it->second.inside; // inside 字段
    }
    return -1;
}

// 查询 human 的位置
int EnvironmentManager::get_entity_location(const std::string& entity_name) {
    if (entity_name == "human" || entity_name == "user" || entity_name == "person") {
        return get_object_location(1); // 假设你有一个字段存储用户位置
    }
    return -1;
}

