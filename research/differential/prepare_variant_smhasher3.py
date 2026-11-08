#!/usr/bin/env python3
"""Add isolated experimental registrations, without modifying Testlib or original hashes."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CHECKOUT=HERE/'vendor/smhasher3'

def main():
    snap=CHECKOUT/'hashes/rainexp_source'; snap.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'src/common.h',snap/'common.h')
    for letter in 'abcd':
        text=(HERE/f'variants/rainstorm_{letter}.cpp').read_text()
        (snap/f'rainstorm_{letter}.cpp').write_text(text.replace('#include "../../../src/common.h"','#include "common.h"'))
    bridge=(HERE/'variants/bridge.cpp').read_text()
    for letter in 'abcd': bridge=bridge.replace(f'#include "rainstorm_{letter}.cpp"',f'#include "rainexp_source/rainstorm_{letter}.cpp"')
    core=CHECKOUT/'hashes/rainexp_core.cpp'; core.write_text(bridge)
    registry=['// Experimental Rainstorm registrations. Derived hash source: Apache-2.0.',
        '#include "Platform.h"','#include "Hashlib.h"',
        'REGISTER_FAMILY(rainexp, $.src_url = "https://github.com/dosyago/rain", $.src_status = HashFamilyInfo::SRC_STABLEISH);']
    codes={}
    with tempfile.TemporaryDirectory() as td:
        libpath=Path(td)/'variants.so'
        subprocess.run(['c++','-std=c++17','-O2','-shared','-fPIC',str(core),'-o',str(libpath)],check=True)
        lib=C.CDLL(str(libpath))
        for letter in 'abcd':
            for bits in (64,128,256):
                name=f'rainexp_{letter}_{bits}'
                verification=[]
                for swapped in (0,1):
                    symbol=f'{name}_{swapped}'
                    registry.append(f'extern "C" void {symbol}(const void*,size_t,uint64_t,void*);')
                    fn=getattr(lib,symbol)
                    fn.argtypes=[C.c_void_p,C.c_size_t,C.c_uint64,C.c_void_p]; fn.restype=None
                    def digest(msg,seed):
                        out=C.create_string_buffer(bits//8); fn(msg,len(msg),seed,out); return out.raw
                    hashes=b''.join(digest(bytes(range(i)),256-i) for i in range(256))
                    verification.append(int.from_bytes(digest(hashes,0)[:4],'little'))
                codes[name]=dict(zip(('LE','BE'),[hex(v) for v in verification]))
                registry.append(f'''REGISTER_HASH({name},
 $.desc = "Experimental Rainstorm {letter.upper()}-{bits}",
 $.impl_flags = FLAG_IMPL_ROTATE | FLAG_IMPL_LICENSE_APACHE2,
 $.bits = {bits},
 $.verification_LE = 0x{verification[0]:08X},
 $.verification_BE = 0x{verification[1]:08X},
 $.hashfn_native = {name}_0,
 $.hashfn_bswap = {name}_1
);''')
    reg=CHECKOUT/'hashes/rainexp.cpp'; reg.write_text('\n'.join(registry)+'\n')
    for path,line in [(CHECKOUT/'hashes/Hashsrc.cmake','list(APPEND HASH_SRC_FILES hashes/rainexp.cpp)'),
                      (CHECKOUT/'CMakeLists.txt','target_sources(SMHasher3Hashlib PRIVATE hashes/rainexp_core.cpp)')]:
        text=path.read_text()
        if line not in text: path.write_text(text+'\n'+line+'\n')
    # Same upstream BLAKE3 implementation and seed adaptation, but no metadata
    # slowdown: require the same test sizes/repetitions as OG and A/B/C.
    control=CHECKOUT/'hashes/blake3.cpp'
    control_text=control.read_text()
    if 'REGISTER_HASH(raincontrol_blake3_256,' not in control_text:
        control.write_text(control_text+"""
// Campaign control: unchanged BLAKE3 function, full test budgets.
REGISTER_HASH(raincontrol_blake3_256,
 $.desc = "BLAKE3-256 upstream seeded adapter, matched test budgets",
 $.impl = BLAKE3_IMPL_STR,
 $.hash_flags = FLAG_HASH_CRYPTOGRAPHIC | FLAG_HASH_NO_SEED |
                FLAG_HASH_LOOKUP_TABLE | FLAG_HASH_ENDIAN_INDEPENDENT,
 $.impl_flags = FLAG_IMPL_LICENSE_MIT | FLAG_IMPL_CANONICAL_BOTH |
                FLAG_IMPL_ROTATE | FLAG_IMPL_INCREMENTAL,
 $.bits = 256,
 $.verification_LE = 0x50E4CD91,
 $.verification_BE = 0x50E4CD91,
 $.hashfn_native = BLAKE3<256>,
 $.hashfn_bswap = BLAKE3<256>
);
""")
    sources=[core,reg,control,*snap.iterdir()]
    result={'verification_codes':codes,'variant_manifest':json.loads((HERE/'variants/manifest.json').read_text()),
        'adapter_sha256':{str(p.relative_to(CHECKOUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'smhasher3_revision':subprocess.check_output(['git','-C',str(CHECKOUT),'rev-parse','HEAD'],text=True).strip(),
        'metadata_policy':'Same no-slowdown metadata as exact-source OG registration; no Testlib changes.'}
    (HERE/'variants/smhasher3-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Prepared 12 candidate registrations with native and swapped verification codes.')

if __name__=='__main__': main()
