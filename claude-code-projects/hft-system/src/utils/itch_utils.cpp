#include "itch_utils.h"

namespace itch {

uint16_t readUint16(const char* data) {
    return (uint16_t)((unsigned char)data[0] << 8 |
                      (unsigned char)data[1]);
}

uint32_t readUint32(const char* data) {
    return (uint32_t)((unsigned char)data[0] << 24 |
                      (unsigned char)data[1] << 16 |
                      (unsigned char)data[2] << 8 |
                      (unsigned char)data[3]);
}

uint64_t readUint64(const char* data) {
    uint64_t value = 0;
    for (int i = 0; i < 8; ++i) {
        value = (value << 8) | (unsigned char)data[i];
    }
    return value;
}

double toPrice(uint32_t raw) {
    return raw / 10000.0;
}

} // namespace itch
