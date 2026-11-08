#include "bridge.cpp"
#include <cstdio>
#include <vector>

using Hash = void (*)(const void*,size_t,uint64_t,void*);
using Stream = void (*)(const uint8_t*,size_t,uint64_t,uint32_t,size_t,void*);
struct Entry { Hash hash; Stream stream; unsigned bits; };
#define ENTRY(letter,bits) {rainexp_##letter##_##bits##_0,rainexp_##letter##_stream,bits}
#define ENTRIES(letter) ENTRY(letter,64),ENTRY(letter,128),ENTRY(letter,256),ENTRY(letter,512)
int main() {
    Entry entries[]={ENTRIES(a),ENTRIES(b),ENTRIES(c),ENTRIES(d)};
    size_t cases=0;
    for (size_t len : {0,1,15,16,17,63,64,65,127,128,129,1000,4096}) {
        std::vector<uint8_t> msg(len+1);
        for (size_t i=0;i<len;i++) msg[i]=static_cast<uint8_t>(i*37+11);
        for (uint64_t seed : {UINT64_C(0),UINT64_C(1),UINT64_MAX}) {
            for (auto e:entries) {
                uint8_t a[64]={},b[64]={};
                e.hash(msg.data(),len,seed,a);
                for (size_t chunk : {1,7,63,64,65,129}) {
                    e.stream(msg.data(),len,seed,e.bits,chunk,b);
                    if (std::memcmp(a,b,e.bits/8)) return 1;
                    ++cases;
                }
            }
        }
    }
    std::printf("ASan/UBSan: %zu candidate streaming comparisons passed.\n",cases);
}
