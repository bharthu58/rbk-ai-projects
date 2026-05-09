#pragma once
#include "order_book.h"
#include <unordered_map>
#include <string>

class Market {
public:
    void addOrder(const Order& order);
    void executeOrder(const Execution& execution);
    void printTopOfBook(const std::string& symbol) const;
    void printImbalance(const std::string& symbol, std::ofstream& outputFile, int tick);


private:
    std::unordered_map<std::string, OrderBook> books_;
    std::unordered_map<uint64_t, Order> orders_;
};
