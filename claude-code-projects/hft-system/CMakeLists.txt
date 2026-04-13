cmake_minimum_required(VERSION 3.10)
project(HFTSystem)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include_directories(src)

add_executable(hft_system
    src/main.cpp
    src/parser/itch_parser.cpp
    src/utils/file_reader.cpp
    src/utils/itch_utils.cpp
    src/orderbook/order_book.cpp
    src/orderbook/market.cpp
)