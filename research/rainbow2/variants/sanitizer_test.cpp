#include "bridge.cpp"
#include <cstdio>
#include <cstring>
#include <vector>

using Hash = void (*)(const void*, size_t, uint64_t, void*);
using Stream = void (*)(const uint8_t*, size_t, uint64_t, uint32_t, size_t, void*);
struct Entry { const char* name; Hash hash; Stream stream; unsigned bits; };
#define ENTRY(rung, bits) {#rung "-" #bits, rainbow2_##rung##_##bits##_0, rainbow2_##rung##_stream, bits}
#define ENTRIES(rung) ENTRY(rung, 64), ENTRY(rung, 128), ENTRY(rung, 256)

int main() {
    Entry entries[] = {
        ENTRIES(r0), ENTRIES(r1), ENTRIES(r2), ENTRIES(r3), ENTRIES(r4), ENTRIES(r5), ENTRIES(r6)
    };
    size_t cases = 0;
    for (size_t len : {0, 1, 2, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129, 1000, 4096}) {
        std::vector<uint8_t> msg(len + 1);
        for (size_t i = 0; i < len; i++) msg[i] = static_cast<uint8_t>(i * 37 + 11);
        for (uint64_t seed : {UINT64_C(0), UINT64_C(1), UINT64_C(0x123456789ABCDEF0), UINT64_MAX}) {
            for (auto e : entries) {
                uint8_t a[32] = {}, b[32] = {};
                e.hash(msg.data(), len, seed, a);
                for (size_t chunk : {1, 2, 7, 15, 16, 17, 31, 32, 64, 129}) {
                    e.stream(msg.data(), len, seed, e.bits, chunk, b);
                    if (std::memcmp(a, b, e.bits / 8) != 0) {
                        std::fprintf(stderr, "MISMATCH: %s len=%zu seed=%llu chunk=%zu\n",
                                     e.name, len, (unsigned long long)seed, chunk);
                        return 1;
                    }
                    ++cases;
                }
            }
        }
    }
    std::printf("ASan/UBSan: %zu Rainbow 2 ladder streaming comparisons passed.\n", cases);
    return 0;
}
