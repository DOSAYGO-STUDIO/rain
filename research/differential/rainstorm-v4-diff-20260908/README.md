# Rainstorm v4 endpoint differential campaign — 2026-09-08

These runs use the current production `src/rainstorm.cpp` (v4.0.0), not the
frozen pre-v4 source retained by the historical OG analysis. The batch bridge
is `../production_native.cpp`; `broad-all-widths.json` records two successful
published Rainstorm-256 vector checks. Both reports fingerprint the production
source, common header, bridge, and statistical scanner.

## Dense Rainstorm-256 run

```sh
python3 research/differential/scan_production.py --bits 256 \
  --lengths 16 64 65 128 --all-bits \
  --masks 3 8000000000000001 10000000000000001 ffffffffffffffff \
  --samples 65536 --batch 4096 --p-min 0.001 --alpha 0.01 \
  --output research/differential/rainstorm-v4-diff-20260908/dense-256.json
```

- 2,200 fixed input-difference/length cases.
- 144,179,200 paired observations.
- No zero output differences (fixed-difference hash collisions).
- No bit or byte projection alerts under the campaign-wide threshold.
- Every complete 256-bit output difference occurred at most once per case.
- Largest observed single-bit bias: `0.0099334716796875`.
- Simultaneous projection radius: `0.01328550807789877`.
- On the simultaneous confidence event, every tested bit's true bias is at
  most the observed family maximum plus the radius, approximately `0.02322`.
- With zero collision observations, the reported simultaneous one-sided upper
  bound per prespecified fixed-difference case is approximately `0.00020445`.

The all-exact-bin Hoeffding upper bound is approximately `0.03824`; it is very
loose because it covers all `2^256` possible differences. It must not be
presented as a cryptographic-strength bound.

## Breadth run across every output width

```sh
python3 research/differential/scan_production.py \
  --lengths 7 8 9 15 16 17 31 32 33 63 64 65 127 128 129 \
  --masks 3 --samples 65536 --batch 4096 \
  --p-min 0.001 --alpha 0.01 \
  --output research/differential/rainstorm-v4-diff-20260908/broad-all-widths.json
```

- 360 cases: 90 each for 64-, 128-, 256-, and 512-bit outputs.
- 23,592,960 paired observations.
- No zero output differences and no projection alerts.
- Every complete output difference occurred at most once per case.
- Largest observed single-bit biases by output size:
  - 64: `0.00787353515625`
  - 128: `0.00775146484375`
  - 256: `0.00823974609375`
  - 512: `0.008209228515625`
- Simultaneous projection radius: `0.01273586676805467`.
- On the simultaneous confidence event, every tested bit's true bias is at
  most approximately `0.02098`.
- The zero-observation collision upper bound is approximately `0.00017683` per
  prespecified case, simultaneous across this campaign.

## Interpretation

Each run separately allocates family-wide error `alpha = 0.01`. If both
confidence statements are considered together, a simple union bound gives
joint coverage of at least 98 percent, under the reports' IID sampling model.

This is a clean endpoint screen, not a proof of collision resistance or of the
absence of useful differentials. In particular:

- The empirical collision upper bounds are vastly above cryptographic target
  probabilities.
- Only declared XOR input differences and message lengths were tested.
- Bit and byte projections do not cover all multi-bit linear relations.
- An internal trail can be rare, conditional, or cancel before the digest.
- Message modification, additive/rotational differences, related seeds,
  reduced rounds, and chosen-prefix paths remain outside these runs.

The next complementary step remains internal paired tracing and targeted trail
search, followed by fresh native validation of any candidate relation.
