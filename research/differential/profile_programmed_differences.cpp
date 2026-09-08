#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <vector>

#include "../../src/rainstorm.cpp"

namespace {

static constexpr uint64_t PRIMES[16] = {
    1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47};

uint64_t splitmix64(uint64_t& state) {
  uint64_t value = (state += UINT64_C(0x9e3779b97f4a7c15));
  value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
  value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
  return value ^ (value >> 31);
}

void initial_state(uint64_t* state) {
  for (unsigned i = 0; i < 16; ++i) state[i] = 64 + PRIMES[i];
}

void program_data(const uint64_t* outputs, uint64_t* data) {
  uint64_t state[16];
  initial_state(state);
  uint64_t counter = rainstorm::CTR_RIGHT;
  for (unsigned lane = 0; lane < 8; ++lane) {
    uint64_t incoming = state[8 + lane];
    if (lane) incoming -= counter;
    data[lane] = incoming ^
        (ROTR64(outputs[lane], 64 - rainstorm::Z[lane]) + rainstorm::K[lane]);
    counter += outputs[lane];
  }
}

void message_boundary(const uint64_t* outputs, uint64_t* data,
                      uint64_t* state) {
  program_data(outputs, data);
  initial_state(state);
  for (unsigned round = 0; round < 4; ++round) {
    rainstorm::weakfunc(state, data, round & 1);
  }
}

unsigned weight(const uint64_t* a, const uint64_t* b) {
  unsigned result = 0;
  for (unsigned i = 0; i < 16; ++i) {
    result += __builtin_popcountll(a[i] ^ b[i]);
  }
  return result;
}

struct Candidate {
  unsigned bit = 0;
  unsigned lane_mask = 0;
  double mean = 0;
  unsigned minimum = 1025;
};

bool by_mean(const Candidate& left, const Candidate& right) {
  if (left.mean != right.mean) return left.mean < right.mean;
  return left.minimum < right.minimum;
}

void print_words(const uint64_t* values, unsigned count) {
  std::printf("[");
  for (unsigned i = 0; i < count; ++i) {
    if (i) std::printf(",");
    std::printf("\"0x%016llx\"", static_cast<unsigned long long>(values[i]));
  }
  std::printf("]");
}

}  // namespace

int main(int argc, char** argv) {
  const uint64_t samples = argc > 1
      ? std::strtoull(argv[1], nullptr, 0) : UINT64_C(1024);
  uint64_t generator = argc > 2
      ? std::strtoull(argv[2], nullptr, 0) : UINT64_C(20260908);
  const bool additive = argc > 3 && std::strcmp(argv[3], "add") == 0;
  if (argc > 4 && std::freopen(argv[4], "w", stdout) == nullptr) return 3;
  const int selected_bit = argc > 5
      ? static_cast<int>(std::strtol(argv[5], nullptr, 0)) : -1;
  const int selected_mask = argc > 6
      ? static_cast<int>(std::strtol(argv[6], nullptr, 0)) : -1;
  if (selected_bit > 63 || selected_mask > 255 || selected_mask == 0) return 4;
  if (!samples) return 2;

  std::vector<Candidate> candidates;
  candidates.reserve(selected_bit >= 0 && selected_mask >= 0 ? 1 : 64 * 255);
  unsigned global_minimum = 1025;
  unsigned global_bit = 0;
  unsigned global_mask = 0;
  uint64_t best_y_a[8] = {};
  uint64_t best_y_b[8] = {};
  uint64_t best_data_a[8] = {};
  uint64_t best_data_b[8] = {};
  uint64_t best_state_a[16] = {};
  uint64_t best_state_b[16] = {};

  for (unsigned bit = 0; bit < 64; ++bit) {
    if (selected_bit >= 0 && bit != static_cast<unsigned>(selected_bit)) continue;
    const uint64_t delta = UINT64_C(1) << bit;
    for (unsigned lane_mask = 1; lane_mask < 256; ++lane_mask) {
      if (selected_mask >= 0 &&
          lane_mask != static_cast<unsigned>(selected_mask)) continue;
      uint64_t weight_sum = 0;
      unsigned minimum = 1025;
      for (uint64_t sample = 0; sample < samples; ++sample) {
        uint64_t y_a[8];
        uint64_t y_b[8];
        for (unsigned lane = 0; lane < 8; ++lane) {
          y_a[lane] = splitmix64(generator);
          y_b[lane] = y_a[lane];
          if ((lane_mask >> lane) & 1) {
            y_b[lane] = additive ? y_b[lane] + delta : y_b[lane] ^ delta;
          }
        }
        uint64_t data_a[8];
        uint64_t data_b[8];
        uint64_t state_a[16];
        uint64_t state_b[16];
        message_boundary(y_a, data_a, state_a);
        message_boundary(y_b, data_b, state_b);
        const unsigned active = weight(state_a, state_b);
        weight_sum += active;
        minimum = std::min(minimum, active);
        if (active < global_minimum) {
          global_minimum = active;
          global_bit = bit;
          global_mask = lane_mask;
          std::memcpy(best_y_a, y_a, sizeof(y_a));
          std::memcpy(best_y_b, y_b, sizeof(y_b));
          std::memcpy(best_data_a, data_a, sizeof(data_a));
          std::memcpy(best_data_b, data_b, sizeof(data_b));
          std::memcpy(best_state_a, state_a, sizeof(state_a));
          std::memcpy(best_state_b, state_b, sizeof(state_b));
        }
      }
      candidates.push_back(Candidate{
          bit, lane_mask, static_cast<double>(weight_sum) / samples, minimum});
    }
  }
  std::sort(candidates.begin(), candidates.end(), by_mean);

  std::printf(
      "{\"experiment\":\"programmed-first-round-difference-screen\","
      "\"production_version\":\"4.0.0\",\"message_length\":64,"
      "\"message_rounds\":4,\"relation\":\"%s\","
      "\"samples_per_difference\":%llu,\"tested_differences\":%zu,"
      "\"pair_evaluations\":%llu,\"top_by_mean\":[",
      additive ? "add" : "xor", static_cast<unsigned long long>(samples),
      candidates.size(),
      static_cast<unsigned long long>(samples * candidates.size()));
  const size_t reported = std::min<size_t>(16, candidates.size());
  for (size_t i = 0; i < reported; ++i) {
    if (i) std::printf(",");
    const Candidate& item = candidates[i];
    std::printf(
        "{\"bit\":%u,\"lane_mask\":\"0x%02x\","
        "\"mean_active_bits\":%.9f,\"minimum_active_bits\":%u}",
        item.bit, item.lane_mask, item.mean, item.minimum);
  }
  std::printf(
      "],\"minimum_witness\":{\"active_bits\":%u,\"bit\":%u,"
      "\"lane_mask\":\"0x%02x\",\"first_outputs_a\":",
      global_minimum, global_bit, global_mask);
  print_words(best_y_a, 8);
  std::printf(",\"first_outputs_b\":");
  print_words(best_y_b, 8);
  std::printf(",\"message_words_a\":");
  print_words(best_data_a, 8);
  std::printf(",\"message_words_b\":");
  print_words(best_data_b, 8);
  std::printf(",\"boundary_state_a\":");
  print_words(best_state_a, 16);
  std::printf(",\"boundary_state_b\":");
  print_words(best_state_b, 16);
  std::printf(
      "},\"scope\":\"Discovery over one-bit XOR/additive differences applied "
      "to every nonempty subset of programmed first-round words. Candidate "
      "selection requires fresh validation.\"}\n");
  return 0;
}
