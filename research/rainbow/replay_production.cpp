// Replay candidate messages through the UNTOUCHED production Rainbow.
//
// This file includes src/rainbow.cpp verbatim; it is the authority for whether
// a collision is real.  Messages arrive as hex on the command line, so the
// bytes replayed are the serialized bytes, never in-memory uint64_t values.
//
//   ./replay_production <hex_a> <hex_b> [seed]

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "../../src/common.h"
#include "../../src/rainbow.cpp"

static bool from_hex(const std::string& text, std::vector<uint8_t>& out) {
  if (text.size() % 2 != 0) return false;
  out.clear();
  for (size_t i = 0; i < text.size(); i += 2) {
    auto nibble = [](char c) -> int {
      if (c >= '0' && c <= '9') return c - '0';
      if (c >= 'a' && c <= 'f') return c - 'a' + 10;
      if (c >= 'A' && c <= 'F') return c - 'A' + 10;
      return -1;
    };
    const int hi = nibble(text[i]), lo = nibble(text[i + 1]);
    if (hi < 0 || lo < 0) return false;
    out.push_back((uint8_t)((hi << 4) | lo));
  }
  return true;
}

static std::string to_hex(const uint8_t* data, size_t n) {
  static const char* digits = "0123456789abcdef";
  std::string out;
  for (size_t i = 0; i < n; ++i) {
    out.push_back(digits[data[i] >> 4]);
    out.push_back(digits[data[i] & 15]);
  }
  return out;
}

template <uint32_t bits>
static bool compare(const std::vector<uint8_t>& a, const std::vector<uint8_t>& b,
                    uint64_t seed) {
  std::vector<uint8_t> da(bits / 8), db(bits / 8);
  rainbow::rainbow<bits, bswap>(a.data(), a.size(), seed, da.data());
  rainbow::rainbow<bits, bswap>(b.data(), b.size(), seed, db.data());
  const bool equal = da == db;
  printf("  rainbow-%u\n", bits);
  printf("    a = %s\n", to_hex(da.data(), da.size()).c_str());
  printf("    b = %s\n", to_hex(db.data(), db.size()).c_str());
  printf("    equal = %s\n", equal ? "YES" : "no");
  return equal;
}

int main(int argc, char** argv) {
  if (argc < 3) {
    fprintf(stderr, "usage: replay_production <hex_a> <hex_b> [seed]\n");
    return 2;
  }
  std::vector<uint8_t> a, b;
  if (!from_hex(argv[1], a) || !from_hex(argv[2], b)) {
    fprintf(stderr, "messages must be hex\n");
    return 2;
  }
  const uint64_t seed = (argc > 3) ? strtoull(argv[3], nullptr, 0) : 0;

  printf("production replay (src/rainbow.cpp, unmodified)\n");
  printf("  message a (%zu bytes) = %s\n", a.size(), argv[1]);
  printf("  message b (%zu bytes) = %s\n", b.size(), argv[2]);
  printf("  seed = %llu\n", (unsigned long long)seed);
  if (a == b) {
    fprintf(stderr, "messages are identical -- not a collision\n");
    return 1;
  }
  if (a.size() != b.size()) {
    printf("  NOTE: lengths differ; Rainbow is length-keyed\n");
  }

  const bool e64 = compare<64>(a, b, seed);
  const bool e128 = compare<128>(a, b, seed);
  const bool e256 = compare<256>(a, b, seed);

  const bool all = e64 && e128 && e256;
  printf("\n%s\n", all ? "CONFIRMED: distinct messages collide at 64, 128 and 256 bits"
                       : "NOT a full collision");
  return all ? 0 : 1;
}
