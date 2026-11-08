"""Where the ray effect turns ON: constant r, r ~ w/2, or w - r constant?

The argmax is a bad observable -- the peak is a broad plateau (w=12 reads
41.8, 39.4, 45.3 at r=5,6,7) so r* is within noise over several r. The ONSET is
sharp: R_r(1) sits near the depth baseline and then jumps by an order of
magnitude within one step of r. So r_on = min{ r : R_r(1) >= THRESH } is measured
here instead, over several instances, together with the turn-off r_off.

The second half asks whether r_on is set by the rotation amounts. If randomising
r0, r1 leaves r_on where it was, the mechanism is about how many high bits stay
active, not about where the rotations land.
"""
import sys, pathlib, statistics, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import ddt_spectrum as D
from models import rainbow as R

THRESH = 10.0


def onset(w, theta_what=None, seed=1, sample=16):
    spec = D.spectrum(w, theta_what=theta_what, seed=seed, rs=range(0, w - 1),
                      sample=sample)
    hot = [r for r in sorted(spec) if spec[r][1] >= THRESH]
    peak = max(spec, key=lambda r: spec[r][1])
    return (hot[0] if hot else None, hot[-1] if hot else None,
            peak, spec[peak][1], spec)


print("ONSET / OFFSET of ray anisotropy, real Rainbow   (R_r(1) >= 10)")
print("  w   r_on  r_off   w-r_on  r_on/w    peak r*   R(r*)")
for w in (10, 12, 14, 16, 18):
    runs = [onset(w, seed=s) for s in (1, 2, 3)]
    ons = [r[0] for r in runs if r[0] is not None]
    offs = [r[1] for r in runs if r[1] is not None]
    if not ons:
        print(f" {w:>2}   never reaches threshold")
        continue
    on, off = statistics.median(ons), statistics.median(offs)
    pk = statistics.median([r[2] for r in runs])
    rv = statistics.median([r[3] for r in runs])
    print(f" {w:>2}   {on:>4.1f}  {off:>5.1f}   {w-on:>6.1f}  {on/w:>6.2f}"
          f"   {pk:>7.1f}  {rv:>7.1f}    onsets={ons} offs={offs}", flush=True)

print()
print("Does the onset track the ROTATION amounts?  (w=16, r0/r1 randomised)")
print("  rotations      r_on   w-r_on   peak r*    R(r*)")
base = R.default_theta(16)
print(f"  {str(base.mixa_rotations[:2]):<14} (real)", flush=True)
for seed in (11, 12, 13, 14, 15):
    th = D.randomised_theta(16, seed, "rots")
    on, off, pk, rv, _ = onset(16, theta_what="rots", seed=seed)
    got = "none" if on is None else f"{on:>4}"
    print(f"  {str(th.mixa_rotations[:2]):<14} {got}   {'' if on is None else 16-on:>6}"
          f"   {pk:>7}  {rv:>7.1f}", flush=True)
