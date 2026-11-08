// Rainbow pair-sum collision attack.
//
// Rainbow injects each complete 16-byte block as
//     h0 -= x   h1 += x        h2 += y   h3 -= y
// so message injection PRESERVES the two pair sums h0+h1 and h2+h3, and the
// attacker chooses freely where inside that coset the pair lands.  mixA keeps
// (h0,h1) and (h2,h3) independent, so after a mixA block the whole future of a
// pair is determined by ONE 64-bit value -- its pair sum -- not by its 128 bits.
//
// For two equal-length messages with the same seed the initial state is equal,
// so fixing the first block's second word makes (h2,h3) evolve identically and
// only ONE 64-bit function has to collide:
//
//     A(x) = ROTR64((s0 - x) * P, 23) * Q
//     B(x) = ROTR64(((s1 + x) ^ A(x)) * R, 29) * S
//     H(x) = A(x) + B(x)
//
// Given H(xa) == H(xb), the next block's first word p_i = -B(x_i) drives both
// first pairs to the identical point (H, 0): h1 = B + (-B) = 0 and
// h0 = A - (-B) = A + B = H.  The complete four-word state is then equal before
// that block's mixer, so every later operation -- mixB, rotate_right, the tail,
// finalization and every digest width -- is identical.
//
// The search is a van Oorschot-Wiener parallel distinguished-point rho on H.
// Nothing here modifies Rainbow; replay_production.cpp hashes the emitted bytes
// with the untouched src/rainbow.cpp.

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

// ---------------------------------------------------------------- constants
// Reproduced from src/rainbow.cpp (NOT included, so the attack cannot depend on
// or accidentally modify production code; replay uses the real file).
namespace bowc {
static const uint64_t P = UINT64_C(0xFFFFFFFFFFFFFFFF) - 58;
static const uint64_t Q = UINT64_C(13166748625691186689);
static const uint64_t R = UINT64_C(1573836600196043749);
static const uint64_t S = UINT64_C(1478582680485693857);
static const uint64_t T = UINT64_C(1584163446043636637);
static const uint64_t U = UINT64_C(1358537349836140151);
static const uint64_t V = UINT64_C(2849285319520710901);
static const uint64_t W = UINT64_C(2366157163652459183);
}  // namespace bowc

static inline uint64_t rotr64(uint64_t x, unsigned n) {
  return (x >> n) | (x << (64 - n));
}

// ------------------------------------------------------- reference Rainbow
// A faithful re-implementation used ONLY for the internal state trace and a
// self-check.  The authority is src/rainbow.cpp via replay_production.cpp.
struct State {
  uint64_t h[4];
};

static inline void mixA(uint64_t* s) {
  uint64_t a = s[0], b = s[1], c = s[2], d = s[3];
  a *= bowc::P; a = rotr64(a, 23); a *= bowc::Q;
  b ^= a;
  b *= bowc::R; b = rotr64(b, 29); b *= bowc::S;
  c *= bowc::T; c = rotr64(c, 31); c *= bowc::U;
  d ^= c;
  d *= bowc::V; d = rotr64(d, 37); d *= bowc::W;
  s[0] = a; s[1] = b; s[2] = c; s[3] = d;
}

static inline void mixB(uint64_t* s, uint64_t iv) {
  uint64_t a = s[1], b = s[2];
  a *= bowc::V; a = rotr64(a, 23); a *= bowc::W;
  b ^= a + iv;
  b *= bowc::R; b = rotr64(b, 23); b *= bowc::S;
  s[1] = b; s[2] = a;
}

static inline void rotate_right(uint64_t* h) {
  uint64_t t = h[3];
  h[3] = h[2]; h[2] = h[1]; h[1] = h[0]; h[0] = t;
}

static inline uint64_t get_u64_le(const uint8_t* d, size_t i) {
  uint64_t r; std::memcpy(&r, d + i, 8); return r;  // attack host is LE
}
static inline void put_u64_le(uint64_t v, uint8_t* d, size_t i) {
  std::memcpy(d + i, &v, 8);
}

// Full reference hash, mirroring the single-call template in src/rainbow.cpp.
static void rainbow_ref(const uint8_t* data, size_t olen, uint64_t seed,
                        uint32_t hashsize, uint8_t* out) {
  uint64_t h[4] = {seed + olen + 1, seed + olen + 2, seed + olen + 3,
                   seed + olen + 5};
  size_t len = olen;
  bool inner = false;
  while (len >= 16) {
    uint64_t g = get_u64_le(data, 0);
    h[0] -= g; h[1] += g;
    data += 8;
    g = get_u64_le(data, 0);
    h[2] += g; h[3] -= g;
    if (inner) { mixB(h, seed); rotate_right(h); } else { mixA(h); }
    inner = !inner;
    data += 8;
    len -= 16;
  }
  mixB(h, seed);
  switch (len) {  // only reached for a partial tail; our messages are aligned
    case 15: h[0] += (uint64_t)data[14] << 56; [[fallthrough]];
    case 14: h[1] += (uint64_t)data[13] << 48; [[fallthrough]];
    case 13: h[2] += (uint64_t)data[12] << 40; [[fallthrough]];
    case 12: h[3] += (uint64_t)data[11] << 32; [[fallthrough]];
    case 11: h[0] += (uint64_t)data[10] << 24; [[fallthrough]];
    case 10: h[1] += (uint64_t)data[9] << 16; [[fallthrough]];
    case 9:  h[2] += (uint64_t)data[8] << 8; [[fallthrough]];
    case 8:  h[3] += data[7]; [[fallthrough]];
    case 7:  h[0] += (uint64_t)data[6] << 48; [[fallthrough]];
    case 6:  h[1] += (uint64_t)data[5] << 40; [[fallthrough]];
    case 5:  h[2] += (uint64_t)data[4] << 32; [[fallthrough]];
    case 4:  h[3] += (uint64_t)data[3] << 24; [[fallthrough]];
    case 3:  h[0] += (uint64_t)data[2] << 16; [[fallthrough]];
    case 2:  h[1] += (uint64_t)data[1] << 8; [[fallthrough]];
    case 1:  h[2] += (uint64_t)data[0];
    default: break;
  }
  mixA(h); mixB(h, seed); mixA(h);
  uint64_t g = 0; g -= h[2]; g -= h[3];
  put_u64_le(g, out, 0);
  if (hashsize == 128) {
    mixA(h); g = 0; g -= h[3]; g -= h[2]; put_u64_le(g, out, 8);
  } else if (hashsize == 256) {
    mixA(h); g = 0; g -= h[3]; g -= h[2]; put_u64_le(g, out, 8);
    mixA(h); mixB(h, seed); mixA(h);
    g = 0; g -= h[3]; g -= h[2]; put_u64_le(g, out, 16);
    mixA(h); g = 0; g -= h[3]; g -= h[2]; put_u64_le(g, out, 24);
  }
}

// ------------------------------------------------------------- the H map
static uint64_t S0, S1, S2, S3;  // initial state words for (seed, olen)

struct Pair { uint64_t a, b; };

static inline Pair first_pair_after_mixA(uint64_t h0, uint64_t h1) {
  uint64_t a = h0 * bowc::P; a = rotr64(a, 23); a *= bowc::Q;
  uint64_t b = h1 ^ a; b *= bowc::R; b = rotr64(b, 29); b *= bowc::S;
  return Pair{a, b};
}

static inline Pair second_pair_after_mixA(uint64_t h2, uint64_t h3) {
  uint64_t c = h2 * bowc::T; c = rotr64(c, 31); c *= bowc::U;
  uint64_t d = h3 ^ c; d *= bowc::V; d = rotr64(d, 37); d *= bowc::W;
  return Pair{c, d};
}

// H(x) = A(x) + B(x): the pair sum of the first pair after block 1 + mixA.
static inline uint64_t Hmap(uint64_t x) {
  uint64_t a = (S0 - x) * bowc::P; a = rotr64(a, 23); a *= bowc::Q;
  uint64_t b = (S1 + x) ^ a; b *= bowc::R; b = rotr64(b, 29); b *= bowc::S;
  return a + b;
}

// --------------------------------------------- distinguished-point rho search
struct WalkRecord {
  uint64_t start;
  uint64_t length;
};

static std::mutex g_map_mutex;
static std::unordered_map<uint64_t, WalkRecord> g_endpoints;
static std::atomic<uint64_t> g_evaluations{0};
static std::atomic<uint64_t> g_walks{0};
static std::atomic<uint64_t> g_merges{0};
static std::atomic<bool> g_found{false};
static uint64_t g_xa = 0, g_xb = 0;
static std::mutex g_result_mutex;

// Given two walk startpoints reaching one distinguished endpoint, step forward
// until the step BEFORE they meet: that pair is the collision.
static bool recover(uint64_t start1, uint64_t len1, uint64_t start2,
                    uint64_t len2, uint64_t& xa, uint64_t& xb) {
  if (start1 == start2) return false;  // same walk re-registered
  uint64_t a = start1, b = start2;
  uint64_t la = len1, lb = len2;
  while (la > lb) { a = Hmap(a); --la; }
  while (lb > la) { b = Hmap(b); --lb; }
  for (uint64_t i = 0; i <= la; ++i) {
    if (a == b) return false;  // walks merged at a point, not at a collision
    uint64_t na = Hmap(a), nb = Hmap(b);
    if (na == nb) { xa = a; xb = b; return a != b; }
    a = na; b = nb;
  }
  return false;
}

static void worker(unsigned id, unsigned dp_bits, uint64_t rng_seed) {
  const uint64_t dp_mask = (dp_bits >= 64) ? ~UINT64_C(0)
                                           : ((UINT64_C(1) << dp_bits) - 1);
  const uint64_t max_steps = UINT64_C(20) << dp_bits;
  std::mt19937_64 rng(rng_seed + id);
  uint64_t local_evals = 0;

  while (!g_found.load(std::memory_order_relaxed)) {
    const uint64_t start = rng();
    uint64_t x = start;
    uint64_t steps = 0;
    while ((x & dp_mask) != 0 && steps < max_steps) {
      x = Hmap(x);
      ++steps;
    }
    local_evals += steps;
    if (local_evals > (1u << 22)) {
      g_evaluations.fetch_add(local_evals, std::memory_order_relaxed);
      local_evals = 0;
    }
    if ((x & dp_mask) != 0) continue;  // abandoned: fell into a short cycle
    g_walks.fetch_add(1, std::memory_order_relaxed);

    WalkRecord other{0, 0};
    bool clash = false;
    {
      std::lock_guard<std::mutex> lock(g_map_mutex);
      auto it = g_endpoints.find(x);
      if (it == g_endpoints.end()) {
        g_endpoints.emplace(x, WalkRecord{start, steps});
      } else {
        other = it->second;
        clash = true;
      }
    }
    if (!clash) continue;
    g_merges.fetch_add(1, std::memory_order_relaxed);

    uint64_t xa = 0, xb = 0;
    if (recover(other.start, other.length, start, steps, xa, xb)) {
      std::lock_guard<std::mutex> lock(g_result_mutex);
      if (!g_found.exchange(true)) { g_xa = xa; g_xb = xb; }
      break;
    }
  }
  g_evaluations.fetch_add(local_evals, std::memory_order_relaxed);
}

// ------------------------------------------------------------------ output
static std::string hex_bytes(const uint8_t* data, size_t n) {
  static const char* digits = "0123456789abcdef";
  std::string out;
  out.reserve(n * 2);
  for (size_t i = 0; i < n; ++i) {
    out.push_back(digits[data[i] >> 4]);
    out.push_back(digits[data[i] & 15]);
  }
  return out;
}

int main(int argc, char** argv) {
  uint64_t seed = 0;
  unsigned dp_bits = 20;
  unsigned threads = std::thread::hardware_concurrency();
  uint64_t rng_seed = 0x5eed1234abcdULL;
  const char* json_path = "research/rainbow/collision-result.json";

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    auto value = [&](const char* key) -> const char* {
      return arg.compare(0, strlen(key), key) == 0 ? arg.c_str() + strlen(key)
                                                   : nullptr;
    };
    if (const char* v = value("--seed=")) seed = strtoull(v, nullptr, 0);
    else if (const char* v2 = value("--dp-bits=")) dp_bits = (unsigned)atoi(v2);
    else if (const char* v3 = value("--threads=")) threads = (unsigned)atoi(v3);
    else if (const char* v4 = value("--rng-seed=")) rng_seed = strtoull(v4, nullptr, 0);
    else if (const char* v5 = value("--json=")) json_path = v5;
    else { fprintf(stderr, "unknown argument: %s\n", argv[i]); return 2; }
  }
  if (threads == 0) threads = 4;

  // Both candidate messages are 32 bytes with the same seed, so they share
  // this initial state exactly.
  const size_t olen = 32;
  S0 = seed + olen + 1;
  S1 = seed + olen + 2;
  S2 = seed + olen + 3;
  S3 = seed + olen + 5;

  printf("rainbow pair-sum collision attack\n");
  printf("  seed=%" PRIu64 " message length=%zu bytes\n", seed, olen);
  printf("  initial state s0..s3 = %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",
         S0, S1, S2, S3);
  printf("  searching H(x) = A(x) + B(x) with %u threads, %u distinguished bits\n",
         threads, dp_bits);
  fflush(stdout);

  const auto t0 = std::chrono::steady_clock::now();
  std::vector<std::thread> pool;
  for (unsigned i = 0; i < threads; ++i)
    pool.emplace_back(worker, i, dp_bits, rng_seed);
  for (auto& t : pool) t.join();
  const auto t1 = std::chrono::steady_clock::now();
  const double wall = std::chrono::duration<double>(t1 - t0).count();

  if (!g_found.load()) {
    fprintf(stderr, "no collision found\n");
    return 1;
  }

  const uint64_t xa = g_xa, xb = g_xb;
  const uint64_t evaluations = g_evaluations.load();
  const Pair pa = first_pair_after_mixA(S0 - xa, S1 + xa);
  const Pair pb = first_pair_after_mixA(S0 - xb, S1 + xb);
  const uint64_t Ha = pa.a + pa.b, Hb = pb.a + pb.b;

  printf("\ncollision in H\n");
  printf("  xa = %" PRIu64 " (0x%016" PRIx64 ")\n", xa, xa);
  printf("  xb = %" PRIu64 " (0x%016" PRIx64 ")\n", xb, xb);
  printf("  A(xa)=0x%016" PRIx64 "  B(xa)=0x%016" PRIx64 "\n", pa.a, pa.b);
  printf("  A(xb)=0x%016" PRIx64 "  B(xb)=0x%016" PRIx64 "\n", pb.a, pb.b);
  printf("  H(xa)=0x%016" PRIx64 "  H(xb)=0x%016" PRIx64 "  equal=%s\n", Ha, Hb,
         Ha == Hb ? "yes" : "NO");
  printf("  evaluations=%" PRIu64 " (2^%.2f) walks=%" PRIu64 " merges=%" PRIu64 "\n",
         evaluations, evaluations ? log2((double)evaluations) : 0.0,
         g_walks.load(), g_merges.load());
  printf("  wall=%.2fs throughput=%.2f Meval/s\n", wall,
         wall > 0 ? evaluations / wall / 1e6 : 0.0);

  if (xa == xb || Ha != Hb) {
    fprintf(stderr, "invalid collision candidate\n");
    return 1;
  }

  // Bridge: the second block's first word drives each first pair to (H, 0).
  const uint64_t p_a = (uint64_t)0 - pa.b;
  const uint64_t p_b = (uint64_t)0 - pb.b;

  uint8_t msg_a[32], msg_b[32];
  put_u64_le(xa, msg_a, 0);  put_u64_le(0, msg_a, 8);
  put_u64_le(p_a, msg_a, 16); put_u64_le(0, msg_a, 24);
  put_u64_le(xb, msg_b, 0);  put_u64_le(0, msg_b, 8);
  put_u64_le(p_b, msg_b, 16); put_u64_le(0, msg_b, 24);

  if (std::memcmp(msg_a, msg_b, 32) == 0) {
    fprintf(stderr, "messages are identical\n");
    return 1;
  }

  // State trace: prove the merge point explicitly.
  auto trace_to_merge = [&](const uint8_t* m, uint64_t st[4]) {
    uint64_t h[4] = {S0, S1, S2, S3};
    uint64_t x = get_u64_le(m, 0), y = get_u64_le(m, 8);
    h[0] -= x; h[1] += x; h[2] += y; h[3] -= y;   // block 1 injection
    mixA(h);                                       // first mixer
    uint64_t p = get_u64_le(m, 16), q = get_u64_le(m, 24);
    h[0] -= p; h[1] += p; h[2] += q; h[3] -= q;   // block 2 injection
    memcpy(st, h, sizeof(uint64_t) * 4);
  };
  uint64_t merge_a[4], merge_b[4];
  trace_to_merge(msg_a, merge_a);
  trace_to_merge(msg_b, merge_b);
  const bool merged = memcmp(merge_a, merge_b, sizeof(merge_a)) == 0;
  printf("\nstate after block-2 injection\n");
  printf("  a: %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
         merge_a[0], merge_a[1], merge_a[2], merge_a[3]);
  printf("  b: %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
         merge_b[0], merge_b[1], merge_b[2], merge_b[3]);
  printf("  identical=%s\n", merged ? "yes" : "NO");

  // Self-check with the reference implementation at all three widths.
  uint8_t da64[8], db64[8], da128[16], db128[16], da256[32], db256[32];
  rainbow_ref(msg_a, 32, seed, 64, da64);
  rainbow_ref(msg_b, 32, seed, 64, db64);
  rainbow_ref(msg_a, 32, seed, 128, da128);
  rainbow_ref(msg_b, 32, seed, 128, db128);
  rainbow_ref(msg_a, 32, seed, 256, da256);
  rainbow_ref(msg_b, 32, seed, 256, db256);
  const bool eq64 = memcmp(da64, db64, 8) == 0;
  const bool eq128 = memcmp(da128, db128, 16) == 0;
  const bool eq256 = memcmp(da256, db256, 32) == 0;

  printf("\nmessages\n");
  printf("  a = %s\n", hex_bytes(msg_a, 32).c_str());
  printf("  b = %s\n", hex_bytes(msg_b, 32).c_str());
  printf("reference digests (attack's own implementation)\n");
  printf("  64  a=%s b=%s equal=%s\n", hex_bytes(da64, 8).c_str(),
         hex_bytes(db64, 8).c_str(), eq64 ? "yes" : "NO");
  printf("  128 a=%s b=%s equal=%s\n", hex_bytes(da128, 16).c_str(),
         hex_bytes(db128, 16).c_str(), eq128 ? "yes" : "NO");
  printf("  256 a=%s b=%s equal=%s\n", hex_bytes(da256, 32).c_str(),
         hex_bytes(db256, 32).c_str(), eq256 ? "yes" : "NO");

  FILE* f = fopen(json_path, "w");
  if (!f) { perror("open json"); return 1; }
  fprintf(f, "{\n");
  fprintf(f, "  \"attack\": \"rainbow-pair-sum-32-byte\",\n");
  fprintf(f, "  \"seed\": %" PRIu64 ",\n", seed);
  fprintf(f, "  \"message_length\": 32,\n");
  fprintf(f, "  \"initial_state\": [%" PRIu64 ", %" PRIu64 ", %" PRIu64 ", %" PRIu64 "],\n",
          S0, S1, S2, S3);
  fprintf(f, "  \"xa\": %" PRIu64 ",\n  \"xb\": %" PRIu64 ",\n", xa, xb);
  fprintf(f, "  \"A_xa\": %" PRIu64 ",\n  \"B_xa\": %" PRIu64 ",\n", pa.a, pa.b);
  fprintf(f, "  \"A_xb\": %" PRIu64 ",\n  \"B_xb\": %" PRIu64 ",\n", pb.a, pb.b);
  fprintf(f, "  \"H\": %" PRIu64 ",\n", Ha);
  fprintf(f, "  \"bridge_pa\": %" PRIu64 ",\n  \"bridge_pb\": %" PRIu64 ",\n", p_a, p_b);
  fprintf(f, "  \"message_a\": \"%s\",\n", hex_bytes(msg_a, 32).c_str());
  fprintf(f, "  \"message_b\": \"%s\",\n", hex_bytes(msg_b, 32).c_str());
  fprintf(f, "  \"merged_state\": [%" PRIu64 ", %" PRIu64 ", %" PRIu64 ", %" PRIu64 "],\n",
          merge_a[0], merge_a[1], merge_a[2], merge_a[3]);
  fprintf(f, "  \"state_merged\": %s,\n", merged ? "true" : "false");
  fprintf(f, "  \"reference_digest_64\": \"%s\",\n", hex_bytes(da64, 8).c_str());
  fprintf(f, "  \"reference_digest_128\": \"%s\",\n", hex_bytes(da128, 16).c_str());
  fprintf(f, "  \"reference_digest_256\": \"%s\",\n", hex_bytes(da256, 32).c_str());
  fprintf(f, "  \"search\": {\n");
  fprintf(f, "    \"evaluations\": %" PRIu64 ",\n", evaluations);
  fprintf(f, "    \"log2_evaluations\": %.4f,\n",
          evaluations ? log2((double)evaluations) : 0.0);
  fprintf(f, "    \"distinguished_bits\": %u,\n", dp_bits);
  fprintf(f, "    \"walks\": %" PRIu64 ",\n", g_walks.load());
  fprintf(f, "    \"endpoints\": %zu,\n", g_endpoints.size());
  fprintf(f, "    \"merges\": %" PRIu64 ",\n", g_merges.load());
  fprintf(f, "    \"threads\": %u,\n", threads);
  fprintf(f, "    \"rng_seed\": %" PRIu64 ",\n", rng_seed);
  fprintf(f, "    \"wall_seconds\": %.3f,\n", wall);
  fprintf(f, "    \"throughput_meval_per_s\": %.3f\n", wall > 0 ? evaluations / wall / 1e6 : 0.0);
  fprintf(f, "  }\n}\n");
  fclose(f);
  printf("\nwrote %s\n", json_path);

  return (merged && eq64 && eq128 && eq256) ? 0 : 1;
}
