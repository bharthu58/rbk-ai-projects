#include "utils/file_reader.h"
#include "parser/itch_parser.h"
#include <iostream>
#include <vector>
#include "orderbook/market.h"
#include <fstream>

int main() {
    std::string filename = "data/12302019.NASDAQ_ITCH50";  // Update with actual file

    FileReader reader(filename);
    ITCHParser parser;

    std::vector<char> buffer;
    int count = 0;

    Market market;

    std::ofstream outputFile("imbalance.csv");
    if (!outputFile.is_open()) {
        std::cerr << "Failed to open output file." << std::endl;
        return 1;
    }

    // write header.
    outputFile << "msg_count,mid_price,imbalance,best_bid,best_ask,spread\n";



    while (reader.readNextMessage(buffer)) {
        if (buffer[0] == 'A' || buffer[0] == 'E') {
            parser.parseMessage(market, buffer);

            ++count;
            market.printImbalance("EQNR", outputFile, count, buffer[0]);

            if (count >= 50000) break;
        }
    }
    std::cout << "Processed " << count << " messages." << std::endl;

    
    return 0;
}