#!/usr/bin/env python3
"""Snapshot the exact local hashes into a dedicated SMHasher3 registration.

Does not change the production algorithms or SMHasher3's statistical tests.
Run again after every candidate edit, then rebuild and run the full collection.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout',type=Path,default=HERE/'vendor/smhasher3')
    p.add_argument('--source-root',type=Path,default=ROOT,
                   help='Root containing src/; use reference/ to reproduce the pre-v4 OG campaign')
    args=p.parse_args()
    checkout=args.checkout.resolve()
    if sys.byteorder!='little': p.error('adapter verification currently requires a little-endian host')
    snap=checkout/'hashes/rainlocal_source'
    snap.mkdir(exist_ok=True)
    for name in ('common.h','rainbow.cpp','rainstorm.cpp'): shutil.copyfile(args.source_root/'src'/name,snap/name)
    core=['#include "rainlocal_source/rainbow.cpp"','#include "rainlocal_source/rainstorm.cpp"']
    entries=[]
    for algo in ('rainbow','rainstorm'):
        for bits in (64,128,256):
            name=f'rainlocal_{algo}_{bits}'
            entries.append((name,algo,bits))
            for swap in (0,1):
                core.append(f'extern "C" void {name}_{swap}(const void* p, size_t n, uint64_t s, void* q) {{ {algo}::{algo}<{bits},{str(bool(swap)).lower()}>(p,n,s,q); }}')
    core_path=checkout/'hashes/rainlocal_core.cpp'
    core_path.write_text('\n'.join(core)+'\n')
    registry=['// Local analysis adapter. Hash source snapshots retain their original licensing.',
        '#include "Platform.h"','#include "Hashlib.h"',
        'REGISTER_FAMILY(rainlocal, $.src_url = "https://github.com/dosyago/rain", $.src_status = HashFamilyInfo::SRC_STABLEISH);']
    codes={}
    with tempfile.TemporaryDirectory() as td:
        lib=Path(td)/'core.so'
        subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-O2','-shared','-fPIC',str(core_path),'-o',str(lib)],check=True)
        native=C.CDLL(str(lib))
        for name,algo,bits in entries:
            verification=[]
            for swap in (0,1):
                symbol=f'{name}_{swap}'
                registry.append(f'extern "C" void {symbol}(const void*,size_t,uint64_t,void*);')
                fn=getattr(native,symbol)
                fn.argtypes=[C.c_void_p,C.c_size_t,C.c_uint64,C.c_void_p]; fn.restype=None
                def digest(data,seed):
                    out=C.create_string_buffer(bits//8)
                    fn(data,len(data),seed,out)
                    return out.raw
                hashes=b''.join(digest(bytes(range(i)),256-i) for i in range(256))
                verification.append(int.from_bytes(digest(hashes,0)[:4],'little'))
            codes[name]={'LE':hex(verification[0]),'BE':hex(verification[1])}
            registry.append(f'''REGISTER_HASH({name},
 $.desc = "Exact local {algo}-{bits} source snapshot",
 $.impl_flags = FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
 $.bits = {bits},
 $.verification_LE = 0x{verification[0]:08X},
 $.verification_BE = 0x{verification[1]:08X},
 $.hashfn_native = {name}_0,
 $.hashfn_bswap = {name}_1
);''')
    (checkout/'hashes/rainlocal.cpp').write_text('\n'.join(registry)+'\n')
    src=checkout/'hashes/Hashsrc.cmake'
    text=src.read_text()
    addition='\nlist(APPEND HASH_SRC_FILES hashes/rainlocal.cpp)\n'
    if addition.strip() not in text: src.write_text(text+addition)
    # Core is a separate TU to avoid type/macro collisions with Platform.h.
    cmake=checkout/'CMakeLists.txt'
    text=cmake.read_text()
    addition='\ntarget_sources(SMHasher3Hashlib PRIVATE hashes/rainlocal_core.cpp)\n'
    if addition.strip() not in text: cmake.write_text(text+addition)
    manifest={'smhasher3_revision':subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip(),
        'production_sha256':{name:hashlib.sha256((snap/name).read_bytes()).hexdigest() for name in ('common.h','rainbow.cpp','rainstorm.cpp')},
        'verification_codes':codes,'supported_sizes':[64,128,256],
        'limitation':'Upstream Testlib does not instantiate 512-bit hashes. No truncated substitute is registered.',
        'full_command_template':'SMHasher3 --test=All,BadSeeds --extra --ncpu=4 rainlocal-<algorithm>-<bits>',
        'status':'Prepared source snapshot and verification codes; not a full statistical test result.'}
    (HERE/'smhasher3-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
