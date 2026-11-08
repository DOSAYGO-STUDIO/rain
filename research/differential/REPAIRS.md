# Repair alternatives and walkthrough

These alternatives were proposed against the frozen pre-v4 reference. A was
subsequently promoted as Rainstorm 4.0.0 after passing the full 256-bit native
SMHasher3 campaign (253/253 checks). B also passed that campaign. See
[release validation](../../results/rainstorm-4.0.0/README.md).
The accompanying analysis proves local properties, not full-hash security.

## What happened, in a small example

Imagine a right round with just three high words. Call the values produced by
the rotations `a,b,c`. The counter ends as `C+a+b+c`. The last operation wraps
back to the first high word and subtracts that counter:

```
[a,b,c] -> [a-(C+a+b+c), b, c] -> [-C-b-c, b, c]
```

The first result no longer contains `a`. The actual algorithm does exactly
this with eight words and arithmetic modulo `2^64`.

There is a copy of `a` in the low half, because the round XORs it into a low
word. That prevents this observation from immediately giving collisions
between two messages starting at the same state. But for arbitrary incoming
states, the previous low word is also unknown: changing it compensates for
changing `a`. The remaining high input words can compensate for the changed
counter. That is why the exact statement is a `2^64`-member collision family
on **incoming states**, with a fixed block, rather than a full-message attack.

This distinction matters. Deliberate compression in a hash is normal, and the
source already describes a noninvertible-state objective. Noninvertibility
is not the surprise by itself. The precise algebraic cancellation, constant
high-half sum, and trivially constructible internal collision family are the
structures we can now identify and target. A 960-bit image does not on its
own undermine the generic security goals of a 256- or 512-bit digest.

There is a separate finalization issue. The extra rounds always process the
left half. The first output word is therefore just one 64-bit value passed
through the same reversible function repeatedly. Increasing that round count
does not make the first word incorporate the other low words or any high
words after the fold. The fixed cross-size relation follows from that fact.

## Option A: route the wraparound subtraction into the other half

In the right branch only, replace

```cpp
h[(k & 7) + 8] -= ctr;
```

with

```cpp
h[i == 15 ? 0 : i + 1] -= ctr;
```

The first seven targets remain high words 9 through 15. The last target
becomes low word 0, completing a ring across all sixteen words. This mirrors
the left round's boundary crossing into high word 0.

**What can be proved:** the repaired right round is a permutation for every
fixed block. Its output high words retain all `y[0..7]`. Compute their sum
and the final counter; undo the last subtraction on low word zero; undo each
low XOR; then reconstruct the high inputs using the equations in the main
report. Every step is uniquely reversible. The original left round is also
invertible because its transformed low words are all retained; undo the high
updates using those words, then reconstruct low inputs in order.

This removes the particular `2^64` collision family and high-half sum
constraint. It also introduces a high-to-low boundary update in the right
round. It does **not** repair left-only finalization or prove an adequate
round count. This is my preferred local repair to investigate: it makes the
boundary behavior symmetric and its inverse is straightforward to audit.

## Option B: retain the target, change the final counter coefficient

In the right branch only, keep the first seven subtractions unchanged and use

```cpp
h[(k & 7) + 8] -= (i == 15 ? (ctr << 1) : ctr);
```

Unsigned shifts here implement multiplication by two modulo `2^64`.
The final high word zero becomes

```
out[8] = y[0] - 2*(C+y[0]+sum(y[1..7]))
       = -y[0] - 2*(C+sum(y[1..7])).
```

**What can be proved:** it is now uniquely reversible:

```
y[0] = -out[8] - 2*(C+sum(out[9..15])).
```

Once `y[0]` is recovered, invert the rest as before. More generally, a final
coefficient `c` gives coefficient `1-c` on `y[0]`; unique recovery requires
`c` even, so `1-c` is odd and invertible modulo `2^64`.

This is a smaller structural change than A, but keeps the same directional
layout and leaves the finalization problem intact. Bit shifts may introduce
unhelpful differential behavior, so the algebra is only an invertibility
argument. **Merely switching subtraction to addition is insufficient:** it
makes the coefficient of `y[0]` equal two and leaves a two-to-one round map.
That is one reason to prove candidate repairs before optimizing them.

## Option C: a new Rainstorm version addressing both findings

Use A or B for the right round, and redesign finalization and domain
separation together:

1. Replace the left-only final schedule with a fixed even number of
   alternating left/right rounds shared by every digest size. For example,
   an experimental schedule can start with right and then alternate; the
   number of rounds must be chosen from cryptanalysis, not from this example.
2. Encode a version tag and requested output size into a distinct,
   unambiguous domain prefix, together with the seed and message length,
   before processing message blocks. Write down the exact encoding before
   implementation; do not hide it in ad hoc seed arithmetic.
3. Retain explicit unambiguous padding, and specify output extraction from
   the resulting common full-state transformation.

The structural reason to alternate is that a right round reads and transforms
the high half and writes the low half. The proof of high-half independence
for repeated left rounds then no longer applies. This alone does not prove
full avalanche, eliminate other relations, or determine a security margin.
Domain separation removes the premise of the demonstrated cross-size
`f_t^r(x)` relation: the variants no longer begin with the same folded state.

An alternative output API could deliberately use one XOF-style stream with
consistent truncation, accepting explicit prefix relationships between
sizes. That is a different, valid interface goal; independence across sizes
is not universally required. The present relation is noteworthy because it
arises from isolated 64-bit processing rather than a documented XOF design.

C is the more complete research direction. It is also a new hash design,
with new vectors, compatibility consequences, performance costs, and an
unknown security margin. More elaborate is not automatically more secure.

## Option D: keep Rain as research, use an established hash for security

For a security-facing API, implement the hash over the **original message**
using an established construction through a maintained implementation.
[NIST FIPS 202](https://csrc.nist.gov/pubs/fips/202/final) specifies SHA3-256
and SHA3-512, among others. A performance-oriented alternative to assess is
[BLAKE3, using its designers' specification](https://github.com/BLAKE3-team/BLAKE3-specs)
and official implementation; its stated 128-bit security target should not
be confused with a higher target merely because more output bytes are
requested.

This replaces the need to establish Rainstorm's cryptographic security while
leaving Rainbow/Rainstorm available for research and appropriate non-security
uses. It does not preserve existing digests. Benchmark the actual workload
before choosing on performance grounds.

Hashing a Rainstorm digest with SHA-3 does **not** repair collisions already
created by Rainstorm: equal inner digests remain equal. The established hash
must process the original message if that is the security foundation.

The executable round models in [check_repairs.py](check_repairs.py) match the
original native right round on 1,000 random inputs and check both directions
of the proposed A/B inverses on 1,000 inputs each; results are in
[repair-checks.json](repair-checks.json). These checks support the algebraic
proofs above and are not full-hash implementations or statistical acceptance
tests.

## Comparison

| Proposal | Right-round collapse | Final one-way dependency | Compatibility | What is proved |
| --- | --- | --- | --- | --- |
| A: cross-half wrap | Removed | Remains | New digests | Fixed-block round bijectivity |
| B: even coefficient | Removed | Remains | New digests | Fixed-block round bijectivity |
| C: A/B + final schedule + domains | Removed | Current structural cause removed | New algorithm/version | Local bijectivity; old proofs of defects no longer apply |
| D: established full-message hash | Rainstorm bypassed | Rainstorm bypassed | New algorithm/API choice | Relies on that construction's published analysis |

## Required validation before accepting a candidate

For every concrete implementation of A, B, or C:

- Record the exact source revision and run native inverse/witness regression
  tests, known-answer vectors, and streaming equivalence with sanitizers.
- Run this differential suite with declared probability budgets, including
  expanded input masks, block boundaries, all output sizes, and multiple
  fixed public seeds. Search reduced-round trails and full-state reachability
  separately; these are currently missing from the suite.
- Register the exact candidate source in Frank J. T. Wojcik's full
  [SMHasher3 from GitLab](https://gitlab.com/fwojcik/smhasher3), regenerate its
  verification constants, and run its complete listed test collection with
  extended tests. Include BadSeeds and other tests not included by `All`.
  Record tool revision, candidate digest, command line, all failures, and
  performance. Do not label a smoke test or `All` alone as the full collection.
- Compare with the unchanged baseline on the same machine. Investigate
  failures and account for multiple comparisons rather than changing
  constants until a test happens to pass.

No production candidate was applied during this analysis, so full SMHasher3
acceptance results for repairs remain a required next step, not a claimed
result of this report.
