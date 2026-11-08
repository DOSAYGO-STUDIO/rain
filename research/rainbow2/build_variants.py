#!/usr/bin/env python3
"""Generate auditable experimental Rainbow 2 ladder sources (r0..r5) from untouched src/rainbow.cpp."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VARIANTS_DIR = HERE / "variants"


def replace_exact(s: str, old: str, new: str, count: int) -> str:
    actual = s.count(old)
    if actual != count:
        raise RuntimeError(f"Source drift: expected {count} instances of {old!r}, found {actual}")
    return s.replace(old, new)


def generate():
    VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
    original = (ROOT / "src/rainbow.cpp").read_text()
    base = replace_exact(original, '#include "common.h"', '#include "../../../src/common.h"', 1)

    definitions = {
        "r0": "Baseline Rainbow v3.7.1 (unmodified control).",
        "r1": "Asymmetric block injection only: h[0]-=g0, h[1]+=ROTR64(g0,19), h[2]+=g1, h[3]-=ROTR64(g1,41). Breaks pair-sum coset invariant (W1).",
        "r2": "Feistel cross-coupled mixA only: adds a ^= d; c ^= b; at the end of mixA. Breaks pair-separability (W2) and cures dead-word h[0]'' in finalization (W3).",
        "r3": "Hardened core (R1 + R2): asymmetric injection + Feistel cross-coupled mixA.",
        "r4": "R3 + 4-lane lossless output squeeze: g = (h[0] ^ h[2]) - (h[1] ^ h[3]). Eliminates -sigma_2 output readout (W3, W4).",
        "r5": "R4 + nonlinear domain-separated seed/length/width initialization. Eliminates additive seed correlation and cross-width prefixing (W4, W5).",
        "r6": "Zero-latency cross-coupled core (R1 asymmetric injection + b^=c, d^=a, s=[b,c,d,a] in mixA + 4-lane squeeze). Fixes W1–W4 at zero extra mixA instructions.",
    }

    manifest_variants = {}

    for rung in ("r0", "r1", "r2", "r3", "r4", "r5", "r6"):
        s = replace_exact(base, "namespace rainbow {", f"namespace rainbow_{rung} {{", 1)

        # R1, R3, R4, R5, R6: Asymmetric block injection (both HashState::ingest_block and single-call rainbow)
        if rung in ("r1", "r3", "r4", "r5", "r6"):
            old_stream_inj = """      uint64_t g = GET_U64<false>(block, 0);
      h[0] -= g;
      h[1] += g;
      g = GET_U64<false>(block, 8);
      h[2] += g;
      h[3] -= g;"""
            new_stream_inj = """      uint64_t g = GET_U64<false>(block, 0);
      h[0] -= g;
      h[1] += ROTR64(g, 19);
      g = GET_U64<false>(block, 8);
      h[2] += g;
      h[3] -= ROTR64(g, 41);"""
            s = replace_exact(s, old_stream_inj, new_stream_inj, 1)

            old_single_inj = """      g = GET_U64<bswap>(data, 0);
      h[0] -= g;
      h[1] += g;
      data += 8;

      g = GET_U64<bswap>(data, 0);
      h[2] += g;
      h[3] -= g;"""
            new_single_inj = """      g = GET_U64<bswap>(data, 0);
      h[0] -= g;
      h[1] += ROTR64(g, 19);
      data += 8;

      g = GET_U64<bswap>(data, 0);
      h[2] += g;
      h[3] -= ROTR64(g, 41);"""
            s = replace_exact(s, old_single_inj, new_single_inj, 1)

        # R2, R3, R4, R5: Feistel cross-coupled mixA
        if rung in ("r2", "r3", "r4", "r5"):
            old_mixa_end = """    d *= V;
    d = ROTR64(d, 37);
    d *= W;

    s[0] = a; s[1] = b; s[2] = c; s[3] = d;"""
            new_mixa_end = """    d *= V;
    d = ROTR64(d, 37);
    d *= W;

    a ^= d;
    c ^= b;

    s[0] = a; s[1] = b; s[2] = c; s[3] = d;"""
            s = replace_exact(s, old_mixa_end, new_mixa_end, 1)

        # R6: Zero-instruction cross-XOR + 4-cycle register rename in mixA
        if rung == "r6":
            old_mixa_full = """    b ^= a;

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

    s[0] = a; s[1] = b; s[2] = c; s[3] = d;"""
            new_mixa_full = """    c *= T;
    c = ROTR64(c, 31);
    c *= U;

    b ^= c;
    d ^= a;

    b *= R;
    b = ROTR64(b, 29);
    b *= S;

    d *= V;
    d = ROTR64(d, 37);
    d *= W;

    s[0] = b; s[1] = c; s[2] = d; s[3] = a;"""
            s = replace_exact(s, old_mixa_full, new_mixa_full, 1)

        # R4, R5: 4-lane rotated output squeeze ROTR64(h[0] - h[1], 29) - h[2] - h[3]
        # (avoids bit-0 cancellation of b^d when combined with R2's post-multiply a^=d; c^=b;)
        if rung in ("r4", "r5"):
            s = replace_exact(
                s,
                """      uint64_t g = 0;
      g -= h[2];
      g -= h[3];""",
                """      uint64_t g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];""",
                1,
            )
            s = replace_exact(
                s,
                """    g = 0;
    g -= h[2];
    g -= h[3];""",
                """    g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];""",
                1,
            )
            s = replace_exact(
                s,
                """        g = 0;
        g -= h[3];
        g -= h[2];""",
                """        g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];""",
                4,
            )
            s = replace_exact(
                s,
                """      g = 0;
      g -= h[3];
      g -= h[2];""",
                """      g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];""",
                4,
            )

        # R6: 4-lane output squeeze (h[0] ^ h[2]) - (h[1] ^ h[3]) (safe with R6's pre-multiply mixA)
        if rung == "r6":
            s = replace_exact(
                s,
                """      uint64_t g = 0;
      g -= h[2];
      g -= h[3];""",
                """      uint64_t g = (h[0] ^ h[2]) - (h[1] ^ h[3]);""",
                1,
            )
            s = replace_exact(
                s,
                """    g = 0;
    g -= h[2];
    g -= h[3];""",
                """    g = (h[0] ^ h[2]) - (h[1] ^ h[3]);""",
                1,
            )
            s = replace_exact(
                s,
                """        g = 0;
        g -= h[3];
        g -= h[2];""",
                """        g = (h[0] ^ h[2]) - (h[1] ^ h[3]);""",
                4,
            )
            s = replace_exact(
                s,
                """      g = 0;
      g -= h[3];
      g -= h[2];""",
                """      g = (h[0] ^ h[2]) - (h[1] ^ h[3]);""",
                4,
            )

        # R5: Nonlinear domain-separated IV (seed, olen, hashsize) with pre-multiply rotation
        if rung == "r5":
            old_stream_iv = """      state.h[0] = seed + olen + 1;
      state.h[1] = seed + olen + 2;
      state.h[2] = seed + olen + 3;
      state.h[3] = seed + olen + 5;"""
            new_stream_iv = """      uint64_t dom = ((uint64_t)hashsize << 32) ^ (olen * P);
      state.h[0] = ROTR64(seed ^ dom, 17) * Q + 1;
      state.h[1] = (ROTR64(seed + olen, 29) * R) ^ (dom + 2);
      state.h[2] = ROTR64(seed ^ (olen * T), 41) * U + 3;
      state.h[3] = (ROTR64(seed + dom, 53) * V) ^ W;"""
            s = replace_exact(s, old_stream_iv, new_stream_iv, 1)

            old_single_iv = """    uint64_t h[4] = {
      seed + olen + 1,
      seed + olen + 2,
      seed + olen + 3,
      seed + olen + 5
    };"""
            new_single_iv = """    uint64_t dom = ((uint64_t)hashsize << 32) ^ (olen * P);
    uint64_t h[4] = {
      ROTR64(seed ^ dom, 17) * Q + 1,
      (ROTR64(seed + olen, 29) * R) ^ (dom + 2),
      ROTR64(seed ^ (olen * T), 41) * U + 3,
      (ROTR64(seed + dom, 53) * V) ^ W
    };"""
            s = replace_exact(s, old_single_iv, new_single_iv, 1)

        header = (
            f"// EXPERIMENTAL RAINBOW 2 LADDER VARIANT ({rung.upper()}).\n"
            "// Generated by research/rainbow2/build_variants.py from src/rainbow.cpp.\n"
        )
        out_path = VARIANTS_DIR / f"rainbow_{rung}.cpp"
        out_path.write_text(header + s)
        manifest_variants[rung] = {
            "file": str(out_path.relative_to(ROOT)),
            "sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
        }

    # Write bridge.cpp and sanitizer_test.cpp
    all_rungs = ("r0", "r1", "r2", "r3", "r4", "r5", "r6")
    bridge_lines = [
        f'#include "rainbow_{r}.cpp"' for r in all_rungs
    ] + [
        "",
        "#define EXPORT_VARIANT(rung, bits, swapped) \\",
        'extern "C" void rainbow2_##rung##_##bits##_##swapped(const void* p, size_t n, uint64_t seed, void* out) { \\',
        "  rainbow_##rung::rainbow<bits, swapped>(p, n, seed, out); \\",
        "}",
        "#define EXPORT_SIZE(rung, bits) EXPORT_VARIANT(rung, bits, 0) EXPORT_VARIANT(rung, bits, 1)",
        "#define EXPORT_ALL(rung) EXPORT_SIZE(rung, 64) EXPORT_SIZE(rung, 128) EXPORT_SIZE(rung, 256)",
    ]
    for r in all_rungs:
        bridge_lines.append(f"EXPORT_ALL({r})")
    bridge_lines += [
        "",
        "#define EXPORT_STREAM(rung) \\",
        'extern "C" void rainbow2_##rung##_stream(const uint8_t* p, size_t n, uint64_t seed, uint32_t bits, size_t chunk, void* out) { \\',
        "  auto s = rainbow_##rung::HashState::initialize(seed, n, bits); \\",
        "  for (size_t i = 0; i < n; i += chunk) s.update(p + i, std::min(chunk, n - i)); \\",
        "  s.finalize(out); \\",
        "}",
    ]
    for r in all_rungs:
        bridge_lines.append(f"EXPORT_STREAM({r})")

    (VARIANTS_DIR / "bridge.cpp").write_text("\n".join(bridge_lines) + "\n")

    san_lines = """#include "bridge.cpp"
#include <cstdio>
#include <cstring>
#include <vector>

using Hash = void (*)(const void*, size_t, uint64_t, void*);
using Stream = void (*)(const uint8_t*, size_t, uint64_t, uint32_t, size_t, void*);
struct Entry { const char* name; Hash hash; Stream stream; unsigned bits; };
#define ENTRY(rung, bits) {#rung "-" #bits, rainbow2_##rung##_##bits##_0, rainbow2_##rung##_stream, bits}
#define ENTRIES(rung) ENTRY(rung, 64), ENTRY(rung, 128), ENTRY(rung, 256)

int main() {
    Entry entries[] = {
        ENTRIES(r0), ENTRIES(r1), ENTRIES(r2), ENTRIES(r3), ENTRIES(r4), ENTRIES(r5), ENTRIES(r6)
    };
    size_t cases = 0;
    for (size_t len : {0, 1, 2, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129, 1000, 4096}) {
        std::vector<uint8_t> msg(len + 1);
        for (size_t i = 0; i < len; i++) msg[i] = static_cast<uint8_t>(i * 37 + 11);
        for (uint64_t seed : {UINT64_C(0), UINT64_C(1), UINT64_C(0x123456789ABCDEF0), UINT64_MAX}) {
            for (auto e : entries) {
                uint8_t a[32] = {}, b[32] = {};
                e.hash(msg.data(), len, seed, a);
                for (size_t chunk : {1, 2, 7, 15, 16, 17, 31, 32, 64, 129}) {
                    e.stream(msg.data(), len, seed, e.bits, chunk, b);
                    if (std::memcmp(a, b, e.bits / 8) != 0) {
                        std::fprintf(stderr, "MISMATCH: %s len=%zu seed=%llu chunk=%zu\\n",
                                     e.name, len, (unsigned long long)seed, chunk);
                        return 1;
                    }
                    ++cases;
                }
            }
        }
    }
    std::printf("ASan/UBSan: %zu Rainbow 2 ladder streaming comparisons passed.\\n", cases);
    return 0;
}
"""
    (VARIANTS_DIR / "sanitizer_test.cpp").write_text(san_lines)

    manifest = {
        "original_file": "src/rainbow.cpp",
        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "variants": manifest_variants,
        "definitions": definitions,
    }
    (VARIANTS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
