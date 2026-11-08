// streaming-test — proves HashState streaming equals the single-call
// templates, for both hashes, every size, many seeds/lengths/chunkings,
// and anchors rainbow-256/rainstorm-256 seed-0 against two published
// vectors so the test cannot drift along with the implementation.
//
// Build and run: make test-streaming

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "rainbow.cpp"
#include "rainbow2.cpp"
#include "rainstorm.cpp"

static int failures = 0;

static std::string hex(const uint8_t* d, size_t n) {
  static const char* x = "0123456789abcdef";
  std::string s;
  for (size_t i = 0; i < n; i++) { s += x[d[i] >> 4]; s += x[d[i] & 15]; }
  return s;
}

// deterministic filler so failures reproduce exactly
static void fill(std::vector<uint8_t>& v) {
  uint64_t x = 0x9e3779b97f4a7c15ULL;
  for (size_t i = 0; i < v.size(); i++) {
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    v[i] = (uint8_t)x;
  }
}

template <typename StateT, void SINGLE(const void*, size_t, seed_t, void*)>
static void check(const char* algo, uint32_t bits, seed_t seed,
                  const std::vector<uint8_t>& data, size_t chunk) {
  uint8_t want[64] = {0}, got[64] = {0};
  SINGLE(data.data(), data.size(), seed, want);

  StateT st = StateT::initialize(seed, data.size(), bits);
  size_t off = 0;
  while (off < data.size()) {
    size_t n = chunk < data.size() - off ? chunk : data.size() - off;
    st.update(data.data() + off, n);
    off += n;
  }
  if (data.empty()) st.update(data.data(), 0);
  st.finalize(got);

  if (memcmp(want, got, bits / 8) != 0) {
    failures++;
    printf("MISMATCH %s-%u seed=%llu len=%zu chunk=%zu\n  single: %s\n  stream: %s\n",
           algo, bits, (unsigned long long)seed, data.size(), chunk,
           hex(want, bits / 8).c_str(), hex(got, bits / 8).c_str());
  }
}

static void anchor(const char* algo, const char* input, const char* want_hex) {
  uint8_t out[32];
  std::string got;
  size_t len = strlen(input);
  if (strcmp(algo, "rainbow") == 0) {
    auto st = rainbow::HashState::initialize(0, len, 256);
    st.update((const uint8_t*)input, len);
    st.finalize(out);
  } else if (strcmp(algo, "rainbow2") == 0) {
    auto st = rainbow2::HashState::initialize(0, len, 256);
    st.update((const uint8_t*)input, len);
    st.finalize(out);
  } else {
    auto st = rainstorm::HashState::initialize(0, len, 256);
    st.update((const uint8_t*)input, len);
    st.finalize(out);
  }
  got = hex(out, 32);
  if (got != want_hex) {
    failures++;
    printf("VECTOR MISMATCH %s-256 \"%s\"\n  want %s\n  got  %s\n", algo, input, want_hex, got.c_str());
  }
}

// thin adapters so both templates fit one test harness
static void rb64(const void* p, size_t n, seed_t s, void* o)  { rainbow::rainbow<64, false>(p, n, s, o); }
static void rb128(const void* p, size_t n, seed_t s, void* o) { rainbow::rainbow<128, false>(p, n, s, o); }
static void rb256(const void* p, size_t n, seed_t s, void* o) { rainbow::rainbow<256, false>(p, n, s, o); }
static void rb2_64(const void* p, size_t n, seed_t s, void* o)  { rainbow2::rainbow2<64, false>(p, n, s, o); }
static void rb2_128(const void* p, size_t n, seed_t s, void* o) { rainbow2::rainbow2<128, false>(p, n, s, o); }
static void rb2_256(const void* p, size_t n, seed_t s, void* o) { rainbow2::rainbow2<256, false>(p, n, s, o); }
static void rs64(const void* p, size_t n, seed_t s, void* o)  { rainstorm::rainstorm<64, false>(p, n, s, o); }
static void rs128(const void* p, size_t n, seed_t s, void* o) { rainstorm::rainstorm<128, false>(p, n, s, o); }
static void rs256(const void* p, size_t n, seed_t s, void* o) { rainstorm::rainstorm<256, false>(p, n, s, o); }
static void rs512(const void* p, size_t n, seed_t s, void* o) { rainstorm::rainstorm<512, false>(p, n, s, o); }

int main() {
  // published vectors (verification/vectors.txt), through the STREAMING path
  anchor("rainbow",   "", "91fc76841e1431f6d58871e4c981fb37e3c0ac0f9f141c3e99b78f46c727c454");
  anchor("rainbow2",  "", "343286cc43eb2661e66f0226777cc0d64a820c89258990e6945db30ed44e4787");
  anchor("rainstorm", "", "bf6aa062a4c6ccf8b69697494100743f24da78e0e0140af278f3156772734b49");
  anchor("rainbow",   "The quick brown fox jumps over the lazy dog",
         "9c72cf9f50d0f3145ad0f45cf97c09afa6f7555562358dc15c4f4bb14cf2aa85");
  anchor("rainbow2",  "The quick brown fox jumps over the lazy dog",
         "fd3ffb7c54a739ab1365546ee03566bac46cf9a8276225a715675c3261620973");
  anchor("rainstorm", "The quick brown fox jumps over the lazy dog",
         "2343e4baabecf8be423ab643fcdfa113e14bf75e7a5f8a6a37f02a260282ac45");

  const size_t lengths[] = { 0, 1, 15, 16, 17, 43, 63, 64, 65, 127, 128, 129,
                             1000, 4096, 100000 };
  const seed_t  seeds[]  = { 0, 1, 42, 0xdeadbeefULL };
  const size_t  chunks[] = { 1, 7, 16, 63, 64, 65, 1000, (size_t)-1 };
  int cases = 0;

  for (size_t len : lengths) {
    std::vector<uint8_t> data(len);
    fill(data);
    for (seed_t seed : seeds) {
      for (size_t chunk : chunks) {
        size_t c = chunk == (size_t)-1 ? (len ? len : 1) : chunk;
        check<rainbow::HashState,   rb64 >("rainbow", 64,  seed, data, c);
        check<rainbow::HashState,   rb128>("rainbow", 128, seed, data, c);
        check<rainbow::HashState,   rb256>("rainbow", 256, seed, data, c);
        check<rainbow2::HashState,  rb2_64 >("rainbow2", 64,  seed, data, c);
        check<rainbow2::HashState,  rb2_128>("rainbow2", 128, seed, data, c);
        check<rainbow2::HashState,  rb2_256>("rainbow2", 256, seed, data, c);
        check<rainstorm::HashState, rs64 >("rainstorm", 64,  seed, data, c);
        check<rainstorm::HashState, rs128>("rainstorm", 128, seed, data, c);
        check<rainstorm::HashState, rs256>("rainstorm", 256, seed, data, c);
        check<rainstorm::HashState, rs512>("rainstorm", 512, seed, data, c);
        cases += 10;
      }
    }
  }

  if (failures) {
    printf("streaming-test: %d FAILURE(S) out of %d cases\n", failures, cases);
    return 1;
  }
  printf("streaming-test: all %d cases match the single-call templates (plus 4 published vectors)\n", cases);
  return 0;
}
