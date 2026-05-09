#include "order_book.h"
#include "order.h"
#include "utils/itch_utils.h"
#include <iostream>
#include <iomanip>
#include <algorithm>

using namespace itch;

void OrderBook::addOrder(const Order& order) {
    if (order.side == 'B') {
        bids_[order.price].push_back(order);
    } else {
        asks_[order.price].push_back(order);
    }
    bookUpdated = true;
}

void OrderBook::executeOrder(const Order& order) {
    std::vector<Order>& pricelevelVector = (order.side == 'B') ? bids_[order.price] : asks_[order.price];

    if(!pricelevelVector.empty()) // safety check.
    {
        auto it = std::find_if(pricelevelVector.begin(), pricelevelVector.end(),
            [&](const Order& o) { return o.order_id == order.order_id; });
        if (it != pricelevelVector.end()) {
            it->shares -= order.shares;
            if (it->shares <= 0) {
                pricelevelVector.erase(it);
            }
            if (pricelevelVector.empty()) {
                (order.side == 'B') ? bids_.erase(order.price) : asks_.erase(order.price);
            }
            bookUpdated = true;
        }
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

uint64_t OrderBook::computeTotalBidVolume() const
{
    uint64_t total = 0;
    for (const auto& pricelevel : bids_) {
        for (const auto& order : pricelevel.second) {
            total += order.shares;
        }
    }   
    return total;
}

uint64_t OrderBook::computeTotalAskVolume() const
{
    uint64_t total = 0;
    for (const auto& pricelevel : asks_) {  
        for(const auto& order : pricelevel.second) {
            total += order.shares;
        }   
    }
    return total;
}

int64_t OrderBook::computeImbalance() const
{
    return static_cast<int64_t>(computeTotalBidVolume()) - static_cast<int64_t>(computeTotalAskVolume());
}

double OrderBook::getBestBid() const
{
    if (!bids_.empty()) {
        auto it = bids_.rbegin();
        return toPrice(it->first);
    }
    return 0.0;
}

double OrderBook::getBestAsk() const
{
    if (!asks_.empty()) {
        auto it = asks_.begin();
        return toPrice(it->first);
    }
    return 0.0; 
}