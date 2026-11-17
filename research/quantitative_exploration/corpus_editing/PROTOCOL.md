# Hard cuts and transitions across the available corpus: run protocol

On 2026-10-26, the user explicitly requested a studio-grouped examination of the entire corpus. See `../ACTIVE_EDITING_RUN.txt` for the current run directory. This study processes complete films frame by frame; the previous approximately 1Hz gray-level samples cannot serve as cut detection.

## Scope and source protection

The research JSON contains 732 records. Of 454 existing paths, one is a misnamed byte-identical duplicate. Existing opening-title and SHA evidence is retained, and only 453 unique film sources are processed; 279 records lack valid video. Existing stable keys and digital-byte SHA values identify sources. Most unique-filename associations remain provisional rather than manually verified identities across the corpus. Complete-file SHA is rechecked before each actual job. Original videos, JSON, Excel and the original manual reference remain read-only. No database is connected, no models are downloaded, and nothing is uploaded or pushed.

Group by each specific production name, retaining 东北/长春 and 上海/天马/海燕 separately. Films receive equal weight, with 1/k per institution for co-productions. Retain every institution, missing film and failure. Only institutions with at least 10 measured films enter the main comparison figures; smaller stratified samples are reported separately.

## Frozen measurements

1. Decode complete films in software, preserve original PTS, and resize BGR images to width≤320 with AREA interpolation. Do not fabricate times from average frame rates or skip frames.
2. Reuse the mathematical definition of the PySceneDetect0.7.1 V-only adaptive algorithm: frame-by-frame HSV-V pixel MAD, with a ratio≥3 to the mean of the 2 frames on each side and MAD≥15. Apply a minimum interval of 0.12 seconds in original PTS and retain suppressed candidates. Ratios 2.5/3.5 and a fixed ROI provide sensitivity checks. V is not historically calibrated photometric luminance.

   V-only processing may miss colour cuts distinguished mainly by hue. A uniform signal avoids choosing different algorithms from colour labels, but this film's B&W reference cannot validate colour recall. The 0.12-second filter may affect very short inserts. These are known limitations; no unsupported corpus-wide accuracy guarantee is made.
3. Preserve complete frame-level PTS/display intervals, full-frame/ROI V differences, ROI gray-level means/standard deviations, a directly resized 16×12 gray cache and adjacent differences. Gradual detection uses the existing default/strict/fade-only endpoint-mixing rules. The cache differs from the previous 64×48 cache and is explicitly revalidated, without claiming an unchanged signal.
4. Strict complete-interval gradual detection is known to have failed. Corpus-wide gradual output is used only for **model-candidate diagnostics**, not actual transition frequencies, dissolve/fade preferences, true shot segmentation or studio-style conclusions. These candidates do not automatically remove hard cuts.

   Gradual candidates here cover only operational definitions of endpoint mixing and near-black fades in/out. They do not claim to cover every editing transition, including wipes, irises or occlusions. Failure to match a complete interval does not establish that no real transition occurred.
5. Intervals bounded by hard cuts at both ends exclude file edges but can still contain missed gradual transitions, so they are not directly called average shot lengths. Preserve candidate rates in 100 relative-position bins without assuming narrative acts. Report threshold disagreements, ROI, single-studio, year×type×colour-label and source-width stratifications without selecting favourable settings.

6. Before complete group results are produced, specify an additional A–B–A warning: flag candidates when the small gray images approximately 0.12 seconds before/after have endpoint MAD≤0.03 and the intervening peak MAD≥0.10. The pattern may be a flash, a real short insert or movement. Use it only as exclusion sensitivity; do not remove primary cuts or call it false-positive ground truth.

7. Add “local candidate rate / film mean candidate rate” to temporal figures to distinguish total switching volume from positional distribution. Films with zero candidates remain missing for this normalisation, with separately reported effective n. Given the same candidate set, it is invariant to uniform playback-speed scaling, but neither establishes original projection speed nor eliminates detection errors. Positions are not narrative acts. This is an additional presentation specified before complete results were published, not a claim of preregistered hypotheses.

Algorithm reference: [official PySceneDetect documentation](https://www.scenedetect.com/docs/latest/api/detectors.html). Engineering tests compare an independent vector implementation point by point with the installed version. Local candidates for 《上甘岭》 at 150–750 seconds reproduce the original baseline point by point.

## Revalidation against the existing reference

Retain both frame-number-origin interpretations of the independent manual annotations, without choosing the more favourable interpretation. At ±0.08 seconds, excluding manually annotated gradual intervals, both hard-cut scores are 43 matches/2 false positives/2 misses. Results at ±0.04/0.12 seconds are also preserved. This single-film interval contributed to method development; it is not external accuracy validation for 453 films.

At tIoU≥0.5, gradual detection still yields 0 matches/91 false positives/4 misses. More lenient tIoU scores and other configurations are preserved without replacing the strict primary result. The available local TransNetV2 model also failed strict interval evaluation. Its existing CPU measurement processed 15248 frames in about 160 seconds; linear extrapolation to the frame-complete corpus is about one week. This run does not launch multi-day computation with a weak model, retrain it or download models.

## Execution revisions (measurement parameters unchanged)

The first version repeatedly created scaling contexts; its partial run is preserved in `corpus-20261026T114005Z`. Sharing VideoReformatter and using AUTO decoding with 2 threads produced exactly identical values in all 11 arrays, including PTS, every score and cached pixels, in the same 15248-frame preflight, while approximately halving runtime. The task's four old CPU processes were stopped, and `corpus-20261026T114911Z` started from scratch without altering or borrowing old job receipts. The initial failed validation adapter lacked transition_id, so its first preflight was not published. After fixing the ID, it was rerun without changing thresholds, labels or scoring criteria.

During the run, 《无穷的潜力》 had a complete 126024-frame cache, but a pure-white frame's ROI mean of 1.0000000000000002 triggered the former strict 0–1 range check. Recovery permits only excursions≤8×float64 machine precision; larger excursions and NaN are not repaired. Preserve the original cache and failure record, with a separate recovery explanation. After rechecking complete source SHA, the source tail through actual EOF and the final display endpoint, complete the result from the cache to avoid decoding the entire film again. The actual recovery program and helper source are archived by receipt SHA in `recovery_sources/`; the frozen batch extraction core is unchanged. Record the initial failure and final effective completion separately in the original `extraction_complete.json` and new `effective_extraction_complete.json`, preserving negative evidence. This is a numerical-guard recovery, not a model-parameter or label adjustment.

## Conditional permutation reference: exploratory, without a preregistration claim

Specify before seeing complete studio-group results: use only single-studio films from institutions with at least 10 originally measured members. Form exact-year×film-type×metadata-colour cells; comparisons require ≥5 films and ≥2 institutions per cell. Subtract cell means, then compute between-group residual sum of squares / total residual sum of squares. With fixed seed 20261026, permute film values within cells 999 times while preserving studio and composition distributions. Adding source width to the same cells is a secondary sensitivity check. Insufficient samples yield BLOCKED rather than relaxed thresholds.

Report actual coverage, the null distribution and the conditional reference tail fraction. Historical evidence does not guarantee exchangeability; provenance, people, subjects, cinematographers and institutional selection may remain confounded. This is neither population significance from random sampling nor a studio causal effect. Co-productions remain in the main descriptive table but do not enter this particular reference.

## QA and stopping rule

Frame-complete processing and numerical-consistency auditing are separate from film-semantic accuracy. After completion, sample films by institution with a fixed seed, randomly select one hard-cut and one gradual candidate per film, and save five-frame contact sheets at original PTS. Keep assistant observations separate from the independent manual reference. Candidate sampling cannot estimate corpus-wide recall. No additional viewing task is assigned to the researcher.

Stop after all 453 sources have been attempted, missing films/failures are explicit, and studio tables, timelines, sensitivity results, an independent arithmetic audit, actual contact-sheet inspection and reports are complete. Producing many candidates does not make a failed gradual method successful.
