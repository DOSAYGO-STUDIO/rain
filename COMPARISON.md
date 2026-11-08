# The Pantheon of Hashes: Architectural Comparison of Rainbow 2 & Rainstorm v4

This document presents an objective, no-fluff architectural evaluation of **Rainbow 2** and **Rainstorm v4**, and situates them within the broader landscape of modern non-cryptographic and cryptographic hash functions.

---

## Executive Radar & Landscape Overview

```
                                [Vector / Hardware-Accelerated]
                                      MeowHash (AES-NI)
                                      MuseAir / a5hash
                                             │
             [Bulk Throughput]               │               [Short-Key Latency]
             wyhash / rapidhash              │               rapidhash / ahash
             xxHash3                         │               komihash / ChibiHash
                     \                       │                      /
                      \                      │                     /
                       ────── Rainbow 2 (R5, 64/128/256) ──────────
                                             │
                                             │ [Wide Outputs (128/256-bit)]
                                             │ SMHasher3 100% Clean
                                             │ Mathematically Hardened
                                             ▼
                               [Heavy PRF / Proof-of-Work]
                                     Rainstorm v4 (4-round)
                                     SipHash / HighwayHash
                                             │
                                             ▼
                               [Standardized Cryptography]
                                     BLAKE3 (Tree Hashing)
                                     SHA-256 (SHA-NI)
                                     SHA-3 / Keccak
```

---

## 1. Rainbow 2 in the Non-Cryptographic Pantheon

Rainbow 2 (`R5`) is a hardened, pure scalar non-cryptographic hash family designed for high-throughput, cross-platform portability, and genuine wide-digest diffusion (64, 128, and 256 bits).

### Performance Profile
* **Bulk Streaming Throughput (`4.60`–`4.69` GiB/s, `1.41`–`1.44` B/cycle):**
  * *Versus dedicated AES-NI / AVX-512 engines:* Algorithms leveraging hardware AES instructions (such as `MeowHash` at ~12.4 GiB/s) or heavily unrolled wide vectorization (`MuseAir` at ~7–8 GiB/s) are roughly 2× faster on long keys on modern x86.
  * *Versus scalar C++ algorithms:* Rainbow 2 is on par with `xxHash64` and `FarmHash` (~4.5–5.0 GiB/s), and slightly behind `wyhash` / `rapidhash` (~7–8 GiB/s on platforms featuring fast 64×64 $\to$ 128-bit single-instruction multipliers).
  * *Ranking:* **Top 10–15%** overall for bulk scalar throughput.
* **Short-Key Latency (1–32 Bytes, ~59–131 cycles):**
  * Hash functions engineered exclusively for in-memory hash tables (`rapidhash`, `ahash`, `komihash`) achieve 25–35 cycles on tiny inputs by avoiding full diffusion rounds.
  * Rainbow 2 intentionally incurs an additional ~25–40 cycle tax to execute complete 256-bit cross-diffusion Feistel rounds (`mixA`) and multi-round finalization.
  * *Ranking:* **Mid-pack (45th–50th percentile)** for in-memory hash table lookups of 4-to-8-byte keys.
* **Statistical Cleanliness & SMHasher3 Quality:**
  * **This is Rainbow 2's primary competitive advantage.** Most non-cryptographic hashes either fail to provide native 256-bit digests or, when extended to 256 bits, exhibit bias, sparse-key failures, or avalanche warnings in SMHasher3.
  * Rainbow 2 achieved a **100% PASS rate across all 252 tests** on all three widths (64, 128, and 256-bit) with 0 failures and 0 warnings.
  * *Ranking:* **Top 1%** for wide-output non-cryptographic statistical quality.

### Unique Selling Proposition (USP)
1. **Mathematical Hardening:** Unlike `xxHash`, `Murmur3`, or `wyhash` (which succumb rapidly to linear multicollision attacks under differential cryptanalysis), Rainbow 2 has formal mathematical immunity against pair-sum coset collapse, word-separation, and length-extension attacks ($W_1$–$W_5$).
2. **Absolute Portability:** Less than 200 lines of standard C++20 with zero architecture-specific `#ifdefs`, generating identical output across Apple Silicon, x86_64, WebAssembly, and RISC-V.

> **When to Use Rainbow 2:** Ideal for **content addressing, distributed deduplication, cache keys, chunk integrity, and filesystem indexing** where 128-bit or 256-bit collision immunity against accidental or simple algebraic adversaries is mandatory, without requiring heavy cryptographic primitives.

---

## 2. Rainstorm v4 in the Cryptographic / Heavy PRF Pantheon

Rainstorm v4 is an experimental, round-configurable ARX hash and cipher primitive supporting digest widths from 64 to 512 bits.

### Performance Profile
* **Bulk Throughput (`2.0`–`3.0` GiB/s, 4 rounds):**
  * Substantially faster than software-only (unaccelerated) SHA-256 (~450 MB/s).
  * However, modern desktop and server CPUs feature dedicated hardware instructions (`SHA-NI`), enabling standard SHA-256 to reach 2.5–3.5 GiB/s, while tree-hashed designs like `BLAKE3` reach 10–15 GiB/s via SIMD parallelism.
  * *Ranking:* Competitive with hardware SHA-256, but behind tree-parallelized SIMD cryptographic hashes.
* **Cryptographic Strength & Security Margin:**
  * *Corrected Round Structure:* The v4.0.0 right-round cross-half wraparound correction fixed the 64-bit state-loss flaw from v3.
  * *Differential Cryptanalysis:* In our formal differential campaign, production 4-round Rainstorm ($\mathrm{RS}_n^{(4,4)}$) showed no differential trails or output distinguishers below generic collision bounds.
  * *Honest Reality Check:*
    1. Reduced-round versions are demonstrably vulnerable: 2-round Rainstorm without padding ($\mathrm{RS}_n^{(2,0)}$) collapses to an exact algebraic collision in $2^{31.9}$ operations (~2 seconds).
    2. A 4-round design has a relatively narrow security margin compared to conservative standards such as SHA-3 (24 rounds) or ChaCha20 (20 rounds).
    3. It has not received decades of adversarial cryptanalysis by academic teams worldwide (Gröbner basis solvers, differential-linear attacks, biclique cryptanalysis).
  * *Ranking:* It is an experimental cryptographic construction and heavy PRF; it is **not** a replacement for NIST-standardized cryptography.

### Unique Selling Proposition (USP)
* Rainstorm is uniquely versatile: it scales continuously from 64 to 512 bits, supports arbitrary round counts for security/performance trade-offs, and functions natively as a variable-size block/stream cipher construction via plaintext mining.

> **When to Use Rainstorm:** Ideal for **Proof-of-Work engines, heavy PRFs, MAC generation, experimental encryption, and data-integrity verification** where a custom, highly non-linear, configurable ARX construction is desirable.

---

## 3. Comparative Metric Matrix

| Hash | Primary Role | Bulk Speed | 1–32B Latency | SMHasher3 Status | Cryptanalytic Posture | Portability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Rainbow 2** | Fast Wide Non-Crypto | **4.6–4.7 GiB/s** | ~59–131 cyc | **100% PASS** (64/128/256) | Immune to $W_1$–$W_5$ algebraic attacks | 100% Scalar C++20 |
| **rapidhash** | In-Memory Hash Tables | **7.0–8.8 GiB/s** | **~30 cyc** | 100% PASS (64-bit) | Vulnerable to seed & algebraic attacks | Requires fast 64x64 mult |
| **MeowHash** | x86 Bulk Non-Crypto | **12.4 GiB/s** | ~61 cyc | 100% PASS (AES-NI) | Non-cryptographic | Requires x86 AES-NI |
| **xxHash3** | General Purpose Non-Crypto | **10.0–13.0 GiB/s** | ~35 cyc | 100% PASS | Non-cryptographic | Vectorized (AVX2/NEON) |
| **Rainstorm v4**| Heavy PRF / PoW | **2.0–3.0 GiB/s** | ~180–220 cyc | **100% PASS** (256-bit) | 4-round secure against differential hulls | 100% Scalar C++20 |
| **BLAKE3** | Standard Cryptographic | **10–15 GiB/s** | ~120 cyc | Cryptographic | Full cryptographic standard | SIMD Tree Hashing |
| **SHA-256** | Global Standard | **2.5–3.5 GiB/s (NI)** | ~110 cyc | Standard | Decades of global cryptanalysis | Hardware SHA-NI |
| **SHA-3 / Keccak**| Conservative Crypto | **0.5–0.8 GiB/s** | ~240 cyc | Standard | Extremely high security margin | Large permutation state |

---

## 4. Decision Guide: What Should You Choose?

* Choose **Rainbow 2** if:
  * You need **128-bit or 256-bit** hashes for deduplication, content addressing, distributed object storage, or caching.
  * You want guaranteed zero SMHasher3 failures without vendor-specific intrinsics.
  * You want complete portability across embedded, browser (WASM), mobile, and server environments.
  * You want immunity to trivial algebraic collision tricks without paying the latency cost of SHA-256.

* Choose **Rainstorm v4** if:
  * You need a configurable-round ARX construction with up to 512-bit digest width.
  * You are building a Proof-of-Work system, heavy PRF, or custom authenticated encryption mechanism.
  * You want an auditable, compact cipher/hash dual construction.

* Choose **SHA-256 / BLAKE3** if:
  * You require formal compliance, digital signature security, TLS certificates, password hashing, or legally mandated cryptographic assurance.

---

## 5. Future Architecture: TreeStorm

To bridge the performance gap between serial ARX processing (~2.5 GiB/s) and memory-bandwidth saturation (**30–50+ GiB/s**), the project roadmap includes **TreeStorm**:
* **8-Way AVX-512 Vectorization:** Processes 8 independent 64-byte blocks across 512-bit ZMM registers via native `_mm512_ror_epi64` (`vprorq`), `_mm512_add_epi64`, and `_mm512_xor_si512`.
* **Hierarchical Merkle Tree:** 1 KB / 2 KB chunking with parallel thread dispatch and binary parent node aggregation.
* **IV Domain Separation:** Bit flags (`IS_LEAF`, `IS_PARENT`, `IS_ROOT`) prevent Merkle extension ambiguity at zero performance overhead.
* **Seekable Hashing:** Sub-chunk streaming proofs and incremental file verification.
