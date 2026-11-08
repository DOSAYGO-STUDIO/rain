#!/usr/bin/env python3
"""Run the frozen cloud bundle, sequentially; retain logs and explicit exit codes."""
import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ncpu', type=int, default=32)
    args = p.parse_args()
    if args.ncpu < 1:
        p.error('ncpu must be positive')
    root = Path(__file__).resolve().parent
    out = root / 'results'
    out.mkdir(exist_ok=False)  # Never overwrite an earlier run.
    binary = root / 'smhasher3/build/SMHasher3'
    provenance = {
        'platform': platform.platform(), 'ncpu': args.ncpu,
        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'cpu': subprocess.check_output(['lscpu'], text=True),
        'compiler': subprocess.check_output(['c++', '--version'], text=True),
        'started_unix': time.time(),
    }
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    for name in ('bundle-info.json', 'source-manifest.json'):
        shutil.copyfile(root / name, out / name)
    shutil.copyfile(root / 'smhasher3/build/CMakeCache.txt', out / 'CMakeCache.txt')
    jobs = [('OG', 'rainlocal-rainstorm-256'), ('A', 'rainexp-a-256'),
            ('B', 'rainexp-b-256'), ('C', 'rainexp-c-256'),
            ('BLAKE3', 'raincontrol-blake3-256')]
    # Validate both endian registrations before the full native campaign.
    for label, name in jobs:
        for endian in ('native', 'nonnative'):
            with (out / f'{label}-sanity-{endian}.log').open('w') as log:
                subprocess.run([str(binary), '--test=Sanity', '--extra',
                    '--exit-code-on-failure', f'--endian={endian}',
                    f'--ncpu={args.ncpu}', name], stdout=log,
                    stderr=subprocess.STDOUT, check=True)
    results = []
    for label, name in jobs:
        command = [str(binary), '--test=All,BadSeeds', '--extra',
                   '--exit-code-on-failure', '--endian=native',
                   f'--ncpu={args.ncpu}', name]
        record = {'id': label, 'command': command, 'started_unix': time.time()}
        results.append(record)
        def save():
            (out / 'status.json').write_text(json.dumps(results, indent=2))
        save()
        path = out / f'{label}-256-native.log'
        with path.open('w') as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            record['pid'] = proc.pid
            save()
            record['exit_code'] = proc.wait()
        text = path.read_text(errors='replace')
        summary = re.search(r'Overall result: (pass|FAIL)\s+\(\s*(\d+)\s*/\s*(\d+) passed\)', text)
        footer = re.search(r'Verification value is .*?Testing took ([\d.]+) seconds', text)
        record.update(finished_unix=time.time(), complete=bool(summary and footer),
                      result=summary.group(1) if summary else 'incomplete')
        save()
    return int(any(r['exit_code'] != 0 or not r['complete'] or r['result'] != 'pass' for r in results))

if __name__ == '__main__':
    raise SystemExit(main())
