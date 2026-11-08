# Rain

> **News - [Cryptanalysis of Rainbow v3.7.1 & Design of Rainbow 2 (`R5`)](output/pdf/rainbow-pair-sum-cryptanalysis.pdf) ([LaTeX](output/pdf/rainbow-pair-sum-cryptanalysis.tex) | [JPEG Contact Sheet](output/pdf/rainbow-pair-sum-cryptanalysis-contact-sheet.jpg) | [X Card 1](output/pdf/rainbow-pair-sum-cryptanalysis-x-sheet-1.jpg) | [X Card 2](output/pdf/rainbow-pair-sum-cryptanalysis-x-sheet-2.jpg) | [Ladder Data](research/rainbow2/results/ALGEBRAIC-LADDER.md)):** Our 10-page cryptanalysis of Rainbow v3.7.1 proves a $2^{32.29}$ same-seed full-state collision (`5.2M` evaluations, `6.6 s`) and a $2^{34.86}$ chosen-prefix collision across all three digest widths (Theorem 1 & Proposition 1), alongside a 192-bit finalization bottleneck (`W3`), 2-adic differential rays (`W1b`), cross-width output prefixing (`W4`), and top-bit seed IV linearity (`W5`). Using an iterative Algebra-to-SMHasher3 hardening ladder (`R0`–`R6`), we introduce **Rainbow 2 (`R5`, [`src/rainbow2.cpp`](src/rainbow2.cpp))** as a separate hardened hash family (`rainsum -a rainbow2`) that eliminates all five structural weakness classes while sustaining `4.60`–`4.69` GiB/s bulk throughput (`1.41`–`1.44` B/cycle).
>
> **News - [Cryptanalysis of Rainstorm v4.0.0](output/pdf/rainstorm-v4-external-cryptanalysis.pdf) ([LaTeX](output/pdf/rainstorm-v4-external-cryptanalysis.tex) | [JPEG Contact Sheet](output/pdf/rainstorm-v4-external-cryptanalysis-contact-sheet.jpg) | [X Card 1](output/pdf/rainstorm-v4-external-cryptanalysis-x-sheet-1.jpg) | [X Card 2](output/pdf/rainstorm-v4-external-cryptanalysis-x-sheet-2.jpg) | [15p Archival Sheet](output/pdf/rainstorm-v4-external-cryptanalysis-15p-contact-sheet.jpg)):** Our external cryptanalysis reports an exact algebraic fold collapse and verified $2^{31.9225}$ collision for two-message-round reduced Rainstorm-256 without padding compression ($\mathrm{RS}_n^{(2,0)}$), characterizes the one-padding-round obstruction and four-inverse-padding-round differential hull, and finds no production Rainstorm-128/256 ($\mathrm{RS}_n^{(4,4)}$) collision or output distinguisher below generic cost in the completed campaign. The result is empirical evidence, not a security proof.
>
> 🏛️ **[The Pantheon of Hashes: Architectural Comparison of Rainbow 2 & Rainstorm v4](COMPARISON.md):** An objective, no-fluff comparison analyzing where Rainbow 2 and Rainstorm v4 stand in bulk speed, small-key latency, SMHasher3 quality, and security margins versus `BLAKE3`, `rapidhash`, `MeowHash`, `xxHash3`, and `SHA-256`.

> [!TIP]
> **Example usage (hash everything)**:
> ```console
>  find . -type f -print0 | xargs -0 -I{} rainsum {}
> ```

This repository features the **Rainbow** and **Rainstorm** hash functions (collectively, **Rain Hashes**), created by [Cris](https://github.com/o0101) at [DOSAYGO](https://github.com/dosyago) and licensed under Apache-2.0. Version-specific [results](results) are available in the `results/` directory, or at the [SMHasher3 GitLab repository](https://gitlab.com/fwojcik/smhasher3/-/blob/main/results/README.md). The CLI tool API is similar to standard tools like `sha256sum`, but with more switches to select algorithm and digest length. The hashes produce digests ranging from 64 through to 512 bits wide. See the table below for details.

### Rainstorm 4.0.0: counter wraparound correction

Rainstorm's right round now subtracts its final counter from `h[0]`, rather than
wrapping to `h[8]`. This adopts the cross-half wraparound proposed by
[@under-my-pillow in issue #161](https://github.com/DOSAYGO-STUDIO/rain/issues/161).
The old index caused an exact 64-bit loss of incoming state information in each
right round for a fixed block. The corrected round is invertible for a fixed
block. This removes that chosen-state collision construction; it is not a proof
of full-hash cryptographic security, and no valid-message collision is claimed.

**Compatibility:** Rainstorm digests change at every output size. Rainstorm-derived
MACs, keys and ciphertext are also incompatible with previous releases. Keep a
matching older release to verify old digests or decrypt old Rainstorm ciphertext.
Rainbow digests are unchanged. Current [test vectors](js/test-vectors.json) cover
all digest sizes; native and WASM implementations are checked against them.

The promoted implementation (candidate A) passed **253/253 checks** in the full
extended SMHasher3 **256-bit native** campaign, including BadSeeds. This result
does not cover a full 512-bit SMHasher3 run: that suite supports widths only
through 256 bits. See the [v4 validation and analysis notes](results/rainstorm-4.0.0/README.md).

The codebase includes:

- A C++ reference implementation
- A WASM port (for Node.js and browser environments)
- A Makefile for building all targets
- An experimental cryptosystem based on [plaintext mining ciphers](https://dosaygo-research.github.io/rain/paper/cipher-note.pdf)

| Algorithm | Speed              | Hash Size        | Purpose                              | Core Mixing Function                              | Security                        |
|-----------|--------------------|------------------|--------------------------------------|---------------------------------------------------|---------------------------------|
| Rainbow   | 3 - 6 GiB/s        | 64, 128, 256 bits| General-purpose, non-crypto hash      | Multiplication, addition/subtraction, rotation, XOR| Not designed as cryptographic   |
| Rainbow 2 (`R5`) | 4.6 - 4.7 GiB/s | 64, 128, 256 bits| Hardened general-purpose fast hash (`-a rainbow2`) | Rotated block load, Feistel `mixA`, 4-lane rotated squeeze, domain IV | Eliminates `W1`–`W5` algebraic weaknesses of Rainbow v3.7.1 |
| Rainstorm | 2 - 3 GiB/s (4 rds)| 64, 128, 256, 512 bits   | Proposed as a crypto-hash but requires analyses | Addition/subtraction, rotation, XOR                | Unvetted, no formal analysis    |

---

## Table of Contents

- [Architectural Comparison (The Pantheon of Hashes)](COMPARISON.md)
- [Usage Options](#usage-options)
- [Assets](#assets)
- [Building](#building)
- [Benchmark](#benchmark)
- [Repository Structure](#repository-structure)
- [Rainbow](#rainbow)
  - [Cryptanalysis of Rainbow v3.7.1 & The Rainbow 2 Hardening Ladder](#cryptanalysis-of-rainbow-v371--the-rainbow-2-hardening-ladder)
- [Rainstorm - Unvetted for Security](#rainstorm---unvetted-for-security)
  - [Cryptanalysis of Rainstorm v4.0.0](#cryptanalysis-of-rainstorm-v400)
- [Note on Cryptographic Intent](#note-on-cryptographic-intent)
- [Roadmap: TreeStorm](#roadmap-treestorm-experimental-parallel-architecture)
- [Genesis](#genesis)
- [License](#license)
- [Rainsum Field Manual](#rainsum-field-manual)
  - [1. Introduction](#1-introduction)
  - [2. Basic Usage](#2-basic-usage)
    - [2.1 Command Structure](#21-command-structure)
    - [2.2 Options](#22-options)
  - [3. Modes of Operation](#3-modes-of-operation)
    - [3.1 Digest Mode](#31-digest-mode)
    - [3.2 Stream Mode](#32-stream-mode)
  - [4. Hash Algorithms and Sizes](#4-hash-algorithms-and-sizes)
  - [5. Test Vectors](#5-test-vectors)
  - [6. Seed Values](#6-seed-values)
  - [7. Help and Version Information](#7-help-and-version-information)
  - [8. Compilation](#8-compilation)
  - [9. Conclusion](#9-conclusion)
- [Developer Information](#developer-information)
  - [Stability](#stability)
  - [Test vectors](#test-vectors)
  - [Building and Installing](#building-and-installing)
  - [Contributions](#contributions)
- [Story](#story)
- [Misue Disclaimer](#misuse-disclaimer)

---

## Usage Options

### JavaScript (WASM) Channel

1. **Node.js Library**
   Install:
   ```bash
   npm i @dosyago/rainsum@latest
   ```
   Usage:
   ```js
   import { rainbowHash, rainstormHash } from '@dosyago/rainsum';

   const seed = 0x0;
   const hash = await rainbowHash(256, seed, 'Hello there!');
   const intendedCryptoHash = await rainstormHash(512, seed, Buffer.from('Hello there!'));
   ```

2. **Global Binary via NPM**
   ```bash
   npm i -g @dosyago/rainsum@latest
   jsrsum --help
   ```

### Native Channel

1. **Build everything** (For WASM ensure [Emscripten](https://emscripten.org/docs/getting_started/downloads.html) is installed):
   ```bash
   make clean && make
   sudo make install  # optional, installs 'rainsum' globally
   ```

   If you encounter troubles on macOS use the build script:
   ```bash
   ./scripts/build.sh
   ```

2. **Use as a library or CLI**:
   - Link `rainstorm.o` or `rainbow.o` into your project, or include `tool.h` and source files from `./src/`.
   - Use the `rainsum` CLI directly:
     ```bash
     rainsum file.txt
     # By default: Rainbow, 256-bit hash
     rainsum --help
     ```

`jsrsum` (via NPM + WASM) mirrors the CLI/API of `rainsum` but runs slower.

---

## Assets

- `rainsum` CLI tool and associated `.o` object files (C++)
- WASM binary
- JS CLI tool (`jsrsum`) with an ES Module API exporting `rainbowHash` and `rainstormHash`
- Scripts:
  - `./scripts/bench.mjs`: Benchmark JS WASM vs C++
  - `./scripts/verify.mjs`: Verify correctness
  - Other utility scripts

---

## Building

```bash
make clean && make
```

Optional installation:
```bash
sudo make install
```

---

## Benchmark

**C++ vs WASM (Node.js)**

These benchmarks highlight the performance gap between native C++ and the WASM-based implementation under Node.js:

```
Test Input & Size          Run   C++ Version        WASM Version       Speedup
10 bytes (input1)          1     6,964,250 ns     129,892,625 ns     18x (C++ wins!)
100 bytes (input2)         1     6,876,208 ns     127,928,542 ns     18x (C++ wins!)
1,000 bytes (input3)       1     6,583,125 ns     127,668,333 ns     19x (C++ wins!)
10,000 bytes (input4)      1     5,920,167 ns     127,438,666 ns     21x (C++ wins!)
100,000 bytes (input5)     1     6,214,916 ns     127,551,791 ns     20x (C++ wins!)
1,000,000 bytes (input6)   1     5,321,500 ns     126,986,167 ns     23x (C++ wins!)
10,000,000 bytes (input7)  1     9,879,042 ns     132,929,875 ns     13x (C++ wins!)
100,000,000 bytes (input8) 1    49,761,375 ns     207,500,917 ns      4x (C++ wins!)
```

Runs 2 and 3 show similar results, consistently demonstrating that the native C++ version outperforms the WASM variant by a factor of ~3x to ~25x, depending on input size.

---

## Repository Structure

```
.
├─ LICENSE.txt
├─ Makefile
├─ README.md
├─ docs/
├─ js/
├─ rain/
│  ├─ bin/
│  └─ obj/
├─ results/
│  ├─ dieharder/
│  └─ smhasher3/
├─ scripts/
└─ src/
   ├─ common.h
   ├─ rainbow.cpp
   ├─ rainstorm.cpp
   ├─ rainsum.cpp
   ├─ tool.h
   └─ ...
```

---

## Rainbow

**Rainbow** is a fast, general-purpose non-cryptographic hash that can produce 64-bit, 128-bit, or 256-bit hashes. It is simple, compact (~140 LOC), and passes all SMHasher3 tests for its 64-bit variant. Its prime-based mixing function yields strong avalanche properties.

### Cryptanalysis of Rainbow v3.7.1 & The Rainbow 2 Hardening Ladder

- **Paper (10-page manuscript)**: [PDF](output/pdf/rainbow-pair-sum-cryptanalysis.pdf) | [LaTeX Source (`.tex`)](output/pdf/rainbow-pair-sum-cryptanalysis.tex) | [Contact Sheet (5x2 JPEG)](output/pdf/rainbow-pair-sum-cryptanalysis-contact-sheet.jpg) | [Portrait Contact Sheet (2x5 JPEG)](output/pdf/rainbow-pair-sum-cryptanalysis-contact-sheet-portrait.jpg) | [X Card 1 (Pages 1–5)](output/pdf/rainbow-pair-sum-cryptanalysis-x-sheet-1.jpg) | [X Card 2 (Pages 6–10)](output/pdf/rainbow-pair-sum-cryptanalysis-x-sheet-2.jpg) | [Page Renders (`page-01.jpg`–`page-10.jpg`)](output/pdf/rainbow-pair-sum-cryptanalysis-pages)
- **Implementation & Validation**: [`src/rainbow2.cpp`](src/rainbow2.cpp) (`rainsum -a rainbow2`) | [`results/rainbow-2/`](results/rainbow-2) | [`research/rainbow/`](research/rainbow) (Collision & Chosen-Prefix Witnesses) | [`research/rainbow-spectrum/`](research/rainbow-spectrum) (`Q01`–`Q28`) | [`research/rainbow2/results/ALGEBRAIC-LADDER.md`](research/rainbow2/results/ALGEBRAIC-LADDER.md)

#### Structural Weaknesses Identified in Rainbow v3.7.1 (`src/rainbow.cpp`)

1. **W1 — Pair-Sum Coset Collapse & Practical Full-Hash Collisions (Theorem 1 & Proposition 1):** In Rainbow's 16-byte streaming loop, each block $(x, y) \in (\mathbb{Z}/2^{64}\mathbb{Z})^2$ enters the 256-bit state $h = (h_0, h_1, h_2, h_3)$ via
   $$h_0' = h_0 - x, \qquad h_1' = h_1 + x, \qquad h_2' = h_2 + y, \qquad h_3' = h_3 - y.$$
   This preserves the two 64-bit pair sums $\sigma_1(h) = h_0 + h_1$ and $\sigma_2(h) = h_2 + h_3$ across every block injection (`Lemma 1`). Two 256-bit states $S, T$ are mergeable by a single 16-byte message block in $O(1)$ time (`0` search queries) if and only if $\sigma_1(S) = \sigma_1(T)$ and $\sigma_2(S) = \sigma_2(T)$ (`Theorem 1`, verified `1000/1000`). Furthermore, because `mixA` acts independently on $(h_0, h_1)$ and $(h_2, h_3)$ (`Definition 1`), a 2-block state collision after an `mixA` step decouples into **two independent 64-bit birthday searches** (`Proposition 1`), yielding:
   - **Same-seed full-hash collision (`Result 2`):** Two 32-byte messages (`000000000000000021000000000000000b12e4797bf1493f2100000000000000` and `0000000000000000210000000000000006bf63eb8160bd702100000000000000`) found in `5,206,393,642` evaluations ($2^{32.29}$, `6.63 s` on M1) that merge to the identical 256-bit internal state and collide across `rainbow-64`, `rainbow-128`, and `rainbow-256`.
   - **Chosen-prefix full-hash collision (`Result 3`):** Two 96-byte chosen-prefix messages (`From: alice@example.com Amount: USD    10.00` vs `USD 1000000.00`) found in `29,864,438,256` evaluations ($2^{34.86}$, `50.0 s`) that collide across all three digest widths.
2. **W1b — 2-Adic Differential Rays (`Q18`/`Q19`):** Because multiplication by odd primes (`P, Q, R, S, T, U, V, W`) preserves the 2-adic valuation $v_2(\Delta)$ and the symmetric injection $\Delta h = (-\Delta x, +\Delta x, +\Delta y, -\Delta y)$ aligns high-valuation differences across both lanes of each half, 1-block differential distribution tables exhibit sharp anisotropic rays ($M_r = 11.01\times$, quotiented ray $S_r = 145.29\times$ at $w=12$).
3. **W2 — Exact Pair-Separability of `mixA`:** `mixA` transforms $(h_0, h_1)$ and $(h_2, h_3)$ as two completely independent 128-bit halves: $\mathrm{mixA}(h_0, h_1, h_2, h_3) = (F_1(h_0, h_1), F_2(h_2, h_3))$. Cross-pair diffusion between $(h_0, h_1)$ and $(h_2, h_3)$ is identically **`0.000`** for any number of consecutive `mixA` rounds $k \ge 1$.
4. **W3 — 192-Bit Finalization Bottleneck (`Q20`, Proposition 2):** In finalization (`mixB(h, seed); [tail]; mixA(h); mixB(h, seed); mixA(h);`), `mixB` leaves $h_0$ untouched and `mixA` never couples $(h_0, h_1)$ into $(h_2, h_3)$, while the output squeeze `g = 0 - h[2] - h[3]` reads only $(h_2, h_3)$. Consequently, after the post-loop `mixB`, **word $h_0''$ is 100% dead in 64-bit and 128-bit finalization** (`0/2000` sensitivity), compressing the 256-bit state through a **192-bit bottleneck** before the digest is emitted. On the $w=4$ (16-bit) model, the finalizer reaches only `4,007 / 65,536` (`6.11%`) of the state space vs. $1 - e^{-1} \approx 63.21\%$ for a uniform random map.
5. **W4 & W5 — Cross-Width Output Prefixing & Top-Bit Seed Linearity (`Q22`):** Because `hashsize` is absent from the IV (`seed + olen + {1,2,3,5}`) and finalization emits words sequentially from the same trajectory, `rainbow-64(m)` is always the exact 8-byte prefix of `rainbow-128(m)` and `rainbow-256(m)` (`200/200` trials). Moreover, flipping the top bit of the seed ($\Delta\mathrm{seed} = 2^{63}$) flips only bit 63 in each initial lane (`4.0` bits out of 256), transferring $9.5\%$ of message collisions across related seeds at $w=8$.

#### The Rainbow 2 Hardening Ladder (`R0` – `R6`) & Iterative Algebra-to-SMHasher3 Discovery

To evaluate minimal, speed-preserving fixes without pre-judging the design trade-off, we constructed a 7-rung hardening ladder (`R0`–`R6`) and benchmarked all 21 variants (`r0..r6` $\times$ `64, 128, 256` bits) through **SMHasher3** on a 32-vCPU AMD EPYC Milan instance (`c2d-highcpu-32`).

During the initial SMHasher3 `Avalanche` sweep, a remarkable interaction emerged between `R2`'s Feistel cross-XOR (`a ^= d; c ^= b;`) and an unrotated 4-lane XOR-subtract squeeze `g_unrot = (h[0] ^ h[2]) - (h[1] ^ h[3])`: while `R0, R1, R2, R3, R6` passed 100%, the unrotated squeeze exhibited a **27.6%–27.7% bias at output bit 0** on non-block-aligned tail keys (3–12 and 20 bytes). We proved the exact algebraic mechanism (**Proposition 3 in the paper**): after `mixA` ends with `a ^= d; c ^= b;`, the state is $(h_0, h_1, h_2, h_3) = (a \oplus d, b, c \oplus b, d)$. Setting $Y = a \oplus c$ and $X = b \oplus d$, the unrotated squeeze equals
$$g_{\mathrm{unrot}} = (h_0 \oplus h_2) - (h_1 \oplus h_3) = (Y \oplus X) - X \pmod{2^{64}},$$
whose least significant bit is $(Y_0 \oplus X_0) \oplus X_0 \equiv Y_0 \pmod 2$, **canceling $X_0 = b_0 \oplus d_0$ out of bit 0 identically!** Replacing the unrotated squeeze in `R4` and `R5` with the rotated 4-lane subtract squeeze
$$g = \mathrm{ROTR}_{29}(h_0 - h_1) - h_2 - h_3$$
breaks the bit-alignment between $(h_0, h_1)$ and $(h_2, h_3)$, eliminating the cancellation completely and reducing max SMHasher3 `Avalanche` bias to `0.652%–0.923%` (`0` failures across all widths).

| Rung | Modification Summary | LE Verif (`64 / 128 / 256`) | W1: 1-Block Merges | W1b: DDT Ray $M_r$ | W2: `mixA` Cross-Pair | W3a: Dead-Word Live (`h0''`) | W3b: $w=4$ Finalizer Image | W4: Cross-Width Prefix | W5: $\Delta\mathrm{seed}=2^{63}$ IV Wt | Small Keys (`64/128/256` cyc/hash) | Bulk Speed (`256 KiB` aligned) | SMHasher3 Suite |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **R0** | Baseline Rainbow v3.7.1 | `ED7533D3` / `FF03173F` / `65F4A210` | `1000/1000` ❌ | `11.01x` ❌ | `0.000` ❌ | `0/2000` ❌ | `6.1%` ❌ | `200/200` ❌ | `4.0` b ❌ | `50.53 / 56.94 / 87.13` | `1.47` B/c (`4.79` GiB/s) | PASS (`64/128/256`) |
| **R1** | Asymmetric rotated block load (`ROTR64(x,19)`, `ROTR64(y,41)`) | `095F02F9` / `FBDC549E` / `570AB08D` | **`0/1000`** ✅ | **`3.95x`** ✅ | `0.000` ❌ | `0/2000` ❌ | `6.1%` ❌ | `200/200` ❌ | `4.0` b ❌ | **`49.87 / 53.68 / 85.85`** | **`1.47` B/c (`4.79` GiB/s)** | PASS (`64/128/256`) |
| **R2** | Feistel cross-XOR in `mixA` (`a ^= d; c ^= b;`) | `E02D3EC1` / `5CF6A260` / `A5D67BE2` | `1000/1000` ❌ | `8.98x` ⚠️ | **`0.500`** ✅ | **`2000/2000`** ✅ | **`63.7%`** ✅ | `200/200` ❌ | `4.0` b ❌ | `56.99 / 67.22 / 112.11` | `1.39` B/c (`4.52` GiB/s) | PASS (`64/128/256`) |
| **R3** | `R1 + R2` combined core | `E2B79318` / `E09013C2` / `D32AAA3D` | **`0/1000`** ✅ | **`3.67x`** ✅ | **`0.500`** ✅ | **`2000/2000`** ✅ | **`63.7%`** ✅ | `200/200` ❌ | `4.0` b ❌ | `56.35 / 64.65 / 112.19` | `1.44` B/c (`4.69` GiB/s) | PASS (`64/128/256`) |
| **R4** | `R3` + rotated 4-lane squeeze `ROTR64(h0-h1,29)-h2-h3` | `CA69A2EB` / `8CD2FC6F` / `21A65AE5` | **`0/1000`** ✅ | **`3.67x`** ✅ | **`0.500`** ✅ | **`2000/2000`** ✅ | **`63.2%`** ✅ | `200/200` ❌ | `4.0` b ❌ | `56.45 / 82.62 / 130.20` | `1.39–1.44` B/c (`4.51–4.70` GiB/s) | PASS (`Avalanche,BIC`) |
| **R5 (Rainbow 2)** | `R4` + domain-separated rotated-multiply IV | **`B6EB54B1` / `BA2E84CC` / `4F7D97BE`** | **`0/1000`** ✅ | **`3.67x`** ✅ | **`0.500`** ✅ | **`2000/2000`** ✅ | **`63.2%`** ✅ | **`0/200`** ✅ | **`76.7` b** ✅ | `59.01 / 81.93 / 130.98` | `1.39–1.44` B/c (`4.51–4.70` GiB/s) | **PASS (`64/128/256` All - 100%)** |
| **R6** | Zero-instruction cyclic `mixA` (`b^=c; d^=a; s=[b,c,d,a]`) + `R1` + `R4` | `F502226B` / `5002C45E` / `24832643` | **`0/1000`** ✅ | **`3.70x`** ✅ | **`0.375`** ✅ | **`2000/2000`** ✅ | **`63.2%`** ✅ | `200/200` ❌ | `4.0` b ❌ | **`45.66 / 55.05 / 95.61`** | `1.41–1.42` B/c (`4.61–4.62` GiB/s) | PASS (`64/128/256`) |

#### Design Rationale: Why `R5` Was Selected as Rainbow 2 (`rainbow2`)

1. **Why not `R1` alone?** `R1` breaks Theorem 1's pair-sum coset collapse at zero speed cost (`49.87` cycles/hash, `4.79` GiB/s), but leaves `mixA` 100% pair-separable (`W2`) and retains the 192-bit finalization bottleneck (`W3`), where word $h_0''$ is 100% dead in 64-bit mode and the $w=4$ finalizer reaches only `6.1%` of the state space.
2. **Why not `R3` or `R4`?** `R3` and `R4` fix the streaming and finalization core (`W1`–`W3`) at `4.61–4.69` GiB/s, but retain the linear additive IV (`W4`–`W5`), leaving `rainbow-64(m)` as a trivial 8-byte prefix of `rainbow-128/256(m)` and leaving top-bit seed flips ($\Delta\mathrm{seed} = 2^{63}$) with only a `4.0`-bit initial IV difference (`9.5%` related-seed collision transfer).
3. **Why not `R6`?** `R6` achieves the lowest small-key latency (`45.66` cycles/hash) by placing `b ^= c; d ^= a;` prior to the second multiply in `mixA` and cyclically renaming the output registers. However, its 2-round cross-pair avalanche (`0.375`) is slightly below the full `0.500` diffusion of the post-multiply Feistel cross-coupling in `R2`–`R5`, and without `R5`'s IV it leaves `W4` and `W5` open.
4. **Why `R5` is the complete design point:** **`R5` is the only rung on the ladder that eliminates every structural weakness identified in our cryptanalytic campaign (`W1`, `W1b`, `W2`, `W3`, `W4`, and `W5`) simultaneously.** Its bulk streaming loop is identical to `R3`/`R4` and runs at `4.60–4.69` GiB/s (`96%–98%` of unmodified Rainbow 1's `4.79` GiB/s), because the domain-separated rotated-multiply IV and the rotated 4-lane output squeeze execute only once per message outside the block loop. Promoting `R5` as a separate hash family (**Rainbow 2**, [`src/rainbow2.cpp`](src/rainbow2.cpp), `rainsum -a rainbow2`) preserves 100% backward compatibility for existing Rainbow 1 test vectors while providing a hardened 64/128/256-bit family whose wider digests deliver genuine full-state mixing.
5. **SMHasher3 Upstream Integration:** All three widths (`rainbow2-64`, `rainbow2-128`, `rainbow2-256`) completed 100% clean passes on the full SMHasher3 test suite (`--test=All`, 252/252 tests, 0 failures, logs archived in [`research/rainbow2/results/smhasher3-campaign/results/`](research/rainbow2/results/smhasher3-campaign/results/)). Submitted upstream to SMHasher3 via [GitLab Merge Request !37](https://gitlab.com/fwojcik/smhasher3/-/merge_requests/37).

---

## Rainstorm - Unvetted for Security

**Rainstorm** is a slower, more complex hash function inspired by cryptographic designs. It supports output sizes of 64 to 512 bits and adjustable rounds. While it uses operations reminiscent of cryptographic hashes, it **is not formally certified**. Consider it experimental, with public cryptanalytic evaluation documented below.

### Cryptanalysis of Rainstorm v4.0.0

- **Paper (8-page revised manuscript)**: [PDF](output/pdf/rainstorm-v4-external-cryptanalysis.pdf) | [LaTeX Source (`.tex`)](output/pdf/rainstorm-v4-external-cryptanalysis.tex) | [Standalone Python Verifier](research/differential/verify_paper_collision.py)
- **Contact Sheets (JPEG for X / social)**: [Full 8-Page Contact Sheet (4x2)](output/pdf/rainstorm-v4-external-cryptanalysis-contact-sheet.jpg) | [Portrait 8-Page Sheet (2x4)](output/pdf/rainstorm-v4-external-cryptanalysis-contact-sheet-portrait.jpg) | [X Post Card 1 (Pages 1–4)](output/pdf/rainstorm-v4-external-cryptanalysis-x-sheet-1.jpg) | [X Post Card 2 (Pages 5–8)](output/pdf/rainstorm-v4-external-cryptanalysis-x-sheet-2.jpg) | [Archival 15-Page Campaign Contact Sheet](output/pdf/rainstorm-v4-external-cryptanalysis-15p-contact-sheet.jpg)
- **Individual Page Renders**: [`output/pdf/rainstorm-v4-external-cryptanalysis-pages/`](output/pdf/rainstorm-v4-external-cryptanalysis-pages) (`page-01.jpg`–`page-08.jpg`)

#### Summary of Findings (`src/rainstorm.cpp` v4.0.0, SHA-256 `8b70ceb6...`)

1. **Exact Right-Round Message Programming (Lemma 1):** For any fixed incoming 1024-bit state $(L, H)$ and any target vector of transformed first-round outputs $(y_0, \dots, y_7) \in (\mathbb{Z}/2^{64}\mathbb{Z})^8$, there is a unique 64-byte message block $d_i = q_i \oplus (\mathrm{ROTL}_{Z_i}(y_i) + K_i)$ realizing $y$ in one right round $R_d$.
2. **Two-Round Algebraic Fold Collapse (Proposition 1 & Corollary 1):** After one programmed right round $R_d$ and the subsequent left round $T_d$ on the same block, the subtractive fold $F_i = L_i'' - H_i''$ satisfies the exact identity
   $$F_0 = C_L + \sum_{j=0}^7 x_j - y_0 + 2(y_0 \land x_0), \qquad F_i = -y_i + 2(y_i \land x_i) \quad (1 \le i \le 7)$$
   using $a \oplus b = a + b - 2(a \land b) \pmod{2^{64}}$. Choosing the 1-parameter family $y(v) = (0, 0, 0, 0, 0, 0, v, -v)$ forces $F_1 = F_2 = F_3 = F_4 = F_5 = 0$ identically and keeps the right-round counter wrap $c_8 = C_R$ fixed, collapsing six of the eight folded 64-bit words into a single 64-bit scalar condition $G(v) = F_0(v) = C_L + \sum_{j=0}^7 x_j(v)$.
3. **Finalization Prefix Preservation & Practical Reduced Collision (Lemma 2 & Proposition 2):** Because finalization left rounds $T_P$ are triangular in lane index ($a_i, x_i, L_i'$ depend only on lanes $\le i$), equality of the first six folded words $(F_0, \dots, F_5)$ is preserved through any number of finalization rounds. A 64-walk distinguished-point rho search on an Apple M1 MacBook Air found the colliding parameters `v_a = 685a913fd5b0d24c` and `v_b = edf1c79141fbc6c4` after **`4,070,333,044` ($2^{31.9225}$) walk evaluations** (`73.572 s` wall time, `55.3M` evals/s), yielding distinct 64-byte messages that collide across the full 64-, 128-, and 256-bit reduced digests $\mathrm{RS}_n^{(2,0)}$ (and share their first six 64-bit output words under $\mathrm{RS}_{512}^{(2,0)}$).
4. **The Padding Boundary & Full-Schedule Separation (Proposition 3):** Restoring a single mandatory padding round ($\mathrm{RS}_n^{(2,1)}$) preserves the five zero fold words $F_1 = \dots = F_5 = 0$ on the $y(v)$ family, but adds an exact second 64-bit condition $S(v) = \sum_{j=0}^7 u_j(v)$ at fold word zero. On the recovered $\mathrm{RS}_n^{(2,0)}$ witness, $S(v_a) =$ `56dd9e897c83da47` $\ne$ `0aa1525395140b82` $= S(v_b)$, so the reduced collision is separated by production Rainstorm ($\mathrm{RS}_n^{(4,4)}$, four message rounds + four padding rounds). Across the full differential, rebound, higher-order, MITM, and SAT/SMT (Z3 / Bitwuzla) campaigns, no collision or output distinguisher was found for full production Rainstorm.

| Target Variant | Rounds $(r_m, r_p)$ | Result | Complexity / Status |
|---|---|---|---|
| $R_d$ (1st message round) | $(1, 0)$ | Exact 8-word state programming ($y_0, \dots, y_7$) | $O(1)$ per block (bijective) |
| $\mathrm{RS}_{64/128/256}^{(2,0)}$ | $(2, 0)$ | 6-word fold collapse ($F_1=\dots=F_5=0$) + full 256-bit collision | **$2^{31.9225}$** walk evals (`73.6 s` on M1, verified witness) |
| $\mathrm{RS}_{64/128/256}^{(2,1)}$ | $(2, 1)$ | 5-word collapse preserved; adds 2nd 64-bit condition $S(v_a)=S(v_b)$ | 128-bit target on 64-bit family ($2^{-64}$ random-map survival) |
| $T_P^{-4} \circ \mathrm{Fold}$ | $(0, 4)$ inv. | Sparse backward differential hull from arbitrary pre-fold state | $\Pr[\mathrm{wt} \le 36] \approx 2.16 \times 10^{-7}$ ($58 / 2^{28}$ held-out pairs; unreachable from IV) |
| Production $\mathrm{RS}_n^{(4,4)}$ | $(4, 4)$ | Full 4 message + 4 padding rounds + finalization | **No collision or distinguisher found** |

### Documents

- **Cryptanalysis of Rainstorm v4.0.0 (Fold Collapse & Full-Schedule Boundary)**: [PDF](output/pdf/rainstorm-v4-external-cryptanalysis.pdf) | [Contact Sheet (JPEG)](output/pdf/rainstorm-v4-external-cryptanalysis-contact-sheet.jpg)
- **Rainstorm Formal Spec (Draft)**: [PDF](docs/paper/storm-spec.pdf)
- **Rainstorm Crypto Note**: [PDF](docs/paper/crypto-note.pdf)

---

## Note on Cryptographic Intent

Rainstorm's design includes concepts from cryptographic hashing, but without formal analysis, it should not be considered secure. Feedback and analysis are welcome.

---

## Genesis

The mixing functions were inspired by Discohash and refined iteratively using SMHasher3 over a few weeks, guided by experience and intuition. Careful prime selection ensured broad avalanche properties.

---

## License

Apache-2.0 © 2023 - 2024 Cris & DOSAYGO Corporation. With improvements &copy; Frank J. T. Wojcik 2023

---

# Rainsum Field Manual

## 1. Introduction

Rainsum is a CLI tool for hashing input data using Rainbow or Rainstorm. It supports two primary modes:
- **Digest Mode:** Produces a fixed-length hexadecimal output.
- **Stream Mode:** Iteratively feeds the hash back into itself to produce a variable-length stream of binary output.

A JavaScript WASM version (`jsrsum`) offers similar functionality at reduced speed.

## 2. Basic Usage

### 2.1 Command Structure

```
rainsum [OPTIONS] [INFILE]
```

If no `INFILE` is provided, input is read from standard input.

### 2.2 Options

- `-m, --mode [digest|stream]`: Default `digest`.
- `-a, --algorithm [bow|storm]`: Choose `rainbow` (`bow`) or `rainstorm` (`storm`). Default `storm`.
- `-s, --size [64-256|64-512]`: Hash size in bits. Default `256`. Rainbow supports 64,128,256. Rainstorm supports 64,128,256,512.
- `-o, --output-file FILE`: Write output to `FILE`.
- `-t, --test-vectors`: Run test vectors.
- `-l, --output-length HASHES`: For stream mode, number of iterations.
- `--seed VALUE`: Sets the seed (64-bit number or string). A string seed is hashed by Rainstorm to produce a 64-bit seed.
- `-h, --help`: Show help.
- `-v, --version`: Print version.

## 3. Modes of Operation

### 3.1 Digest Mode

Produces a single, fixed-size hash in hex. For example:

```bash
rainsum -m digest -a storm -s 256 -o output.txt input.txt
```

### 3.2 Stream Mode

Generates a stream of hashes by repeatedly feeding the previous hash into the function. Specify iterations with `-l`. Example:

```bash
rainsum -m stream -a storm -s 512 -l 1000000 -o output.txt input.txt
```

## 4. Hash Algorithms and Sizes

- `bow` (Rainbow): 64, 128, 256 bits
- `storm` (Rainstorm): 64, 128, 256, 512 bits

## 5. Test Vectors

Use `-t, --test-vectors` to verify correctness against known inputs.

## 6. Seed Values

Use `--seed` to set a custom seed. String seeds are hashed to a 64-bit value.

## 7. Help and Version Information

- `rainsum --help`
- `rainsum --version`

## 8. Compilation

A modern C++17 compiler is required. Run `make` to build. Ensure necessary build tools (like `xcode-select` on macOS) are installed. On macOS you should use `./scripts/build.sh` to ensure that path to the correct compiler and SDK is accurate, modify that script if needed for your system.

## 9. Conclusion

Rainsum provides flexible hashing through Rainbow or Rainstorm. Experiment freely and enjoy the convenience of multiple modes and sizes.

---

# Developer Information

## Stability

The hash definitions may evolve. Changes that affect outputs will be indicated by version increments.

## Test Vectors

Refer to `--test-vectors` and `results/` for known outputs and verification.

## Building and Installing

```bash
make
sudo make install
rainsum --help
```

## Contributions

Improvements, analyses, and faster implementations are welcomed.

---

# Story

This is my hash included in the best hash testing library out there "SMHasher3" maintained by Frank T Wojcik: https://gitlab.com/fwojcik/smhasher3
This test lib has many improvements over SMHasher 1 & 2, listed on the previous link. Results are: https://gitlab.com/fwojcik/smhasher3/-/blob/main/results/README.md

When first benchmarked in SMHasher3, Rainbow was among the fastest portable 128-bit and 256-bit non-cryptographic hashes without requiring specialized hardware vector or AES instructions. Today, with modern vectorized contenders in the arena, Rainbow and Rainbow 2 remain remarkably fast portable scalar hash families (4.6–4.8 GiB/s, ~1.4 B/cycle) with scalable 64, 128, and 256-bit digests that pass SMHasher3 cleanly. Rainbow 2 hardens the original design against algebraic collision classes (W1–W5) while maintaining compact, easily auditable source code (~150–200 LOC). Alongside Rainbow, Rainstorm provides an experimental, round-configurable hash with formal differential analysis.

The random constants are primes that were selected based on their avalanche quality under a multiply modulo operation. This part of the development was interesting different primes had very distinctly different avalanche qualities. The highest quality primes caused good avalanche (~ 50% bit flip probability) across the widest possible set of bits, on average. These are quite rare. A lot of large primes only avalanche across a narrow range of bits, even in a 128-bit space. The search program took a couple of days to discover all these primes running on a 2020s era MBP. Primes are chosen because they give a complete residue set under the modulus, ensuring a long cycle length at least regarding the nominal test operation.

The rest of the hash was developed by trial and error using my intuition on developing hashes arising from long experience of doing so, and using SMHasher3 to evaluate the results, by iterating to improve and re-testing, over a period of a couple of weeks in the holidays a few years ago. I started making hash functions in my teens as a fun hobby.

---

## Roadmap: TreeStorm (Experimental Parallel Architecture)

**TreeStorm** is an experimental high-throughput parallel tree-hashing architecture on the project roadmap, designed to scale Rainstorm from scalar execution (~2.5 GiB/s) to memory-bandwidth saturation (**30–50+ GiB/s** across multi-core systems):

1. **8-Way AVX-512 SIMD Multi-Buffer Kernel:**
   - Rainstorm’s round operations map 1:1 onto native 64-bit AVX-512 vector instructions (`vprorq` / `_mm512_ror_epi64`, `vpaddq` / `_mm512_add_epi64`, and `vpxorq` / `_mm512_xor_si512`).
   - Rather than vectorizing within a single block (which is bottlenecked by sequential data dependencies), the kernel interleaves 8 independent message blocks simultaneously across 512-bit ZMM registers, delivering an immediate ~5–7× single-core throughput multiplier (14–18 GiB/s).

2. **Hierarchical Merkle Tree Structure (BLAKE-style):**
   - The input stream is chunked into 1 KB or 2 KB leaves.
   - Leaves are processed in parallel (8 chunks per AVX-512 thread, farmed out across CPU worker threads via OpenMP/multiprocessing).
   - Parent nodes hash the concatenated 256-bit or 512-bit digests of their children in a balanced binary Merkle tree until the root is produced.

3. **Domain Separation & Security Guarantees:**
   - Strict domain separation flags (`IS_LEAF`, `IS_PARENT`, `IS_ROOT`) embedded directly in the Rainstorm IV prevent tree-mangling, length-extension, and leaf/node confusion attacks at zero runtime cost.

4. **Seekable & Incremental Hashing:**
   - Enables constant-time verification of arbitrary byte ranges in multi-gigabyte files (Bao-style streaming proofs) and $O(\log N)$ incremental updates.

---

### Misuse Disclaimer

> [!WARNING]
> Do not use this for bad things.

This project is provided under the Apache-2.0 license and is intended for lawful and ethical purposes only. The author(s) of this software explicitly disclaim any liability for its use in activities that violate applicable laws, regulations, or ethical standards. By using this project, you agree to comply with all relevant laws and not to use it for malicious or harmful purposes, including but not limited to:

- Developing or distributing malware, ransomware, or other harmful software.
- Compromising the privacy, security, or rights of others.
- Engaging in illegal surveillance or unauthorized access to systems.

The responsibility for the use or misuse of this software lies entirely with the user. If you do not agree with these terms, do not use this software.

  **Copyright 2024 Dosyago Corporation USA and @o0101**

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

**Reiteration of some key sections from the LICENSE**

   7. **Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.**

   8. **Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.**

   9. **Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.**


---
