#!/usr/bin/env python3
"""
Evaluate Q18/Q19 DDT ray anisotropy & depth bias and Q22 top-bit seed collision transfer
across the Rainbow 2 hardening ladder (R0..R5).
"""
import json
from pathlib import Path
import random
import statistics
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/rainbow-spectrum"))

from models import rainbow as R  # noqa: E402
from og.ddt_spectrum import null_energy, row_energy  # noqa: E402
from research.rainbow2.algebraic_ladder_eval import (  # noqa: E402
    finalize_state_w,
    inject_w,
    mixA_w,
    mixB_w,
    rotr,
    scale_constants,
)

RESULTS_DIR = HERE / "results"


def eval_ddt_w12():
    w = 12
    theta = R.default_theta(w)
    m, r = theta.multipliers, theta.mixa_rotations
    mask = (1 << w) - 1
    rot = lambda v, k: ((v >> k) | (v << (w - k))) & mask if k else v
    r_inj = max(1, (19 * w) // 64)

    out = {}
    for mode, asym in (("R0_R2_sym_inj", False), ("R1_R3_R4_R5_asym_inj", True)):
        max_M_list, max_R1_list, max_S_list = [], [], []
        for seed in (101, 202, 303):
            rng = random.Random(seed)
            s0, s1 = rng.getrandbits(w), rng.getrandbits(w)
            g = [0] * (1 << w)
            for x in range(1 << w):
                t = (s0 - x) & mask
                a = (rot((t * m[0]) & mask, r[0]) * m[1]) & mask
                v = (s1 + (rot(x, r_inj) if asym else x)) & mask
                k = v ^ a
                c = rot((k * m[2]) & mask, r[1])
                g[a] = c
            null = null_energy(g, w, random.Random(999 + seed))
            max_M, max_R1, max_S = 0.0, 0.0, 0.0
            for r_val in range(0, w - 1):
                odds = [u for u in range(1, 1 << (w - r_val), 2)]
                en = {u: row_energy(g, (u << r_val) & mask, w) / null for u in odds}
                med = statistics.median(en.values())
                R1 = en[1] / med
                S_r = max(en.values())
                max_M = max(max_M, med)
                max_R1 = max(max_R1, R1)
                max_S = max(max_S, S_r)
            max_M_list.append(max_M)
            max_R1_list.append(max_R1)
            max_S_list.append(max_S)
        out[mode] = {
            "median_max_M_r": round(statistics.median(max_M_list), 2),
            "median_max_R_r_1": round(statistics.median(max_R1_list), 2),
            "median_max_S_r_all_odd_u": round(statistics.median(max_S_list), 2),
        }
    return out


def eval_q22_seed_transfer_w8():
    """
    Measure Q22 direct collision transfer rate under top-bit seed flip (delta = 1<<(w-1))
    at w=8 across R0..R5 on the 1-round message map (matching run_label_isolation.py).
    """
    w = 8
    mask = (1 << w) - 1
    th = R.default_theta(w)
    m, r = th.multipliers, th.mixa_rotations
    r_inj = max(1, (19 * w) // 64)

    def init_s01(rung: str, seed: int):
        olen = 32
        seed &= mask
        if rung == "r5":
            dom = (64 ^ ((olen * m[0]) & mask)) & mask
            return (
                ((rotr(seed ^ dom, 3, w) * m[1]) + 1) & mask,
                ((rotr((seed + olen) & mask, 5, w) * m[2]) ^ ((dom + 2) & mask)) & mask,
            )
        return ((seed + olen + 1) & mask, (seed + olen + 2) & mask)

    def H_rung(rung: str, theta_m3: int, seed: int, x: int) -> int:
        s0, s1 = init_s01(rung, seed)
        asym = rung in ("r1", "r3", "r4", "r5")
        t = (s0 - x) & mask
        a = (rotr((t * m[0]) & mask, r[0], w) * m[1]) & mask
        v = (s1 + (rotr(x, r_inj, w) if asym else x)) & mask
        c = rotr(((v ^ a) * m[2]) & mask, r[1], w)
        b = (c * theta_m3) & mask
        if rung in ("r4", "r5"):
            return (a ^ b) & mask
        return (a + b) & mask

    space = list(range(1, 1 << w, 2))
    results = {}
    for rung in ("r0", "r1", "r2", "r3", "r4", "r5"):
        rng = random.Random(12)
        hit_top = tot = 0
        hit_rand = 0
        for _ in range(200):
            theta = rng.choice(space)
            # find collision at seed L=0
            seen = {}
            wit = None
            for _ in range(1 << (w // 2 + 6)):
                x = rng.randrange(1 << w)
                hv = H_rung(rung, theta, 0, x)
                if hv in seen and seen[hv] != x:
                    wit = (seen[hv], x)
                    break
                seen.setdefault(hv, x)
            if wit is None:
                continue
            xa, xb = wit
            tot += 1
            if H_rung(rung, theta, 128, xa) == H_rung(rung, theta, 128, xb):
                hit_top += 1
            rseed = rng.randrange(1, 128)
            if H_rung(rung, theta, rseed, xa) == H_rung(rung, theta, rseed, xb):
                hit_rand += 1

        results[rung] = {
            "trials": tot,
            "topbit_seed_transfer_hits": hit_top,
            "topbit_seed_transfer_rate": round(hit_top / max(tot, 1), 4),
            "random_seed_transfer_hits": hit_rand,
            "random_seed_transfer_rate": round(hit_rand / max(tot, 1), 4),
            "chance_rate_w8": round(1 / 256.0, 4),
        }
    return results


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    res = {
        "ddt_w12_ablation": eval_ddt_w12(),
        "q22_seed_transfer_w8": eval_q22_seed_transfer_w8(),
    }
    out = RESULTS_DIR / "ddt-and-seed-eval.json"
    out.write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
