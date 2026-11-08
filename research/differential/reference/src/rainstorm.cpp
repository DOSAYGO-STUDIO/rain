#define __STORMVERSION__ "3.7.1"
// v2 is NIS2-v1 - non invertible state, v1 - passess all normal smhasher tests. BadSeeds not tested yet.
// includes a compress step on each ingest to make it harder to invert the state even given knowledge of it

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <algorithm>

// If you have platform-specific or hashing environment headers, include them here
// #include "Platform.h"
// #include "Hashlib.h"

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#define KEEPALIVE EMSCRIPTEN_KEEPALIVE
#else
#define KEEPALIVE
#endif

#include "common.h"

namespace rainstorm {
  // Frank's fixes: use static constexpr for these constants
  static constexpr int ROUNDS = 4;
  static constexpr int FINAL_ROUNDS = 2;

  // Primes and rotation amounts chosen for avalanche qualities
  static constexpr uint64_t P = UINT64_C(0xFFFFFFFFFFFFFFFF) - 58;
  static constexpr uint64_t Q = UINT64_C(13166748625691186689);
  static constexpr uint64_t R = UINT64_C(1573836600196043749);
  static constexpr uint64_t S = UINT64_C(1478582680485693857);
  static constexpr uint64_t T = UINT64_C(1584163446043636637);
  static constexpr uint64_t U = UINT64_C(1358537349836140151);
  static constexpr uint64_t V = UINT64_C(2849285319520710901);
  static constexpr uint64_t W = UINT64_C(2366157163652459183);

  static const uint64_t K[8] = { P, Q, R, S, T, U, V, W };
  static const uint64_t Z[8] = { 17, 19, 23, 29, 31, 37, 41, 53 };

  static constexpr uint64_t CTR_LEFT  = UINT64_C(0xefcdab8967452301);
  static constexpr uint64_t CTR_RIGHT = UINT64_C(0x1032547698badcfe);

  static inline void weakfunc(uint64_t* h, const uint64_t* data, bool left) {
    uint64_t ctr;
    if (left) {
      ctr = CTR_LEFT;
      for (int i = 0, j = 1, k = 8; i < 8; i++, j++, k++) {
        h[i] ^= data[i];            // ingest
        h[i] -= K[i];               
        h[i] = ROTR64(h[i], Z[i]);  // rotate

        h[k] ^= h[i];               // xor blit high 512

        ctr += h[i];                
        h[j] -= ctr;                
      }
    } else {
      ctr = CTR_RIGHT;
      for (int i = 8, j = 0, k = 1; i < 16; i++, j++, k++) {
        h[i] ^= data[j];            // ingest
        h[i] -= K[j];               
        h[i] = ROTR64(h[i], Z[j]);  // rotate

        h[j] ^= h[i];               // blit low 512

        ctr += h[i];                
        h[(k & 7) + 8] -= ctr;      
      }
    }
  }

  /*
  static inline void compress1( uint64_t * h, const uint64_t * start, const seed_t seed ) {
    for (int i = 0, j = 1; i < 15; i++, j++) {
        h[i] += h[j] - K[h[i]&7];
        h[j] = start[j] ^ seed;
    }
  }
  */

  // Streaming state. Semantically IDENTICAL to the single-call rainstorm()
  // below: initialize with the TOTAL input length (the state is length-keyed),
  // feed the bytes through update() in any chunking, then finalize().
  // Verified against the single-call path and the published vectors by
  // src/streaming-test.cpp (make test-streaming).
  //
  // History: this struct used to be dead code with two defects. Its h[2] init
  // constant duplicated h[1]'s (+2 twice, shifting the sequence to end at +43
  // where the single-call template ends at +47), and update() ran the
  // finalization tail on its first call, so a second update() was silently
  // ignored. Both fixed 2026-07-27; the single-call template — the path the
  // CLI, the WASM port, and SMHasher3 all use — is unchanged and remains the
  // definition of the hash.
  struct HashState : IHashState {
    uint64_t  h[16];
    uint64_t  temp[8];       // the final rounds mix over the last (padded) block
    seed_t    seed;
    size_t    olen;
    uint32_t  hashsize;
    uint8_t   pending[64];
    size_t    pending_len = 0;
    bool      finalized = false;

    static HashState initialize(const seed_t seed, size_t olen, uint32_t hashsize) {
      HashState state;
      static const uint64_t primes[16] = { 1, 2, 3, 5, 7, 11, 13, 17,
                                           19, 23, 29, 31, 37, 41, 43, 47 };
      for (int i = 0; i < 16; i++) {
        state.h[i] = seed + olen + primes[i];
      }
      state.len = 0;
      state.seed = seed;
      state.olen = olen;
      state.hashsize = hashsize;
      state.pending_len = 0;
      state.finalized = false;
      return state;
    }

    void ingest_block(const uint8_t* block) {
      for (int i = 0, j = 0; i < 8; ++i, j += 8) {
        temp[i] = GET_U64<false>(block, j);
      }
      for (int i = 0; i < ROUNDS; i++) {
        weakfunc(this->h, temp, i & 1);
      }
    }

    void update(const uint8_t* chunk, size_t chunk_len) {
      if (finalized) return;
      this->len += chunk_len;
      if (pending_len > 0) {
        size_t take = std::min((size_t)(64 - pending_len), chunk_len);
        memcpy(pending + pending_len, chunk, take);
        pending_len += take;
        chunk += take;
        chunk_len -= take;
        if (pending_len == 64) {
          ingest_block(pending);
          pending_len = 0;
        }
      }
      while (chunk_len >= 64) {
        ingest_block(chunk);
        chunk += 64;
        chunk_len -= 64;
      }
      if (chunk_len > 0) {
        memcpy(pending, chunk, chunk_len);
        pending_len = chunk_len;
      }
    }

    void finalize(void* out) {
      if (finalized) return;
      // the tail block: remainder bytes over a (0x80 + remainder)-filled pad,
      // exactly as the single-call path pads its final block
      memset(temp, (0x80 + pending_len) & 255, sizeof(temp));
      memcpy(temp, pending, pending_len);
      for (int i = 0; i < ROUNDS; i++) {
        weakfunc(h, temp, i & 1);
      }
      for (int i = 0, j = 8; i < 8; i++, j++) {
        h[i] -= h[j];
      }
      if (hashsize > 64) {
        for (int i = 0; i < std::max((int)hashsize / 64, FINAL_ROUNDS); i++) {
          weakfunc(h, temp, true);
        }
      }
      for (uint32_t i = 0, j = 0; i < std::min((uint32_t)8, hashsize / 64); i++, j += 8) {
        PUT_U64<false>(h[i], (uint8_t *)out, j);
      }
      finalized = true;
    }
  };

  template <uint32_t hashsize, bool bswap>
  static void rainstorm(const void* in, const size_t len, const seed_t seed, void* out) {
    const uint8_t * data = (const uint8_t *)in;
    uint64_t h[16] = {
      seed + len + 1,
      seed + len + 2,
      seed + len + 3,
      seed + len + 5,
      seed + len + 7,
      seed + len + 11,
      seed + len + 13,
      seed + len + 17,
      seed + len + 19,
      seed + len + 23,
      seed + len + 29,
      seed + len + 31,
      seed + len + 37,
      seed + len + 41,
      seed + len + 43,
      seed + len + 47
    };

    uint64_t temp[8];
    size_t lenRemaining = len;

    while (lenRemaining >= 64) {
      for (int i = 0, j = 0; i < 8; ++i, j += 8) {
        temp[i] = GET_U64<bswap>(data, j);
      }

      for (int i = 0; i < ROUNDS; i++) {
        weakfunc(h, temp, i & 1);
      }

      //compress1(h, start, seed);

      data += 64;
      lenRemaining -= 64;
    }

    memset(temp, (0x80 + lenRemaining) & 255, sizeof(temp));
    memcpy(temp, data, lenRemaining);
    // Frank's fix: remove the length encoding line that can cause issues
    // temp[lenRemaining >> 3] |= (uint64_t)(lenRemaining << ((lenRemaining&7)*8));

    //compress1(h, start, seed);

    for (int i = 0; i < ROUNDS; i++) {
      weakfunc(h, temp, i & 1);
    }

    for (int i = 0, j = 8; i < 8; i++, j++) {
      h[i] -= h[j];
    }

    if (hashsize > 64) {
      for (int i = 0; i < std::max((int)hashsize / 64, FINAL_ROUNDS); i++) {
        weakfunc(h, temp, true);
      }
    }

    for (uint32_t i = 0, j = 0; i < std::min((uint32_t)8, hashsize / 64); i++, j += 8) {
      PUT_U64<bswap>(h[i], (uint8_t *)out, j);
    }
  }
}
