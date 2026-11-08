#!/usr/bin/env python3
"""Pre-release comparison: chosen-state collision family and finite message screen."""
import argparse
import ctypes as C
import json
from pathlib import Path
import random
import subprocess
import tempfile
from suite import Native, MASK, right_preimage, scan
from check_repairs import right, inverse
from scan_variants import Adapter

HERE = Path(__file__).resolve().parent

def main():
    native = Native()
    rng = random.Random(20260908)
    trials = 1000
    for _ in range(trials):
        block = [rng.getrandbits(64) for _ in range(8)]
        low = [rng.getrandbits(64) for _ in range(8)]
        y = [rng.getrandbits(64) for _ in range(8)]
        x = right_preimage(low, y, block)
        y[0] ^= 1
        xp = right_preimage(low, y, block)
        assert native.round(x, block) == native.round(xp, block)
        assert right(x, block, 'A') != right(xp, block, 'A')
        assert inverse(right(x, block, 'A'), block, 'A') == x
        # Both retain this simple one-right-round truncated differential.
        z = x.copy(); z[7] ^= 1 << 63
        for variant in ('original', 'A'):
            want = right(x, block, variant); want[7] ^= 1 << 63
            assert right(z, block, variant) == want
    output = HERE / 'redteam-og-a-20260908'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        lib = Path(td) / 'variants.so'
        subprocess.run(['c++','-std=c++17','-O2','-shared','-fPIC',
                        str(HERE/'variants/bridge.cpp'),'-o',str(lib)],check=True)
        for name, adapter in [('OG', native), ('A', Adapter(C.CDLL(str(lib)), 'a'))]:
            args = argparse.Namespace(lengths=[1,15,16,17,63,64,65,127,128,129],
                all_bits=False, masks=None, algorithm='rainstorm', bits=None,
                alpha=.005, samples=4096, batch=1024, replay_seed=None,
                hash_seed=0, p_min=.01)
            result = scan(adapter,args)
            (output/f'{name}.json').write_text(json.dumps(result,indent=2)+'\n')
            print(name, 'pairs',sum(r['samples'] for r in result['records']),
                  'collisions',sum(r['collisions'] for r in result['records']),
                  'long-domain alert cases',sum(bool(r['projection_alerts']) for r in result['records'] if r['length']>1),flush=True)
    (output/'rounds.json').write_text(json.dumps(dict(trials=trials,
        og_chosen_state_collisions=trials, a_same_pair_collisions=0,
        a_inverse_checks=trials, shared_one_round_xor_differential_checks=trials,
        scope='Fixed-block, freely chosen incoming states; not reachable-message collisions.'),indent=2)+'\n')

if __name__ == '__main__':
    main()
