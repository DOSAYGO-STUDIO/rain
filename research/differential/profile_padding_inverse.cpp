#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>

#include "../../src/rainstorm.cpp"

namespace {

uint64_t splitmix64(uint64_t& state) {
  uint64_t value = (state += UINT64_C(0x9e3779b97f4a7c15));
  value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
  value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
  return value ^ (value >> 31);
}

void invert_weakfunc(const uint64_t* output, const uint64_t* data, bool left,
                     uint64_t* input) {
  uint64_t transformed[8];
  uint64_t counters[8];
  uint64_t counter = left ? rainstorm::CTR_LEFT : rainstorm::CTR_RIGHT;
  for (unsigned lane = 0; lane < 8; ++lane) {
    transformed[lane] = output[(left ? 0 : 8) + lane];
    counters[lane] = counter;
    counter += transformed[lane];
  }
  uint64_t active[8];
  for (unsigned lane = 0; lane < 8; ++lane) {
    uint64_t before =
        (ROTR64(transformed[lane], 64 - rainstorm::Z[lane]) +
         rainstorm::K[lane]) ^ data[lane];
    if (lane) before += counters[lane];
    active[lane] = before;
  }
  if (left) {
    for (unsigned lane = 0; lane < 8; ++lane) input[lane] = active[lane];
    input[8] = (output[8] + counter) ^ transformed[0];
    for (unsigned lane = 1; lane < 8; ++lane) {
      input[8 + lane] = output[8 + lane] ^ transformed[lane];
    }
  } else {
    for (unsigned lane = 0; lane < 8; ++lane) input[8 + lane] = active[lane];
    input[0] = (output[0] + counter) ^ transformed[0];
    for (unsigned lane = 1; lane < 8; ++lane) {
      input[lane] = output[lane] ^ transformed[lane];
    }
  }
}

struct Counts {
  uint64_t bit_sum = 0;
  uint64_t word_sum = 0;
  unsigned minimum_bits = 1025;
  unsigned minimum_words = 17;
  uint64_t below_384 = 0;
  uint64_t below_448 = 0;
};

struct MinimumWitness {
  unsigned active_bits = 1025;
  uint64_t pre_fold_a[16] = {};
  uint64_t pre_fold_b[16] = {};
  uint64_t boundary_a[16] = {};
  uint64_t boundary_b[16] = {};
};

// Best lane-0, MSB-additive boundary difference discovered in the independent
// 2^24-sample run.  A fresh run counts this exact XOR characteristic rather
// than confusing low Hamming weight with differential probability.
static constexpr uint64_t DISCOVERED_BOUNDARY_XOR[16] = {
    UINT64_C(0x0000000200000000), UINT64_C(0x0000000000050000),
    UINT64_C(0x8000000000c10000), UINT64_C(0x0000000010010000),
    UINT64_C(0x8000000140010000), UINT64_C(0x0000001000010000),
    UINT64_C(0x8000010000010000), UINT64_C(0x0010000000010000),
    UINT64_C(0x0000000200010000), UINT64_C(0x8000000000010000),
    UINT64_C(0x8000000000010000), UINT64_C(0x8000000000010000),
    UINT64_C(0x8000000000010000), UINT64_C(0x8000000000010000),
    UINT64_C(0x8000000000010000), UINT64_C(0x8000000000010000)};

void observe(const uint64_t* a, const uint64_t* b, Counts& counts) {
  unsigned bits = 0;
  unsigned words = 0;
  for (unsigned i = 0; i < 16; ++i) {
    const uint64_t difference = a[i] ^ b[i];
    bits += __builtin_popcountll(difference);
    words += difference != 0;
  }
  counts.bit_sum += bits;
  counts.word_sum += words;
  if (bits < counts.minimum_bits) counts.minimum_bits = bits;
  if (words < counts.minimum_words) counts.minimum_words = words;
  counts.below_384 += bits < 384;
  counts.below_448 += bits < 448;
}

unsigned active_bits(const uint64_t* a, const uint64_t* b) {
  unsigned bits = 0;
  for (unsigned i = 0; i < 16; ++i) {
    bits += __builtin_popcountll(a[i] ^ b[i]);
  }
  return bits;
}

void print_words(const uint64_t* words) {
  std::printf("[");
  for (unsigned i = 0; i < 16; ++i) {
    if (i) std::printf(",");
    std::printf("\"0x%016llx\"", static_cast<unsigned long long>(words[i]));
  }
  std::printf("]");
}

}  // namespace

int main(int argc, char** argv) {
  const uint64_t samples = argc > 1
      ? std::strtoull(argv[1], nullptr, 0) : UINT64_C(1048576);
  const unsigned lane = argc > 2
      ? static_cast<unsigned>(std::strtoul(argv[2], nullptr, 0)) : 0;
  const uint64_t delta = argc > 3
      ? std::strtoull(argv[3], nullptr, 0) : UINT64_C(1);
  uint64_t generator = argc > 4
      ? std::strtoull(argv[4], nullptr, 0) : UINT64_C(20260908);
  if (argc > 5 && std::freopen(argv[5], "w", stdout) == nullptr) return 4;
  if (!samples || lane > 7 || !delta) return 2;

  const uint64_t padding[8] = {
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080)};
  // Independent round-trip guard for the C++ inverse used by this profiler.
  {
    uint64_t state[16];
    uint64_t data[8];
    uint64_t check_generator = UINT64_C(0x5eed123456789abc);
    for (uint64_t& value : state) value = splitmix64(check_generator);
    for (uint64_t& value : data) value = splitmix64(check_generator);
    for (unsigned direction = 0; direction < 2; ++direction) {
      const bool left = direction != 0;
      uint64_t output[16];
      uint64_t recovered[16];
      std::memcpy(output, state, sizeof(state));
      rainstorm::weakfunc(output, data, left);
      invert_weakfunc(output, data, left, recovered);
      if (std::memcmp(state, recovered, sizeof(state)) != 0) return 3;
    }
  }
  std::array<Counts, 5> counts{};
  MinimumWitness minimum;
  uint64_t final_at_most_36 = 0;
  uint64_t final_at_most_40 = 0;
  uint64_t final_at_most_48 = 0;
  uint64_t final_at_most_64 = 0;
  uint64_t discovered_characteristic_matches = 0;
  for (uint64_t sample = 0; sample < samples; ++sample) {
    uint64_t a[16];
    uint64_t b[16];
    for (unsigned i = 0; i < 16; ++i) a[i] = b[i] = splitmix64(generator);
    // Equal additive changes in the selected low/high pair preserve its fold.
    b[lane] += delta;
    b[8 + lane] += delta;
    uint64_t pre_fold_a[16];
    uint64_t pre_fold_b[16];
    std::memcpy(pre_fold_a, a, sizeof(a));
    std::memcpy(pre_fold_b, b, sizeof(b));
    observe(a, b, counts[0]);
    for (int round = 3; round >= 0; --round) {
      uint64_t previous_a[16];
      uint64_t previous_b[16];
      invert_weakfunc(a, padding, round & 1, previous_a);
      invert_weakfunc(b, padding, round & 1, previous_b);
      std::memcpy(a, previous_a, sizeof(a));
      std::memcpy(b, previous_b, sizeof(b));
      observe(a, b, counts[4 - round]);
    }
    const unsigned final_bits = active_bits(a, b);
    final_at_most_36 += final_bits <= 36;
    final_at_most_40 += final_bits <= 40;
    final_at_most_48 += final_bits <= 48;
    final_at_most_64 += final_bits <= 64;
    if (lane == 0 && delta == (UINT64_C(1) << 63)) {
      bool matches = true;
      for (unsigned i = 0; i < 16; ++i) {
        matches &= (a[i] ^ b[i]) == DISCOVERED_BOUNDARY_XOR[i];
      }
      discovered_characteristic_matches += matches;
    }
    if (final_bits < minimum.active_bits) {
      minimum.active_bits = final_bits;
      std::memcpy(minimum.pre_fold_a, pre_fold_a, sizeof(pre_fold_a));
      std::memcpy(minimum.pre_fold_b, pre_fold_b, sizeof(pre_fold_b));
      std::memcpy(minimum.boundary_a, a, sizeof(a));
      std::memcpy(minimum.boundary_b, b, sizeof(b));
    }
  }
  std::printf(
      "{\"experiment\":\"inverse-padding-fold-preserving-differential\","
      "\"samples\":%llu,\"fold_lane\":%u,\"additive_delta\":\"0x%016llx\","
      "\"checkpoints\":[",
      static_cast<unsigned long long>(samples), lane,
      static_cast<unsigned long long>(delta));
  for (unsigned checkpoint = 0; checkpoint < counts.size(); ++checkpoint) {
    if (checkpoint) std::printf(",");
    const Counts& item = counts[checkpoint];
    std::printf(
        "{\"inverse_rounds\":%u,\"mean_active_bits\":%.9f,"
        "\"mean_active_words\":%.9f,\"minimum_active_bits\":%u,"
        "\"minimum_active_words\":%u,\"below_384_bits\":%llu,"
        "\"below_448_bits\":%llu}", checkpoint,
        static_cast<double>(item.bit_sum) / samples,
        static_cast<double>(item.word_sum) / samples, item.minimum_bits,
        item.minimum_words,
        static_cast<unsigned long long>(item.below_384),
        static_cast<unsigned long long>(item.below_448));
  }
  std::printf(
      "],\"final_weight_tail\":{\"at_most_36\":%llu,"
      "\"at_most_40\":%llu,\"at_most_48\":%llu,\"at_most_64\":%llu},"
      "\"held_out_discovered_characteristic_matches\":%llu,"
      "\"minimum_witness\":{\"active_bits\":%u,\"pre_fold_a\":",
      static_cast<unsigned long long>(final_at_most_36),
      static_cast<unsigned long long>(final_at_most_40),
      static_cast<unsigned long long>(final_at_most_48),
      static_cast<unsigned long long>(final_at_most_64),
      static_cast<unsigned long long>(discovered_characteristic_matches),
      minimum.active_bits);
  print_words(minimum.pre_fold_a);
  std::printf(",\"pre_fold_b\":");
  print_words(minimum.pre_fold_b);
  std::printf(",\"message_padding_boundary_a\":");
  print_words(minimum.boundary_a);
  std::printf(",\"message_padding_boundary_b\":");
  print_words(minimum.boundary_b);
  std::printf("}}\n");
  return 0;
}
