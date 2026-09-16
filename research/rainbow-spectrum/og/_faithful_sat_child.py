#!/usr/bin/env python3
"""One public SAT draw against the FAITHFUL B artifact."""
import json, pathlib, random, sys, time
HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "attacks"))

def main():
    w, t, draw, solver_name, budget = (int(sys.argv[1]), int(sys.argv[2]),
        int(sys.argv[3]), sys.argv[4], int(sys.argv[5]))
    suffix = sys.argv[6] if len(sys.argv) > 6 else 'mixb'
    from pysat.solvers import Solver
    import faithful_artifact as FA, faithful_plant as FP
    from models import cnf as C
    rng = random.Random(8800 + 97 * draw + w)
    seed = rng.getrandbits(w)
    # PLANTED: random S,T give an unsatisfiable relation. Two different states
    # reaching the same state generically has no solution, so an unplanted
    # instance is unsat and any cost fitted over the lucky few is meaningless.
    ths, S0, T0 = FP.plant(w, t, rng, seed)
    art = FA.build(ths, S0, T0, t, seed, suffix)
    clauses, vin, stats = C.build(art, seed=draw, shuffle=True)
    started = time.time()
    with Solver(name=solver_name, bootstrap_with=clauses) as s:
        s.conf_budget(budget)
        verdict = s.solve_limited(expect_interrupt=False)
        accum = s.accum_stats()
    print(json.dumps({"w": w, "t": t, "draw": draw, "solver": solver_name, "suffix": suffix,
        "gates": art.meta["gates"], "clauses": stats["clauses"],
        "conflicts": accum.get("conflicts"), "seconds": round(time.time()-started,2),
        "status": {True:"sat",False:"unsat",None:"budget"}[verdict],
        "event": verdict is True}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
