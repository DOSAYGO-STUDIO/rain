"""A minimal And-Inverter Graph, so a flattened map can be published as gates.

WHY BIT LEVEL. models/symbolic.py already builds an exact word-level DAG of the
composition, and that DAG is NOT a valid public artifact: a multiplication by a
secret multiplier appears in it as a literal `const` node, so publishing the DAG
publishes theta. Any flattening that keeps word-level multiply-by-constant has
the same defect. Going to bits compiles each constant multiply into a fixed
network of adders, which is the first representation where the constant is not
sitting in a field waiting to be read.

Whether the gate network still BETRAYS the constant is a separate question with
its own answer, and it is measured rather than assumed -- see
attacks/theta_recovery.py. A shift-and-add network has one addend per set bit of
the multiplier, so the obvious worry is that structure alone reveals popcount.

The graph is strash-ed (structurally hashed): identical AND nodes are shared, so
the same function built two ways converges on the same subgraph, and constant
folding happens at construction. Literals are integers: bit 0 is the inversion
flag, the rest is the node index, with 0 = FALSE and 1 = TRUE.
"""

FALSE, TRUE = 0, 1


def lit(node, inverted=False):
    return (node << 1) | (1 if inverted else 0)


def invert(literal):
    return literal ^ 1


def is_const(literal):
    return literal in (FALSE, TRUE)


class Aig:
    def __init__(self):
        self.ands = []                      # (left_literal, right_literal)
        self.inputs = []                    # literals, in declaration order
        self.names = []                     # parallel to inputs, for the header
        self._hash = {}

    # ---------------------------------------------------------------- building
    def input(self, name):
        node = len(self.ands) + 1 + len(self.inputs)
        # Inputs occupy their own index space ahead of ANDs; keep it simple by
        # allocating inputs first and refusing to interleave.
        if self.ands:
            raise RuntimeError("declare all inputs before building gates")
        literal = lit(len(self.inputs) + 1)
        self.inputs.append(literal)
        self.names.append(name)
        return literal

    def and_(self, a, b):
        if a == FALSE or b == FALSE:
            return FALSE
        if a == TRUE:
            return b
        if b == TRUE:
            return a
        if a == b:
            return a
        if a == invert(b):
            return FALSE
        key = (a, b) if a <= b else (b, a)
        hit = self._hash.get(key)
        if hit is not None:
            return hit
        self.ands.append(key)
        literal = lit(len(self.inputs) + len(self.ands))
        self._hash[key] = literal
        return literal

    def or_(self, a, b):
        return invert(self.and_(invert(a), invert(b)))

    def xor(self, a, b):
        return self.or_(self.and_(a, invert(b)), self.and_(invert(a), b))

    # ------------------------------------------------------------- word layer
    def const_word(self, value, w):
        return [TRUE if (value >> i) & 1 else FALSE for i in range(w)]

    def add(self, xs, ys):
        """Ripple-carry, little-endian, truncated to len(xs)."""
        out, carry = [], FALSE
        for x, y in zip(xs, ys):
            total = self.xor(self.xor(x, y), carry)
            carry = self.or_(self.and_(x, y),
                             self.and_(carry, self.or_(x, y)))
            out.append(total)
        return out

    def negate(self, xs):
        one = [TRUE] + [FALSE] * (len(xs) - 1)
        return self.add([invert(x) for x in xs], one)

    def sub(self, xs, ys):
        return self.add(xs, self.negate(ys))

    def xor_word(self, xs, ys):
        return [self.xor(x, y) for x, y in zip(xs, ys)]

    def rotr(self, xs, n):
        w = len(xs)
        n %= w
        return [xs[(i + n) % w] for i in range(w)]

    def mul_const(self, xs, value, w):
        """Shift and add. The constant never survives as a field, only as shape."""
        acc = [FALSE] * w
        for i in range(w):
            if (value >> i) & 1:
                shifted = [FALSE] * i + xs[:w - i]
                acc = self.add(acc, shifted)
        return acc

    # ------------------------------------------------------------- evaluation
    def evaluate(self, outputs, assignment):
        """Simulate. `assignment` maps input literal -> 0/1. No theta involved."""
        values = {FALSE: 0, TRUE: 1}
        for literal in self.inputs:
            values[literal] = assignment[literal] & 1
            values[invert(literal)] = values[literal] ^ 1
        for index, (a, b) in enumerate(self.ands, start=1):
            literal = lit(len(self.inputs) + index)
            value = values[a] & values[b]
            values[literal] = value
            values[invert(literal)] = value ^ 1
        return [values[o] for o in outputs]

    def stats(self):
        return {"inputs": len(self.inputs), "ands": len(self.ands)}
