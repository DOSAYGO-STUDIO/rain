#!/usr/bin/env python3
"""The scaling series, re-measured so that it means what it says.

scaling_wide.py produced the w=12..18 medians that every drift verdict in this
project has been computed from. It solves every width and every draw inside one
process, and solver_state_contamination.py shows that is not a valid way to
measure cost: conflict count is a property of (instance, process history), not
of the instance. One fixed instance solved sixteen times in a single process
spans 2.32x, while the same instance in a fresh process reproduces exactly.

So the series is re-run with one solve per process. Nothing else changes -- same
widths, same seed stream, same generator, same public_solve, same 900s budget.
This is a re-measurement, not a redesign, and it is deliberately boring: if the
exponent moves, it moves because the old numbers were noise, and if it does not,
the old conclusion is confirmed on data that can be reproduced.

WHY IT IS AFFORDABLE NOW. Two beliefs that made this look expensive were both
measured false today: a z3 instance at these widths holds ~93 MB flat rather
than a huge clause database, and the OOM kills were collateral from the desktop
rather than this workload. So draws run three-wide instead of one-wide, and
w=12..22 is about twenty-five minutes rather than a day.

WALL TIME IS NOT USED AS A MEASUREMENT. timeout_validity.py showed one
deterministic instance recorded as solved in 127.5s, solved in 385.1s and
censored at >900s depending only on how busy the machine was. The 900s budget is
kept solely so a pathological draw cannot hang the run; every draw also records
z3's rlimit count, which is deterministic and immune to contention. Any draw
that does hit the clock is reported as censored and never counted as its cap.

w=24 is not run here. deepen-w24.json already holds it, measured the same way.
"""

import json
import pathlib
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
RESULTS = HERE.parents[1] / "results"
CHILD = HERE.parent / "_w24_child.py"          # generic: takes w as argv

WIDTHS = (12, 14, 16, 18, 20, 22)
DRAWS = 10
TIMEOUT_MS = 900000
PROCS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
RSS_CAP_MB = 800
SYSTEM_FLOOR_MB = 250
ARTIFACT = RESULTS / "scaling-clean.json"


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


def rss_mb(pid):
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.strip()) / 1024 if out.strip() else None
    except (ValueError, subprocess.SubprocessError):
        return None


def summarise(rows):
    out = {}
    for hardened in (False, True):
        label = "hardened" if hardened else "weak"
        per_width = {}
        for w in WIDTHS:
            mine = [r for r in rows
                    if r["w"] == w and r["hardened"] == hardened]
            solved = sorted(r["conflicts"] for r in mine
                            if r.get("event") and r["conflicts"])
            censored = [r for r in mine if r.get("event") is False]
            rlimits = sorted(r["rlimit_count"] for r in mine
                             if r.get("event") and r.get("rlimit_count"))
            per_width[str(w)] = {
                "n": len(solved), "attempted": len(mine),
                "censored": len(censored),
                "median": statistics.median(solved) if solved else None,
                "median_rlimit": statistics.median(rlimits) if rlimits else None,
                "raw": solved,
            }
        out[label] = {
            "per_width": per_width,
            # Shaped like scaling-wide.json so the frozen analysis can consume
            # it without a single line of the rule being rewritten.
            "median_conflicts": {w: row["median"]
                                 for w, row in per_width.items() if row["median"]},
            "n": {w: row["n"] for w, row in per_width.items()},
        }
    return out


def write(rows, started):
    report = {
        "experiment": "scaling_clean",
        "purpose": "re-measure the scaling series with one solve per process",
        "supersedes": "scaling-wide.json (all draws in a single process)",
        "reason": "results/solver-state-contamination.json",
        "widths": list(WIDTHS), "draws": DRAWS, "timeout_ms": TIMEOUT_MS,
        "isolation": "one child process per draw; artifact rewritten per draw",
        "w24_lives_in": "deepen-w24.json (measured the same way)",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": round(time.time() - started, 1),
        "raw": rows,
        "variants": summarise(rows),
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
    done = {(r["w"], r["hardened"], r["draw"]) for r in rows}

    pending = [(w, hardened, draw)
               for w in WIDTHS for hardened in (False, True)
               for draw in range(DRAWS)
               if (w, hardened, draw) not in done]
    total = len(pending) + len(rows)
    running = []

    while pending or running:
        while pending and len(running) < PROCS:
            free = system_free_mb()
            if free is not None and free < SYSTEM_FLOOR_MB and running:
                break
            w, hardened, draw = pending.pop(0)
            proc = subprocess.Popen(
                [sys.executable, str(CHILD), str(w), "1" if hardened else "0",
                 str(draw), str(TIMEOUT_MS), "0"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            running.append({"proc": proc, "w": w, "hardened": hardened,
                            "draw": draw, "peak": 0.0, "killed": False})

        time.sleep(1.0)

        for job in list(running):
            proc = job["proc"]
            current = rss_mb(proc.pid)
            if current:
                job["peak"] = max(job["peak"], current)
                if current > RSS_CAP_MB:
                    job["killed"] = True
                    proc.kill()
            if proc.poll() is None:
                continue
            running.remove(job)
            stdout, stderr = proc.communicate()
            if proc.returncode != 0 or not stdout.strip():
                row = {"w": job["w"], "hardened": job["hardened"],
                       "draw": job["draw"], "conflicts": None, "event": None,
                       "status": "memory_killed_by_parent" if job["killed"]
                                 else f"child_exit_{proc.returncode}",
                       "stderr": stderr.strip()[-200:]}
            else:
                row = json.loads(stdout.strip().splitlines()[-1])
            row["observed_peak_rss_mb"] = round(job["peak"], 1)
            rows.append(row)
            report = write(rows, started)
            mark = {True: "solved", False: "CENSORED",
                    None: "failed"}[row.get("event")]
            print(f"  w={row['w']:>2} "
                  f"{'hardened' if row['hardened'] else 'weak    '} "
                  f"draw {row['draw']}: conflicts={row.get('conflicts')} {mark} "
                  f"({row.get('seconds')}s)  [{len(rows)}/{total}, "
                  f"elapsed {report['wall_seconds']:.0f}s]", flush=True)

    report = write(rows, started)
    for label in ("weak", "hardened"):
        print(f"\n{label}:")
        for w in WIDTHS:
            row = report["variants"][label]["per_width"][str(w)]
            print(f"  w={w:>2}  n={row['n']}/{row['attempted']}  "
                  f"median={row['median']}  "
                  f"median_rlimit={row['median_rlimit']}"
                  + (f"  CENSORED {row['censored']}" if row["censored"] else ""))
    print(f"\nwall {report['wall_seconds']}s -> {ARTIFACT}")
    print("next: apply the frozen drift test to this and deepen-w24.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
