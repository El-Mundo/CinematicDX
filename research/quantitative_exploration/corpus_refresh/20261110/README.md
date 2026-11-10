# Corpus source refresh, 10 November 2026

The current corpus contains **454 video files**. File-state comparison with the October extraction receipts identified three replacements. Full-file SHA256 checks confirmed that all three contain changed bytes. Their film keys remain stable. The source change table records both versions, file sizes, technical changes and measurements.

## Updated sources

| Film | Metadata year | New dimensions | New duration, seconds | Relative grey-level change L30 | Hard-cut candidates | Gradual candidates |
|---|---:|---:|---:|---:|---:|---:|
| 买牛、扒瓜园 | 1965 | 852×638 | 4847.158 | 0.356721 | 177 | 522 |
| 永恒的友谊 | 1960 | 720×576 | 5439.520 | 0.365859 | 395 | 649 |
| 老保管、新媳妇来了 | 1966 | 852×662 | 3911.655 | 0.486365 | 127 | 476 |

Opening-credit inspection confirms the new *Yong Heng De You Yi* source as 《永恒的友谊》, produced by Xi'an Film Studio and directed by Liu Baode. Its measurements now belong to that film key. The first title of the combined 《老保管、新媳妇来了》 record was inspected within the opening two minutes. The second title was outside that inspection sample. Release years follow the research metadata.

[Changes and previous file measurements](changed_sources.csv) and [all 454 source versions](source_versions.csv) provide the numerical record. Previous file measurements belong to the previous bytes and effective film identity shown in the change table.

## Current empirical coverage

| Quantity | Updated result |
|---|---:|
| Metadata records | 732 |
| Videos with completed measurements | 454 |
| Metadata records lacking a corresponding local video | 278 |
| Measured duration, hours | 663.922079 |
| Timestamped grey-level samples | 2,390,266 |
| Decoded presentation frames for editing analysis | 59,715,616 |
| Primary hard-cut candidates | 194,781 |
| Default gradual-transition candidates | 253,704 |
| Institutions with measured films | 17 |

Three sources were re-extracted. The other 451 retain their original measurements and receipts. Reuse checks compare device, inode, byte count, modification time and change time against those original receipts, and verify all saved measurement output hashes. Unchanged video bytes were not reread. The three replacements received new complete-file hashes and complete editing decodes to EOF. Inherited configurations and the current configuration use the same extraction methods and parameters.

All film tables, institutional summaries, 100-bin relative timelines, 10/30/60-second grey-level comparisons, type/colour/year/source-size strata, editing threshold and crop comparisons, conditional permutation references and central 10–90% editing comparisons were rebuilt from the current film set. Institution weights remain equal per film with fractional 1/k memberships for co-productions.

## Validation

- The complete Python suite passed **262 tests**. The test log accompanies this release.
- Independent numerical audits passed for all 454 sources. They check original PTS, scalar grey-level statistics, the scalar hard-cut decision rule, candidate totals and institutional weighting.
- The three replacements received nine additional fixed 60-second sampling checks, totalling 540 seconds. All nine passed the existing reference-frame versus dense-decoding criteria. The original 24-clip validation remains separately recorded.
- The chroma diagnostic now covers 454 sources and 1,362 sampled frames. It reuses 451 source-bound diagnostics and extracts nine new frames. The 14 flagged sources retain the same video versions and sampled bytes as the prior inspection.
- The current institutional candidate sample contains 17 films, 34 candidates and 170 source frames. All six contact sheets were inspected. Sixteen of the 17 gradual-candidate rows retain the same scene configuration across the sampled frames, commonly showing performance or other within-shot changes. One row contains visible image mixing. These observations explain continuing failure cases.
- Opening-credit and candidate contact-sheet observations are assistant inspections. The independent researcher reference remains the 《上甘岭》02:30–12:30 annotation, using its existing video SHA. Hard-cut precision, recall and F1 are 0.9556 at ±80 ms. Default gradual localisation gives 0 matched, 91 unmatched predictions and 4 missed reference spans at temporal IoU ≥0.5. Gradual tables describe candidate output under that measured limitation.

## Results and inspectable data

- [Grey-level report](luminance/REPORT.md), [film coverage and measurements](luminance/film_measurements_and_coverage.csv), and [institutional summary](luminance/studio_summary_all.csv).
- [Editing report](editing/REPORT.md), [film coverage and measurements](editing/film_measurements_and_coverage.csv), and [institutional summary](editing/studio_summary_all.csv).
- Both result directories include the complete generated CSV tables and PNG/PDF figures. The validation directory contains numerical audits, new-source sampling checks, source-identity observations, chroma observations and editing contact-sheet observations.
- [Provenance and published-file SHA256 manifest](provenance.json).

The updated 30-second grey-level means for groups with at least ten measured members range from 0.388396 to 0.426049. Northeast, Bayi and Xi'an are the three highest groups at this timescale. Within-group variation and the other temporal scales accompany these means in the result tables. Institutional and historical interpretation still requires source criticism and film-historical evidence.

## Reproduction and version history

Current local runs are `research-local/corpus-refresh/20261110/luminance` and `research-local/corpus-refresh/20261110/editing`, each with an `analysis/` directory. `ACTIVE_CORPUS_RUN.txt` and `ACTIVE_EDITING_RUN.txt` select these runs. Original videos, research metadata, annotations and the October extraction bundles serve as preserved inputs to the version chain.

The incremental entry point is `scripts/refresh_corpus_sources.py`. The two current `REPRODUCE.md` documents specify preparation, extraction and aggregate replay. Reproduction requires the local source files and parent extraction bundles. Large frame arrays remain in the local research output directory. The dated October presentation and audit sections document their original snapshot. This release supplies the current corpus data.

This update used Codex for version checking, incremental execution, numerical audits and report maintenance. Human annotations retain their original provenance.
