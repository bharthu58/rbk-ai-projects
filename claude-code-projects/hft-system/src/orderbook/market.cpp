#include "market.h"
#include <iostream>
#include <fstream>
#include <cassert>

void Market::addOrder(const Order& order) {
    books_[order.symbol].addOrder(order);
    orders_[order.order_id] = order;
}

void Market::executeOrder(const Execution& execution) {
    assert(execution.shares > 0);
    auto it = orders_.find(execution.order_id);
    if (it == orders_.end()) {
        return;  // order arrived before replay window
    }

    Order& order = it->second;
    if (execution.shares > order.shares) {
        std::cerr << "Execute shares exceed order shares — skipping" << std::endl;
        return;
    }

#ifdef DEBUG
    std::cout << "Before: " << (order.side == 'B' ? "BID" : "ASK")
              << " " << order.price / 10000.0
              << " (" << order.shares << " shares)" << std::endl;
#endif

    order.shares -= execution.shares;

    if (order.shares == 0) {
#ifdef DEBUG
        std::cout << "After:  " << (order.side == 'B' ? "BID" : "ASK")
                  << " " << order.price / 10000.0
                  << " (0 shares — removed)" << std::endl;
#endif
        books_[order.symbol].executeOrder(order);
        orders_.erase(it);
    } else {
#ifdef DEBUG
        std::cout << "After:  " << (order.side == 'B' ? "BID" : "ASK")
                  << " " << order.price / 10000.0
                  << " (" << order.shares << " shares)" << std::endl;
#endif
        books_[order.symbol].executeOrder(order);
    }
}

void Market::printTopOfBook(const std::string& symbol) const {
    auto it = books_.find(symbol);
    if (it == books_.end()) return;
    it->second.printTopOfBook(symbol);
}

void Market::printImbalance(const std::string &symbol, std::ofstream &outputFile, int tick, char msgType)
{
    auto it = books_.find(symbol);
    if (it == books_.end()) return;
    OrderBook& book = it->second;

    if (book.isBookUpdated() && (book.getBestBid() > 0.0 || book.getBestAsk() > 0.0)) {
        int64_t imbalance = book.computeImbalance();
        double bid = book.getBestBid();
        double ask = book.getBestAsk();
        double mid = book.getMid();
        double spread = (bid > 0.0 && ask > 0.0) ? ask - bid : 0.0;
        if (bid > 0.0 && ask > 0.0 && spread < 0.0)
            std::cerr << "[CROSSED BOOK] " << symbol << " tick=" << tick
                      << " msg=" << msgType
                      << " bid=" << bid << " ask=" << ask << " spread=" << spread << "\n";
        outputFile << tick << "," << mid << "," << imbalance << ","
                   << bid << "," << ask << "," << spread << "\n";
        outputFile.flush();
        book.resetBookUpdated();
    }
}
