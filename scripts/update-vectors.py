#!/usr/bin/env python3
"""Regenerate published vectors from the built native CLI; verify WASM separately."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    vectors = []
    for algorithm, sizes in [('rainbow', (64,128,256)), ('rainstorm', (64,128,256,512))]:
        for bits in sizes:
            output = subprocess.check_output([str(ROOT/'rainsum'), '--test-vectors',
                                              '-a', algorithm, '-s', str(bits)], text=True)
            for line in output.splitlines():
                digest, message = line.split(' ', 1)
                assert re.fullmatch('[0-9a-f]{'+str(bits//4)+'}', digest)
                vectors.append(dict(algorithm=algorithm,bits=bits,seed='0',
                                    message=json.loads(message),hex=digest))
    storm = {v['message']:v['hex'] for v in vectors if v['algorithm']=='rainstorm' and v['bits']==256}
    api = ROOT/'js/lib/api.mjs'
    section = api.read_text().split('const STORM_TV = [',1)[1].split('];',1)[0]
    replacements = {}
    for digest, encoded in re.findall(r'\[\s*"([0-9a-f]+)",\s*("[^"\n]*")\s*\]',section):
        replacements[digest] = storm[json.loads(encoded)]
    assert len(replacements)==7
    for name in ('js/lib/api.mjs','js/rainsum.mjs','docs/app.js','src/streaming-test.cpp'):
        path=ROOT/name; text=path.read_text()
        for old,new in replacements.items(): text=text.replace(old,new)
        path.write_text(text)
    spec=ROOT/'docs/paper/storm-spec.tex'
    text=re.sub(r'(Message: ("[^"\n]*")\nDigest: )[0-9a-f]+',
                lambda m:m[1]+storm[json.loads(m[2])],spec.read_text())
    spec.write_text(text)
    version=json.loads((ROOT/'js/package.json').read_text())['version']
    (ROOT/'js/test-vectors.json').write_text(json.dumps(dict(version=version,vectors=vectors),indent=2)+'\n')
    print(f'Updated {len(vectors)} vectors across every supported digest size.')

if __name__=='__main__': main()
