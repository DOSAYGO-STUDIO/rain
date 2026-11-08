#!/usr/bin/env python3
"""Phase 4 + 5: exact symbolic flattening, then attack the flattened form.

Until now the "flat" attacker only had input/output access. The hypothesis is
stronger: the attacker possesses the exact closed form of the composed function
and merely lacks its useful decomposition. A truth table can conceal algebraic
structure that a symbolic form announces immediately, so those are different
adversaries and the real test had not been run.

EXACT FLATTENING. Algebraic normal form is the honest flattening. ANF is
canonical: two entirely different programs computing the same Boolean function
produce the same ANF, so it retains no marker saying "this monomial came from
round 1". Intermediates are eliminated by construction rather than hidden. Any
advantage the factor-aware solver keeps therefore cannot come from a difference
in the mathematical function -- only from knowing a decomposition of it.

THE ATTACK. A class label is a combination of output bits that is CONSTANT as
the last round's controls vary (degree 0 in those controls) AND takes different
values on different classes. Constancy alone is not enough and is not evidence:
the low bits of modular addition are GF(2)-linear, so constant combinations
exist trivially. Discrimination across held-out classes is what makes a relation
a usable steering quotient, and it is the same criterion the GF(2) and Z/2^r
searches used.

POSITIVE CONTROL. The same pipeline runs on the pre-mixer state, where the pair
sums are planted and genuinely label classes. The control must find
discriminating degree-0 relations. If it does not, the machinery is broken and
its negatives are worthless.

EQUIVALENCE CONTROL. For every construction, factored == DAG == ANF is checked
on EVERY input, so exact flattening is a trusted transformation rather than
another source of artifacts.
"""

import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from compositions.sequential import Composition       # noqa: E402
from models import rainbow as R                       # noqa: E402
from models import spectrum as S                      # noqa: E402
from models import symbolic as Y                      # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
PAIRS = S.PAIRINGS[0]
SIGNS = ((-1, 1), (1, -1))
LANES = 4


def make_thetas(w, count, rng):
    out = []
    while len(out) < count:
        theta = S.random_theta(w, rng, pairs=PAIRS, signs=SIGNS)
        if S.validate_weakness(theta, rng, trials=30)["admissible"]:
            out.append(theta)
    return tuple(out)


# --------------------------------------------------------------- symbolic form
def symbolic_round(builder, state, controls, theta):
    out = list(state)
    for (i, j), (si, sj), x in zip(theta.pairs, theta.signs, controls):
        out[i] = builder.add(out[i], x) if si == 1 else builder.sub(out[i], x)
        out[j] = builder.add(out[j], x) if sj == 1 else builder.sub(out[j], x)
    m, r = theta.multipliers, theta.mixa_rotations
    mixed = list(out)
    for index, (i, j) in enumerate(theta.pairs):
        m0, m1, m2, m3 = m[4 * index:4 * index + 4]
        r0, r1 = r[2 * index], r[2 * index + 1]
        a = builder.mul(builder.rotr(builder.mul(out[i], builder.const(m0)), r0),
                        builder.const(m1))
        b = builder.mul(builder.rotr(
            builder.mul(builder.xor(out[j], a), builder.const(m2)), r1),
            builder.const(m3))
        mixed[i], mixed[j] = a, b
    return tuple(mixed)


def build_dag(composition, state_values):
    """Whole composition as one hash-consed DAG, every round symbolic.

    This is the evaluable flat form and the honest measure of flattening growth;
    it costs no truth table, so it scales past the ANF sizes.
    """
    w = composition.w
    builder = Y.Builder(w)
    state = tuple(builder.const(v) for v in state_values)
    npairs = composition.controls_per_round
    index = 0
    for theta in composition.thetas:
        controls = tuple(builder.var(index + n) for n in range(npairs))
        index += npairs
        state = symbolic_round(builder, state, controls, theta)
    return Y.stats(list(state))


def build_last_round_dag(composition, state_values, prefix):
    """DAG over the last round's controls only, with the prefix folded in."""
    w = composition.w
    npairs = composition.controls_per_round
    state = state_values
    for index, theta in enumerate(composition.thetas[:-1]):
        state = R.transition(state, prefix[index], theta, inner=False, seed=0)
    builder = Y.Builder(w)
    symbolic = tuple(builder.const(v) for v in state)
    controls = tuple(builder.var(n) for n in range(npairs))
    roots = symbolic_round(builder, symbolic, controls, composition.thetas[-1])
    return builder, roots


# --------------------------------------------------------------------- ANF
def mobius(table):
    """Moebius transform, an involution over GF(2): truth table <-> ANF."""
    values = list(table)
    n = len(values).bit_length() - 1
    for i in range(n):
        step = 1 << i
        for j in range(len(values)):
            if j & step:
                values[j] ^= values[j ^ step]
    return values


def truth_tables(evaluate_word, nvars, nbits):
    size = 1 << nvars
    tables = [[0] * size for _ in range(nbits)]
    for assignment in range(size):
        word = evaluate_word(assignment)
        for bit in range(nbits):
            tables[bit][assignment] = (word >> bit) & 1
    return tables


def degree_of(coefficients):
    best = -1
    for mask, value in enumerate(coefficients):
        if value:
            best = max(best, bin(mask).count("1"))
    return best


def constant_relations(anf_bits, nvars):
    """Bit-combinations that are CONSTANT in the controls (degree 0 in ANF).

    Returned as provenance masks over output-bit indices, found by eliminating
    the non-constant monomials: a GF(2) dependency among those tails is exactly
    a combination whose only surviving monomial is the constant term.
    """
    nonconstant = [m for m in range(1 << nvars) if m != 0]
    index_of = {mask: i for i, mask in enumerate(nonconstant)}
    vectors = []
    for coefficients in anf_bits:
        value = 0
        for mask in nonconstant:
            if coefficients[mask]:
                value |= 1 << index_of[mask]
        vectors.append(value)

    basis, relations = {}, []
    for index, vector in enumerate(vectors):
        current, provenance = vector, 1 << index
        while current:
            pivot = current.bit_length() - 1
            if pivot in basis:
                value, prov = basis[pivot]
                current ^= value
                provenance ^= prov
            else:
                basis[pivot] = (current, provenance)
                break
        if current == 0:
            relations.append(provenance)
    return relations


def relation_value(provenance, word):
    """Value of a bit-combination on one output word."""
    total = 0
    mask = provenance
    while mask:
        bit = (mask & -mask).bit_length() - 1
        total ^= (word >> bit) & 1
        mask &= mask - 1
    return total


# ------------------------------------------------------------------ experiment
def class_evaluator(composition, state_values, prefix, premixer):
    """Outputs as the LAST round's controls vary; the prefix fixes the class."""
    w = composition.w
    npairs = composition.controls_per_round
    base = state_values
    for index, theta in enumerate(composition.thetas[:-1]):
        base = R.transition(base, prefix[index], theta, inner=False, seed=0)
    last = composition.thetas[-1]

    def evaluate(assignment):
        controls = tuple((assignment >> (n * w)) & ((1 << w) - 1)
                         for n in range(npairs))
        state = (R.inject(base, controls, last) if premixer
                 else R.transition(base, controls, last, inner=False, seed=0))
        word = 0
        for lane, value in enumerate(state):
            word |= value << (lane * w)
        return word

    return evaluate


def run(w, k, rng, premixer=False, heldout=6, max_degree=3):
    composition = Composition(thetas=make_thetas(w, k, rng))
    state_values = tuple(rng.getrandbits(w) for _ in range(LANES))
    npairs = composition.controls_per_round
    nvars = npairs * w
    nbits = LANES * w

    prefixes = [tuple(tuple(rng.getrandbits(w) for _ in range(npairs))
                      for _ in range(max(0, k - 1)))
                for _ in range(heldout)]

    per_class_anf, per_class_tables = [], []
    for prefix in prefixes:
        evaluate = class_evaluator(composition, state_values, prefix, premixer)
        tables = truth_tables(evaluate, nvars, nbits)
        per_class_tables.append(tables)
        per_class_anf.append([mobius(t) for t in tables])

    # Relations must hold in EVERY class, then discriminate between classes.
    common = None
    for anf_bits in per_class_anf:
        found = set(constant_relations(anf_bits, nvars))
        common = found if common is None else (common & found)
    common = sorted(common or [])

    discriminating = []
    for provenance in common:
        # The relation is constant within its class, so one assignment suffices.
        values = set()
        for tables in per_class_tables:
            word = 0
            for bit in range(nbits):
                word |= tables[bit][0] << bit
            values.add(relation_value(provenance, word))
        if len(values) > 1:
            discriminating.append(provenance)

    # Exhaustive equivalence: factored == DAG == ANF on every input.
    builder, roots = build_last_round_dag(composition, state_values, prefixes[0])
    evaluate = class_evaluator(composition, state_values, prefixes[0], premixer)
    dag_mismatch = anf_mismatch = 0
    if not premixer:
        for assignment in range(1 << nvars):
            env = {n: (assignment >> (n * w)) & ((1 << w) - 1) for n in range(npairs)}
            word = 0
            for lane, root in enumerate(roots):
                word |= Y.evaluate(root, env, w) << (lane * w)
            if word != evaluate(assignment):
                dag_mismatch += 1
    for bit in range(nbits):
        if mobius(per_class_anf[0][bit]) != per_class_tables[0][bit]:
            anf_mismatch += 1

    anf_bits = per_class_anf[0]
    degrees = [degree_of(c) for c in anf_bits]
    monomials = [sum(1 for v in c if v) for c in anf_bits]

    return {
        "w": w, "k": k, "variables": nvars, "output_bits": nbits,
        "classes": heldout,
        "whole_composition_dag": build_dag(composition, state_values),
        "last_round_dag": Y.stats(list(roots)),
        "anf_max_degree": max(degrees),
        "anf_min_degree": min(degrees),
        "mean_monomials": round(sum(monomials) / len(monomials), 1),
        "anf_density": round(sum(monomials) / (nbits * (1 << nvars)), 4),
        "constant_relations_in_every_class": len(common),
        "discriminating_class_labels": len(discriminating),
        # Existence is not capability. The factored attacker gets sigma, which
        # is npairs*w bits; a handful of GF(2) label bits is leakage, not an
        # equivalent steering quotient, so the comparison is in BITS.
        "label_bits": len(discriminating),
        "sigma_bits": nvars,
        "label_fraction_of_sigma": round(len(discriminating) / nvars, 4),
        "distinct_label_values_seen": len({
            tuple(relation_value(p, sum(tables[b][0] << b for b in range(nbits)))
                  for p in discriminating)
            for tables in per_class_tables}) if discriminating else 0,
        "equivalence": {
            "inputs_checked": 1 << nvars,
            "factored_vs_dag_mismatches": dag_mismatch,
            "anf_vs_truth_mismatched_bits": anf_mismatch,
            "identical": dag_mismatch == 0 and anf_mismatch == 0,
        },
    }


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    report = {
        "experiment": "exact_flattening_and_algebraic_attack",
        "question": "does the closed algebraic form expose a steering quotient?",
        "criterion": ("a class label is a bit-combination constant in the last "
                      "round's controls AND differing across classes; constancy "
                      "alone is trivial because low bits of modular addition are "
                      "GF(2)-linear"),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "control": [], "flattened": [],
    }

    print("positive control: pre-mixer state, where the pair sums are planted")
    for w in (3, 4, 5):
        row = run(w, 2, rng, premixer=True)
        report["control"].append(row)
        print(f"  w={w}  constant relations {row['constant_relations_in_every_class']}"
              f"  discriminating {row['discriminating_class_labels']}"
              f"  -> {'PASS' if row['discriminating_class_labels'] else 'FAIL'}")

    print("\nflattened composition (exhaustive equivalence: factored == DAG == ANF)")
    for w, k in ((3, 2), (4, 2), (5, 2), (6, 2), (3, 3), (4, 3), (5, 3)):
        row = run(w, k, rng)
        report["flattened"].append(row)
        eq = row["equivalence"]
        whole = row["whole_composition_dag"]
        print(f"  w={w} k={k}  vars={row['variables']}  "
              f"DAG {whole['dag_nodes']}n/d{whole['depth']}/{whole['multiplications']}mul  "
              f"deg {row['anf_min_degree']}..{row['anf_max_degree']}  "
              f"mono {row['mean_monomials']}  dens {row['anf_density']}  "
              f"equiv {eq['identical']}({eq['inputs_checked']})  "
              f"const {row['constant_relations_in_every_class']} -> "
              f"discriminating {row['discriminating_class_labels']}")

    report["growth_table"] = [
        {"w": r["w"], "k": r["k"], "anf_max_degree": r["anf_max_degree"],
         "mean_monomials": r["mean_monomials"], "anf_density": r["anf_density"],
         "dag_nodes": r["whole_composition_dag"]["dag_nodes"],
         "dag_depth": r["whole_composition_dag"]["depth"],
         "multiplications": r["whole_composition_dag"]["multiplications"]}
        for r in report["flattened"]]

    control_ok = all(r["discriminating_class_labels"] > 0 for r in report["control"])
    equiv_ok = all(r["equivalence"]["identical"] for r in report["flattened"])
    leaks = [r for r in report["flattened"] if r["label_bits"] > 0]
    # A break requires the flat attacker to obtain sigma-equivalent capability,
    # not merely some nonzero label. One bit out of 2w narrows the search by a
    # factor of two; it does not replace a 2^(w/2) birthday on sigma.
    broke = any(r["label_bits"] >= r["sigma_bits"] for r in report["flattened"])
    report["positive_control_passed"] = control_ok
    report["equivalence_verified"] = equiv_ok
    report["partial_leakage_draws"] = len(leaks)
    report["max_label_bits_observed"] = max(
        (r["label_bits"] for r in report["flattened"]), default=0)
    report["algebraic_attack_recovered_sigma"] = broke

    if not equiv_ok:
        report["conclusion"] = (
            "EQUIVALENCE FAILED: the flattened form is not the same function as "
            "the factored one, so nothing measured on it means anything.")
    elif not control_ok:
        report["conclusion"] = (
            "POSITIVE CONTROL FAILED: the pipeline did not find the planted pair "
            "sums on the pre-mixer state. Negatives are meaningless until it does.")
    elif broke:
        report["conclusion"] = (
            "The exact flattened form yields sigma-equivalent capability: the "
            "flat attacker recovers as many label bits as the factored attacker "
            "gets from sigma, so the separation does not survive flattening.")
    elif leaks:
        report["conclusion"] = (
            f"PARTIAL LEAKAGE. The flattened form exposes a discriminating "
            f"GF(2) class label in {len(leaks)} of {len(report['flattened'])} "
            f"configurations, worth at most "
            f"{report['max_label_bits_observed']} bit(s) against sigma's "
            f"npairs*w. Brute force confirms such a relation really is constant "
            f"across every control assignment in every class, so this is real "
            f"structure and not a validation artifact. The Z/2^r search could "
            f"not see it because it is GF(2)-linear in output BITS rather than "
            f"Z/2^r-linear in output WORDS. One bit halves the attacker's search; "
            f"it does not replace a 2^(w/2) birthday on sigma. So exact "
            f"flattening REDUCES the separation without closing it.")
    else:
        report["conclusion"] = (
            "Flattening is verified exact on every input, the control recovers "
            "the planted labels, and the flattened composition exposes no "
            "discriminating class label among combinations of output bits. Same "
            "function, different structural knowledge, different capability. "
            "Untried: relations over larger bit sets, higher-degree quotients, "
            "SAT/SMT on the emitted form, and meet-in-the-middle.")
    path = RESULTS / "flattening-algebraic.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
