#include "order_book.h"
#include "order.h"
#include "utils/itch_utils.h"
#include <iostream>
#include <cassert>
#include <iomanip>
#include <algorithm>

using namespace itch;

void OrderBook::addOrder(const Order& order) {
    assert(order.price > 0);
    assert(order.side == 'B' || order.side == 'S');
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
            if (it->shares == 0) {
                pricelevelVector.erase(it);
            }
            if (pricelevelVector.empty()) {
                (order.side == 'B') ? bids_.erase(order.price) : asks_.erase(order.price);
            }
            bookUpdated = true;
        }
    }
}


void OrderBook::printTopOfBook(const std::string& symbol) const {
    double bid = getBestBid();
    double ask = getBestAsk();
    std::cout << std::fixed << std::setprecision(4)
              << symbol
              << " | BID: " << (bid > 0.0 ? std::to_string(bid) : "---")
              << " | ASK: " << (ask > 0.0 ? std::to_string(ask) : "---");
    if (bid > 0.0 && ask > 0.0)
        std::cout << " | SPREAD: " << (ask - bid);
    std::cout << std::endl;
}

uint64_t OrderBook::totalVolume(const std::map<uint32_t, std::vector<Order>>& side)
{
    uint64_t total = 0;
    for (const auto& level : side)
        for (const auto& order : level.second)
            total += order.shares;
    return total;
}

uint64_t OrderBook::computeTotalBidVolume() const { return totalVolume(bids_); }
uint64_t OrderBook::computeTotalAskVolume() const { return totalVolume(asks_); }

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