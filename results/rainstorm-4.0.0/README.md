# Rainstorm 4.0.0 validation

The release promotes experimental candidate A: the final counter subtraction in
the right round targets `h[0]` instead of `h[8]`. No round count, padding, IV,
finalization or extraction behavior was otherwise changed. Rainbow is unchanged.

## Differential red team

For a fixed input block, the old right round is exactly 2^64-to-1 on incoming
1024-bit states. If its transformed high words before the final subtraction are
y0,...,y7, its final h[8] is −CTR_RIGHT−sum(y1,...,y7), independent of y0.
Choose any y0 and compensate the low word and incoming high words to obtain
the same complete round output. This constructs chosen-state collisions without
searching 2^64 possibilities. It does not establish that such states can be
reached from the hash IV by valid messages.

The corrected round retains all eight transformed high words. Recover its
pre-subtraction low h[0] by adding CTR_RIGHT+sum(y0,...,y7); the remaining
operations can then be undone in reverse. It is a permutation for each fixed
block, ruling out that same-block chosen-state collision family.

A pre-release check reproduced 1,000 old-round collisions. None of those pairs
collided under A, and all 1,000 A inverse checks passed. Both designs retain a
simple one-right-round truncated differential in an inactive low word; that
observation is not a full-hash attack. A also allows efficient backward
evaluation when the full internal state and block are known. A digest does not
expose that full state. Finalization's truncation and cross-size relations
remain unchanged; no full-hash security proof is asserted.

Fresh finite-domain screens tested 770,048 message pairs **per design**, over
64/128/256/512-bit outputs, seed zero, and lengths 1,15,16,17,63,64,65,127,128,129.
Each of 188 selected input-difference/output-size cases used 4,096 random pairs.
No full-digest collision was found in either design. No bit/byte projection
alerts occurred on domains longer than one byte. One-byte domains have at most
128 unordered pairs for a fixed nonzero XOR difference, so projected imbalance
there is not evidence of a scalable attack.

These are bounded searches over declared cases, not a guarantee against every
differential. Assuming IID uniform messages, the union bound for missing any
output difference of probability at least p in D tested cases is
min(1, D/p * (1-p)^N). No inference is made about untested differences, seeds,
lengths, rare events, or attacker-selected internal-state reachability.

## SMHasher3

Upstream revision: `3b619371047761408406991685da1c2b3f751899`.
Command: `SMHasher3 --test=All,BadSeeds --extra --exit-code-on-failure --endian=native --ncpu=16 rainexp-a-256`.
Result: **pass, 253/253 checks**, exit code 0, 12,879.24 seconds.
The exact-source adapter used the same test-budget metadata as the original.
The full original also passed 253/253 checks. A's verification constants were
`0x46A86116` (native LE) and `0x41895C3A` (local nonnative adapter). The local nonnative padded-tail convention differs from the
upstream SMHasher3 implementation; upstream verification constants must be
computed from its own implementation.

The complete candidate-A log is in `smhasher3-A-256-native.log`; its SHA-256 is
recorded in `validation.json`. It includes statistical results and speed data,
not credentials or cloud connection details. Per-case p-values are dependent
and are not a cryptographic quality score. A showed a favorable seed-avalanche
pattern (lower bias in 10/12 cases versus the original), but mixed ordinary
avalanche results and an 11.6% small-key cycle cost in this measurement.

SMHasher3's instantiated output widths stop at 256 bits. All four Rainstorm
widths are covered separately by native/WASM vectors, streaming equivalence,
and differential checks. The original frozen sources remain under
`research/differential/reference/src` so the historical analysis is reproducible.

## Compatibility

All Rainstorm digest widths and Rainstorm-derived cryptographic outputs change.
Use an older matching release for old digests and ciphertext. The file format
does not automatically translate old Rainstorm-derived keys or authentication
tags. This is why the release uses a new major version.

## Release regression checks

Native streaming: 3,360 cases plus four published anchors. Production matches
frozen candidate A in 512 comparisons across four widths, both endian paths,
16 lengths and four seeds. All 49 native/WASM vectors pass. Upstream SMHasher3
Sanity passes for all three registrations on both endian paths. Stream-cipher
interoperability passes in both native/WASM directions. This validation also
found and fixed a JavaScript ownership bug: encryption must copy ciphertext
before freeing the WASM allocation used by subsequent HMAC calculations.
