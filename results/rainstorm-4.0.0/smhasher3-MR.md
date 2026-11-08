# Update Rainstorm to v4.0.0 and refresh verification codes

Rainstorm 4.0.0 changes the last right-round counter subtraction from h[8] to h[0]. The old wrap cancels one transformed state word and makes the fixed-block right round exactly 2^64-to-1 on arbitrary incoming states. The new wrap makes that round invertible. No full-message collision is claimed.

This patch updates all three Rainstorm registrations and their native/swapped verification codes. Round counts, IV, padding, finalization, flags and test budgets are unchanged. All Rainstorm digests change.

Release: https://github.com/DOSAYGO-STUDIO/rain/releases/tag/v4.0.0
Analysis and full candidate log: https://github.com/DOSAYGO-STUDIO/rain/tree/v4.0.0/results/rainstorm-4.0.0
Contributor discussion: https://github.com/DOSAYGO-STUDIO/rain/issues/161

Validation against upstream revision 3b619371047761408406991685da1c2b3f751899:
- Built SMHasher3 in Release mode.
- `--test=Sanity --extra --exit-code-on-failure` passes for rainstorm, rainstorm-128 and rainstorm-256 under both `--endian=native` and `--endian=nonnative` (six runs).
- Exact-source candidate A passed `--test=All,BadSeeds --extra --exit-code-on-failure --endian=native --ncpu=16 rainexp-a-256`: 253/253 checks. Its native verification code matches this upstream implementation (46A86116).
- Swapped codes were computed and validated using the upstream implementation, which swaps padded tail words differently from the standalone source adapter.

Statistical passes and the round-level proof do not establish cryptographic security. No 512-bit SMHasher3 registration is added.
