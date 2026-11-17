# Actual run and reproduction entry points

## Current version: 2026-11-10

The current run is `research-local/corpus-refresh/20261110/editing`, with final analysis in `analysis/`. See [source refresh and results](../corpus_refresh/20261110/README.md) for the current 454-video summaries, old/new video SHA values for three films and publicly viewable CSV files. `ACTIVE_EDITING_RUN.txt` records the current entry point.

The same frame-by-frame algorithm re-extracted 《买牛、扒瓜园》《永恒的友谊》《老保管、新媳妇来了》. The other 451 unchanged sources inherit original frame-level caches, candidates and receipts. `measurement_reuse.json` binds each inherited job to its original run, configuration SHA, receipt SHA and video version. Numerical auditing verifies identical extraction parameters, allowing changes only to descriptive fields such as run scope. Each new source has its complete SHA256 reread and is decoded to EOF.

See the [gray-level reproduction entry point](../corpus_studio/REPRODUCE.md) for commands to create a new incremental run directory and extract the three films. Then execute the following steps in the new run's `editing/` directory, substituting the actual new directory.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python MPLCONFIGDIR=/tmp/cinematicdx-mpl OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/analyse_corpus_editing.py \
  --run research-local/corpus-refresh/replay-20261110/editing \
  --report-directory research-local/corpus-refresh/replay-20261110/editing/report

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/challenge_editing_edges.py \
  --run research-local/corpus-refresh/replay-20261110/editing

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/audit_corpus_editing.py \
  --run research-local/corpus-refresh/replay-20261110/editing
```

Aggregation recalculates every studio table, temporal profile, parameter/source sensitivity, conditional permutation reference and central-film challenge. The audit independently recomputes scalar cut rules, PTS, candidate counts and institutional means. Output directories must not already exist. Rebuilding inherited results requires per-film outputs from parent runs.

Manual validation still uses the same-SHA 《上甘岭》 reference at 02:30–12:30. The primary hard-cut configuration yields 43 matches, 2 false positives and 2 misses (±80 milliseconds). Default gradual detection yields 0 matches, 91 false positives and 4 misses at tIoU≥0.5. The three source-version updates add actual extraction evidence; the validation sample remains the original independently annotated interval.

## Historical run notes: 2026-10-26

The commands, counts and paths below document the October version. Use the entry point above for the current version and results.

Current-run pointer: `research/quantitative_exploration/ACTIVE_EDITING_RUN.txt`. This run is `research-local/studio-editing/corpus-20261026T114911Z`, with final analysis in `analysis/`. All 453/453 sources are complete, as are the numerical audit, assistant inspection of all six contact sheets and research interpretation. See the [final assessment](ASSESSMENT.md). `completion_receipt.json` binds actual outputs from each stage. `progress.json` records only the original batch's progress and cannot erase later recovery records.

## Inputs and frozen configuration

`plan.json` preserves 732 film records, 453 unique-source jobs, original paths, keys, source SHA values and inherited identity mappings. The mislabelled duplicate among 454 original paths is counted only once; 279 records without valid video remain in coverage tables. The original research JSON is at the repository root, and films are on the external drive `/Volumes/Extreme SSD/Video/Chinese1949-66`. Engineering tests cannot replace empirical reruns without these actual source files.

`config.json` binds extraction-source SHA, parameters and original Excel SHA. Complete SHA values for all original videos are rechecked before unfinished jobs begin. Each job's `run.json` retains source-file state and output SHA values. If inputs, source code or parameters change, create a new run directory rather than altering old receipts to force reuse.

The existing `.venv-m3` contains PyAV18, NumPy2.4.6, OpenCV4.13 and PySceneDetect0.7.1. The source introduces no heavy dependencies or model downloads. Matplotlib produces static scientific figures; Chinese names use the local STHeiti font path. Other systems may explicitly substitute a font without silently changing measurement parameters.

## Execution

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/run_corpus_editing.py \
  --run research-local/studio-editing/corpus-20261026T114911Z --workers 4
```

This is the actual extraction command. It has completed and need not be restarted. Successful jobs with identical inputs are reused after receipt checks. Preserve partial outputs from unfinished/failed jobs separately before retrying; retain initial failures and subsequent revisions. For independent re-extraction, create another directory, copy the frozen plan/config and passed preflight records, verify original paths, code and SHA, and run without deleting existing results.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/finish_corpus_editing.py \
  --run research-local/studio-editing/corpus-20261026T114911Z --wait
```

This is the actual finalisation command and has completed. It sequentially produces grouped analysis, institution-balanced contact sheets and an independent numerical audit. `pipeline_ready.json` means only that numerical outputs are complete, not corpus-wide human validation. The additional actual observations are stored separately in `visual_qa/assistant_review.json` and are not independent human ground truth. See ASSESSMENT.md for the final interpretation.

The first direct-seek inspection could not locate some encoded frames exactly. Its partial outputs remain in `visual_qa_direct_seek_failure_preserved/`. The revised script decodes from an earlier point until the exact original PTS, succeeding for 17 films/170 frames. The actual revised source and SHA are in `visual_qa/inspect_corpus_editing.py` and `selection_and_receipt.json`. The old QA source archived during aggregation remains intact without being represented as the final executed version.

The central-film challenge is a separate analysis added after inspecting end-title material; it does not change primary results:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-m3/bin/python \
  research/quantitative_exploration/scripts/challenge_editing_edges.py \
  --run <new-run-copy-containing-the-same-verified-candidates>
```

The `edge_challenge/` output must not exist; the script refuses to overwrite it. It reads original candidates, checks each film's full-file rate against the primary table, and counts within [10%,90%) of actual decoded coverage. This is complete for the current 453 films, with all input/script/result SHA values preserved.

To recompute grouping only, preserve the original `analysis/` and execute `analyse_corpus_editing.py --run <new-copy> --report-directory <separate-report-directory>` in a new run copy. That copy may reuse identical, verified per-film read-only outputs. Do not overwrite original results or publicly release a test-subset report.

## Outputs

| Path | Contents |
|---|---|
| `preflight/results.json` | Hard cuts with both frame-number origins, multiple tolerances/settings; gradual transitions at multiple tIoU thresholds, retaining strict failures |
| `preflight/fullfilm_execution_equivalence.json` | Old/new execution feature and cut-file SHA equivalence for the first four complete films |
| `preflight/hardware_probe_result.json` | Unavailable hardware-decoding preflight; final processing remains software CPU |
| `films/<job_id>/frame_features.npz` | Every decoded frame's original PTS/nextPTS, display time, V differences, small gray images and other features; no 1Hz subsampling |
| `films/<job_id>/cut_candidates.json` | Primary/lenient/strict/ROI candidates, retaining minimum-interval suppression records |
| `films/<job_id>/gradual_*.json` | Gradual candidates, raw candidates/NMS, near-black holds and rule diagnostics; not transition ground truth |
| `films/<job_id>/summary.json` and `run.json` | Per-film measurements, software, endpoint evidence, actual complete-decoding status, source and output SHA |
| `films/<job_id>/roundoff_recovery.json` | Original values/cache indices/repaired values for tiny floating-point excursions; original cache is not overwritten |
| `recovery_sources/<SHA>/` | Source snapshots of the actual recovery program and helper |
| `extraction_complete.json` and `effective_extraction_complete.json` | Separate initial completion/failure records and effective completion records that preserve failures |
| `analysis/film_measurements_and_coverage.csv` | 732 rows, retaining missing and failed records separately without fabricated measurements |
| `analysis/studio_summary_*.csv` | All institutions, B&W/Colour features and single-studio films; equal film weights and co-production 1/k weights |
| `analysis/studio_year_colour_type.csv` | Year×metadata-colour×type composition comparisons |
| `analysis/studio_source_width.csv` and `studio_frame_cadence.csv` | Digital source dimensions and actual frame-cadence sensitivity, without claiming historical transfer conditions |
| `analysis/*relative_timeline.csv` and PNG/PDF | Candidate rates in 100 relative-position bins, not narrative stages |
| `analysis/conditional_*reference.json` | 999 within-composition-cell permutations for single-studio films, with actual coverage and BLOCKED status for sparse samples |
| `analysis/transient-flags-*.json` | Brief A–B–A return warnings, possibly flashes or real short inserts; primary cuts remain intact |
| `visual_qa/` | Five-frame candidate contact sheets from institution-based film sampling and their provenance; assistant observations are not independent ground truth |
| `numerical_audit.json` | Audit of frame-level PTS, independent scalar hard-cut rules, weights and group means |
| `edge_challenge/` | Post-result central-film sensitivity for all 453 films; does not replace primary results |
| `completion_evidence/`, `completion_receipt.json` | Test/failure logs, stage provenance and final output SHA; original failures retained |

Engineering tests: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v`. Currently 255 tests pass, including machine-precision-only recovery and rejection of actual out-of-range values/NaN. Real-film conclusions remain limited by manual-reference coverage, source quality and method validity.

## Known use boundaries

Hard-cut accuracy has only within-condition evidence from ten minutes of 《上甘岭》. V-only processing has limited sensitivity to cuts distinguished mainly by hue; source FPS, movement and flashes also affect results. Gradual detection failed strict complete-interval evaluation, so candidate density cannot establish actual studio preferences for fades/dissolves. These rules do not cover wipes, irises and other forms. Existing manual annotations were not rewritten in response to automatic results, and the researcher was not asked to view or annotate again.
