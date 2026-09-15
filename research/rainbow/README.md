# Rainbow pair-sum cryptanalysis

Collision attacks against **full, unreduced** Rainbow v3.7.1 (`src/rainbow.cpp`).
Nothing here modifies Rainbow; every witness is replayed through the untouched
production source and through the shipped `rainsum` CLI.

Paper: [`output/pdf/rainbow-pair-sum-cryptanalysis.tex`](../../output/pdf/rainbow-pair-sum-cryptanalysis.tex)

## The finding in one paragraph

Rainbow injects each 16-byte block as `h0 -= x; h1 += x; h2 += y; h3 -= y`, so
injection **preserves the two pair sums** `s1 = h0+h1` and `s2 = h2+h3` exactly,
while letting the attacker move the state anywhere else inside the coset they
define. Two states therefore merge into the *identical* state under one further
block, with **zero search**, if and only if their pair sums agree — this is an
iff, so the other 128 bits of state are attacker-erasable. And because `mixA`
never moves information between `(h0,h1)` and `(h2,h3)`, the two sums are
refreshed by two independent 64-bit maps. A nominally 256-bit collision problem
becomes two independent 64-bit searches.

Consequence: **the digest width is decorative for collisions.** One message pair
collides at 64, 128 and 256 bits at once, because the internal states are equal
before finalization starts.

| Variant | Generic collision cost | Cost here | Shortfall |
|---|---|---|---|
| rainbow-64 | 2^32 | 2^32.3 | none (generic) |
| rainbow-128 | 2^64 | 2^32.3 | ~2^32 |
| rainbow-256 | 2^128 | 2^32.3 | ~2^96 |

Rainbow is documented as a non-cryptographic hash and claims no collision
resistance, so nothing it claims is refuted. What fails is the implicit idea
that picking a wider digest buys proportionally more collision resistance.

## Results

**Same-seed collision** — two 32-byte messages, 2^32.28 evaluations, 6.6 s on 8 cores.

```
a = 2f364d27a71c36f20000000000000000dbc4cde348f671ec0000000000000000
b = c16862808118f8170000000000000000ebc98b7034e669320000000000000000
rainbow-256(a) = rainbow-256(b) = b013b427e381f006c89c06357350be4be142f3bdc749f11c58acc1b99a4d91e3
```

**Chosen-prefix collision** — two 96-byte messages with opposed meanings,
2^34.80 evaluations, 50 s on 8 cores.

```
"From: alice@example.com  Amount: USD      10.00"
"From: mallory@example.net Amount: USD 1000000.00"
rainbow-256(a) = rainbow-256(b) = 913ac822c5f4c8fe40cb08c0af232d8ab58e007cc27e827269d591fd423682db
```

## Files

| File | Purpose |
|---|---|
| `collision_pair_sum.cpp` | Same-seed attack: rho search on `H(x) = A(x)+B(x)`, emits the merged pair |
| `chosen_prefix_collision.cpp` | Chosen-prefix attack: two claws + bridge; also the theorem self-test |
| `replay_production.cpp` | Includes `src/rainbow.cpp` **verbatim**; the authority on any claimed collision |
| `verify_pair_sum.py` | Independent Python (big-int) implementation; re-derives everything from the message bytes and prints a checkpoint trace |
| `collision-result.json` | Same-seed witness + full search accounting |
| `chosen-prefix-result.json` | Chosen-prefix witness + full search accounting |

The three C++ tools each transcribe Rainbow's arithmetic *independently* rather
than sharing a header. That duplication is deliberate: it makes agreement
between them evidence rather than tautology.

## Reproducing

```bash
mkdir -p research/rainbow/bin
for t in collision_pair_sum chosen_prefix_collision replay_production; do
  clang++ -std=c++20 -O3 -march=native -o research/rainbow/bin/$t research/rainbow/$t.cpp
done

# same-seed collision (~7 s on 8 cores)
./research/rainbow/bin/collision_pair_sum --seed=0 --dp-bits=20 --threads=8

# chosen-prefix collision (~50 s on 8 cores); runs the theorem self-test first
./research/rainbow/bin/chosen_prefix_collision --dp-bits=20 --threads=8

# independent verification
python3 research/rainbow/verify_pair_sum.py research/rainbow/collision-result.json
python3 research/rainbow/verify_pair_sum.py research/rainbow/chosen-prefix-result.json

# production replay (authority)
./research/rainbow/bin/replay_production <hex_a> <hex_b> 0

# shipped CLI, as a fourth opinion
make rainsum
printf '<bytes>' > /tmp/a.bin
./rain/bin/rainsum -a bow -s 256 /tmp/a.bin
```

Searches are randomized, so each run yields different witnesses; `--rng-seed=N`
fixes the stream. `--prefix-a=` / `--prefix-b=` choose your own prefixes (they
are space-padded to a common 32-byte boundary so the next block is a `mixA`
block, and Rainbow is length-keyed so both messages must match in length).

## Verification chain

Every witness is checked four independent ways, and all four must agree:

1. the attack binary's own transcription of Rainbow;
2. `verify_pair_sum.py`, a from-scratch Python implementation;
3. `replay_production`, which includes the untouched `src/rainbow.cpp`;
4. the shipped `rainsum` CLI.

Messages cross every boundary as hex and are replayed from bytes, so no
endianness assumption is shared between search and verification.

## A note on the self-test

`chosen_prefix_collision` runs `theorem_selftest` before doing any work: 1000
random state pairs constructed to share pair sums but otherwise unrelated, each
merged by the closed form, each required to be bitwise identical afterwards —
and to stay identical through both mixers. It caught a real sign error during
development (the negated word is `h0` for the first pair but `h3` for the
second, so `y' = y + (t3 - s3)`, not `y + (s3 - t3)`). Keep it enabled.
