#!/usr/bin/env python3
"""Experiment B: one-sided planted sparse-witness recovery.

The counting model killed the symmetric task analytically: whenever the
privileged route is feasible, the public relation already has >= 2^(2w)
solutions, because a sigma-match still leaves x, y free. Fixing ONE side's merge
controls removes exactly that degeneracy -- each sigma-match then contributes a
single solution -- which is the only regime worth spending compute in.

CHALLENGE GENERATION (no search, and no witness left behind)
  1. draw the factors; fix side A's merge controls canonically to zero;
  2. sample a witness: prefix_A, prefix_B, merge_B;
  3. run A forward to its final state;
  4. INVERT B's rounds from that state to derive the second start state T, so
     the sampled controls are guaranteed to be a witness -- no searching, and it
     works for the hardened variant too, which is why the control survives here;
  5. verify the witness forward;
  6. DISCARD the witness before any solver runs.

SOLVERS
  privileged  gets the factorization but NOT the witness. It must rediscover a
              witness via sigma: two independent w-bit halves, matched
              separately, so ~2^(w/2+1) work -- not 2^w, because mixA is
              pair-separable and word p drives pair p alone.
  public      gets only the exact flattened relation and the public states, and
              is asked for ANY witness -- not the planted one, not the factors.

THE CONTROL IS THE POINT. Everything here is built from reversible machinery, so
recovering B's controls from a fixed target may be plain backward propagation
regardless of Rainbow's weakness. The hardened variant -- injection that
preserves no pair sum -- is what distinguishes "the solver exploits the
weakness" from "this relation is easy for everyone", which is the trap the
previous SMT experiment fell into.

A result is meaningful in either direction:
  both easy      -> dead branch, the relation is easy for another reason;
  nobody solves  -> overconstrained, back off c;
  weak-privileged cheap while weak-public and both hardened are hard
                 -> the first toy demonstration of the phenomenon (NOT a
                    finished construction).
"""

import json
import math
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import z3                                                    # noqa: E402

from models import rainbow as R                              # noqa: E402
from models import solverstats as ST                         # noqa: E402
from models import spectrum as S                             # noqa: E402
from models import wordops as W                              # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
PAIRS = S.PAIRINGS[0]
SIGNS = ((-1, 1), (1, -1))
LANES = 4


def make_thetas(w, count, rng):
    out = []
    while len(out) < count:
        theta = S.random_theta(w, rng, pairs=PAIRS, signs=SIGNS)
        if S.validate_weakness(theta, rng, trials=20)["admissible"]:
            out.append(theta)
    return tuple(out)


# ------------------------------------------------------------- exact inverses
def mix_inv(state, theta):
    """Inverse of mixA; every step is a bijection so this is exact."""
    w = theta.w
    m, r = theta.multipliers, theta.mixa_rotations
    out = list(state)
    for index, (i, j) in enumerate(theta.pairs):
        m0, m1, m2, m3 = m[4 * index:4 * index + 4]
        r0, r1 = r[2 * index], r[2 * index + 1]
        a, b = state[i], state[j]
        hi = W.mul(W.rotl(W.mul(a, W.inv_odd(m1, w), w), r0, w), W.inv_odd(m0, w), w)
        q = W.rotl(W.mul(b, W.inv_odd(m3, w), w), r1, w)
        hj = W.xor(W.mul(q, W.inv_odd(m2, w), w), a, w)
        out[i], out[j] = hi, hj
    return tuple(out)


def inject_weak(state, controls, theta):
    return R.inject(state, controls, theta)


def inject_weak_inv(state, controls, theta):
    w = theta.w
    out = list(state)
    for (i, j), (si, sj), x in zip(theta.pairs, theta.signs, controls):
        out[i] = W.add(out[i], -si * x, w)
        out[j] = W.add(out[j], -sj * x, w)
    return tuple(out)


def inject_hard(state, controls, theta):
    """Weakness removed: -x against +rotr(x,1) preserves no pair sum."""
    w = theta.w
    out = list(state)
    for (i, j), _s, x in zip(theta.pairs, theta.signs, controls):
        out[i] = W.sub(out[i], x, w)
        out[j] = W.add(out[j], W.rotr(x, 1, w), w)
    return tuple(out)


def inject_hard_inv(state, controls, theta):
    w = theta.w
    out = list(state)
    for (i, j), _s, x in zip(theta.pairs, theta.signs, controls):
        out[i] = W.add(out[i], x, w)
        out[j] = W.sub(out[j], W.rotr(x, 1, w), w)
    return tuple(out)


def round_fwd(state, controls, theta, hardened):
    inject = inject_hard if hardened else inject_weak
    return R.mix_a(inject(state, controls, theta), theta)


def round_inv(state, controls, theta, hardened):
    inverse = inject_hard_inv if hardened else inject_weak_inv
    return inverse(mix_inv(state, theta), controls, theta)


# --------------------------------------------------------- challenge planting
def plant(w, k, t, rng, hardened):
    thetas = make_thetas(w, k, rng)
    npairs = len(thetas[0].pairs)
    start = tuple(rng.getrandbits(w) for _ in range(LANES))

    prefix_a = tuple(tuple(rng.getrandbits(t) for _ in range(npairs))
                     for _ in range(k - 1))
    prefix_b = tuple(tuple(rng.getrandbits(t) for _ in range(npairs))
                     for _ in range(k - 1))
    merge_a = (0,) * npairs
    merge_b = tuple(rng.getrandbits(w) for _ in range(npairs))

    state = start
    for index in range(k - 1):
        state = round_fwd(state, prefix_a[index], thetas[index], hardened)
    final = round_fwd(state, merge_a, thetas[-1], hardened)

    # Invert B's rounds from the same final state to derive T.
    back = round_inv(final, merge_b, thetas[-1], hardened)
    for index in range(k - 2, -1, -1):
        back = round_inv(back, prefix_b[index], thetas[index], hardened)
    target = back

    witness = {"prefix_a": prefix_a, "prefix_b": prefix_b, "merge_b": merge_b}
    ok = evaluate(thetas, target, prefix_b, merge_b, hardened) == final
    return {"thetas": thetas, "S": start, "T": target, "final": final,
            "merge_a": merge_a, "witness_valid": ok, "_witness": witness}


def evaluate(thetas, state, prefix, merge, hardened):
    for index, controls in enumerate(prefix):
        state = round_fwd(state, controls, thetas[index], hardened)
    return round_fwd(state, merge, thetas[-1], hardened)


# --------------------------------------------------------- privileged solver
def privileged_solve(challenge, t, hardened):
    """Rediscover a witness from the factorization, without the planted one.

    Weak only: match each sigma half independently over 2^t candidates per side,
    then the merge controls are forced. Cost ~2^(w/2+1), not 2^w.
    """
    thetas = challenge["thetas"]
    w = thetas[0].w
    npairs = len(thetas[0].pairs)
    last = thetas[-1]
    evaluations = 0

    tables = {}
    for side, state in (("a", challenge["S"]), ("b", challenge["T"])):
        for pair_index in range(npairs):
            book = {}
            for value in range(1 << t):
                controls = [0] * npairs
                controls[pair_index] = value
                moved = round_fwd(state, tuple(controls), thetas[0], hardened)
                evaluations += 1
                book.setdefault(R.invariants(moved, last)[pair_index], value)
            tables[(side, pair_index)] = book

    chosen_a, chosen_b = [0] * npairs, [0] * npairs
    for pair_index in range(npairs):
        book_a = tables[("a", pair_index)]
        book_b = tables[("b", pair_index)]
        shared = set(book_a) & set(book_b)
        if not shared:
            return {"solved": False, "evaluations": evaluations,
                    "reason": f"no sigma match on pair {pair_index}"}
        key = next(iter(shared))
        chosen_a[pair_index] = book_a[key]
        chosen_b[pair_index] = book_b[key]

    a = round_fwd(challenge["S"], tuple(chosen_a), thetas[0], hardened)
    b = round_fwd(challenge["T"], tuple(chosen_b), thetas[0], hardened)
    inject = inject_hard if hardened else inject_weak
    a = inject(a, challenge["merge_a"], last)

    # Forced merge controls for side B. inject(b, x) must equal a, so for pair
    # (i, j) carrying sign si on lane i we need b_i + si*x = a_i, hence
    # x = si*(a_i - b_i), using that si is +/-1 and so is its own inverse.
    merge_b = []
    for (i, _j), (si, _sj) in zip(last.pairs, last.signs):
        delta = W.sub(a[i], b[i], w)
        merge_b.append(delta if si == 1 else W.sub(0, delta, w))
    merge_b = tuple(merge_b)

    got = evaluate(thetas, challenge["T"], (tuple(chosen_b),), merge_b, hardened)
    want = evaluate(thetas, challenge["S"], (tuple(chosen_a),),
                    challenge["merge_a"], hardened)
    return {"solved": got == want, "evaluations": evaluations,
            "log2_evaluations": round(math.log2(max(1, evaluations)), 2),
            "predicted_log2": round(w / 2 + 1, 2)}


# ------------------------------------------------------------- public solver
def public_solve(challenge, t, hardened, timeout_ms):
    thetas = challenge["thetas"]
    w = thetas[0].w
    k = len(thetas)
    npairs = len(thetas[0].pairs)

    def zmix(state, theta):
        m, r = theta.multipliers, theta.mixa_rotations
        out = list(state)
        for index, (i, j) in enumerate(theta.pairs):
            m0, m1, m2, m3 = m[4 * index:4 * index + 4]
            r0, r1 = r[2 * index], r[2 * index + 1]
            a = z3.RotateRight(state[i] * z3.BitVecVal(m0, w), r0) * z3.BitVecVal(m1, w)
            b = z3.RotateRight((state[j] ^ a) * z3.BitVecVal(m2, w), r1) * z3.BitVecVal(m3, w)
            out[i], out[j] = a, b
        return tuple(out)

    def zround(state, controls, theta):
        out = list(state)
        for (i, j), (si, sj), x in zip(theta.pairs, theta.signs, controls):
            if hardened:
                out[i] = out[i] - x
                out[j] = out[j] + z3.RotateRight(x, 1)
            else:
                out[i] = out[i] + x if si == 1 else out[i] - x
                out[j] = out[j] + x if sj == 1 else out[j] - x
        return zmix(out, theta)

    solver = z3.Solver()
    solver.set("timeout", timeout_ms)

    pa = [[z3.BitVec(f"pa{i}_{n}", w) for n in range(npairs)] for i in range(k - 1)]
    pb = [[z3.BitVec(f"pb{i}_{n}", w) for n in range(npairs)] for i in range(k - 1)]
    mb = [z3.BitVec(f"mb{n}", w) for n in range(npairs)]

    # The restriction is public: prefix words carry only t bits.
    limit = z3.BitVecVal((1 << t) - 1, w)
    for row in pa + pb:
        for v in row:
            solver.add(z3.ULE(v, limit))

    state = tuple(z3.BitVecVal(v, w) for v in challenge["S"])
    for index in range(k - 1):
        state = zround(state, pa[index], thetas[index])
    out_a = zround(state, [z3.BitVecVal(0, w)] * npairs, thetas[-1])

    state = tuple(z3.BitVecVal(v, w) for v in challenge["T"])
    for index in range(k - 1):
        state = zround(state, pb[index], thetas[index])
    out_b = zround(state, mb, thetas[-1])

    solver.add(z3.And([out_a[i] == out_b[i] for i in range(LANES)]))

    start = time.time()
    verdict = solver.check()
    elapsed = time.time() - start

    stats = ST.collect(solver.statistics())

    row = {"verdict": str(verdict), "seconds": round(elapsed, 3), "stats": stats}
    if verdict == z3.sat:
        model = solver.model()
        rd = lambda v: model.eval(v, model_completion=True).as_long()
        prefix_b = tuple(tuple(rd(v) for v in row_) for row_ in pb)
        prefix_a = tuple(tuple(rd(v) for v in row_) for row_ in pa)
        merge_b = tuple(rd(v) for v in mb)
        left = evaluate(thetas, challenge["S"], prefix_a,
                        challenge["merge_a"], hardened)
        right = evaluate(thetas, challenge["T"], prefix_b, merge_b, hardened)
        row["replay_verified"] = left == right
    return row


# ------------------------------------------------------------ exhaustive count
def exhaustive_solutions(challenge, t, hardened):
    """Count every witness, to confirm the relation really is sparse."""
    thetas = challenge["thetas"]
    w = thetas[0].w
    npairs = len(thetas[0].pairs)
    k = len(thetas)
    if k != 2:
        return None
    total = 0
    for a0 in range(1 << t):
        for a1 in range(1 << t):
            left = evaluate(thetas, challenge["S"], ((a0, a1),),
                            challenge["merge_a"], hardened)
            for b0 in range(1 << t):
                for b1 in range(1 << t):
                    for x in range(1 << w):
                        for y in range(1 << w):
                            if evaluate(thetas, challenge["T"], ((b0, b1),),
                                        (x, y), hardened) == left:
                                total += 1
    return total


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    timeout_ms = 60000
    report = {"experiment": "B_planted_sparse_witness",
              "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "z3": z3.get_version_string(), "rows": [], "counts": []}

    print("sparsity check: does fixing one side remove the 2^(2w) degeneracy?")
    for w, c in ((4, 0), (4, 1)):
        t = w // 2 + c
        for hardened in (False, True):
            challenge = plant(w, 2, t, rng, hardened)
            count = exhaustive_solutions(challenge, t, hardened)
            predicted = 1 << (4 * c)
            row = {"w": w, "c": c, "t": t,
                   "hardened": hardened, "solutions": count,
                   "predicted": predicted, "witness_valid": challenge["witness_valid"]}
            report["counts"].append(row)
            print(f"  w={w} c={c} t={t} {'hardened' if hardened else 'weak    '}"
                  f"  solutions={count}  predicted~{predicted}"
                  f"  witness_ok={challenge['witness_valid']}")

    print("\nwitness recovery: privileged (factors) vs public (flat form only)")
    print("   w  c  variant     privileged            public")
    for w in (8, 12, 16, 20):
        for c in (0, 1):
            t = w // 2 + c
            for hardened in (False, True):
                challenge = plant(w, 2, t, rng, hardened)
                priv = privileged_solve(challenge, t, hardened)
                pub = public_solve(challenge, t, hardened, timeout_ms)
                row = {"w": w, "c": c, "t": t, "hardened": hardened,
                       "witness_valid": challenge["witness_valid"],
                       "privileged": priv, "public": pub}
                report["rows"].append(row)
                label = "hardened" if hardened else "weak    "
                pstate = (f"solved 2^{priv.get('log2_evaluations')}"
                          if priv.get("solved") else f"FAILED ({priv.get('reason','')})")
                print(f"  {w:>3}  {c}  {label}   {pstate:<20}  "
                      f"{pub['verdict']:>7} {pub['seconds']:>7}s  "
                      f"confl={ST.show(pub['stats'], 'conflict'):<7} "
                      f"dec={ST.show(pub['stats'], 'decision'):<7} "
                      f"prop={ST.show(pub['stats'], 'propagation')}"
                      + ("" if pub.get("replay_verified") is not False else "  REPLAY FAILED"))

    path = RESULTS / "experiment-b.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
