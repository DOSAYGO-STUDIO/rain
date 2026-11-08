#!/usr/bin/env python3
"""Standalone verifier for the paper's seed-zero, 64-byte collision."""
MASK = (1 << 64) - 1
K = [18446744073709551557, 13166748625691186689,
     1573836600196043749, 1478582680485693857,
     1584163446043636637, 1358537349836140151,
     2849285319520710901, 2366157163652459183]
Z = [17, 19, 23, 29, 31, 37, 41, 53]
CR, CL = 0x1032547698badcfe, 0xefcdab8967452301
IV = [64 + p for p in [1, 2, 3, 5, 7, 11, 13, 17,
                       19, 23, 29, 31, 37, 41, 43, 47]]
PAD = [0x8080808080808080] * 8


def rotate(x, z):
    return ((x >> z) | (x << (64 - z))) & MASK


def round_state(h, d, left):
    # Direct implementation of the displayed two-half recurrences.
    low, high = h[:8], h[8:]
    active, other = (low, high) if left else (high, low)
    counter = CL if left else CR
    out = []
    for i in range(8):
        q = (active[i] - (counter if i else 0)) & MASK
        out.append(rotate(((q ^ d[i]) - K[i]) & MASK, Z[i]))
        counter = (counter + out[i]) & MASK
    passive = [other[i] ^ out[i] for i in range(8)]
    passive[0] = (passive[0] - counter) & MASK
    return out + passive if left else passive + out


def program(v):
    y, d, counter = [0] * 6 + [v, (-v) & MASK], [], CR
    for i in range(8):
        q = (IV[8 + i] - (counter if i else 0)) & MASK
        d.append(q ^ ((rotate(y[i], 64 - Z[i]) + K[i]) & MASK))
        counter = (counter + y[i]) & MASK
    assert round_state(IV, d, False)[8:] == y
    return d


def state(d, rm=2, rp=0):
    h = IV[:]
    for data, rounds in [(d, rm), (PAD, rp)]:
        for r in range(rounds):
            h = round_state(h, data, bool(r & 1))
    return h


def fold(h):
    return [(h[i] - h[8 + i]) & MASK for i in range(8)]


def encode(words):
    return b''.join(w.to_bytes(8, 'little') for w in words).hex()


def digest(h, bits):
    h = fold(h) + h[8:]
    for _ in range(0 if bits == 64 else max(bits // 64, 2)):
        h = round_state(h, PAD, True)
    return encode(h[:bits // 64])


def verify():
    da, db = program(0x4cd2b0d53f915a68), program(0xc4c6fb4191c7f1ed)
    prefix = ('96ffffffffffffff58b56a3e941b7459bab074c685cf1afa'
              'c02a2056945049fbfad0d3accbbf31fa1c4d50f00cd517fd')
    assert encode(da) == prefix + '193863ec0929f2a58af12b6ca5571671'
    assert encode(db) == prefix + '75d7ff14f926a35834c0702bc01e3bc8'
    assert da != db
    a, b = state(da), state(db)
    assert fold(a)[:6] == fold(b)[:6] == [0xf65354081cfe534e] + [0]*5
    expected = {64: '4e53fe1c085453f6',
                128: '62b5f41d42757d67c8a1b25310889a9d',
                256: ('303dbf39c7cd3ae7893f50fcc1328919'
                      '25347bdd65f99d45d9a4f38c92d87b0d')}
    for bits, value in expected.items():
        assert digest(a, bits) == digest(b, bits) == value
    assert digest(a, 512)[:96] == digest(b, 512)[:96]
    assert digest(a, 512) != digest(b, 512)
    pa, pb = state(da, 2, 1), state(db, 2, 1)
    assert fold(pa)[1:6] == fold(pb)[1:6]
    assert fold(pa)[0] != fold(pb)[0]
    assert sum(pa[8:]) & MASK == 0x56ddbed97c83ad47
    assert sum(pb[8:]) & MASK == 0xae1525395140b829
    assert digest(pa, 256) != digest(pb, 256)
    for bits in (128, 256):
        assert digest(state(da, 4, 4), bits) != digest(state(db, 4, 4), bits)
    print('PASS: messages, fold, reduced digests, padding, production checks')


if __name__ == '__main__':
    verify()
