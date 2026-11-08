#!/usr/bin/env python3
"""Bundle only SMHasher3 sources and public runner scripts; no credentials."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    vendor = here / 'vendor/smhasher3'
    files = set(subprocess.check_output(
        ['git', '-C', str(vendor), 'ls-files'], text=True).splitlines())
    # Include our untracked adapters; never include .git, builds, or home files.
    for pattern in ('hashes/rainlocal*', 'hashes/rainexp*'):
        for path in vendor.glob(pattern):
            if path.is_file():
                files.add(str(path.relative_to(vendor)))
            else:
                files.update(str(q.relative_to(vendor)) for q in path.rglob('*') if q.is_file())
    manifest = {f: hashlib.sha256((vendor / f).read_bytes()).hexdigest()
                for f in sorted(files) if (vendor / f).is_file()}
    for required in ('hashes/rainlocal.cpp', 'hashes/rainexp.cpp'):
        if required not in manifest:
            raise SystemExit('Run the SMHasher3 adapter preparation scripts first')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, 'w:gz') as archive:
        for name in manifest:
            archive.add(vendor / name, arcname='smhasher3/' + name, recursive=False)
        for name in ('cloud_run.py', 'cloud_build.sh'):
            archive.add(here / name, arcname=name)
        data = json.dumps(manifest, indent=2).encode()
        entry = tarfile.TarInfo('source-manifest.json')
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
        info = {
            'upstream_revision': subprocess.check_output(
                ['git', '-C', str(vendor), 'rev-parse', 'HEAD'], text=True).strip(),
            'source_manifest_sha256': hashlib.sha256(data).hexdigest(),
            'runner_sha256': {n: hashlib.sha256((here / n).read_bytes()).hexdigest()
                              for n in ('cloud_run.py', 'cloud_build.sh')},
        }
        data = json.dumps(info, indent=2).encode()
        entry = tarfile.TarInfo('bundle-info.json')
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
    print(f'{len(manifest)} source files; {args.output.stat().st_size} bytes')

if __name__ == '__main__':
    main()
