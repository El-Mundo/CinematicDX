# Update record

## 17 November 2026, English documentation using Codex

Translated explanatory documentation, report templates and figure labels into English. Original film titles, production institutions, metadata, annotation vocabularies and database-related values remain unchanged. Two user-supplied presentation versions are copied unchanged into dated folders: the [current upgrade deck](docs/presentations/20261113/README.md) and the [historical technical demo](docs/presentations/20261028/README.md). The [presentation index](docs/presentations/README.md) distinguishes them. The underlying measurements and source-version records remain unchanged.

## 10 November 2026, corpus source refresh using Codex

Replaced-source checks identified 《买牛、扒瓜园》《永恒的友谊》《老保管、新媳妇来了》. Their full-file hashes, ingestion records, grey-level samples, hard-cut candidates and gradual-transition candidates now describe the new versions. The corpus remains 454 videos.

All institutional tables, relative timelines, temporal/threshold/crop/source sensitivities and conditional references were rebuilt. The [published data release](research/quantitative_exploration/corpus_refresh/20261110/README.md) contains the current tables, figures and source-version manifest. It records 2,390,266 grey-level observations and 194,781 primary hard-cut candidates across 59,715,616 decoded frames. Gradual outputs retain their candidate status and the existing unsuccessful interval validation.

451 measurements retain their original receipts through explicit source/configuration checks. New extraction, source-identity inspection, nine additional sampling checks and independent numerical audits completed successfully. The Python suite passed 262 tests. The dated October audit records that earlier research snapshot; the presentation index identifies the current upgrade deck and historical technical demo separately.

## 28 October 2026 — GUI and interaction experience improvements using Codex

This publication brings the desktop update developed in `ee00475c39e0fbff54fa34b68bcc04b33ff865b6` onto `master`. It preserves that existing commit and the Codex development branch. The mainline merge message identifies both the GUI/interaction focus and Codex assistance.

### Desktop changes

- Equal Local directory and Database choices, one active metadata store, remembered setup and visible source/error information.
- Catalog search, exact production-label and year filters, clearer empty states, optional stable keys and linked-media information.
- Local research-record folder access, refreshed JavaFX styling, and macOS launch/package scripts.

Research-record actions open existing folders. They do not run CV analysis. The optional Python worker remains a process-lifecycle placeholder.

### Additional material in this publication

The earlier development commit also contains the metadata-store abstraction, standalone timestamped Python analysis code, tests, methodological records and Upgrade pilot audit. These are part of the mainline publication and should not be mistaken for a GUI-only diff. This dated publication originally included a preliminary-results presentation summarising existing evidence and measurement procedures, without rerunning film extraction. For the presentation versions now available, see the [presentation index](docs/presentations/README.md).

Original videos, the research inventory, original human annotations, local catalogs/settings, model/runtime caches and intermediate experimental data remain outside Git. The application screenshots were captured from the actual running interface. The preliminary-results presentation embedded selected existing figures. Aggregate results and their limitations remain documented in the research reports.

### AI assistance, validation and review

Implementation, tests, interface styling, build tooling, experiments, audits and report/presentation preparation received assistance from OpenAI Codex. Research questions, constraints and the independent shot-boundary/narrative annotations came from the researcher. Assistant visual observations and model predictions do not become independent human reference data. See the [detailed disclosure](docs/AI_ASSISTANCE.md).

Previously executed verification recorded 109 passing Java tests, 255 passing Python tests and actual native macOS interaction checks in [GUI verification](docs/gui/VERIFICATION.md). This publication step adds disclosure/reporting and merges the existing implementation; it does not claim a new run of those suites. Engineering tests do not establish CV accuracy or validate film-theoretical interpretation.

Hard-cut accuracy is locally assessed on the annotated excerpt. Complete gradual-transition segmentation remains unreliable. Cross-film studio comparisons and visual–narrative correspondence remain exploratory. No independent coauthor review or approval is recorded by this publication.
