"""k weak factors composed into one public relation.

THE BARGAIN THIS IS BUILT TO TEST. Private latency should stay at ONE factor's
collision search however many factors there are. Security should come from the
composition, not from widening Rainbow and ruining the cheap side. So w is held
fixed and k varies, and the only question worth asking first is whether public
cost grows with k while private cost merely multiplies by it.

TWO FAMILIES, ONE OF WHICH IS A CONTROL.

  parallel   x = (y_1..y_k), z = (r_1..r_k). No coupling. Every seam is visible:
             an attacker splits it into k independent problems and pays k times
             one factor. Public cost must grow roughly LINEARLY in k here. If it
             grows exponentially, the measurement is broken, not the construction
             -- that is what this family is for.

  coupled    y = L x, z = M r, with L and M secret random invertible GF(2)
             matrices. Every public input bit feeds every factor and every
             public output bit mixes every residual, so no seam is visible to
             differential probing -- which is precisely the attack that recovered
             the pairing in theta_recovery.py. Private stitching stays free:
             solve each factor, concatenate, apply L^-1. M changes nothing about
             the solution set (M r = 0 iff r = 0) but hides which outputs group.

THE PREDICTED KILLER, stated before building it. This is the hide-a-separable-
map-behind-secret-linear-layers paradigm of multivariate cryptography, and its
history is mostly structure-recovery attacks. For separable R, the second
derivative D_a D_b R vanishes identically whenever a and b lie in different
factors, and linear L carries that block structure straight through. So a
public attacker can plausibly recover the decomposition by linear algebra on
second derivatives. og/derivative_attack.py tests exactly that, and until it has
run, any amplification SAT shows on the coupled family is suspect -- CDCL is
known to be weak on dense XOR layers, so a SAT blow-up here could be the
solver's blind spot rather than hardness.
"""

import random

from models.aig import Aig

from factor import (input_bits, private_witness, residual_circuit,
                    witness_to_bits)


# ------------------------------------------------------------------ GF(2) linear
def _rank_and_inverse(rows, n):
    """Gauss-Jordan over GF(2). rows[i] is an int bitmask. Returns (rank, inverse)."""
    a = list(rows)
    inv = [1 << i for i in range(n)]
    rank = 0
    for col in range(n):
        pivot = next((r for r in range(rank, n) if (a[r] >> col) & 1), None)
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        inv[rank], inv[pivot] = inv[pivot], inv[rank]
        for r in range(n):
            if r != rank and (a[r] >> col) & 1:
                a[r] ^= a[rank]
                inv[r] ^= inv[rank]
        rank += 1
    return rank, (inv if rank == n else None)


def random_invertible(n, rng):
    while True:
        rows = [rng.getrandbits(n) for _ in range(n)]
        rank, inverse = _rank_and_inverse(rows, n)
        if rank == n:
            return rows, inverse


def apply_bits(rows, bits):
    """Matrix times bit-vector over GF(2); bits[j] is column j."""
    vector = sum(b << j for j, b in enumerate(bits))
    return [bin(row & vector).count("1") & 1 for row in rows]


def apply_literals(aig, rows, literals):
    out = []
    for row in rows:
        acc = 0                                    # FALSE
        for j, literal in enumerate(literals):
            if (row >> j) & 1:
                acc = literal if acc == 0 else aig.xor(acc, literal)
        out.append(acc)
    return out


# ----------------------------------------------------------------------- compose
FAMILIES = ("parallel", "coupled")
# Diagnostic ablations, not candidates: which secret layer does the work?
ABLATIONS = ("coupled_in", "coupled_out")


def build(family, factors, w, t, rng):
    """Compile k factors into one public artifact. Returns public + secret parts."""
    k = len(factors)
    per, _ = input_bits(w, t)
    n = k * per
    aig = Aig()
    x = [aig.input(f"x{i}") for i in range(n)]

    secret = {"family": family}
    mix_inputs = family in ("coupled", "coupled_in")
    mix_outputs = family in ("coupled", "coupled_out")
    if family not in FAMILIES + ABLATIONS:
        raise ValueError(family)
    if mix_inputs:
        L, L_inv = random_invertible(n, rng)
        y = apply_literals(aig, L, x)
        secret.update(L=L, L_inv=L_inv)
    else:
        y = list(x)

    residuals = []
    for index, challenge in enumerate(factors):
        residuals += residual_circuit(aig, challenge, t, y[index * per:(index + 1) * per])

    if mix_outputs:
        M, _ = random_invertible(len(residuals), rng)
        z = apply_literals(aig, M, residuals)
        secret["M"] = M
    else:
        z = residuals

    public = {"aig": aig, "x": x, "z": z,
              "meta": {"family": family, "k": k, "w": w, "t": t,
                       "input_bits": n, "output_bits": len(z),
                       "gates": len(aig.ands)}}
    return public, secret


def private_solve(public, secret, factors, w, t):
    """Solve every factor independently, then stitch. Returns (x_bits, cost, ok).

    Stitching is one GF(2) matrix application -- polynomial, and not a search.
    Private cost is reported two ways because the bargain depends on both:
    total work sums over factors, latency is one factor since they are
    independent and could run in parallel.
    """
    y_bits, per_factor = [], []
    for challenge in factors:
        witness, evaluations, ok = private_witness(challenge, t)
        if not ok:
            return None, {"total": None, "latency": None}, False
        y_bits += witness_to_bits(witness, w, t)
        per_factor.append(evaluations)

    x_bits = (apply_bits(secret["L_inv"], y_bits)
              if "L_inv" in secret else y_bits)

    aig = public["aig"]
    z = aig.evaluate(public["z"], {l: b for l, b in zip(public["x"], x_bits)})
    return x_bits, {"total": sum(per_factor), "latency": max(per_factor),
                    "per_factor": per_factor}, not any(z)
