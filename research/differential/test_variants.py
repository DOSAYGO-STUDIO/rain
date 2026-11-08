#!/usr/bin/env python3
"""Native-vs-independent-model and streaming checks for concrete candidates."""
import ctypes as C
import json
from pathlib import Path
import random
import subprocess
import tempfile
from suite import Native, MASK
from check_repairs import right

HERE=Path(__file__).resolve().parent
PRIMES=[1,2,3,5,7,11,13,17,19,23,29,31,37,41,43,47]

def reference(native,variant,msg,seed,bits):
    h=[(seed+len(msg)+p)&MASK for p in PRIMES]
    def round_(h,words,left):
        return native.round(h,words,True) if left else right(h,words,{'a':'A','b':'B','c':'A','d':'original'}[variant])
    def absorb(h,words):
        for i in range(4): h=round_(h,words,bool(i&1))
        return h
    if variant=='c':
        h=absorb(h,[int.from_bytes(b'RNSTEXP1','little'),1,bits,seed,len(msg),0,0,0])
    rem=len(msg)%64
    padded=msg+bytes([0x80+rem])*(64-rem)
    for off in range(0,len(padded),64):
        words=[int.from_bytes(padded[off+i:off+i+8],'little') for i in range(0,64,8)]
        h=absorb(h,words)
    for i in range(8): h[i]=(h[i]-h[i+8])&MASK
    nfinal=4 if variant in ('c','d') else (max(bits//64,2) if bits>64 else 0)
    for i in range(nfinal): h=round_(h,words,bool(i&1) if variant in ('c','d') else True)
    return b''.join(v.to_bytes(8,'little') for v in h[:bits//64])

def main():
    native=Native(); rng=random.Random(43218); comparisons=0; vectors={}
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'variants.so'
        subprocess.run(['c++','-std=c++17','-O2','-shared','-fPIC',str(HERE/'variants/bridge.cpp'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        for variant in 'abcd':
            for bits in (64,128,256,512):
                fn=getattr(lib,f'rainexp_{variant}_{bits}_0')
                fn.argtypes=[C.c_void_p,C.c_size_t,C.c_uint64,C.c_void_p]; fn.restype=None
                stream=getattr(lib,f'rainexp_{variant}_stream')
                stream.argtypes=[C.c_void_p,C.c_size_t,C.c_uint64,C.c_uint32,C.c_size_t,C.c_void_p]; stream.restype=None
                for length in (0,1,7,15,16,17,63,64,65,127,128,129,257):
                    for seed in (0,1,MASK):
                        msg=rng.randbytes(length); want=reference(native,variant,msg,seed,bits)
                        out=C.create_string_buffer(bits//8); fn(msg,length,seed,out)
                        assert out.raw==want,(variant,bits,length,seed)
                        for chunk in (1,7,64,129):
                            streamed=C.create_string_buffer(bits//8)
                            stream(msg,length,seed,bits,chunk,streamed)
                            assert streamed.raw==want,(variant,bits,length,seed,chunk)
                            comparisons+=1
                        if length==0 and seed==0: vectors[f'{variant}-{bits}']=want.hex()
    result={'native_reference_and_streaming_comparisons':comparisons,'passed':True,'empty_seed_zero_vectors':vectors}
    (HERE/'variants/checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
