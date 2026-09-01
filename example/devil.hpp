/*
 * Simulation@Home Competition
 * File: devil.hpp
 * Author: Jiongkun Xie
 * Affiliation: Multi-Agent Systems Lab.
 *              University of Science and Technology of China
 */

#ifndef __home_devil_HPP__
#define __home_devil_HPP__

#include "cserver/plug.hpp"
#include "environment_manager.hpp"
#include "instruction_parser.hpp"
namespace _home
{

    class Devil : public Plug
    {
        EnvironmentManager env;
        InstructionParser ins_parser;
    public:
        Devil();
        
        
    protected:
        void Plan();

        void Fini();
        bool execute_state_task(EnvironmentManager& env, const Rule& rule);
        bool execute_task_with_constraints(EnvironmentManager& env, InstructionParser& ins_parser, const Rule& rule);
        bool check_constraints(EnvironmentManager& env, InstructionParser& ins_parser, const Predicate& task);
        bool check_condition_match(EnvironmentManager& env, const Predicate& task, const Condition& cond);
        bool execute_pickup_task(EnvironmentManager& env, const Predicate& task);
        bool execute_putdown_task(EnvironmentManager& env, const Predicate& task);
        bool execute_puton_task(EnvironmentManager& env, const Predicate& task);
        bool execute_putin_task(EnvironmentManager& env, const Predicate& task);
        bool execute_goto_task(EnvironmentManager& env, const Predicate& task);
        bool execute_give_task(EnvironmentManager& env, const Predicate& task);
        bool execute_takeout_task(EnvironmentManager& env, const Predicate& task);
        Color get_color_from_string(const std::string& color_str) const;
        bool execute_close_task(EnvironmentManager& env, const Predicate& task);
        bool execute_open_task(EnvironmentManager& env, const Predicate& task);
    
    int find_object_by_conditions(EnvironmentManager& env, ObjectType type, Color color = Color::Unknown);
    bool is_object_protected(EnvironmentManager& env, int obj_id, ObjectType type);
    int try_held_object(EnvironmentManager& env, ObjectType type, Color color = Color::Unknown);
    bool is_reserved_by_specific_task(ObjectType type, Color col);
    ObjectType str_to_object_type(const std::string& s) const;
        
        bool execute_pickup(EnvironmentManager& env, int obj_id);
        bool execute_puton(EnvironmentManager& env, const Predicate& task);
        // bool execute_putoff(EnvironmentManager& env, int obj_id); // 对应 PutOn 的逆操作
        bool execute_putin(EnvironmentManager& env, const Predicate& task);
        bool execute_takeout(EnvironmentManager& env, int obj_id, int container_id);
        bool execute_move(EnvironmentManager& env, int loc);
        bool execute_give(EnvironmentManager& env, const Predicate& task);

        int find_object_by_type(EnvironmentManager& env, ObjectType type);
        int find_object_by_sort(EnvironmentManager& env, const std::string& sort_name);
    };//Plug

}//_home

#endif//__home_devil_HPP__
//end of file
