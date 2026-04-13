#pragma once
#include <vector>
#include "orderbook/market.h"

class ITCHParser {
public:
    Order parseAddOrder(const std::vector<char>& msg);
    void parseMessage(Market& market, const std::vector<char>& msg);
};