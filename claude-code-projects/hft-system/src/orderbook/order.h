#pragma once
#include <cstdint>
#include <string>


struct Order {
    uint64_t order_id;
    char side;
    uint32_t shares;
    uint32_t price;
    std::string symbol;
};