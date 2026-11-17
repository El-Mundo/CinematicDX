# Method ranking supported by evidence (2026-10-26)

## Current data entry point, 2026-11-10

Current results for 454 videos are in the [version update and results](corpus_refresh/20261110/README.md). Three source updates use the same measurement protocol, 451 results retain their original receipts, and all studio statistics were recomputed. Hard cuts and digital brightness remain the core measurements. Complete gradual segmentation remains REJECTED for its stated use.

The ranking and numbers below are a method-assessment snapshot from 2026-10-26. Group statistics for the data update should use the new-version tables. The original experiment's evidence scope continues to apply to single-film human validation and narrative correspondence for 《上甘岭》.

| Rank | Candidate | Current status and evidence | Decision |
|---|---|---|---|
| 1 | C01 hard-cut timing, conservative durations and ordering | Timing/distribution arithmetic VERIFIED; additional fine-sequence organisation PROVISIONAL. 41 intervals, 37 adjacent relations; within-block permutations show no exceptional ordering | Core data; retain timelines and controls without montage labels |
| 2 | C02 within-version digital brightness/contrast | Extraction VERIFIED; narrative correspondence PROVISIONAL. Six cut-associated events: 0.1012 versus controls around 0.0185, retained under frame integration, leave-one-out and source perturbations | Strongest new narrative candidate; conditional association does not establish a general rule |
| 3 | C04 low-frequency configuration-similarity retrieval | PROVISIONAL. Changing representative frames retains 5–7 of the top10 pairs, with clear mismatches; advantage over brightness baseline varies by temporal gap | Assist visual-relation retrieval; not yet a semantic motif/location tool |
| 4 | C03 visual-activity proxy | PROVISIONAL. Correlation and optical-flow rank correlation 0.932; complete event exposure for only 4/10 | Prefer inexpensive correlation and missingness flags; defer camera-movement classification/full-event comparisons |
| 5 | C05 current Haar boxes as person-count/shot-scale proxies | REJECTED for this use. Missed profiles and torso false boxes; parameters affect counts for 21.5% of representative images | Exclude from core; retain face boxes as predictions only |
| 6 | C06 current automatic complete gradual segmentation | REJECTED for this use. Existing strict-interval primary scoring failed | Stop optimising around 4 examples; do not automatically change the shot table |

This is not a cross-film accuracy leaderboard. VERIFIED covers only the stated measurement/numerical claims. Character identity, narrative function, attention mechanisms and political meaning have not been automatically validated.

Minimum combination: source version/PTS/quality and missingness + reference-checked hard cuts/conservative duration sequences + same-copy grayscale mean/contrast + an independent narrative-event layer and conditional controls. Activity is optional, and similarity supports exploration.

Full evidence: [report](REPORT.md). This round's outputs: `research-local/quantitative-exploration/round-20261026T001205Z`.

## Assessment after the corpus extension

Actual outputs for 453 films/17 institutions support C02's computational feasibility. Uniform sampling passed agreement checks against fully decoded 1Hz observations in 24 fixed clips. The earlier keyframe-only approach was rejected after deviations in 3 clips. Cross-studio 30-second means are close, film-level differences overlap, and 10/30/60-second rankings vary. Source colour casts/colour labels and duplicate files provide empirical counterexamples. C02 therefore remains a core measurement of **brightness organisation within digital versions**. Cross-studio historical/style interpretation remains PROVISIONAL; a larger dataset does not validate original lighting, narrative structure or studio style. This full-corpus grayscale processing does not expand validation for C01 or the other methods. See the [extension report](corpus_studio/REPORT.md).

## Ranking decision after corpus-wide editing tests

C01 and C02 remain the minimum core. Frame-complete computation for 453 films and independent scalar/PTS audits now support C01's computational feasibility. Human accuracy evidence still covers only the ten-minute 《上甘岭》 development interval and cannot be generalised across studios. Institutional means and local/whole-film rates support description. Conditional permutation references leave differences requiring interpretation, while rankings remain sensitive to thresholds, film composition and file edges. Although C06 candidates have been scanned across the corpus, strict complete start–end localisation still fails, and assistant checks show many within-shot changes. It therefore remains last and cannot represent true transition rates. These tests do not expand C03–C05 validation. See the [final assessment](corpus_editing/ASSESSMENT.md).
