#!/usr/bin/env python3
"""Finite-domain differential search and executable algebraic witnesses (stdlib only)."""
import argparse
import collections
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MASK = (1 << 64) - 1
K = [MASK-58, 13166748625691186689, 1573836600196043749,
     1478582680485693857, 1584163446043636637, 1358537349836140151,
     2849285319520710901, 2366157163652459183]
Z = [17,19,23,29,31,37,41,53]
CTR = 0x1032547698badcfe
U64 = C.c_uint64

def rol(x,n): return ((x << n) | (x >> (64-n))) & MASK

def ror(x,n): return ((x >> n) | (x << (64-n))) & MASK

class Native:
    def __init__(self):
        if sys.byteorder != 'little':
            raise RuntimeError('This suite currently targets the native little-endian implementation.')
        self.tmp = tempfile.TemporaryDirectory(prefix='rain-differential-')
        lib = Path(self.tmp.name) / 'native.so'
        subprocess.run([os.environ.get('CXX','c++'), '-std=c++17','-O2','-shared',
                        '-fPIC',str(Path(__file__).with_name('native.cpp')),'-o',str(lib)],check=True)
        self.lib = C.CDLL(str(lib))
        self.lib.hash_many.argtypes = [C.c_int,C.c_uint,U64,C.c_void_p,C.c_size_t,C.c_size_t,C.c_void_p]
        self.lib.hash_many.restype = C.c_int
        self.lib.storm_round.argtypes = [C.POINTER(U64),C.POINTER(U64),C.c_int]
        self.lib.storm_round.restype = None
        self.lib.bow_mix.argtypes = [C.POINTER(U64),U64,C.c_int]
        self.lib.bow_mix.restype = None

    def hashes(self, algo, bits, seed, data, length, count):
        assert len(data) == length * count
        out = C.create_string_buffer(count * (bits // 8))
        if self.lib.hash_many(algo,bits,seed,data,length,count,out):
            raise ValueError('Unsupported algorithm/output size')
        return out.raw

    def round(self,h,d,left=False):
        h,d = (U64*16)(*h),(U64*8)(*d)
        self.lib.storm_round(h,d,left)
        return list(h)

    def mix(self,h,seed,b):
        h = (U64*4)(*h)
        self.lib.bow_mix(h,seed,b)
        return list(h)

def unmix(h,seed,b):
    def inv(x,p,q,r): return (rol((x*pow(r,-1,1<<64)) & MASK,q)*pow(p,-1,1<<64)) & MASK
    a,b1,c,d = h
    if b:
        old1 = inv(c,K[6],23,K[7])
        old2 = inv(b1,K[2],23,K[3]) ^ ((c+seed)&MASK)
        return [a,old1,old2,d]
    return [inv(a,K[0],23,K[1]), inv(b1,K[2],29,K[3]) ^ a,
            inv(c,K[4],31,K[5]), inv(d,K[6],37,K[7]) ^ c]

def right_preimage(low,y,d):
    hi=[]
    ctr=CTR
    for i in range(8):
        v = ((rol(y[i],Z[i])+K[i]) & MASK) ^ d[i]
        hi.append(v if i == 0 else (v+ctr)&MASK)
        ctr=(ctr+y[i])&MASK
    return [low[i]^y[i] for i in range(8)] + hi

def selftest(n):
    rng=random.Random(3917)
    # Published production vectors, independent of the bridge.
    want=['91fc76841e1431f6d58871e4c981fb37e3c0ac0f9f141c3e99b78f46c727c454',
          '340b44c7eee5a41f118273c6e1ec519247fa2075266423943dc86b0c8e3cceb9']
    for algo in range(2):
        assert n.hashes(algo,256,0,b'',0,1).hex()==want[algo]
    witness=None
    for _ in range(256):
        d=[rng.getrandbits(64) for _ in range(8)]
        low=[rng.getrandbits(64) for _ in range(8)]
        y=[rng.getrandbits(64) for _ in range(8)]
        a=right_preimage(low,y,d)
        yy=y.copy(); yy[0]^=1
        b=right_preimage(low,yy,d)
        out=n.round(a,d)
        assert a!=b and out==n.round(b,d)
        assert out==low+[(-CTR-sum(y[1:]))&MASK]+y[1:]
        # Fixed XOR differential: toggle inactive h[7] MSB. No carry/rotation
        # touches the inactive half in a right round, so it survives unchanged.
        x=[rng.getrandbits(64) for _ in range(16)]
        xp=x.copy(); xp[7]^=1<<63
        expected=n.round(x,d); expected[7]^=1<<63
        assert n.round(xp,d)==expected
        for which in (False,True):
            h=x[:4]; seed=rng.getrandbits(64)
            assert unmix(n.mix(h,seed,which),seed,which)==h
        # Final left-only rounds cannot bring upper-half differences back low.
        xp=x.copy(); xp[8]^=1
        for __ in range(8):
            x=n.round(x,d,True); xp=n.round(xp,d,True)
            assert x[:8]==xp[:8]
        witness={'block':[hex(v) for v in d], 'state_a':[hex(v) for v in a],
                 'state_b':[hex(v) for v in b], 'common_output':[hex(v) for v in out]}
    # Full-hash cross-size first-word relation for known final pad word.
    for length in (0,1,15,16,17,63,64,65,127,128):
        msg=rng.randbytes(length)
        rem=length%64
        tail=msg[length-rem:] if rem else b''
        pad=tail+bytes([0x80+rem])*(64-rem)
        d0=int.from_bytes(pad[:8],'little')
        x=int.from_bytes(n.hashes(1,64,0,msg,length,1)[:8],'little')
        for bits, rounds in ((128,2),(256,4),(512,8)):
            y=x
            for _ in range(rounds): y=ror(((y^d0)-K[0])&MASK,17)
            assert y==int.from_bytes(n.hashes(1,bits,0,msg,length,1)[:8],'little')
    return {'passed':True,'random_witness_trials':256,'right_round_collision_witness':witness}

def bounds(n,d,b,alpha,p):
    # All full output differences (including unseen ones), union bound.
    return {'all_exact_differences_hoeffding_radius':math.sqrt((math.log(2*d/alpha)+b*math.log(2))/(2*n)),
            'zero_collision_upper':-math.expm1(math.log(alpha/d)/n),
            'miss_any_mass_at_least_p_upper':min(1.0,math.exp(min(0,math.log(d/p)+n*math.log1p(-p)))),
            'samples_per_delta_for_discovery':math.ceil(math.log(d/(alpha*p))/-math.log1p(-p))}

def scan(native,args):
    lengths=sorted(set(args.lengths))
    cases=[]
    for length in lengths:
        deltas=range(length*8) if args.all_bits else sorted({0,7,(length//2)*8,length*8-8,length*8-1})
        for bit in deltas: cases.append((length,1<<bit))
        if args.masks:
            for value in args.masks:
                delta=int(value,16)
                if not 0<delta<1<<(length*8): raise ValueError('mask must fit every selected message length and be nonzero')
                cases.append((length,delta))
    cases=list(dict.fromkeys(cases))
    outputs=[(0,b) for b in (64,128,256)]+[(1,b) for b in (64,128,256,512)]
    if args.algorithm!='both': outputs=[c for c in outputs if c[0]==(args.algorithm=='rainstorm')]
    if args.bits: outputs=[c for c in outputs if c[1]==args.bits]
    if not outputs: raise ValueError('Unsupported algorithm/output size combination')
    d=len(cases)*len(outputs)
    # Fixed-budget simultaneous intervals: one third alpha each for exact bins,
    # bit/byte projections, and zero-collision upper bounds.
    projected_tests=sum((b+(b//8)*256)*len(cases) for _,b in outputs)
    radius=math.sqrt(math.log(2*projected_tests/(args.alpha/3))/(2*args.samples))
    rng=random.Random(args.replay_seed) if args.replay_seed is not None else None
    records=[]
    for algo,bits in outputs:
        width=bits//8
        for length,delta in cases:
            counts=collections.Counter()
            byte_counts=[[0]*256 for _ in range(width)]
            collision_witness=None
            for start in range(0,args.samples,args.batch):
                size=min(args.batch,args.samples-start)
                raw=rng.randbytes(size*length) if rng else os.urandom(size*length)
                mask=delta.to_bytes(length,'little')
                paired=bytes(v^mask[i%length] for i,v in enumerate(raw))
                ha=native.hashes(algo,bits,args.hash_seed,raw,length,size)
                hb=native.hashes(algo,bits,args.hash_seed,paired,length,size)
                for j in range(size):
                    off=j*width
                    diff=bytes(a^b for a,b in zip(ha[off:off+width],hb[off:off+width]))
                    counts[diff]+=1
                    for k,v in enumerate(diff): byte_counts[k][v]+=1
                    if not any(diff) and collision_witness is None:
                        collision_witness=[raw[j*length:(j+1)*length].hex(),paired[j*length:(j+1)*length].hex()]
            alerts=[]; max_bit_bias=0.0
            for k,hist in enumerate(byte_counts):
                for bit in range(8):
                    freq=sum(v for x,v in enumerate(hist) if (x>>bit)&1)/args.samples
                    max_bit_bias=max(max_bit_bias,abs(freq-.5))
                    if abs(freq-.5)>radius: alerts.append({'bit':k*8+bit,'frequency':freq})
                for value,count in enumerate(hist):
                    freq=count/args.samples
                    if abs(freq-1/256)>radius: alerts.append({'byte':k,'value':value,'frequency':freq})
            bd=bounds(args.samples,d,bits,args.alpha/3,args.p_min)
            top,count=counts.most_common(1)[0]
            records.append({'algorithm':['rainbow','rainstorm'][algo],'bits':bits,'length':length,
                'input_xor_hex_little_endian':delta.to_bytes(length,'little').hex(),
                'samples':args.samples,'distinct_output_differences':len(counts),
                'most_frequent_difference':top.hex(),'most_frequent_count':count,
                'max_exact_probability_upper':min(1,count/args.samples+bd['all_exact_differences_hoeffding_radius']),
                'collisions':counts[bytes(width)],'collision_witness':collision_witness,
                'max_bit_bias':max_bit_bias,'projection_alerts':alerts,'bounds':bd})
        print(f'completed {("rainbow","rainstorm")[algo]}-{bits}',file=sys.stderr)
    return {'mode':'scan','parameters':vars(args),'sampling': 'deterministic replay; probability claims conditional on IID idealization' if rng else 'OS random bytes; probability claims assume IID uniform messages',
        'family_size':d,'projection_radius':radius,'records':records}

def exhaustive(native,args):
    # Actual full hashes, restricted messages: low k bits vary; other bits zero.
    k=args.domain_bits
    if not 1<=k<=10: raise ValueError('domain-bits must be 1..10 (quadratic exhaustive work)')
    length=(k+7)//8; size=1<<k
    algo=int(args.algorithm=='rainstorm')
    bits=args.bits or 256
    data=b''.join(x.to_bytes(length,'little') for x in range(size))
    out=native.hashes(algo,bits,args.hash_seed,data,length,size)
    values=[int.from_bytes(out[i*(bits//8):(i+1)*(bits//8)],'little') for i in range(size)]
    rows=[]
    for delta in range(1,size):
        count=collections.Counter(values[x]^values[x^delta] for x in range(size))
        value,hits=count.most_common(1)[0]
        rows.append({'input_xor':delta,'max_count':hits,'denominator':size,
                     'max_probability':hits/size,'output_xor':hex(value),'collision_count':count[0]})
    return {'mode':'exhaustive','parameters':vars(args),'message_length':length,
            'domain':'all messages with only the low domain_bits bits variable', 'rows':rows}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['selftest','scan','exhaustive','plan'])
    p.add_argument('--algorithm',choices=['both','rainbow','rainstorm'],default='both')
    p.add_argument('--bits',type=int,choices=[64,128,256,512])
    p.add_argument('--lengths',type=int,nargs='+',default=[1,15,16,17,63,64,65])
    p.add_argument('--samples',type=int,default=4096)
    p.add_argument('--batch',type=int,default=1024)
    p.add_argument('--all-bits',action='store_true')
    p.add_argument('--masks',nargs='*',help='additional integer XOR masks in hex, low byte first in messages')
    p.add_argument('--hash-seed',type=lambda x:int(x,0),default=0)
    p.add_argument('--replay-seed',type=int)
    p.add_argument('--alpha',type=float,default=.01)
    p.add_argument('--p-min',type=float,default=.01)
    p.add_argument('--domain-bits',type=int,default=8)
    p.add_argument('--family-size',type=int,default=1,help='plan only: number of fixed input differences/configurations')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    if not (0<args.alpha<1 and 0<args.p_min<1 and args.samples>0 and args.batch>0 and
            args.family_size>0 and all(v>0 for v in args.lengths) and 0<=args.hash_seed<=MASK):
        p.error('invalid probability, budget, length, or hash seed')
    if args.mode=='exhaustive' and args.algorithm=='both': p.error('exhaustive requires one --algorithm')
    if args.mode=='plan': result=bounds(args.samples,args.family_size,args.bits or 256,args.alpha,args.p_min)
    else:
        native=Native()
        checks=selftest(native)
        if args.mode=='selftest': result=checks
        elif args.mode=='scan': result=scan(native,args)
        else: result=exhaustive(native,args)
        result['selftest_passed']=True
        result['source_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [Path(__file__).parent/'reference/src'/n for n in ('rainbow.cpp','rainstorm.cpp','common.h')]+[Path(__file__),Path(__file__).with_name('native.cpp')]}
    encoded=json.dumps(result,indent=2,default=str)+'\n'
    if args.output: args.output.write_text(encoded)
    else: print(encoded,end='')

if __name__=='__main__': main()
