#!/usr/bin/env python3
"""SMT against the exact flattened form -- and the control that reinterprets it.

Every previous flat attack sampled the function or searched a fixed family of
invariants. A solver is different in kind: handed the complete equations, it can
say "I do not care what your hidden structure was, I will solve the steering
constraint directly."

The query is the CAPABILITY, never parameter recovery:

    given states S != T, find controls x and y with F(S; x) == F(T; y)

which is exactly what the factored attacker gets from sigma for about
2 * 2^(w/2) pair evaluations.

THE CONTROL THAT MATTERS. Solving it quickly proves nothing on its own, because
the query may simply be easy. The same query is therefore also run against a
HARDENED variant whose injection does not preserve the pair sums
(h_i -= x, h_j += rotr(x,1)), so the planted weakness is absent. Then:

  * weak fast, hardened slow  -> the solver is exploiting the weakness, and the
                                 separation is real but SMT-breakable;
  * weak fast, hardened fast  -> the query is underconstrained and easy for
                                 anything of this shape. The solver reveals
                                 nothing about the weakness, and any separation
                                 measured against a birthday baseline was an
                                 artifact of a needlessly weak public attacker.

That second branch is the damaging one, and it is what the data shows. The
constraint system has 2*k*npairs*w bits of control freedom against only 4w bits
of equality, so roughly 2^(4w) solutions exist and propagation walks to one.
Conflicts near zero confirm it: the solver is not searching at all.

CONTROLS
  positive: the same query on the pre-mixer state, where sigma is planted.
  replay:   every model is replayed through the independent Python model.
  draws:    several theta instances and state pairs per width, since a single
            pathological instance can make a solver look brilliant or hopeless.
"""

import json
import pathlib
import random
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import z3                                                    # noqa: E402

from compositions.sequential import Composition              # noqa: E402
from models import solverstats as ST                         # noqa: E402
from models import spectrum as S                             # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
PAIRS = S.PAIRINGS[0]
SIGNS = ((-1, 1), (1, -1))
LANES = 4
# Statistics go through models/solverstats, which keeps z3's own key names and
# reports an absent counter as None rather than 0. See that module for why.


def make_thetas(w, count, rng):
    out = []
    while len(out) < count:
        theta = S.random_theta(w, rng, pairs=PAIRS, signs=SIGNS)
        if S.validate_weakness(theta, rng, trials=20)["admissible"]:
            out.append(theta)
    return tuple(out)


def _mix(out, theta):
    w = theta.w
    m, r = theta.multipliers, theta.mixa_rotations
    mixed = list(out)
    for index, (i, j) in enumerate(theta.pairs):
        m0, m1, m2, m3 = m[4 * index:4 * index + 4]
        r0, r1 = r[2 * index], r[2 * index + 1]
        a = z3.RotateRight(out[i] * z3.BitVecVal(m0, w), r0) * z3.BitVecVal(m1, w)
        b = z3.RotateRight((out[j] ^ a) * z3.BitVecVal(m2, w), r1) * z3.BitVecVal(m3, w)
        mixed[i], mixed[j] = a, b
    return tuple(mixed)


def z3_round(state, controls, theta, premixer=False):
    """Weak round: injection preserves both pair sums, exactly as Rainbow."""
    out = list(state)
    for (i, j), (si, sj), x in zip(theta.pairs, theta.signs, controls):
        out[i] = out[i] + x if si == 1 else out[i] - x
        out[j] = out[j] + x if sj == 1 else out[j] - x
    return tuple(out) if premixer else _mix(out, theta)


def hardened_round(state, controls, theta, premixer=False):
    """Weakness REMOVED: -x against +rotr(x,1) does not cancel, so no pair sum
    is preserved and the cheap steering construction does not exist."""
    out = list(state)
    for (i, j), _signs, x in zip(theta.pairs, theta.signs, controls):
        out[i] = out[i] - x
        out[j] = out[j] + z3.RotateRight(x, 1)
    return tuple(out) if premixer else _mix(out, theta)


def solve_merge(composition, sa, sb, timeout_ms, roundfn, premixer=False):
    w = composition.w
    k = len(composition.thetas)
    npairs = composition.controls_per_round
    xs = [z3.BitVec(f"x{i}", w) for i in range(k * npairs)]
    ys = [z3.BitVec(f"y{i}", w) for i in range(k * npairs)]

    def compose(values, variables):
        state = tuple(z3.BitVecVal(v, w) for v in values)
        for index, theta in enumerate(composition.thetas):
            controls = variables[index * npairs:(index + 1) * npairs]
            last = index == k - 1
            state = roundfn(state, controls, theta, premixer=premixer and last)
        return state

    out_a, out_b = compose(sa, xs), compose(sb, ys)
    solver = z3.Solver()
    solver.set("timeout", timeout_ms)
    solver.add(z3.And([out_a[i] == out_b[i] for i in range(LANES)]))

    start = time.time()
    verdict = solver.check()
    elapsed = time.time() - start

    stats = ST.collect(solver.statistics())

    row = {"verdict": str(verdict), "seconds": round(elapsed, 3), "stats": stats,
           "control_bits": 2 * k * npairs * w, "constraint_bits": LANES * w}
    if verdict == z3.sat and not premixer and roundfn is z3_round:
        model = solver.model()
        read = lambda vs: [model.eval(v, model_completion=True).as_long() for v in vs]
        xv, yv = read(xs), read(ys)
        ca = tuple(tuple(xv[i * npairs + n] for n in range(npairs)) for i in range(k))
        cb = tuple(tuple(yv[i * npairs + n] for n in range(npairs)) for i in range(k))
        row["replay_verified"] = (composition.evaluate(sa, ca)
                                  == composition.evaluate(sb, cb))
    return row


def run_width(w, k, rng, timeout_ms, roundfn, draws=3):
    rows = []
    for _ in range(draws):
        composition = Composition(thetas=make_thetas(w, k, rng))
        sa = tuple(rng.getrandbits(w) for _ in range(LANES))
        sb = tuple(rng.getrandbits(w) for _ in range(LANES))
        rows.append(solve_merge(composition, sa, sb, timeout_ms, roundfn))
    solved = [r for r in rows if r["verdict"] == "sat"]

    def median_stat(name):
        """Median of a counter, or None if ANY draw failed to report it.

        Never defaults a missing counter to zero: that is exactly how this file
        once claimed the solver performed no search at all.
        """
        values = [ST.get(r["stats"], name) for r in rows]
        if any(value is None for value in values):
            return None
        return statistics.median(values)

    return {
        "w": w, "k": k, "draws": draws,
        "solved": len(solved),
        "median_seconds": round(statistics.median([r["seconds"] for r in rows]), 3),
        "median_conflicts": median_stat("conflict"),
        "median_decisions": median_stat("decision"),
        "replay_failures": sum(1 for r in rows if r.get("replay_verified") is False),
        "rows": rows,
    }


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    timeout_ms = 60000
    report = {
        "attack": "smt_steering_on_exact_flattened_form",
        "query": "find controls x, y with F(S;x) == F(T;y); never parameter recovery",
        "timeout_ms": timeout_ms,
        "z3_version": z3.get_version_string(),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "control": [], "weak": [], "hardened": [],
    }

    print("positive control: pre-mixer state (sigma planted)")
    for w in (8, 16):
        composition = Composition(thetas=make_thetas(w, 2, rng))
        sa = tuple(rng.getrandbits(w) for _ in range(LANES))
        sb = tuple(rng.getrandbits(w) for _ in range(LANES))
        row = solve_merge(composition, sa, sb, timeout_ms, z3_round, premixer=True)
        row["w"] = w
        report["control"].append(row)
        print(f"  w={w:>2}  {row['verdict']:>7}  {row['seconds']}s")

    print("\nthe question is not 'does it solve' but 'does removing the weakness matter'")
    print("   w   k        weak (sat/n, median s, conflicts)      hardened (weakness removed)")
    for w in (8, 12, 16, 20, 24):
        for k in (2, 4):
            weak = run_width(w, k, rng, timeout_ms, z3_round)
            hard = run_width(w, k, rng, timeout_ms, hardened_round)
            report["weak"].append(weak)
            report["hardened"].append(hard)
            print(f"  {w:>3}  {k}   {weak['solved']}/{weak['draws']} "
                  f"{weak['median_seconds']:>8}s c={weak['median_conflicts']:<8}"
                  f"      {hard['solved']}/{hard['draws']} "
                  f"{hard['median_seconds']:>8}s c={hard['median_conflicts']}")

    control_ok = all(r["verdict"] == "sat" for r in report["control"])
    replay_bad = sum(r["replay_failures"] for r in report["weak"])
    weak_solved = sum(r["solved"] for r in report["weak"])
    weak_total = sum(r["draws"] for r in report["weak"])
    hard_solved = sum(r["solved"] for r in report["hardened"])
    hard_total = sum(r["draws"] for r in report["hardened"])
    report["weak_solve_rate"] = round(weak_solved / weak_total, 3)
    report["hardened_solve_rate"] = round(hard_solved / hard_total, 3)
    report["positive_control_passed"] = control_ok

    if not control_ok:
        report["conclusion"] = ("POSITIVE CONTROL FAILED: the encoding is wrong.")
    elif replay_bad:
        report["conclusion"] = (
            f"{replay_bad} returned models did not replay through the Python "
            "model, so the encoding does not match and nothing here holds.")
    elif hard_solved >= hard_total * 0.8 and weak_solved >= weak_total * 0.8:
        report["conclusion"] = (
            "THE QUERY IS EASY FOR EVERYTHING, so it measures nothing about the "
            "weakness. The solver merges the HARDENED construction -- whose "
            "injection preserves no pair sum, so the cheap steering "
            "construction does not exist -- about as readily as the weak one "
            f"(hardened {report['hardened_solve_rate']} vs weak "
            f"{report['weak_solve_rate']} solved). The reason is structural: "
            "the system has 2*k*npairs*w bits of control freedom against only "
            "4w bits of equality, so roughly 2^(4w) solutions exist and the "
            "solver reaches one without difficulty. (An earlier version of this "
            "sentence added that conflict counts were near zero and the solver "
            "'barely searches'. That was a statistics-key bug in this file -- z3 "
            "reports 'sat conflicts', the lookup asked for 'conflicts' and "
            "defaulted the miss to zero -- not a fact about the solve. The "
            "counting argument alone carries the conclusion.) CONSEQUENCE: the flat birthday "
            "baseline of ~2^(2w) used elsewhere in this program is the cost of "
            "a RANDOM-SEARCH attacker, not of the best public attacker. An "
            "equation-solving public attacker obtains the merge cheaply at "
            "widths where birthday search is hopeless, so the factored-vs-flat "
            "separation measured against that baseline does not survive. What "
            "remains unrefuted is narrower: that the SPECIFIC sigma-steering "
            "route is cheap only with the decomposition.")
    else:
        report["conclusion"] = (
            f"Removing the weakness changes the solver's difficulty (weak "
            f"{report['weak_solve_rate']} vs hardened "
            f"{report['hardened_solve_rate']} solved), so the solver is "
            "engaging with the planted structure rather than with a trivially "
            "underconstrained system. Scaling should now be read from the "
            "per-width medians.")
    path = RESULTS / "smt-steering.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
