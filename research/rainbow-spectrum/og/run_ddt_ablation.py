"""Ablation matrix and width scaling for the DDT depth/ray decomposition."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import ddt_spectrum as D

W = 12
RS = [0, 2, 4, 6, 8]

print("=" * 74)
print("ABLATION MATRIX  (w=12, real Rainbow constants unless stated)")
print("  M_r = median over odd u of row energy / shuffle null   -> DEPTH bias")
print("  R_r(1) = E_r(1) / M_r                                  -> RAY anisotropy")
print("=" * 74)
print(f"{'variant':<24}" + "".join(f"  M_{r}   R_{r}(1)" for r in RS), flush=True)

rows = []
cases = [(v, None) for v in D.VARIANTS] + [
    ("rainbow", "mults"), ("rainbow", "rots"), ("rainbow", "both")]
for variant, what in cases:
    name = variant if what is None else f"rainbow/rand-{what}"
    inst = 3 if what else 1
    spec = D.spectrum(W, variant=variant, theta_what=what, rs=RS, instances=inst)
    cells = "".join(f"  {spec[r][0]:5.2f} {spec[r][1]:8.2f}" for r in RS)
    print(f"{name:<24}{cells}", flush=True)
    rows.append((name, spec))

print()
print("=" * 74)
print("WIDTH SCALING  (real Rainbow; where does the ray effect turn on?)")
print("=" * 74)
for w in (10, 12, 14, 16):
    spec = D.spectrum(w, rs=range(0, w - 1))
    best_r = max(spec, key=lambda r: spec[r][1])
    line = "  ".join(f"r={r}:{spec[r][1]:.1f}" for r in sorted(spec))
    print(f"w={w:>2}  peak r*={best_r:>2}  R={spec[best_r][1]:7.2f}   "
          f"w-r*={w-best_r:>2}   r*/w={best_r/w:.2f}", flush=True)
    print(f"      M_r: " + " ".join(f"{spec[r][0]:.1f}" for r in sorted(spec)), flush=True)
    print(f"      R_r(1): {line}", flush=True)
