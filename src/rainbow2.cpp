#define __RAINBOW2VERSION__ "2.0.0"
// Rainbow 2 (R5): Hardened 64/128/256-bit fast hash family derived from the
// algebraic cryptanalysis of Rainbow v3.7.1 and empirical SMHasher3 evaluation
// across a 7-rung hardening ladder (R0..R6).
//
// Structural upgrades over Rainbow v3.7.1 (R0):
// 1. Asymmetric rotated block injection (R1): replaces the rank-2 pair-sum load
//    (h0 -= x, h1 += x, h2 += y, h3 -= y) with full-rank rotated injection
//    (h0 -= x, h1 += ROTR64(x,19), h2 += y, h3 -= ROTR64(y,41)), eliminating
//    Theorem 1's pair-sum invariant and 1-block state merges (0/1,000) and
//    collapsing 2-adic DDT rays from 145.3x to 3.67x.
// 2. Feistel cross-coupled mixA (R2): appends two reversible cross-half XORs
//    (a ^= d; c ^= b;) at the end of mixA, breaking the (h0,h1)|(h2,h3)
//    half-independence, raising 2-round cross-pair avalanche from 0.000 to
//    0.500, and activating all 4 words in finalization.
// 3. Rotated 4-lane output squeeze (R4): replaces the 2-lane readout
//    g = 0 - h[2] - h[3] with g = ROTR64(h[0] - h[1], 29) - h[2] - h[3],
//    avoiding the bit-0 parity cancellation of unrotated XOR-subtract squeezes
//    (Proposition 3) and ensuring every output word directly combines all four
//    64-bit state lanes.
// 4. Domain-separated rotated-multiply IV (R5): replaces the linear additive IV
//    (seed + olen + {1,2,3,5}) with a domain-separated rotated-multiply IV
//    binding seed, olen, and hashsize, eliminating cross-width output prefixing
//    (0/200) and top-bit seed IV linearity (76.7-bit initial Hamming distance
//    on delta_seed = 2^63).
//
// Full paper: output/pdf/rainbow-pair-sum-cryptanalysis.pdf
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <algorithm>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#define KEEPALIVE EMSCRIPTEN_KEEPALIVE
#else
#define KEEPALIVE
#endif

#include "common.h"

namespace rainbow2 {
  static const uint64_t P = UINT64_C(0xFFFFFFFFFFFFFFFF) - 58;
  static const uint64_t Q = UINT64_C(13166748625691186689);
  static const uint64_t R = UINT64_C(1573836600196043749);
  static const uint64_t S = UINT64_C(1478582680485693857);
  static const uint64_t T = UINT64_C(1584163446043636637);
  static const uint64_t U = UINT64_C(1358537349836140151);
  static const uint64_t V = UINT64_C(2849285319520710901);
  static const uint64_t W = UINT64_C(2366157163652459183);

  static inline void rotate_right(uint64_t h[4]) {
    uint64_t temp = h[3];  // Store the last element
    h[3] = h[2];           // Shift elements right
    h[2] = h[1];
    h[1] = h[0];
    h[0] = temp;           // Place the last element in the first position
  }

  static inline void mixA(uint64_t* s) {
    uint64_t a = s[0], b = s[1], c = s[2], d = s[3];

    a *= P;
    a = ROTR64(a, 23);
    a *= Q;

    b ^= a;

    b *= R;
    b = ROTR64(b, 29);
    b *= S;

    c *= T;
    c = ROTR64(c, 31);
    c *= U;

    d ^= c;

    d *= V;
    d = ROTR64(d, 37);
    d *= W;

    a ^= d;
    c ^= b;

    s[0] = a; s[1] = b; s[2] = c; s[3] = d;
  }

  static inline void mixB(uint64_t* s, uint64_t iv) {
    uint64_t a = s[1], b = s[2];

    a *= V;
    a = ROTR64(a, 23);
    a *= W;

    b ^= a + iv;

    b *= R;
    b = ROTR64(b, 23);
    b *= S;

    s[1] = b; s[2] = a;
  }

  // Streaming state. Semantically IDENTICAL to the single-call rainbow2()
  // below: initialize with the TOTAL input length (the state is length-keyed
  // and width-domain-separated), feed the bytes through update() in any
  // chunking, then finalize().
  struct HashState : IHashState {
    uint64_t  h[4];
    seed_t    seed;
    uint32_t  hashsize;
    bool      inner = false;
    uint8_t   pending[16];
    size_t    pending_len = 0;
    bool      finalized = false;

    static HashState initialize(const seed_t seed, size_t olen, uint32_t hashsize) {
      HashState state;
      uint64_t dom = ((uint64_t)hashsize << 32) ^ (olen * P);
      state.h[0] = ROTR64(seed ^ dom, 17) * Q + 1;
      state.h[1] = (ROTR64(seed + olen, 29) * R) ^ (dom + 2);
      state.h[2] = ROTR64(seed ^ (olen * T), 41) * U + 3;
      state.h[3] = (ROTR64(seed + dom, 53) * V) ^ W;
      state.len = 0;
      state.seed = seed;
      state.hashsize = hashsize;
      state.inner = false;
      state.pending_len = 0;
      state.finalized = false;
      return state;
    }

    void ingest_block(const uint8_t* block) {
      uint64_t g = GET_U64<false>(block, 0);
      h[0] -= g;
      h[1] += ROTR64(g, 19);
      g = GET_U64<false>(block, 8);
      h[2] += g;
      h[3] -= ROTR64(g, 41);
      if (inner) {
        mixB(h, seed);
        rotate_right(h);
      } else {
        mixA(h);
      }
      inner = !inner;
    }

    void update(const uint8_t* chunk, size_t chunk_len) {
      if (finalized) return;
      this->len += chunk_len;
      if (pending_len > 0) {
        size_t take = std::min((size_t)(16 - pending_len), chunk_len);
        memcpy(pending + pending_len, chunk, take);
        pending_len += take;
        chunk += take;
        chunk_len -= take;
        if (pending_len == 16) {
          ingest_block(pending);
          pending_len = 0;
        }
      }
      while (chunk_len >= 16) {
        ingest_block(chunk);
        chunk += 16;
        chunk_len -= 16;
      }
      if (chunk_len > 0) {
        memcpy(pending, chunk, chunk_len);
        pending_len = chunk_len;
      }
    }

    void finalize(void* out) {
      if (finalized) return;
      mixB(h, seed);
      switch (pending_len) {
        case 15: h[0] += (uint64_t)pending[14] << 56; // [[fallthrough]]
        case 14: h[1] += (uint64_t)pending[13] << 48; // [[fallthrough]]
        case 13: h[2] += (uint64_t)pending[12] << 40; // [[fallthrough]]
        case 12: h[3] += (uint64_t)pending[11] << 32; // [[fallthrough]]
        case 11: h[0] += (uint64_t)pending[10] << 24; // [[fallthrough]]
        case 10: h[1] += (uint64_t)pending[9]  << 16; // [[fallthrough]]
        case  9: h[2] += (uint64_t)pending[8]  << 8;  // [[fallthrough]]
        case  8: h[3] += pending[7];                  // [[fallthrough]]
        case  7: h[0] += (uint64_t)pending[6]  << 48; // [[fallthrough]]
        case  6: h[1] += (uint64_t)pending[5]  << 40; // [[fallthrough]]
        case  5: h[2] += (uint64_t)pending[4]  << 32; // [[fallthrough]]
        case  4: h[3] += (uint64_t)pending[3]  << 24; // [[fallthrough]]
        case  3: h[0] += (uint64_t)pending[2]  << 16; // [[fallthrough]]
        case  2: h[1] += (uint64_t)pending[1]  <<  8; // [[fallthrough]]
        case  1: h[2] += pending[0];
      }
      mixA(h);
      mixB(h, seed);
      mixA(h);

      uint64_t g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
      PUT_U64<false>(g, (uint8_t *)out, 0);

      if (hashsize == 128) {
        mixA(h);
        g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
        PUT_U64<false>(g, (uint8_t *)out, 8);
      } else if (hashsize == 256) {
        mixA(h);
        g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
        PUT_U64<false>(g, (uint8_t *)out, 8);
        mixA(h);
        mixB(h, seed);
        mixA(h);
        g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
        PUT_U64<false>(g, (uint8_t *)out, 16);
        mixA(h);
        g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
        PUT_U64<false>(g, (uint8_t *)out, 24);
      }

      finalized = true;
    }
  };

  // Single-call version with no streaming needed
  template <uint32_t hashsize, bool bswap>
  static void rainbow2(const void* in, const size_t olen, const seed_t seed, void* out) {
    const uint8_t * data = (const uint8_t *)in;
    uint64_t dom = ((uint64_t)hashsize << 32) ^ (olen * P);
    uint64_t h[4] = {
      ROTR64(seed ^ dom, 17) * Q + 1,
      (ROTR64(seed + olen, 29) * R) ^ (dom + 2),
      ROTR64(seed ^ (olen * T), 41) * U + 3,
      (ROTR64(seed + dom, 53) * V) ^ W
    };
    size_t len = olen;
    uint64_t g = 0;
    bool inner = false;

    while (len >= 16) {
      g = GET_U64<bswap>(data, 0);
      h[0] -= g;
      h[1] += ROTR64(g, 19);
      data += 8;

      g = GET_U64<bswap>(data, 0);
      h[2] += g;
      h[3] -= ROTR64(g, 41);

      if (inner) {
        mixB(h, seed);
        rotate_right(h);
      } else {
        mixA(h);
      }
      inner = !inner;

      data += 8;
      len  -= 16;
    }

    // After main loop
    mixB(h, seed);

    switch (len) {
      case 15: h[0] += (uint64_t)data[14] << 56; // [[fallthrough]];
      case 14: h[1] += (uint64_t)data[13] << 48; // [[fallthrough]]
      case 13: h[2] += (uint64_t)data[12] << 40; // [[fallthrough]]
      case 12: h[3] += (uint64_t)data[11] << 32; // [[fallthrough]]
      case 11: h[0] += (uint64_t)data[10] << 24; // [[fallthrough]]
      case 10: h[1] += (uint64_t)data[9]  << 16; // [[fallthrough]]
      case  9: h[2] += (uint64_t)data[8]  << 8;  // [[fallthrough]]
      case  8: h[3] += data[7];                  // [[fallthrough]]
      case  7: h[0] += (uint64_t)data[6]  << 48; // [[fallthrough]]
      case  6: h[1] += (uint64_t)data[5]  << 40; // [[fallthrough]]
      case  5: h[2] += (uint64_t)data[4]  << 32; // [[fallthrough]]
      case  4: h[3] += (uint64_t)data[3]  << 24; // [[fallthrough]]
      case  3: h[0] += (uint64_t)data[2]  << 16; // [[fallthrough]]
      case  2: h[1] += (uint64_t)data[1]  <<  8; // [[fallthrough]]
      case  1: h[2] += (uint64_t)data[0];
    }

    mixA(h);
    mixB(h, seed);
    mixA(h);

    g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
    PUT_U64<bswap>(g, (uint8_t *)out, 0);

    if (hashsize == 128) {
      mixA(h);
      g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
      PUT_U64<bswap>(g, (uint8_t *)out, 8);
    } else if (hashsize == 256) {
      mixA(h);
      g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
      PUT_U64<bswap>(g, (uint8_t *)out, 8);
      mixA(h);
      mixB(h, seed);
      mixA(h);
      g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
      PUT_U64<bswap>(g, (uint8_t *)out, 16);
      mixA(h);
      g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
      PUT_U64<bswap>(g, (uint8_t *)out, 24);
    }
  }

  template <uint32_t hashsize, bool bswap>
  static inline void rainbow(const void* in, const size_t olen, const seed_t seed, void* out) {
    rainbow2<hashsize, bswap>(in, olen, seed, out);
  }
}
