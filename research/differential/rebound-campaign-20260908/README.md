# Rainstorm v4.0.0 external cryptanalysis campaign

This directory preserves the machine-readable results behind
[`External Cryptanalysis of Rainstorm v4.0.0`](../../../output/pdf/rainstorm-v4-external-cryptanalysis.pdf).
The target is the production v4.0.0 construction at seed zero. Full-production
claims use distinct 64-byte messages and their identical mandatory `0x80`
padding block.

## Result

- A native distinguished-point search found a collision in the programmed
  two-message-round, zero-padding-round reduction after 4,070,333,044 walk
  evaluations (`2^31.9225`). Independent replay confirms equal 64-, 128-, and
  256-bit reduced outputs. This is a reduced-round attack, not a collision in
  production Rainstorm.
- The collision retains fold words 1--5 through one genuine fixed-padding
  right round. Fold word zero then requires equality of an additional 64-bit
  transformed-word sum.
- A held-out `2^28`-pair inverse-padding experiment found 58 arbitrary-state
  boundary differences of Hamming weight at most 36, with minimum 34. The
  exact discovery mask did not repeat, so the observation is a differential
  hull rather than a fixed characteristic.
- Forward programmed-difference, higher-order, differential-linear, and
  Boolean-Jacobian campaigns found no validated production output
  distinguisher. Exact Z3 and Bitwuzla production collision jobs timed out;
  known-broken controls also timed out, so `unknown` supports no negative
  claim.
- No production Rainstorm-128 or Rainstorm-256 collision was found. The paper
  records the remaining attack obligations and does not claim a security
  proof.

## Principal artifacts

- `two-round-native-rho-search.json`: search cost and collision messages.
- `two-round-native-rho-replay.json`: independent reduced and production
  replay, including native C++ digests.
- `inverse-padding-heldout-2p28.json`: fresh validation of the backward
  low-weight hull.
- `forward-programmed-{xor,add}-{discovery,validation}.json`: inbound screens.
- `higher-order-d{8,12,16,20}.json`: production Rainstorm-128 affine-cube
  derivative screens.
- `differential-linear-{discovery,validation-single,validation-multi}.json`:
  production parity screens and held-out checks.
- `jacobian-rank-campaign-{64,128}.json`: 32-base Boolean-Jacobian campaigns.
- `flat-production-{sat,sls,bitwuzla-prop}-300s.json`: flattened exact-model
  solver diagnostics.

Run the regression checks from `research/differential/`:

```sh
python3 -m unittest -v test_suite.py
```

Build the paper from `output/pdf/`:

```sh
pdflatex -interaction=nonstopmode -halt-on-error rainstorm-v4-external-cryptanalysis.tex
pdflatex -interaction=nonstopmode -halt-on-error rainstorm-v4-external-cryptanalysis.tex
```
