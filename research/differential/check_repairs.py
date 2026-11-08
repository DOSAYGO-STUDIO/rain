#!/usr/bin/env python3
"""Executable round-only models for the repair proposals, not new hash versions."""
import json
import random
from suite import Native, MASK, K, Z, CTR, ror, right_preimage

def right(h,d,proposal):
    h=h.copy(); ctr=CTR
    for i in range(8):
        h[8+i]=ror(((h[8+i]^d[i])-K[i])&MASK,Z[i])
        h[i]^=h[8+i]
        ctr=(ctr+h[8+i])&MASK
        target=8+((i+1)&7)
        if i==7 and proposal=='A': target=0
        coefficient=2 if i==7 and proposal=='B' else 1
        h[target]=(h[target]-coefficient*ctr)&MASK
    return h

def inverse(h,d,proposal):
    y=h[8:].copy()
    if proposal=='B': y[0]=(-h[8]-2*(CTR+sum(y[1:])))&MASK
    low=h[:8].copy()
    if proposal=='A': low[0]=(low[0]+CTR+sum(y))&MASK
    return right_preimage(low,y,d)

def main():
    native=Native(); rng=random.Random(7123)
    for _ in range(1000):
        h=[rng.getrandbits(64) for _ in range(16)]
        d=[rng.getrandbits(64) for _ in range(8)]
        assert right(h,d,'original')==native.round(h,d)
        for proposal in ('A','B'):
            assert inverse(right(h,d,proposal),d,proposal)==h
            assert right(inverse(h,d,proposal),d,proposal)==h
    print(json.dumps({'trials':1000,'original_model_matches_native':True,
                      'A_two_sided_inverse':True,'B_two_sided_inverse':True,
                      'scope':'Round-only models; no full-hash candidate or SMHasher3 claim.'},indent=2))

if __name__=='__main__': main()
