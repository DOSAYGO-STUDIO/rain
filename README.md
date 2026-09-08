# Rain

> **News - [Cryptanalysis of Rainstorm](output/pdf/rainstorm-v4-external-cryptanalysis.pdf):** an independent external review reports a practical collision for a two-message-round reduction and no production Rainstorm-128 collision or output distinguisher below the generic $2^{64}$ collision baseline in the completed campaign. The result is evidence, not a security proof.

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
| Rainstorm | 2 - 3 GiB/s (4 rds)| 64, 128, 256, 512 bits   | Proposed as a crypto-hash but requires analyses | Addition/subtraction, rotation, XOR                | Unvetted, no formal analysis    |

---

## Table of Contents

- [Usage Options](#usage-options)
- [Assets](#assets)
- [Building](#building)
- [Benchmark](#benchmark)
- [Repository Structure](#repository-structure)
- [Rainbow](#rainbow)
- [Rainstorm - Unvetted for Security](#rainstorm---unvetted-for-security)
- [Note on Cryptographic Intent](#note-on-cryptographic-intent)
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

---

## Rainstorm - Unvetted for Security

**Rainstorm** is a slower, more complex hash function inspired by cryptographic designs. It supports output sizes of 64 to 512 bits and adjustable rounds. While it uses operations reminiscent of cryptographic hashes, it **is not formally analyzed by any 3rd-party**. Consider it experimental, but designed to be secure. 

### Documents

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

Rainbow is the fastest 128-bit hash, and the fastest 256-bit hash (non-crypto). The 8th fastest 64-bit hash (by family, or 9th fastest overall, and 13-th fatest overall if you include 32-bit hashes). The advantage of rainbow is its easily scalable output size (64, 128 and 256), its high quality (passes all the tests), and its utter simplicity: it is under 140 source lines of code, easily readable

The random constants are primes that were selected based on their avalanche quality under a multiply modulo operation. This part of the development was interesting different primes had very distinctly different avalanche qualities. The highest quality primes caused good avalanche (~ 50% bit flip probability) across the widest possible set of bits, on average. These are quite rare. A lot of large primes only avalanche across a narrow range of bits, even in a 128-bit space. The search program took a couple of days to discover all these primes running on a 2020s era MBP. Primes are chosen because they give a complete residue set under the modulus, ensuring a long cycle length at least regarding the nominal test operation.

The rest of the hash was developed by trial and error using my intuition on developing hashes arising from long experience of doing so, and using SMHasher3 to evaluate the results, by iterating to improve and re-testing, over a period of a couple of weeks in the holidays a few years ago. I started making hash functions in my teens as a fun hobby.

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
