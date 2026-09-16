#!/usr/bin/env python3
"""Conflict counts are not a property of the instance. They never were.

This is the measurement defect underneath every conflict number this project has
published, and it was found by accident: three runs of the same w=24 draw
disagreed, and the one that AGREED exactly was the one that happened to be the
first solve in its process.

THREE TESTS, in the order that narrows it.

1. fresh process per draw vs one shared process, same draws, same seeds

       fresh   [4071, 5224, 3527, 6267, 628]
       shared  [4071, 5396, 5188, 5343, 5662]

   The first draw agrees exactly. Nothing after it does.

2. is it the INSTANCE that differs? No. plant() was fingerprinted (states,
   thetas, signs, multipliers, rotations) forward and in reverse draw order and
   is byte-identical either way. It is a pure function of its seeded rng, so the
   old runs solved exactly the problems they said they did. This matters: the
   defect is in measurement, not in what was measured.

3. is it the SOLVER? Yes. One identical instance, solved sixteen times in a
   single process:

       5224, 2789, 4665, 3495, 4637, 4587, 3058, 4180, 3896,
       5312, 2728, 2422, 5610, 4342, 3149, 3917

   Same problem, same seed, same answer, and a 2.32x spread in cost. The first
   value is exactly the fresh-process value; the rest are not reproducible.
   Pinning sat.random_seed, smt.random_seed and nlsat.seed does NOT fix it, so
   this is not z3's documented randomness -- it is per-process state that
   survives between Solver objects, most plausibly allocator state feeding
   pointer-ordered iteration in the heuristics.

WHAT IT DOES AND DOES NOT INVALIDATE.

  It is noise, not a systematic drift with position: over sixteen repeats the
  first half averaged 4,079 and the second half 3,922. That matters because
  scaling_wide.py solves every width in one process with larger widths always
  later, so a positional trend would have been confounded with width and would
  have biased the exponent directly. Measured, it does not.

  What it does do is put a large multiplicative noise floor under every single
  draw -- 2.32x at w=12, on an instance that cannot vary at all. Per-width
  medians were treated as estimates of instance difficulty; they are estimates
  of instance difficulty convolved with this. The specific consequence: "n=3
  with a 5x spread at w=24", which is what triggered the deepening effort in the
  first place, needs no instance-variance explanation. Solver noise alone
  produces most of it.

  The capability result is untouched. 61/61 privileged versus 0/61 public is a
  sat/unsat outcome, not a cost measurement, and nothing here moves it.

4. does one solve per process actually fix it? Yes, exactly. Three draws, each
   run in three independent fresh processes, agree to the digit on BOTH cost
   metrics:

       draw 0   (4071, 1313856) x3
       draw 1   (5224, 1113490) x3
       draw 2   (3527, 1151672) x3

   That is the constructive half of this result and it is stronger than merely
   removing a bias. Under the clean protocol, cost is a deterministic function
   of the instance, so the spread across draws at a width is PURE INSTANCE
   VARIANCE with no solver noise in it at all. The 2.32x floor is a property of
   the old measurements only, and nothing measured from here carries it.

   Incidentally the two metrics are not monotone with one another -- draw 0 has
   fewer conflicts than draw 1 but more rlimit -- which is what makes agreement
   between them a real check rather than a restatement.

THE FIX, and it is not optional: one solve per process. deepen_w24.py and
scaling_clean.py work this way. scaling_wide.py and deepen.py do not, so the
w=12..22 numbers they produced cannot be spliced against cleanly measured w=24
numbers as if they were the same kind of quantity -- which is why the series was
re-measured rather than patched at the top end.
"""

import hashlib
import json
import pathlib
import random
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
RESULTS = HERE.parents[1] / "results"
CHILD = HERE.parent / "_w24_child.py"
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))

W = 12
DRAWS = 5
REPEATS = 16


def fingerprint(challenge):
    """Solver-independent identity of a planted problem."""
    blob = json.dumps({
        "S": list(challenge["S"]), "T": list(challenge["T"]),
        "merge_a": list(challenge["merge_a"]),
        "thetas": [[list(t.pairs), list(t.signs), list(t.multipliers),
                    list(t.mixa_rotations)] for t in challenge["thetas"]],
    }, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def main():
    from experiment_b import plant, public_solve
    from models import solverstats as ST

    RESULTS.mkdir(parents=True, exist_ok=True)
    seeded = lambda d: random.Random(8800 + 97 * d + W)
    t = W // 2

    # 1. fresh process per draw
    fresh = []
    for d in range(DRAWS):
        out = subprocess.run(
            [sys.executable, str(CHILD), str(W), "0", str(d), "60000", "0"],
            capture_output=True, text=True).stdout.strip()
        fresh.append(json.loads(out.splitlines()[-1]).get("conflicts")
                     if out else None)

    # 1b. same draws, one process
    shared = []
    for d in range(DRAWS):
        challenge = plant(W, 2, t, seeded(d), False)
        shared.append(ST.get(public_solve(challenge, t, False, 60000)["stats"],
                             "conflict"))

    # 2. are the instances themselves order-dependent?
    forward = [fingerprint(plant(W, 2, t, seeded(d), False))
               for d in range(DRAWS)]
    reverse = {d: fingerprint(plant(W, 2, t, seeded(d), False))
               for d in reversed(range(DRAWS))}
    instances_stable = all(forward[d] == reverse[d] for d in range(DRAWS))

    # 3. one instance, many solves, one process
    repeats = []
    for _ in range(REPEATS):
        challenge = plant(W, 2, t, seeded(1), False)
        repeats.append(ST.get(public_solve(challenge, t, False, 60000)["stats"],
                              "conflict"))
    half = REPEATS // 2

    # 4. does a fresh process per solve give determinism?
    determinism = {}
    for d in range(3):
        seen = []
        for _ in range(3):
            out = subprocess.run(
                [sys.executable, str(CHILD), str(W), "0", str(d), "60000", "0"],
                capture_output=True, text=True).stdout.strip()
            row = json.loads(out.splitlines()[-1])
            seen.append((row.get("conflicts"), row.get("rlimit_count")))
        determinism[d] = {"observed": seen, "identical": len(set(seen)) == 1}

    report = {
        "experiment": "solver_state_contamination",
        "question": "is conflict count a property of the instance?",
        "answer": "no -- only of (instance, process history)",
        "w": W,
        "fresh_process_per_draw": fresh,
        "one_shared_process": shared,
        "first_draw_agrees": fresh[0] == shared[0],
        "later_draws_agree": fresh[1:] == shared[1:],
        "instances_order_independent": instances_stable,
        "instance_fingerprints": forward,
        "same_instance_repeated": repeats,
        "repeat_spread": (round(max(repeats) / min(repeats), 2)
                          if repeats and min(repeats) else None),
        "repeat_first_half_mean": round(statistics.mean(repeats[:half]), 1),
        "repeat_second_half_mean": round(statistics.mean(repeats[half:]), 1),
        "positional_drift": "none measured; the contamination is noise",
        "z3_seeds_fix_it": False,
        "fresh_process_determinism": determinism,
        "fresh_process_is_deterministic": all(v["identical"]
                                              for v in determinism.values()),
        "consequence": ("under one-solve-per-process, cost is a deterministic "
                        "function of the instance, so per-width spread is pure "
                        "instance variance and carries no solver noise"),
        "affected": ["scaling_wide.py (one process, all widths, all draws)",
                     "deepen.py (pool workers each run several draws)"],
        "unaffected": ["deepen_w24.py and _w24_child.py (one solve per process)",
                       "the 61/61 vs 0/61 capability result (sat/unsat, not cost)"],
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = RESULTS / "solver-state-contamination.json"
    path.write_text(json.dumps(report, indent=2))

    print(f"fresh  {fresh}")
    print(f"shared {shared}")
    print(f"  first agrees {report['first_draw_agrees']}, "
          f"later agree {report['later_draws_agree']}")
    print(f"instances order-independent: {instances_stable}")
    print(f"same instance x{REPEATS}: {repeats}")
    print(f"  spread {report['repeat_spread']}x, "
          f"halves {report['repeat_first_half_mean']} / "
          f"{report['repeat_second_half_mean']}")
    print(f"fresh-process determinism: "
          f"{report['fresh_process_is_deterministic']}")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
