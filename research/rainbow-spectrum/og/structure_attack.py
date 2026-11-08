#!/usr/bin/env python3
"""Can a public attacker read the secret mixing layer straight off the circuit?

The coupled family hides k separable factors behind secret GF(2) layers,
z = M R(L x), and SAT choked on it: 54,742 conflicts at k=1, over three million
at k=2. That looks like amplification. It may be nothing of the sort, because
CDCL is notoriously weak on dense XOR, and an attacker is not obliged to use
CDCL. An attacker holds the actual public circuit and may exploit its structure.
This attack does exactly that, using nothing but the public AIG.

THE STRUCTURAL FACT IT EXPLOITS. y = L x is affine in the public inputs; the
factor internals are not. So:

  1. AFFINE NODES. Every node is evaluated bit-sliced over sampled inputs -- the
     zero vector, the unit vectors, random vectors -- and a node is affine iff
     its values equal f(0) XOR sum_j c_j x_j with c_j = f(e_j) XOR f(0). The
     coefficient vector c is then a row of some linear map of x.

  2. THE XOR-INTERNAL TRAP. A compiled XOR is three AND gates: two nonlinear
     halves feeding one affine output. Those halves are nonlinear gates whose
     inputs are affine -- and in a left-folded XOR tree those inputs are partial
     sums that straddle factors. Taken naively they would contaminate the
     candidate rows. So a nonlinear gate whose every fanout is affine is marked
     ABSORBED and ignored: it is part of a linear operation, not of a factor.

  3. CANDIDATE ROWS are affine nodes feeding at least one non-absorbed nonlinear
     gate. Each such row is block-pure -- a function of one factor's inputs --
     so a maximal independent subset B spans x-space with exactly n_i rows per
     factor.

  4. INTERACTION. Change coordinates u = B x. Coordinates p and q interact iff
     the second derivative D_p D_q z is not identically zero. For separable R it
     vanishes whenever p and q belong to different factors, and M cannot hide
     that: an invertible linear map sends zero to zero and only zero. Connected
     components of the interaction graph are the factors.

If the recovered partition matches the true one, the coupling is transparent:
the attacker splits the problem into k independent factors exactly as the
keyholder does, public cost is k times one factor, and the SAT blow-up was the
solver's blind spot. That would kill linear coupling as an amplifier.
"""

import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

import compose as C                                              # noqa: E402
import factor as F                                               # noqa: E402

RESULTS = HERE.parents[1] / "results"


# --------------------------------------------------------------- bit-sliced eval
def evaluate_all(aig, samples, n):
    """Every node's value over every sample at once. Returns (values, mask)."""
    count = len(samples)
    mask = (1 << count) - 1
    n_inputs = len(aig.inputs)
    values = [0] * (n_inputs + len(aig.ands) + 1)
    for j in range(n):
        values[j + 1] = sum(((s >> j) & 1) << r for r, s in enumerate(samples))

    def read(literal):
        node, inv = literal >> 1, literal & 1
        base = values[node] if node else 0
        return base ^ mask if inv else base

    for index, (a, b) in enumerate(aig.ands, start=1):
        values[n_inputs + index] = read(a) & read(b)
    return values, mask, read


# ------------------------------------------------------------------- the attack
def attack(public, rng, random_samples=96, interaction_points=4):
    aig, n = public["aig"], public["meta"]["input_bits"]
    n_inputs = len(aig.inputs)
    total = n_inputs + len(aig.ands)

    # 1. affine nodes -------------------------------------------------------
    samples = [0] + [1 << j for j in range(n)] + \
              [rng.getrandbits(n) for _ in range(random_samples)]
    values, mask, _ = evaluate_all(aig, samples, n)
    unit = [values[j + 1] for j in range(n)]          # input j over all samples

    affine = {}                                        # node -> coefficient row
    for node in range(1, total + 1):
        v = values[node]
        f0 = v & 1
        row = 0
        for j in range(n):
            if ((v >> (1 + j)) & 1) ^ f0:
                row |= 1 << j
        predicted = mask if f0 else 0
        for j in range(n):
            if (row >> j) & 1:
                predicted ^= unit[j]
        if predicted == v and row:
            affine[node] = row

    # 2. absorbed nonlinear gates ------------------------------------------
    fanout = {node: [] for node in range(1, total + 1)}
    for index, (a, b) in enumerate(aig.ands, start=1):
        gate = n_inputs + index
        for literal in (a, b):
            if literal >> 1:
                fanout[literal >> 1].append(gate)
    nonlinear = [n_inputs + i for i in range(1, len(aig.ands) + 1)
                 if (n_inputs + i) not in affine]
    absorbed = {g for g in nonlinear
                if fanout[g] and all(f in affine for f in fanout[g])}

    # 3. candidate rows -----------------------------------------------------
    candidates = []
    seen = set()
    for index, (a, b) in enumerate(aig.ands, start=1):
        gate = n_inputs + index
        if gate in affine or gate in absorbed:
            continue
        for literal in (a, b):
            node = literal >> 1
            if node in affine and affine[node] not in seen:
                seen.add(affine[node])
                candidates.append(affine[node])

    basis, pivots = [], []
    reduced = []
    for row in candidates:
        r = row
        for pivot, prow in zip(pivots, reduced):
            if (r >> pivot) & 1:
                r ^= prow
        if r:
            pivot = r.bit_length() - 1
            reduced = [p ^ r if (p >> pivot) & 1 else p for p in reduced]
            pivots.append(pivot)
            reduced.append(r)
            basis.append(row)
    if len(basis) < n:
        return {"recovered": False, "stage": "basis",
                "rank": len(basis), "needed": n,
                "affine_nodes": len(affine), "absorbed": len(absorbed),
                "candidates": len(candidates)}

    _, basis_inv = C._rank_and_inverse(basis, n)
    direction = [sum(((basis_inv[i] >> p) & 1) << i for i in range(n))
                 for p in range(n)]

    # 4. interaction graph by second derivatives ---------------------------
    pairs = [(p, q) for p in range(n) for q in range(p + 1, n)]
    points = [rng.getrandbits(n) for _ in range(interaction_points)]
    batch = []
    for p, q in pairs:
        for x in points:
            batch += [x, x ^ direction[p], x ^ direction[q],
                      x ^ direction[p] ^ direction[q]]
    values, mask, read = evaluate_all(aig, batch, n)
    outputs = [read(literal) for literal in public["z"]]
    signal = 0
    for out in outputs:
        block = 0
        for offset in range(4):
            stride = out >> offset
            block ^= stride
        signal |= out
    # Recover per-pair second-derivative nonzero-ness from the batch layout.
    interacts = {}
    for index, (p, q) in enumerate(pairs):
        hit = False
        for point_index in range(interaction_points):
            base = 4 * (index * interaction_points + point_index)
            for out in outputs:
                if (((out >> base) ^ (out >> (base + 1)) ^ (out >> (base + 2))
                     ^ (out >> (base + 3))) & 1):
                    hit = True
                    break
            if hit:
                break
        interacts[(p, q)] = hit

    parent = list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for (p, q), hit in interacts.items():
        if hit:
            parent[find(p)] = find(q)
    groups = {}
    for p in range(n):
        groups.setdefault(find(p), []).append(p)
    partition = sorted(sorted(g) for g in groups.values())

    return {"recovered": True, "basis": basis, "partition": partition,
            "components": len(partition),
            "affine_nodes": len(affine), "absorbed": len(absorbed),
            "candidates": len(candidates),
            "interacting_pairs": sum(interacts.values()),
            "pairs_tested": len(pairs)}


def score_partition(result, secret, family, per, n):
    """Does the recovered partition REFINE the true factor partition?

    The first version of this required an exact match against a k-block truth
    and scored every instance "resisted" -- including the parallel CONTROL,
    which has no coupling and is trivially decomposable. An attack that fails
    on the control is mis-scored, not blocked.

    The attack in fact recovers MORE than the factors. A factor's residual is
    A(pa) XOR B(pb, mb), additively separable between sides, and mix_a
    separates the pairs, so each factor genuinely splits into four independent
    pieces: {pa_0}, {pa_1}, {pb_0, mb_0}, {pb_1, mb_1}. Hence 4k components.
    The right question is whether each recovered component lies inside ONE
    true factor. If so, the attacker has the decomposition -- and a finer one
    than the keyholder needs.
    """
    basis = result["basis"]
    _, basis_inv = C._rank_and_inverse(basis, n)
    L = secret["L"] if family == "coupled" else [1 << i for i in range(n)]
    G = []
    for row in L:
        acc = 0
        for j in range(n):
            if (row >> j) & 1:
                acc ^= basis_inv[j]
        G.append(acc)
    block_of = []
    for p in range(n):
        touched = {i // per for i in range(n) if (G[i] >> p) & 1}
        block_of.append(touched)
    pure = all(len(b) == 1 for b in block_of)

    component_blocks = []
    for component in result["partition"]:
        blocks = set()
        for p in component:
            blocks |= block_of[p]
        component_blocks.append(blocks)
    refines = pure and all(len(b) == 1 for b in component_blocks)
    covered = {next(iter(b)) for b in component_blocks if len(b) == 1}
    return {"basis_block_pure": pure,
            "refines_truth": refines,
            "factors_separated": len(covered) if refines else 0,
            "components_per_factor": (len(result["partition"]) / len(covered)
                                      if refines and covered else None)}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    w, t = 6, 3
    per, _ = F.input_bits(w, t)
    rows = []
    for family in C.FAMILIES:
        for k in (1, 2, 3, 4):
            for draw in range(3):
                rng = random.Random(31337 + 1009 * draw + 101 * k + w)
                factors = [F.new_factor(w, t, random.Random(rng.getrandbits(32)))
                           for _ in range(k)]
                public, secret = C.build(family, factors, w, t, rng)
                n = public["meta"]["input_bits"]
                started = time.time()
                result = attack(public, random.Random(draw))
                elapsed = time.time() - started
                row = {"family": family, "k": k, "draw": draw, "n": n,
                       "seconds": round(elapsed, 2),
                       **{key: result[key] for key in
                          ("recovered", "affine_nodes", "absorbed", "candidates")
                          if key in result}}
                if result["recovered"]:
                    row.update(components=result["components"],
                               interacting_pairs=result["interacting_pairs"],
                               pairs_tested=result["pairs_tested"],
                               **score_partition(result, secret, family, per, n))
                else:
                    row.update(stage=result.get("stage"), rank=result.get("rank"))
                rows.append(row)
                verdict = ("DECOMPOSED" if row.get("refines_truth")
                           else "resisted" if row["recovered"] else "no basis")
                print(f"  {family:<9} k={k} draw={draw}  n={n:>3}  "
                      f"affine={row['affine_nodes']:>5} absorbed={row['absorbed']:>5}  "
                      f"components={row.get('components', '-')!s:>2}  "
                      f"factors={row.get('factors_separated', '-')!s:>2}/{k}  "
                      f"-> {verdict}  ({row['seconds']}s)", flush=True)

    control = [r for r in rows if r["family"] == "parallel"]
    control_ok = all(r.get("refines_truth") for r in control)
    coupled = [r for r in rows if r["family"] == "coupled" and r["k"] > 1]
    broken = [r for r in coupled if r.get("refines_truth")]
    report = {"attack": "og/structure_attack",
              "access": "the public AIG only",
              "method": "affine-node detection -> block-pure basis -> "
                        "second-derivative interaction graph",
              "control_decomposed": f"{sum(r.get('refines_truth', False) for r in control)}/{len(control)}",
              "control_passed": control_ok,
              "coupled_k_ge_2_decomposed": f"{len(broken)}/{len(coupled)}",
              "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "rows": rows}
    if not control_ok:
        report["conclusion"] = (
            "THE CONTROL FAILED: the attack does not decompose the uncoupled "
            "parallel family, so it proves nothing about the coupled one.")
    elif len(broken) == len(coupled):
        # Keep DEMONSTRATED and INFERRED apart. What this attack shows is that
        # the decomposition is recoverable from the public circuit. It does not
        # produce a witness, so "public cost is linear in k" and "the SAT
        # blow-up was CDCL's XOR weakness" are inferences until a witness is
        # actually found at that cost. The first draft of this conclusion
        # asserted both as findings.
        report["demonstrated"] = (
            f"the factor decomposition is recoverable from the public circuit "
            f"alone in {len(broken)}/{len(coupled)} coupled instances with "
            f"k >= 2, finer than the factors (4 pieces each), matching the "
            f"uncoupled control")
        report["inferred_not_yet_demonstrated"] = [
            "public witness-finding cost is linear in k",
            "the SAT blow-up on the coupled family is CDCL's weakness on dense "
            "XOR rather than hardness",
        ]
        report["conclusion"] = (
            f"The secret linear mixing layer is transparent: from the public "
            f"circuit alone the decomposition was recovered in "
            f"{len(broken)}/{len(coupled)} coupled instances with k >= 2, finer "
            f"than the factors, exactly as on the uncoupled control. Linear "
            f"coupling hides no seam, so it cannot be what amplifies security "
            f"with k. NOT YET DEMONSTRATED: that a witness then follows at "
            f"linear-in-k cost, and that the SAT blow-up was the solver's XOR "
            f"blind spot. Both are strongly suggested and neither is shown.")
    else:
        report["conclusion"] = (
            f"Control passed; coupled decomposed in {len(broken)}/{len(coupled)}. "
            f"Failures are recorded per row. A failure of this attack is not "
            f"evidence of hardness until a stronger one also fails.")
    path = RESULTS / "og-structure-attack.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
