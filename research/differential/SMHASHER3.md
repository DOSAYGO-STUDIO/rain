# SMHasher3 setup and acceptance runs

This file records the initial pre-v4 setup. Candidate A subsequently passed
the full 256-bit native campaign and was promoted as v4.0.0; see
[release validation](../../results/rainstorm-4.0.0/README.md). To reproduce the
original comparison, pass `--source-root research/differential/reference`
to `prepare_smhasher3.py`. Its default snapshots current production instead.

Cloned the full official repository, including its history, from
https://gitlab.com/fwojcik/smhasher3 into `vendor/smhasher3` (ignored by Git).
The pinned revision and exact production-source fingerprints are recorded in
[smhasher3-manifest.json](smhasher3-manifest.json).

CMake was installed into the local `vendor/build-tools` Python environment.
The full build completed successfully, and all six exact-source registrations
passed extended Sanity on both native and swapped paths: 12 successful
runs, with verification, basic sanity, zero-extension, and thread-safety
checks. Local smoke logs are runtime artifacts and are not committed.
These are smoke checks only.

The local source adapter preserves upstream test code and adds six separately
named hashes backed by snapshots of this repository's actual implementation.
Upstream hash registrations remain intact for comparison. Verification codes
are calculated from the snapshots using SMHasher3's defined verification
procedure, for both native and swapped paths.

To set up again from a fresh checkout:

```sh
git clone https://gitlab.com/fwojcik/smhasher3.git research/differential/vendor/smhasher3
git -C research/differential/vendor/smhasher3 checkout 3b619371047761408406991685da1c2b3f751899
python3 -m venv research/differential/vendor/build-tools
research/differential/vendor/build-tools/bin/pip install cmake==4.4.3
python3 research/differential/prepare_smhasher3.py
research/differential/vendor/build-tools/bin/cmake \
  -S research/differential/vendor/smhasher3 \
  -B research/differential/vendor/smhasher3/build -DCMAKE_BUILD_TYPE=Release
research/differential/vendor/build-tools/bin/cmake \
  --build research/differential/vendor/smhasher3/build -j 4
```

After any production candidate change, rerun preparation and build. The runner
rejects stale snapshots or a binary older than the adapter sources. Run the
complete per-hash collection for all six supported variants:

```sh
python3 research/differential/run_smhasher3.py --mode full --ncpu 4 \
  --output research/differential/vendor/full-candidate-001
```

This executes `--test=All,BadSeeds --extra --exit-code-on-failure`, for
both native and swapped paths by default (`--endian` can restrict it).
The failure-exit flag matters: upstream otherwise returns zero even on test
failures. The runner also rejects an unexpected available-test list. At the pinned revision, BadSeeds
is the only per-hash suite omitted by All. `VerifyAll`, `SanityAll`, and
`SpeedAll` are whole-registry override modes, not additional per-hash tests;
combining them would silently replace the requested candidate test run.
The runner saves the available-test list, binary hash, tool version,
source fingerprints, complete logs, commands, and exit codes. Review test
failures and skipped tests in the logs; a successful process is not itself
proof that every desired check ran. Full extended tests, especially BadSeeds,
can be very expensive. Revisit the selected suite list after updating upstream.

A separate `--mode smoke` runs extended Sanity only. It is explicitly not an
acceptance run. `--hashes rainlocal-rainstorm-256` can restrict a run to a
particular candidate.

Two integration limitations surfaced:

- Upstream Testlib only instantiates output widths through 256 bits. It cannot
  run full-width Rainstorm-512 tests merely by adding a registration. That
  needs a separately audited Testlib extension; testing two truncated halves
  is not equivalent. The differential suite here does test the full 512-bit
  production digest.
- Upstream Rainstorm explicitly byte-swaps the padded final words in its
  swapped path; this repository's implementation does not. Their LE
  verification constants match, but the swapped constants differ. The
  adapter intentionally tests the repository source and records its own
  constants rather than silently testing upstream's different implementation.
  This source discrepancy should be resolved when specifying portability
  for a new version.

No full statistical repair-acceptance result is claimed: no production repair
has been applied. The current setup is the harness to use when implementing
and comparing the proposals in [REPAIRS.md](REPAIRS.md).
