#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "../../src/rainstorm.cpp"

namespace {

uint64_t splitmix64(uint64_t& state) {
  uint64_t value = (state += UINT64_C(0x9e3779b97f4a7c15));
  value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
  value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
  return value ^ (value >> 31);
}

uint64_t rotl(uint64_t value, unsigned count) {
  return count ? (value << count) | (value >> (64 - count)) : value;
}

struct Mask { uint64_t low; uint64_t high; };

std::array<Mask, 256> output_masks() {
  std::array<Mask, 256> masks{};
  for (unsigned bit = 0; bit < 128; ++bit) {
    masks[bit] = bit < 64 ? Mask{UINT64_C(1) << bit, 0}
                          : Mask{0, UINT64_C(1) << (bit - 64)};
  }
  for (unsigned rotation = 0; rotation < 64; ++rotation) {
    masks[128 + rotation] = {
        rotl(UINT64_C(0xaaaaaaaaaaaaaaaa), rotation),
        rotl(UINT64_C(0xcccccccccccccccc), rotation)};
  }
  uint64_t generator = UINT64_C(0xd1ff1e57bea71001);
  for (unsigned index = 192; index < masks.size(); ++index) {
    masks[index] = {splitmix64(generator), splitmix64(generator)};
  }
  return masks;
}

struct Result {
  unsigned input_bit;
  unsigned mask_index;
  uint64_t ones;
  double z;
};

bool by_abs_z(const Result& left, const Result& right) {
  return std::abs(left.z) > std::abs(right.z);
}

}  // namespace

int main(int argc, char** argv) {
  const uint64_t samples = argc > 1
      ? std::strtoull(argv[1], nullptr, 0) : UINT64_C(8192);
  uint64_t generator = argc > 2
      ? std::strtoull(argv[2], nullptr, 0) : UINT64_C(20260908);
  if (argc > 3 && std::freopen(argv[3], "w", stdout) == nullptr) return 3;
  const int selected_input_bit = argc > 4
      ? static_cast<int>(std::strtol(argv[4], nullptr, 0)) : -1;
  const int selected_mask = argc > 5
      ? static_cast<int>(std::strtol(argv[5], nullptr, 0)) : -1;
  if (!samples || selected_input_bit > 511 || selected_mask > 255) return 2;

  const auto masks = output_masks();
  std::vector<Result> results;
  results.reserve(selected_input_bit >= 0 && selected_mask >= 0 ? 1 : 512 * 256);
  for (unsigned input_bit = 0; input_bit < 512; ++input_bit) {
    if (selected_input_bit >= 0 &&
        input_bit != static_cast<unsigned>(selected_input_bit)) continue;
    std::array<uint64_t, 256> counts{};
    for (uint64_t sample = 0; sample < samples; ++sample) {
      uint8_t message_a[64];
      for (unsigned offset = 0; offset < 64; offset += 8) {
        const uint64_t value = splitmix64(generator);
        std::memcpy(message_a + offset, &value, sizeof(value));
      }
      uint8_t message_b[64];
      std::memcpy(message_b, message_a, sizeof(message_a));
      message_b[input_bit >> 3] ^= static_cast<uint8_t>(1u << (input_bit & 7));
      uint64_t digest_a[2];
      uint64_t digest_b[2];
      rainstorm::rainstorm<128, false>(message_a, sizeof(message_a), 0, digest_a);
      rainstorm::rainstorm<128, false>(message_b, sizeof(message_b), 0, digest_b);
      const uint64_t difference_low = digest_a[0] ^ digest_b[0];
      const uint64_t difference_high = digest_a[1] ^ digest_b[1];
      for (unsigned mask_index = 0; mask_index < masks.size(); ++mask_index) {
        if (selected_mask >= 0 &&
            mask_index != static_cast<unsigned>(selected_mask)) continue;
        const Mask mask = masks[mask_index];
        counts[mask_index] +=
            __builtin_parityll(difference_low & mask.low) ^
            __builtin_parityll(difference_high & mask.high);
      }
    }
    const double denominator = std::sqrt(samples * 0.25);
    for (unsigned mask_index = 0; mask_index < masks.size(); ++mask_index) {
      if (selected_mask >= 0 &&
          mask_index != static_cast<unsigned>(selected_mask)) continue;
      const double z = (counts[mask_index] - samples * 0.5) / denominator;
      results.push_back(Result{input_bit, mask_index, counts[mask_index], z});
    }
  }
  std::sort(results.begin(), results.end(), by_abs_z);

  std::printf(
      "{\"experiment\":\"production-rainstorm128-differential-linear-screen\","
      "\"production_version\":\"4.0.0\",\"message_length\":64,"
      "\"input_relation\":\"single-bit XOR\",\"output_relation\":"
      "\"parity of XOR difference under recorded mask\","
      "\"samples_per_test\":%llu,\"tested_input_differences\":%u,"
      "\"tested_output_masks_per_difference\":%u,\"total_tests\":%zu,"
      "\"top\":[",
      static_cast<unsigned long long>(samples),
      selected_input_bit >= 0 ? 1 : 512, selected_mask >= 0 ? 1 : 256,
      results.size());
  const size_t reported = std::min<size_t>(16, results.size());
  for (size_t index = 0; index < reported; ++index) {
    if (index) std::printf(",");
    const Result& item = results[index];
    const Mask mask = masks[item.mask_index];
    std::printf(
        "{\"input_bit\":%u,\"mask_index\":%u,"
        "\"output_mask_low\":\"0x%016llx\","
        "\"output_mask_high\":\"0x%016llx\",\"ones\":%llu,"
        "\"frequency\":%.9f,\"z\":%.9f}",
        item.input_bit, item.mask_index,
        static_cast<unsigned long long>(mask.low),
        static_cast<unsigned long long>(mask.high),
        static_cast<unsigned long long>(item.ones),
        static_cast<double>(item.ones) / samples, item.z);
  }
  std::printf(
      "],\"scope\":\"Discovery screen. The maximum is selected from all "
      "recorded tests and requires fresh validation; no independence among "
      "overlapping parity masks is assumed.\"}\n");
  return 0;
}
