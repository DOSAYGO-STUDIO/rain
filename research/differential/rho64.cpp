#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

#include "../../src/rainstorm.cpp"

enum class MappingMode { FullRainstorm64, ProgrammedReduced };

static MappingMode mapping_mode = MappingMode::FullRainstorm64;
static unsigned programmed_message_rounds = 2;
static unsigned programmed_lane_p = 6;
static unsigned programmed_lane_q = 7;

static uint64_t programmed_reduced(uint64_t value, uint64_t* message,
                                   uint64_t* fold_words = nullptr,
                                   uint64_t* reduced_digest = nullptr) {
  static constexpr uint64_t primes[16] = {
      1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47};
  uint64_t h[16];
  for (unsigned i = 0; i < 16; ++i) h[i] = 64 + primes[i];

  // Program the output y of the first (right) round.  y[0] = y[1] = 0
  // makes folded word 1 identically zero after the following left round.
  // The nonzero pair has sum zero, which leaves one free 64-bit parameter.
  uint64_t y[8] = {};
  y[programmed_lane_p] = value;
  y[programmed_lane_q] = uint64_t(0) - value;
  uint64_t data[8];
  uint64_t counter = rainstorm::CTR_RIGHT;
  for (unsigned i = 0; i < 8; ++i) {
    uint64_t incoming = h[8 + i];
    if (i) incoming -= counter;
    data[i] = incoming ^
        (ROTR64(y[i], 64 - rainstorm::Z[i]) + rainstorm::K[i]);
    counter += y[i];
  }

  for (unsigned round = 0; round < programmed_message_rounds; ++round) {
    rainstorm::weakfunc(h, data, round & 1);
  }
  if (message) std::memcpy(message, data, sizeof(data));
  const uint64_t first_fold_word = h[0] - h[8];
  if (fold_words) {
    for (unsigned i = 0; i < 8; ++i) fold_words[i] = h[i] - h[8 + i];
  }
  if (reduced_digest) {
    for (unsigned i = 0; i < 8; ++i) h[i] -= h[8 + i];
    const uint64_t padding[8] = {
        UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
        UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
        UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080),
        UINT64_C(0x8080808080808080), UINT64_C(0x8080808080808080)};
    // Rainstorm-256 uses four final left rounds.
    for (unsigned round = 0; round < 4; ++round) {
      rainstorm::weakfunc(h, padding, true);
    }
    for (unsigned i = 0; i < 4; ++i) reduced_digest[i] = h[i];
  }
  return first_fold_word;
}

static inline uint64_t step(uint64_t value) {
  if (mapping_mode == MappingMode::ProgrammedReduced) {
    return programmed_reduced(value, nullptr);
  }
  uint64_t output;
  rainstorm::rainstorm<64, false>(&value, sizeof(value), 0, &output);
  return output;
}

struct Record {
  uint64_t start;
  uint32_t length;
};

static uint64_t splitmix64(uint64_t& state) {
  uint64_t value = (state += UINT64_C(0x9e3779b97f4a7c15));
  value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
  value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
  return value ^ (value >> 31);
}

static std::string little_hex(uint64_t value) {
  static constexpr char alphabet[] = "0123456789abcdef";
  std::string rendered(16, '0');
  for (size_t byte = 0; byte < 8; ++byte) {
    const uint8_t item = static_cast<uint8_t>(value >> (8 * byte));
    rendered[2 * byte] = alphabet[item >> 4];
    rendered[2 * byte + 1] = alphabet[item & 15];
  }
  return rendered;
}

static std::string programmed_message_hex(uint64_t value) {
  uint64_t words[8];
  programmed_reduced(value, words);
  std::string rendered;
  rendered.reserve(128);
  for (uint64_t word : words) rendered += little_hex(word);
  return rendered;
}

static std::string little_words_hex(const uint64_t* words, size_t count) {
  std::string rendered;
  rendered.reserve(count * 16);
  for (size_t i = 0; i < count; ++i) rendered += little_hex(words[i]);
  return rendered;
}

static const char* programmed_mapping_name() {
  return programmed_message_rounds == 2
      ? "two-round-zero-prefix-zero-sum-programmed-family"
      : "three-round-fold-word-zero-projection";
}

static bool recover_collision(const Record& first, const Record& second,
                              uint64_t& message_a, uint64_t& message_b,
                              uint64_t& digest, uint64_t& replay_evaluations) {
  uint64_t a = first.start;
  uint64_t b = second.start;
  uint32_t length_a = first.length;
  uint32_t length_b = second.length;
  while (length_a > length_b) {
    a = step(a);
    --length_a;
    ++replay_evaluations;
  }
  while (length_b > length_a) {
    b = step(b);
    --length_b;
    ++replay_evaluations;
  }
  // In a permutation or a same-path overlap, alignment reaches an identical
  // state without exposing distinct predecessors.
  if (a == b) return false;
  uint64_t previous_a = a;
  uint64_t previous_b = b;
  while (a != b && length_a) {
    previous_a = a;
    previous_b = b;
    a = step(a);
    b = step(b);
    --length_a;
    replay_evaluations += 2;
  }
  if (a != b || previous_a == previous_b) return false;
  const uint64_t check_a = step(previous_a);
  const uint64_t check_b = step(previous_b);
  replay_evaluations += 2;
  if (check_a != check_b) return false;
  message_a = previous_a;
  message_b = previous_b;
  digest = check_a;
  return true;
}

static int search(uint64_t maximum_evaluations, unsigned distinguished_bits,
                  size_t streams, uint64_t seed) {
  if (!maximum_evaluations || !streams || distinguished_bits < 8 ||
      distinguished_bits > 28) {
    return 2;
  }
  const uint64_t distinguished_mask =
      (UINT64_C(1) << distinguished_bits) - 1;
  const uint64_t maximum_chain = UINT64_C(20) << distinguished_bits;
  struct Walk { uint64_t start; uint64_t current; uint32_t length; };
  std::vector<Walk> walks(streams);
  uint64_t generator = seed;
  for (Walk& walk : walks) {
    walk.start = walk.current = splitmix64(generator);
    walk.length = 0;
  }
  std::unordered_map<uint64_t, Record> endpoints;
  const uint64_t expected_endpoints =
      maximum_evaluations >> distinguished_bits;
  endpoints.reserve(static_cast<size_t>(expected_endpoints * 2 + 1024));
  uint64_t evaluations = 0;
  uint64_t replay_evaluations = 0;
  uint64_t endpoint_merges = 0;
  uint64_t same_path_merges = 0;
  uint64_t abandoned_chains = 0;
  uint64_t next_progress = UINT64_C(1000000000);
  const auto started = std::chrono::steady_clock::now();

  auto restart = [&](Walk& walk) {
    walk.start = walk.current = splitmix64(generator);
    walk.length = 0;
  };

  while (evaluations < maximum_evaluations) {
    for (Walk& walk : walks) {
      if (evaluations >= maximum_evaluations) break;
      walk.current = step(walk.current);
      ++walk.length;
      ++evaluations;
      if ((walk.current & distinguished_mask) == 0) {
        const Record current{walk.start, walk.length};
        const auto [position, inserted] = endpoints.emplace(walk.current, current);
        if (!inserted && position->second.start != current.start) {
          ++endpoint_merges;
          uint64_t message_a = 0;
          uint64_t message_b = 0;
          uint64_t digest = 0;
          if (recover_collision(position->second, current, message_a, message_b,
                                digest, replay_evaluations)) {
            const double seconds = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - started).count();
            if (mapping_mode == MappingMode::ProgrammedReduced) {
              uint64_t fold_a[8];
              uint64_t fold_b[8];
              uint64_t reduced_a[4];
              uint64_t reduced_b[4];
              const uint64_t fold0_a = programmed_reduced(
                  message_a, nullptr, fold_a, reduced_a);
              const uint64_t fold0_b = programmed_reduced(
                  message_b, nullptr, fold_b, reduced_b);
              if (fold0_a != fold0_b) return 3;
              unsigned equal_prefix_words = 0;
              while (equal_prefix_words < 8 &&
                     fold_a[equal_prefix_words] == fold_b[equal_prefix_words]) {
                ++equal_prefix_words;
              }
              bool reduced_collision = true;
              for (unsigned i = 0; i < 4; ++i) {
                reduced_collision &= reduced_a[i] == reduced_b[i];
              }
              if (programmed_message_rounds == 2 &&
                  (equal_prefix_words < 6 || !reduced_collision)) return 3;
              std::printf(
                  "{\"status\":\"%s\","
                  "\"mapping\":\"%s\","
                  "\"production_equivalent\":false,\"message_length\":64,"
                  "\"message_rounds\":%u,\"padding_rounds\":0,"
                  "\"searched_projection_bits\":64,"
                  "\"equal_fold_prefix_bits\":%u,"
                  "\"reduced_digest_bits\":256,\"parameter_a_hex\":\"%s\","
                  "\"parameter_b_hex\":\"%s\",\"message_a_hex\":\"%s\","
                  "\"message_b_hex\":\"%s\",\"fold_prefix_hex\":\"%s\","
                  "\"reduced_digest_hex\":\"%s\","
                  "\"reduced_digest_collision\":%s,"
                  "\"programmed_lanes\":[%u,%u],"
                  "\"walk_evaluations\":%llu,\"replay_evaluations\":%llu,"
                  "\"distinguished_bits\":%u,\"stored_endpoints\":%zu,"
                  "\"endpoint_merges\":%llu,\"same_path_merges\":%llu,"
                  "\"abandoned_chains\":%llu,\"seconds\":%.9f,"
                  "\"evaluations_per_second\":%.3f}\n",
                  reduced_collision ? "collision" : "projection-collision",
                  programmed_mapping_name(), programmed_message_rounds,
                  equal_prefix_words * 64,
                  little_hex(message_a).c_str(), little_hex(message_b).c_str(),
                  programmed_message_hex(message_a).c_str(),
                  programmed_message_hex(message_b).c_str(),
                  little_words_hex(fold_a, 6).c_str(),
                  little_words_hex(reduced_a, 4).c_str(),
                  reduced_collision ? "true" : "false", programmed_lane_p,
                  programmed_lane_q,
                  static_cast<unsigned long long>(evaluations),
                  static_cast<unsigned long long>(replay_evaluations),
                  distinguished_bits, endpoints.size(),
                  static_cast<unsigned long long>(endpoint_merges),
                  static_cast<unsigned long long>(same_path_merges),
                  static_cast<unsigned long long>(abandoned_chains), seconds,
                  evaluations / seconds);
            } else {
              std::printf(
                  "{\"status\":\"collision\",\"message_length\":8,"
                  "\"digest_bits\":64,\"message_a_hex\":\"%s\","
                  "\"message_b_hex\":\"%s\",\"digest_hex\":\"%s\","
                  "\"walk_evaluations\":%llu,\"replay_evaluations\":%llu,"
                  "\"distinguished_bits\":%u,\"stored_endpoints\":%zu,"
                  "\"endpoint_merges\":%llu,\"same_path_merges\":%llu,"
                  "\"abandoned_chains\":%llu,\"seconds\":%.9f,"
                  "\"evaluations_per_second\":%.3f}\n",
                  little_hex(message_a).c_str(), little_hex(message_b).c_str(),
                  little_hex(digest).c_str(),
                  static_cast<unsigned long long>(evaluations),
                  static_cast<unsigned long long>(replay_evaluations),
                  distinguished_bits, endpoints.size(),
                  static_cast<unsigned long long>(endpoint_merges),
                  static_cast<unsigned long long>(same_path_merges),
                  static_cast<unsigned long long>(abandoned_chains), seconds,
                  evaluations / seconds);
            }
            return 0;
          }
          ++same_path_merges;
        }
        restart(walk);
      } else if (walk.length >= maximum_chain) {
        ++abandoned_chains;
        restart(walk);
      }
      if (evaluations >= next_progress) {
        const double seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();
        std::fprintf(stderr,
            "progress evaluations=%llu endpoints=%zu merges=%llu same_path=%llu "
            "seconds=%.3f\n",
            static_cast<unsigned long long>(evaluations), endpoints.size(),
            static_cast<unsigned long long>(endpoint_merges),
            static_cast<unsigned long long>(same_path_merges), seconds);
        next_progress += UINT64_C(1000000000);
      }
    }
  }
  const double seconds = std::chrono::duration<double>(
      std::chrono::steady_clock::now() - started).count();
  std::printf(
      "{\"status\":\"budget-exhausted\",\"mapping\":\"%s\","
      "\"message_length\":%u,\"target_bits\":%u,\"walk_evaluations\":%llu,"
      "\"replay_evaluations\":%llu,\"distinguished_bits\":%u,"
      "\"stored_endpoints\":%zu,\"endpoint_merges\":%llu,"
      "\"same_path_merges\":%llu,\"abandoned_chains\":%llu,"
      "\"seconds\":%.9f,\"evaluations_per_second\":%.3f}\n",
      mapping_mode == MappingMode::ProgrammedReduced
          ? programmed_mapping_name()
          : "full-rainstorm-64",
      mapping_mode == MappingMode::ProgrammedReduced ? 64 : 8,
      mapping_mode == MappingMode::ProgrammedReduced
          ? (programmed_message_rounds == 2 ? 384 : 64) : 64,
      static_cast<unsigned long long>(evaluations),
      static_cast<unsigned long long>(replay_evaluations), distinguished_bits,
      endpoints.size(), static_cast<unsigned long long>(endpoint_merges),
      static_cast<unsigned long long>(same_path_merges),
      static_cast<unsigned long long>(abandoned_chains), seconds,
      evaluations / seconds);
  return 1;
}

int main(int argc, char** argv) {
  if (argc > 1 && (std::strcmp(argv[1], "search") == 0 ||
                   std::strcmp(argv[1], "search-two-round") == 0 ||
                   std::strcmp(argv[1], "search-three-round-projection") == 0)) {
    const bool programmed = std::strcmp(argv[1], "search") != 0;
    mapping_mode = programmed ? MappingMode::ProgrammedReduced
                              : MappingMode::FullRainstorm64;
    programmed_message_rounds =
        std::strcmp(argv[1], "search-three-round-projection") == 0 ? 3 : 2;
    const uint64_t maximum = argc > 2
        ? std::strtoull(argv[2], nullptr, 0) : UINT64_C(12000000000);
    const unsigned distinguished = argc > 3
        ? static_cast<unsigned>(std::strtoul(argv[3], nullptr, 0)) : 16;
    const size_t search_streams = argc > 4
        ? std::strtoull(argv[4], nullptr, 0) : 64;
    const uint64_t seed = argc > 5
        ? std::strtoull(argv[5], nullptr, 0) : UINT64_C(20260908);
    if (programmed) {
      programmed_lane_p = argc > 6
          ? static_cast<unsigned>(std::strtoul(argv[6], nullptr, 0)) : 6;
      programmed_lane_q = argc > 7
          ? static_cast<unsigned>(std::strtoul(argv[7], nullptr, 0)) : 7;
      if (programmed_lane_p < 2 || programmed_lane_p > 7 ||
          programmed_lane_q < 2 || programmed_lane_q > 7 ||
          programmed_lane_p == programmed_lane_q) return 2;
    }
    return search(maximum, distinguished, search_streams, seed);
  }
  uint64_t evaluations = UINT64_C(10000000);
  size_t streams = 8;
  if (argc > 1) evaluations = std::strtoull(argv[1], nullptr, 0);
  if (argc > 2) streams = std::strtoull(argv[2], nullptr, 0);
  if (!evaluations || !streams) return 2;
  std::vector<uint64_t> state(streams);
  for (size_t i = 0; i < streams; ++i) {
    state[i] = UINT64_C(0x9e3779b97f4a7c15) * (i + 1);
  }
  const auto started = std::chrono::steady_clock::now();
  uint64_t completed = 0;
  while (completed < evaluations) {
    for (size_t i = 0; i < streams && completed < evaluations; ++i, ++completed) {
      state[i] = step(state[i]);
    }
  }
  const auto stopped = std::chrono::steady_clock::now();
  const double seconds = std::chrono::duration<double>(stopped - started).count();
  uint64_t checksum = 0;
  for (uint64_t value : state) checksum ^= value;
  std::printf(
      "{\"evaluations\":%llu,\"streams\":%zu,\"seconds\":%.9f,"
      "\"evaluations_per_second\":%.3f,\"checksum\":\"0x%016llx\"}\n",
      static_cast<unsigned long long>(evaluations), streams, seconds,
      evaluations / seconds, static_cast<unsigned long long>(checksum));
  return 0;
}
