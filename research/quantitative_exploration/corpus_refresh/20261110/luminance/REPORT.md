# CinematicDX: corpus-wide digital gray-level change by production institution

Status **PROVISIONAL**: coverage and numerical extraction have actual outputs and checks. Historical and institutional interpretation remains exploratory rather than a causal or general studio-style conclusion.

## Actual coverage

- Metadata: 732 films. Available video files: 454. Successful extractions: 454. Failures: 0.
- No measurements were invented for the 278 metadata records lacking local video. Quality/identity exclusions: 0. Final film-level comparison: 454 films.
- Actual file processing covered about 663.92 hours. Primary-film observations retain 2,390,266 original PTS samples (2,390,266 samples extracted from 454 files). Metadata contains 60 specific production institutions, of which 17 have included films.
- Processing duration counts 454 files. After deduplication, 454 digital byte versions cover about 663.92 hours. Identity corrections use an evidence-preserving analysis mapping without changing original filenames or metadata.
- Identity associations based on existing unique filenames remain provisional. Four ambiguous same-title cases use earlier assistant opening-credit checks and file SHA. Not every film has independent human opening-credit identity validation.
- Videos, metadata and original Excel files serve only as inputs. Extraction and analysis run locally.

This version update re-extracted 3 source files and inherited existing measurements for 451 source files. The reuse manifest retains the original run directory, receipt SHA and video version. Old and new extractions use identical measurement parameters. See this run's `plan.json` and the parent directory's `refresh.json` for the source manifest and update record.

This source-version check recorded 0 groups of duplicate byte versions across film keys and 0 unresolved conflicts in the analysis mapping. Per-file versions and selections are in `source_versions.csv`. Identity corrections apply only to versions matching their expected video SHA.

| Type | Measured films |
|---|---:|
| Feature | 362 |
| Opera | 63 |
| Performance | 11 |
| Artistic Documentary | 9 |
| Musical | 9 |


| Colour field | Measured films |
|---|---:|
| B&W | 346 |
| Colour | 108 |


## Definition of studios

Specific institutional names in `production` remain distinct rather than being replaced by the regional/collective categories in `category`. 东北电影制片厂 and 长春电影制片厂, and Shanghai, Tianma and Haiyan, retain their separate metadata entries without an imposed institutional genealogy. Co-productions receive weight 1/k per institution. Films are not weighted by frame count or duration. Member counts can overlap across studios, while fractional weights across all institutions still sum to the included-film count. Single-studio and colour/type sensitivities are reported separately.

## Measurement and validation

Uniform approximately 1Hz reference-frame sampling preserves original PTS/time_base. Gray images have width<=160 with a fixed crop of 5% on each side and 10% at top/bottom. Full-frame measurements provide a sensitivity check. There is no per-frame histogram equalisation or claim to recover original photographic brightness. Nearest-observation temporal representation is capped at 5 seconds. Missing observations are not filled with 0, and inadequate coverage is not silently included.

The primary statistic is **the mean absolute difference between adjacent 30-second ROI gray-level means, divided by the film's temporal gray-level standard deviation**. It describes relatively slow gray-level variation, not a cutting rate, narrative-event detection or optical flow per second. Normalisation cannot eliminate differences in nonlinear tone mapping, scanning, restoration, compression or content composition.

The initial keyframe-only method passed only 21 of 24 fixed real validation clips because sparsely encoded sources introduced bias. The original failure and code are archived. Uniform reference-frame sampling retained the original thresholds and passed 24/24 clips. Compared with complete-decoding 1Hz sampling, the median 30-second mean error was 0.000313 and the maximum 0.002252. This is neither frame-complete full-film ground truth nor historical-brightness calibration, and it does not cover every unknown transfer workflow.

## Main studio table (at least 10 included member films)

| Production institution | Metadata/video available/included | Mean relative 30-second change | Central 10–90% | Year×colour×type centred residual |
|---|---:|---:|---:|---:|
| 东北电影制片厂 | 34/26/26 | 0.426 | 0.409 | 0.010 (n=23) |
| 八一电影制片厂 | 74/63/63 | 0.412 | 0.402 | 0.007 (n=57) |
| 西安电影制片厂 | 22/17/17 | 0.412 | 0.409 | 0.004 (n=12) |
| 北京电影制片厂 | 91/76/76 | 0.407 | 0.399 | 0.001 (n=56) |
| 上海电影制片厂 | 55/52/52 | 0.405 | 0.396 | -0.014 (n=43) |
| 长春电影制片厂 | 155/109/109 | 0.403 | 0.393 | -0.001 (n=89) |
| 江南电影制片厂 | 23/14/14 | 0.400 | 0.389 | -0.008 (n=9) |
| 天马电影制片厂 | 69/36/36 | 0.398 | 0.387 | -0.002 (n=25) |
| 珠江电影制片厂 | 25/15/15 | 0.395 | 0.383 | 0.014 (n=11) |
| 海燕电影制片厂 | 76/38/38 | 0.388 | 0.383 | -0.004 (n=30) |


Higher values indicate more variation at the 30-second scale relative to the film's overall gray-level range. They cannot directly mean “brighter,” “more tense” or “more political.” The table is a descriptive ordering of current digital versions. Small institutional samples remain in the complete CSV without ranking their strength.

Year×colour×type residuals are differences from the mean for films with the same year, colour and type. They are computed only for cells containing at least 5 films and at least 2 institutions. The reported n is the available-film count. This is sensitivity to an alternative explanation, not an identified causal studio effect. Cinematographers, subjects, restoration batches and all source differences have not been matched.

## Composition and sensitivity

| Production institution | All | B&W features | Colour features | Single-studio films |
|---|---:|---:|---:|---:|
| 东北电影制片厂 | 0.426 | 0.427 (n=23) | — (n=0) | 0.426 |
| 八一电影制片厂 | 0.412 | 0.422 (n=49) | 0.384 (n=9) | 0.413 |
| 西安电影制片厂 | 0.412 | 0.418 (n=10) | 0.373 (n=1) | 0.412 |
| 北京电影制片厂 | 0.407 | 0.409 (n=40) | 0.434 (n=17) | 0.407 |
| 上海电影制片厂 | 0.405 | 0.397 (n=40) | — (n=0) | 0.405 |
| 长春电影制片厂 | 0.403 | 0.405 (n=72) | 0.423 (n=17) | 0.403 |
| 江南电影制片厂 | 0.400 | 0.398 (n=7) | 0.393 (n=2) | 0.400 |
| 天马电影制片厂 | 0.398 | 0.411 (n=21) | 0.429 (n=6) | 0.398 |
| 珠江电影制片厂 | 0.395 | 0.417 (n=8) | 0.323 (n=1) | 0.404 |
| 海燕电影制片厂 | 0.388 | 0.392 (n=22) | 0.409 (n=8) | 0.388 |

Absolute digital gray-level means for all institutions are descriptive and cannot independently explain historical lighting across studios. B&W/Colour and Feature/Opera/Artistic Documentary/Performance/Musical remain separate. CSV files preserve year details, source pixel widths and the 10/30/60-second scales without selecting the most favourable scale. The central 10–90% analysis is only an endpoint/opening/ending sensitivity check, not automatic identification of the narrative body. Single-studio means that metadata lists one production entry, not that all historical collaboration is known.

The 100-position-bin curves aggregate equally weighted, within-film-standardised profiles with fractional co-production weights. Relative position is a coordinate, not an assumed four-act structure or fixed narrative stage. Interquartile ranges across films show sample heterogeneity, not population confidence intervals or significance from independent frames.

## What these results support

1. For the 10 institutions with at least 10 films, the primary means range from 0.388–0.426, a span of 0.038. Their interquartile ranges across films share an overlap at 0.382–0.430. A studio mean cannot replace within-studio variation. Overlap is not a significance test establishing “no difference.”
2. **Temporal-scale comparison**: the three highest groups at 10 seconds are 八一电影制片厂, 天马电影制片厂, 长春电影制片厂; the three highest groups at 30 seconds are 东北电影制片厂, 八一电影制片厂, 西安电影制片厂; the three highest groups at 60 seconds are 东北电影制片厂, 上海电影制片厂, 八一电影制片厂. `studio_temporal_scale_sensitivity.csv` preserves complete means at every scale. Each comparison concerns digital gray-level change at its specified timescale.
3. **Composition-conditioned comparison**: the same-year×colour×type centred residuals include 上海电影制片厂 -0.014 (n=43); 珠江电影制片厂 0.014 (n=11). Each conditional comparison uses its own matchable film subset and still requires interpretation alongside subject, cinematographer and copy provenance.
4. Within-film profiles preserve positional differences lost in means. Brighter openings/endings in several groups are patterns for further investigation only. No independent opening/ending or event annotations were made here. Relative positions cannot be named as narrative stages, and co-occurrence is not treated as an institutional functional principle.

## Source-quality counterexample and supplementary checks

Sampling found clearly multicoloured frames in 《刘三姐》, although its metadata label is B&W. Subsequent opening-credit inspection identified 《刘三姐》, 长春电影制片厂 and director 苏里, consistent with the existing record. No year was read. This observation independently establishes neither the original colour process nor a basis for automatic relabelling.

A subsequent **post-result source diagnostic** sampled fixed 20%/50%/80% positions in all 454 films, totalling 1362 frames. Stronger-chroma flags occurred in 14 B&W-labelled videos. Earlier contact sheets show both clearly multicoloured images and nearly monochrome images with purple/green casts. Current per-film flags indicate digital chroma requiring inspection. The chroma rule has no independent human accuracy estimate, and absence of a flag does not establish that an entire film is B&W. The diagnostic remains PROVISIONAL. Original metadata, the main analysis and all films remain intact.

Used only as exclusion sensitivity, these flags change the primary 30-second studio means by at most 0.003918 in absolute value among groups with at least 10 films. See `colour_label_qa/studio_chroma_flag_sensitivity.csv` for B&W, B&W-feature and all-type results. This indicates limited numerical sensitivity of these means to this exclusion operation, not unbiased colour/year strata across sources.

## Key limitations

1. Acquisition and preservation shape the visible sample. The 278 records lacking valid video are unevenly distributed across studios, so this sample cannot represent the complete population of 732 films.
2. Copy provenance and scanning/restoration histories are largely unknown. Identical encoding/dimensions do not guarantee the same transfer conditions, and within-film z standardisation cannot repair these issues.
3. Institutions intertwine with period, colour format, film type, people/locations and subject distributions. Observed group differences are not independent proof of studio style.
4. Only part of 《上甘岭》 has an independent narrative-event reference. The other films lack full-film narrative ground truth, so macro-level curves must not be treated as narrative structure.
5. Approximately 1Hz sampling and 30-second means overlook rapid flashes, short transitions and frame-level jitter. The project's hard-cut/gradual tasks remain separately validated.
6. File SHA identifies digital byte versions rather than authenticating historical copies. Provisional identity mappings remain marked. Original-filename mapping found 0 groups of duplicate bytes across films, with 0 currently unresolved conflicts.
7. “Full film” means the complete local-file timeline, not a verified complete historical release. Platform introductions, logos, subtitles, endings and incomplete versions can affect gray levels. No such content was automatically removed according to the curves.

## Outputs and reproduction

Experiment directory: `/Users/caoshuangyuan/Desktop/Workspace/CinematicDX/research-local/corpus-refresh/20261110/luminance`. All 454 videos have attempt records. Each successful file's summary/samples/profiles/run binds original-file SHA, software, parameters and PTS. The main table, 732-film coverage table, year/colour/type and source-size tables, single-studio analyses, all-studio relative timelines and negative validation results are preserved.

Current analysis directory: `/Users/caoshuangyuan/Desktop/Workspace/CinematicDX/research-local/corpus-refresh/20261110/luminance/analysis`. Complete studio tables, per-film coverage and temporal profiles are respectively `studio_summary_all.csv`, `film_measurements_and_coverage.csv` and `studio_relative_timeline.csv`. PNG/PDF figures are in the same directory.

`run_corpus_luminance.py` can resume from completed per-film receipts and rejects reuse after input or parameter changes. `analyse_studio_corpus.py` accepts only inputs whose complete attempt sequence has finished. It does not publish partial results as corpus-wide findings. Output snapshots retain core code and report-generation source.

These remain reproducible measurements of digital formal properties and temporal organisation. Source calibration, independent material and film-historical interpretation are required before institutional or historical arguments can be supported.
