#pragma once
#include <cstdint>

namespace itch {

uint16_t readUint16(const char* data);
uint32_t readUint32(const char* data);
uint64_t readUint64(const char* data);

double toPrice(uint32_t raw);  // ITCH prices have 4 implied decimal places

} // namespace itch
