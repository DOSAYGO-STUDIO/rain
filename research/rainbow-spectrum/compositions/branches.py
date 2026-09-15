"""Phases 3B and 3C: composition operators other than sequential rounds.

Branch A (sequential) is in sequential.py. It turned out to be the weakest kind
of composition for this purpose: every round keeps its own invariant, so the
attacker simply merges at whichever round is cheapest and depth buys nothing.

Both operators here must satisfy the same admissibility rule as the spectrum:
the cheap steering has to SURVIVE. That constrains their design sharply.

  B  ParallelAlgebraic: several factors over the SAME injected state, combined
     lane-wise. The single shared injection is what keeps a common coset, so
     steering still composes; the public object is a sum of instances rather
     than a visible chain.

  C  CrossParameterized: the mixer's parameters are chosen by the CURRENT pair
     sums. Selecting on the state itself would break the weakness -- injection
     moves the state, so different controls would land in different parameter
     regions and the coset would fragment. Selecting on the pair sums, exactly
     the quantities injection preserves, keeps the selector constant across the
     whole control range. Cheap steering survives, while the weak coordinate
     system now varies per sigma-class, which is what a global invariant search
     cannot follow.
"""

import pathlib
import sys
from dataclasses import dataclass
from typing import Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from models import rainbow as R          # noqa: E402
from models import wordops as W          # noqa: E402


def _combine(a, b, w, how):
    if how == "add":
        return tuple(W.add(x, y, w) for x, y in zip(a, b))
    if how == "xor":
        return tuple(W.xor(x, y, w) for x, y in zip(a, b))
    raise ValueError(f"unknown combine {how}")


@dataclass(frozen=True)
class ParallelAlgebraic:
    """Branch B. Each round injects ONCE, then several mixers run on that same
    injected state and their outputs are combined lane-wise."""

    thetas: Tuple[R.Theta, ...]          # the parallel factors (>= 2)
    k: int = 2                           # how many such rounds
    combine: str = "add"
    seed: int = 0

    @property
    def w(self):
        return self.thetas[0].w

    @property
    def controls_per_round(self):
        return len(self.thetas[0].pairs)

    @property
    def injection_theta(self):
        """Injection is global: all factors must agree on pairs and signs, or
        there is no common coset and the weakness does not survive."""
        return self.thetas[0]

    def round(self, state, controls):
        injected = R.inject(state, controls, self.injection_theta)
        out = R.mix_a(injected, self.thetas[0])
        for theta in self.thetas[1:]:
            out = _combine(out, R.mix_a(injected, theta), self.w, self.combine)
        return out

    def evaluate(self, state, controls):
        for control in controls:
            state = self.round(state, control)
        return state

    def trace(self, state, controls):
        states = [state]
        for control in controls:
            state = self.round(state, control)
            states.append(state)
        return states


@dataclass(frozen=True)
class CrossParameterized:
    """Branch C. The mixer is selected by the pair sums of the incoming state.

    Injection parameters are global and fixed, so sigma is well defined and
    preserved; only the mixer varies. Every palette member shares the pairing,
    so per-pair independence -- and therefore divide-and-conquer -- is retained.
    """

    palette: Tuple[R.Theta, ...]
    k: int = 2
    seed: int = 0

    @property
    def w(self):
        return self.palette[0].w

    @property
    def controls_per_round(self):
        return len(self.palette[0].pairs)

    @property
    def injection_theta(self):
        return self.palette[0]

    def select(self, state):
        """Chosen from sigma alone, which injection cannot change."""
        s1, s2 = R.invariants(state, self.injection_theta)
        return self.palette[(s1 ^ s2) % len(self.palette)]

    def round(self, state, controls):
        theta = self.select(state)          # decided BEFORE injection
        return R.mix_a(R.inject(state, controls, self.injection_theta), theta)

    def evaluate(self, state, controls):
        for control in controls:
            state = self.round(state, control)
        return state

    def trace(self, state, controls):
        states = [state]
        for control in controls:
            state = self.round(state, control)
            states.append(state)
        return states


def steering_survives(composition, rng, trials=200):
    """Admissibility: does one round still merge two equal-sigma states?

    This is the check that rejects the naive version of branch C, where the
    mixer is selected from the whole state instead of from sigma.
    """
    w = composition.w
    inj = composition.injection_theta
    merged = 0
    for _ in range(trials):
        sa = tuple(rng.getrandbits(w) for _ in range(4))
        sb = list(tuple(rng.getrandbits(w) for _ in range(4)))
        for (i, j), (si, sj), inv in zip(inj.pairs, inj.signs, R.invariants(tuple(sa), inj)):
            target = W.sub(W.mul(sj % (1 << w), sb[i], w), inv, w)
            sb[j] = target if si == 1 else W.neg(target, w)
        sb = tuple(sb)
        got = R.steer(inj, sa, sb, free=tuple(rng.getrandbits(w) for _ in inj.pairs))
        if got is None:
            continue
        if composition.round(sa, got[0]) == composition.round(sb, got[1]):
            merged += 1
    return {"trials": trials, "merged": merged, "survives": merged == trials}


@dataclass(frozen=True)
class NaiveCrossParameterized(CrossParameterized):
    """Deliberately broken control: selects on the whole state, not on sigma.

    Kept because the program asks that failed constructions be recorded. This
    one should FAIL steering_survives, demonstrating why the selector must read
    an injection-invariant quantity.
    """

    def select(self, state):
        return self.palette[(state[0] ^ state[2]) % len(self.palette)]
