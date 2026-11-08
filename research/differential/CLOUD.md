# Run the comparison on an existing Linux SSH host

The scripts provision no cloud resources and contain no cloud credentials,
account names, SSH keys, or fixed host addresses. Use your own SSH config alias.
They need the prepared SMHasher3 checkout described in SMHASHER3.md and the
experimental adapters from `prepare_variant_smhasher3.py`.

To reproduce the OG/A/B/C comparison after v4 was promoted, prepare the frozen
pre-v4 reference as OG (otherwise the default adapter uses current production):

```sh
python3 research/differential/build_variants.py
python3 research/differential/prepare_smhasher3.py --source-root research/differential/reference
python3 research/differential/prepare_variant_smhasher3.py
```

On an Ubuntu 24.04 host, install dependencies once:

```sh
sudo apt-get update
sudo apt-get install -y build-essential cmake python3 git rsync
```

From this repository, upload, build, and start the full sequential campaign:

```sh
bash research/differential/cloud_upload.sh YOUR_SSH_ALIAS 8
```

The second argument controls build parallelism and SMHasher3 `--ncpu`.
The command prints a unique remote directory. Inside it, `build-and-run.log`
captures preparation and build output, and `results/` holds per-hash logs,
exit codes, completion summaries, and machine/binary provenance. The command
starts a detached process; a successful upload is not a successful test run.
Use a fresh directory for each campaign; the runner refuses to overwrite results.

The archive includes tracked SMHasher3 source files at their current working-tree
contents plus the local/experimental adapter sources, and a SHA-256 manifest.
It excludes `.git`, compiled binaries, the user's home directory and credentials.
The receiver verifies the source manifest before building natively for its CPU.
The build supplies `-include cstdlib` because upstream `lib/AEStest.cpp` calls
`exit()` without its declaration on GCC/Linux. This adds a standard header;
hash and statistical test source files are unchanged. The compiler flags are
preserved in the result's CMake cache.

The runner validates native and nonnative Sanity for all five registrations,
then runs original, A, B, C and BLAKE3 control, sequentially, each with
`--test=All,BadSeeds --extra --exit-code-on-failure --endian=native`.
This is the 256-bit comparison. A pass requires the final summary and timing
footer as well as a successful exit. Preserve failures as findings; an interrupted
run is incomplete. The seed sweep cannot resume from printed checkpoints.

Copy logs back regularly, especially before any machine expiration:

```sh
rsync -az YOUR_SSH_ALIAS:REMOTE_DIRECTORY/results/ LOCAL_RESULTS_DIRECTORY/
```

Machine creation, billing limits and automatic deletion are external to these
scripts. A powered-off Hetzner instance still incurs charges: expiration must
delete the instance and its chargeable primary IP. Keep deletion credentials
and scheduling records outside the public repository. Deletion must not wait
for these tests or for log collection.
