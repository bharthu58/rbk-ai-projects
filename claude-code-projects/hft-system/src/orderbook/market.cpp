#include "market.h"

void Market::addOrder(const std::string& symbol, const Order& order) {
    books_[symbol].addOrder(order);
}

void Market::printTopOfBook(const std::string& symbol) const {
    auto it = books_.find(symbol);
    if (it == books_.end()) return;
    it->second.printTopOfBook();
}
