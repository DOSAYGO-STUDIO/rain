#!/usr/bin/env python3
"""Run the prepared exact-source registrations; default is the full per-hash suite."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['full','smoke'],default='full')
    p.add_argument('--ncpu',type=int,default=4)
    p.add_argument('--endian',choices=['both','native','nonnative'],default='both')
    p.add_argument('--checkout',type=Path,default=HERE/'vendor/smhasher3')
    p.add_argument('--hashes',nargs='+',default=[f'rainlocal-{a}-{b}' for a in ('rainbow','rainstorm') for b in (64,128,256)])
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.ncpu<1: p.error('--ncpu must be positive')
    manifest=json.loads((HERE/'smhasher3-manifest.json').read_text())
    allowed={name.replace('_','-') for name in manifest['verification_codes']}
    if not set(args.hashes)<=allowed: p.error('unsupported hash name; 512-bit tests require a Testlib extension')
    for name,expected in manifest['production_sha256'].items():
        for path in (ROOT/'src'/name,args.checkout/'hashes/rainlocal_source'/name):
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                p.error('source drift: rerun prepare_smhasher3.py and rebuild before testing')
    exe=(args.checkout/'build/SMHasher3').resolve()
    # Ensure a newer snapshot cannot silently be tested against an older executable.
    sources=[args.checkout/'hashes/rainlocal.cpp',args.checkout/'hashes/rainlocal_core.cpp']
    sources+=list((args.checkout/'hashes/rainlocal_source').iterdir())
    if any(path.stat().st_mtime>exe.stat().st_mtime for path in sources):
        p.error('binary is older than the adapter snapshot; rebuild first')
    args.output.mkdir(parents=True,exist_ok=False)
    tests=subprocess.check_output([str(exe),'--tests'],text=True)
    (args.output/'available-tests.txt').write_text(tests)
    known=set('VerifyAll SanityAll SpeedAll All Sanity Speed SpeedSmall SpeedBulk Hashmap Avalanche Sparse Permutation Cyclic TwoBytes Text Zeroes Seed SeedZeroes SeedSparse SeedBlockLen SeedBlockOffset SeedBitflip SeedAvalanche SeedBIC PerlinNoise Bitflip BIC BadSeeds'.split())
    actual=set(tests.split('Valid tests:')[-1].split())
    if actual!=known: p.error('upstream test list changed; review full-suite selection before running')
    version=subprocess.check_output([str(exe),'--version'],text=True)
    (args.output/'version.txt').write_text(version)
    report={'mode':args.mode,'manifest':manifest,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'runs':[]}
    # At pinned upstream revision, All excludes only BadSeeds among per-hash
    # suites. VerifyAll/SanityAll/SpeedAll override selection and test unrelated
    # registered hashes, so they are not combined into this per-hash command.
    for name in args.hashes:
        for endian in (['native','nonnative'] if args.endian=='both' else [args.endian]):
            cmd=[str(exe),'--test='+('All,BadSeeds' if args.mode=='full' else 'Sanity'),
                 '--extra','--exit-code-on-failure',f'--endian={endian}',f'--ncpu={args.ncpu}',name]
            print('Running '+' '.join(cmd),flush=True)
            with (args.output/(name+'-'+endian+'.log')).open('w') as log:
                result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            report['runs'].append({'hash':name,'endian':endian,'command':cmd,'exit_code':result.returncode})
            (args.output/'run.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(int(any(run['exit_code'] for run in report['runs'])))

if __name__=='__main__': main()
