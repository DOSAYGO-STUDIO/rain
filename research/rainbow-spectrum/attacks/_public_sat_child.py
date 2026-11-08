#!/usr/bin/env python3
"""One public-only attack draw, in its own process.

The attack path touches the PublicArtifact and nothing else. theta is used in
exactly two places, both outside the attack: to compile the artifact in the
first place, and to verify afterwards that a returned witness is genuine. If the
solver's answer could not be checked against the factored implementation there
would be no way to tell a real witness from a decoding bug, and this project has
already shipped one result that was an encoding artifact.

The budget is a CONFLICT budget, not a clock. timeout-validity.json showed one
deterministic instance recorded as solved in 127.5s, solved in 385.1s and
censored at >900s purely from machine load, so wall time cannot decide which
draws are censored. A conflict budget is deterministic: the same instance is
censored or not censored regardless of what else the machine is doing.
"""

import json
import pathlib
import random
import resource
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))


def words_from_bits(bits, count, width):
    return tuple(sum(bits[i * width + b] << b for b in range(width))
                 for i in range(count))


def main():
    w, t = int(sys.argv[1]), int(sys.argv[2])
    hardened = sys.argv[3] == "1"
    draw = int(sys.argv[4])
    solver_name = sys.argv[5]
    budget = int(sys.argv[6])

    from pysat.solvers import Solver
    from models import public_artifact as PA, cnf as C
    from experiment_b import plant, evaluate, privileged_solve

    rng = random.Random(8800 + 97 * draw + w)
    challenge = plant(w, 2, t, rng, hardened)
    thetas = challenge["thetas"]                      # compile + verify only
    artifact = PA.build(thetas, challenge["S"], challenge["T"],
                        challenge["merge_a"], t, hardened)

    out = {"w": w, "t": t, "hardened": hardened, "draw": draw,
           "solver": solver_name, "budget": budget}

    # ---- the attack: public artifact in, witness out. No theta on this path.
    started = time.time()
    clauses, var_of_input, stats = C.build(artifact, seed=draw, shuffle=True)
    out["cnf"] = stats
    try:
        with Solver(name=solver_name, bootstrap_with=clauses) as solver:
            solver.conf_budget(budget)
            verdict = solver.solve_limited(expect_interrupt=False)
            model = solver.get_model() if verdict else None
            accum = solver.accum_stats()
    except Exception as error:
        out.update(status=f"error:{type(error).__name__}",
                   detail=str(error)[:200], conflicts=None, event=None)
        print(json.dumps(out))
        return 0
    elapsed = time.time() - started

    conflicts = accum.get("conflicts")
    out["decisions"] = accum.get("decisions")
    out["propagations"] = accum.get("propagations")
    out["conflicts"] = conflicts
    out["seconds"] = round(elapsed, 2)
    # verdict is True (sat), False (unsat) or None (budget exhausted)
    out["status"] = {True: "sat", False: "unsat", None: "budget"}[verdict]
    out["event"] = verdict is True

    # ---- verification against the factored implementation (ground truth)
    if model:
        values = C.decode(model, artifact, var_of_input)
        npairs, k = artifact.meta["npairs"], artifact.meta["k"]
        prefix_a = tuple(words_from_bits(values[f"pa{i}"], npairs, t)
                         for i in range(k - 1))
        prefix_b = tuple(words_from_bits(values[f"pb{i}"], npairs, t)
                         for i in range(k - 1))
        merge_b = words_from_bits(values["mb"], npairs, w)
        left = evaluate(thetas, challenge["S"], prefix_a,
                        challenge["merge_a"], hardened)
        right = evaluate(thetas, challenge["T"], prefix_b, merge_b, hardened)
        out["witness_verified"] = (left == right)
        out["witness"] = {"prefix_a": [list(x) for x in prefix_a],
                          "prefix_b": [list(x) for x in prefix_b],
                          "merge_b": list(merge_b)}
        # Cross-check that the artifact agrees with the factored map too.
        out["artifact_agrees"] = (
            artifact.eval_side("a", **values) == left
            and artifact.eval_side("b", **values) == right)

    # ---- the privileged route on the SAME instance, for the comparison
    privileged = privileged_solve(challenge, t, hardened)
    out["privileged_solved"] = bool(privileged.get("solved"))
    out["privileged_evaluations"] = privileged.get("evaluations")

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out["peak_rss_mb"] = round(peak / (1048576 if sys.platform == "darwin"
                                       else 1024), 1)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
