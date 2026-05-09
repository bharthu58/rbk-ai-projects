#pragma once
#include <vector>
#include "orderbook/market.h"

class ITCHParser {
public:
    void parseMessage(Market& market, const std::vector<char>& msg);
    Order parseAddOrder(const std::vector<char>& msg);
    Execution parseOrderExecuted(const std::vector<char>& msg);
};