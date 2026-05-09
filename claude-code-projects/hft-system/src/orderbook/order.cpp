#include "order.h"
#include <iostream>


void Order::printOrder()
{
    std::cout << "Order ID: " << order_id << std::endl;
    std::cout << "Side: " << side << std::endl;
    std::cout << "Shares: " << shares << std::endl;
    std::cout << "Price: " << price << std::endl;
    std::cout << "Symbol: " << symbol << std::endl;
}