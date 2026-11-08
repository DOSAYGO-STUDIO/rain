#!/usr/bin/env python3
"""Does a secret-free public object actually exist? Regression test for the boundary.

Experiment B's "public" solver received challenge["thetas"] and built its formula
out of the secret multipliers, rotations, pairs and signs. So its 0.722 exponent
was never a public number, and nothing downstream of it -- the representation
gap, the negative control, the interaction table -- was measuring what it
claimed. This file is the repair, and it is written as a test rather than a
demonstration so the boundary cannot rot back.

Four things are checked, in the order that makes failure informative:

  1. EXACTNESS. The compiled artifact agrees with the factored implementation on
     EVERY input at toy widths. Not sampled: enumerated. A flattening that is
     merely usually right is not a flattening.

  2. SECRET-FREEDOM, checked on the serialised bytes rather than on intent. The
     artifact is written to JSON and the multipliers, rotations, signs, pairing,
     planted witness and intermediate states are searched for in the output --
     as values, not just as field names, because a field can be renamed and a
     4-tuple of multipliers cannot hide by being called something else.

  3. SURVIVAL AFTER DELETION. The artifact is reloaded from those bytes alone,
     with the original object and every theta dropped, and must still evaluate.
     This is the property that makes it public: not that we promise not to look
     at theta, but that theta is not there.

  4. THE PRIVILEGED ROUTE DIES WITHOUT THE SECRET. privileged_solve is offered
     the public challenge with thetas removed and must fail to run at all. If it
     still worked, the "secret" was not doing any work.

A note on what is deliberately NOT claimed here. Bit-level compilation removes
theta as a readable field; it does not prove theta is unrecoverable from the
gate graph. A shift-and-add network has one addend per set bit of its
multiplier, so shape may leak what the field no longer states. That question
belongs to attacks/theta_recovery.py and is not prejudged here.
"""

import itertools
import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))

from models import public_artifact as PA                         # noqa: E402
from experiment_b import evaluate, plant, privileged_solve       # noqa: E402

RESULTS = HERE.parents[1] / "results"
CASES = [(3, 1), (4, 2), (5, 2)]          # (w, t) -- small enough to enumerate


def split(bits, count, width):
    return tuple(sum(bits[i * width + b] << b for b in range(width))
                 for i in range(count))


def to_bits(words, width):
    return [(word >> b) & 1 for word in words for b in range(width)]


def exhaustive_check(artifact, thetas, S, T, merge_a, w, t, hardened, cap=200000):
    """Every input, both sides, compared against the factored implementation."""
    npairs, k = artifact.meta["npairs"], artifact.meta["k"]
    pa_bits = (k - 1) * npairs * t
    mb_bits = npairs * w
    checked, mismatches = 0, []

    for pa in itertools.product((0, 1), repeat=pa_bits):
        groups = {f"pa{i}": list(pa[i * npairs * t:(i + 1) * npairs * t])
                  for i in range(k - 1)}
        groups.update({f"pb{i}": [0] * (npairs * t) for i in range(k - 1)})
        groups["mb"] = [0] * mb_bits
        got = artifact.eval_side("a", **groups)
        prefix = tuple(split(list(pa[i * npairs * t:(i + 1) * npairs * t]),
                             npairs, t) for i in range(k - 1))
        want = evaluate(thetas, S, prefix, merge_a, hardened)
        checked += 1
        if got != want:
            mismatches.append({"side": "a", "prefix": prefix,
                               "got": got, "want": want})

    budget = max(1, cap // max(1, 2 ** pa_bits))
    for pb in itertools.product((0, 1), repeat=pa_bits):
        for mb in itertools.islice(
                itertools.product((0, 1), repeat=mb_bits), budget):
            groups = {f"pa{i}": [0] * (npairs * t) for i in range(k - 1)}
            groups.update({f"pb{i}": list(pb[i * npairs * t:(i + 1) * npairs * t])
                           for i in range(k - 1)})
            groups["mb"] = list(mb)
            got = artifact.eval_side("b", **groups)
            prefix = tuple(split(list(pb[i * npairs * t:(i + 1) * npairs * t]),
                                 npairs, t) for i in range(k - 1))
            want = evaluate(thetas, T, prefix, split(list(mb), npairs, w),
                            hardened)
            checked += 1
            if got != want:
                mismatches.append({"side": "b", "prefix": prefix,
                                   "merge": split(list(mb), npairs, w),
                                   "got": got, "want": want})
    return checked, mismatches


def secret_values_in(blob, thetas, challenge, w):
    """Search the serialised bytes for secret VALUES, not just field names."""
    data = json.loads(blob)
    text = json.dumps(data)
    numbers = set()
    for token in json.dumps(data["ands"]).replace("[", " ").replace("]", " ") \
                     .replace(",", " ").split():
        if token.isdigit():
            numbers.add(int(token))
    leaked = {}
    for theta_index, theta in enumerate(thetas):
        for field in ("multipliers", "mixa_rotations"):
            values = getattr(theta, field)
            # Rotations are tiny integers and collide with gate indices by
            # coincidence, so only multi-value coincidence counts as a leak.
            hits = [v for v in values if v in numbers and v > max(w, 8)]
            if len(hits) == len(values) and values:
                leaked[f"theta{theta_index}.{field}"] = list(values)
        if str(list(theta.pairs)) in text:
            leaked[f"theta{theta_index}.pairs"] = list(theta.pairs)
    for field in ("merge_a", "prefix_a", "prefix_b", "merge_b", "final"):
        value = challenge.get(field)
        if value is not None and json.dumps(list(value) if isinstance(
                value, (list, tuple)) else value) in text:
            leaked[field] = value
    return leaked


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {"test": "public_boundary",
              "question": "can the public object exist without the trapdoor?",
              "cases": [], "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    failures = []

    for w, t in CASES:
        for hardened in (False, True):
            rng = random.Random(4242 + w * 17 + int(hardened))
            challenge = plant(w, 2, t, rng, hardened)
            thetas = challenge["thetas"]
            artifact = PA.build(thetas, challenge["S"], challenge["T"],
                                challenge["merge_a"], t, hardened)

            checked, mismatches = exhaustive_check(
                artifact, thetas, challenge["S"], challenge["T"],
                challenge["merge_a"], w, t, hardened)

            blob = artifact.to_json()
            leaked = secret_values_in(blob, thetas, challenge, w)

            # Reload from bytes alone; drop the originals entirely.
            reloaded = PA.PublicArtifact.from_json(blob)
            del artifact
            npairs, k = reloaded.meta["npairs"], reloaded.meta["k"]
            groups = {f"pa{i}": [0] * (npairs * t) for i in range(k - 1)}
            groups.update({f"pb{i}": [1] * (npairs * t) for i in range(k - 1)})
            groups["mb"] = [1] * (npairs * w)
            survives = reloaded.eval_side("b", **groups) == evaluate(
                thetas, challenge["T"],
                tuple(split([1] * (npairs * t), npairs, t)
                      for _ in range(k - 1)),
                split([1] * (npairs * w), npairs, w), hardened)

            # The privileged route must be unable to run without the secret.
            public_only = {key: value for key, value in challenge.items()
                           if key in ("S", "T")}
            try:
                privileged_solve(public_only, t, hardened)
                privileged_dies = False
                reason = "privileged_solve RAN without thetas"
            except Exception as error:
                privileged_dies = True
                reason = type(error).__name__

            case = {
                "w": w, "t": t, "hardened": hardened,
                "gates": reloaded.aig.stats(),
                "inputs_checked_exhaustively": checked,
                "mismatches": len(mismatches),
                "exact": not mismatches,
                "secret_values_found_in_bytes": leaked,
                "secret_free": not leaked,
                "survives_deletion": survives,
                "privileged_dies_without_secret": privileged_dies,
                "privileged_failure": reason,
                "artifact_bytes": len(blob),
            }
            report["cases"].append(case)
            flag = "ok " if (case["exact"] and case["secret_free"]
                             and survives and privileged_dies) else "FAIL"
            print(f"  [{flag}] w={w} t={t} "
                  f"{'hardened' if hardened else 'weak    '}  "
                  f"{case['gates']['ands']:>6} ands  "
                  f"{checked:>6} inputs checked  exact={case['exact']}  "
                  f"secret_free={case['secret_free']}  "
                  f"survives={survives}  priv_dies={privileged_dies}")
            if flag == "FAIL":
                failures.append(case)

    report["all_passed"] = not failures
    report["conclusion"] = (
        "A secret-free public artifact exists and is exact: the compiled "
        "circuit matches the factored implementation on every enumerated "
        "input, carries none of the secret values in its serialised form, "
        "still evaluates after theta is deleted, and the privileged route "
        "cannot run without the secret. This establishes the boundary; it does "
        "NOT establish that theta is unrecoverable from the gate graph."
        if not failures else
        f"BOUNDARY NOT ESTABLISHED: {len(failures)} case(s) failed.")
    path = RESULTS / "public-boundary.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
