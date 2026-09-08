"""Keep compilation out of OG's timed speed/hashmap sections."""
import os
from pathlib import Path
import subprocess
import time
ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'research/differential'
log=Path(__file__).with_name('og-256-native.log')
while True:
    text=log.read_text(errors='replace')
    if '[[[ Avalanche' in text or 'Testing took' in text: break
    try: os.kill(16252,0)
    except ProcessLookupError: break
    time.sleep(10)
try:
    with Path(__file__).with_name('candidate-build.log').open('w') as out:
        for cmd in [
            ['python3',str(HERE/'test_variants.py')],
            ['c++','-std=c++17','-O1','-fsanitize=address,undefined',str(HERE/'variants/sanitizer_test.cpp'),'-o',str(HERE/'campaign-20260907/bin/variant-sanitizer')],
            [str(HERE/'campaign-20260907/bin/variant-sanitizer')],
            ['python3',str(HERE/'scan_variants.py')],
            ['python3',str(HERE/'prepare_variant_smhasher3.py')],
            [str(HERE/'vendor/build-tools/bin/cmake'),'--build',str(HERE/'vendor/smhasher3/build'),'-j','2']]:
            out.write('COMMAND: '+' '.join(cmd)+'\n'); out.flush()
            subprocess.run(cmd,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
    Path(__file__).with_name('candidate-build.complete').write_text('Native reference/streaming checks and SMHasher3 build passed.\n')
except Exception as exc:
    Path(__file__).with_name('candidate-build.failed').write_text(repr(exc)+'\n')
    raise
