#!/usr/bin/env python3
"""Durable sequential full-suite campaign, with live JSON and Markdown results."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def atomic(path,data):
    temp=path.with_suffix(path.suffix+'.tmp'); temp.write_text(data); temp.replace(path)

def inspect_log(path):
    if not path.exists(): return {}
    text=path.read_text(errors='replace')
    stages=re.findall(r'\[\[\[ (.*?) \]\]\]',text)
    overall=re.search(r'Overall result: (pass|FAIL)\s+\(\s*(\d+)\s*/\s*(\d+) passed\)',text)
    runtime=re.search(r'Verification value is .*?Testing took ([\d.]+) seconds',text)
    small=re.findall(r'Average\s+-\s+([\d.]+) cycles/hash',text)
    bulk=re.findall(r'Average\s+-\s+([\d.]+) bytes/cycle\s+-\s+([\d.]+) GiB/sec',text)
    return {'stage':stages[-1] if stages else 'startup','completed_stages':stages,
            'reported_result':overall.group(1) if overall else None,
            'passed_checks':int(overall.group(2)) if overall else None,
            'total_checks':int(overall.group(3)) if overall else None,
            'elapsed_test_seconds':float(runtime.group(1)) if runtime else None,
            'complete_log':bool(overall and runtime),
            'small_cycles_per_hash':float(small[0]) if small else None,
            'bulk_bytes_per_cycle':[float(x[0]) for x in bulk],
            'bulk_gib_per_second_at_reference_3_5ghz':[float(x[1]) for x in bulk],
            'failure_marker_lines':[line for line in text.splitlines() if 'FAIL' in line],
            'skip_marker_lines':[line for line in text.splitlines() if re.search(r'\bskip',line,re.I)]}

def publish(directory,state):
    state['updated_utc']=now()
    for run in state['runs']: run['results']=inspect_log(directory/run['log'])
    atomic(directory/'status.json',json.dumps(state,indent=2)+'\n')
    lines=['# Full SMHasher3 comparison','',f"Updated: {state['updated_utc']}",'',
           '| Candidate | Status | Stage | Reported result | Checks | Small cycles/hash | Bulk bytes/cycle |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    for r in state['runs']:
        x=r['results']; checks=f"{x['passed_checks']}/{x['total_checks']}" if x.get('total_checks') is not None else 'pending'
        bulk=', '.join(map(str,x.get('bulk_bytes_per_cycle',[]))) or 'pending'
        lines.append(f"| {r['id']} | {r['status']} | {x.get('stage','pending')} | {x.get('reported_result') or 'pending'} | {checks} | {x.get('small_cycles_per_hash') or 'pending'} | {bulk} |")
    queued=json.loads((directory/'plan.json').read_text())['jobs']
    started={r['id'] for r in state['runs']}
    for job in queued:
        if job['id'] not in started:
            lines.append(f"| {job['id']} | queued | pending | pending | pending | pending | pending |")
    lines+=['','Bulk entries follow the full suite’s fixed-size and varying-size tests. Its GiB/s numbers use a reference 3.5 GHz; they are not direct wall-clock throughput measurements.',
            '','Incomplete logs are not passes. BLAKE3 control uses upstream’s seed adaptation with matched test-budget metadata.',
            '','Statistical results and speed do not establish cryptographic security. No winner is selected until all requested runs finish.']
    if state.get('finished_utc'):
        eligible=[r for r in state['runs'] if r['status']=='completed' and r['results'].get('reported_result')=='pass']
        small=[r for r in eligible if r['results'].get('small_cycles_per_hash') is not None]
        bulk=[r for r in eligible if r['results'].get('bulk_bytes_per_cycle')]
        lines+=['','## Completed comparison','']
        if len(eligible)!=len(state['runs']):
            lines.append(f"{len(eligible)} of {len(state['runs'])} runs completed with a reported statistical pass. See failed/incomplete logs before accepting a candidate.")
        if small:
            best=min(small,key=lambda r:r['results']['small_cycles_per_hash'])
            lines.append(f"Lowest reported small-key latency among passing runs: {best['id']} ({best['results']['small_cycles_per_hash']} cycles/hash).")
        if bulk:
            best=max(bulk,key=lambda r:r['results']['bulk_bytes_per_cycle'][0])
            lines.append(f"Highest reported fixed-size bulk throughput among passing runs: {best['id']} ({best['results']['bulk_bytes_per_cycle'][0]} bytes/cycle).")
        lines.append('These are results from one sequential campaign on a fanless machine. Thermal drift and measurement variation can affect close performance rankings; they do not rank security.')
    atomic(directory/'RESULTS.md','\n'.join(lines)+'\n')

def alive(pid):
    try: os.kill(pid,0); return True
    except ProcessLookupError: return False

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['run','status'])
    p.add_argument('--directory',type=Path,default=HERE/'campaign-20260907')
    p.add_argument('--adopt-original-pid',type=int)
    p.add_argument('--resume',action='store_true')
    args=p.parse_args(); directory=args.directory.resolve()
    status=directory/'status.json'
    if args.mode=='status':
        print((directory/'RESULTS.md').read_text()); return
    if status.exists() and not args.resume: raise SystemExit('A campaign already exists; use --resume only after its controller has stopped.')
    state={'started_utc':now(),'controller_pid':os.getpid(),'runs':[],
        'smhasher3_revision':subprocess.check_output(['git','-C',str(HERE/'vendor/smhasher3'),'rev-parse','HEAD'],text=True).strip(),
        'hardware':subprocess.check_output(['sysctl','-n','hw.model','hw.ncpu','hw.memsize'],text=True).splitlines()}
    if args.resume:
        state=json.loads(status.read_text())
        if alive(state['controller_pid']): raise SystemExit('Existing controller is still alive; refusing duplicate campaign.')
        state['controller_pid']=os.getpid()
        state.pop('finished_utc',None)
        state.pop('controller_error',None)
        active=[r for r in state['runs'] if r['status']=='running']
        if active:
            if len(active)!=1: raise SystemExit('Multiple active runs recorded; refusing to guess ownership.')
            if active[0]['id']=='OG-256':
                args.adopt_original_pid=active[0]['pid']
            else:
                run=active[0]
                while alive(run['pid']):
                    publish(directory,state); time.sleep(10)
                run['status']='completed' if inspect_log(directory/run['log']).get('complete_log') else 'incomplete-external-exit'
                run['exit_code']=None
                run['exit_code_note']='Process adopted after controller restart; inspect the final test summary.'
                run['finished_utc']=now(); publish(directory,state)
    if args.adopt_original_pid:
        original={'id':'OG-256','log':'og-256-native.log','status':'running','pid':args.adopt_original_pid,
            'exit_code':None,'exit_code_note':'Adopted external run; completion is checked from SMHasher3’s final summary and footer.',
            'binary_sha256':hashlib.sha256((directory/'bin/SMHasher3-original').read_bytes()).hexdigest(),
            'command':['SMHasher3-original','--test=All,BadSeeds','--extra','--exit-code-on-failure','--endian=native','--ncpu=4','rainlocal-rainstorm-256']}
        previous=next((r for r in state['runs'] if r['id']=='OG-256'),None)
        if previous: original=previous
        else: state['runs'].append(original)
        while alive(args.adopt_original_pid):
            publish(directory,state); time.sleep(10)
        results=inspect_log(directory/original['log'])
        original['status']='completed' if results.get('complete_log') else 'incomplete-external-exit'
        original['finished_utc']=now(); publish(directory,state)
    # The plan can be updated before a queued run starts, without disrupting
    # the currently running hash. Completed job IDs are never rerun silently.
    done={run['id'] for run in state['runs']}
    while True:
        plan=json.loads((directory/'plan.json').read_text())
        remaining=[job for job in plan['jobs'] if job['id'] not in done]
        if not remaining: break
        job=remaining[0]
        marker=directory/'candidate-ready.json'
        while not marker.exists():
            failure=directory/'candidate-build.failed'
            if failure.exists():
                state['controller_error']=failure.read_text(); publish(directory,state)
                raise SystemExit('Candidate build failed; see candidate-build.log')
            publish(directory,state); time.sleep(10)
        src=HERE/'vendor/smhasher3/build/SMHasher3'
        dst=directory/'bin/SMHasher3-candidates'
        if not dst.exists(): raise SystemExit('Frozen candidate binary is missing; do not silently replace it.')
        expected=json.loads(marker.read_text())
        if not expected.get('passed') or hashlib.sha256(dst.read_bytes()).hexdigest()!=expected['binary_sha256']:
            state['controller_error']='Candidate binary does not match validated provenance'; publish(directory,state)
            raise SystemExit(state['controller_error'])
        cmd=[str(dst),'--test=All,BadSeeds','--extra','--exit-code-on-failure',
             '--endian='+job.get('endian','native'),'--ncpu=4',job['hash']]
        run={'id':job['id'],'command':cmd,'log':job['id'].lower()+'.log','status':'running','started_utc':now(),
             'binary_sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}
        state['runs'].append(run)
        with (directory/run['log']).open('w') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            run['pid']=proc.pid
            while proc.poll() is None:
                publish(directory,state); time.sleep(10)
            run['exit_code']=proc.returncode
        results=inspect_log(directory/run['log'])
        run['status']='completed' if results.get('complete_log') else 'incomplete-process-exit'
        run['finished_utc']=now(); done.add(job['id']); publish(directory,state)
    state['finished_utc']=now(); publish(directory,state)

if __name__=='__main__': main()
