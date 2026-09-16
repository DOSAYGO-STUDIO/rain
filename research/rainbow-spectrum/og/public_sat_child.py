#!/usr/bin/env python3
"""One public SAT attack on a k-factor composition, one solve per process.

The attacker gets the composed public circuit and must find x with z(x) = 0.
It is Tseitin-encoded with variable numbering, clause order and literal order
shuffled, handed to a pysat solver under a deterministic CONFLICT budget, and any
returned x is re-evaluated through the public circuit AND checked factor by
factor against the secret decomposition before it counts.
"""

import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))


def tseitin(public, seed):
    aig = public["aig"]
    n_inputs, total = len(aig.inputs), len(aig.inputs) + len(aig.ands)
    order = list(range(1, total + 2))
    random.Random(seed).shuffle(order)
    var = {node: order[node - 1] for node in range(1, total + 1)}
    vtrue = order[total]

    def lit(literal):
        node, inv = literal >> 1, literal & 1
        if node == 0:
            return vtrue if inv else -vtrue
        return -var[node] if inv else var[node]

    clauses = [[vtrue]]
    for index, (a, b) in enumerate(aig.ands, start=1):
        z, la, lb = var[n_inputs + index], lit(a), lit(b)
        clauses += [[-z, la], [-z, lb], [z, -la, -lb]]
    for out in public["z"]:
        clauses.append([-lit(out)])                 # every output bit must be 0
    rng = random.Random(seed ^ 0x2545F491)
    for clause in clauses:
        rng.shuffle(clause)
    rng.shuffle(clauses)
    return clauses, {literal: var[literal >> 1] for literal in aig.inputs}


def main():
    family, k, w, t, draw, solver_name, budget = (
        sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]),
        int(sys.argv[5]), sys.argv[6], int(sys.argv[7]))
    from pysat.solvers import Solver
    import compose as C
    import factor as F

    rng = random.Random(31337 + 1009 * draw + 101 * k + w)
    factors = [F.new_factor(w, t, random.Random(rng.getrandbits(32)))
               for _ in range(k)]
    public, secret = C.build(family, factors, w, t, rng)
    _, private_cost, private_ok = C.private_solve(public, secret, factors, w, t)

    out = {"family": family, "k": k, "w": w, "t": t, "draw": draw,
           "solver": solver_name, "budget": budget, "meta": public["meta"],
           "private_ok": private_ok, "private_total": private_cost["total"],
           "private_latency": private_cost["latency"]}

    clauses, var_of_input = tseitin(public, draw)
    out["cnf_clauses"] = len(clauses)
    started = time.time()
    with Solver(name=solver_name, bootstrap_with=clauses) as solver:
        solver.conf_budget(budget)
        verdict = solver.solve_limited(expect_interrupt=False)
        model = solver.get_model() if verdict else None
        stats = solver.accum_stats()
    out.update(seconds=round(time.time() - started, 2),
               conflicts=stats.get("conflicts"),
               status={True: "sat", False: "unsat", None: "budget"}[verdict],
               event=verdict is True)

    if model:
        positive = set(v for v in model if v > 0)
        x_bits = [1 if var_of_input[l] in positive else 0 for l in public["x"]]
        z = public["aig"].evaluate(public["z"], dict(zip(public["x"], x_bits)))
        # Ground truth: map back through the secret and check every factor.
        y_bits = (C.apply_bits(secret["L"], x_bits)
                  if "L" in secret else x_bits)
        per, _ = F.input_bits(w, t)
        from models.aig import Aig
        factor_ok = []
        for i, challenge in enumerate(factors):
            aig = Aig()
            ys = [aig.input(f"y{j}") for j in range(per)]
            residual = F.residual_circuit(aig, challenge, t, ys)
            bits = y_bits[i * per:(i + 1) * per]
            factor_ok.append(not any(aig.evaluate(residual, dict(zip(ys, bits)))))
        out["public_z_zero"] = not any(z)
        out["every_factor_satisfied"] = all(factor_ok)
        out["witness_verified"] = (not any(z)) and all(factor_ok)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
