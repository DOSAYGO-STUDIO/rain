"""Does the DDT ray depend on the 2-adic DISTANCE of the multipliers, or on bits?

Q18 showed random multipliers destroy the ray. That says the constants matter but
not how. The collision-family side is governed by 2-adic distance between
multipliers (v2(m' - m) controls transport), so the question is whether the same
metric governs the differential resonance.

THE DISCRIMINATOR. Three perturbation families that all sit at EXACTLY the same
2-adic distance j from the real multiplier m (m odd throughout):

    add:  m' = m + 2^j              m' - m = 2^j        v2 = j
    mul:  m' = m * (1 + 2^j)        m' - m = m * 2^j    v2 = j
    xor:  m' = m XOR 2^j            m' - m = +/- 2^j    v2 = j

If ray strength is a function of v2(m' - m) alone, all three curves coincide at
every j. If they diverge, the resonance is about specific bit patterns and the
two halves of the research do NOT reconnect through the 2-adic metric. Same
valuation, three different words: the test is free of the usual confound where a
"closer" constant is also a more similar one.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import ddt_spectrum as D
from models import rainbow as R

FAMILIES = {
    "add": lambda m, j, w: (m + (1 << j)) & ((1 << w) - 1),
    "mul": lambda m, j, w: (m * (1 + (1 << j))) & ((1 << w) - 1),
    "xor": lambda m, j, w: m ^ (1 << j),
}


def perturbed(w, which, j, family):
    base = R.default_theta(w)
    mults = list(base.multipliers)
    mults[which] = FAMILIES[family](mults[which], j, w)
    assert mults[which] & 1, "multiplier must stay odd"
    return R.Theta(w=w, multipliers=tuple(mults),
                   mixa_rotations=base.mixa_rotations,
                   mixb_rotations=base.mixb_rotations, label=f"{family}-{j}")


def peak(w, theta, sample=16):
    spec = D.spectrum(w, rs=range(0, w - 1), sample=sample, theta=theta)
    r = max(spec, key=lambda r: spec[r][1])
    return spec[r][1], r, max(spec[k][0] for k in spec)


def sweep(w, which):
    base = peak(w, R.default_theta(w))
    print(f"--- w={w}, perturbing m[{which}] "
          f"({'A branch' if which < 2 else 'C branch'}); "
          f"real: R={base[0]:.1f} at r*={base[1]}, max M_r={base[2]:.1f} ---")
    print("   j |      add        |      mul        |      xor        "
          "   (R at r*,  r*)")
    for j in range(1, w):
        cells = []
        for fam in ("add", "mul", "xor"):
            Rv, rs, _ = peak(w, perturbed(w, which, j, fam))
            cells.append(f"{Rv:8.1f} @{rs:<3}")
        print(f"  {j:>2} | " + " | ".join(cells), flush=True)
    print()


for which in (0, 1, 2, 3):
    sweep(12, which)
