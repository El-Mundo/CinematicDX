# CinematicDX: autonomous quantitative-method exploration

## 2026-10-26: scope and initial decisions for this round

- Working branch: `codex/quantitative-evidence-20261026`. Existing uncommitted Java, Python and research outputs are preserved without committing, pushing or changing the database.
- Real material: 《上甘岭》(1956), research-inventory namespace `research-inventory`, key=`shang gan ling`. Video version: `sha256:a044ce2cd1b561bf2599f21b5415163e01f7abdd6313919ac1f8ed5e9657d9f0`.
- This round's only film interval is playback offset `[150,750)` seconds, totalling 600 seconds. Reuse verified per-frame caches first; additional decoding is limited to a small representative-image set within this interval. No other films are processed, and the scope does not expand to the 30-minute limit.
- Original video, Excel, confirmed human references and earlier failed experiments are read-only. Do not ask the researcher to rewatch or reannotate, download models/data or upload imagery.
- Existing independent human references: 45 hard cuts inside the interval, 4 gradual intervals and 11 events. E001 is at the observation window's left edge, and E011 is right-censored. Event precision is approximately seconds; retain both 0/1-based frame-number scenarios.
- Previous gradual experiments give rule-based scores 0/91/4 and pretrained comparison scores 0/3/4 under the primary intersection-over-union standard, representing matched/unmatched/missed intervals. Preserve these as negative evidence rather than continuing to optimise on 4 cases.
- Earlier M4 ±30-second controls have no identifiable matching and cannot imply absence of narrative relationships. This round instead asks whether narrow-window digital image changes exceed ordinary cutting, explicitly recording this as a new exploratory design.
- Freeze this round's procedure before generating new computed outputs. This is exploratory research on development material rather than preregistration, blind testing or external validation.

Planned stopping conditions: assess at least four candidates, complete at least two executable real-material experiments, record validation and failures, and produce rankings, reproducible code and the most promising narrative-control follow-up. Do not repeatedly optimise weak methods merely because code already exists.

## Methodological reading

Verified original-author/journal sources: Cutting et al. (2010), Cutting et al. (2011), Cutting (2016), CineScale (2021), HISTORIAN (2022) and official OpenCV method documentation. See `BIBLIOGRAPHY.md`. Some PMC/ScienceDirect full-text entry points required CAPTCHAs or returned 403. Record only material actually verified, without claiming to have read inaccessible full texts.

## Experiment execution record

Actual output paths, numbers, statuses and stopping decisions are in the completion records below and REPORT.md.

## 2026-10-26T00:28:25.914995+00:00: round completed and stopped

- Experiment directory: `research-local/quantitative-exploration/round-20261026T001205Z`. Q01–Q04, the Q05 challenge and a second numerical-implementation check are complete. Unique film material remains 600 seconds without expanding to other films.
- The strongest new evidence is conditional brightness reorganisation in this film. Retain E010, low-level-similarity mismatches and failures of the character proxy.
- Ordering controls show that global permutations and preservation of passage differences produce conclusions of different strength. Positive correlation alone cannot establish a principle of form.
- Missing activity windows remain blank. Insufficient 10-second hard-cut control pools are BLOCKED, without post-hoc metric rescue.
- Engineering tests first identified normalisation of numerical DCT residuals for constant images. This was corrected to missingness before producing actual film outputs. Duplicate descriptive-field names in the first supplementary audit prevented receipt publication; correcting those names allowed it to pass without changing original statistics or thresholds.
- All 225 Python tests passed. Original video/Excel/reference SHA values match, and PTS checks passed for all 144 images. Assistant observations remain distinct from researcher annotations, and future human-review sheets stay blank.
- No commits/pushes, database connections or additional dependency/model downloads. Stop development on this film after completing the task's conditions. The next confirmatory experiment remains HYPOTHESIS.

### Complete replay acceptance under the same procedure

A full replay in `research-local/quantitative-exploration/replay-20261026-verification` gives matching SHA values for 16 core products and matching challenge numbers. Face-box counts, areas and coordinate sets match, but return order differs in 10/288 rows. Keep both raw CSV files and do not use array indices as character identities. Original annotations are unchanged. The two requested decoding intervals total 20 minutes, with 10 minutes of unique material. The replay is not a new independent empirical sample.

## 2026-10-26T08:40:40.500177+00:00: user-authorised full-corpus extension by studio

The inventory contains 732 metadata records, 454 videos and 278 records without video. Use specific production institutions and fractional co-production weights, retaining unknown/provisional identity flags. A 24-clip preflight found failures of keyframe-only sampling on long-GOP sources, and that original method is preserved. Uniform reference frames at about 1Hz passed 24/24 checks. Four-process corpus batching has started. Protocol: corpus_studio/PROTOCOL.md; progress/outputs: research-local/studio-luminance/corpus-20261026T083348Z.

## 2026-10-26T10:56:05.037428+00:00: full-corpus production-institution analysis completed

All 454/454 videos succeeded; 452 films were included and 278 metadata records lack video. The corpus covers about 662.84 hours; studio reports and coverage tables are in corpus_studio/REPORT.md. Retain films as analysis units, fractional co-production weights and year/colour/type sensitivities. Group differences are not interpreted as institutional causes or narrative recognition.

## 2026-10-26T11:02:50.021821+00:00: full-corpus production-institution analysis completed

All 454/454 videos succeeded; 453 films were included and 279 metadata records lack video. The corpus covers about 662.84 hours; studio reports and coverage tables are in corpus_studio/REPORT.md. Retain films as analysis units, fractional co-production weights and year/colour/type sensitivities. Group differences are not interpreted as institutional causes or narrative recognition.

## Corpus-result revision and completion (2026-10-26)

The preceding 452-film result was an initial conservative exclusion of duplicate bytes across keys rather than decoding failure, preserved in `analysis/`. Opening-credit images subsequently confirmed that 《永恒的友谊.mp4》 was actually a byte-identical copy of 《延安游击队》. File-SHA-bound `identity_overrides.json` resolves this in derived analysis, without changing original filenames/JSON. Current `analysis_final/` contains 453 films, 279 records lacking valid video and 17 institutions. `analysis_revision2/` preserves the intermediate version.

Studio quartile plots, relative-time heatmaps, a 14-frame source-quality contact sheet and the opening credits of 《刘三姐》 were actually inspected. Multicoloured imagery under a B&W label prompted post-hoc source diagnostics. All 453×3 frames were extracted, and the 14 chroma warnings include obvious colour casts, so they cannot become original-colour-process labels. Exclusion sensitivities change primary means by at most 0.003918; the main analysis neither removes films nor changes labels.

Final independent numerical audits passed for 454-file products/source states, 732 keys, PTS/means/SDs of 453 films, co-production weights and studio means. All 247 Python tests passed. Source states and research JSON/original Excel SHA values remain unchanged. Primary group-mean differences are smaller than substantial within-group variation, and timescale rankings change, so further studio-ranking optimisation stops. The next narrative validation still requires independent references, without asking the researcher to rewatch now. Code, parameters, failed procedures, early results, figures, QA and actual limitations are preserved. Final entry points: corpus_studio/REPRODUCE.md and CURRENT_ANALYSIS.txt in the run directory.

## 2026-10-26T11:08:15.870873+00:00: full-corpus production-institution analysis completed

All 454/454 videos succeeded; 453 films were included and 279 metadata records lack video. The corpus covers about 662.84 hours; studio reports and coverage tables are in corpus_studio/REPORT.md. Retain films as analysis units, fractional co-production weights and year/colour/type sensitivities. Group differences are not interpreted as institutional causes or narrative recognition.

## 2026-10-26T11:58:52.726159+00:00: hard-cut/transition testing by institution started for all available material

The user authorised the complete corpus. Current run: `research-local/studio-editing/corpus-20261026T114911Z`, covering all frames of 453 distinct films and retaining 732-record coverage. Existing 1Hz brightness data cannot substitute for this. The hard-cut V-only baseline reproduces native original-PTS candidates point by point. Both frame-number scenarios give 43TP/2FP/2FN at ±0.08 seconds, excluding human gradual intervals. Complete gradual intervals still yield 0TP/91FP/4FN; later corpus outputs are candidate diagnostics only. Existing independent annotations remain unchanged, without additional viewing requests.

The first partial run is preserved. A new current run started after checks showed that a shared scaler and AUTO2 threading produce exactly the same 11 arrays across 15248 frames. Complete frame_features.npz and cut_candidates.json SHA values also match byte for byte for the first four films before/after optimisation. These are not new independent empirical samples. All 253 Python engineering tests passed. Corpus batching is incomplete, so studio results are not published prematurely.

### 2026-10-26T12:37:45.467964+00:00: S02 numerical-boundary recovery

A pure-white frame in the complete 126024-frame cache for 《无穷的潜力》 had ROImean=1.0000000000000002 and was rejected by the old strict range check. Values are clipped back to the boundary only within 8×float64 machine precision, preserving original NPZ files and failures. Rechecking complete source SHA, actual EOF tail frames and display endpoints completed 415 hard-cut candidates and gradual diagnostics. Thresholds, original pixels and annotations remain unchanged, without decoding the full film again. The repaired source is archived by SHA; all 255 tests passed while remaining corpus batches continued.

## 2026-10-26: S02 full-corpus hard-cut/transition testing completed and stopped

All 453/453 distinct sources completed, with 732 coverage rows, 279 missing valid videos and data for 17/60 institutions. Actual coverage is 59,478,844 frames and 661.2911 hours, producing 194,243 primary hard-cut candidates and 252,711 default gradual candidates. The first batch had 451 successes and 2 failures. Two more frames in 《胜利在望》 had the same machine-precision boundary excess. The frozen recovery protocol completed 614 candidates. Neither recovery overwrites original NPZ/failure records, and independent EOF/SHA checks passed.

Primary group candidate rates range from 4.011–5.440/minute, with common overlap of ten group IQRs at 4.474–5.115. At threshold 2.5, 东北 exceeds 天马; among B&W features, 海燕 exceeds 天马; under single-institution metadata, 珠江 slightly exceeds 天马. A 999-permutation reference within year × type × colour cells gives observed residual share 0.0764 and reference median 0.0220 for 347 films. Adding source width uses a different 299-film set, giving 0.1135 versus 0.0265. Both corrected tail proportions are 0.001. Do not label these causal or compare different samples as effect strengthening.

Retesting original hard-cut references gives 43/2/2 under both frame-number scenarios at ±0.08 seconds. Strict gradual scores remain 0/91/4 at tIoU≥0.5. These ten minutes are development material, without corpus-wide accuracy ground truth. Default gradual counts cannot represent true studio preferences. Preserve all original annotations without asking the researcher to rewatch.

Original seek-based spot checks could not locate some encoded source frames; partial products and failure logs are stored separately. Earlier decoding precisely reached 170 original-PTS frames. The assistant actually inspected all 6 contact sheets covering 17 films/34 candidates: 13 gradual rows show no obvious mixing, with other examples already in dissolves, fade-type confusion, ending cards reading “完” and fade-ins. Hard cuts also show counting/type-unit issues near ghosting or images turning black. Assistant interpretations are stored separately, without replacing researcher references or estimating corpus-wide P/R.

Real end-title counterexamples motivated an additional post-hoc [10%,90%) sensitivity using all existing candidates without decoding again. Whole-film rates were checked for all 453 films. Ten-group changes range from −0.180 to +0.024/minute, with 珠江 exceeding 海燕. The main analysis remains unchanged. This is not automatic narrative or ending segmentation.

Independent scalar cut/PTS/source-state/product checks for all 453 films, 732-row coverage and institutional weights/means passed. Original research JSON/Excel SHA values remain unchanged, and all 255 Python tests passed. Actual extraction took about 5.86 hours of software CPU time, plus 93.8 seconds for recovery. No commits/pushes, DB operations, downloads or uploads occurred. Final entry point: [corpus_editing/ASSESSMENT.md](corpus_editing/ASSESSMENT.md); reproduction and archived records are in REPRODUCE in the same directory. Stop repeatedly optimising weak models and institutional rankings. Independent narrative correspondence remains the next research direction.

## 2026-11-10T22:22:56.272947+00:00: full-corpus production-institution analysis completed

All 454/454 videos succeeded; 454 films were included and 278 metadata records lack video. The corpus covers about 663.92 hours; studio reports and coverage tables are in corpus_studio/REPORT.md. Retain films as analysis units, fractional co-production weights and year/colour/type sensitivities. Group differences are not interpreted as institutional causes or narrative recognition.

## 2026-11-10: Three-source version refresh

Current source count is 454. File-state comparison identified replacements for 《买牛、扒瓜园》《永恒的友谊》《老保管、新媳妇来了》. All three received new full-file SHA256, ingestion records, grey-level samples and frame-complete cut/gradual candidate extraction. 451 other source measurements retain their original receipts and output digests. Current identity mapping assigns the new 永恒 source to its own key after opening-credit inspection.

Both independent numerical audits passed across 454 sources and 732 metadata keys. Current aggregates contain 2,390,266 timestamped grey-level observations, 59,715,616 decoded editing frames, 194,781 primary cut candidates and 253,704 default gradual candidates. All institutional tables, temporal/threshold/crop/source strata, conditional references and central-interval comparisons were rebuilt. Nine fixed sampling checks on the new encodings passed, alongside the separately preserved 24-clip validation.

New identity QA viewed 30 opening frames. Chroma QA extracted nine replacement-source frames and inherited 451 version-bound diagnostics. The current institutional candidate sample inspected 170 frames in six contact sheets. Sixteen gradual-candidate rows retained one scene configuration, while one showed image mixing. These assistant observations remain separate from the independent Shang Gan Ling manual reference and its existing validation.

The Python suite passed 262 tests. Resume checks verified completed refresh jobs without republishing extraction receipts. Current run pointers select research-local/corpus-refresh/20261110/luminance and editing. Public tables, figures, source versions and verification records are packaged under corpus_refresh/20261110. October results and dated presentations remain snapshots linked to the current release.
