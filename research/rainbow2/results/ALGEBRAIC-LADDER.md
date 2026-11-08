# Rainbow 2 Hardening Ladder: Local Algebraic & Cryptanalytic Evaluation

- **Native vs. Independent Python Reference Comparisons:** `2352` passed (100%)
- **ASan/UBSan Streaming Comparisons:** `13,680` passed (100%)

## 1. SMHasher3 Verification Codes (`R0`–`R5`)

| Rung | 64-bit LE / BE | 128-bit LE / BE | 256-bit LE / BE |
| :--- | :--- | :--- | :--- |
| **R0** | `0xED7533D3` / `0xBE75A175` | `0xFF03173F` / `0xA8EAD0C3` | `0x65F4A210` / `0xD2AFD9EB` |
| **R1** | `0x095F02F9` / `0xF06D8289` | `0xFBDC549E` / `0x901EB93D` | `0x570AB08D` / `0x73B033BD` |
| **R2** | `0xE02D3EC1` / `0x7AF35F0B` | `0x5CF6A260` / `0x53978553` | `0xA5D67BE2` / `0xEED31FCB` |
| **R3** | `0xE2B79318` / `0x16929991` | `0xE09013C2` / `0xBF0BAB04` | `0xD32AAA3D` / `0x286FE0FC` |
| **R4** | `0x5FDFFF80` / `0xC8E39BE7` | `0x08A61AD1` / `0xA000D9D1` | `0xE8582941` / `0x27433C0D` |
| **R5** | `0x87C8CAEB` / `0xAACEA2C3` | `0xEA64F06C` / `0x700610B1` | `0xA13E40A5` / `0xF4329234` |
| **R6** | `0xF502226B` / `0x3097DADA` | `0x5002C45E` / `0x2FC29E44` | `0x24832643` / `0x4769CE02` |

## 2. Algebraic Weakness Elimination Matrix

| Metric | R0 (v3.7.1) | R1 (Inj) | R2 (Cross-mixA) | R3 (R1+R2) | R4 (R3+4Lane) | R5 (R4+IV) | R6 (R1+Swap) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Published Same-Seed Collision Collides?** | YES (BROKEN) | **NO** | **NO** | **NO** | **NO** | **NO** | **NO** |
| **Published Chosen-Prefix Collision Collides?** | YES (BROKEN) | **NO** | **NO** | **NO** | **NO** | **NO** | **NO** |
| **W1: Theorem 1 1-Block Merges (of 1000, $w=64$)** | 1000 | 0 | 1000 | 0 | 0 | 0 | 0 |
| **W1: $\sigma$-Agreeing Merges (of 300, $w=4$ exhaustive)** | 300 | 21 | 300 | 21 | 21 | 21 | 21 |
| **W1: Distinct $(\sigma_1,\sigma_2)$ Reached in 1 Block ($w=4$, max 256)** | 1 | 105 | 1 | 105 | 105 | 105 | 105 |
| **W2: `mixA` Exact Bijection ($w=4$ 65536 & $w=64$ 1000)** | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **W2: Cross-Pair Avalanche (1 `mixA` P0$\to$P1 / P1$\to$P0)** | 0.000 / 0.000 | 0.000 / 0.000 | 0.217 / 0.241 | 0.217 / 0.241 | 0.217 / 0.241 | 0.217 / 0.241 | 0.197 / 0.233 |
| **W2: Cross-Pair Avalanche (2 `mixA` P0$\to$P1 / P1$\to$P0)** | 0.000 / 0.000 | 0.000 / 0.000 | 0.500 / 0.500 | 0.500 / 0.500 | 0.500 / 0.500 | 0.500 / 0.500 | 0.368 / 0.375 |
| **W3 (Q20): $w=4$ Finalization Image Size (of 65,536)** | 4007 (0.061) | 4007 (0.061) | 41766 (0.637) | 41766 (0.637) | 41616 (0.635) | 41616 (0.635) | 41395 (0.632) |
| **W3 (Q20): $w=64$ Dead-Word `h[0]''` Affects Words 2,3 (of 2000)** | 0 | 0 | 2000 | 2000 | 2000 | 2000 | 2000 |
| **W3 (Q20): $w=64$ `(h0,h1)` Affects 128-bit Squeeze (of 2000)** | 0 | 0 | 2000 | 2000 | 2000 | 2000 | 2000 |
| **W4: Cross-Width Prefixing (64 in 128 / 128 in 256, of 200)** | 200 / 200 | 200 / 200 | 200 / 200 | 200 / 200 | 200 / 200 | 0 / 0 | 200 / 200 |
| **W5 (Q22): Top-Bit Seed Flip IV Hamming Weight (of 256 bits)** | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 76.7 | 4.0 |
