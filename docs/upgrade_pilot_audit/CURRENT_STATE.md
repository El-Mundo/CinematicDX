# Current state: Upgrade pilot readiness

Audit date: 26 October 2026. This assessment concerns the inspected local workspace, not merely the GitHub branch. Evidence identifiers and exact locations are in [EVIDENCE_INVENTORY.md](EVIDENCE_INVENTORY.md).

This audit records the state before the subsequent GUI refresh and Git publication. Later discovery of the cached Maven distribution, Java verification and native desktop screenshots are documented in [GUI verification](../gui/VERIFICATION.md); the empirical results and their limitations below are unchanged.

**Assessment: COMPARATIVE PILOT AVAILABLE, at an exploratory descriptive level.** More importantly for the Upgrade, a bounded single-film analytical pilot already connects measured visual properties with independently supplied narrative events. This is stronger than a functioning application or extraction demonstration. It is not a validated account of complete film form, a cross-film narrative replication, or an explanation of institutional causation. These are internal planning categories, not university regulations.

## What a credible pilot must demonstrate here

The essential chain is identifiable real material → inspectable timestamped measurements → a precise question about organisation or relationships → independent reference structures → bounded validation and interpretation. Measuring several sophisticated properties is unnecessary if none answers a film-studies question. A defensible negative finding also counts. Full-corpus SNA, automatic narrative recognition, a frontend, and perfect gradual-transition segmentation are not prerequisites for the narrower pilot identified below.

| Internal level | Evidence actually available | Assessment |
|---|---|---|
| 0: design | Research framework, protocols, bibliography, modular pipeline and source/annotation distinctions | Present; not empirical evidence by itself |
| 1: technical feasibility | Standalone Python CLI and research scripts; current imports and 255 executed tests pass | Present; tests include synthetic fixtures and do not validate film interpretation |
| 2: empirical extraction | Complete digital-file analysis of *Shang Gan Ling*, source manifest, original PTS, candidate intervals, gray measurements, error records | Present |
| 3: analytical pilot | Q01 interval-order controls; Q02/Q05 gray reorganisation near independent event onsets versus ordinary hard cuts; counterexamples and robustness checks | Present, exploratory and within one development excerpt |
| 4: comparative pilot | Consistent digital-gray measurements across 453 distinct linked sources, studio/type/year/source sensitivities; full-frame cut-candidate extension | Present for qualified descriptive comparison; no independent cross-film narrative replication |

The corpus extension strengthens feasibility and comparative description. It does not turn six within-film event boundaries into hundreds of independent narrative tests.

## Repository and executable functionality

- `cinematic/`: JavaFX metadata application. `MetadataStore` has parallel JDBC and local-directory implementations; film/attribute/media CSV workflows, configuration and worker lifecycle code exist. Repository SQL defines `films`, `film_media_storage`, `custom_field_definitions` and `film_custom_fields`. This is metadata infrastructure, not a CV research result.
- `analysis-python/cinematicdx/`: ingestion, source probing, inventory, timestamp handling, shot candidates/reports, manual-reference validation, narrative alignment, gradual candidates, exploration, and corpus analysis. These workflows execute without JavaFX, JDBC or MariaDB.
- `analysis-python/worker.py` is a signal-aware waiting loop. It is not the implementation of the CV pipeline. Actual research runs use the CLI or scripts directly.
- `research/quantitative_exploration/`: protocols, experiments, method assessments, source snapshots and bounded runners. Some runners are experiment-specific and use local paths/fonts; this is a reproducible local research workflow rather than a portable finished product.
- `research-local/` and `outputs/`: substantial real empirical outputs and original annotation intake. `research-local/` is ignored by Git; it must not be confused with published repository data.
- `database/`: existing MariaDB system/storage files. No server was started or queried. Application-table contents are UNVERIFIED; neither the presence of these files nor the 732-record JSON proves 732 SQL rows.
- No notebook was found inside CinematicDX. Relevant notebooks and face-clustering results exist in separately inspected sibling projects.

The active branch is `codex/quantitative-evidence-20261026`. HEAD, `master` and the local `origin/master` all resolve to `326ef7687bda5e7ada9010f6d42d3b013816a097`. The six inspected commits concern the original metadata application. Most current analysis modules and research records are untracked; modified Java sources are also uncommitted. **That commit alone cannot reproduce the pilot.** Existing hash-bound source snapshots help, but an Upgrade evidence packet must include the actual working code and selected derived data. No commit, checkout or remote operation was performed.

## Actual material and provenance

The research JSON contains 732 films and 732 distinct keys. A current directory check finds 454 non-hidden MP4 paths, representing 453 distinct linked file versions under the documented byte-identical misnaming correction. There are 279 metadata records without a valid corresponding video. All 453 current source-file states match the final editing receipts in this audit; the current *Shang Gan Ling* file was additionally rehashed in full.

*Shang Gan Ling* is linked to the 1956 Changchun production record, with Sha Meng and Lin Shan listed as directors. The digital version is `sha256:a044ce2cd1b561bf2599f21b5415163e01f7abdd6313919ac1f8ed5e9657d9f0`: H.264, 852×656, 185,825 decoded frames, decoded coverage 7,434.006 seconds, time base 1/16000, first source timestamp 0.043 seconds. Header frame-rate fields differ slightly; nominal 25 fps is not used to reconstruct timestamps. Acquisition, scan/restoration history and historical appearance remain unknown. Production facts are verified as recorded metadata, not newly established archival facts.

## Strongest existing results

1. **Full-file feasibility:** M3 has 934 hard-cut candidates and 935 automatic partition intervals for this file, with IDs, start/end timestamps, durations and figures. The automatic interval mean 7.9508 seconds and median 3.32 seconds are not validated true average/median shot lengths: gradual transitions and other missed boundaries remain. The first automatic interval alone spans 198.4 seconds, illustrating why candidate partitions require qualification.
2. **Independent local reference:** the researcher confirmed complete, independent annotation over 150–750 seconds: 45 hard cuts, four gradual spans and 11 narrative event records. There are ten internal event onsets. E011 continues beyond the window; its true end remains unknown. Original Excel values are preserved. Confused boundary-kind fields are not used as intended labels. Approximate second-level event times and both QuickTime frame-origin scenarios are retained.
3. **Hard-cut validation:** at ±0.08 seconds, both origin scenarios give 43 TP, 2 FP and 2 FN, precision/recall/F1 0.9556. This is a development-excerpt assessment, not full-film or corpus accuracy. Other tolerances and thresholds are saved.
4. **Sequence analysis:** 41 manually bounded intervals avoiding annotated gradual spans have mean 8.945 seconds and median 4.960 seconds. Their four runs differ markedly. The observed adjacent log-duration change, 0.7788, is not exceptional against within-run shuffles (median 0.8568; descriptive 2.5–97.5% range 0.7060–1.0017). Weaker whole-sequence shuffling makes the result appear stronger by removing run differences. This supports the methodological importance of the comparison baseline; it does not identify metric montage.
5. **Narrative correspondence:** for six hard-cut-associated event onsets, absolute pre/post digital-gray change averages 0.101233, versus median 0.018460 across 1,999 matched control assignments. Original-frame integration gives control median 0.018576. E010 changes only 0.004046; E006 lies inside its broad event-specific control range. Thus the aggregate contrast does not establish a universal visual event signature. Controls use the independent manual cut reference, not an assumption that all automatic candidates are correct.
6. **Comparative feasibility:** 453 linked films have approximately 2.38 million timestamped gray samples. The 30-second relative-change studio means range 0.388–0.426, with extensive within-group overlap and scale-dependent rankings. A separate all-frame run decoded 59,478,844 frames and produced 194,243 hard-cut candidates. Both are exploratory descriptions, not established studio styles.

## Methods that must not be presented as established measurements

Current complete gradual-transition segmentation fails its strict local interval test. Default rules give 0/91/4 and the saved TransNet V2 comparison 0/3/4 (TP/FP/FN at tIoU≥0.5). Looser overlap scores do not rescue the complete-interval claim. Current Haar outputs also fail as person-count/shot-scale proxies: 79/144 images have no detections, 31/144 change count under a parameter change, and inspected examples include missed side faces and false boxes. No independent shot-scale or person-count accuracy assessment exists. Optical-flow event comparisons have insufficient valid coverage; similarity retrieval is low-level, not verified motif recognition.

The accessible sixteen-film face/narrative study is a reusable external precedent with actual tables and manual adjudication data. It is not a CinematicDX experiment, and its retained-face accuracy must not be transferred to detection recall or to Chinese historical material.

## Current execution checks and limits

The audit executed the CLI help command and the complete Python suite: **255 tests passed in 7.411 seconds, no skips**. It verified 177 initial pilot output hashes, six protocol inputs, 16 saved replay artifact pairs, the current source-video digest, 453 source states, 15 editing-stage hashes, 492 editing aggregate output hashes, 39 luminance aggregate output hashes and six pinned TransNet files. The six-event mean and saved control median were recalculated from existing tables/arrays. No new extraction, inference, model download or corpus processing was run.

The local runtime is Python 3.11.3, PyAV 18.0.0, OpenCV 4.13.0, NumPy 2.4.6, PySceneDetect 0.7.1 and Matplotlib 3.10.8. Combined PyAV/OpenCV imports emit duplicate AVFoundation class warnings; the checks nevertheless complete. Use a writable `MPLCONFIGDIR` for demonstrations. TensorFlow/DeepFace/MTCNN are not in this isolated environment. The saved TransNet run used a separately recorded system TensorFlow runtime and was not rerun. JDK 11 exists; Maven was not found on PATH or in the bounded standard/tmp searches, so Java compilation/tests and live UI behaviour were not revalidated. These limitations do not prevent the standalone Python pilot.

The shortest remaining route is evidence selection, careful film-level interpretation, captions and preservation of a reproducible packet. No new CV feature is compulsory for a limited Upgrade claim. See [gap analysis](PILOT_GAP_ANALYSIS.md), [minimum specification](MINIMUM_PILOT_PLAN.md) and [priority plan](ACTION_PRIORITY.md).
