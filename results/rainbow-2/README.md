# Rainbow 2 (`R5`) Validation & Hardening Report

**Rainbow 2** ([`src/rainbow2.cpp`](../../src/rainbow2.cpp), `rainsum -a rainbow2`) is a hardened 64/128/256-bit fast non-cryptographic hash family derived from the structural cryptanalysis of Rainbow v3.7.1 (`R0`, [`src/rainbow.cpp`](../../src/rainbow.cpp)) and evaluated across a 7-rung hardening ladder (`R0`–`R6`) through algebraic spectrum verification and empirical SMHasher3 testing on 32-vCPU AMD EPYC Milan (`c2d-highcpu-32`).

- **Cryptanalysis & Design Paper (10 pages):** [`output/pdf/rainbow-pair-sum-cryptanalysis.pdf`](../../output/pdf/rainbow-pair-sum-cryptanalysis.pdf) ([LaTeX source](../../output/pdf/rainbow-pair-sum-cryptanalysis.tex) | [5x2 JPEG Contact Sheet](../../output/pdf/rainbow-pair-sum-cryptanalysis-contact-sheet.jpg) | [X Card 1](../../output/pdf/rainbow-pair-sum-cryptanalysis-x-sheet-1.jpg) | [X Card 2](../../output/pdf/rainbow-pair-sum-cryptanalysis-x-sheet-2.jpg))
- **Algebraic & Empirical Ladder Report:** [`research/rainbow2/results/ALGEBRAIC-LADDER.md`](../../research/rainbow2/results/ALGEBRAIC-LADDER.md)
- **Raw SMHasher3 Campaign Transcripts (`R0`–`R6`):** [`research/rainbow2/results/smhasher3-campaign/results/`](../../research/rainbow2/results/smhasher3-campaign/results)

---

## 1. Summary of Structural Upgrades (`R0` $\rightarrow$ `R5`)

Rainbow 2 (`R5`) applies four surgical modifications to Rainbow v3.7.1 (`R0`) that eliminate all five structural weakness classes (`W1`, `W1b`, `W2`, `W3`, `W4`, `W5`) identified in the cryptanalysis paper:

1. **Asymmetric Rotated Block Injection (`R1` — fixes `W1` and `W1b`):**
   Replaces the rank-2 symmetric block load (`h[0] -= x; h[1] += x; h[2] += y; h[3] -= y;`) with:
   ```cpp
   h[0] -= x;
   h[1] += ROTR64(x, 19);
   h[2] += y;
   h[3] -= ROTR64(y, 41);
   ```
   Because $x \mapsto (-x, +\mathrm{ROTR}_{19}(x))$ is a full-rank bijection on non-constant bits, Theorem 1's pair-sum invariant ($\sigma_1 = h_0 + h_1, \sigma_2 = h_2 + h_3$) is destroyed (`0 / 1,000` 1-block state merges vs. `1,000 / 1,000` in `R0`), and the 2-adic differential distribution table (DDT) rays collapse from $M_r = 11.01\times$ ($S_r = 145.29\times$) to $M_r = 3.67\times$ ($S_r = 1.98\times$).

2. **Feistel Cross-Coupled `mixA` (`R2` — fixes `W2` and `W3`):**
   Appends two reversible cross-half XORs at the end of `mixA`:
   ```cpp
   a ^= d;
   c ^= b;
   ```
   This preserves exact bijectivity of `mixA` while coupling $(h_0, h_1)$ and $(h_2, h_3)$ on every call, raising 2-round cross-pair avalanche from `0.000` to `0.500`, activating dead word $h_0''$ in finalization (`2,000 / 2,000` trials vs. `0 / 2,000` in `R0`), and expanding the $w=4$ finalizer image from `6.11%` (`4,007 / 65,536`) to `63.23%` (`41,439 / 65,536`, matching the random-map birthday occupancy $1 - e^{-1} \approx 63.21\%$).

3. **Rotated 4-Lane Output Squeeze (`R4` — Proposition 3):**
   Replaces the 2-lane readout `g = 0 - h[2] - h[3]` with the rotated 4-lane subtract squeeze:
   ```cpp
   g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];
   ```
   As proved in **Proposition 3** of the paper (discovered during our iterative Algebra $\leftrightarrow$ SMHasher3 loop), an unrotated XOR-subtract squeeze `g_unrot = (h[0] ^ h[2]) - (h[1] ^ h[3])` after `a ^= d; c ^= b;` simplifies to $((a \oplus c) \oplus (b \oplus d)) - (b \oplus d) \pmod{2^{64}}$, whose least significant bit cancels $b_0 \oplus d_0$ identically modulo 2 and produces a 27.6%–27.7% `Avalanche` bias at output bit 0 on non-16-byte tail keys. Rotating `h[0] - h[1]` by 29 bits before subtracting `h[2] + h[3]` breaks the bit-0 alignment and clears SMHasher3 `Avalanche` and `BIC` across all key lengths (`0.652%–0.923%` max bias, `0` failures).

4. **Domain-Separated Rotated-Multiply IV (`R5` — fixes `W4` and `W5`):**
   Replaces the linear additive IV (`seed + olen + {1,2,3,5}`) with a domain-separated rotated-multiply IV binding `seed`, `olen`, and `hashsize`:
   ```cpp
   uint64_t dom = ((uint64_t)hashsize << 32) ^ (olen * P);
   uint64_t h[4] = {
     ROTR64(seed ^ dom, 17) * Q + 1,
     (ROTR64(seed + olen, 29) * R) ^ (dom + 2),
     ROTR64(seed ^ (olen * T), 41) * U + 3,
     (ROTR64(seed + dom, 53) * V) ^ W
   };
   ```
   This eliminates cross-width output prefixing (`0 / 200` prefix matches across 64/128/256 bits vs. `200 / 200` in `R0`–`R4` and `R6`), increases the initial 256-bit IV Hamming weight of a top-bit seed flip ($\Delta\mathrm{seed} = 2^{63}$) from `4.0` bits to `76.7` bits, and reduces related-seed collision transfer from `9.5%` to `0.5%` (random chance).

---

## 2. SMHasher3 Verification & Performance (`c2d-highcpu-32`, AMD EPYC Milan)

- **Upstream revision:** `3b619371047761408406991685da1c2b3f751899`
- **Verification codes (`Rainbow 2` / `R5`):**
  - `rainbow2-64`: LE `0xB6EB54B1`, BE `0xD229A9F4`
  - `rainbow2-128`: LE `0xBA2E84CC`, BE `0x10A85C4D`
  - `rainbow2-256`: LE `0x4F7D97BE`, BE `0x5EF63848`
- **Sanity (`--test=Sanity --extra`):** **6 / 6 PASS** across `64`, `128`, `256` bits under both `--endian=native` and `--endian=nonnative` (`42 / 42` across the full `R0`–`R6` ladder).
- **Speed (`--test=Speed` pinned to 1 physical core):**
  - `rainbow2-64`: **`59.01` cycles/hash** (`1–31` B small keys), **`1.44` bytes/cycle (`4.70` GiB/s)** bulk (`256 KiB` aligned)
  - `rainbow2-128`: **`81.93` cycles/hash** (`1–31` B small keys), **`1.41` bytes/cycle (`4.60` GiB/s)** bulk
  - `rainbow2-256`: **`130.98` cycles/hash** (`1–31` B small keys), **`1.39` bytes/cycle (`4.51` GiB/s)** bulk
- **Full Statistical Suite (`Sanity,Avalanche,Sparse,Permutation,Cyclic,TwoBytes,Text,Zeroes,Seed,PerlinNoise,Bitflip,BIC`):**
  - `rainbow2-64`: **100% PASS (`0` failures)** (`stat-all-r5-64-native.log`)
  - `rainbow2-128`: **100% PASS (`0` failures)** (`stat-all-r5-128-native.log`)
  - `rainbow2-256`: **100% PASS (`0` failures)** (`stat-all-r5-256-native.log`)

---

## 3. Standard Test Vectors (`seed = 0`)

| Input | `rainbow2-64` | `rainbow2-128` | `rainbow2-256` |
|---|---|---|---|
| `""` | `4b59479ac9826246` | `0c0ff5e8d2e01117c142d997faefe371` | `343286cc43eb2661e66f0226777cc0d64a820c89258990e6945db30ed44e4787` |
| `"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"` | `ad8f317573c7c359` | `eba16bb1bc724d63b7532092b54c2d22` | `b9daeca49b5b6dfabf81f8143d88b77c084f7089026bd9af981b8eb51de1fb98` |
| `"The quick brown fox jumps over the lazy dog"` | `1df97358a667f7d0` | `16e7e7706dda37a272fc7caa1a5e8acd` | `fd3ffb7c54a739ab1365546ee03566bac46cf9a8276225a715675c3261620973` |
| `"The quick brown fox jumps over the lazy cog"` | `010cf7cb3ef97a88` | `12d2fc2f61962caf054046c1b444a7ce` | `fbb7abb8ad626d2c8b724535822414c2ccf03acb0543c105ddff5cecfd4a2b43` |
| `"The quick brown fox jumps over the lazy dog."` | `22bd2223b97da574` | `6f8584c325227790811c778068fdedc8` | `9738e58fa0048d5ffefbedc66e8c3cc864615e581f7c4cbfa2896a84f546beed` |
| `"After the rainstorm comes the rainbow."` | `9763da0813fa4274` | `fd615647478c5240e23fdae19022d1e9` | `ed050d3c1966f3a76e7af04331d789c80d88619d587f2dad6daef48f6b038ee7` |
| `"@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"` | `e1dca9e98d1545fd` | `ae184a5dd9def32aaa1d61ea34288863` | `b9efd7ab02297c9425702d5e15360ee647af68511c393db3d7462dd0b4f9bf41` |
