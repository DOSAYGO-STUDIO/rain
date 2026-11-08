// Analysis bridge: frozen pre-v4 reference for OG-versus-candidate comparisons.
#include <cstdint>
#include <cstring>
#include <vector>
#include "reference/src/rainbow.cpp"
#include "reference/src/rainstorm.cpp"

extern "C" int hash_many(int algo, unsigned bits, uint64_t seed,
                         const uint8_t* in, size_t len, size_t count, uint8_t* out) {
  if ((algo != 0 && algo != 1) || (bits != 64 && bits != 128 && bits != 256 &&
      !(algo == 1 && bits == 512))) return -1;
  for (size_t i = 0; i < count; ++i) {
    const auto p = in + i * len;
    auto q = out + i * (bits / 8);
    if (algo == 0) {
      switch(bits) {
        case 64: rainbow::rainbow<64, false>(p,len,seed,q); break;
        case 128: rainbow::rainbow<128, false>(p,len,seed,q); break;
        case 256: rainbow::rainbow<256, false>(p,len,seed,q); break;
      }
    } else {
      switch(bits) {
        case 64: rainstorm::rainstorm<64, false>(p,len,seed,q); break;
        case 128: rainstorm::rainstorm<128, false>(p,len,seed,q); break;
        case 256: rainstorm::rainstorm<256, false>(p,len,seed,q); break;
        case 512: rainstorm::rainstorm<512, false>(p,len,seed,q); break;
      }
    }
  }
  return 0;
}
extern "C" void storm_round(uint64_t* h, const uint64_t* d, int left) {
  rainstorm::weakfunc(h,d,left != 0);
}
extern "C" void bow_mix(uint64_t* h, uint64_t seed, int b) {
  if (b) rainbow::mixB(h,seed); else rainbow::mixA(h);
}
