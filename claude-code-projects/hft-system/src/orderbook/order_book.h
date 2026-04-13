#pragma once

#include "order.h"
#include <map>
#include <vector>

class OrderBook {
public:
    void addOrder(const Order& order);
    void printTopOfBook() const;

    private:
    std::map<uint32_t, std::vector<Order>> bids_;
    std::map<uint32_t, std::vector<Order>> asks_;
};
