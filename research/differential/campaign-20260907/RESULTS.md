# Full SMHasher3 comparison

Updated: 2026-09-07T21:02:35.050355+00:00

| Candidate | Status | Stage | Reported result | Checks | Small cycles/hash | Bulk bytes/cycle |
| --- | --- | --- | --- | --- | --- | --- |
| OG-256 | running | BadSeeds Tests | pending | pending | 137.91 | 0.62, 0.66 |
| A-256 | queued | pending | pending | pending | pending | pending |
| B-256 | queued | pending | pending | pending | pending | pending |
| C-256 | queued | pending | pending | pending | pending | pending |
| BLAKE3-256 | queued | pending | pending | pending | pending | pending |

Bulk entries follow the full suite’s fixed-size and varying-size tests. Its GiB/s numbers use a reference 3.5 GHz; they are not direct wall-clock throughput measurements.

Incomplete logs are not passes. BLAKE3 control uses upstream’s seed adaptation with matched test-budget metadata.

Statistical results and speed do not establish cryptographic security. No winner is selected until all requested runs finish.

Local campaign stopped at user request on 2026-09-07T21:03:05.441028+00:00. The original run is incomplete; queued candidates were not started.
