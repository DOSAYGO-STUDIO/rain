# Frozen original reference

These three files are copied without modification from commit
`b73a43239e7fb0f516bc17e757d3a09cbb63f0da` of DOSAYGO-STUDIO/rain.
They preserve the pre-v4 Rainstorm behavior for differential comparisons.
They are not the current production implementation. Their original Apache-2.0
licensing and copyright notices apply.

`native.cpp`, the round witnesses and `build_variants.py` use this reference.
Current production Rainstorm is tested separately against candidate A by
`test_release.py`. This separation keeps the historical witness reproducible
after the indexing correction is promoted.
