# M2: Video inventory, source registration and timeline probing

For the current corpus results as of 10 November 2026, see the [source refresh and results](../research/quantitative_exploration/corpus_refresh/20261110/README.md). Three changed sources among 454 videos were re-extracted. The other 451 retain their original extraction receipts. All studio-level grey-level, hard-cut and gradual-candidate summaries were recomputed. Grey-level extraction succeeded for every video, retaining 2,390,266 timestamped observations. Of the 732 metadata records, 278 lack a corresponding local video. Reproduction entry points are documented for [grey-level analysis](../research/quantitative_exploration/corpus_studio/REPRODUCE.md) and [editing measurements](../research/quantitative_exploration/corpus_editing/REPRODUCE.md). The M2/M3 procedures and manual-annotation experiments below document their respective dated stages.

These commands run independently of JavaFX and the database. They require Python 3.9 or later and `ffprobe` on PATH, with no third-party Python packages. `worker.py` retains its original purpose and does not launch these commands.

## 1. Verify the video directory

Run from the repository root and replace the example path with the actual directory:

```sh
python3 analysis-python/cinematicdx_cli.py inventory \
  --root "/path/to/videos" \
  --metadata ChineseSocialistFilms49-66.json \
  --expected-count 454 \
  --probe-headers \
  --output research-local/m2/inventory-001
```

`--probe-headers` performs bounded container and stream probing on candidate files. It does not compute corpus-wide content checksums or require complete video decoding. Without it, the command inventories directories and permissions only. File extensions identify video candidates, not a verified count of distinct films. Multi-part files, alternative versions, duplicate content and missing films require further assessment.

The inventory does not follow symbolic links and excludes hidden and system entries. It retains directory errors, empty or unreadable files and probe failures in its reports. Filename matching supplies candidates without assigning film identity automatically. `readable` records a permissions check. A successful technical probe provides evidence that a file could actually be opened. Neither establishes that the complete film can be decoded.

Outputs:

- `inventory.json`: complete inventory, candidate matches, errors and optional raw technical probe information.
- `inventory.csv`: a per-file overview for inspection.
- `run.json`: parameters, software and code identifiers, metadata checksum, output checksums and limitations.

`expected_count_matches` compares only the number of scanned candidate files. Inspect `scan_complete`, errors and exclusions as well to establish what the count of 454 represents.

## 2. Register an explicitly identified film

First verify the file-to-film association manually, then explicitly supply its metadata `key` or the local catalog's `film_key`:

```sh
python3 analysis-python/cinematicdx_cli.py ingest \
  --video "/path/to/videos/桥.mp4" \
  --metadata ChineseSocialistFilms49-66.json \
  --film-id qiao \
  --source-description "Record the known download, copy or transcription source; leave unknown details unknown" \
  --output research-local/m2/qiao-run-001
```

Copies or renamed files with identical contents receive the same `video_version_id=sha256:…`. This identifies the complete file bytes, not a historical print, restoration edition or image-content fingerprint. Remuxing or changing file tags can also produce a new identifier. Film identity and file version are recorded separately. The research inventory uses the `research-inventory` namespace by default, which `--metadata-namespace` can override explicitly. Local catalogs use their own UUIDs.

Metadata input supports the existing research JSON and local-directory `catalog.json`, both read-only. This command does not import the research JSON into the Java application, connect to the database or change global application settings.

Outputs:

- `source_manifest.json`: film reference, complete-file SHA-256, original and resolved paths, metadata source and original record, video-stream selection, technical timeline and quality flags.
- `probe.json`: raw ffprobe output, exact arguments, software version and diagnostics.
- `timestamp_sample.json`: a bounded sample of opening-frame timestamps, retaining original PTS, time_base, rational seconds, best-effort timestamps and separately identified playback offsets.
- `run.json`: run UUID, time, parameters, code version or source checksum, and output checksums.

The default sample retains up to 12 frame timestamps. `--timestamp-sample-frames` changes this limit, up to 256. If multiple video streams have no unique default, select one explicitly with `--stream-index`. This is an absolute stream index. Cover images are not treated as film video streams.

ffprobe's `-read_intervals %+#N` limits packets rather than an exact number of frames, so the sample can contain fewer frames than requested. Probing may read additional data to identify the codec and is subject to a timeout. See the [official ffprobe documentation](https://ffmpeg.org/ffprobe.html#Main-options).

Original time coordinates are neither reconstructed from average frame rates nor silently reset to zero. Playback offsets are saved separately as derived coordinates. Matching header frame rates or a small sample of evenly spaced timestamps cannot establish a constant frame rate throughout the film, so `frame_rate_mode` remains `unknown`. This stage does not validate timestamps or decoding across the full file, detect shots, transcode video or establish the authenticity of historical provenance.

Each run requires a new output directory and refuses to overwrite an existing one. It writes the success receipt last and publishes no successful result after a failure. If the input file or metadata changes during execution, registration fails and must be repeated. Keep outputs outside the source-video directory. Git already ignores `research-local/`.

## Validation

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python \
  python3 -m unittest discover -s analysis-python/tests -v
```

Tests use temporary files, mocked probes and very small synthetic videos. They require no research films. Synthetic videos validate the tool workflow and do not establish completion of a real-corpus pilot.

# M3: Shot candidates, durations and timelines

M3 uses an optional isolated environment. M2 itself still requires none of these third-party Python dependencies:

```sh
python3 -m venv .venv-m3
.venv-m3/bin/python -m pip install -r analysis-python/requirements-m3.lock.txt
```

The lockfile records the complete environment tested on macOS ARM64 with Python 3.11.3. Direct dependencies appear in `requirements-m3.txt`. The global Homebrew OpenCV installation lacked a required dynamic library on this machine, so it was not reused. PyAV supplies original timestamps, PySceneDetect 0.7.1 supplies cut suggestions, and Matplotlib produces static plots. No new interface or database dependency is introduced.

For this copy of *Shang Gan Ling* (《上甘岭》), default HSV differences produced suspicious changes close to whole-second positions during opening calibration, despite visual continuity between adjacent frames. A synthetic near-grey colour-shift test reproduced HSV false positives. The baseline for this copy therefore explicitly uses `--luma-only`. This library option actually measures differences in the HSV V channel, rather than historically calibrated film luminance. Suitability for other films is not established.

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py shots \
  --manifest research-local/m2/shang-gan-ling-20261025T202349Z/source_manifest.json \
  --luma-only \
  --output research-local/m3/new-shot-run
```

Use `--start-seconds 300 --end-seconds 420` to process a local interval. These parameters are playback offsets, not source PTS. The actual first and last frames, original ticks, time_base, derived playback offsets and requested range are recorded separately. Every frame is decoded and participates in detection. Analysis images default to a width of 320 pixels, without frame skipping or changes to the source video. The default Adaptive threshold of 3, minimum content change of 15 and minimum candidate interval of 0.12 seconds are recorded, along with filtered-out candidates. Content mode defaults to a threshold of 27.

Outputs are `shots.json`, `shots.csv`, `boundaries.csv`, `summary.json` and `run.json`. Every cut initially has status `unreviewed_prediction`, with transition type awaiting classification. Intervals use `[start,end)` coordinates. The ends of a processed excerpt may contain only part of a shot. Gradual transitions, flashes, camera shake and digital-copy noise still require review. These outputs cannot directly serve as shot ground truth.

Time calculations always use original PyAV PTS and rational time_base values. The library compatibility parameter `fps=1` is not the film's frame rate and does not reconstruct source time. CFR/VFR and H264 B-frame tests verify that it does not round fractional-second boundaries. The source copy's 0.043-second starting offset remains unchanged.

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py shot-report \
  --shots research-local/m3/new-shot-run/shots.json \
  --output research-local/m3/new-report
```

The report includes mean and median duration, duration distributions, ordered timelines, local candidate-cut rates and static PNG/PDF figures. The default uses centred 60-second windows at 15-second steps. Edge windows use their actual covered duration as the denominator. Shot durations and cut rates derive from the same segmentation, so they are not independent discoveries about film form. They do not identify metric montage.

## Independent validation of shot boundaries

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py boundary-reference-template \
  --shots research-local/m3/new-shot-run/shots.json \
  --output research-local/m3/new-boundary-reference
```

The template does not copy predicted cuts. Researchers should independently mark all hard cuts within an explicit coverage interval and record the annotator, method, independence and exhaustiveness within that interval. Narrow `coverage` when reviewing only part of a film. Uncertain gradual transitions may appear as excluded intervals. A reference obtained by inspecting and correcting predictions individually is not an independent reference set.

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py validate-shots \
  --shots research-local/m3/new-shot-run/shots.json \
  --reference /path/to/independent-annotations/boundary_reference.json \
  --tolerance-seconds 0.04 \
  --output research-local/m3/new-validation
```

The 0.04-second tolerance is an example. Prespecify it using the annotation protocol and actual frame intervals. Validation uses one-to-one matching and reports TP/FP/FN, precision/recall/F1, timing errors and individual matches. Rates in genuinely zero-cut intervals can be undefined rather than automatically becoming 100%. Assistant and synthetic references retain explicit provenance and cannot pass as researcher annotations. Opening-segment inspection, prediction-guided spot checks and synthetic tests do not replace independent validation on a real held-out interval.

# M4: Independent narrative annotation and alignment

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py annotation-template \
  --shots research-local/m3/new-shot-run/shots.json \
  --output research-local/m4/new-narrative-template
```

The template starts with an empty `events` list and an awaiting-annotation status. It does not infer events from cut rates. Film and video-version bindings remain fixed, and narrative annotations do not depend on a particular shot-segmentation version. Annotators must specify `annotator`, `annotation_method` (human/assistant/synthetic), `independent_of_visual_measurements` and completion status. Each event requires a unique ID, start and end times, description and certainty. Location, character configuration, narrative time and interpretive notes may be recorded separately. Events may overlap or begin and end within shots.

Define events first in a separate research annotation protocol. For example, specify which changes in an action's goal or situation constitute a new event, and how to handle changes in location, character configuration or narrative time. Such changes are not automatic event criteria. Annotate before inspecting measurement curves and retain disagreements and uncertainty. Visual objects or motifs are not automatically events or formal properties.

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py align-narrative \
  --shots research-local/m3/new-shot-run/shots.json \
  --annotations /path/to/independent-annotations/narrative_annotations.json \
  --window-seconds 30 --control-count 3 --seed 0 \
  --output research-local/m4/new-alignment
```

Outputs include event/shot interval overlaps, cut rates before and after event onsets, and control comparisons. Onsets are not snapped to the nearest cut. Events occurring at cuts are matched to non-event cuts in the same broad temporal region. The central cut is removed, and overlapping event/control windows are excluded. Onsets within shots and at other transitions are reported separately. Dividing the timeline into thirds controls film position and does not assume a three-act narrative. Insufficient matches, edge truncation, uncertain events and window overlaps are reported explicitly.

The default compares the change in cut rate over 30 seconds before and after each event onset against the change at matched controls. Whole-window density is another description. Controls are assigned greedily in event-time order with a fixed random seed. Only complete matched sets reserve control windows. The unit of analysis is the event onset, not a frame or overlapping window. The tool produces no p-values or historical causal conclusions. Unreviewed shots, assistant/synthetic events or annotations without a declaration of independence prevent outputs from being labelled directly interpretable research evidence.

The initial implementation created empty templates only. The real trial annotations and local experiment subsequently supplied are documented below.

### Frame numbering, precision and coverage edges in manual annotations

On 25 October 2026, the first manual trial annotations covered *Shang Gan Ling* (《上甘岭》), 02:30–12:30: 11 narrative events and 50 transition records. Snapshots preserve the original Excel files and cells. The researcher subsequently confirmed that both tables were complete and independent within this interval, that blank certainty meant confident under their rules, and that E011 continued beyond coverage. A separate confirmed version preserves the original draft and source tables. B050 falls outside coverage, leaving 45 hard cuts and 4 gradual transitions within the interval.

A true boundary denotes the researcher's judgement of where an event actually begins or ends. Coverage truncation means that an event begins before or ends after the observation interval, so an interval edge limits the observable portion. Narrative-time continuity is a different judgement and cannot replace these labels. Where original entries used different meanings, retain their values and the annotator's explanation, and mark boundary nature as awaiting confirmation. Do not relabel it automatically from time continuity. Edge cases for gradual transitions likewise concern whether they cross the coverage endpoints.

`cinematicdx.frame_times.resolve_frame_times(manifest_path, frame_numbers, frame_base=...)` requires an explicit zero-based or one-based choice. `resolve_frame_base_candidates(...)` can retain both alternatives during one bounded sequential decode. Both recheck the complete source-video SHA-256, enumerate presentation-order frames from the selected stream's beginning, and retain original PTS/time_base and M2 playback offsets. They decode only through the largest requested frame number and do not divide frame numbers by a nominal or average frame rate. The relation between a player's displayed frame numbers and decoded ordinals still requires calibration. Do not choose the frame base according to which conversion better matches the model being evaluated.

Second-level narrative times retain their approximate second-level precision. Do not invent milliseconds or use a one-frame tolerance to assert that an event falls exactly at a cut. Explorations with wider windows must remain within complete annotation coverage and examine timing-perturbation sensitivity. The original `align-narrative` command did not yet handle separate annotation coverage, truncation fields or second-level timing uncertainty. These records cannot be fed directly into the full-film control workflow.

### Local experiment at 02:30–12:30

`cinematicdx.pilot_compare.compute_pilot_comparison(annotations, shots, manual_reference)` is the pure-computation interface for this 600-second experiment. It explicitly validates film/video identity, local completeness and independence, and computes only within 150–750 seconds. E001's coverage start is not treated as a genuine narrative onset. E011's actual end remains unset, with the observed endpoint of 750 seconds used only for interval overlaps. Previously misused boundary-nature fields do not enter the calculation.

The primary comparison fixes 30 seconds before and after an event onset, removing the central ±1 second from both cut counts and effective exposure. Controls are non-event hard cuts in the same temporal third, with complete, mutually non-overlapping windows and no reuse. The random seed is 0, with one control per event. Exploratory sensitivities separately use 15- and 10-second windows on each side and common onset shifts of −1/0/+1 seconds. These are not independent samples or confidence intervals. Both frame-base scenarios are computed without selection by model score.

The primary ±30-second design yielded no identifiable matched comparison. Its mean remains unset and cannot be interpreted as evidence of no relationship. With zero timing perturbation, ±15 seconds produced only 2 matched sets and ±10 seconds only 3. The mean change relative to controls reversed direction, providing no support for a stable relationship. At the primary 0.08-second tolerance, M3 yielded 43 matches, 2 false positives and 2 misses in both frame-base scenarios, with F1 approximately 95.56%. This is internal validation on the same film and an interval already used for parameter exploration. Gradual-endpoint representation, frame base and tolerance sensitivities are preserved separately. Three manually annotated dissolves were not covered by the existing point candidates. Hard-cut scores therefore cannot establish the reliability of complete shot segmentation.

The results root is `research-local/pilot-results/shang-gan-ling-150-750-20261025T225931Z`. Its `analysis_design.json`, input checksums, complete sensitivities, source snapshots and `run_m4.py` support recalculation. The design was exploratory and selected after inspecting the annotation-time distribution, rather than preregistered validation. Research inputs and outputs remain in an untracked local directory. Re-decoding requires the same hashed video version. Analysis does not require a database service.

## M3/M4 tests and platform record

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python \
  .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v
```

The local OpenCV and PyAV installations bundle separate FFmpeg libraries that emit macOS AVFoundation duplicate-class notices during import. Retain these logs. This work uses file decoding, while camera capture remains unverified. Run records preserve PyAV's embedded library versions. Command-line `ffmpeg -version` output cannot substitute for them.

## Gradual transitions: Interval candidates and independent evaluation

Gradual outputs are start/end intervals, saved alongside the original M3 point candidates without automatically changing the final shot segmentation. The added Python interfaces do not depend on the database:

- `cinematicdx.transition_features.extract_transition_features(...)`: extracts fixed-ROI grey levels, histograms, changes and small image caches for every frame, retaining original PTS, actual frame exposure and evaluation coverage without reading manual annotations.
- `cinematicdx.gradual.detect_gradual_candidates(features, config=...)`: applies near-black monotonic-change and multiscale endpoint-mixing rules, retaining raw candidates, overlap suppression, black-frame and motion diagnostics. Scores are heuristic rankings, not probabilities.
- `cinematicdx.transition_scores.scores_to_transition_intervals(...)`: converts per-frame model scores into contiguous intervals using actual PTS, explicit thresholds and minimum durations, without filling gaps. Short events are saved separately rather than automatically classified as hard cuts.
- `cinematicdx.transition_validation.validate_gradual_transitions(...)`: performs exact one-to-one matching within declared complete coverage, reporting interval localisation, boundary errors, types and all unmatched candidates separately. `point_near_span_diagnostic(...)` describes only point-to-span proximity and does not produce gradual-transition F1.

The current exact matcher is for small experiments, accepting at most 16 gradual reference intervals per scenario and explicitly rejecting larger inputs. This round used only 4. A larger evaluation requires a scalable matching implementation with verified equivalence. Restricting evaluation to small windows around positives would improperly bypass full-interval false-positive scoring.

On 26 October 2026, the original 4 manually annotated gradual transitions in *Shang Gan Ling* (《上甘岭》), 150–750 seconds, were retested. The design and all prespecified parameters were frozen before the corresponding inference runs. However, the interval and annotations were already known, so this remains internal exploration rather than a blind or held-out test. Both zero-based and one-based frame scenarios are retained. The original Excel file, human references and previous point candidates were unchanged.

At the primary temporal intersection-over-union threshold `tIoU >= 0.50`, the primary rule configuration yielded 0 matches, 91 unmatched candidates and 4 misses. The frozen external TransNet V2 comparison yielded 0/3/4. Its three candidates fell within three annotated intervals but achieved IoU of only approximately 0.326–0.418. The fourth response split into short intervals. Failure does not imply an absence of change signals. At the prespecified relaxed threshold `tIoU >= 0.30`, the pretrained comparison yielded 3/0/1, with F1 approximately 0.857. This sensitivity result does not replace failure at the primary criterion.

The TransNet V2 comparison used only the existing local TensorFlow installation and downloaded and verified approximately 36.5 MB of weights from a fixed author commit. It involved no training, fine-tuning or changes to project dependencies. This experiment converts `many_hot` scores using `>0.5` and a contiguous duration of `>=0.4` seconds, without classifying fade-out or dissolve types. Unknown types in the general evaluation cannot establish type-classification performance. Model source, license, weights and environment receipts remain in the local research directory, outside ordinary M3 installation requirements. See the [author implementation](https://github.com/soCzech/TransNetV2) and [paper](https://arxiv.org/abs/2008.04838).

The full experiment resides in `research-local/gradual-pilot/experiment-20261025T233231Z`. `analysis_protocol.json`, `frozen_detector_configs.json` and `pretrained_comparator_protocol.json` record the design. `run_experiment.py` and `run_pretrained_comparator.py` reproduce the calculations. `build_report.py` generates static plots, individual diagnostics and a report from saved results. Failed rule parameters, complete sensitivities and unclassified short intervals are retained. Cached `frame_delta_seconds` originally used backward differences. The rule runner explicitly adapts these to forward exposure as `(next_pts-pts)*time_base`, preserving an adaptation receipt without modifying the original cache.

Further work should separate candidate discovery from complete interval estimation. First test the mechanisms against synthetic transitions with known extents and motion/exposure negative controls, then freeze rules for comparison on real intervals. Do not extend predicted spans directly from these 4 references. Passing all 208 Python tests in this round establishes implementation conformity with the protocol. It does not support automatically accepting gradual candidates as final shot boundaries, cross-film accuracy claims or conclusions about narrative relationships.
