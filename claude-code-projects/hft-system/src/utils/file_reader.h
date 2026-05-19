#pragma once
#include <string>
#include <vector>

class FileReader {
public:
    explicit FileReader(const std::string& filename);
    ~FileReader();
    bool readNextMessage(std::vector<char>& buffer);

private:
    std::string filename_;
    FILE* file_;
};