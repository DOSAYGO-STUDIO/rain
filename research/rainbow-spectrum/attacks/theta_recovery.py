#!/usr/bin/env python3
"""What does the public artifact give away about theta? The pairing, immediately.

Kill criterion, stated before running: if the public representation trivially
reveals theta or the sigma-matching route, say so directly rather than looking
for a reading that survives. Part of it does.

THE LEAK. mix_a is pair-separable -- that separability is the entire reason the
privileged attack can divide and conquer -- and separability is visible from
outside. Vary one merge control word and only that pair's output lanes move.
Fourteen public evaluations recover the pairing exactly, using nothing but
PublicArtifact.eval_side.

THE CONTROL MATTERS HERE MORE THAN THE RESULT. Experiment B pins
PAIRS = S.PAIRINGS[0], so every challenge it generates uses ((0,1),(2,3)). An
attack that simply printed that constant would score 100% against every instance
this project has ever produced, and would look like a devastating break. So the
attack is run against all three pairings with signs drawn freely, and it
recovers the non-default ones too. Without that control this file would be
worthless.

WHAT IT DOES AND DOES NOT COST THE CONSTRUCTION.

  It is a genuine leak of part of the secret decomposition, and it is not
  repairable by better compilation: it follows from the function itself, not
  from how the circuit was emitted. Any exact public artifact leaks it, because
  an attacker with only black-box access sees the same separability.

  It hands the attacker independence between pairs, which turns one 4w-bit
  matching problem into two 2w-bit ones. Counting the remaining work for a pair:
  side A offers 2^t = 2^(w/2) candidates, side B offers 2^(t+w) = 2^(3w/2), and
  a match must agree on 2w bits, so a meet-in-the-middle storing A and
  enumerating B costs about 2^(3w/2) against the privileged 2^(w/2).

  So the pairing alone does not hand over the sigma route. What remains secret
  and load-bearing is the invariant -- which functional of the pair is preserved
  by the injection -- and the final mixer's inverse. Whether those survive
  contact with a real solver is the question the CNF attacks exist to answer,
  and it is not prejudged here.

This is reported as a partial break of secrecy, not of the construction.
"""

import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))

from models import public_artifact as PA                         # noqa: E402
from models import spectrum as S                                 # noqa: E402

RESULTS = HERE.parents[1] / "results"
PAIRINGS = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
PROBES = 7


def recover_pairing(artifact):
    """Public-only. Returns the recovered pairing and the query count."""
    meta = artifact.meta
    npairs, lanes, k, w, t = (meta["npairs"], meta["lanes"], meta["k"],
                              meta["w"], meta["t"])
    queries = 0

    def evaluate(words):
        nonlocal queries
        groups = {f"pa{i}": [0] * (npairs * t) for i in range(k - 1)}
        groups.update({f"pb{i}": [0] * (npairs * t) for i in range(k - 1)})
        bits = []
        for word in words:
            bits += [(word >> b) & 1 for b in range(w)]
        groups["mb"] = bits
        queries += 1
        return artifact.eval_side("b", **groups)

    base = evaluate([0] * npairs)
    recovered = []
    for pair_index in range(npairs):
        moved = set()
        for value in range(1, PROBES + 1):
            words = [0] * npairs
            words[pair_index] = value
            out = evaluate(words)
            moved |= {lane for lane in range(lanes) if out[lane] != base[lane]}
        recovered.append(tuple(sorted(moved)))
    return sorted(recovered), queries


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for pairing in PAIRINGS:
        for hardened in (False, True):
            for trial in range(4):
                rng = random.Random(7000 + trial + 13 * PAIRINGS.index(pairing)
                                    + 101 * int(hardened))
                w, t = 6, 3
                thetas = []
                while len(thetas) < 2:
                    theta = S.random_theta(w, rng, pairs=pairing)
                    if S.validate_weakness(theta, rng,
                                           trials=20)["admissible"]:
                        thetas.append(theta)
                thetas = tuple(thetas)
                npairs = len(thetas[0].pairs)
                start = tuple(rng.getrandbits(w) for _ in range(4))
                target = tuple(rng.getrandbits(w) for _ in range(4))
                artifact = PA.build(thetas, start, target,
                                    tuple(0 for _ in range(npairs)), t, hardened)
                recovered, queries = recover_pairing(artifact)
                truth = sorted(tuple(sorted(p)) for p in thetas[-1].pairs)
                rows.append({
                    "pairing": [list(p) for p in pairing],
                    # Normalise both sides: a list-of-tuples never equals a
                    # list-of-lists, and getting this wrong silently reported
                    # every row as non-default, which is the flattering answer.
                    "is_default": ([sorted(x) for x in pairing]
                                   == [sorted(x) for x in PAIRINGS[0]]),
                    "hardened": hardened, "trial": trial,
                    "recovered": [list(p) for p in recovered],
                    "truth": [list(p) for p in truth],
                    "correct": recovered == truth, "queries": queries,
                })

    correct = sum(r["correct"] for r in rows)
    nondefault = [r for r in rows if not r["is_default"]]
    report = {
        "attack": "theta_recovery/pairing_by_differential_probing",
        "access": "PublicArtifact.eval_side only -- no theta, no gates inspected",
        "recovered": f"{correct}/{len(rows)}",
        "recovered_nondefault_pairings":
            f"{sum(r['correct'] for r in nondefault)}/{len(nondefault)}",
        "queries_per_recovery": rows[0]["queries"],
        "control": "run against all three pairings; Experiment B pins "
                   "PAIRINGS[0], so a constant-output attack would have scored "
                   "100% on every challenge this project has generated",
        "consequence": "pairs become independent: one 4w-bit match becomes two "
                       "2w-bit matches. Per pair the MITM is still ~2^(3w/2) "
                       "against the privileged 2^(w/2), so the pairing alone "
                       "does not surrender the sigma route",
        "still_secret": ["which functional of the pair the injection preserves",
                         "the final mixer's inverse"],
        "verdict": "PARTIAL BREAK of secrecy, not of the construction",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rows": rows,
    }
    path = RESULTS / "theta-recovery.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"pairing recovered {correct}/{len(rows)} "
          f"({sum(r['correct'] for r in nondefault)}/{len(nondefault)} on "
          f"non-default pairings) in {rows[0]['queries']} public queries each")
    print(f"{report['verdict']}: {report['consequence']}")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
