"""A public artifact: the composed map as gates, with theta deleted.

THE BOUNDARY THIS ENFORCES. Experiment B did not test a trapdoor because its
"public" solver was handed challenge["thetas"] -- the same factorization the
privileged solver uses -- and built its formula from the secret multipliers,
rotations, pairs and signs. So the gap it measured was generic SMT against a
specialised sigma-matching algorithm holding identical structural information.
That is an algorithmic gap; it says nothing about representation.

A valid public artifact has to satisfy something much stricter:

  1. public evaluation needs only the artifact and public challenge data;
  2. every theta, factor boundary, intermediate state, planted witness, sigma,
     pairing, sign, rotation, multiplier and generation trace can be DELETED;
  3. after deletion the public evaluator and every public attack still run;
  4. the privileged route dies when the secret is withheld.

So the artifact here is a bit-level circuit. Word level is not sufficient and
this is worth being precise about: models/symbolic.py builds an exact word-level
DAG of the same composition, but a multiply-by-multiplier appears in it as a
literal const node, so publishing that DAG publishes theta outright. At bit
level each constant multiply becomes a fixed adder network and the constant is
no longer a field anyone can read off.

That is necessary, not sufficient, and the difference is the whole question. A
shift-and-add network has one addend per set bit of the multiplier, so the gate
graph may still betray theta through its shape. That is measured in
attacks/theta_recovery.py rather than assumed either way here.

WHAT IS BAKED IN. S, T and the canonical merge_a are public challenge data, so
they are compiled in as constants. The free inputs are exactly what an attacker
must find: prefix_A, prefix_B, merge_B. Two output vectors are published, one
per side, because an attacker needs to evaluate the sides separately to attempt
anything of meet-in-the-middle shape -- withholding that would be hiding the
problem rather than protecting the secret.
"""

import json

from .aig import Aig, FALSE, TRUE


class PublicArtifact:
    """Gates and public data. Contains no theta and no witness."""

    def __init__(self, aig, groups, out_a, out_b, meta):
        self.aig = aig
        self.groups = groups          # name -> list of input literals
        self.out_a = out_a            # 4w literals
        self.out_b = out_b
        self.meta = meta              # w, lanes, k, t, npairs, hardened

    # ------------------------------------------------------------- evaluation
    def _assign(self, values):
        assignment = {}
        for name, literals in self.groups.items():
            supplied = values.get(name)
            if supplied is None:
                raise KeyError(f"missing input group {name}")
            for literal, bit in zip(literals, supplied):
                assignment[literal] = bit
        if len(assignment) != len(self.aig.inputs):
            raise ValueError("input width mismatch")
        return assignment

    def eval_side(self, side, **values):
        outputs = self.out_a if side == "a" else self.out_b
        bits = self.aig.evaluate(outputs, self._assign(values))
        w, lanes = self.meta["w"], self.meta["lanes"]
        return tuple(sum(bits[lane * w + i] << i for i in range(w))
                     for lane in range(lanes))

    # ---------------------------------------------------------- serialisation
    def to_json(self):
        """Everything needed to evaluate, and provably nothing else."""
        return json.dumps({
            "format": "rainbow-spectrum/public-artifact/1",
            "meta": self.meta,
            "inputs": self.aig.names,
            "groups": {k: v for k, v in self.groups.items()},
            "ands": self.aig.ands,
            "out_a": self.out_a, "out_b": self.out_b,
        })

    @staticmethod
    def from_json(blob):
        data = json.loads(blob)
        aig = Aig()
        for name in data["inputs"]:
            aig.input(name)
        aig.ands = [tuple(pair) for pair in data["ands"]]
        return PublicArtifact(aig, {k: list(v) for k, v in data["groups"].items()},
                              data["out_a"], data["out_b"], data["meta"])


def _bits(aig, group, count, name):
    return [aig.input(f"{name}{i}") for i in range(count)]


def build(thetas, S, T, merge_a, t, hardened):
    """Compile the challenge into gates. This is the ONLY place theta is read."""
    w = thetas[0].w
    lanes = len(S)
    npairs = len(thetas[0].pairs)
    k = len(thetas)
    aig = Aig()

    groups = {}
    # Inputs must all be declared before any gate is built.
    for round_index in range(k - 1):
        groups[f"pa{round_index}"] = _bits(aig, None, npairs * t, f"pa{round_index}_")
        groups[f"pb{round_index}"] = _bits(aig, None, npairs * t, f"pb{round_index}_")
    groups["mb"] = _bits(aig, None, npairs * w, "mb_")

    def words(group, width):
        literals = groups[group]
        return [literals[i * width:(i + 1) * width] for i in range(npairs)]

    def widen(word, width):
        """A t-bit control is a w-bit value with the top bits zero."""
        return list(word) + [FALSE] * (w - width)

    def mix(state, theta):
        m, r = theta.multipliers, theta.mixa_rotations
        out = list(state)
        for index, (i, j) in enumerate(theta.pairs):
            m0, m1, m2, m3 = m[4 * index:4 * index + 4]
            r0, r1 = r[2 * index], r[2 * index + 1]
            a = aig.mul_const(aig.rotr(aig.mul_const(state[i], m0, w), r0), m1, w)
            xj = aig.xor_word(state[j], a)
            b = aig.mul_const(aig.rotr(aig.mul_const(xj, m2, w), r1), m3, w)
            out[i], out[j] = a, b
        return out

    def rnd(state, controls, theta):
        out = list(state)
        for (i, j), (si, sj), x in zip(theta.pairs, theta.signs, controls):
            if hardened:
                out[i] = aig.sub(out[i], x)
                out[j] = aig.add(out[j], aig.rotr(x, 1))
            else:
                out[i] = aig.add(out[i], x) if si == 1 else aig.sub(out[i], x)
                out[j] = aig.add(out[j], x) if sj == 1 else aig.sub(out[j], x)
        return mix(out, theta)

    def const_state(values):
        return [aig.const_word(v, w) for v in values]

    # side A: public start S, secret-free prefix inputs, canonical merge_a
    state = const_state(S)
    for index in range(k - 1):
        state = rnd(state, [widen(x, t) for x in words(f"pa{index}", t)],
                    thetas[index])
    state = rnd(state, [aig.const_word(v, w) for v in merge_a], thetas[-1])
    out_a = [bit for word in state for bit in word]

    # side B: public start T, free prefix AND free merge
    state = const_state(T)
    for index in range(k - 1):
        state = rnd(state, [widen(x, t) for x in words(f"pb{index}", t)],
                    thetas[index])
    state = rnd(state, words("mb", w), thetas[-1])
    out_b = [bit for word in state for bit in word]

    meta = {"w": w, "lanes": lanes, "k": k, "t": t, "npairs": npairs,
            "hardened": bool(hardened)}
    return PublicArtifact(aig, groups, out_a, out_b, meta)
