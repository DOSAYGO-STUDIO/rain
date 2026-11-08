#!/usr/bin/env python3
"""Experiment B, re-run across the repaired public/private boundary.

The original measurement is void: public_solve was handed challenge["thetas"]
and built its formula from the secret multipliers, rotations, pairs and signs,
so "public" cost was never public. Everything downstream of it -- the 0.722
exponent, the representation gap, the interaction table -- measured generic SMT
against a specialised algorithm holding the same secret.

This measures the real thing. The attacker gets PublicArtifact and nothing else:
a bit-level circuit, Tseitin-encoded to clauses, with variable numbering, clause
order and literal order shuffled. No theta, no factor boundaries, no
intermediate states, no witness. The artifact is validated by
attacks/public_boundary.py, which checks exactness on every enumerated input at
toy widths and verifies that the bytes contain no secret values.

THREE INDEPENDENT SOLVERS, none of them z3. Every previous number in this
project came from one solver driven by an encoding written by the same process
that built the construction. Minisat22, Glucose4 and Cadical153 are separate
codebases with different heuristics, and disagreement between them is a finding
rather than noise.

DETERMINISTIC BUDGET. Censoring is by conflict count, not by clock, because wall
time on this machine was measured to censor on load rather than difficulty --
one fixed instance was recorded solved at 127.5s, solved at 385.1s, and censored
at >900s. A conflict budget censors the same instance the same way every time.

EVERY WITNESS IS VERIFIED against the factored implementation before it counts.
A SAT answer that cannot be replayed through the real map is a decoding bug, and
this project has already published one result that was an encoding artifact.

The comparison is against the privileged route measured on the SAME instances,
which costs exactly 4*2^(w/2) evaluations, so its exponent is 0.5 with no fit
required.
"""

import json
import math
import pathlib
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
RESULTS = HERE.parents[1] / "results"
CHILD = HERE.parent / "_public_sat_child.py"
PYTHON = "/tmp/satenv/bin/python"          # pysat lives in its own venv

WIDTHS = (6, 8, 10, 12, 14, 16, 18)
SOLVERS = ("minisat22", "glucose4", "cadical153")
DRAWS = 10
BUDGET = 4000000
PROCS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SYSTEM_FLOOR_MB = 250
ARTIFACT = RESULTS / "public-sat-scaling.json"


def system_free_mb():
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True,
                             timeout=5).stdout
    except subprocess.SubprocessError:
        return None
    page, total = 4096, 0
    for line in out.splitlines():
        if "page size of" in line:
            page = int(line.split("page size of")[1].split()[0])
        for label in ("Pages free:", "Pages inactive:", "Pages speculative:"):
            if line.startswith(label):
                total += int(line.split(":")[1].strip().rstrip("."))
    return total * page / 1048576


def fit(points):
    n = len(points)
    if n < 2:
        return None
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    denominator = sum((x - mx) ** 2 for x, _ in points)
    if not denominator:
        return None
    return sum((x - mx) * (y - my) for x, y in points) / denominator


def summarise(rows):
    out = {}
    for solver in SOLVERS:
        for hardened in (False, True):
            label = f"{solver}/{'hardened' if hardened else 'weak'}"
            per_width, points = {}, []
            for w in WIDTHS:
                mine = [r for r in rows if r["w"] == w
                        and r["solver"] == solver
                        and r["hardened"] == hardened]
                good = sorted(r["conflicts"] for r in mine
                              if r.get("event") and r.get("witness_verified")
                              and r.get("conflicts"))
                unverified = [r for r in mine
                              if r.get("event") and not r.get("witness_verified")]
                per_width[str(w)] = {
                    "n": len(good), "attempted": len(mine),
                    "unverified_witnesses": len(unverified),
                    "censored": sum(1 for r in mine
                                    if r.get("status") == "budget"),
                    "median": statistics.median(good) if good else None,
                    "raw": good,
                }
                if good:
                    points.append((w, math.log2(statistics.median(good))))
            slope = fit(points)
            out[label] = {"per_width": per_width,
                          "beta": round(slope, 4) if slope else None,
                          "gap_vs_privileged": (round(slope - 0.5, 4)
                                                if slope else None)}
    return out


def write(rows, started):
    report = {
        "experiment": "public_sat_scaling",
        "boundary": "attacker gets PublicArtifact only; validated by "
                    "attacks/public_boundary.py",
        "supersedes": "scaling-clean.json and every exponent derived from "
                      "public_solve, which received challenge['thetas']",
        "solvers": list(SOLVERS), "widths": list(WIDTHS), "draws": DRAWS,
        "budget_conflicts": BUDGET,
        "censoring": "deterministic conflict budget, not wall clock",
        "privileged_beta": 0.5,
        "privileged_cost": "exactly 4*2^(w/2) evaluations, no fit required",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": round(time.time() - started, 1),
        "raw": rows, "variants": summarise(rows),
    }
    ARTIFACT.write_text(json.dumps(report, indent=2))
    return report


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.time()
    rows = []
    if ARTIFACT.exists():
        try:
            rows = json.loads(ARTIFACT.read_text()).get("raw", [])
            print(f"resuming with {len(rows)} draws on disk")
        except json.JSONDecodeError:
            rows = []
    done = {(r["w"], r["solver"], r["hardened"], r["draw"]) for r in rows}

    pending = [(w, solver, hardened, draw)
               for w in WIDTHS for solver in SOLVERS
               for hardened in (False, True) for draw in range(DRAWS)
               if (w, solver, hardened, draw) not in done]
    total = len(pending) + len(rows)
    running = []

    while pending or running:
        while pending and len(running) < PROCS:
            free = system_free_mb()
            if free is not None and free < SYSTEM_FLOOR_MB and running:
                break
            w, solver, hardened, draw = pending.pop(0)
            proc = subprocess.Popen(
                [PYTHON, str(CHILD), str(w), str(w // 2),
                 "1" if hardened else "0", str(draw), solver, str(BUDGET)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            running.append({"proc": proc, "w": w, "solver": solver,
                            "hardened": hardened, "draw": draw})

        time.sleep(1.0)
        for job in list(running):
            if job["proc"].poll() is None:
                continue
            running.remove(job)
            stdout, stderr = job["proc"].communicate()
            if job["proc"].returncode != 0 or not stdout.strip():
                row = {"w": job["w"], "solver": job["solver"],
                       "hardened": job["hardened"], "draw": job["draw"],
                       "conflicts": None, "event": None,
                       "status": f"child_exit_{job['proc'].returncode}",
                       "stderr": stderr.strip()[-200:]}
            else:
                row = json.loads(stdout.strip().splitlines()[-1])
            rows.append(row)
            report = write(rows, started)
            print(f"  w={row['w']:>2} {row['solver']:<11} "
                  f"{'hardened' if row['hardened'] else 'weak    '} "
                  f"draw {row['draw']}: {row.get('status')} "
                  f"conflicts={row.get('conflicts')} "
                  f"verified={row.get('witness_verified')}  "
                  f"[{len(rows)}/{total}, {report['wall_seconds']:.0f}s]",
                  flush=True)

    report = write(rows, started)
    print()
    for label, entry in report["variants"].items():
        widths = " ".join(f"{entry['per_width'][str(w)]['median'] or 0:>9.0f}"
                          for w in WIDTHS)
        print(f"  {label:<24} {widths}   beta={entry['beta']} "
              f"gap={entry['gap_vs_privileged']}")
    print(f"\nwall {report['wall_seconds']}s -> {ARTIFACT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
