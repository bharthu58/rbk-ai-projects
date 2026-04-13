#include "order_book.h"
#include "order.h"
#include "utils/itch_utils.h"
#include <iostream>
#include <iomanip>

using namespace itch;

void OrderBook::addOrder(const Order& order) {
    if (order.side == 'B') {
        bids_[order.price].push_back(order);
    } else {
        asks_[order.price].push_back(order);
    }
}

void OrderBook::printTopOfBook() const {
    std::cout << std::fixed << std::setprecision(4);
    std::cout << "Top of Book:" << std::endl;

    if (!bids_.empty()) {
        auto it = bids_.rbegin();
        std::cout << "BEST BID: $" << toPrice(it->first) << std::endl;
    } else {
        std::cout << "No bids." << std::endl;
    }

    if (!asks_.empty()) {
        auto it = asks_.begin();
        std::cout << "BEST ASK: $" << toPrice(it->first) << std::endl;
    } else {
        std::cout << "No asks." << std::endl;
    }

    if (!bids_.empty() && !asks_.empty()) {
        double spread = toPrice(asks_.begin()->first) - toPrice(bids_.rbegin()->first);
        std::cout << "SPREAD:   $" << spread << std::endl;
    }
}
    
        


