# Editing across the available corpus by production institution: final assessment

## Current results entry point: 2026-11-10

The current data version covers 454 videos. Three changed sources were re-extracted frame by frame; measurements for 451 unchanged sources are inherited with original receipts. See [source refresh and results](../corpus_refresh/20261110/README.md) for updated studio summaries, all candidate statistics, temporal profiles and audits. The current run is `research-local/corpus-refresh/20261110/editing`.

The independent manual reference and strict gradual validation for 《上甘岭》 still use the same video version. Hard-cut candidates support descriptive comparisons with quality flags. Complete gradual segmentation remains REJECTED.

## Assessment snapshot: 2026-10-26

The coverage counts, tables, costs and visual inspections below belong to the October run. Use the newer results above for current corpus counts and group statistics.

Frame-complete processing of all 453 available films is complete. **Hard-cut candidates can support descriptive research with quality flags; the current gradual detector cannot support actual transition-frequency or studio-preference comparisons.** This study tests editing changes and their distributions in digital files. It has not established studio style, narrative structure or historical causation.

Main run: `research-local/studio-editing/corpus-20261026T114911Z`. See the [complete measurement report](REPORT.md) for technical definitions and all validation tables, and [reproduction notes](REPRODUCE.md) for operations. The run directory's `analysis/REPORT.md` and its hash receipt remain unchanged. This document adds interpretation and actual image observations.

## Actual coverage and cost

- There are 732 metadata records and 454 original video paths. The confirmed misnamed byte-identical duplicate counts only once as 《延安游击队》, giving 453 unique file versions. All 453/453 completed; 279 records lack valid video. Missing films must not be interpreted as having zero cuts.
- Processing covered 59,478,844 decoded frames and 661.2911 hours. Of 60 metadata institutions, 17 have available films. Complete-film processing means decoding the complete current local file to EOF, not proof of a complete historical copy.
- Four-process software CPU extraction took about 21,098.8 seconds (5.86 hours), plus 93.8 seconds in total for two floating-point-boundary recoveries. These times exclude some preflight, grouping and auditing. Existing hardware-decoding experiments failed; no GPU use is claimed.
- In two complete caches, respectively 1/2 ROI means were 1.0000000000000002. Only computational copies were repaired within machine precision. Original caches, failures and source files remain intact; complete-video SHA and actual EOF were rechecked. A failure does not mean the video was unprocessed.
- Of the input links, 449 remain provisional unique-filename matches and 4 are marked as assistant-reviewed against opening titles. The duplicate-file identity decision has separate inherited evidence. **Having 453 films does not mean 453 independent identity authentications.** Year, colour and institution still mainly derive from research metadata.
- Each film retains complete source SHA, original PTS, method parameters/versions, caches, candidates, missingness/warnings and receipts. Complete source SHA is checked before extraction, and file state is checked at completion and in the final audit. Final SHA values for the research JSON and original Excel are unchanged. Videos, annotations and the database were not modified.

## Studio hard-cut candidate differences: a signal with unstable ordering

The following institutions each have at least 10 available films. Compute candidates/minute per film, then average with equal film weights and 1/k per institution for co-productions. Here n counts films including that institution; institutional n values cannot be added to obtain the unique-film total. 东北/长春 and 上海/天马/海燕 remain distinct original institutions.

| Production institution | Available n | Primary candidates/minute | Between-film interquartile range | Central 10–90% candidates/minute* |
|---|---:|---:|---:|---:|
| 天马 | 36 | 5.440 | 4.474–6.468 | 5.334 |
| 海燕 | 38 | 5.365 | 4.159–6.484 | 5.185 |
| 珠江 | 15 | 5.206 | 3.309–7.264 | 5.230 |
| 东北 | 26 | 5.096 | 4.240–6.579 | 4.955 |
| 长春 | 109 | 4.964 | 4.025–5.978 | 4.804 |
| 八一 | 63 | 4.899 | 4.339–5.542 | 4.784 |
| 江南 | 14 | 4.866 | 3.943–6.128 | 4.717 |
| 上海 | 52 | 4.736 | 3.485–5.836 | 4.653 |
| 北京 | 76 | 4.493 | 3.495–5.376 | 4.370 |
| 西安 | 16 | 4.011 | 2.011–5.115 | 3.876 |

*The central-film analysis is **post-result sensitivity**, added after inspecting end-title material and relative-position curves; it does not replace the primary analysis. It restricts actual decoded coverage to [10%,90%) without changing candidate rules or film weights. It is not validated segmentation of titles/credits or narrative boundaries. See `edge_challenge/run.json` for provenance and numbers, and `challenge_editing_edges.py` for reproduction. No redecoding was performed.

The between-film interquartile ranges of all ten groups overlap at 4.474–5.115. Means differ, but many films overlap across groups. IQR describes a distribution rather than a confidence interval for the mean, and overlap does not itself establish absence of association.

The ordering faces these empirical challenges:

1. Lowering the ratio threshold from 3 to 2.5 raises 东北 from 5.096 to 5.623, above 天马 at 5.545; 天马 is highest under the primary setting. ROI also changes some values. Threshold-specific ranks are not stable institutional characteristics.
2. Among metadata-labelled B&W features and institutions with at least 10 films, 海燕 at 5.937 (22 films) exceeds 天马 at 5.855 (21 films); 八一 is 4.962 (49 films). Type/colour composition affects the all-type ordering. Only 长春 (17 films, 5.701) and 北京 (17 films, 4.927) reach 10 Colour features. V-only processing may miss changes distinguished mainly by hue, and the B&W pilot reference does not validate colour recall.
3. Restricting to films whose metadata lists one production institution gives 珠江 a mean of 5.448 across 11 films, just above 天马 at 5.440. The gap is small. “Single-studio” means metadata lists one institution, not proof of no other historical collaboration.
4. In the central-film challenge, 珠江 at 5.230 exceeds 海燕 at 5.185. Mean changes across the ten groups range from −0.180 to +0.024 candidates/minute. Full-file opening/ending presentation contributes to these statistics. Position bins cannot directly be called exposition, climax or ending.
5. Actual median frame intervals correspond to about 25Hz in 447 films and 23.81Hz in 6 films. The adaptive window is defined in frame counts; PTS intervals and minimum-interval filtering affect results. This does not identify original camera or projection speed.

### Conditional permutation reference

Restrict metadata single-studio samples to institutions with original available n≥10. Retain overlapping same-year×type×colour cells with at least 5 films and at least 2 institutions. Subtract cell means, then calculate the between-institution residual sum of squares as a share of total residual sum of squares. Permute film values within cells 999 times, using seed 20261026.

| Condition | Actual films/cells | Observed share | Permutation median | Permutation 2.5–97.5% range | Corrected tail fraction ≥ observed |
|---|---:|---:|---:|---:|---:|
| Year×type×colour | 347/25 | 0.0764 | 0.0220 | 0.0075–0.0487 | 0.001 |
| Also require equal source width | 299/30 | 0.1135 | 0.0265 | 0.0081–0.0563 | 0.001 |

Under both conditions, observed group differences exceed this permutation reference and merit research with further provenance controls. **The rows contain different film sets; the change from 0.0764→0.1135 does not establish that resolution control strengthens an institutional effect.** Institutional n eligibility is applied before cell filtering, leaving some institutions with only 8/9 films after matching. Original sample counts remain in JSON. None of the 999 reference statistics reached the observed value; the plus-one correction gives 0.001, not zero probability.

Conditional exchangeability remains unestablished. Nonrandom missing films, shared creative personnel, subjects, institutional selection, transfer/restoration provenance and identity links may explain differences. Source width is not restoration batch. This exploratory reference establishes neither population significance, a specific studio's causal effect nor a political interpretation.

## Hard-cut and gradual validation have different conclusions

Corpus-wide outputs contain 194,243 primary hard-cut candidates and 252,711 default gradual candidates. They conflict/overlap and cannot be added into an actual total transition count. Hard-cut intervals do not directly yield complete, true average shot length.

The only independent researcher reference remains 《上甘岭》 at 02:30–12:30: 45 hard cuts and 4 gradual intervals. Both QuickTime frame-number origins, 0/1, are retained without forcing a 1-frame shift. At ±0.08 seconds, both primary settings yield 43 matches, 2 unmatched predictions and 2 misses, with precision and recall of 95.56%. Lenient results are 44/3/1 and strict results 42/2/3. The challenge without manual gradual-exclusion intervals also gives 43/2/2. All 934 full-film candidates match the old native PySceneDetect baseline timestamp by timestamp. This is an engineering regression check, not independent accuracy validation.

Those 10 minutes previously contributed to method development; 95.56% cannot be treated as accuracy across 453 films. Tolerance, original manual timing error, explosion smoke, flashes, within-shot movement, very short inserts and colour differences remain limitations. No new independent missed-detection survey was conducted across the corpus.

At complete-interval tIoU≥0.5, default gradual detection gives 0 matches/91 unmatched predictions/4 misses, strict gives 0/6/4, and fade-only gives 0/2/4, identically under both frame-number interpretations. At the lower threshold of 0.3, strict results are 2/4/2, suggesting some local candidates may be useful without replacing the complete-localisation target with a more lenient standard. Current rules do not cover every wipe, iris or other form. Counting units for composite fade-out—black hold—new image sequences also remain unresolved.

**Automatic complete gradual segmentation is currently REJECTED; this run cannot reliably estimate cross-studio gradual frequencies or type preferences.** Do not repeatedly optimise on four examples or launch multi-day corpus inference with the existing weak model. Negative results and candidates remain preserved.

## Actual image inspection and failure examples

With a fixed seed, sample one film from each of 17 institutions with data; deduplication leaves 17 films. Randomly select 1 primary hard cut and 1 default gradual candidate per film, totalling 34 rows, 170 frames and 6 contact sheets, all actually viewed by the assistant. Every source frame matches original PTS exactly. Preserve failures from the former direct-seek method separately; the revised earlier-start decoding does not substitute merely approximate nearby frames.

- Clear spatial/compositional discontinuities appear in 15 hard-cut rows. Ghosting is already visible near the selected point in 《杨门女将》, and the selected point in 《丽人行》 changes from an image to black. These raise category/counting-unit questions for ordinary hard cuts versus composite transitions. This is not a 15/17 accuracy estimate.
- In 13 of 17 gradual candidates, the five-frame images show no obvious cross-scene mixing, often showing action within one shot. 《枯木逢春》 at 5582.04 seconds and 《球迷》 at 2216.374 seconds are inspectable counterexamples.
- The opening sample of the candidate in 《东进序曲》 at 3752.754 seconds is already within a dissolve, followed by disappearance of the old image. It may identify part of the process without establishing its complete start. 《刘明珠》 at 1661.488 seconds darkens gradually but is labelled dissolve, also indicating classification problems.
- 《阿福寻宝记》 at 4175.680 seconds contains the character “完” and a changing ending background, reminding us that full-file counts include end presentation. A near-black brightening in 《丽人行》 at 2312.095 seconds gives a positive indication of candidate usefulness, but five frames do not validate all endpoints.

Observations are in `visual_qa/assistant_review.json`; original sampling/frame-hash receipts remain unchanged. These are limited assistant visual observations, not researcher reannotation, blind full-interval evaluation or corpus ground truth. Sampling only candidates, without random no-candidate intervals, cannot estimate corpus-wide recall or establish elimination of false positives.

## Research uses and stopping decision

| Property | Implemented/measured | Reliability and cost | Narrative/form relevance | Recommendation |
|---|---|---|---|---|
| Original hard-cut candidate PTS and local rates | All 453 films, frame complete | Independent reference in a development interval; cross-film accuracy PROVISIONAL; about 5.86 hours of CPU batch processing | Describes switching organisation and supports alignment to independent events; does not identify events itself | Include in the core while retaining prediction flags, thresholds and conflicts |
| Candidate intervals and adjacent order | Derived from caches for 453 films | Arithmetic is verifiable; missed graduals mean intervals are not all actual shots | Closer to organisation than a mean, but still requires an appropriate shuffled-order control | Use conservatively; do not call it metric montage |
| Relative-time local/whole-film rate | 453 films, 100 bins | Reproducible; affected by file edges/missingness; films rather than frames are samples | Separates distribution from mean without automatically naming narrative acts | Retain alongside original timelines and preserve effective n |
| Default/strict complete gradual intervals | Candidates for 453 films; 4 reference intervals revalidated | Strict primary criterion failed; low cost does not imply validity | Transition organisation may matter, but this measurement did not meet its target | Complete segmentation REJECTED; retrieval candidates PROVISIONAL |
| Digital near-black holds | Rule-derived for 453 films | Explicit thresholds; not validated as photographic black frames/actual fades | May align with narrative pauses, but visual property is not function | Auxiliary description only, without fade counts |

The independent numerical audit checked original PTS, scalar reimplementations of candidate rules, per-film rates, coverage/weights for 60 institutions, original-file state and output hashes across all 453 films; all passed. All 255 Python tests passed. These verify computation and provenance integrity, not every film-theoretical inference.

The minimal defensible combination remains source version/PTS/missingness + flagged hard cuts/conservative intervals + within-version gray-level temporal profiles + independent narrative annotations. Studio-grouped corpus results aid film selection and descriptive relationships, but cannot replace tests of narrative correspondence. The strongest next experiment compares “gray-level reorganisation + local switching rate” near existing independent events with ordinary hard-cut controls from the same period, freezing windows and retaining counterexamples such as E010. The same 10 minutes of 《上甘岭》 can only continue as an exploratory challenge. Confirmatory expansion needs new independent references; no additional researcher viewing or reannotation is requested now.

The attempt across all available sources, parameter/composition challenges, actual failure examples and research records is complete. Stop further optimisation of rankings and the weak gradual model. Retain missing films, identities, institutional genealogy, composite-transition counting and provenance conditions as open research judgements.
