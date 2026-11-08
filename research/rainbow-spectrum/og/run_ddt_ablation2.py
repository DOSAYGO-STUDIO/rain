"""Ablation matrix, redone as max over ALL r.

The first version sampled r in {0,2,4,6,8} and reported R at those fixed r. That
is invalid for any variant that MOVES the ray: randomising the rotations shifts
the peak from r=8 to anywhere in 7..11, so a fixed-r reading scored a relocated
ray as an absent one. Every row here reports

    max_r R_r(1)   and   argmax_r

so "the ray is gone" and "the ray moved" are distinguishable. M_r is summarised
by its value at the top of the range, where the depth effect is largest.
"""
import sys, pathlib, statistics
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import ddt_spectrum as D

def row(w, variant, what, seeds=(1, 2, 3), sample=16):
    peaks, args, mtop, mmax = [], [], [], []
    for s in seeds:
        spec = D.spectrum(w, variant=variant, theta_what=what, seed=s,
                          rs=range(0, w - 1), sample=sample)
        pk = max(spec, key=lambda r: spec[r][1])
        peaks.append(spec[pk][1]); args.append(pk)
        mtop.append(spec[max(spec)][0])
        mmax.append(max(spec[r][0] for r in spec))
    return (statistics.median(peaks), statistics.median(args),
            statistics.median(mmax), args)

for w in (12, 16):
    print(f"=== w={w}: ray reported as max over all r ===")
    print(f"{'variant':<22}{'max M_r':>9}{'max_r R_r(1)':>14}{'r*':>5}   r* per seed")
    for variant, what in ([(v, None) for v in D.VARIANTS] +
                          [("rainbow", "mults"), ("rainbow", "rots"),
                           ("rainbow", "both")]):
        name = variant if what is None else f"rainbow/rand-{what}"
        R1, rstar, M, args = row(w, variant, what)
        print(f"{name:<22}{M:9.1f}{R1:14.1f}{rstar:5.0f}   {args}", flush=True)
    print()
