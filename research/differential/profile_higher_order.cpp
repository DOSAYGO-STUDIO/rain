#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <vector>

#include "../../src/rainstorm.cpp"

namespace {

uint64_t splitmix64(uint64_t& state) {
  uint64_t value = (state += UINT64_C(0x9e3779b97f4a7c15));
  value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
  value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
  return value ^ (value >> 31);
}

void random_message(uint8_t* message, uint64_t& generator) {
  for (unsigned offset = 0; offset < 64; offset += 8) {
    const uint64_t value = splitmix64(generator);
    std::memcpy(message + offset, &value, sizeof(value));
  }
}

std::vector<unsigned> choose_cube(unsigned dimension, uint64_t& generator) {
  std::array<unsigned, 512> positions{};
  for (unsigned i = 0; i < positions.size(); ++i) positions[i] = i;
  for (unsigned i = 0; i < dimension; ++i) {
    const unsigned selected = i + splitmix64(generator) % (512 - i);
    std::swap(positions[i], positions[selected]);
  }
  return std::vector<unsigned>(positions.begin(), positions.begin() + dimension);
}

void clear_cube(uint8_t* message, const std::vector<unsigned>& cube) {
  for (unsigned position : cube) {
    message[position >> 3] &= static_cast<uint8_t>(~(1u << (position & 7)));
  }
}

void toggle_bit(uint8_t* message, unsigned position) {
  message[position >> 3] ^= static_cast<uint8_t>(1u << (position & 7));
}

void print_cube(const std::vector<unsigned>& cube) {
  std::printf("[");
  for (size_t i = 0; i < cube.size(); ++i) {
    if (i) std::printf(",");
    std::printf("%u", cube[i]);
  }
  std::printf("]");
}

}  // namespace

int main(int argc, char** argv) {
  const unsigned dimension = argc > 1
      ? static_cast<unsigned>(std::strtoul(argv[1], nullptr, 0)) : 12;
  const unsigned cube_sets = argc > 2
      ? static_cast<unsigned>(std::strtoul(argv[2], nullptr, 0)) : 16;
  const unsigned bases_per_cube = argc > 3
      ? static_cast<unsigned>(std::strtoul(argv[3], nullptr, 0)) : 64;
  uint64_t generator = argc > 4
      ? std::strtoull(argv[4], nullptr, 0) : UINT64_C(20260908);
  if (argc > 5 && std::freopen(argv[5], "w", stdout) == nullptr) return 3;
  if (!dimension || dimension > 28 || !cube_sets || !bases_per_cube) return 2;

  const uint64_t points_per_derivative = UINT64_C(1) << dimension;
  const uint64_t observations = uint64_t(cube_sets) * bases_per_cube;
  std::array<uint64_t, 128> one_counts{};
  uint64_t zero_vectors = 0;
  uint64_t total_weight = 0;
  unsigned minimum_weight = 129;
  unsigned maximum_weight = 0;
  double maximum_within_cube_abs_z = 0.0;
  std::vector<std::vector<unsigned>> cubes;
  cubes.reserve(cube_sets);

  for (unsigned cube_index = 0; cube_index < cube_sets; ++cube_index) {
    cubes.push_back(choose_cube(dimension, generator));
    const auto& cube = cubes.back();
    std::array<unsigned, 128> cube_one_counts{};
    for (unsigned base_index = 0; base_index < bases_per_cube; ++base_index) {
      uint8_t message[64];
      random_message(message, generator);
      clear_cube(message, cube);
      uint64_t derivative[2] = {};
      for (uint64_t point = 0; point < points_per_derivative; ++point) {
        if (point) toggle_bit(message, cube[__builtin_ctzll(point)]);
        uint64_t digest[2];
        rainstorm::rainstorm<128, false>(message, sizeof(message), 0, digest);
        derivative[0] ^= digest[0];
        derivative[1] ^= digest[1];
      }
      const unsigned weight = __builtin_popcountll(derivative[0]) +
                              __builtin_popcountll(derivative[1]);
      total_weight += weight;
      minimum_weight = std::min(minimum_weight, weight);
      maximum_weight = std::max(maximum_weight, weight);
      zero_vectors += weight == 0;
      for (unsigned bit = 0; bit < 128; ++bit) {
        const unsigned value = (derivative[bit >> 6] >> (bit & 63)) & 1;
        one_counts[bit] += value;
        cube_one_counts[bit] += value;
      }
    }
    const double denominator = std::sqrt(bases_per_cube * 0.25);
    for (unsigned bit = 0; bit < 128; ++bit) {
      const double z = (cube_one_counts[bit] - bases_per_cube * 0.5) /
                       denominator;
      maximum_within_cube_abs_z = std::max(maximum_within_cube_abs_z,
                                            std::abs(z));
    }
  }

  double maximum_global_abs_z = 0.0;
  unsigned maximum_global_bit = 0;
  const double global_denominator = std::sqrt(observations * 0.25);
  for (unsigned bit = 0; bit < 128; ++bit) {
    const double z = (one_counts[bit] - observations * 0.5) /
                     global_denominator;
    if (std::abs(z) > maximum_global_abs_z) {
      maximum_global_abs_z = std::abs(z);
      maximum_global_bit = bit;
    }
  }

  std::printf(
      "{\"experiment\":\"production-rainstorm128-higher-order-profile\","
      "\"production_version\":\"4.0.0\",\"message_length\":64,"
      "\"digest_bits\":128,\"cube_dimension\":%u,\"cube_sets\":%u,"
      "\"bases_per_cube\":%u,\"derivative_observations\":%llu,"
      "\"points_per_derivative\":%llu,\"hash_evaluations\":%llu,"
      "\"zero_derivative_vectors\":%llu,\"minimum_derivative_weight\":%u,"
      "\"maximum_derivative_weight\":%u,\"mean_derivative_weight\":%.9f,"
      "\"maximum_global_abs_z\":%.9f,\"maximum_global_bit\":%u,"
      "\"maximum_within_cube_abs_z\":%.9f,\"cube_bit_positions\":[",
      dimension, cube_sets, bases_per_cube,
      static_cast<unsigned long long>(observations),
      static_cast<unsigned long long>(points_per_derivative),
      static_cast<unsigned long long>(observations * points_per_derivative),
      static_cast<unsigned long long>(zero_vectors), minimum_weight,
      maximum_weight, static_cast<double>(total_weight) / observations,
      maximum_global_abs_z, maximum_global_bit, maximum_within_cube_abs_z);
  for (unsigned i = 0; i < cubes.size(); ++i) {
    if (i) std::printf(",");
    print_cube(cubes[i]);
  }
  std::printf(
      "],\"interpretation\":\"XOR sums are highest-order Boolean derivatives "
      "on the recorded affine cubes. Structural zero sums or repeatable output-"
      "bit bias are distinguishers; isolated extrema require held-out validation.\"}\n");
  return 0;
}
