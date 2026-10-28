# Update record

## 28 October 2026 — GUI and interaction experience improvements using Codex

This publication brings the desktop update developed in `ee00475c39e0fbff54fa34b68bcc04b33ff865b6` onto `master`. It preserves that existing commit and the Codex development branch. The mainline merge message identifies both the GUI/interaction focus and Codex assistance.

### Desktop changes

- Equal Local directory and Database choices, one active metadata store, remembered setup and visible source/error information.
- Catalog search, exact production-label and year filters, clearer empty states, optional stable keys and linked-media information.
- Local research-record folder access, refreshed JavaFX styling, and macOS launch/package scripts.

Research-record actions open existing folders. They do not run CV analysis. The optional Python worker remains a process-lifecycle placeholder.

### Additional material in this publication

The earlier development commit also contains the metadata-store abstraction, standalone timestamped Python analysis code, tests, methodological records and Upgrade pilot audit. These are part of the mainline publication and should not be mistaken for a GUI-only diff. The new [preliminary-results presentation](docs/presentations/20261028/README.md) summarises existing evidence and explains how measurements are generated from video; preparing it did not rerun film extraction.

Original videos, the research inventory, original human annotations, local catalogs/settings, model/runtime caches and intermediate experimental data remain outside Git. The application screenshots were captured from the actual running interface. The presentation embeds selected existing figures, so the aggregate results and documented limitations shown there are included in the published report.

### AI assistance, validation and review

Implementation, tests, interface styling, build tooling, experiments, audits and report/presentation preparation received assistance from OpenAI Codex. Research questions, constraints and the independent shot-boundary/narrative annotations came from the researcher. Assistant visual observations and model predictions do not become independent human reference data. See the [detailed disclosure](docs/AI_ASSISTANCE.md).

Previously executed verification recorded 109 passing Java tests, 255 passing Python tests and actual native macOS interaction checks in [GUI verification](docs/gui/VERIFICATION.md). This publication step adds disclosure/reporting and merges the existing implementation; it does not claim a new run of those suites. Engineering tests do not establish CV accuracy or validate film-theoretical interpretation.

Hard-cut accuracy is locally assessed on the annotated excerpt. Complete gradual-transition segmentation remains unreliable. Cross-film studio comparisons and visual–narrative correspondence remain exploratory. No independent coauthor review or approval is recorded by this publication.
