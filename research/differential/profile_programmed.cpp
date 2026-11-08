#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "../../src/rainstorm.cpp"

namespace {

constexpr unsigned kStages = 7;
constexpr unsigned kWidths[] = {4, 8, 12, 16, 20, 24, 32};
constexpr const char* kStageNames[kStages] = {
    "message_round_2", "message_round_3", "message_round_4",
    "padding_round_1", "padding_round_2", "padding_round_3",
    "padding_round_4"};

struct StageCounts {
  uint64_t xor_ones[8][64] = {};
  uint64_t xor_low_zero[sizeof(kWidths) / sizeof(kWidths[0])] = {};
  uint64_t add_low_zero[sizeof(kWidths) / sizeof(kWidths[0])] = {};
  uint64_t equal_words[8] = {};
  uint64_t state_active_bit_sum = 0;
  uint64_t state_active_word_sum = 0;
  unsigned state_minimum_active_bits = 1025;
  unsigned state_minimum_active_words = 17;
};

uint64_t splitmix64(uint64_t& state) {
  uint64_t value = (state += UINT64_C(0x9e3779b97f4a7c15));
  value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
  value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
  return value ^ (value >> 31);
}

void initialize(uint64_t* state) {
  static constexpr uint64_t primes[16] = {
      1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47};
  for (unsigned i = 0; i < 16; ++i) state[i] = 64 + primes[i];
}

void program(uint64_t parameter, unsigned lane_p, unsigned lane_q,
             uint64_t* data) {
  uint64_t initial[16];
  initialize(initial);
  uint64_t y[8] = {};
  y[lane_p] = parameter;
  y[lane_q] = uint64_t(0) - parameter;
  uint64_t counter = rainstorm::CTR_RIGHT;
  for (unsigned i = 0; i < 8; ++i) {
    uint64_t incoming = initial[8 + i];
    if (i) incoming -= counter;
    data[i] = incoming ^
        (ROTR64(y[i], 64 - rainstorm::Z[i]) + rainstorm::K[i]);
    counter += y[i];
  }
}

void observe(const uint64_t* a, const uint64_t* b, StageCounts& counts) {
  unsigned state_bits = 0;
  unsigned state_words = 0;
  for (unsigned word = 0; word < 16; ++word) {
    const uint64_t value = a[word] ^ b[word];
    state_bits += __builtin_popcountll(value);
    state_words += value != 0;
  }
  counts.state_active_bit_sum += state_bits;
  counts.state_active_word_sum += state_words;
  if (state_bits < counts.state_minimum_active_bits) {
    counts.state_minimum_active_bits = state_bits;
  }
  if (state_words < counts.state_minimum_active_words) {
    counts.state_minimum_active_words = state_words;
  }
  uint64_t fold_a[8];
  uint64_t fold_b[8];
  for (unsigned word = 0; word < 8; ++word) {
    fold_a[word] = a[word] - a[8 + word];
    fold_b[word] = b[word] - b[8 + word];
    const uint64_t difference = fold_a[word] ^ fold_b[word];
    counts.equal_words[word] += difference == 0;
    for (unsigned bit = 0; bit < 64; ++bit) {
      counts.xor_ones[word][bit] += (difference >> bit) & 1;
    }
  }
  const uint64_t xor_difference = fold_a[0] ^ fold_b[0];
  const uint64_t add_difference = fold_b[0] - fold_a[0];
  for (unsigned i = 0; i < sizeof(kWidths) / sizeof(kWidths[0]); ++i) {
    const uint64_t mask = (UINT64_C(1) << kWidths[i]) - 1;
    counts.xor_low_zero[i] += (xor_difference & mask) == 0;
    counts.add_low_zero[i] += (add_difference & mask) == 0;
  }
}

void process_pair(uint64_t parameter_a, uint64_t parameter_b,
                  unsigned lane_p, unsigned lane_q,
                  std::array<StageCounts, kStages>& counts) {
  uint64_t data_a[8];
  uint64_t data_b[8];
  uint64_t state_a[16];
  uint64_t state_b[16];
  program(parameter_a, lane_p, lane_q, data_a);
  program(parameter_b, lane_p, lane_q, data_b);
  initialize(state_a);
  initialize(state_b);
  unsigned stage = 0;
  for (unsigned round = 0; round < 4; ++round) {
    rainstorm::weakfunc(state_a, data_a, round & 1);
    rainstorm::weakfunc(state_b, data_b, round & 1);
    if (round >= 1) observe(state_a, state_b, counts[stage++]);
  }
  const uint64_t padding[8] = {
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
      UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080)};
  for (unsigned round = 0; round < 4; ++round) {
    rainstorm::weakfunc(state_a, padding, round & 1);
    rainstorm::weakfunc(state_b, padding, round & 1);
    observe(state_a, state_b, counts[stage++]);
  }
}

}  // namespace

int main(int argc, char** argv) {
  const uint64_t samples = argc > 1
      ? std::strtoull(argv[1], nullptr, 0) : UINT64_C(4194304);
  const uint64_t delta = argc > 2
      ? std::strtoull(argv[2], nullptr, 0) : UINT64_C(1);
  uint64_t generator = argc > 3
      ? std::strtoull(argv[3], nullptr, 0) : UINT64_C(20260908);
  const char* relation = argc > 4 ? argv[4] : "xor";
  const unsigned rotation = argc > 5
      ? static_cast<unsigned>(std::strtoul(argv[5], nullptr, 0)) : 1;
  const unsigned lane_p = argc > 6
      ? static_cast<unsigned>(std::strtoul(argv[6], nullptr, 0)) : 6;
  const unsigned lane_q = argc > 7
      ? static_cast<unsigned>(std::strtoul(argv[7], nullptr, 0)) : 7;
  if (!samples || !delta) return 2;
  if (std::strcmp(relation, "xor") != 0 &&
      std::strcmp(relation, "add") != 0 &&
      std::strcmp(relation, "rx") != 0) return 2;
  if (std::strcmp(relation, "rx") == 0 &&
      (rotation == 0 || rotation >= 64)) return 2;
  if (lane_p < 2 || lane_p > 7 || lane_q < 2 || lane_q > 7 ||
      lane_p == lane_q) return 2;
  std::array<StageCounts, kStages> counts{};
  const auto started = std::chrono::steady_clock::now();
  for (uint64_t sample = 0; sample < samples; ++sample) {
    const uint64_t parameter = splitmix64(generator);
    uint64_t paired = parameter ^ delta;
    if (std::strcmp(relation, "add") == 0) paired = parameter + delta;
    if (std::strcmp(relation, "rx") == 0) {
      paired = ROTR64(parameter, 64 - rotation) ^ delta;
    }
    process_pair(parameter, paired, lane_p, lane_q, counts);
  }
  const double seconds = std::chrono::duration<double>(
      std::chrono::steady_clock::now() - started).count();
  std::printf(
      "{\"experiment\":\"programmed-family-fixed-difference-profile\","
      "\"production_version\":\"4.0.0\",\"samples\":%llu,"
      "\"parameter_relation\":\"%s\",\"parameter_difference\":\"0x%016llx\","
      "\"rx_rotation\":%u,\"programmed_lanes\":[%u,%u],\"seconds\":%.9f,"
      "\"pairs_per_second\":%.3f,\"stages\":[",
      static_cast<unsigned long long>(samples),
      relation, static_cast<unsigned long long>(delta), rotation, lane_p, lane_q,
      seconds, samples / seconds);
  for (unsigned stage = 0; stage < kStages; ++stage) {
    if (stage) std::printf(",");
    double maximum_z = 0;
    unsigned maximum_word = 0;
    unsigned maximum_bit = 0;
    for (unsigned word = 0; word < 8; ++word) {
      for (unsigned bit = 0; bit < 64; ++bit) {
        const double z = (counts[stage].xor_ones[word][bit] - samples / 2.0) /
                         std::sqrt(samples / 4.0);
        if (std::fabs(z) > std::fabs(maximum_z)) {
          maximum_z = z;
          maximum_word = word;
          maximum_bit = bit;
        }
      }
    }
    std::printf(
        "{\"stage\":\"%s\",\"maximum_xor_bit_z\":%.9f,"
        "\"maximum_xor_bit_word\":%u,\"maximum_xor_bit_index\":%u,"
        "\"mean_state_active_bits\":%.9f,\"minimum_state_active_bits\":%u,"
        "\"mean_state_active_words\":%.9f,\"minimum_state_active_words\":%u,"
        "\"equal_fold_word_counts\":[",
        kStageNames[stage], maximum_z, maximum_word, maximum_bit,
        static_cast<double>(counts[stage].state_active_bit_sum) / samples,
        counts[stage].state_minimum_active_bits,
        static_cast<double>(counts[stage].state_active_word_sum) / samples,
        counts[stage].state_minimum_active_words);
    for (unsigned word = 0; word < 8; ++word) {
      if (word) std::printf(",");
      std::printf("%llu", static_cast<unsigned long long>(
          counts[stage].equal_words[word]));
    }
    std::printf("],\"fold0_low_zero_counts\":[");
    for (unsigned i = 0; i < sizeof(kWidths) / sizeof(kWidths[0]); ++i) {
      if (i) std::printf(",");
      std::printf(
          "{\"bits\":%u,\"random_expectation\":%.9f,"
          "\"xor_count\":%llu,\"add_count\":%llu}",
          kWidths[i], std::ldexp(static_cast<double>(samples), -int(kWidths[i])),
          static_cast<unsigned long long>(counts[stage].xor_low_zero[i]),
          static_cast<unsigned long long>(counts[stage].add_low_zero[i]));
    }
    std::printf("]}");
  }
  std::printf("]}\n");
  return 0;
}
