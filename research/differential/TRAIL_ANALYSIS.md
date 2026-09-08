# Rainstorm algebra and classical differential trail plan

Status: proposed analysis program, not a security result.

This note follows the first bounded fold campaign in
[`fold-campaign-20260908/`](fold-campaign-20260908/), in which all eight matched
OG/A SMT instances exhausted their 60-second budgets and returned `unknown`.

## 1. The central difficulty

There is no single notion of difference that stays simple through every
Rainstorm operation.

For paired values `x_a` and `x_b`, define:

```
XOR difference:       delta(x) = x_a XOR x_b
additive difference:  nabla(x) = x_a - x_b  (mod 2^64)
```

XOR differences propagate exactly through XOR and rotation. Additive
differences propagate exactly through addition and subtraction. The other
operation in each representation introduces value-dependent carry, borrow, or
bit-position behavior. A useful analysis must either change representations at
carefully modeled boundaries or carry enough bit-level conditions to connect
them.

The second difficulty is dependence. The counter accumulates transformed state
words, the same data block is reused for four rounds, and state words feed later
operations. Multiplying local modular-addition probabilities is only a search
heuristic unless the relevant independence assumptions have been justified.

### Minimal worked experiment: multiplication by five

Use 8-bit words and

```
f(x) = 5*x mod 256 = x + (x << 2) mod 256.
```

For an XOR differential, enumerate every base `x`, pair it with `x XOR 1`, and
count `f(x) XOR f(x XOR 1)`. The exact distribution is:

| Output XOR difference | Count | Probability |
| ---: | ---: | ---: |
| `0x05` | 128 | 1/2 |
| `0x0d` | 64 | 1/4 |
| `0x1d` | 32 | 1/8 |
| `0x3d` | 16 | 1/16 |
| `0x7d` | 8 | 1/32 |
| `0xfd` | 8 | 1/32 |

For an additive differential, pair `x` with `x + 1`. Then

```
f(x + 1) - f(x) = 5 mod 256
```

for all 256 bases. This probability-one additive trail coexists with a
nontrivial XOR distribution.

There is also a compact dependence lesson. In the expression `x + (x << 2)`,
the addition operands are related. If they were incorrectly treated as
independent operands having XOR differences `0x01` and `0x04`, standard xdp+
gives output difference `0x05` probability 1/4. The real multiplication gives
probability 1/2. A correct local addition table can therefore produce an
incorrect full-function estimate when its input distribution is wrong.

Reproduce both distributions with:

```sh
python3 research/differential/toy_multiply_differential.py \
  --bits 8 --shift 2 --input-difference 1 --mode xor \
  --compare-independent
```

## 2. Exact algebra of one right round

All equations are in `R = Z/(2^64 Z)`. Let `rho_i` be rotate-right by `Z[i]`,
let `d_i` be data word `i`, and let `C_R` be the right-round counter constant.
Write the incoming halves as `L_i` and `H_i`.

Set:

```
c_0 = C_R
q_0 = H_0
q_i = H_i - c_i                         for i = 1,...,7
y_i = rho_i((q_i XOR d_i) - K_i)
c_(i+1) = c_i + y_i
u_i = L_i XOR y_i
```

The counter chain means that a difference entering data word zero can affect
every later transformed high word through `c_i`, even when data words 1--7 are
fixed.

For OG, the round output is:

```
L'_i = u_i                               for i = 0,...,7
H'_0 = y_0 - c_8 = -C_R - sum(y_1,...,y_7)
H'_i = y_i                               for i = 1,...,7
```

The cancellation of `y_0` in `H'_0` is the proved 64-bit state loss.

For candidate A / Rainstorm 4.0.0, the output is:

```
L'_0 = u_0 - c_8
L'_i = u_i                               for i = 1,...,7
H'_i = y_i                               for i = 0,...,7
```

All eight `y_i` remain visible and the round is invertible for a fixed block.
That local invertibility does not establish collision resistance of the folded,
truncated full hash.

## 3. Exact algebra of one left round

Let `C_L` be the left-round counter constant. Set:

```
c_0 = C_L
p_0 = L_0
p_i = L_i - c_i                         for i = 1,...,7
x_i = rho_i((p_i XOR d_i) - K_i)
c_(i+1) = c_i + x_i
```

The output is:

```
L'_i = x_i                               for i = 0,...,7
H'_0 = (H_0 XOR x_0) - c_8
H'_i = H_i XOR x_i                       for i = 1,...,7
```

The lower output prefix `0..j` depends only on the incoming lower prefix and
data prefix `0..j`. This triangular structure explains why equal fold prefixes
remain equal through the left-only final rounds.

## 4. Fold algebra

The fold is:

```
F_i = L_i - H_i.
```

For two messages, exact fold equality is equivalent to each of:

```
L_a[i] - H_a[i] = L_b[i] - H_b[i]
L_a[i] - L_b[i] = H_a[i] - H_b[i]
L_a[i] + H_b[i] = L_b[i] + H_a[i]
```

All equalities are modulo `2^64`. The last line is a cross-sum. The incorrect
same-side sum `L_a + L_b = H_a + H_b` does not follow.

The additive condition is exact, but additive differences do not rotate or pass
through XOR cleanly. That is why the fold equation is a useful endpoint and not
by itself a full differential trail.

## 5. What the bounded SMT query really asks

With eight symbolic prefix bytes, only message word `d_0` varies. All other
message words are zero. For variant `V`, define the deterministic bounded map:

```
Phi_(V,k): {0,1}^64 -> {0,1}^(64k)
```

where `Phi_(V,k)(x)` is the first `k` fold words reached from the prescribed IV
by the message `(x,0,...,0)` followed by the real padding block.

The two-copy SMT query asks whether `Phi_(V,k)` is non-injective:

```
exists a != b: Phi_(V,k)(a) = Phi_(V,k)(b).
```

For `k=1`, domain and codomain both have 64 bits. A collision exists exactly
when this component map is not a permutation. A random 64-to-64-bit mapping is
overwhelmingly likely to have collisions, but the current SMT encoding may
still be a poor collision-finding algorithm.

For `k=2`, a random mapping has about one half expected colliding pair over the
entire bounded domain. For `k=4` and `k=8`, random-map collisions in this
64-bit domain are negligibly likely. An `unsat` result would prove injectivity
only for the exact bounded map; a timeout proves nothing.

## 6. Classical XOR differential definitions

For modular addition `z = x + y`, define its XOR differential probability:

```
xdp_plus(alpha, beta -> gamma)
  = Pr[((x XOR alpha) + (y XOR beta)) XOR (x + y) = gamma].
```

Define `xdp_minus` analogously for `x - y`. These probabilities can be
computed with carry/borrow automata rather than a full `2^(3w)` difference
table. Lipmaa and Moriai give efficient algorithms for differential properties
of addition modulo powers of two:

<https://eprint.iacr.org/2001/001>

Under XOR differences:

- XOR and fixed rotations have probability-one transitions.
- Subtraction of a constant has a value-dependent output difference.
- Counter addition and the subsequent word subtraction are nonlinear
  transitions with two varying, correlated operands.
- The final fold is another modular subtraction; a collision trail requests
  zero output difference on selected words.

A characteristic fixes every intermediate difference. A differential fixes
only endpoints and sums the probabilities of all compatible characteristics.
Finding one good characteristic is not automatically the same as estimating
the full differential effect.

## 7. Proposed trail-search program

### Phase A: trace and primitive validation

1. Add an exact paired execution trace at every primitive boundary: pre-XOR,
   post-XOR, post-constant-subtraction, post-rotation, counter update, target
   subtraction, round boundary, and fold.
2. Implement and test exact `xdp_plus` and `xdp_minus` carry automata.
3. Exhaustively validate them for word sizes 4, 8, and 12 before using 64-bit
   words.
4. Validate reduced-word Rainstorm-like rounds exhaustively. Toy-word results
   validate tooling only and do not transfer as security claims.

### Phase B: reduced-round reconnaissance

Search OG and A separately through:

1. one right weak round;
2. right then left;
3. three and four message-block rounds;
4. progressively more padding-block rounds;
5. the fold and then the output final rounds.

At each depth, record the best weight found:

```
trail weight W = -log2(product of local transition probabilities).
```

Because Rainstorm is not automatically a Markov construction, call this a
ranking score until concrete experiments validate it.

Biryukov and Velichkov describe partial difference tables and Matsui-style
branch-and-bound searches for ARX trails:

<https://eprint.iacr.org/2013/853.pdf>

### Phase C: input-difference families

Start with declared families rather than allowing the tool to silently choose
anything:

- every one-bit XOR difference in `d_0`;
- weight-two and weight-three masks in `d_0`, prioritized around rotation
  boundaries and carry chains;
- additive differences `+/- 2^b` and short runs of set bits;
- one active word among `d_0,...,d_7`;
- two active message words chosen to cancel at a later counter or fold step.

For every candidate, record both XOR and additive descriptions. Two masks that
look similar in one representation may behave very differently in the other.

### Phase D: search targets

Search for more than exact full collisions:

- zero XOR difference in fold word zero;
- zero prefixes of 2, 4, and 8 fold words;
- low-Hamming-weight fold and digest differences;
- unusually likely exact output differences;
- impossible local or reduced-round transitions;
- iterative or self-canceling patterns across right/left round pairs;
- OG-only trails that use the canceled `y_0` term;
- trails surviving A, which indicate structure unrelated to the repaired wrap.

### Phase E: dependency-safe validation

For each proposed trail:

1. Fix the input difference and use SMT to find one compatible base message.
   This uses one symbolic message, rather than two unconstrained messages.
2. Include intermediate difference constraints in the SMT instance.
3. Replay every satisfying pair through the independent arithmetic model and
   native C++.
4. Sample many uniform base messages with the fixed difference and measure the
   endpoint differential probability.
5. Compare measured probability with the predicted local-weight product.
6. If they disagree, preserve the counterexample and refine the dependency
   model rather than reporting the product as an attack probability.

The fixed-key/fixed-constant dependence issue is important. General ARX
branch-and-bound methods often state optimality under Markov or independent
round-key assumptions; Rainstorm has neither independent secret round keys nor
fresh message words in every round:

<https://eprint.iacr.org/2016/409.pdf>

### Phase F: message modification

If a trail has useful probability but several early carry conditions, determine
whether free message words can be chosen to force those conditions. This is
different from merely sampling pairs. It turns probabilistic early transitions
into construction work and leaves only later conditions probabilistic.

Message modification was central to practical differential collision work on
MD-family hashes, but it must be re-derived for Rainstorm's equations rather
than imported by analogy:

<https://iacr.org/archive/eurocrypt2005/34940001/34940001.pdf>

## 8. What would count as interesting

For an `n`-bit full digest, generic collision work is about `2^(n/2)`. A fixed
input-difference trail producing a collision with probability `p` costs about
`1/p` chosen pairs before message-modification gains. It beats generic birthday
work only when roughly:

```
p > 2^(-n/2).
```

For Rainstorm-64, a collision trail of probability `2^-40` would be a
distinguisher relative to the random fixed-difference probability `2^-64`, but
it would not beat the `2^32` generic birthday collision cost. The same trail
logic must always be compared against the correct generic goal.

For a `t`-bit zero prefix, the random reference probability is `2^-t`. A useful
result reports the measured probability, uncertainty interval, input-difference
family, and total data/time/memory cost, not only a trail diagram.

## 9. What SMHasher3 does not settle

Rainstorm 4.0.0 passed the pinned 256-bit SMHasher3 collection, but SMHasher3 is
not a proof system or an enumerator of chosen differential trails. It also does
not instantiate this repository's 512-bit output. Its broad empirical tests can
miss:

- a rare event whose probability is far below the test's sample resolution;
- an adversarial input difference not selected by the suite;
- a multi-round characteristic requiring correlated carries;
- message modification that forces internal conditions;
- a truncated or internal-state event not represented by the suite's output
  statistic.

The local differential screen used 4,096 pairs for each selected case. An event
of probability `2^-20` has only about a 0.39 percent chance of appearing even
once in 4,096 trials. A trail search can identify one such event first, after
which a targeted experiment can allocate millions of trials to that exact
difference and endpoint.

Passing broad statistics and finding no high-probability trail are useful but
different pieces of evidence. Neither alone establishes collision resistance.

## 10. Proposed implementation artifacts

Keep the first implementation modular and auditable:

```
rainstorm_model.py     exact production-v4 model and checkpoints
trail_trace.py       exact paired primitive trace
profile_trails.py    empirical fixed-difference checkpoint profile
smt_programmed.py    exact first-right-round algebraic parameterization
xdp.py               carry/borrow differential probabilities
search_trails.py     threshold or branch-and-bound search
smt_digest.py        bounded actual-digest collision model
trail_smt.py         fixed-difference trail compatibility model
validate_trail.py    native probability measurement and confidence bounds
test_trails.py       exhaustive toy-word and native equivalence tests
```

Every result JSON should include variant, rounds, word size, input difference,
all intermediate differences, predicted weight, measured probability and
confidence interval, trials, seed, source hashes, solver/tool versions, and
native replay data.

## 11. Learning priorities

The most valuable concepts to master are:

1. the distinction between XOR and additive differences;
2. bit-level carry/borrow propagation in modular addition;
3. a characteristic versus the sum of trails forming a differential;
4. dependence assumptions behind multiplying local probabilities;
5. message modification and sufficient bit conditions;
6. generic attack baselines and honest data/time/memory accounting;
7. strict separation of internal, reduced-round, truncated, and full-hash
   claims.

The deepest practical skill is learning to distrust a clean probability until
the conditions that make its factors independent have been written down and
tested.
