#!/usr/bin/env python3
"""One public SAT draw against the FAITHFUL B artifact."""
import json, pathlib, random, sys, time
HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "attacks"))

def main():
    w, t, draw, solver_name, budget = (int(sys.argv[1]), int(sys.argv[2]),
        int(sys.argv[3]), sys.argv[4], int(sys.argv[5]))
    from pysat.solvers import Solver
    import faithful_artifact as FA
    from models import cnf as C
    from models import spectrum as S
    rng = random.Random(8800 + 97 * draw + w)
    seed = rng.getrandbits(w)
    ths = []
    while len(ths) < 2:
        th = S.random_theta(w, rng, pairs=S.PAIRINGS[0], signs=((-1,1),(1,-1)))
        if S.validate_weakness(th, rng, trials=20)["admissible"]: ths.append(th)
    S0 = tuple(rng.getrandbits(w) for _ in range(4))
    T0 = tuple(rng.getrandbits(w) for _ in range(4))
    art = FA.build(tuple(ths), S0, T0, t, seed)
    clauses, vin, stats = C.build(art, seed=draw, shuffle=True)
    started = time.time()
    with Solver(name=solver_name, bootstrap_with=clauses) as s:
        s.conf_budget(budget)
        verdict = s.solve_limited(expect_interrupt=False)
        accum = s.accum_stats()
    print(json.dumps({"w": w, "t": t, "draw": draw, "solver": solver_name,
        "gates": art.meta["gates"], "clauses": stats["clauses"],
        "conflicts": accum.get("conflicts"), "seconds": round(time.time()-started,2),
        "status": {True:"sat",False:"unsat",None:"budget"}[verdict],
        "event": verdict is True}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
