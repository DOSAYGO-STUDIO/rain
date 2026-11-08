#!/usr/bin/env python3
"""Run the same bounded differential screen on each concrete Rainstorm experiment."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from suite import scan

HERE=Path(__file__).resolve().parent

class Adapter:
    def __init__(self,lib,letter): self.lib,self.letter=lib,letter
    def hashes(self,algo,bits,seed,data,length,count):
        fn=getattr(self.lib,f'rainexp_{self.letter}_{bits}_0')
        fn.argtypes=[C.c_void_p,C.c_size_t,C.c_uint64,C.c_void_p]; fn.restype=None
        out=C.create_string_buffer(count*(bits//8))
        for i in range(count): fn(data[i*length:(i+1)*length],length,seed,C.byref(out,i*(bits//8)))
        return out.raw

def main():
    with tempfile.TemporaryDirectory() as td:
        libpath=Path(td)/'variants.so'
        subprocess.run(['c++','-std=c++17','-O2','-shared','-fPIC',str(HERE/'variants/bridge.cpp'),'-o',str(libpath)],check=True)
        lib=C.CDLL(str(libpath))
        for letter in 'abcd':
            # Separate declared families, each with alpha .0025: joint coverage
            # of the four candidate screens is >= .99 by a union bound.
            args=argparse.Namespace(lengths=[1,15,16,17,63,64,65],all_bits=False,masks=None,
                algorithm='rainstorm',bits=256,alpha=.0025,samples=4096,batch=1024,
                replay_seed=None,hash_seed=0,p_min=.01)
            result=scan(Adapter(lib,letter),args)
            result['candidate']=letter
            result['candidate_sha256']=hashlib.sha256((HERE/f'variants/rainstorm_{letter}.cpp').read_bytes()).hexdigest()
            result['native_reference_checks']='variants/checks.json (run before this screen)'
            (HERE/f'variants/differential-{letter}.json').write_text(json.dumps(result,indent=2)+'\n')
            print(letter,'pairs',sum(r['samples'] for r in result['records']),
                  'collisions',sum(r['collisions'] for r in result['records']),flush=True)

if __name__=='__main__': main()
