#include <cstddef>
#include <cstdint>

#include "../../src/rainstorm.cpp"

// Batch bridge for the current production Rainstorm source.  This is kept
// separate from native.cpp, whose purpose is to preserve the frozen pre-v4
// reference used by the historical OG analysis.
extern "C" int rainstorm_hash_many(unsigned bits, uint64_t seed,
                                    const void* input, size_t length,
                                    size_t count, void* output) {
  const auto* p = static_cast<const uint8_t*>(input);
  auto* q = static_cast<uint8_t*>(output);
  for (size_t i = 0; i < count; ++i) {
    const void* message = length ? p + i * length : p;
    switch (bits) {
      case 64:
        rainstorm::rainstorm<64, false>(message, length, seed, q + i * 8);
        break;
      case 128:
        rainstorm::rainstorm<128, false>(message, length, seed, q + i * 16);
        break;
      case 256:
        rainstorm::rainstorm<256, false>(message, length, seed, q + i * 32);
        break;
      case 512:
        rainstorm::rainstorm<512, false>(message, length, seed, q + i * 64);
        break;
      default:
        return 1;
    }
  }
  return 0;
}
