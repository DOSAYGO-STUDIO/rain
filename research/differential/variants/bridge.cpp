#include "rainstorm_a.cpp"
#include "rainstorm_b.cpp"
#include "rainstorm_c.cpp"
#include "rainstorm_d.cpp"

#define EXPORT_VARIANT(letter, bits, swapped) \
extern "C" void rainexp_##letter##_##bits##_##swapped(const void* p, size_t n, uint64_t seed, void* out) { \
  rainstorm_##letter::rainstorm<bits, swapped>(p,n,seed,out); \
}
#define EXPORT_SIZE(letter,bits) EXPORT_VARIANT(letter,bits,0) EXPORT_VARIANT(letter,bits,1)
#define EXPORT_ALL(letter) EXPORT_SIZE(letter,64) EXPORT_SIZE(letter,128) EXPORT_SIZE(letter,256) EXPORT_SIZE(letter,512)
EXPORT_ALL(a)
EXPORT_ALL(b)
EXPORT_ALL(c)
EXPORT_ALL(d)

#define EXPORT_STREAM(letter) \
extern "C" void rainexp_##letter##_stream(const uint8_t* p, size_t n, uint64_t seed, uint32_t bits, size_t chunk, void* out) { \
  auto s=rainstorm_##letter::HashState::initialize(seed,n,bits); \
  for (size_t i=0;i<n;i+=chunk) s.update(p+i,std::min(chunk,n-i)); \
  s.finalize(out); \
}
EXPORT_STREAM(a)
EXPORT_STREAM(b)
EXPORT_STREAM(c)
EXPORT_STREAM(d)
