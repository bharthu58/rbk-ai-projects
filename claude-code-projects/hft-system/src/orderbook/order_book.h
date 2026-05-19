#pragma once

#include "order.h"
#include <cstdint>
#include <map>
#include <vector>

class OrderBook {
public:
    void addOrder(const Order& order);
    void executeOrder(const Order& order);

    void printTopOfBook(const std::string& symbol) const;
    bool isBookUpdated() const { return bookUpdated; }
    void resetBookUpdated() { bookUpdated = false; }
    int64_t getLastImbalance() const { return lastImbalance_; }
    void setLastImbalance(int64_t v) { lastImbalance_ = v; }

    uint64_t computeTotalBidVolume() const;
    uint64_t computeTotalAskVolume() const;
    int64_t computeImbalance() const;

    double getBestBid() const;
    double getBestAsk() const;
    double getMid() const {
        double bid = getBestBid(), ask = getBestAsk();
        if (bid > 0.0 && ask > 0.0) return (bid + ask) / 2.0;
        return bid > 0.0 ? bid : ask;
    }
    
private:
    static uint64_t totalVolume(const std::map<uint32_t, std::vector<Order>>& side);

    std::map<uint32_t, std::vector<Order>> bids_;
    std::map<uint32_t, std::vector<Order>> asks_;

    bool bookUpdated = false;
    int64_t lastImbalance_ = INT64_MIN;
};
