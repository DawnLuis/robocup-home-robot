//------------------------------------------------------------------
// RoboCup 服务机器人仿真赛项 · 参赛程序
// Author : Dawnluis   (GitHub: DawnLuis)
// Repo   : https://github.com/DawnLuis/robocup-home-robot
//------------------------------------------------------------------
// nlu.h
#ifndef NLU_H
#define NLU_H

#include <string>
#include "instruction_parser.hpp"

class SimpleNLU {
public:
    // ✅ 返回 string 而不是 vector<Predicate>
    std::string parse(const std::string& input);
};

#endif // NLU_H