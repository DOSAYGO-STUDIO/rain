#!/usr/bin/env python3
"""Descriptive comparison of matched SMHasher logs, not a security score."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import statistics

FAMILIES = ('Avalanche Tests', "BIC 'Bit Independence Criteria' Tests",
            'Seed Avalanche Tests', "Seed 'Bit Independence Criteria' Tests")

def parse(path):
    text = path.read_text(errors='replace')
    stage = ''
    rows = []
    metrics = {s: [] for s in FAMILIES}
    for number, line in enumerate(text.splitlines(), 1):
        header = re.search(r'\[\[\[ (.*?) \]\]\]', line)
        if header:
            stage = header[1]
        marker = re.search(r'\(\^\s*(\d+)\)', line)
        if marker:
            rows.append(dict(section=stage, line=number, k=int(marker[1]), text=line))
        m = re.search(r'Testing\s+(\d+)-byte keys.*?(?:max is ([\d.]+)%|max ([\d.]+) at bit)', line)
        if m and stage in metrics:
            metrics[stage].append(dict(key_bytes=int(m[1]), value=float(m[2] or m[3])))
    summary = re.search(r'Overall result: (pass|FAIL)\s+\(\s*(\d+)\s*/\s*(\d+) passed\)', text)
    return dict(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        result=summary[1] if summary else 'incomplete',
        summary=summary[0] if summary else None,
        small_cycles=float(re.search(r'Average\s+-\s+([\d.]+) cycles/hash', text)[1]),
        bulk_bytes_per_cycle=[float(x) for x in re.findall(r'Average\s+-\s+([\d.]+) bytes/cycle', text)],
        metrics=metrics, rows=rows,
        metric_summary={s:dict(count=len(v), mean=statistics.mean(x['value'] for x in v),
                               maximum=max(x['value'] for x in v)) for s,v in metrics.items()},
        tail_k_max=max(r['k'] for r in rows),
        tail_k_ge10=sum(r['k'] >= 10 for r in rows),
        tail_k_ge16=sum(r['k'] >= 16 for r in rows),
        distribution_k_max=max(r['k'] for r in rows if 'Testing distribution' in r['text']))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('logs', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    data = {n:parse(args.logs / f'{n}-256-native.log') for n in ('OG','A','B','C')}
    for n, d in data.items():
        if [r['section'] for r in d['rows']] != [r['section'] for r in data['OG']['rows']]:
            raise SystemExit(f'{n}: statistical row coverage differs; cannot compare directly')
        d['paired_vs_original'] = {}
        for family in FAMILIES:
            original = data['OG']['metrics'][family]
            candidate = d['metrics'][family]
            if [r['key_bytes'] for r in original] != [r['key_bytes'] for r in candidate]:
                raise SystemExit(f'{n}: unmatched key lengths in {family}')
            counts = collections.Counter('lower' if b['value'] < a['value'] else
                                         'higher' if b['value'] > a['value'] else 'tied'
                                         for a,b in zip(original,candidate))
            d['paired_vs_original'][family] = dict(counts)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'statistics.json').write_text(json.dumps(data,indent=2)+'\n')
    lines = ['# SMHasher3 descriptive comparison', '',
        'Scope: 256-bit native, full extended budgets, same cloud machine and binary. '
        'Original, A and B have completed; C is provisional until its final footer appears. '
        'BLAKE3 is not included until comparable logs exist.', '',
        '| Metric | Original | A | B | C |', '|---|---:|---:|---:|---:|']
    def row(label, values):
        lines.append('| '+label+' | '+' | '.join(map(str,values))+' |')
    row('Run result', [d['result'] for d in data.values()])
    for family in FAMILIES:
        row(f'{family}: mean of per-case maxima',
            [f"{d['metric_summary'][family]['mean']:.5f}" for d in data.values()])
        row(f'{family}: worst maximum',
            [f"{d['metric_summary'][family]['maximum']:.4f}" for d in data.values()])
    for key,label in [('tail_k_max','Largest p-value marker k'),
                      ('tail_k_ge10','Reported rows with k >= 10'),
                      ('tail_k_ge16','Reported rows with k >= 16'),
                      ('distribution_k_max','Largest distribution marker k'),
                      ('small_cycles','Small-key cycles/hash')]:
        row(label,[d[key] for d in data.values()])
    row('Fixed-size bulk bytes/cycle',[d['bulk_bytes_per_cycle'][0] for d in data.values()])
    lines += ['', '## Interpretation', '',
        '- A has lower seed-avalanche bias than OG in 10/12 matched cases, '
        'but lower input-avalanche bias in only 8/21. This is a narrow favorable pattern, '
        'not evidence of a uniformly better statistical distribution.',
        '- B preserves baseline speed in this measurement. Its seed BIC has the weakest '
        'observed maximum (0.0191 at 1024 bytes), still below the suite warning threshold.',
        '- C has the least extreme maximum k overall, but the most extreme distribution k. '
        'Its seed sweep remains incomplete in this snapshot.',
        '- No reported p-value row reaches the warning threshold. Truncated collision '
        'fluctuations are not full-digest collisions.', '',
        '## Definitions and limits', '',
        'Avalanche numbers are the suite percentages: 200 × |observed flip probability − 0.5|. '
        'Thus 0.920% corresponds to a 0.460-percentage-point deviation from 50%, '
        'not a 0.920-point deviation. BIC values are the suite maximum Cramér’s V. '
        'Means here average per-case maxima, not every individual tested bit.', '',
        'The displayed (^k) is floor(−log2(p)), capped at 99. Larger k is a more extreme '
        'reported deviation. Upstream warning/failure bounds are 2^-16 / 2^-20. '
        'See util/Reporting.cpp (ReportBias, ReportChiSqIndep, ReportDistribution) and '
        'util/Stats.cpp (GetLog2PValue) in the pinned upstream checkout.', '',
        'There are 5,066 reported p-value rows per candidate, including 230 distribution rows. '
        'Rows are dependent, include overlapping truncations, and some reported p-values '
        'are bounds or already adjusted for within-test searches. Their maxima and tail '
        'counts are descriptive; do not combine them as independent observations or '
        'interpret higher p-values as greater security. These are single deterministic '
        'campaigns, with no independent-seed replication or prespecified superiority test.', '',
        'A uses 11.6% more small-key cycles than OG; C uses 116.2% more. B differs by '
        'less than 0.3%, too little to declare a speed win from one run. Rounded bulk '
        'measurements are also descriptive. Statistical testing does not resolve the '
        'separate state-loss/invertibility analysis or prove collision resistance.', '',
        'Machine-readable statistics.json contains source-log fingerprints, individual '
        'metrics, matched-case comparisons and every scored log line for audit.']
    (args.output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(args.output/'REPORT.md')

if __name__ == '__main__':
    main()
