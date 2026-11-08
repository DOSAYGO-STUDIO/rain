"""Phase 3A: sequential composition of weak Rainbow factors.

    F(S; x_1..x_k) = R_{theta_k}( ... R_{theta_1}(S, x_1) ..., x_k)

Each round takes its own control words, so the attacker's freedom is k*|pairs|
words. The factored solver may use the intermediate states; the flat solver gets
only the input/output behaviour of F, with every factor boundary erased.

Also provides the exhaustive tools the milestone requires at toy width:
reachable sets, and the exact optimal merge cost.
"""

import itertools
import pathlib
import sys
from dataclasses import dataclass
from typing import Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from models import rainbow as R          # noqa: E402
from models import wordops as W          # noqa: E402


@dataclass(frozen=True)
class Composition:
    thetas: Tuple[R.Theta, ...]
    seed: int = 0
    alternate_mixers: bool = False   # False => every round uses the separable mixA

    @property
    def k(self):
        return len(self.thetas)

    @property
    def w(self):
        return self.thetas[0].w

    @property
    def controls_per_round(self):
        return len(self.thetas[0].pairs)

    def inner_flag(self, index):
        return self.alternate_mixers and (index % 2 == 1)

    def evaluate(self, state, controls):
        """controls is a tuple of k tuples, one control word per pair per round."""
        for index, (theta, control) in enumerate(zip(self.thetas, controls)):
            state = R.transition(state, control, theta,
                                 inner=self.inner_flag(index), seed=self.seed)
        return state

    def trace(self, state, controls):
        """Intermediate states, which only the factored solver may look at."""
        states = [state]
        for index, (theta, control) in enumerate(zip(self.thetas, controls)):
            state = R.transition(state, control, theta,
                                 inner=self.inner_flag(index), seed=self.seed)
            states.append(state)
        return states

    def all_controls(self):
        """Every control sequence; only tractable at toy sizes."""
        space = range(1 << self.w)
        per_round = list(itertools.product(space, repeat=self.controls_per_round))
        return itertools.product(per_round, repeat=self.k)

    def control_count(self):
        return (1 << (self.w * self.controls_per_round)) ** self.k


def reachable(composition, state, budget=None):
    """The exact set of states reachable from `state` under all controls.

    Returns {final_state: controls}. This is the flat attacker's ground truth at
    toy width, and the basis for the exhaustive optimal cost.
    """
    out = {}
    for index, controls in enumerate(composition.all_controls()):
        if budget is not None and index >= budget:
            break
        out.setdefault(composition.evaluate(state, controls), controls)
    return out


def optimal_merge(composition, state_a, state_b):
    """Exhaustive optimum: does any control pair merge them, and at what cost?

    Cost is counted as evaluations of F, which is the honest unit for comparing
    against the factored solver.
    """
    reach_a = {}
    evaluations = 0
    for controls in composition.all_controls():
        reach_a[composition.evaluate(state_a, controls)] = controls
        evaluations += 1
    for controls in composition.all_controls():
        evaluations += 1
        final = composition.evaluate(state_b, controls)
        if final in reach_a:
            return {
                "merged": True,
                "evaluations": evaluations,
                "controls_a": reach_a[final],
                "controls_b": controls,
                "state": final,
            }
    return {"merged": False, "evaluations": evaluations}


def invariants_before_last(composition, state, controls_prefix):
    """The invariants the final round will steer on, given earlier controls.

    This is exactly the quantity the factored solver birthday-searches, and the
    quantity the flat solver does not obviously have access to.
    """
    state_now = state
    for index in range(composition.k - 1):
        state_now = R.transition(state_now, controls_prefix[index],
                                 composition.thetas[index],
                                 inner=composition.inner_flag(index),
                                 seed=composition.seed)
    return R.invariants(state_now, composition.thetas[-1]), state_now
