"""The prediction: a ray at depth r survives a perturbation of m[1] at
valuation j iff r + j >= w.

Reason: the ray d = 2^r reaches the outer A multiply as a difference of
valuation ~r; perturbing m[1] by delta with v2(delta) = j changes the product
difference by ~2^r * delta, which vanishes mod 2^w exactly when r + j >= w. That
is the pair-sum transport law  v2(m' - m) + v2(e) >= w  applied inside the DDT.

The measured recovery thresholds already satisfy j_rec = w - r_off at all four
widths (5,5,6,7 against r_off 5,7,8,9). This prints the full (j, r) map so the
boundary can be seen rather than inferred from two summaries.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import ddt_spectrum as D
from og.run_ddt_perturb import perturbed
from models import rainbow as R

for w in (12, 14):
    print(f"=== w={w}: R_r(1) for m[1] perturbed at valuation j (family add) ===")
    print("       predicted-preserved region is r >= w - j, marked with |")
    real = D.spectrum(w, rs=range(0, w - 1), sample=16, theta=R.default_theta(w))
    hdr = "  j \\ r " + "".join(f"{r:>7}" for r in range(w - 1))
    print(hdr)
    print("   real " + "".join(f"{real[r][1]:7.1f}" for r in range(w - 1)))
    for j in range(1, w):
        spec = D.spectrum(w, rs=range(0, w - 1), sample=16,
                          theta=perturbed(w, 1, j, "add"))
        cells = []
        for r in range(w - 1):
            sep = "|" if r == w - j else " "
            cells.append(f"{sep}{spec[r][1]:6.1f}")
        print(f"  {j:>2}     " + "".join(cells), flush=True)
    print()
