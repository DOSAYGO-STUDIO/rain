# Revision in response to ePrint rejection

The editor quoted broad acceptance criteria and did not identify individual errors. The changes below are our assessment of weaknesses in the submitted manuscript, not a claim to know the editor's specific reasoning. The operations page was blocked by robots.txt during this review; the quoted criteria in the rejection supplied the editorial requirements.

Revised title: **A Fold Collapse in Two-Round Rainstorm-256 without Padding Compression**.

## What changed

- **Clear and readable:** replaced the sprawling campaign report with a focused argument: target definition, programming lemma, fold identity, finalization proof, concrete witness, and one-padding-round obstruction. Historical experiments and the related-seed appendix remain in the original archive; they are no longer presented as contributions of this paper.
- **Self-contained:** included the IV, all constants, endian conventions, complete right/left round recurrences, padding and width-dependent finalization. Added a complete standalone Python witness verifier in the appendix and as `research/differential/verify_paper_collision.py`.
- **Claims supported:** proved prefix preservation and its inverse, explicitly proved distinctness of the messages and the digest collision implication, and scoped the padding proof to lanes 1 through 5. The old proof's unqualified statement that H_i=x_i for i>0 was false in lanes 6 and 7.
- **Complexity corrected:** 2^31.9225 is a recorded successful walk cost, not a proved expected complexity. The paper now distinguishes walk and replay counts, operation units, random-mapping assumptions, and unmeasured memory overhead. The native implementation interleaves 64 walks; it does not run 64 hardware threads.
- **Padding extension corrected:** the one-parameter family has only 2^64 inputs. A random map from that domain to 128 bits has about 1/2 expected collision pairs even after complete enumeration. The former unqualified 2^64 generic-search claim did not account for domain exhaustion. Equality of the extra sum is not proved independent or random.
- **Interesting contribution identified:** the construction-specific interaction between exact message programming, cross-half XOR, and subtractive folding. No claim of a new generic search method, an exhaustive novelty search, completed rebound attack, or production security margin.
- **Archival provenance corrected:** the existing v1 tag contains the original campaign, not this revision. It has not been retargeted. No revised public artifact release is claimed.

## Validation performed on 17 September 2026

- Standalone verifier passes all fixed witness assertions, including reduced 64/128/256 digests, the 384-bit prefix of the 512-bit digest, unequal full 512-bit outputs, and failure of the padding and production extensions.
- 200 round comparisons against the existing integer model (100 deterministic random states/data blocks, both directions) pass.
- Eight production digest comparisons against the native C++ bridge pass (both witness messages, all four widths).
- Reference source SHA-256 matches the manuscript: `8b70ceb620aaaf19859733705fa39c0ce849340a701e05fb89cdc2e07bf3712f`.
- Manuscript rebuilt with two pdflatex passes and visually reviewed. Historical billion-evaluation timing was not rerun, and no new attack campaign was performed.

## Submission status

This is a substantive local revision, not a resubmission. No editor was contacted. Acceptance and novelty remain editorial judgments; polishing the argument cannot establish them. Before submitting, the author should review the changed claims and disclosure, publish a fresh immutable artifact release containing this revision and verifier, and use the revised title/abstract/keywords. Preserve the old tag and raw campaign records.

To build from `output/pdf`, run `pdflatex -interaction=nonstopmode -halt-on-error rainstorm-v4-external-cryptanalysis.tex` twice. The TeX source includes the verifier by relative path; distribute that file with the source. The compiled PDF contains the full listing and can be read independently.
