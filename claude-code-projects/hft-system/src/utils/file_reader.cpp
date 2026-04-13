#include "file_reader.h"
#include <cstdint>
#include <cstdio>
#include <iostream>

FileReader::FileReader(const std::string& filename) : filename_(filename) {
    file_ = fopen(filename.c_str(), "rb");
    if (!file_) {
        std::cerr << "Failed to open file: " << filename << std::endl;
    }
}

bool FileReader::readNextMessage(std::vector<char>& buffer) {
    if (!file_) return false;

    // ITCH messages start with 2-byte length
    uint16_t length;
    size_t read = fread(&length, sizeof(uint16_t), 1, file_);
    if (read != 1) return false;

    // Convert from big-endian
    length = (length >> 8) | (length << 8);

    buffer.resize(length);
    read = fread(buffer.data(), 1, length, file_);

    return read == length;
}