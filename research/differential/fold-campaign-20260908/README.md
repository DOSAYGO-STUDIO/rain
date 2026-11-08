# Bounded fold campaign: 2026-09-08

This directory records the first matched OG/A Z3 campaign for reachable fold
cancellation. It is a bounded experiment, not a security result.

## Fixed instance

- Z3 4.15.4 under Python 3.14.4
- Darwin 25.5.0 on arm64
- 64-byte messages, public seed zero
- first 8 bytes symbolic in each message; remaining 56 bytes zero
- exact 64-bit bit-vector arithmetic
- 60-second solver timeout for every query
- variants run sequentially

The four target sets were word 0, words 0--1, words 0--3, and words 0--7.

## Results

| Variant | Equal fold words | Status | Solver seconds | Artifact |
| --- | --- | --- | ---: | --- |
| OG | 0 | unknown | 61.370 | `og-words-0.json` |
| A | 0 | unknown | 61.438 | `a-words-0.json` |
| OG | 0--1 | unknown | 61.500 | `og-words-0-1.json` |
| A | 0--1 | unknown | 61.482 | `a-words-0-1.json` |
| OG | 0--3 | unknown | 61.332 | `og-words-0-3.json` |
| A | 0--3 | unknown | 60.088 | `a-words-0-3.json` |
| OG | 0--7 | unknown | 60.085 | `og-words-0-7.json` |
| A | 0--7 | unknown | 61.557 | `a-words-0-7.json` |

All eight runs exhausted approximately their configured timeout. Total time
inside `solver.check()` was 488.852 seconds. There was no SAT witness and no
UNSAT proof. Every result is therefore inconclusive.

The campaign was run immediately before `smt_fold.py` gained explicit
`unknown_reason` reporting. The configured timeouts and elapsed values strongly
identify timeout as the cause, but the raw artifacts intentionally remain
unchanged and do not contain that later field.

## Interpretation

Increasing the timeout is not guaranteed to produce SAT or UNSAT. For the
one-word target, a generic collision is expected to exist in a random mapping
from the 64-bit symbolic prefix to one 64-bit fold word, but the monolithic
two-copy SMT encoding may still be a poor way to find it. For wider targets,
the bounded mapping may be injective, but a timeout cannot establish that.

The next useful direction is to derive and search fixed differential trails,
then constrain one symbolic message and a chosen input difference. This can
reduce solver freedom and provides a probability-based comparison with generic
behavior.
