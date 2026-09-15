"""Exact width-w word operations.

Everything in this laboratory is parameterized by a word width w, so a toy
instance at w=4 and production Rainbow at w=64 run through identical code.
Operations are exact Python integers masked to w bits -- no numpy, no floats,
no silent truncation.
"""


def mask(w):
    return (1 << w) - 1


def add(a, b, w):
    return (a + b) & mask(w)


def sub(a, b, w):
    return (a - b) & mask(w)


def neg(a, w):
    return (-a) & mask(w)


def xor(a, b, w):
    return (a ^ b) & mask(w)


def mul(a, b, w):
    return (a * b) & mask(w)


def rotr(x, n, w):
    """Rotate right by n within w bits."""
    n %= w
    x &= mask(w)
    if n == 0:
        return x
    return ((x >> n) | (x << (w - n))) & mask(w)


def rotl(x, n, w):
    return rotr(x, (-n) % w, w)


def inv_odd(a, w):
    """Multiplicative inverse of an odd a modulo 2^w."""
    if a % 2 == 0:
        raise ValueError("only odd values are invertible mod 2^w")
    return pow(a, -1, 1 << w)


def make_odd(a, w):
    """Reduce a into w bits and force it odd, so it stays invertible."""
    return ((a & mask(w)) | 1) & mask(w)


def scale_rotation(r, w, reference=64):
    """Scale a reference-width rotation to width w, never 0 and never w."""
    if w <= 1:
        return 0
    scaled = round(r * w / reference)
    if scaled <= 0:
        scaled = 1
    if scaled >= w:
        scaled = w - 1
    return scaled


def words_to_int(state, w):
    """Pack a state tuple into one integer, low lane first."""
    value = 0
    for index, word in enumerate(state):
        value |= (word & mask(w)) << (index * w)
    return value


def int_to_words(value, lanes, w):
    return tuple((value >> (index * w)) & mask(w) for index in range(lanes))
