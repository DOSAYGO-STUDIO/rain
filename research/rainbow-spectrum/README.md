# Rainbow spectrum: does factored knowledge beat flat knowledge?

Research program investigating whether Rainbow's collision-steering weakness can
become a structural primitive: individually steerable factors composed into a
flat map whose steering is no longer cheaply accessible, while knowledge of the
factorization still permits cheap steering.

**Status: the phenomenon is not disproved at toy scale, and a scaling separation
is measured. That is not the same as a positive result** — the flat side has so
far survived only two attacks. See [Limitations](#limitations).

Prerequisite: the underlying weakness is the pair-sum collapse documented in
[`../rainbow/`](../rainbow/).

## What is being measured

Both solvers get the same task: given states `S` and `T`, find control sequences
with `F(S; x) == F(T; y)`.

- **Factored** knows every θ and may use intermediate states.
- **Flat** gets only the input/output behaviour of `F`.

Costs are in **round-equivalents** so they are comparable: one flat evaluation of
`F` costs `k` rounds, one factored pair-map costs half a round.

## Results

### Phase 1 — the weakness, exhaustively verified

All checks pass (`results/phase1-verification.json`):

- the w=64 model reproduces production Rainbow, anchored to the independently
  verified implementation in `../rainbow/`;
- fixed-control transitions are permutations (exhaustive, w=3..8 per pair; full
  4-lane state at w=3,4 for both mixers);
- injection preserves both pair invariants (exhaustive at w=3,4);
- **merge iff invariants agree**, both directions: at w=4, all 4096 agreeing
  state pairs merged and **0 of 61440** differing pairs did;
- `steer()` merges for every free choice, and one pair has exactly 2^w solutions;
- the birthday construction tracks theory over nine widths:

| w | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 22 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| log2 median evals | 4.39 | 5.32 | 6.19 | 7.63 | 8.43 | 9.18 | 10.45 | 11.35 | 12.18 |
| analytic `w/2+0.235` | 4.24 | 5.24 | 6.24 | 7.24 | 8.24 | 9.24 | 10.24 | 11.24 | 12.24 |

### k=1 — no separation

A flat attacker who can isolate the injection recovers an equivalent steering
capability in **3 evaluations, independent of w**, and agrees with ground-truth
mergeability 500/500 (`results/flat-invariant-probe.json`). Any separation must
therefore come from composition.

Caveat: this gives the attacker `inject` on its own. In a genuinely flattened map
they would have to invert the mixer, so this is a *weaker* threat model than the
program specifies. It is a bound on where not to look, not a proof about k=1.

### Separation under composition

Aligned pairing across factors (`results/milestone-separation.json`):

| w | factored | flat | separation |
|---|---|---|---|
| 3 | 2^2.6 | 2^7.7 | 2^5.1 |
| 4 | 2^3.4 | 2^9.9 | 2^6.4 |
| 5 | 2^3.4 | 2^11.8 | 2^8.3 |
| 6 | 2^4.0 | 2^13.6 | 2^9.6 |
| 7 | 2^4.3 | 2^15.7 | 2^11.5 |
| 8 | 2^4.6 | 2^16.9 | 2^12.3 |

Factored tracks `2^(w/2)`, flat tracks `2^(2w)` (at w=8, k=2 the prediction is
2^17 and the measurement is 2^16.9), and the gap grows as roughly `2^(1.5w)`.
This is a scaling separation, not a constant factor.

**Composition depth is not a separation axis.** `k` barely moves either side: the
factored attacker merges at round 2 and coasts, and the flat birthday is on the
final state regardless of `k`. Width is the axis that matters.

### Rotating the pairing is a candidate defence

The divide-and-conquer needs consecutive factors to agree on the pairing. If each
factor rotates its pairing, the merge-round invariant mixes lanes from different
round-1 pairs and the two conditions must be matched **jointly**:

| regime | divide-and-conquer available | factored cost |
|---|---|---|
| aligned | 20/20 | ~2^(w/2) |
| rotated | 0/20 | ~2^w (w=7 → 2^7.4, w=8 k=3 → 2^9.2) |

Rows where the rotated regime still shows 20/20 are the ~1/3 of draws where two
random pairings coincide; their costs fall back to the aligned figure, which
confirms the mechanism. This is also a candidate defence for Rainbow itself.

### Phase 7 — attacking the hypothesis

Both attacks fail (`results/flat-adversarial.json`):

- **A, GF(2)-linear invariant of the output.** Classes enumerated exactly, and
  candidates validated on held-out classes. Every candidate died: w=3 gave 4
  candidates → 1 validated → **0 discriminating**; w=4 gave 2 → 0; w=5,6,8 gave
  none. The lone w=3 survivor is constant on *every* class, so it is a constant
  of the map, not a class label.
- **B, class canonicalisation.** Correct but dominated: 2^7.0 vs generic 2^7 at
  w=3, and 2^13.2 vs 2^9 at w=4, because each label costs a full class
  enumeration.

**Positive control:** the same test on the pre-mixer coset consistently finds 5–7
GF(2)-linear invariants — the low bits of the pair sums, which genuinely are
GF(2)-linear. The test detects structure when structure exists, so the negative
on outputs is meaningful rather than a broken measurement.

## Limitations

The honest verdict is "not yet disproved", not "secure".

1. Only two flat attacks have been run. **Untried:** Z/2^w-linear functional
   search (the invariant is Z/2^w-linear, not GF(2)-linear, so this is the most
   likely to bite), ANF/algebraic elimination, SAT/SMT, meet-in-the-middle, and
   amortised precomputation (a one-off 2^(4w) class partition makes every later
   merge free, which is a real threat model).
2. The separation is the *same* phenomenon as the Rainbow break itself —
   birthday on a w-bit invariant versus birthday on a 4w-bit state. It has not
   been shown to be a new primitive.
3. Toy widths only. At w≤8 a flat attacker could brute-force structure that would
   be out of reach asymptotically, so these sizes identify scaling laws; they do
   not establish hardness.
4. Phase 4 exact flattening (truth table / ANF / CNF with intermediate variables
   eliminated) is **not** implemented. The flat solver currently gets
   input/output access, not a flattened representation.
5. Composition branches B (algebraic) and C (cross-parameterized) are not built.

## Failure taxonomy

Kept deliberately, per the program:

| failure | cause | lesson |
|---|---|---|
| factored solver merged 0/20 | `mix_a` was hardcoded to lanes (0,1),(2,3) while `random_theta` drew other pairings, so injection and the mixer disagreed | separability must be defined against θ's own pairing |
| `validate_weakness` admitted those members | it only tested properties of *injection*, never that the weakness survives the mixer | admissibility must test per-pair independence **through a round** |
| factored matched the wrong functional | invariants computed with round 1's θ, but `steer` tests the merge round's θ | the invariant that matters belongs to the round where the merge happens |
| Attack A "succeeded" at w=3..6 | last-round controls drawn randomly *with replacement*, so ~40 distinct points of 64 faked a rank deficiency | enumerate classes exactly; validate on held-out data |
| flat cost was an artifact | the birthday ran the whole budget on side A before sampling side B | two-sided interleaved search, stop at first cross-match |
| merge-iff row looked catastrophic | duplicate JSON key `of_which_merged` silently overwrote the agreeing count | never reuse a key in a result record |

## Layout and reproduction

```
models/      wordops.py (exact width-w arithmetic), rainbow.py (Theta, mixers,
             steer), spectrum.py (parameterized family + admissibility)
compositions/sequential.py (F = R_k o ... o R_1, reachable sets)
attacks/     phase1_verify.py, flat_invariant_probe.py,
             milestone_separation.py, flat_adversarial.py
results/     machine-readable JSON for every run
```

```bash
cd research/rainbow-spectrum
python3 attacks/phase1_verify.py          # ~16 s, exhaustive
python3 attacks/flat_invariant_probe.py   # instant
python3 attacks/milestone_separation.py   # ~45 s
python3 attacks/flat_adversarial.py       # ~3 s
```

All runs are seeded (`random.Random(20260915)`) and write JSON to `results/`.
Nothing here modifies Rainbow; `models/rainbow.py` carries its own transcription
and is anchored to production at w=64 by `selftest_matches_production`.
