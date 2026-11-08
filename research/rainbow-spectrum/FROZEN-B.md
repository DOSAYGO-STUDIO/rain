# Experiment B — FROZEN

**Tag:** `experiment-b-frozen` · **Frozen:** 2026-09-16

This construction is frozen. It is not to be modified while it is attacked.
Anything that changes it is a new construction with a new name.

## What is frozen

The composition in `attacks/experiment_b.py` (`plant`, `round_fwd`,
`inject_weak`, `inject_hard`, `make_thetas`) and its public form in
`models/aig.py`, `models/public_artifact.py`, `models/cnf.py`.

- 4 lanes of w bits, 2 pairs, k = 2 rounds
- round = pair-sum-preserving injection, then pair-separable `mix_a`
- prefix controls restricted to t = w/2 bits; side A's merge fixed to zero
- public object: bit-level AIG, θ compiled to gates and deleted

## The security game

A **hidden collision-steering relation**:

| algorithm | input | output |
|---|---|---|
| `KeyGen(w)` | width | public artifact `P`, secret factorization `sk` |
| `Eval(P, x)` | artifact, inputs | output state — public |
| `Witness(sk, P)` | secret, artifact | `(prefix_A, prefix_B, merge_B)` — private |
| `Verify(P, x)` | artifact, candidate | accept iff side A = side B — public |

The adversary receives `P` only and **wins by producing any witness `Verify`
accepts**, at cost asymptotically competitive with `Witness`. It need not
recover `sk`.

## Status at freeze

| | weak | hardened |
|---|---|---|
| flat, best public attack | 2^0.761w | 2^0.700w |
| factored | 2^0.500w exactly | no shortcut (0/70) |

- public attacks: SAT on shuffled CNF ×3 independent solvers (0.761–0.824),
  meet-in-the-middle (1.400)
- **known leak:** the pairing, in 15 public evaluations
- negative control: no solver's weak−hardened interval excludes zero

**Kill criterion:** any public algorithm reaching O(2^(w/2)) — or asymptotically
competitive — kills B as a trapdoor candidate.

This is a toy candidate separation, not security.

## Challenges

`challenges/` holds public artifacts at w = 8…20 with `index.json`. The
`target_evaluations_to_beat` is the privileged cost, 4·2^(w/2).
`challenges/secret/` holds scoring data only (no θ).

**Caution for red-teamers:** `attacks/emit_challenge.py` contains the generation
seeds, from which θ is regenerable. An independent attacker must be given
`challenges/` without the `attacks/` directory.
