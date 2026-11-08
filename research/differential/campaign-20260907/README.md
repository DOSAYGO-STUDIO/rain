# Sequential comparison campaign (in progress)

Requested 2026-09-07: compare the original Rainstorm with concrete alternatives
using the full SMHasher3 per-hash collection, sequentially, and collect
statistical and speed results. No production algorithm is being replaced.

The first run is the exact original 256-bit native implementation:

```
SMHasher3-original --test=All,BadSeeds --extra --exit-code-on-failure \
  --endian=native --ncpu=4 rainlocal-rainstorm-256
```

Log: `og-256-native.log`. Absence of failures in an incomplete log is not a
pass. Extended BadSeeds alone enumerates two ranges of 2^32 seeds, with 90
messages per seed: 773,094,113,280 hash evaluations plus collision analysis.

Candidate definitions are generated from the original source and fingerprinted
in `../variants/manifest.json`:

- A: final right-round subtraction targets low word 0; original finalization.
- B: double only the last right-round counter subtraction; original finalization.
- C: A, plus four right/left/right/left final rounds for every output width,
  plus an initial 64-byte domain block. Its eight little-endian words are:
  ASCII `RNSTEXP1`, version 1, requested output bits, public seed, original
  message byte length, zero, zero, zero. The normal length-dependent IV and
  message padding remain. Prefix absorption uses four normal rounds. Thus
  256-bit C adds one block of work and changes final round direction; it does
  not claim a chosen security margin.
- Optional D: original absorbing rounds, four alternating final rounds only.
  This isolates the finalization change while preserving the original loss.

The original fourth proposal was an established full-message hash. BLAKE3-256
is the provisional control unless the user selects finalization-only D.
SMHasher3's BLAKE3 registration has a homegrown seeding adaptation. The
control retains that exact implementation but removes its VERY_SLOW metadata
flag so test sizes/repetitions match the original and A/B/C. This tests the
upstream seeded adapter; it is not a claim about standard BLAKE3 under a
newly invented seed API.

Interpretation correction: the upper half already contributes through prior
rounds and the fold. Ignoring it afterwards can be intentional. Moreover,
the left-only final map is itself a permutation of the low 512 bits for a
fixed last block: it rearranges/mixes what remains, rather than additionally
compressing that low half. Final truncation discards the rest. Our proved
absence of backward diffusion and the cross-size relationship are properties
to evaluate, not a proof that this arrangement is insecure. Likewise, making
a round invertible does not make the full hash invertible after truncation.

Ranking will report statistical failures first, then speed among candidates
that complete the same tests. It will not rank cryptographic security by
SMHasher3 p-values. Performance tests should run without another campaign or
heavy build running concurrently. Any incomplete/aborted run will be labeled
as such, and any compiler/build noise affecting timings will be recorded.

## Validated and running

- Original and candidate benchmark binaries are frozen in `bin/`; fingerprints
  and compiler/source provenance are in `provenance.json`.
- The four Rainstorm experiment sources passed 2,496 native-reference/streaming
  comparisons and 3,744 ASan/UBSan streaming comparisons.
- Their four differential screens each tested 131,072 pairs with no full-hash
  collisions and no bit/byte projection alerts on lengths greater than one.
  One-byte-domain alerts have the small-domain interpretation documented in
  the main analysis; these screens are not full SMHasher3 results.
- All twelve experiment registrations (A/B/C/D at 64/128/256) plus the BLAKE3
  control passed extended SMHasher3 Sanity on both native and swapped paths:
  26 runs, saved under `candidate-sanity/`.
- `plan.json` queues A-256, B-256, C-256, BLAKE3-256 after the running OG-256.
  The original fourth proposal is therefore represented by the BLAKE3 control;
  finalization-only D is validated but not queued in the provisional campaign.
- The controller is detached, records its PID in `controller.pid`, and updates
  `status.json` and `RESULTS.md` every ten seconds. It waits for each full run
  before starting the next. It verifies the frozen candidate binary against
  the successful preflight fingerprint. A statistical failure is collected
  rather than causing the other candidates to be omitted.
- Once all queued runs end, the results report identifies the lowest reported
  small-key latency and highest reported bulk throughput among completed
  statistical passes. Incomplete or failed runs are not counted as passes.
  Close speed rankings need a controlled repeat because this fanless machine
  can change frequency during sustained tests.

Read current state without launching another campaign:

```
python3 research/differential/campaign.py status
```

If the controller itself has stopped, `campaign.py run --resume` adopts any
still-running recorded hash before proceeding; it refuses to start while an
existing controller is alive. Do not launch duplicate full runs, since they
would spoil the sequential performance comparison. Completion remains pending
until each log contains both the full summary and final timing footer.
