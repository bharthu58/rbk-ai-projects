#include "utils/file_reader.h"
#include "parser/itch_parser.h"
#include <iostream>
#include <vector>
#include "orderbook/market.h"

int main() {
    std::string filename = "data/12302019.NASDAQ_ITCH50";  // Update with actual file

    FileReader reader(filename);
    ITCHParser parser;

    std::vector<char> buffer;
    int count = 0;

    Market market;

    while (reader.readNextMessage(buffer)) {
        if (buffer[0] == 'A') {
            parser.parseMessage(market, buffer);
            if (++count >= 10) break;
        }
    }
    std::cout << "Processed " << count << " messages." << std::endl;

    market.printTopOfBook("ARGX");

    return 0;
}