// Rainbow 2 experimental hardening ladder registrations (R0..R5).
// Derived hash source: Apache-2.0.
#include "Platform.h"
#include "Hashlib.h"

REGISTER_FAMILY(rainbow2, $.src_url = "https://github.com/DOSAYGO-STUDIO/rain", $.src_status = HashFamilyInfo::SRC_STABLEISH);

extern "C" void rainbow2_r0_64_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r0_64_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r0_64,
  $.desc = "Rainbow2 ladder R0 (64-bit): Baseline Rainbow v3.7.1 (unmodified control).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 64,
  $.verification_LE = 0xED7533D3,
  $.verification_BE = 0xBE75A175,
  $.hashfn_native = rainbow2_r0_64_0,
  $.hashfn_bswap = rainbow2_r0_64_1
);

extern "C" void rainbow2_r0_128_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r0_128_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r0_128,
  $.desc = "Rainbow2 ladder R0 (128-bit): Baseline Rainbow v3.7.1 (unmodified control).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 128,
  $.verification_LE = 0xFF03173F,
  $.verification_BE = 0xA8EAD0C3,
  $.hashfn_native = rainbow2_r0_128_0,
  $.hashfn_bswap = rainbow2_r0_128_1
);

extern "C" void rainbow2_r0_256_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r0_256_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r0_256,
  $.desc = "Rainbow2 ladder R0 (256-bit): Baseline Rainbow v3.7.1 (unmodified control).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 256,
  $.verification_LE = 0x65F4A210,
  $.verification_BE = 0xD2AFD9EB,
  $.hashfn_native = rainbow2_r0_256_0,
  $.hashfn_bswap = rainbow2_r0_256_1
);

extern "C" void rainbow2_r1_64_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r1_64_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r1_64,
  $.desc = "Rainbow2 ladder R1 (64-bit): Asymmetric block injection only: h[0]-=g0, h[1]+=ROTR64(g0,19), h[2]+=g1, h[3]-=ROTR64(g1,41). Breaks pair-sum coset invariant (W1).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 64,
  $.verification_LE = 0x095F02F9,
  $.verification_BE = 0xF06D8289,
  $.hashfn_native = rainbow2_r1_64_0,
  $.hashfn_bswap = rainbow2_r1_64_1
);

extern "C" void rainbow2_r1_128_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r1_128_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r1_128,
  $.desc = "Rainbow2 ladder R1 (128-bit): Asymmetric block injection only: h[0]-=g0, h[1]+=ROTR64(g0,19), h[2]+=g1, h[3]-=ROTR64(g1,41). Breaks pair-sum coset invariant (W1).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 128,
  $.verification_LE = 0xFBDC549E,
  $.verification_BE = 0x901EB93D,
  $.hashfn_native = rainbow2_r1_128_0,
  $.hashfn_bswap = rainbow2_r1_128_1
);

extern "C" void rainbow2_r1_256_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r1_256_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r1_256,
  $.desc = "Rainbow2 ladder R1 (256-bit): Asymmetric block injection only: h[0]-=g0, h[1]+=ROTR64(g0,19), h[2]+=g1, h[3]-=ROTR64(g1,41). Breaks pair-sum coset invariant (W1).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 256,
  $.verification_LE = 0x570AB08D,
  $.verification_BE = 0x73B033BD,
  $.hashfn_native = rainbow2_r1_256_0,
  $.hashfn_bswap = rainbow2_r1_256_1
);

extern "C" void rainbow2_r2_64_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r2_64_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r2_64,
  $.desc = "Rainbow2 ladder R2 (64-bit): Feistel cross-coupled mixA only: adds a ^= d; c ^= b; at the end of mixA. Breaks pair-separability (W2) and cures dead-word h[0]'' in finalization (W3).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 64,
  $.verification_LE = 0xE02D3EC1,
  $.verification_BE = 0x7AF35F0B,
  $.hashfn_native = rainbow2_r2_64_0,
  $.hashfn_bswap = rainbow2_r2_64_1
);

extern "C" void rainbow2_r2_128_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r2_128_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r2_128,
  $.desc = "Rainbow2 ladder R2 (128-bit): Feistel cross-coupled mixA only: adds a ^= d; c ^= b; at the end of mixA. Breaks pair-separability (W2) and cures dead-word h[0]'' in finalization (W3).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 128,
  $.verification_LE = 0x5CF6A260,
  $.verification_BE = 0x53978553,
  $.hashfn_native = rainbow2_r2_128_0,
  $.hashfn_bswap = rainbow2_r2_128_1
);

extern "C" void rainbow2_r2_256_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r2_256_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r2_256,
  $.desc = "Rainbow2 ladder R2 (256-bit): Feistel cross-coupled mixA only: adds a ^= d; c ^= b; at the end of mixA. Breaks pair-separability (W2) and cures dead-word h[0]'' in finalization (W3).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 256,
  $.verification_LE = 0xA5D67BE2,
  $.verification_BE = 0xEED31FCB,
  $.hashfn_native = rainbow2_r2_256_0,
  $.hashfn_bswap = rainbow2_r2_256_1
);

extern "C" void rainbow2_r3_64_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r3_64_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r3_64,
  $.desc = "Rainbow2 ladder R3 (64-bit): Hardened core (R1 + R2): asymmetric injection + Feistel cross-coupled mixA.",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 64,
  $.verification_LE = 0xE2B79318,
  $.verification_BE = 0x16929991,
  $.hashfn_native = rainbow2_r3_64_0,
  $.hashfn_bswap = rainbow2_r3_64_1
);

extern "C" void rainbow2_r3_128_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r3_128_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r3_128,
  $.desc = "Rainbow2 ladder R3 (128-bit): Hardened core (R1 + R2): asymmetric injection + Feistel cross-coupled mixA.",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 128,
  $.verification_LE = 0xE09013C2,
  $.verification_BE = 0xBF0BAB04,
  $.hashfn_native = rainbow2_r3_128_0,
  $.hashfn_bswap = rainbow2_r3_128_1
);

extern "C" void rainbow2_r3_256_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r3_256_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r3_256,
  $.desc = "Rainbow2 ladder R3 (256-bit): Hardened core (R1 + R2): asymmetric injection + Feistel cross-coupled mixA.",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 256,
  $.verification_LE = 0xD32AAA3D,
  $.verification_BE = 0x286FE0FC,
  $.hashfn_native = rainbow2_r3_256_0,
  $.hashfn_bswap = rainbow2_r3_256_1
);

extern "C" void rainbow2_r4_64_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r4_64_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r4_64,
  $.desc = "Rainbow2 ladder R4 (64-bit): R3 + 4-lane lossless output squeeze: g = (h[0] ^ h[2]) - (h[1] ^ h[3]). Eliminates -sigma_2 output readout (W3, W4).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 64,
  $.verification_LE = 0xCA69A2EB,
  $.verification_BE = 0x53B01BFC,
  $.hashfn_native = rainbow2_r4_64_0,
  $.hashfn_bswap = rainbow2_r4_64_1
);

extern "C" void rainbow2_r4_128_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r4_128_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r4_128,
  $.desc = "Rainbow2 ladder R4 (128-bit): R3 + 4-lane lossless output squeeze: g = (h[0] ^ h[2]) - (h[1] ^ h[3]). Eliminates -sigma_2 output readout (W3, W4).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 128,
  $.verification_LE = 0x8CD2FC6F,
  $.verification_BE = 0x277E7452,
  $.hashfn_native = rainbow2_r4_128_0,
  $.hashfn_bswap = rainbow2_r4_128_1
);

extern "C" void rainbow2_r4_256_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r4_256_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r4_256,
  $.desc = "Rainbow2 ladder R4 (256-bit): R3 + 4-lane lossless output squeeze: g = (h[0] ^ h[2]) - (h[1] ^ h[3]). Eliminates -sigma_2 output readout (W3, W4).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 256,
  $.verification_LE = 0x21A65AE5,
  $.verification_BE = 0x78B9760A,
  $.hashfn_native = rainbow2_r4_256_0,
  $.hashfn_bswap = rainbow2_r4_256_1
);

extern "C" void rainbow2_r5_64_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r5_64_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r5_64,
  $.desc = "Rainbow2 ladder R5 (64-bit): R4 + nonlinear domain-separated seed/length/width initialization. Eliminates additive seed correlation and cross-width prefixing (W4, W5).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 64,
  $.verification_LE = 0xB6EB54B1,
  $.verification_BE = 0xD229A9F4,
  $.hashfn_native = rainbow2_r5_64_0,
  $.hashfn_bswap = rainbow2_r5_64_1
);

extern "C" void rainbow2_r5_128_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r5_128_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r5_128,
  $.desc = "Rainbow2 ladder R5 (128-bit): R4 + nonlinear domain-separated seed/length/width initialization. Eliminates additive seed correlation and cross-width prefixing (W4, W5).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 128,
  $.verification_LE = 0xBA2E84CC,
  $.verification_BE = 0x10A85C4D,
  $.hashfn_native = rainbow2_r5_128_0,
  $.hashfn_bswap = rainbow2_r5_128_1
);

extern "C" void rainbow2_r5_256_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r5_256_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r5_256,
  $.desc = "Rainbow2 ladder R5 (256-bit): R4 + nonlinear domain-separated seed/length/width initialization. Eliminates additive seed correlation and cross-width prefixing (W4, W5).",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 256,
  $.verification_LE = 0x4F7D97BE,
  $.verification_BE = 0x5EF63848,
  $.hashfn_native = rainbow2_r5_256_0,
  $.hashfn_bswap = rainbow2_r5_256_1
);

extern "C" void rainbow2_r6_64_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r6_64_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r6_64,
  $.desc = "Rainbow2 ladder R6 (64-bit): Zero-latency cross-coupled core (R1 asymmetric injection + b^=c, d^=a, s=[b,c,d,a] in mixA + 4-lane squeeze). Fixes W1–W4 at zero extra mixA instructions.",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 64,
  $.verification_LE = 0xF502226B,
  $.verification_BE = 0x3097DADA,
  $.hashfn_native = rainbow2_r6_64_0,
  $.hashfn_bswap = rainbow2_r6_64_1
);

extern "C" void rainbow2_r6_128_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r6_128_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r6_128,
  $.desc = "Rainbow2 ladder R6 (128-bit): Zero-latency cross-coupled core (R1 asymmetric injection + b^=c, d^=a, s=[b,c,d,a] in mixA + 4-lane squeeze). Fixes W1–W4 at zero extra mixA instructions.",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 128,
  $.verification_LE = 0x5002C45E,
  $.verification_BE = 0x2FC29E44,
  $.hashfn_native = rainbow2_r6_128_0,
  $.hashfn_bswap = rainbow2_r6_128_1
);

extern "C" void rainbow2_r6_256_0(const void*, size_t, uint64_t, void*);
extern "C" void rainbow2_r6_256_1(const void*, size_t, uint64_t, void*);
REGISTER_HASH(rainbow2_r6_256,
  $.desc = "Rainbow2 ladder R6 (256-bit): Zero-latency cross-coupled core (R1 asymmetric injection + b^=c, d^=a, s=[b,c,d,a] in mixA + 4-lane squeeze). Fixes W1–W4 at zero extra mixA instructions.",
  $.impl_flags = FLAG_IMPL_MULTIPLY_64_64 | FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
  $.bits = 256,
  $.verification_LE = 0x24832643,
  $.verification_BE = 0x4769CE02,
  $.hashfn_native = rainbow2_r6_256_0,
  $.hashfn_bswap = rainbow2_r6_256_1
);

