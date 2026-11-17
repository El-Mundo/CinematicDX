# Hard cuts and transitions across the available corpus, grouped by production institution

Hard-cut comparisons remain PROVISIONAL. The current gradual-transition model's claim to locate complete start/end intervals is REJECTED. Numerical detector output does not by itself constitute verified transition statistics.

## Coverage and actual computation

There are 732 metadata records and 454 video paths. Frame-complete measurements are available for the current 454 film sources: 454 succeeded, 0 failed, and 278 records lack a valid video. Actual decoding covered 59,715,616 frames and 663.92 hours. Measurements cover 17/60 institutions. The current run binds each source association to its film key and video SHA.

This version update re-extracted 3 source files and inherited frame-complete measurements for 451 source files. The reuse manifest binds the original run directory, receipt SHA and video version. All institutional statistics, temporal profiles and conditional references were recomputed from the current film table. See this run's `plan.json` and the parent directory's `refresh.json` for source and update manifests.

Initially, 0 jobs failed; 0 were completed through machine-precision boundary recovery while preserving their original caches. ROI values may be clipped back to the 0–1 boundary only when the excursion is no greater than 8×float64 machine precision. Larger deviations and NaN are rejected. The original video SHA, cache SHA and final frames at actual EOF are rechecked. Original failures and `extraction_complete.json` remain intact. A separate `effective_extraction_complete.json` records final coverage rather than silently erasing failures.

## Measurement and validation

Hard cuts use frame-by-frame HSV-V MAD at full-frame width ≤320. The MAD ratio to the mean of the preceding and following 2 frames must be ≥3, with MAD≥15. Original PTS impose a minimum interval of 0.12 seconds. Ratios 2.5/3.5 and a fixed ROI are separate sensitivity checks. This uses neither the luminance study's 1Hz sampling nor skipped decoded frames or times fabricated from nominal frame rates.

Uniform V-only processing avoids the many HSV false positives previously caused by unstable hue in near-gray images in this film. It may miss colour cuts with similar V but predominantly different hue. The algorithm does not switch automatically according to unreliable colour labels. The B&W 《上甘岭》 reference does not validate recall on colour material, so the B&W-feature tables must be read separately. The 0.12-second minimum interval also suppresses very short insert candidates, whose suppression records are preserved.

Candidates in 《上甘岭》 at 150–750 seconds match the original PySceneDetect0.7.1 baseline point by point. Both QuickTime frame-number interpretations are retained. At ±0.08 seconds, excluding independently annotated gradual intervals, each interpretation gives 43 matches/2 false positives/2 misses, with precision/recall 0.9556. Results at ±0.04/0.12 seconds and all other settings are preserved. Validation uses this film's ten-minute manual reference, which previously contributed to method development. Both frame-number origins remain explicit.

The gradual scan applies the existing endpoint-mixing/near-black fade rules to complete files, retaining default, strict and fade-only configurations. Its BGR2GRAY fixed-ROI cache is resized directly to 16×12, unlike the former 64×48 cache. This is not presented as a speed-only optimisation with an unchanged signal. At tIoU≥0.5, both frame-number interpretations still give 0 matches/91 false positives/4 misses. The earlier failure to locate complete start/end intervals remains documented. The corpus scan examines candidate density, failure and parameter sensitivity. **It cannot establish actual dissolve/fade preferences.**

This transition model operationalises only dissolve and fade candidates. It does not cover all transition types, including wipes, irises and occlusion transitions. Failure to match a complete interval does not establish that no transition occurred. Candidate localisation and complete-interval segmentation are distinct uses.

The already available local TransNetV2 model also failed strict interval validation. Its measured CPU run processed 15248 frames in about 160 seconds. Linear extrapolation to frame-complete processing of the corpus is about one week, so the existence of a model does not justify launching a multi-day job. No models were downloaded or trained, no material was uploaded, and no paid computation was used.

### Parameter comparisons on the same manual interval

| Configuration | Frame-number scenario | Matches/unmatched predictions/misses (±0.08 s) |
|---|---|---:|
| primary | decoded_ordinal_base_0 | 43/2/2 |
| lenient | decoded_ordinal_base_0 | 44/3/1 |
| strict | decoded_ordinal_base_0 | 42/2/3 |
| roi | decoded_ordinal_base_0 | 43/2/2 |
| primary | decoded_ordinal_base_1 | 43/2/2 |
| lenient | decoded_ordinal_base_1 | 44/3/1 |
| strict | decoded_ordinal_base_1 | 42/2/3 |
| roi | decoded_ordinal_base_1 | 43/2/2 |


| Configuration | Frame-number scenario | tIoU | Matches/unmatched predictions/misses |
|---|---|---:|---:|
| default | decoded_ordinal_base_0 | 0.5 | 0/91/4 |
| default | decoded_ordinal_base_1 | 0.5 | 0/91/4 |
| default | decoded_ordinal_base_0 | 0.3 | 2/89/2 |
| default | decoded_ordinal_base_1 | 0.3 | 2/89/2 |
| strict | decoded_ordinal_base_0 | 0.5 | 0/6/4 |
| strict | decoded_ordinal_base_1 | 0.5 | 0/6/4 |
| strict | decoded_ordinal_base_0 | 0.3 | 2/4/2 |
| strict | decoded_ordinal_base_1 | 0.3 | 2/4/2 |
| fade_only_baseline | decoded_ordinal_base_0 | 0.5 | 0/2/4 |
| fade_only_baseline | decoded_ordinal_base_1 | 0.5 | 0/2/4 |
| fade_only_baseline | decoded_ordinal_base_0 | 0.3 | 1/1/3 |
| fade_only_baseline | decoded_ordinal_base_1 | 0.3 | 1/1/3 |


After scoring exclusions, the primary hard-cut setting and manual reference both contain 45 points, yet 2 predictions remain unmatched and 2 reference cuts are missed. Equal totals do not establish correct temporal organisation. Preserved original-frame error images show smoke/explosions, changes between similar gray levels, and areas near gradual-transition endpoints. Assistant observations explain possible failure mechanisms without changing labels or choosing the more favourable frame-number origin. Looser gradual tIoU can support local candidate use but cannot replace strict complete-interval evaluation.

The counting unit for composite transitions also needs specification. A near-black-to-new-image jump following a reference fade may be counted by a point detector. Whether “fade-out—black hold—new shot” is one composite event or separate fade, hold and hard-cut events is a research-protocol decision. This run retains the original annotation scoring rather than changing the reference to improve the figures.

## Studio comparisons

Specific institutions remain separate according to production.name. Films receive equal weight and co-productions receive 1/k per institution. Northeast/Changchun and other institutions are not automatically merged. The table below includes institutions with at least 10 measured films. CSV files retain all 60 institutions, including missing films. Year, type, colour labels and source conditions also shape institutional samples.

| Studio | Metadata/measured | Hard-cut candidates/min | Lenient/strict | ROI | B&W features (n) | Gradual candidates/min* |
|---|---:|---:|---:|---:|---:|---:|
| 天马电影制片厂 | 69/36 | 5.440 | 5.545/5.329 | 5.461 | 5.855 (21) | 5.659 |
| 海燕电影制片厂 | 76/38 | 5.365 | 5.454/5.260 | 5.391 | 5.937 (22) | 6.400 |
| 珠江电影制片厂 | 25/15 | 5.206 | 5.339/5.064 | 5.282 | 6.693 (8) | 6.159 |
| 东北电影制片厂 | 34/26 | 5.096 | 5.623/4.708 | 5.237 | 5.567 (23) | 6.635 |
| 长春电影制片厂 | 155/109 | 4.964 | 5.086/4.828 | 5.004 | 5.277 (72) | 5.676 |
| 八一电影制片厂 | 74/63 | 4.899 | 5.101/4.668 | 4.932 | 4.962 (49) | 6.133 |
| 江南电影制片厂 | 23/14 | 4.866 | 4.968/4.753 | 4.934 | 4.928 (7) | 6.797 |
| 上海电影制片厂 | 55/52 | 4.736 | 4.920/4.558 | 4.805 | 5.352 (40) | 7.267 |
| 北京电影制片厂 | 91/76 | 4.491 | 4.681/4.291 | 4.558 | 5.137 (40) | 6.909 |
| 西安电影制片厂 | 22/17 | 4.041 | 4.198/3.889 | 4.143 | 4.462 (10) | 7.912 |


*The gradual column describes a detector that still makes many errors. It is a method diagnostic, not a ranking of actual transition rates. Full tables also contain interquartile ranges across films, single-studio subsets, year×colour×type strata and source-width strata. Small institutional samples are not ranked, and frames are not treated as independent samples. Source width does not identify scanning/restoration provenance.

The corpus produced 194,781 hard-cut candidates and 253,704 gradual candidates. These are model outputs and cannot be added together as a verified total transition count. Conflicts where hard cuts fall inside gradual-candidate intervals are recorded separately. The weak gradual model does not automatically remove hard cuts.

## Composition-conditioned permutation references

Only single-studio films from institutions with at least 10 originally measured members enter same-year×type×metadata-colour cells (≥5 films and ≥2 institutions). The between-group residual share is computed after subtracting each cell mean. Film values are permuted within cells 999 times with seed 20261026. A second reference additionally requires equal source width without relaxing eligibility thresholds. Co-productions remain in descriptive tables but are not independent group members in this particular reference.

conditional_studio_reference: 348 films, 25 matched cells, 10 institutions; between-studio residual share 0.0780, median across 999 permutations 0.0218, 2.5–97.5% reference range 0.0067–0.0491, reference fraction at least as large as the observed statistic 0.0020.

conditional_source_width_reference: 300 films, 30 matched cells, 10 institutions; between-studio residual share 0.1158, median across 999 permutations 0.0265, 2.5–97.5% reference range 0.0089–0.0615, reference fraction at least as large as the observed statistic 0.0010.

This is an exploratory conditional reference, not a guarantee of exchangeability in historical material. Actual sources, subjects, cinematographers and institutional selection may still confound the comparison. Tail fractions establish neither population patterns under random sampling nor causal studio effects or a particular institution's distinctive style. Matched subsets and full descriptive tables have different coverage and must be read with n.

## Temporal organisation and interpretive limits

Each film retains original candidate PTS, playback coordinates, all frame-level scores, small ROIs and local candidate rates in 100 position bins. Intervals bounded by two complete hard-cut candidates exclude file edges, but undetected gradual transitions may occur inside them. They are therefore candidate-cut-bounded intervals rather than verified average shot lengths. Intervals not intersecting gradual candidates are retained as a sensitivity check, not shot ground truth. Adjacent log-interval change is descriptive and identifies no montage principle, narrative event or cause by itself.

Relative profiles also show “local rate / film mean rate” (1 denotes the film mean), separating total switching volume from relative positional distribution. Films with zero candidates remain missing in this normalisation and have separately reported effective n. Given the same candidate set, the profile is invariant to uniform playback-speed scaling. It does not remove missed detections, source editing, nonuniform speed changes or minimum-interval filtering, and relative positions are not named as narrative stages.

Digital-file opening and ending material, advertising/logos, jitter, movement, flashes, colour casts, repeated frames and unknown transfer workflows can trigger or conceal transitions. Complete-film processing means the complete local file, not a verified complete historical version. The independent human transition reference remains ten minutes of 《上甘岭》, not automatically corpus-wide ground truth. No additional viewing or relabelling was requested.

The adaptive window is defined in frames, so digital frame intervals may also affect scores. Per-film median/p95 presentation intervals are retained, with `studio_frame_cadence.csv` as an additional table. They describe the current digital files' decoded cadence, not original camera/projection frame rates. The proportion of adjacent pairs with zero V-channel difference is also preserved and is not equated with exact duplication of full-colour frames.

An additional A–B–A return flag marks candidates whose small gray images at approximately 0.12 seconds before/after differ by ≤0.03 while the intervening peak difference is ≥0.10. Primary-table cuts remain unchanged. The pattern could be a flash, a real short insert or movement. Only flag rates and exclusion sensitivity are reported, not a verified false-positive rate.

The rules also retain digital near-black holds: ROI mean≤12/255, standard deviation≤0.04, lasting ≥0.08 seconds. These are explicitly thresholded pixel/time properties whose original frames can be inspected. They are not equivalent to actual fades, photographic black frames or narrative pauses. Predicted transition-type counts remain in per-film tables without validation as actual type distributions.

## Outputs and reproduction

Run directory: `/Users/caoshuangyuan/Desktop/Workspace/CinematicDX/research-local/corpus-refresh/20261110/editing`. Current grouping directory: `/Users/caoshuangyuan/Desktop/Workspace/CinematicDX/research-local/corpus-refresh/20261110/editing/analysis`. Per-film `frame_features.npz`, `cut_candidates.json`, `gradual_*.json`, `summary.json` and `run.json` bind complete-video SHA, original PTS, software and parameters. Complete coverage and studio CSV files, timeline PNG/PDF files and preflight results are preserved. Final numerical audits and assistant image inspections are recorded separately. Neither is presented as independent human accuracy validation across the corpus.
