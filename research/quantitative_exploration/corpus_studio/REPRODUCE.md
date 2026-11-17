# Reproduction and output locations

## Current version: 2026-11-10

The current run is `research-local/corpus-refresh/20261110/luminance`, with final analysis in `analysis/`. See [source refresh and results](../corpus_refresh/20261110/README.md) for current results, old/new video SHA values for three films and publicly viewable CSV files. All 454 videos succeeded, retaining 2,390,266 timestamped observations. Of 732 metadata records, 278 lack local video.

Only the new versions of 《买牛、扒瓜园》《永恒的友谊》《老保管、新媳妇来了》 were re-extracted. The other 451 source files inherit original measurements and receipts after device, inode, size, mtime and ctime checks. Complete SHA256 was reread for the three changed files. `measurement_reuse.json` records inherited provenance, original receipt SHA and video versions; `refresh.json` records old/new source associations. Measurement parameters retain the original protocol.

To reproduce the incremental update from the same local videos, use a new output directory and compare the generated change inventory with the three SHA values in the public version table.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/refresh_corpus_sources.py \
  --output-directory research-local/corpus-refresh/replay-20261110 \
  --luminance-parent research-local/studio-luminance/corpus-20261026T083348Z \
  --editing-parent research-local/studio-editing/corpus-20261026T114911Z

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/refresh_corpus_sources.py \
  --output-directory research-local/corpus-refresh/replay-20261110 --extract
```

To recompute only current gray-level aggregates, generate a separate analysis directory from the new version's per-film results.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python MPLCONFIGDIR=/tmp/cinematicdx-mpl OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/analyse_studio_corpus.py \
  --run research-local/corpus-refresh/20261110/luminance \
  --output-directory research-local/corpus-refresh/20261110/luminance/analysis_replay \
  --report-directory research-local/corpus-refresh/20261110/luminance/report_replay \
  --source-diagnostic-directory research-local/corpus-refresh/20261110/luminance/colour_label_qa

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/audit_studio_corpus.py \
  --run research-local/corpus-refresh/20261110/luminance \
  --analysis-directory research-local/corpus-refresh/20261110/luminance/analysis_replay \
  --output-file research-local/corpus-refresh/20261110/luminance/corpus_audit_replay.json
```

The 24-clip sampling validation and independent manual reference for 《上甘岭》 remain bound to original video versions. The three new film versions have separate technical probes, opening-title checks and chroma samples. Chroma diagnostics reuse unchanged-source frames and records by video SHA, resample changed sources, and fully recompute studio exclusion sensitivity. Rebuilding incremental results requires local original videos and per-film outputs in parent run directories.

## Historical run notes: 2026-10-26

The commands, counts and paths below document the October version. Use the entry point above for the current version and results.

This run: `research-local/studio-luminance/corpus-20261026T083348Z`. Current results are in `analysis_final/`; `analysis/` and `analysis_revision2/` are preserved earlier analyses. `CURRENT_ANALYSIS.txt` points to the current version.

Film files are on the external drive `/Volumes/Extreme SSD/Video/Chinese1949-66`. `plan.json` records absolute paths and SHA values for the research JSON and existing M2 identity map; `config.json` records original Excel SHA. Complete video SHA is in each `films/<job_id>/summary.json`; the adjacent `run.json` records software/parameters/original PTS and result SHA. Film keys and source-byte versions have separate identifiers. Matching filenames do not automatically establish identity.

No database, service, model downloads or new dependencies are used. The existing `.venv-m3` is used, with environment lock file `analysis-python/requirements-m3.lock.txt`. Figures use the local STHeiti font. On another operating system, explicitly replace the font path; this affects figure rendering only. Derived NPZ files and images are in Git-ignored directories; videos are not committed.

## Recompute studio results only

The following recomputes from the complete 454 extraction receipts. Outputs must use a new directory; the corpus is not decoded again. Run all commands from the repository root.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python MPLCONFIGDIR=/tmp/cinematicdx-mpl OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/analyse_studio_corpus.py \
  --run research-local/studio-luminance/corpus-20261026T083348Z \
  --output-directory research-local/studio-luminance/corpus-20261026T083348Z/analysis_replay \
  --report-directory research-local/studio-luminance/corpus-20261026T083348Z/replay_report \
  --source-diagnostic-directory research-local/studio-luminance/corpus-20261026T083348Z/colour_label_qa
```

`--report-directory` saves the replay report separately to avoid updating the current research report. CSV numbers should be identical. Receipts contain execution times and reports contain output directories, so whole receipts/reports need not be byte-identical.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/audit_studio_corpus.py \
  --run research-local/studio-luminance/corpus-20261026T083348Z \
  --analysis-directory research-local/studio-luminance/corpus-20261026T083348Z/analysis_replay \
  --output-file research-local/studio-luminance/corpus-20261026T083348Z/corpus_audit_replay.json
```

The audit checks all file receipts, coverage of 732 keys, unchanged original metadata/Excel, original PTS conversion, independently accumulated per-film scalar means/standard deviations, conservation of co-production weights and studio means. It does not validate historical lighting, unknown copies or independent human identity judgements.

## Re-extract from original videos

Core source, inputs and parameters are frozen. Changes prevent reuse of old checkpoints. `run_corpus_luminance.py --run <directory> --workers 4` reuses completed, matching per-film receipts in the current directory. Do not force a rerun by deleting existing results.

For genuinely independent re-extraction, create a separate run directory, copy the saved `plan.json`, `config.json` and passed `sampling_validation.json`, verify source paths and SHA, then start. Preserve both old and new outputs. Current configuration binds source SHA; modified core code cannot be represented as the same method. Corpus-wide re-extraction takes approximately 136 minutes; actual runtime depends on hardware and disk. It need not be executed again for this task.

Source diagnostics can be rerun independently with `inspect_corpus_sources.py` and `check_corpus_colour_labels.py`, each explicitly specifying `--run`, `--analysis-directory` and a new `--output-directory`. The latter samples only 453×3 frames. Its flags are chroma warnings, not validated classifications of original colour processes.

## Main outputs from this run

| File | Meaning |
|---|---|
| `analysis_final/film_measurements_and_coverage.csv` | Complete coverage of 732 records; 453 measured and 279 lacking valid video |
| `analysis_final/studio_summary_all.csv` | All 60 metadata institutions retained, 17 measured; fractional co-production weights |
| `analysis_final/studio_relative_timeline.csv` | 100-position-bin curves for all films/B&W features/Colour features |
| `analysis_final/studio_temporal_scale_sensitivity.csv` | 10/30/60-second and central 10–90% sensitivity |
| `analysis_final/studio_year_colour_type.csv` | Year×colour-label×type stratification and coverage |
| `analysis_final/studio_source_width_sensitivity.csv` | Encoded-width groups; width does not establish transfer provenance |
| `identity_overrides.json` | Derived duplicate-film correction bound to actual file SHA |
| `duplicate_identity_review/` | Opening-title evidence and assistant review for 《延安游击队》 |
| `source_qa_revision2/` | 14 source-quality figures, ROI, additional 《刘三姐》 opening titles and assistant observations |
| `colour_label_qa/` | Chroma diagnostic with 1359 frames, 14 flags, exclusion sensitivity and assistant observations |
| `rejected_keyframe_only/` | Preserved failed method and parameters with 21/24 passing clips |
| `sampling_validation.json` | All 24/24 fixed validation clips pass the uniform approximately 1Hz reference-frame method |
| `corpus_audit_final.json` | Numerical/provenance audit |
| `completion_receipt.json` | Final file paths, check results and SHA; does not validate historical interpretations |

Test command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v`. The 247 passing tests verify engineering mechanisms. Empirical claims also depend on the actual film sources, preflight, numerical audit and explicit limitations above.
