#pragma once
#include <cstdint>
#include <string>


struct Order {
    uint64_t order_id;
    char side;
    uint32_t shares;
    uint32_t price;
    std::string symbol;

    void printOrder();
};

struct Execution {
    uint64_t execution_id;
    uint64_t order_id;
    uint32_t shares;
};