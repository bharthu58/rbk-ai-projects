#include "itch_parser.h"
#include "utils/itch_utils.h"
#include <iostream>
#include <algorithm>
#include "orderbook/market.h"

using namespace itch;

Order ITCHParser::parseAddOrder(const std::vector<char>& msg) {
    int offset = 1;  // Skip message type

    offset += 2; // stock Locate
    offset += 2; // tracking number
    offset += 6; // timestamp

    uint64_t order_id = readUint64(&msg[offset]);
    offset += 8;

    char side = msg[offset];
    offset += 1;

    uint32_t shares = readUint32(&msg[offset]);
    offset += 4;

    std::string stock(&msg[offset], 8);
    stock.erase(std::remove(stock.begin(), stock.end(), ' '), stock.end());
    offset += 8;

    uint32_t price = readUint32(&msg[offset]);
    offset += 4;

    Order order = {order_id, side, shares, price, stock};
    return order;

    // std::cout << "ADD ORDER | "
    //           << "ID: " << order_id
    //           << " Side: " << side
    //           << " Shares: " << shares
    //           << " Price: " << price
    //           << " Stock: " << stock
    //           << std::endl;
}

void ITCHParser::parseMessage(Market& market, const std::vector<char>& msg) {
    if (msg.empty()) return;

    char messageType = msg[0];

    switch (messageType) {
        case 'A': {  // Add Order
            Order order = parseAddOrder(msg);
            market.addOrder(order.symbol, order);
            break;
        }

        case 'E':  // Order Executed
            std::cout << "Order Executed message" << std::endl;
            break;

        default:
            std::cout << "Other message type: " << messageType << std::endl;
    }
}