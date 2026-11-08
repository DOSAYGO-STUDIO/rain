#!/usr/bin/env python3
"""
Orchestrate the Rainbow 2 hardening ladder SMHasher3 campaign on the cloud box:
Stage 1: Extended Sanity (native & nonnative) across all 18 registrations (r0..r5 x 64,128,256).
Stage 2: Uncontended pinned-core Speed benchmarks (taskset -c 0) across all 18 registrations.
Stage 3: Parallel full statistical suites (--test=All --extra) across all 18 registrations.
Stage 4: Parallel BadSeeds suites (--test=BadSeeds --extra) across all 6 rungs.
Every transcript is written to results/ and status.json is updated continuously.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parent
BIN = ROOT / "smhasher3/build/SMHasher3"
OUT = ROOT / "results"

RUNGS = ["r0", "r1", "r2", "r3", "r4", "r5", "r6"]
WIDTHS = [64, 128, 256]


def parse_log(path: Path):
    if not path.exists():
        return {"complete": False, "result": "missing"}
    text = path.read_text(errors="replace")
    summary = re.search(r"Overall result: (pass|FAIL)\s+\(\s*(\d+)\s*/\s*(\d+) passed\)", text)
    footer = re.search(r"Verification value is .*?Testing took ([\d.]+) seconds", text)
    bulk_matches = re.findall(r"Average\s+-\s+([\d.]+)\s+bytes/cycle\s+-\s+([\d.]+)\s+GiB/sec", text)
    small_match = re.search(r"Average\s+-\s+([\d.]+)\s+cycles/hash", text)
    failures = [line.strip() for line in text.splitlines() if "FAIL" in line and "Overall result" not in line]
    complete = bool(footer)
    if summary:
        res = summary.group(1)
    elif complete and not failures:
        res = "pass"
    else:
        res = "incomplete"
    return {
        "complete": complete,
        "result": res,
        "passed_checks": int(summary.group(2)) if summary else None,
        "total_checks": int(summary.group(3)) if summary else None,
        "seconds": float(footer.group(1)) if footer else None,
        "small_cycles_per_hash": float(small_match.group(1)) if small_match else None,
        "bulk_bytes_per_cycle": [float(x[0]) for x in bulk_matches] if bulk_matches else None,
        "bulk_gib_per_sec": [float(x[1]) for x in bulk_matches] if bulk_matches else None,
        "failure_lines": failures[:20],
    }


def run_cmd(job_id: str, cmd: list[str], log_path: Path):
    # Skip if already completed cleanly
    existing = parse_log(log_path)
    if existing.get("complete") and existing.get("result") in ("pass", "FAIL"):
        existing.update({
            "id": job_id,
            "command": cmd,
            "log_file": log_path.name,
            "exit_code": 0 if existing["result"] == "pass" else 1,
            "cached": True,
        })
        return existing
    t0 = time.time()
    with log_path.open("w") as f:
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        rc = proc.wait()
    t1 = time.time()
    meta = parse_log(log_path)
    meta.update({
        "id": job_id,
        "command": cmd,
        "log_file": log_path.name,
        "exit_code": rc,
        "started_unix": t0,
        "finished_unix": t1,
        "wall_seconds": round(t1 - t0, 2),
        "cached": False,
    })
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total-cpus", type=int, default=os.cpu_count() or 32)
    ap.add_argument("--stage", choices=["all", "triage", "full", "badseeds"], default="all")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    prov = {
        "platform": platform.platform(),
        "total_cpus": args.total_cpus,
        "binary_sha256": hashlib.sha256(BIN.read_bytes()).hexdigest(),
        "lscpu": subprocess.check_output(["lscpu"], text=True),
        "compiler": subprocess.check_output(["c++", "--version"], text=True),
        "smhasher3_commit": subprocess.check_output(["git", "-C", str(ROOT / "smhasher3"), "rev-parse", "HEAD"], text=True).strip(),
        "started_unix": time.time(),
    }
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")

    status_path = OUT / "status.json"
    status = {"stages": {}, "updated_unix": time.time()}
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text())
        except Exception:
            pass

    def save_status():
        status["updated_unix"] = time.time()
        status_path.write_text(json.dumps(status, indent=2) + "\n")

    # STAGE 1: Extended Sanity (native & nonnative) across all 18 hashes
    if args.stage in ("all", "triage"):
        sanity_jobs = []
        for r in RUNGS:
            for bits in WIDTHS:
                hname = f"rainbow2-{r}-{bits}"
                for endian in ("native", "nonnative"):
                    jid = f"sanity-{r}-{bits}-{endian}"
                    lpath = OUT / f"{jid}.log"
                    cmd = [
                        str(BIN), "--test=Sanity", "--extra", "--exit-code-on-failure",
                        f"--endian={endian}", "--ncpu=4", hname
                    ]
                    sanity_jobs.append((jid, cmd, lpath))

        sanity_results = []
        with ThreadPoolExecutor(max_workers=max(1, args.total_cpus // 4)) as ex:
            futs = {ex.submit(run_cmd, jid, cmd, lp): jid for jid, cmd, lp in sanity_jobs}
            for fut in as_completed(futs):
                sanity_results.append(fut.result())
                status["stages"]["sanity"] = sanity_results
                save_status()

        # STAGE 2: Uncontended Pinned-Core Speed Benchmarks across all 21 hashes
        speed_results = []
        for bits in WIDTHS:
            for r in RUNGS:
                hname = f"rainbow2-{r}-{bits}"
                jid = f"speed-{r}-{bits}-native"
                lpath = OUT / f"{jid}.log"
                cmd = [
                    "taskset", "-c", "0",
                    str(BIN), "--test=Speed", "--exit-code-on-failure",
                    "--endian=native", "--ncpu=1", hname
                ]
                res = run_cmd(jid, cmd, lpath)
                speed_results.append(res)
                status["stages"]["speed"] = speed_results
                save_status()

        # Fast All (default budget, no --extra) across all 21 hashes in parallel (8 workers x 4 threads = 32 cores)
        fast_jobs = []
        for bits in (256, 128, 64):
            for r in RUNGS:
                hname = f"rainbow2-{r}-{bits}"
                jid = f"fast-all-{r}-{bits}-native"
                lpath = OUT / f"{jid}.log"
                cmd = [
                    str(BIN), "--test=All", "--exit-code-on-failure",
                    "--endian=native", "--ncpu=4", hname
                ]
                fast_jobs.append((jid, cmd, lpath))

        fast_results = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(run_cmd, jid, cmd, lp) for jid, cmd, lp in fast_jobs]
            for fut in as_completed(futs):
                fast_results.append(fut.result())
                status["stages"]["fast_all"] = fast_results
                save_status()

    # STAGE 3: Full Extended All (--test=All --extra) across all 21 hashes (8 workers x 4 threads)
    if args.stage in ("all", "full"):
        full_all_jobs = []
        for bits in (256, 128, 64):
            for r in RUNGS:
                hname = f"rainbow2-{r}-{bits}"
                jid = f"extra-all-{r}-{bits}-native"
                lpath = OUT / f"{jid}.log"
                cmd = [
                    str(BIN), "--test=All", "--extra", "--exit-code-on-failure",
                    "--endian=native", "--ncpu=4", hname
                ]
                full_all_jobs.append((jid, cmd, lpath))

        full_all_results = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(run_cmd, jid, cmd, lp) for jid, cmd, lp in full_all_jobs]
            for fut in as_completed(futs):
                full_all_results.append(fut.result())
                status["stages"]["extra_all"] = full_all_results
                save_status()

    # STAGE 4: Extended BadSeeds (--test=BadSeeds --extra) across the ladder
    if args.stage in ("all", "badseeds"):
        badseeds_jobs = []
        threads_per_job = max(4, args.total_cpus // 6)
        for bits in (256, 128, 64):
            for r in RUNGS:
                hname = f"rainbow2-{r}-{bits}"
                jid = f"extra-badseeds-{r}-{bits}-native"
                lpath = OUT / f"{jid}.log"
                cmd = [
                    str(BIN), "--test=BadSeeds", "--extra", "--exit-code-on-failure",
                    "--endian=native", f"--ncpu={threads_per_job}", hname
                ]
                badseeds_jobs.append((jid, cmd, lpath))

        badseeds_results = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(run_cmd, jid, cmd, lp) for jid, cmd, lp in badseeds_jobs]
            for fut in as_completed(futs):
                badseeds_results.append(fut.result())
                status["stages"]["extra_badseeds"] = badseeds_results
                save_status()

    status["completed_unix"] = time.time()
    save_status()


if __name__ == "__main__":
    main()
