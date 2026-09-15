// Rainbow chosen-prefix collision, and a direct test of the pair-sum theorem.
//
// THEOREM (pair-sum equivalence).  Write the two pair sums of a Rainbow state as
//     s1 = h0 + h1        s2 = h2 + h3       (mod 2^64)
// Message injection is  h0 -= x, h1 += x, h2 += y, h3 -= y, so it preserves both
// sums exactly while moving the state freely inside the coset they define.
// Therefore two states S and T at the same block index can be merged into the
// SAME state by one further message block, with ZERO search, if and only if
// s1(S) == s1(T) and s2(S) == s2(T): pick x freely and set x' = x + (t0 - s0),
// which forces t1 + x' = s1 + x automatically.  The state's collision-relevant
// content is thus the 128-bit pair of sums, not its 256 bits.
//
// mixA is the only step that refreshes those sums, and it acts on (h0,h1) and
// (h2,h3) INDEPENDENTLY.  So the two 64-bit sums can be attacked separately:
//     H(x) = A(x) + B(x)   from (h0,h1)
//     K(y) = C(y) + D(y)   from (h2,h3)
// Two 64-bit claws, ~2^32 each, merge ANY two states -- which is a chosen-prefix
// collision, at every digest width at once.
//
//   ./chosen_prefix_collision --prefix-a=<ascii> --prefix-b=<ascii>
//
// Prefix length must be equal for both (Rainbow is length-keyed) and a multiple
// of 32 bytes, so that the next block is a mixA block.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

// Deliberately re-derived here rather than shared with collision_pair_sum.cpp:
// an independent transcription is a cross-check, and replay_production.cpp
// remains the only authority.
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
static inline uint64_t get_u64_le(const uint8_t* d, size_t i) {
  uint64_t r; std::memcpy(&r, d + i, 8); return r;
}
static inline void put_u64_le(uint64_t v, uint8_t* d, size_t i) {
  std::memcpy(d + i, &v, 8);
}

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

// Absorb whole blocks only; returns the mixer parity for the NEXT block.
static bool absorb(uint64_t* h, const uint8_t* data, size_t len, uint64_t seed,
                   bool inner) {
  while (len >= 16) {
    uint64_t g = get_u64_le(data, 0);
    h[0] -= g; h[1] += g;
    g = get_u64_le(data, 8);
    h[2] += g; h[3] -= g;
    if (inner) { mixB(h, seed); rotate_right(h); } else { mixA(h); }
    inner = !inner;
    data += 16; len -= 16;
  }
  return inner;
}

static void rainbow_ref(const uint8_t* data, size_t olen, uint64_t seed,
                        uint32_t hashsize, uint8_t* out) {
  uint64_t h[4] = {seed + olen + 1, seed + olen + 2, seed + olen + 3,
                   seed + olen + 5};
  const size_t whole = olen - (olen % 16);
  absorb(h, data, whole, seed, false);
  const uint8_t* tail = data + whole;
  const size_t len = olen % 16;
  mixB(h, seed);
  switch (len) {
    case 15: h[0] += (uint64_t)tail[14] << 56; [[fallthrough]];
    case 14: h[1] += (uint64_t)tail[13] << 48; [[fallthrough]];
    case 13: h[2] += (uint64_t)tail[12] << 40; [[fallthrough]];
    case 12: h[3] += (uint64_t)tail[11] << 32; [[fallthrough]];
    case 11: h[0] += (uint64_t)tail[10] << 24; [[fallthrough]];
    case 10: h[1] += (uint64_t)tail[9] << 16; [[fallthrough]];
    case 9:  h[2] += (uint64_t)tail[8] << 8; [[fallthrough]];
    case 8:  h[3] += tail[7]; [[fallthrough]];
    case 7:  h[0] += (uint64_t)tail[6] << 48; [[fallthrough]];
    case 6:  h[1] += (uint64_t)tail[5] << 40; [[fallthrough]];
    case 5:  h[2] += (uint64_t)tail[4] << 32; [[fallthrough]];
    case 4:  h[3] += (uint64_t)tail[3] << 24; [[fallthrough]];
    case 3:  h[0] += (uint64_t)tail[2] << 16; [[fallthrough]];
    case 2:  h[1] += (uint64_t)tail[1] << 8; [[fallthrough]];
    case 1:  h[2] += (uint64_t)tail[0];
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

// ------------------------------------------------- per-pair mixA components
struct Pair { uint64_t a, b; };

static inline Pair firstPair(uint64_t h0, uint64_t h1) {
  uint64_t a = h0 * bowc::P; a = rotr64(a, 23); a *= bowc::Q;
  uint64_t b = h1 ^ a; b *= bowc::R; b = rotr64(b, 29); b *= bowc::S;
  return Pair{a, b};
}
static inline Pair secondPair(uint64_t h2, uint64_t h3) {
  uint64_t c = h2 * bowc::T; c = rotr64(c, 31); c *= bowc::U;
  uint64_t d = h3 ^ c; d *= bowc::V; d = rotr64(d, 37); d *= bowc::W;
  return Pair{c, d};
}

// ------------------------------------------- distinguished-point claw engine
struct SearchStats {
  uint64_t evaluations = 0;
  uint64_t walks = 0;
  uint64_t merges = 0;
  uint64_t endpoints = 0;
  double wall_seconds = 0;
};

// Finds w1 != w2 with f(w1) == f(w2) subject to accept(w1, w2).
template <class F, class Accept>
static bool dp_collision(const F& f, const Accept& accept, unsigned dp_bits,
                         unsigned threads, uint64_t rng_seed, uint64_t& out1,
                         uint64_t& out2, SearchStats& stats) {
  struct Record { uint64_t start, length; };
  std::unordered_map<uint64_t, Record> endpoints;
  std::mutex map_mutex, result_mutex;
  std::atomic<uint64_t> evaluations{0}, walks{0}, merges{0};
  std::atomic<bool> found{false};
  uint64_t r1 = 0, r2 = 0;

  const uint64_t dp_mask = (UINT64_C(1) << dp_bits) - 1;
  const uint64_t max_steps = UINT64_C(20) << dp_bits;
  const auto t0 = std::chrono::steady_clock::now();

  auto recover = [&](uint64_t sa, uint64_t la, uint64_t sb, uint64_t lb,
                     uint64_t& xa, uint64_t& xb) {
    if (sa == sb) return false;
    uint64_t a = sa, b = sb, na = la, nb = lb;
    while (na > nb) { a = f(a); --na; }
    while (nb > na) { b = f(b); --nb; }
    for (uint64_t i = 0; i <= na; ++i) {
      if (a == b) return false;
      const uint64_t fa = f(a), fb = f(b);
      if (fa == fb) { xa = a; xb = b; return a != b && accept(a, b); }
      a = fa; b = fb;
    }
    return false;
  };

  auto worker = [&](unsigned id) {
    std::mt19937_64 rng(rng_seed + 0x9E3779B97F4A7C15ULL * (id + 1));
    uint64_t local = 0;
    while (!found.load(std::memory_order_relaxed)) {
      const uint64_t start = rng();
      uint64_t x = start, steps = 0;
      while ((x & dp_mask) != 0 && steps < max_steps) { x = f(x); ++steps; }
      local += steps;
      if (local > (1u << 22)) {
        evaluations.fetch_add(local, std::memory_order_relaxed);
        local = 0;
      }
      if ((x & dp_mask) != 0) continue;
      walks.fetch_add(1, std::memory_order_relaxed);

      Record other{0, 0};
      bool clash = false;
      {
        std::lock_guard<std::mutex> lock(map_mutex);
        auto it = endpoints.find(x);
        if (it == endpoints.end()) endpoints.emplace(x, Record{start, steps});
        else { other = it->second; clash = true; }
      }
      if (!clash) continue;
      merges.fetch_add(1, std::memory_order_relaxed);

      uint64_t xa = 0, xb = 0;
      if (recover(other.start, other.length, start, steps, xa, xb)) {
        std::lock_guard<std::mutex> lock(result_mutex);
        if (!found.exchange(true)) { r1 = xa; r2 = xb; }
        return;
      }
    }
    evaluations.fetch_add(local, std::memory_order_relaxed);
  };

  std::vector<std::thread> pool;
  for (unsigned i = 0; i < threads; ++i) pool.emplace_back(worker, i);
  for (auto& t : pool) t.join();

  stats.evaluations = evaluations.load();
  stats.walks = walks.load();
  stats.merges = merges.load();
  stats.endpoints = endpoints.size();
  stats.wall_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  out1 = r1; out2 = r2;
  return found.load();
}

// A claw between two functions is a collision of the flavored combination.
static inline bool flavor(uint64_t w) {
  return (w * UINT64_C(0x9E3779B97F4A7C15)) >> 63;
}

static std::string hex_bytes(const uint8_t* data, size_t n) {
  static const char* digits = "0123456789abcdef";
  std::string out;
  for (size_t i = 0; i < n; ++i) {
    out.push_back(digits[data[i] >> 4]);
    out.push_back(digits[data[i] & 15]);
  }
  return out;
}

// -------------------------------------------------------- theorem self-test
// Random states with equal pair sums must merge with one block and no search.
static bool theorem_selftest(uint64_t seed) {
  std::mt19937_64 rng(0xC0FFEE);
  for (int trial = 0; trial < 1000; ++trial) {
    uint64_t S[4] = {rng(), rng(), rng(), rng()};
    uint64_t T[4];
    // Build T with the SAME pair sums but otherwise unrelated words.
    T[0] = rng(); T[1] = (S[0] + S[1]) - T[0];
    T[2] = rng(); T[3] = (S[2] + S[3]) - T[2];

    const uint64_t x = rng(), y = rng();
    // The negated word is h0 for the first pair but h3 for the second, so the
    // offsets are taken from opposite ends: x' from t0-s0, y' from t3-s3.
    const uint64_t xp = x + (T[0] - S[0]);
    const uint64_t yp = y + (T[3] - S[3]);

    uint64_t a[4] = {S[0] - x, S[1] + x, S[2] + y, S[3] - y};
    uint64_t b[4] = {T[0] - xp, T[1] + xp, T[2] + yp, T[3] - yp};
    if (std::memcmp(a, b, sizeof(a)) != 0) {
      printf("  theorem self-test FAILED at trial %d\n", trial);
      return false;
    }
    // And the merge survives either mixer, as identical states must.
    uint64_t a2[4], b2[4];
    memcpy(a2, a, sizeof(a)); memcpy(b2, b, sizeof(b));
    mixA(a2); mixA(b2);
    if (std::memcmp(a2, b2, sizeof(a2)) != 0) return false;
    memcpy(a2, a, sizeof(a)); memcpy(b2, b, sizeof(b));
    mixB(a2, seed); rotate_right(a2);
    mixB(b2, seed); rotate_right(b2);
    if (std::memcmp(a2, b2, sizeof(a2)) != 0) return false;
  }
  return true;
}

int main(int argc, char** argv) {
  std::string prefix_a = "From: alice@example.com  Amount: USD      10.00 ";
  std::string prefix_b = "From: mallory@example.net Amount: USD 1000000.00";
  uint64_t seed = 0;
  unsigned dp_bits = 20, threads = std::thread::hardware_concurrency();
  uint64_t rng_seed = 0xBEEFCAFEULL;
  const char* json_path = "research/rainbow/chosen-prefix-result.json";

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    auto value = [&](const char* key) -> const char* {
      return arg.compare(0, strlen(key), key) == 0 ? arg.c_str() + strlen(key)
                                                   : nullptr;
    };
    if (const char* v = value("--prefix-a=")) prefix_a = v;
    else if (const char* v2 = value("--prefix-b=")) prefix_b = v2;
    else if (const char* v3 = value("--seed=")) seed = strtoull(v3, nullptr, 0);
    else if (const char* v4 = value("--dp-bits=")) dp_bits = (unsigned)atoi(v4);
    else if (const char* v5 = value("--threads=")) threads = (unsigned)atoi(v5);
    else if (const char* v6 = value("--rng-seed=")) rng_seed = strtoull(v6, nullptr, 0);
    else if (const char* v7 = value("--json=")) json_path = v7;
    else { fprintf(stderr, "unknown argument: %s\n", argv[i]); return 2; }
  }
  if (threads == 0) threads = 4;

  printf("pair-sum theorem self-test: ");
  fflush(stdout);
  if (!theorem_selftest(seed)) { printf("FAILED\n"); return 1; }
  printf("1000/1000 random equal-pair-sum state pairs merged in one block, "
         "zero search\n\n");

  if (prefix_a == prefix_b) { fprintf(stderr, "prefixes are identical\n"); return 2; }
  // Space-pad both to a common 32-byte boundary. Rainbow is length-keyed so the
  // two messages must match in length, and a multiple of 32 leaves the next
  // block a mixA block. The padding is simply part of the chosen prefix.
  const size_t want =
      ((std::max(prefix_a.size(), prefix_b.size()) + 31) / 32) * 32;
  if (prefix_a.size() != want || prefix_b.size() != want) {
    printf("padding prefixes with spaces to %zu bytes (32-byte boundary)\n", want);
  }
  prefix_a.resize(want, ' ');
  prefix_b.resize(want, ' ');

  // Total message length is prefix + one claw block + one bridge block.
  const size_t total = prefix_a.size() + 32;
  uint64_t SA[4] = {seed + total + 1, seed + total + 2, seed + total + 3,
                    seed + total + 5};
  uint64_t SB[4];
  memcpy(SB, SA, sizeof(SA));
  const bool inner_a = absorb(SA, (const uint8_t*)prefix_a.data(), prefix_a.size(), seed, false);
  const bool inner_b = absorb(SB, (const uint8_t*)prefix_b.data(), prefix_b.size(), seed, false);

  printf("chosen prefixes (%zu bytes each, total message %zu bytes)\n",
         prefix_a.size(), total);
  printf("  a: \"%s\"\n", prefix_a.c_str());
  printf("  b: \"%s\"\n", prefix_b.c_str());
  printf("state after prefix a: %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
         SA[0], SA[1], SA[2], SA[3]);
  printf("state after prefix b: %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
         SB[0], SB[1], SB[2], SB[3]);
  printf("  next block uses %s for both (required: mixA)\n",
         (!inner_a && !inner_b) ? "mixA" : "MISMATCHED MIXERS");
  printf("  pair sums a: %016" PRIx64 " %016" PRIx64 "\n", SA[0] + SA[1], SA[2] + SA[3]);
  printf("  pair sums b: %016" PRIx64 " %016" PRIx64 "  (differ: the claws fix this)\n\n",
         SB[0] + SB[1], SB[2] + SB[3]);
  if (inner_a || inner_b) return 1;

  // Claw 1 on the first pair: H_A(x) == H_B(x').
  const uint64_t a0 = SA[0], a1 = SA[1], b0 = SB[0], b1 = SB[1];
  auto Hfun = [&](uint64_t w) {
    const uint64_t s0 = flavor(w) ? b0 : a0;
    const uint64_t s1 = flavor(w) ? b1 : a1;
    uint64_t a = (s0 - w) * bowc::P; a = rotr64(a, 23); a *= bowc::Q;
    uint64_t b = (s1 + w) ^ a; b *= bowc::R; b = rotr64(b, 29); b *= bowc::S;
    return a + b;
  };
  auto cross = [](uint64_t w1, uint64_t w2) { return flavor(w1) != flavor(w2); };

  SearchStats stats_h;
  uint64_t w1 = 0, w2 = 0;
  printf("claw 1 (first pair, H)... ");
  fflush(stdout);
  if (!dp_collision(Hfun, cross, dp_bits, threads, rng_seed, w1, w2, stats_h)) {
    fprintf(stderr, "claw 1 failed\n"); return 1;
  }
  const uint64_t x_a = flavor(w1) ? w2 : w1;
  const uint64_t x_b = flavor(w1) ? w1 : w2;
  printf("found in %.2fs, %" PRIu64 " evaluations (2^%.2f)\n", stats_h.wall_seconds,
         stats_h.evaluations, log2((double)stats_h.evaluations));

  // Claw 2 on the second pair: K_A(y) == K_B(y').
  const uint64_t a2 = SA[2], a3 = SA[3], b2 = SB[2], b3 = SB[3];
  auto Kfun = [&](uint64_t w) {
    const uint64_t s2 = flavor(w) ? b2 : a2;
    const uint64_t s3 = flavor(w) ? b3 : a3;
    uint64_t c = (s2 + w) * bowc::T; c = rotr64(c, 31); c *= bowc::U;
    uint64_t d = ((s3 - w) ^ c) * bowc::V; d = rotr64(d, 37); d *= bowc::W;
    return c + d;
  };
  SearchStats stats_k;
  uint64_t v1 = 0, v2 = 0;
  printf("claw 2 (second pair, K)... ");
  fflush(stdout);
  if (!dp_collision(Kfun, cross, dp_bits, threads, rng_seed ^ 0x5A5A5A5A, v1, v2,
                    stats_k)) {
    fprintf(stderr, "claw 2 failed\n"); return 1;
  }
  const uint64_t y_a = flavor(v1) ? v2 : v1;
  const uint64_t y_b = flavor(v1) ? v1 : v2;
  printf("found in %.2fs, %" PRIu64 " evaluations (2^%.2f)\n", stats_k.wall_seconds,
         stats_k.evaluations, log2((double)stats_k.evaluations));

  // Bridge words drive both states to the same (H, 0, 0, K).
  const Pair fa = firstPair(SA[0] - x_a, SA[1] + x_a);
  const Pair fb = firstPair(SB[0] - x_b, SB[1] + x_b);
  const Pair sa = secondPair(SA[2] + y_a, SA[3] - y_a);
  const Pair sb = secondPair(SB[2] + y_b, SB[3] - y_b);
  printf("\n  H_a=%016" PRIx64 "  H_b=%016" PRIx64 "  equal=%s\n",
         fa.a + fa.b, fb.a + fb.b, (fa.a + fa.b) == (fb.a + fb.b) ? "yes" : "NO");
  printf("  K_a=%016" PRIx64 "  K_b=%016" PRIx64 "  equal=%s\n",
         sa.a + sa.b, sb.a + sb.b, (sa.a + sa.b) == (sb.a + sb.b) ? "yes" : "NO");

  std::vector<uint8_t> msg_a(prefix_a.begin(), prefix_a.end());
  std::vector<uint8_t> msg_b(prefix_b.begin(), prefix_b.end());
  msg_a.resize(total); msg_b.resize(total);
  uint8_t* ta = msg_a.data() + prefix_a.size();
  uint8_t* tb = msg_b.data() + prefix_b.size();
  put_u64_le(x_a, ta, 0); put_u64_le(y_a, ta, 8);
  put_u64_le((uint64_t)0 - fa.b, ta, 16); put_u64_le((uint64_t)0 - sa.a, ta, 24);
  put_u64_le(x_b, tb, 0); put_u64_le(y_b, tb, 8);
  put_u64_le((uint64_t)0 - fb.b, tb, 16); put_u64_le((uint64_t)0 - sb.a, tb, 24);

  // Show the merge explicitly.
  auto merged_state = [&](const std::vector<uint8_t>& m, uint64_t st[4]) {
    uint64_t h[4] = {seed + total + 1, seed + total + 2, seed + total + 3,
                     seed + total + 5};
    absorb(h, m.data(), m.size() - 16, seed, false);   // through the claw block
    const uint8_t* last = m.data() + m.size() - 16;
    const uint64_t p = get_u64_le(last, 0), q = get_u64_le(last, 8);
    h[0] -= p; h[1] += p; h[2] += q; h[3] -= q;        // bridge injection
    memcpy(st, h, sizeof(uint64_t) * 4);
  };
  uint64_t ma[4], mb[4];
  merged_state(msg_a, ma); merged_state(msg_b, mb);
  const bool merged = memcmp(ma, mb, sizeof(ma)) == 0;
  printf("\nstate after bridge injection\n");
  printf("  a: %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
         ma[0], ma[1], ma[2], ma[3]);
  printf("  b: %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
         mb[0], mb[1], mb[2], mb[3]);
  printf("  identical=%s\n", merged ? "yes" : "NO");

  uint8_t da[32], db[32];
  bool all_equal = true;
  printf("\nreference digests\n");
  for (uint32_t bits : {64u, 128u, 256u}) {
    rainbow_ref(msg_a.data(), msg_a.size(), seed, bits, da);
    rainbow_ref(msg_b.data(), msg_b.size(), seed, bits, db);
    const bool eq = memcmp(da, db, bits / 8) == 0;
    all_equal = all_equal && eq;
    printf("  %3u a=%s\n      b=%s  equal=%s\n", bits,
           hex_bytes(da, bits / 8).c_str(), hex_bytes(db, bits / 8).c_str(),
           eq ? "yes" : "NO");
  }

  printf("\nmessages\n  a = %s\n  b = %s\n",
         hex_bytes(msg_a.data(), msg_a.size()).c_str(),
         hex_bytes(msg_b.data(), msg_b.size()).c_str());

  const uint64_t total_evals = stats_h.evaluations + stats_k.evaluations;
  printf("\ntotal search: %" PRIu64 " evaluations (2^%.2f), %.2fs wall\n",
         total_evals, log2((double)total_evals),
         stats_h.wall_seconds + stats_k.wall_seconds);

  FILE* f = fopen(json_path, "w");
  if (f) {
    fprintf(f, "{\n  \"attack\": \"rainbow-chosen-prefix\",\n");
    fprintf(f, "  \"seed\": %" PRIu64 ",\n  \"message_length\": %zu,\n", seed, total);
    fprintf(f, "  \"prefix_a\": \"%s\",\n  \"prefix_b\": \"%s\",\n",
            prefix_a.c_str(), prefix_b.c_str());
    fprintf(f, "  \"message_a\": \"%s\",\n", hex_bytes(msg_a.data(), msg_a.size()).c_str());
    fprintf(f, "  \"message_b\": \"%s\",\n", hex_bytes(msg_b.data(), msg_b.size()).c_str());
    fprintf(f, "  \"state_merged\": %s,\n", merged ? "true" : "false");
    fprintf(f, "  \"digests_equal\": %s,\n", all_equal ? "true" : "false");
    fprintf(f, "  \"claw_h\": {\"evaluations\": %" PRIu64 ", \"walks\": %" PRIu64
               ", \"merges\": %" PRIu64 ", \"wall_seconds\": %.3f},\n",
            stats_h.evaluations, stats_h.walks, stats_h.merges, stats_h.wall_seconds);
    fprintf(f, "  \"claw_k\": {\"evaluations\": %" PRIu64 ", \"walks\": %" PRIu64
               ", \"merges\": %" PRIu64 ", \"wall_seconds\": %.3f},\n",
            stats_k.evaluations, stats_k.walks, stats_k.merges, stats_k.wall_seconds);
    fprintf(f, "  \"total_evaluations\": %" PRIu64 ",\n", total_evals);
    fprintf(f, "  \"log2_total_evaluations\": %.4f,\n", log2((double)total_evals));
    fprintf(f, "  \"distinguished_bits\": %u,\n  \"threads\": %u\n}\n", dp_bits, threads);
    fclose(f);
    printf("wrote %s\n", json_path);
  }
  return (merged && all_equal) ? 0 : 1;
}
