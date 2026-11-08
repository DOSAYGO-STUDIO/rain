# Rainbow / Rainstorm differential red-team analysis

**Historical baseline:** this analysis concerns the pre-v4 sources now frozen
in `reference/src/`. Candidate A was promoted to production in v4.0.0 after
its full 256-bit native SMHasher3 run passed 253/253 checks. See
[release validation](../../results/rainstorm-4.0.0/README.md). The original
witness and candidate-generation tools continue to use that frozen baseline.

Analysis date: 2026-09-07. Production source at commit
`b73a43239e7fb0f516bc17e757d3a09cbb63f0da`; both core files label themselves
3.7.1. JSON artifacts record source SHA-256 hashes. No hash implementation was
changed during that initial analysis. This is not a security certification.

The main findings are an exact 64-bit state loss in Rainstorm's right round,
limited diffusion in its final rounds, and related first words across output
sizes. We have **not found a collision between distinct messages for a full
hash**, nor proved collision/preimage resistance. Rainbow is already described
by this repository as noncryptographic.

Concrete repair alternatives and a walkthrough are in [REPAIRS.md](REPAIRS.md).
The downloaded full statistical suite and exact-source adapter are documented
in [SMHASHER3.md](SMHASHER3.md).

## Run the suite

Requires Python 3.9+ and a C++17 compiler (`CXX`, default `c++`), on a
little-endian host. No Python packages required. Compiled libraries live in a
temporary directory. The bridge includes the frozen pre-v4 C++ files;
full hashes are not Python reimplementations.

```sh
python3 research/differential/test_suite.py
python3 research/differential/suite.py selftest --output /tmp/witness.json
python3 research/differential/suite.py scan --output /tmp/scan.json
python3 research/differential/suite.py exhaustive --algorithm rainstorm --domain-bits 8
python3 research/differential/suite.py plan --family-size 224 --p-min 0.01 --alpha 0.01
```

`suite.py` deliberately retains the frozen pre-v4 implementation used by the
historical OG analysis. To run the same endpoint scanner against the actual
v4.0.0 production source, use its separate batch bridge:

```sh
python3 research/differential/scan_production.py --bits 256 \
  --lengths 16 64 65 128 --all-bits --samples 65536 \
  --p-min 0.001 --output /tmp/rainstorm-v4-differential.json
```

The result records SHA-256 fingerprints of the production source, common
header, bridge, and statistical scanner. Keeping the bridge separate prevents
production upgrades from silently changing the preserved OG experiments.
The completed 2026-09-08 production campaign and its raw JSON reports are in
[`rainstorm-v4-diff-20260908/`](rainstorm-v4-diff-20260908/README.md).

## Internal trail and bounded digest tools

`rainstorm_model.py` is an exact production-v4 integer model with checkpoints
after every round, lane, or individual operation. `trail_trace.py` compares one
paired execution under XOR, additive, or wordwise rotation-XOR input relations:

```sh
python3 research/differential/trail_trace.py \
  --length 8 --bits 64 --relation xor --difference 1 \
  --trace-level round --output /tmp/rainstorm-trace.json
```

The first bounded actual-digest target is two distinct 8-byte messages colliding
under Rainstorm-64. This domain has 64 controllable input bits, one four-round
tail schedule, a fold, and no post-fold rounds:

```sh
python3 research/differential/smt_digest.py \
  --message-length 8 --bits 64 --backend sat --timeout 60 \
  --output /tmp/rainstorm-short-64.json
```

The `sat` backend explicitly bit-blasts before using Z3's SAT engine; `smt`
retains the ordinary bit-vector solver. A SAT result is replayed through the
native production C++ implementation. UNSAT applies only to the exact declared
message domain, and `unknown` is inconclusive.

`--reference-message-hex` changes the query to a chosen second-preimage search,
and `--backend sls` selects Z3's quantifier-free bit-vector local search.
`--rounds 1..3` builds a marked reduced-round Rainstorm-64 experiment;
production uses four rounds.

The stronger algebraic formulation programs the transformed words of the first
right round and recovers the corresponding data words exactly:

```sh
python3 research/differential/smt_programmed.py \
  --rounds 4 --free-tail-outputs 8 --backend sat --timeout 60 \
  --output /tmp/rainstorm-programmed-r4.json
```

It targets a 63-byte Rainstorm-64 chosen second preimage. The final byte of its
64-byte data block is constrained to the real `0xbf` padding byte. Fixing a
prefix of the programmed first-round outputs with `--free-tail-outputs` gives a
message-modification-style slice that preserves the reference's early path.
The completed calibration and bounded runs are recorded in
[`short-digest-20260908/`](short-digest-20260908/README.md).

The same campaign includes a native-verified generic Rainstorm-64 collision
control. Build and reproduce the distinguished-point search with:

```sh
c++ -std=c++17 -O3 -march=native \
  research/differential/rho64.cpp -o /tmp/rain-rho64
/tmp/rain-rho64 search 12000000000 16 64 20260908
```

The recorded pair required 7.23 billion walk evaluations, an ordinary result
under the ideal 64-bit birthday model. It is a full 64-bit collision but not a
subgeneric break. Any claimed Rainstorm-64 collision attack must compare its
complete cost with the roughly `2^32` generic baseline.

For empirical reconnaissance before constraint search, profile the selected
difference representation at every round boundary:

```sh
python3 research/differential/profile_trails.py \
  --length 8 --bits 64 --relation xor --difference 1 \
  --samples 4096 --output /tmp/rainstorm-profile-xor-1.json
```

For `--relation rx`, each message word is paired as
`ROTL(message_word, rotation) XOR difference_word`, and internal/output
differences use the same rotation-XOR representation. These profiles are
reconnaissance, not corrected probability claims; candidates must be fixed and
validated in a separately budgeted run.

For a minimal two-input multiplication example, treat the input as two
unsigned `w`-bit operands and pair it with fixed operand XOR differences:

```sh
python3 research/differential/toy_product_differential.py \
  --operand-bits 8 --delta-p 0 --delta-q 1 --product full \
  --mode exhaustive --output /tmp/product-full.json
```

This computes `F(P || Q) = P*Q`, compares it with
`F((P XOR delta_p) || (Q XOR delta_q))`, and collects the complete output-XOR
histogram, individual bit biases, Hamming weights, zero differences, and
pairwise bit statistics for small outputs. `--product low` instead retains only
the low `w` product bits. Exhaustive mode is deliberately limited to `w <= 10`;
sample mode supports widths through 64 bits.

The pairing relation and output comparison can be changed independently. This
version exposes multiplication's natural additive algebra:

```sh
python3 research/differential/toy_product_differential.py \
  --operand-bits 8 --delta-p 0 --delta-q 1 --product low \
  --input-relation add --output-relation subtract \
  --mode exhaustive --output /tmp/product-additive.json
```

In that experiment, `Q' = Q + 1 mod 2^w` and the measured output difference is
`P*Q' - P*Q mod 2^w = P`. Since uniform `P` makes that difference itself
uniform, endpoint bit statistics look ideal even though the input/output
relation is deterministic. This is a compact warning that a uniform difference
histogram does not exclude conditional or algebraic structure. Negative
additive arguments express subtraction, for example `--delta-q=-1`.

Integer division is not folded into the same histogram interface. Division by
zero is undefined, and modular division modulo `2^w` exists only for odd
divisors. A scaling experiment such as `Q' = c*Q` is better checked directly
through the algebraic invariant `F(P,Q') = c*F(P,Q)` than treated as though its
ratios had the uniform bit-vector baseline used by XOR/additive differences.

A larger, explicitly finite search, including every one-bit input difference:

```sh
python3 research/differential/suite.py scan --algorithm rainstorm --bits 256 \
  --lengths 16 64 65 128 --all-bits --samples 65536 --output /tmp/large.json
```

`--masks 8000000000000001` adds a multi-bit XOR difference expressed as an
integer (bit 0 is the low bit of message byte 0). It must fit each selected
length. `--hash-seed 0xffffffffffffffff` changes the fixed public hash seed.
Default samples use OS randomness; `--replay-seed 123` permits deterministic
replay but does not provide a literal IID sampling guarantee. Every run checks
published vectors and algebraic witnesses first. Scan reports successful
execution even if it finds deviations: inspect `projection_alerts`,
`collisions`, and `collision_witness`. Statistical discoveries require follow-up.

Defaults cover 7 output variants, message lengths 1, 15, 16, 17, 63, 64, 65,
and selected low/high/middle bit differences, all with public seed zero.
The suite currently does not search reduced-round hash variants, related
seeds, differing message lengths, additive/rotational message differences,
chosen-prefix paths, or message modification. It does exercise isolated
production rounds in its structural checks. Those omitted search spaces are
not covered by any claim below.

## Proved: Rainstorm right round is exactly 2^64-to-1

All arithmetic here is modulo `2^64`. Fix the data words `d[0..7]`.
Let `y[i]` be the newly rotated high word at iteration `i` of
`weakfunc(h, d, false)`, and let `C = CTR_RIGHT`.

After processing iterations 0 through 6, their counter subtractions modify
the next high word. The last iteration wraps and subtracts the accumulated
counter from high word zero. Consequently the output is

```
out[0..7] = initial_low[i] XOR y[i]
out[8]    = y[0] - (C + y[0] + ... + y[7])
          = -C - y[1] - ... - y[7]
out[9..15] = y[1..7]
```

Thus **sum(out[8..15]) = -C** always: a 64-bit exact constraint independent
of the input or block. An unconstrained uniform 1024-bit state satisfies this
predicate with probability `2^-64`.

The result is stronger than an upper bound on the image. For any desired low
output words `L[i]` and high output words `y[1..7]`, choose `y[0]` freely.
The following uniquely reconstructs an input:

```
initial_low[i] = L[i] XOR y[i]
initial_high[0] = (ROTL(y[0], Z[0]) + K[0]) XOR d[0]
initial_high[i] = ((ROTL(y[i], Z[i]) + K[i]) XOR d[i])
                  + C + sum(y[0..i-1])                  # i = 1..7
```

There are exactly `2^64` choices, all distinct, and all give the same output.
The image has exactly `2^960` elements. `right_preimage` constructs these
inputs and `selftest` checks 256 distinct collision pairs against the native
round. A concrete pair and its common output are in [witness.json](witness.json).

This is a chosen-internal-state collision family. Its input differences depend
on the state/data; it is **not** a single fixed-XOR message differential of
probability one. The round also has simple fixed-XOR differentials of
probability one: changing only an inactive low word changes only that output
low word by the same XOR mask. The tests exercise one such differential.

The production schedule starts with the right round (`i & 1` is initially
false), then left, right, left. For a fixed block its full state map therefore
has image size at most `2^960`. The constructed collision pairs also remain
collisions through all four rounds of that fixed-block transform: once the
first right round produces equal states, subsequent identical operations
cannot separate them. This is still a collision obtained by choosing two
different incoming states, not by hashing two messages under the fixed IV.
Do not subtract another 64 bits merely because
another right round occurs: loss of independence prevents that inference.
Nor does a 960-bit image establish a shortcut against a 512-bit digest. The
construction above varies the incoming state; reachability of both states
from the prescribed IV through actual messages remains an unsolved attack
step. Fixed-state message injection into this one right round is injective:
the low outputs recover all `y[i]`, which successively recover the data words.

## Proved: final left rounds have only forward diffusion

In `weakfunc(..., true)`, low word zero is transformed independently; low word
one depends on words zero and one; and so on. The last counter subtraction
targets `h[8]`, not `h[0]`. No high word is read to compute a low word.
Inductively, **any number of left-only rounds leaves the low half independent
of the incoming high half**. More strongly, low output prefix `0..j` depends
only on the incoming low prefix `0..j` and data prefix `0..j`.

Rainstorm does subtract high from low before these final rounds, so the high
half has already influenced the output. The structural limitation is that adding more of
these particular final rounds adds no subsequent backward or high-to-low
diffusion. Discarding the high half after it has already contributed can be
an intentional and reasonable design choice; this limitation alone is not
a security failure. Differences injected solely in the high half *after* the fold
produce a zero output difference with certainty. This is an internal-state
statement, not an established way to create such differences with messages.

For a fixed last padded data word `t`, define the 64-bit permutation

```
f_t(x) = ROTR((x XOR t) - P, 17)
f_t^-1(y) = (ROTL(y, 17) + P) XOR t
```

If `x` is the first word after the low-minus-high fold (`h[0] -= h[8]`), then the first digest words are exactly:

| Variant | First word |
| --- | --- |
| Rainstorm-64 | x |
| Rainstorm-128 | f_t^2(x) |
| Rainstorm-256 | f_t^4(x) |
| Rainstorm-512 | f_t^8(x) |

For lengths divisible by 64, `t = 0x8080808080808080`, publicly fixed.
Consequently, on that domain, anyone can convert the first word of any variant
into the first word of any other without knowing the message. This gives an
exact cross-variant relation, incompatible with independent random oracles
for the different sizes. It does not by itself distinguish one fixed-size
hash from a random function or give a full-digest collision.

## Proved: Rainbow mixers are permutations, not one-way functions

Every multiplier is odd, hence has a unique inverse modulo `2^64`.
Rotations are bijections. In `mixA`, recover original `a` by inverting its
two multiplications and rotation; recover original `b` by inverting its
transform and XORing the *transformed* `a`. Similarly recover `c,d`.
In `mixB`, the returned third word gives the transformed original second
word, which first allows recovery of the old second and then the old third.
`unmix` implements these inverses and verifies round trips against C++.

Thus every fixed-message block transform is a permutation of the 256-bit
state (word additions/subtractions and the word permutation are also
bijective). There can be no fixed-block collision between distinct incoming
states. This does not imply that different messages cannot collide, or that
output inversion is hard. Permutation-based cryptographic designs exist;
invertibility alone is not a vulnerability.

Primality is unnecessary for the modular inverses: oddness suffices. Also,
multiplication by an odd constant fixes zero, so it cannot have a full-length
cycle on all words. The README's residue/cycle rationale should not be
interpreted as a cryptographic security argument.

## Exactly what “bounded probability of finding any differential” means

A differential is not inherently a flaw: every pair defines one. Fix a
message length, hash seed, output size, nonzero XOR input difference `a`, and
uniform input message `X`. Define

```
p[a,b] = Pr[H(X) XOR H(X XOR a) = b].
```

Here `D` counts all chosen (algorithm, size, length, input difference) cases.
Samples are independent, with replacement, and the budget is fixed before
looking at the results. The formulas concern these distributions, not a
random-key average and not the product of guessed per-round probabilities.

**Observing heavy differentials.** For any fixed output difference with mass
at least `p_min`, the probability of never observing it in `N` pairs is at
most `(1-p_min)^N`. Each distribution contains at most `1/p_min` such bins.
A union bound therefore gives

```
Pr[any differential of mass >= p_min remains unobserved]
    <= min(1, (D/p_min) * (1-p_min)^N).

N >= ceil(log(D/(alpha*p_min)) / -log(1-p_min))
```

suffices for miss probability at most `alpha`, even though the output
differences are not specified in advance. This means *observe a pair in each
heavy bin*. It does not mean certify which bins are heavy or demonstrate a
cryptographic distinguisher. `plan` reports this discovery budget. Small
cryptographic probabilities make it infeasible; for example a threshold near
`2^-128` still requires work on the order of `2^128` times logarithmic factors.

**Simultaneous estimation, including unobserved bins.** Hoeffding's bound for
a Bernoulli count is `Pr[|p_hat-p| > e] <= 2 exp(-2 N e^2)`.
For a `b`-bit digest, allocating error `alpha_e/D` to its `2^b` bins gives

```
e_exact = sqrt((log(2D/alpha_e) + b*log(2))/(2N)).
```

The intervals `[max(0,p_hat-e), min(1,p_hat+e)]` hold simultaneously over
**all** output differences in every scanned case, including bins selected
after observing the data and bins never seen. Thus `max_exact_probability_upper`
is a valid, usually loose upper bound on the largest exact differential mass.
The implementation does not pretend that a frequent discovery selected from
many bins has an unadjusted binomial significance level.

**Truncated differences.** The suite also counts every single output bit and
every output byte value. With `T` such events, the simultaneous radius is
`sqrt(log(2T/alpha_t)/(2N))`. A projection alert means its interval excludes
`1/2` (bit) or `1/256` (byte). This is a deviation from that ideal frequency,
not automatically an attack. Correlations among tests do not invalidate the
union bound. These tests do not cover all multi-bit output masks.

For an actual detection guarantee, if a tested projection has true absolute
bias greater than `2*e` from its reference probability, then it will trigger
an alert whenever the simultaneous confidence event holds. Thus a sufficient
budget for detecting any tested bias of at least `delta` with the allocated
confidence is `N > 2*log(2T/alpha_t)/delta^2`. Likewise, certifying an exact
bin above a threshold needs a probability gap greater than twice its
all-bin estimation radius; merely observing that bin is not certification.

**Zero observed collisions.** For the prespecified event `b=0`, if there are
zero hits, the exact one-sided bound is

```
p_collision <= 1 - (alpha_c/D)^(1/N).
```

The `zero_collision_upper` field applies **only when the collision count is
zero**. Scan uses `alpha_e = alpha_t = alpha_c = alpha/3`, so the three
families of inference together have error probability at most `alpha`.
The discovery miss bound is a separate prospective statement, not another
confidence interval to add to this coverage claim.

The binomial inversion is the zero-success case of
[NIST's exact binomial confidence construction](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).
For additional context, [Lipmaa–Moriai](https://eprint.iacr.org/2001/001)
give exact differential methods for modular addition, and
[the fixed-key differential analysis discussion by its author](https://www.esat.kuleuven.be/cosic/blog/crypto-2022-differential-cryptanalysis-in-the-fixed-key-model/)
explains why chaining round probabilities needs care. This suite makes no
Markov/independent-round assumption.

**No universal efficient guarantee.** Arbitrary lengths and differences form
an unbounded search space. Even after imposing finite bounds, a rare path
might lie in an untested difference or require an infeasible number of
samples. An unrestricted promise to find every exploitable differential is
not provided here. Repeated campaigns, adaptive mask selection, and optional
stopping need new error budgets or separate validation data.

**Exhaustive mode** removes sampling error only on the specified finite domain:
all messages with the low `k` bits varying, other bits zero, and every nonzero
XOR difference confined to those bits. It evaluates the actual full hash,
then enumerates the exact differential distribution for each difference and
reports its maximum and collision count. Work is quadratic in `2^k`; this
implementation deliberately caps `k` at 10. A result on this domain is not a
proof over arbitrary 64-bit words or full-length messages.

## Results from this run

[baseline.json](baseline.json) contains 224 cases, 4,096 sampled pairs per case,
917,504 total pairs (1,835,008 full-hash evaluations), with zero full-digest
collisions. For lengths greater than one byte there were no bit/byte projection
alerts; the largest observed bit bias was 0.033203125. The simultaneous
projection radius was approximately 0.05016, so this run has limited power
against small biases.

The 773 projection alerts all occur in the one-byte domain. A fixed nonzero
XOR difference partitions its 256 messages into only 128 unordered pairs.
Even a random function's fixed table can have substantial bit imbalance on
such a small domain; repeatedly sampling it estimates that imbalance more
precisely. These alerts are not evidence of a cryptographic weakness.

[exhaustive-rainbow-8.json](exhaustive-rainbow-8.json) and
[exhaustive-rainstorm-8.json](exhaustive-rainstorm-8.json) enumerate every
one-byte message and all 255 nonzero differences for each 256-bit hash.
There are no message collisions. Every difference's largest exact count is
2/256: the unavoidable pair symmetry `(x,x XOR a)` and `(x XOR a,x)`.
No two distinct unordered pairs share an output difference for a fixed input
difference in these tiny domains.

The baseline zero-collision bound is about **0.00271005 per selected input
difference**, simultaneously across the family with its allocated error.
That is vastly larger than cryptographic target probabilities. The all-bin
Hoeffding radii range from about 0.08281 (64-bit digest) to 0.21157 (512-bit
digest). Passing this run is not remotely a proof of cryptographic strength.

## Implications and remaining attack work

The exact right-round constraint and final-round dependency structure deserve
attention before any security claim. Simply increasing the count of the
current left-only final rounds preserves the latter dependency structure. Alternating final
round direction would change that structure, but is a new design requiring
analysis and would still include the right-round state collapse. No suggested
change here comes with a security proof.

The next substantive cryptanalytic step is to solve message reachability into
the collision family, or find trails through the actual right/left schedule
with controlled carries. SAT/SMT or constraint search could help with bounded
instances, but a timeout is not an impossibility proof, and toy-word proofs do
not automatically transfer to these 64-bit algorithms. Neither an avalanche
pass nor a collection of invertible/noninvertible components establishes
collision resistance, preimage resistance, pseudorandomness, or safe MAC/KDF
use. Those remain unproved.

### Bounded SMT fold experiment

`smt_fold.py` makes the proposed fold search reproducible with exact Z3
64-bit bit-vectors.  It models two distinct 64-byte messages from the real,
length-keyed IV, processes each message block, then processes their identical
`0x80` padding blocks.  The constraint on word `i` is the additive condition

```
L_a[i] - H_a[i] = L_b[i] - H_b[i]  (mod 2^64),
```

not equality of XOR differences.  Both OG and A are selectable.  Only a
prefix of each message is symbolic so every run describes a precise bounded
instance; `unknown` (normally a timeout) is explicitly inconclusive.  A SAT
witness for word zero is replayed through the integer model and independently
through the corresponding native C++ 64-bit hash.

This is best described as an **SMT-assisted algebraic collision search** (or,
more broadly, an additive differential search), not yet as a probabilistic
differential-characteristic analysis.  The solver chooses both messages and
therefore also chooses their input difference.  It does not prescribe a trail
through each round or estimate the probability of its carry transitions.  If
multiple witnesses exhibit a repeatable input difference and intermediate
state trail, fixing that difference and measuring its probability would be a
separate follow-up experiment.

The equivalent difference condition is

```
L_a[i] - L_b[i] = H_a[i] - H_b[i]  (mod 2^64).
```

Both sides use the same `a minus b` orientation: the additive change in the
low word must equal the additive change in the corresponding high word.  The
fold then subtracts those changes and makes the output difference zero.  An
equivalent sum form is the *cross-sum*

```
L_a[i] + H_b[i] = L_b[i] + H_a[i]  (mod 2^64),
```

not `L_a[i] + L_b[i] = H_a[i] + H_b[i]`.  This follows from ordinary group
algebra; modular wraparound changes how negative values are represented, not
the sign rules.

Here “word” means one 64-bit state word, not a 64-byte message block.  Matching
one folded word is a truncated fold collision and, for word zero, a complete
Rainstorm-64 collision.  Matching words 0--1, 0--3, or 0--7 targets the 128-,
256-, or 512-bit outputs respectively because the common final data and the
left-round triangular dependency preserve an equal low-state prefix.  The
current script independently checks native C++ only for the 64-bit word-zero
case; any wider result must also be replayed through the corresponding native
full-hash output before making a collision claim.

Install the optional solver and run, for example:

```sh
python3 -m pip install z3-solver
python3 research/differential/smt_fold.py --variant A \
  --symbolic-bytes 8 --words 0 --timeout 60 --output /tmp/fold-a.json
```

Add word indexes after `--words` to move from a one-word truncated collision
toward the complete eight-word fold.  More constraints or a larger symbolic
prefix can be materially harder; a timeout establishes no probability bound
and no security result.  The JSON report includes Z3's `unknown_reason` when
available.  Preserve that report along with solver version, timeout, symbolic
byte count, word targets, variant, and machine details.  In particular, OG
returning SAT while A returns `unknown` is not evidence by itself that OG is
weaker: controlled comparisons need identical bounds, repeated runs, native
replay, and a comparison with generic collision-search work.
