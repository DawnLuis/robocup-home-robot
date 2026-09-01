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