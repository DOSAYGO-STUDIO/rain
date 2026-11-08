#include "rainbow_r0.cpp"
#include "rainbow_r1.cpp"
#include "rainbow_r2.cpp"
#include "rainbow_r3.cpp"
#include "rainbow_r4.cpp"
#include "rainbow_r5.cpp"
#include "rainbow_r6.cpp"

#define EXPORT_VARIANT(rung, bits, swapped) \
extern "C" void rainbow2_##rung##_##bits##_##swapped(const void* p, size_t n, uint64_t seed, void* out) { \
  rainbow_##rung::rainbow<bits, swapped>(p, n, seed, out); \
}
#define EXPORT_SIZE(rung, bits) EXPORT_VARIANT(rung, bits, 0) EXPORT_VARIANT(rung, bits, 1)
#define EXPORT_ALL(rung) EXPORT_SIZE(rung, 64) EXPORT_SIZE(rung, 128) EXPORT_SIZE(rung, 256)
EXPORT_ALL(r0)
EXPORT_ALL(r1)
EXPORT_ALL(r2)
EXPORT_ALL(r3)
EXPORT_ALL(r4)
EXPORT_ALL(r5)
EXPORT_ALL(r6)

#define EXPORT_STREAM(rung) \
extern "C" void rainbow2_##rung##_stream(const uint8_t* p, size_t n, uint64_t seed, uint32_t bits, size_t chunk, void* out) { \
  auto s = rainbow_##rung::HashState::initialize(seed, n, bits); \
  for (size_t i = 0; i < n; i += chunk) s.update(p + i, std::min(chunk, n - i)); \
  s.finalize(out); \
}
EXPORT_STREAM(r0)
EXPORT_STREAM(r1)
EXPORT_STREAM(r2)
EXPORT_STREAM(r3)
EXPORT_STREAM(r4)
EXPORT_STREAM(r5)
EXPORT_STREAM(r6)
