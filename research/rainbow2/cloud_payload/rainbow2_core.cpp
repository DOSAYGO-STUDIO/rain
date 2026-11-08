#include "rainbow2_source/rainbow_r0.cpp"
#include "rainbow2_source/rainbow_r1.cpp"
#include "rainbow2_source/rainbow_r2.cpp"
#include "rainbow2_source/rainbow_r3.cpp"
#include "rainbow2_source/rainbow_r4.cpp"
#include "rainbow2_source/rainbow_r5.cpp"
#include "rainbow2_source/rainbow_r6.cpp"

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
