# Add Rainbow 2 (R5) hardened hash family (`rainbow2`, `rainbow2-128`, `rainbow2-256`)

This patch adds **Rainbow 2 (`R5`)** (`hashes/rainbow2.cpp`) as a separate hash family alongside Rainbow v3.7.1 (`hashes/rainbow.cpp`), or can be merged as an in-place update to `hashes/rainbow.cpp` at the maintainer's preference.

## Background & Cryptanalysis of Rainbow v3.7.1

Our algebraic cryptanalysis of Rainbow v3.7.1 identified five structural properties in the 256-bit state schedule:
1. **Pair-sum block injection invariant (`W1`):** `h[0] -= x; h[1] += x; h[2] += y; h[3] -= y;` preserves the two 64-bit pair sums `h[0] + h[1]` and `h[2] + h[3]` across every block injection, reducing full-state collisions to two independent 64-bit birthday searches ($2^{32.29}$ same-seed and $2^{34.86}$ chosen-prefix full-state collisions across all three digest widths).
2. **2-adic differential rays (`W1b`):** Odd-prime multiplication commutes with reduction $\bmod 2^k$, and equal-magnitude lane deltas align across each half (`11.01x` raw DDT ray, `145.3x` quotiented ray at $w=12$).
3. **Pair-separable `mixA` (`W2`):** `mixA` transforms `(h[0], h[1])` and `(h[2], h[3])` independently (`0.000` cross-pair diffusion).
4. **192-bit finalization bottleneck (`W3`):** After the post-loop `mixB`, word `h[0]` is never read or mixed into `(h[2], h[3])` in 64-bit or 128-bit finalization (`0/2000` sensitivity), compressing the 256-bit state through a 192-bit bottleneck.
5. **Cross-width prefixing & linear IV (`W4`, `W5`):** `rainbow-64(m)` is always the 8-byte prefix of `rainbow-128(m)` and `rainbow-256(m)`, and flipping bit 63 of `seed` flips only 4 bits of the initial 256-bit state.

## Summary of Rainbow 2 (`R5`) Changes

Rainbow 2 (`R5`) resolves all five properties while preserving `4.60–4.69` GiB/s bulk throughput (`1.41–1.44` bytes/cycle on AMD EPYC Milan):
- **Asymmetric rotated block load:** `h[0] -= x; h[1] += ROTR64(x, 19); h[2] += y; h[3] -= ROTR64(y, 41);`
- **Feistel cross-coupling in `mixA`:** appends `a ^= d; c ^= b;` at the end of `mixA`.
- **Rotated 4-lane output squeeze:** `g = ROTR64(h[0] - h[1], 29) - h[2] - h[3];`
- **Domain-separated rotated-multiply IV:** binds `seed`, `olen`, and `hashsize` before the first block.

## Validation Against Upstream `3b619371047761408406991685da1c2b3f751899`

- `--test=Sanity --extra --exit-code-on-failure` passes for `rainbow2`, `rainbow2-128`, and `rainbow2-256` under both `--endian=native` and `--endian=nonnative`.
- Verification codes:
  - `rainbow2` (64-bit): LE `0xB6EB54B1`, BE `0xD229A9F4`
  - `rainbow2-128` (128-bit): LE `0xBA2E84CC`, BE `0x10A85C4D`
  - `rainbow2-256` (256-bit): LE `0x4F7D97BE`, BE `0x5EF63848`
- Full statistical suite (`Sanity,Avalanche,Sparse,Permutation,Cyclic,TwoBytes,Text,Zeroes,Seed,PerlinNoise,Bitflip,BIC`) passes with 0 failures across all three widths (`64`, `128`, `256`).
- Paper & full ladder transcripts: https://github.com/DOSAYGO-STUDIO/rain/blob/boss/output/pdf/rainbow-pair-sum-cryptanalysis.pdf
