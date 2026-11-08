"""A small exact symbolic layer: bit-vector AST, hash-consed into a DAG.

Written rather than borrowed because Rainbow's mixture of modular arithmetic,
XOR, rotation and multiplication is awkward to force into a general CAS. One
model then emits evaluation, size/depth statistics, Python, or SMT-LIB.

The DAG is the *evaluable* flat form. The algebraic normal form computed in
attacks/flatten_and_attack.py is the *eliminated* flat form: a polynomial keeps
no memory of how it was factored, so intermediates are gone by construction
rather than merely hidden.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Node:
    op: str                 # const | var | add | sub | xor | mul | rotr
    args: Tuple = ()
    imm: int = 0

    def __repr__(self):
        if self.op == "const":
            return f"0x{self.imm:x}"
        if self.op == "var":
            return f"v{self.imm}"
        if self.op == "rotr":
            return f"rotr({self.args[0]!r},{self.imm})"
        return f"({self.args[0]!r} {self.op} {self.args[1]!r})"


class Builder:
    """Hash-consing builder: structurally identical subtrees become one node."""

    def __init__(self, w):
        self.w = w
        self.mask = (1 << w) - 1
        self._pool = {}

    def _intern(self, node):
        return self._pool.setdefault((node.op, node.args, node.imm), node)

    def const(self, value):
        return self._intern(Node("const", (), value & self.mask))

    def var(self, index):
        return self._intern(Node("var", (), index))

    def _binary(self, op, a, b):
        # Constant folding keeps the DAG honest about its real size.
        if a.op == "const" and b.op == "const":
            table = {"add": lambda x, y: x + y,
                     "sub": lambda x, y: x - y,
                     "xor": lambda x, y: x ^ y,
                     "mul": lambda x, y: x * y}
            return self.const(table[op](a.imm, b.imm))
        return self._intern(Node(op, (a, b), 0))

    def add(self, a, b):
        return self._binary("add", a, b)

    def sub(self, a, b):
        return self._binary("sub", a, b)

    def xor(self, a, b):
        return self._binary("xor", a, b)

    def mul(self, a, b):
        return self._binary("mul", a, b)

    def rotr(self, a, n):
        n %= self.w
        if n == 0:
            return a
        if a.op == "const":
            value = a.imm & self.mask
            return self.const((value >> n) | (value << (self.w - n)))
        return self._intern(Node("rotr", (a,), n))


def evaluate(node, env, w):
    mask = (1 << w) - 1
    memo = {}

    def go(n):
        key = id(n)
        if key in memo:
            return memo[key]
        if n.op == "const":
            value = n.imm & mask
        elif n.op == "var":
            value = env[n.imm] & mask
        elif n.op == "rotr":
            x = go(n.args[0])
            value = ((x >> n.imm) | (x << (w - n.imm))) & mask
        else:
            a, b = go(n.args[0]), go(n.args[1])
            value = {"add": a + b, "sub": a - b, "xor": a ^ b, "mul": a * b}[n.op] & mask
        memo[key] = value
        return value

    return go(node)


def walk(nodes):
    """Every distinct node reachable from the given roots."""
    seen, stack = {}, list(nodes)
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen[id(node)] = node
        stack.extend(node.args)
    return list(seen.values())


def stats(roots):
    """Flattened expression size and circuit depth, as the program asks for."""
    nodes = walk(roots)
    depth_of = {}

    def depth(node):
        key = id(node)
        if key in depth_of:
            return depth_of[key]
        value = 1 + max((depth(a) for a in node.args), default=0)
        depth_of[key] = value
        return value

    counts = {}
    for node in nodes:
        counts[node.op] = counts.get(node.op, 0) + 1
    return {
        "dag_nodes": len(nodes),
        "depth": max((depth(r) for r in roots), default=0),
        "ops": counts,
        "multiplications": counts.get("mul", 0),
    }


def to_smtlib(root, w, name="F"):
    """Emit SMT-LIB for the flattened expression, for an external solver."""
    def go(node):
        if node.op == "const":
            return f"(_ bv{node.imm & ((1 << w) - 1)} {w})"
        if node.op == "var":
            return f"v{node.imm}"
        if node.op == "rotr":
            return f"((_ rotate_right {node.imm}) {go(node.args[0])})"
        opname = {"add": "bvadd", "sub": "bvsub", "xor": "bvxor", "mul": "bvmul"}[node.op]
        return f"({opname} {go(node.args[0])} {go(node.args[1])})"

    variables = sorted({n.imm for n in walk([root]) if n.op == "var"})
    decls = "\n".join(f"(declare-const v{v} (_ BitVec {w}))" for v in variables)
    return f"{decls}\n(define-fun {name} () (_ BitVec {w})\n  {go(root)})\n"
