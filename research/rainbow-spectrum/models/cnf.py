"""Tseitin encoding of a public artifact, with the structure shuffled out.

The point of this file is to remove every advantage an attacker might get from
HOW the circuit was written, so that what is measured is the difficulty of the
function rather than the legibility of its emission. Three things are done:

  * the AIG is Tseitin-encoded to clauses, which is the representation the
    solver would build internally anyway -- but building it here means the
    solver never sees the word-level structure, the round boundaries, or the
    multiplier constants that Experiment B's original "public" encoding handed
    over as z3.BitVecVal literals;

  * variable numbering is permuted, so gate index no longer implies topological
    position and a solver cannot infer the circuit's shape from its numbering;

  * clause order is shuffled, and literal order within each clause, so nothing
    about emission order survives.

The permutation is seeded and recorded, so a run is reproducible and a witness
can be mapped back to the artifact's inputs.

Constants are handled with one forced variable rather than by substitution, so
that a gate feeding on a public constant looks like any other gate.
"""

import random


def build(artifact, seed=0, shuffle=True):
    """Return (clauses, var_of_input_literal, stats).

    The equality of the two published output vectors is part of the formula:
    the attacker's task is to find inputs making side A and side B agree, so
    that constraint belongs in the CNF rather than in a wrapper around it.
    """
    aig = artifact.aig
    n_inputs, n_ands = len(aig.inputs), len(aig.ands)
    total = n_inputs + n_ands

    # Variable 1..total for AIG nodes, plus one forced-true variable.
    order = list(range(1, total + 2))
    if shuffle:
        random.Random(seed).shuffle(order)
    var_of_node = {node: order[node - 1] for node in range(1, total + 1)}
    vtrue = order[total]

    def cnf_lit(literal):
        node, inverted = literal >> 1, literal & 1
        if node == 0:                       # FALSE is literal 0, TRUE is 1
            return vtrue if inverted else -vtrue
        var = var_of_node[node]
        return -var if inverted else var

    clauses = [[vtrue]]
    for index, (left, right) in enumerate(aig.ands, start=1):
        z = var_of_node[n_inputs + index]
        a, b = cnf_lit(left), cnf_lit(right)
        clauses.append([-z, a])
        clauses.append([-z, b])
        clauses.append([z, -a, -b])

    for pa, pb in zip(artifact.out_a, artifact.out_b):
        p, q = cnf_lit(pa), cnf_lit(pb)
        clauses.append([-p, q])
        clauses.append([p, -q])

    if shuffle:
        rng = random.Random(seed ^ 0x5bf03635)
        for clause in clauses:
            rng.shuffle(clause)
        rng.shuffle(clauses)

    var_of_input = {literal: var_of_node[literal >> 1]
                    for literal in aig.inputs}
    stats = {"variables": total + 1, "clauses": len(clauses),
             "inputs": n_inputs, "ands": n_ands, "shuffled": shuffle,
             "seed": seed}
    return clauses, var_of_input, stats


def decode(model, artifact, var_of_input):
    """Map a SAT model back to the artifact's input groups."""
    positive = set(literal for literal in model if literal > 0)
    values = {}
    for name, literals in artifact.groups.items():
        values[name] = [1 if var_of_input[literal] in positive else 0
                        for literal in literals]
    return values
