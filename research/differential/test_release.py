#!/usr/bin/env python3
"""Ensure promoted production code matches the independently tested candidate A."""
import ctypes as C
import random
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    source=f'#include "{ROOT}/src/rainstorm.cpp"\n#undef __STORMVERSION__\n#include "{HERE}/variants/rainstorm_a.cpp"\n'
    for label,namespace in [('production','rainstorm'),('candidate','rainstorm_a')]:
        for bits in (64,128,256,512):
            for swap in (0,1):
                source+=f'extern "C" void {label}_{bits}_{swap}(const void*p,size_t n,uint64_t s,void*q){{{namespace}::rainstorm<{bits},{str(bool(swap)).lower()}>(p,n,s,q);}}\n'
    with tempfile.TemporaryDirectory() as td:
        cpp=Path(td)/'check.cpp';cpp.write_text(source)
        libpath=Path(td)/'check.so'
        subprocess.run(['c++','-std=c++17','-O2','-shared','-fPIC',str(cpp),'-o',str(libpath)],check=True)
        lib=C.CDLL(str(libpath));rng=random.Random(20260908);count=0
        for bits in (64,128,256,512):
            for swap in (0,1):
                functions=[getattr(lib,f'{label}_{bits}_{swap}') for label in ('production','candidate')]
                for fn in functions:fn.argtypes=[C.c_void_p,C.c_size_t,C.c_uint64,C.c_void_p];fn.restype=None
                for length in (0,1,7,15,16,17,31,32,63,64,65,127,128,129,257,1024):
                    for seed in (0,1,(1<<64)-1,rng.getrandbits(64)):
                        msg=rng.randbytes(length);values=[]
                        for fn in functions:
                            out=C.create_string_buffer(bits//8);fn(msg,length,seed,out);values.append(out.raw)
                        assert values[0]==values[1],(bits,swap,length,seed)
                        count+=1
    print(f'PASS: {count} production/candidate-A comparisons, all widths and endian paths.')

if __name__=='__main__':main()
