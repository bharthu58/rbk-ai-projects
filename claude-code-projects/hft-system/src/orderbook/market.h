#pragma once
#include "order_book.h"
#include <unordered_map>
#include <string>

class Market {
public:
    void addOrder(const std::string& symbol, const Order& order);
    void printTopOfBook(const std::string& symbol) const;

private:
    std::unordered_map<std::string, OrderBook> books_;
};
