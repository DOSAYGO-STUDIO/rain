#!/usr/bin/env python3
"""One public SAT draw against a genuine artifact with k rounds."""
import json, pathlib, random, sys, time
HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1])); sys.path.insert(0, str(HERE.parent))

def main():
    w, t, k, draw, solver_name, budget = (int(sys.argv[1]), int(sys.argv[2]),
        int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6]))
    from pysat.solvers import Solver
    from models import public_artifact as PA, cnf as C
    from experiment_b import plant
    rng = random.Random(8800 + 97 * draw + w + 7919 * k)
    challenge = plant(w, k, t, rng, False)
    artifact = PA.build(challenge["thetas"], challenge["S"], challenge["T"],
                        challenge["merge_a"], t, False)
    clauses, var_of_input, stats = C.build(artifact, seed=draw, shuffle=True)
    started = time.time()
    with Solver(name=solver_name, bootstrap_with=clauses) as s:
        s.conf_budget(budget)
        verdict = s.solve_limited(expect_interrupt=False)
        accum = s.accum_stats()
    out = {"w": w, "t": t, "k": k, "draw": draw, "cnf": stats,
           "conflicts": accum.get("conflicts"), "seconds": round(time.time()-started, 2),
           "status": {True: "sat", False: "unsat", None: "budget"}[verdict],
           "event": verdict is True,
           "free_bits": 2 * (k - 1) * len(challenge["thetas"][0].pairs) * t
                        + len(challenge["thetas"][0].pairs) * w}
    print(json.dumps(out))
    return 0

if __name__ == "__main__":
    sys.exit(main())
