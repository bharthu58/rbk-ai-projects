#include "market.h"
#include <iostream>
#include <fstream>

void Market::addOrder(const Order& order) {
    books_[order.symbol].addOrder(order);
    orders_[order.order_id] = order;
}

void Market::executeOrder(const Execution& execution) {
    auto it = orders_.find(execution.order_id);
    if (it == orders_.end()) {
        return;  // order arrived before replay window
    }

    Order& order = it->second;
    if (execution.shares > order.shares) {
        std::cerr << "Execute shares exceed order shares — skipping" << std::endl;
        return;
    }

    std::cout << "Before: " << (order.side == 'B' ? "BID" : "ASK")
              << " " << order.price / 10000.0
              << " (" << order.shares << " shares)" << std::endl;

    order.shares -= execution.shares;

    if (order.shares == 0) {
        std::cout << "After:  " << (order.side == 'B' ? "BID" : "ASK")
                  << " " << order.price / 10000.0
                  << " (0 shares — removed)" << std::endl;
        books_[order.symbol].executeOrder(order);
        orders_.erase(it);
    } else {
        std::cout << "After:  " << (order.side == 'B' ? "BID" : "ASK")
                  << " " << order.price / 10000.0
                  << " (" << order.shares << " shares)" << std::endl;
        books_[order.symbol].executeOrder(order);
    }
}

void Market::printTopOfBook(const std::string& symbol) const {
    auto it = books_.find(symbol);
    if (it == books_.end()) return;
    it->second.printTopOfBook();
}

void Market::printImbalance(const std::string &symbol, std::ofstream &outputFile, int tick)
{
    auto it = books_.find(symbol);
    if (it == books_.end()) return;
    OrderBook& book = it->second;

    if (book.isBookUpdated()) {
        int64_t imbalance = book.computeImbalance();
        double mid = book.getMid();
        outputFile << tick << "," << mid << "," << imbalance << "\n";
        outputFile.flush();
        book.resetBookUpdated();
    }
}
