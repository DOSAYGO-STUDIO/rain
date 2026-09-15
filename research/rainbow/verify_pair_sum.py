#!/usr/bin/env python3
"""Independent verifier for the Rainbow pair-sum collision.

Written from src/rainbow.cpp with Python big integers -- it shares no code with
the attack or the production C++, so agreement between the three is real
evidence.  It re-derives the collision from the message bytes alone and prints
every checkpoint the attack claims.

    python3 research/rainbow/verify_pair_sum.py [collision-result.json]
"""

import json
import sys

MASK = (1 << 64) - 1

P = (1 << 64) - 1 - 58
Q = 13166748625691186689
R = 1573836600196043749
S = 1478582680485693857
T = 1584163446043636637
U = 1358537349836140151
V = 2849285319520710901
W = 2366157163652459183


def rotr64(x, n):
    x &= MASK
    return ((x >> n) | (x << (64 - n))) & MASK


def mix_a(h):
    a, b, c, d = h
    a = (a * P) & MASK
    a = rotr64(a, 23)
    a = (a * Q) & MASK
    b ^= a
    b = (b * R) & MASK
    b = rotr64(b, 29)
    b = (b * S) & MASK
    c = (c * T) & MASK
    c = rotr64(c, 31)
    c = (c * U) & MASK
    d ^= c
    d = (d * V) & MASK
    d = rotr64(d, 37)
    d = (d * W) & MASK
    return [a, b, c, d]


def mix_b(h, iv):
    a, b = h[1], h[2]
    a = (a * V) & MASK
    a = rotr64(a, 23)
    a = (a * W) & MASK
    b ^= (a + iv) & MASK
    b = (b * R) & MASK
    b = rotr64(b, 23)
    b = (b * S) & MASK
    out = list(h)
    out[1] = b
    out[2] = a
    return out


def rotate_right(h):
    return [h[3], h[0], h[1], h[2]]


def absorb(h, data, seed, inner=False):
    """Absorb whole 16-byte blocks, returning the state and the next parity."""
    h = list(h)
    offset = 0
    while len(data) - offset >= 16:
        x = int.from_bytes(data[offset:offset + 8], "little")
        h[0] = (h[0] - x) & MASK
        h[1] = (h[1] + x) & MASK
        y = int.from_bytes(data[offset + 8:offset + 16], "little")
        h[2] = (h[2] + y) & MASK
        h[3] = (h[3] - y) & MASK
        if inner:
            h = mix_b(h, seed)
            h = rotate_right(h)
        else:
            h = mix_a(h)
        inner = not inner
        offset += 16
    return h, inner


TAIL = [
    (15, 0, 14, 56), (14, 1, 13, 48), (13, 2, 12, 40), (12, 3, 11, 32),
    (11, 0, 10, 24), (10, 1, 9, 16), (9, 2, 8, 8), (8, 3, 7, 0),
    (7, 0, 6, 48), (6, 1, 5, 40), (5, 2, 4, 32), (4, 3, 3, 24),
    (3, 0, 2, 16), (2, 1, 1, 8), (1, 2, 0, 0),
]


def rainbow(data, seed, hashsize, trace=None):
    olen = len(data)
    h = [(seed + olen + 1) & MASK, (seed + olen + 2) & MASK,
         (seed + olen + 3) & MASK, (seed + olen + 5) & MASK]
    if trace is not None:
        trace.append(("initial", list(h)))
    offset = 0
    remaining = olen
    inner = False
    block = 0
    while remaining >= 16:
        x = int.from_bytes(data[offset:offset + 8], "little")
        h[0] = (h[0] - x) & MASK
        h[1] = (h[1] + x) & MASK
        y = int.from_bytes(data[offset + 8:offset + 16], "little")
        h[2] = (h[2] + y) & MASK
        h[3] = (h[3] - y) & MASK
        block += 1
        if trace is not None:
            trace.append((f"block-{block} injection", list(h)))
        if inner:
            h = mix_b(h, seed)
            h = rotate_right(h)
        else:
            h = mix_a(h)
        if trace is not None:
            trace.append((f"block-{block} mixer", list(h)))
        inner = not inner
        offset += 16
        remaining -= 16

    h = mix_b(h, seed)
    tail = data[offset:]
    for case, word, index, shift in TAIL:
        if len(tail) >= case:
            h[word] = (h[word] + (tail[index] << shift)) & MASK
    h = mix_a(h)
    h = mix_b(h, seed)
    h = mix_a(h)
    if trace is not None:
        trace.append(("before finalization output", list(h)))

    out = bytearray()
    g = (-(h[2] + h[3])) & MASK
    out += g.to_bytes(8, "little")
    if hashsize == 128:
        h = mix_a(h)
        out += ((-(h[3] + h[2])) & MASK).to_bytes(8, "little")
    elif hashsize == 256:
        h = mix_a(h)
        out += ((-(h[3] + h[2])) & MASK).to_bytes(8, "little")
        h = mix_a(h)
        h = mix_b(h, seed)
        h = mix_a(h)
        out += ((-(h[3] + h[2])) & MASK).to_bytes(8, "little")
        h = mix_a(h)
        out += ((-(h[3] + h[2])) & MASK).to_bytes(8, "little")
    return bytes(out)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "research/rainbow/collision-result.json"
    with open(path) as handle:
        result = json.load(handle)

    seed = result["seed"]
    msg_a = bytes.fromhex(result["message_a"])
    msg_b = bytes.fromhex(result["message_b"])

    print("independent Python verification")
    print(f"  seed = {seed}")
    print(f"  a ({len(msg_a)} bytes) = {msg_a.hex()}")
    print(f"  b ({len(msg_b)} bytes) = {msg_b.hex()}")
    if msg_a == msg_b:
        print("  FAIL: messages are identical")
        return 1
    if len(msg_a) != len(msg_b):
        print("  NOTE: lengths differ")

    # Re-derive the pair sums from the bytes alone, independently of the
    # attack's claims.  The last 32 bytes are always the claw block followed by
    # the bridge block; anything before them is a chosen prefix (possibly empty).
    olen = len(msg_a)
    ok = True
    sums = {}
    for name, msg in (("a", msg_a), ("b", msg_b)):
        h = [(seed + olen + 1) & MASK, (seed + olen + 2) & MASK,
             (seed + olen + 3) & MASK, (seed + olen + 5) & MASK]
        prefix, claw, bridge = msg[:-32], msg[-32:-16], msg[-16:]
        h, inner = absorb(h, prefix, seed, False)
        if inner:
            print(f"  {name}: FAIL claw block is not a mixA block")
            ok = False
        x = int.from_bytes(claw[0:8], "little")
        y = int.from_bytes(claw[8:16], "little")
        h = [(h[0] - x) & MASK, (h[1] + x) & MASK,
             (h[2] + y) & MASK, (h[3] - y) & MASK]
        big_a, big_b, big_c, big_d = mix_a(h)
        p = int.from_bytes(bridge[0:8], "little")
        q = int.from_bytes(bridge[8:16], "little")
        h_sum = (big_a + big_b) & MASK
        k_sum = (big_c + big_d) & MASK
        sums[name] = (h_sum, k_sum, (big_a - p) & MASK, (big_b + p) & MASK,
                      (big_c + q) & MASK, (big_d - q) & MASK)
        print(f"  {name}: prefix={len(prefix)}B x={x} y={y}")
        print(f"     A={big_a} B={big_b} -> H={h_sum}")
        print(f"     C={big_c} D={big_d} -> K={k_sum}")
        print(f"     bridge p={p} q={q}  (pair sums are what must agree)")

    if sums["a"][0] != sums["b"][0]:
        print("  NOTE: H differs between the messages")
    if sums["a"][1] != sums["b"][1]:
        print("  NOTE: K differs between the messages")
    if sums["a"][2:] != sums["b"][2:]:
        print("  FAIL: post-bridge pairs differ")
        ok = False
    else:
        print("  post-bridge state pairs agree exactly")

    traces = {}
    for name, msg in (("a", msg_a), ("b", msg_b)):
        traces[name] = []
        rainbow(msg, seed, 256, traces[name])

    print("\n  checkpoint comparison")
    merged_at = None
    for (label_a, state_a), (label_b, state_b) in zip(traces["a"], traces["b"]):
        same = state_a == state_b
        print(f"    {label_a:<28} identical={'yes' if same else 'no'}")
        if same and merged_at is None and label_a != "initial":
            merged_at = label_a
    if merged_at:
        print(f"  states merge at: {merged_at}")
    else:
        print("  states never merge")
        ok = False

    print("\n  digests")
    for bits in (64, 128, 256):
        da = rainbow(msg_a, seed, bits)
        db = rainbow(msg_b, seed, bits)
        same = da == db
        ok = ok and same
        print(f"    rainbow-{bits}: a={da.hex()}")
        print(f"    {'':>12} b={db.hex()}  equal={'YES' if same else 'no'}")
        claimed = result.get(f"reference_digest_{bits}")
        if claimed is not None and claimed != da.hex():
            print(f"    MISMATCH with attack's claim {claimed}")
            ok = False

    print("\n" + ("CONFIRMED by independent implementation" if ok else "VERIFICATION FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
