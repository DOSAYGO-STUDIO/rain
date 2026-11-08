"""Parameterized Rainbow model at arbitrary word width.

Theta carries every structural choice the spectrum is allowed to vary:
multipliers, rotations, which lanes are paired, injection orientation, and the
lane permutation.  The default Theta at w=64 is production Rainbow v3.7.1
exactly, which is what `selftest_matches_production` checks.

The steering weakness is deliberately retained and exposed through the abstract
interface the research program asks for:

    transition(theta, control, state) -> state
    steer(theta, state_a, state_b)    -> controls_a, controls_b
"""

from dataclasses import dataclass, field
from typing import Tuple

from . import wordops as W

# Production Rainbow v3.7.1 constants, as 64-bit references.
REFERENCE_MULTIPLIERS = (
    (1 << 64) - 1 - 58,      # P
    13166748625691186689,    # Q
    1573836600196043749,     # R
    1478582680485693857,     # S
    1584163446043636637,     # T
    1358537349836140151,     # U
    2849285319520710901,     # V
    2366157163652459183,     # W
)
REFERENCE_MIXA_ROTATIONS = (23, 29, 31, 37)
REFERENCE_MIXB_ROTATIONS = (23, 23)


@dataclass(frozen=True)
class Theta:
    """One member of the Rainbow spectrum."""

    w: int
    multipliers: Tuple[int, ...]
    mixa_rotations: Tuple[int, ...]
    mixb_rotations: Tuple[int, ...]
    # Which lanes form each control pair, and the sign each lane receives.
    pairs: Tuple[Tuple[int, int], ...] = ((0, 1), (2, 3))
    signs: Tuple[Tuple[int, int], ...] = ((-1, 1), (1, -1))
    lane_perm: Tuple[int, ...] = (3, 0, 1, 2)   # rotate_right
    label: str = "default"

    @property
    def lanes(self):
        return 4

    def __post_init__(self):
        if len(self.multipliers) != 8:
            raise ValueError("need 8 multipliers")
        for m in self.multipliers:
            if m % 2 == 0:
                raise ValueError("multipliers must be odd to stay invertible")
        seen = sorted(lane for pair in self.pairs for lane in pair)
        if seen != list(range(self.lanes)):
            raise ValueError("pairs must partition the lanes")
        for sa, sb in self.signs:
            if sa not in (-1, 1) or sb not in (-1, 1):
                raise ValueError("signs must be +/-1")


def default_theta(w, label="default"):
    """Production Rainbow scaled to width w; exactly Rainbow when w == 64."""
    return Theta(
        w=w,
        multipliers=tuple(W.make_odd(m, w) for m in REFERENCE_MULTIPLIERS),
        mixa_rotations=tuple(W.scale_rotation(r, w) for r in REFERENCE_MIXA_ROTATIONS),
        mixb_rotations=tuple(W.scale_rotation(r, w) for r in REFERENCE_MIXB_ROTATIONS),
        label=label,
    )


# --------------------------------------------------------------------- mixers
def mix_a(state, theta):
    """One independent map per pair; this separability is what splits the attack.

    The mixer acts on theta.pairs, the same pairing the injection uses. If the
    two disagree the weakness does not survive the round, which is precisely the
    condition spectrum.validate_weakness rejects.

    With the default pairing ((0,1),(2,3)) this is production Rainbow's mixA:
    pair 0 uses multipliers P,Q,R,S and rotations 23,29; pair 1 uses T,U,V,W
    and 31,37.
    """
    w = theta.w
    m = theta.multipliers
    r = theta.mixa_rotations
    out = list(state)
    for index, (i, j) in enumerate(theta.pairs):
        m0, m1, m2, m3 = m[4 * index:4 * index + 4]
        r0, r1 = r[2 * index], r[2 * index + 1]
        a = W.mul(W.rotr(W.mul(state[i], m0, w), r0, w), m1, w)
        b = W.mul(W.rotr(W.mul(W.xor(state[j], a, w), m2, w), r1, w), m3, w)
        out[i], out[j] = a, b
    return tuple(out)


def mix_b(state, theta, seed):
    w = theta.w
    m = theta.multipliers
    r = theta.mixb_rotations
    h0, h1, h2, h3 = state

    a = W.mul(W.rotr(W.mul(h1, m[6], w), r[0], w), m[7], w)
    b = W.xor(h2, W.add(a, seed, w), w)
    b = W.mul(W.rotr(W.mul(b, m[2], w), r[1], w), m[3], w)
    return (h0, b, a, h3)


def permute(state, theta):
    return tuple(state[i] for i in theta.lane_perm)


# ------------------------------------------------------------------ injection
def inject(state, controls, theta):
    """Apply one control word per pair, with that pair's signs."""
    w = theta.w
    out = list(state)
    for (i, j), (si, sj), x in zip(theta.pairs, theta.signs, controls):
        out[i] = W.add(out[i], si * x, w)
        out[j] = W.add(out[j], sj * x, w)
    return tuple(out)


def invariants(state, theta):
    """The functionals injection preserves, one per pair.

    For signs (si, sj) the preserved functional is sj*h_i - si*h_j:
      (-1, +1) -> h_i + h_j   (Rainbow's pair sum)
      (+1, +1) -> h_i - h_j   (a pair difference)
    Orientation therefore changes the invariant, not merely its sign.
    """
    w = theta.w
    out = []
    for (i, j), (si, sj) in zip(theta.pairs, theta.signs):
        out.append(W.sub(W.mul(sj % (1 << w), state[i], w),
                         W.mul(si % (1 << w), state[j], w), w))
    return tuple(out)


def transition(state, controls, theta, inner=False, seed=0):
    """One full block: inject, then the scheduled mixer."""
    state = inject(state, controls, theta)
    if inner:
        return permute(mix_b(state, theta, seed), theta)
    return mix_a(state, theta)


# -------------------------------------------------------------- the weakness
def steer(theta, state_a, state_b, free=None):
    """The weak-factor capability.

    Returns (controls_a, controls_b) driving both states to the SAME state in
    one block, or None when their invariants differ.  `free` supplies the freely
    chosen control for each pair; every choice works, so the solution set has
    size (2^w)^len(pairs).
    """
    w = theta.w
    if invariants(state_a, theta) != invariants(state_b, theta):
        return None
    if free is None:
        free = (0,) * len(theta.pairs)

    controls_a = list(free)
    controls_b = []
    for index, ((i, _j), (si, _sj)) in enumerate(zip(theta.pairs, theta.signs)):
        x = controls_a[index]
        # state_a[i] + si*x == state_b[i] + si*x'  =>  x' = x - si*(b_i - a_i)
        delta = W.sub(state_b[i], state_a[i], w)
        controls_b.append(W.sub(x, W.mul(si % (1 << w), delta, w), w))
    return tuple(controls_a), tuple(controls_b)


def mergeable(theta, state_a, state_b):
    return invariants(state_a, theta) == invariants(state_b, theta)


# --------------------------------------------------------- production anchor
def selftest_matches_production():
    """The w=64 default must agree with the independently verified Rainbow.

    Imports the Python implementation from research/rainbow/, which was checked
    against unmodified src/rainbow.cpp and the shipped rainsum CLI.
    """
    import importlib.util
    import pathlib

    here = pathlib.Path(__file__).resolve()
    verifier = here.parents[2] / "rainbow" / "verify_pair_sum.py"
    spec = importlib.util.spec_from_file_location("rainbow_verifier", verifier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    theta = default_theta(64)
    if theta.multipliers != REFERENCE_MULTIPLIERS:
        return False, "w=64 multipliers differ from production"
    if theta.mixa_rotations != REFERENCE_MIXA_ROTATIONS:
        return False, "w=64 mixA rotations differ from production"

    import random
    rng = random.Random(20260915)
    for _ in range(2000):
        state = tuple(rng.getrandbits(64) for _ in range(4))
        seed = rng.getrandbits(64)
        if tuple(module.mix_a(list(state))) != mix_a(state, theta):
            return False, "mixA disagrees with the verified implementation"
        if tuple(module.mix_b(list(state), seed)) != mix_b(state, theta, seed):
            return False, "mixB disagrees with the verified implementation"
        if tuple(module.rotate_right(list(state))) != permute(state, theta):
            return False, "lane permutation disagrees"
    return True, "w=64 model reproduces production Rainbow"
