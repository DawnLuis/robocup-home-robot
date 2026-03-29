#ifndef ENVIRONMENT_MANAGER_HPP_
#define ENVIRONMENT_MANAGER_HPP_

#include <string>
#include <map>
#include <vector>
#include <sstream>
#include <regex>

enum class ObjSize { Small, Big };
enum class ObjectType {
    Robot, Human, Book, Can, RemoteControl, Bottle, Cup,
    Desk, Television, Chair, Bed, Refrigerator,
    Closet, Cupboard, Microwave, Sofa, Table,Plant,Couch,Workspace,Worktable,Teapoy,Airconditioner,Washmachine,
    Unknown
};
enum class ContainerState { Unknown, Opened, Closed };
enum class Color { White, Black, Yellow, Blue, Green, Red, Unknown };
std::string color_to_str(Color c);
struct Object {
    int id = -1;
    ObjectType type = ObjectType::Unknown;
    ObjSize size = ObjSize::Small;
    int at = -1;              // 所在位置（大物体ID）
    int inside = -1;          // 在哪个容器中
    bool valid_at = false;
    bool valid_inside = false;
    Color color = Color::Unknown;
    bool is_container = false;
    ContainerState state = ContainerState::Unknown;
    bool held_by_robot = false;     // robot 是否拿着它
    bool on_plate = false;    // 是否在 robot 的盘子里

    void print() const;
};

class EnvironmentManager {
private:
    std::map<int, Object> objects;
    int robot_id = 0;
    int robot_location = 0;
    int held_object = -1;
    int user_location = 1; // 假设用户在位置1

    std::vector<int> plate_objects;

    
public:
    EnvironmentManager() { init_robot(); }

    const std::map<int, Object>& get_objects() const {
        return objects;
    }
    ObjectType str_to_type(const std::string& s);
    Color str_to_color(const std::string& s);
    ObjSize str_to_size(const std::string& s);
    int get_object_container_id(int obj_id) const;
    
    void update_after_pickup(int obj_id);
    void update_after_putdown(int obj_id);
    void update_after_puton(int obj_id, int surface_id);
    void update_after_putin(int obj_id, int container_id);
    void update_after_takeout(int obj_id, int container_id);
    void update_after_move(int loc);
    void update_after_open(int container_id);
    void update_after_close(int container_id);

    void set_container_state(int obj_id, ContainerState state) {
    auto it = objects.find(obj_id);
    if (it != objects.end() && it->second.is_container) {
        it->second.state = state;
    }
}

    // 主接口：解析来自仿真平台的字符串
    void parse_from_domain_string(const std::string& input);

    // 查询接口（供任务规划使用）
    int get_robot_location() const { return robot_location; }
    int get_entity_location(const std::string& entity_name);
    int get_held_object() const { return held_object; }
    const std::vector<int>& get_plate_objects() const { return plate_objects; }
    bool is_holding() const { return held_object != -1; }
    void update_from_askloc(const std::string& result); // 更新物体位置，调用 AskLoc 接口

    const Object* get_object(int id) const;
    int get_object_location(int id) const;        // 返回实际位置（at 或 inside）
    bool is_inside_container(int obj_id, int container_id) const;
    ContainerState get_container_state(int container_id) const;
    Color get_object_color(int id) const;

    void print_all() const;
    void print_object(int id) const;

private:
    void init_robot();
    std::vector<std::string> tokenize(const std::string& s);
    void parse_predicate(const std::vector<std::string>& tokens);
};



#endif // ENVIRONMENT_MANAGER_H