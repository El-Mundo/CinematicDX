# CinematicDX

Computational research infrastructure for *Negotiating Film Form: Computational Approaches to Twentieth-Century Political Cinema*.

## Latest update — 28 October 2026

**GUI and interaction experience improvements using Codex.** The desktop refresh and its supporting metadata/research code are now published on the main development line, `master`. The `codex/quantitative-evidence-20261026` branch records the development work; its name identifies the workflow rather than a separate source of research authority.

For collaborators, the [update summary](CHANGELOG.md) describes the publication scope and the [AI-assistance disclosure](docs/AI_ASSISTANCE.md) distinguishes Codex-assisted code and reporting from researcher-supplied questions and independent manual annotations. The [24-slide preliminary-results presentation](docs/presentations/20261028/README.md) includes measurement procedures, validation and limitations. Independent coauthor review or approval is not implied by publication.

## Desktop workspace

The JavaFX desktop workspace now provides parallel local-directory/database setup, live catalog search, exact production-label and year filters, optional stable keys, linked-media availability, and direct access to local research records and the Upgrade audit. The interface does not turn candidate predictions into validated film measurements.

![Catalog filtered by production and year](docs/gui/screenshots/catalog-filters.jpg)

These are screenshots of the running macOS application. The isolated preview catalog contains 732 rows from the local research inventory and 453 existing media references, populated through the existing CSV workflow. That private catalog, the original inventory, videos, annotations and experimental caches are not shipped with the repository. New users create/open their own catalog.

```sh
./scripts/run-desktop.sh
```

Maven is required; the script also detects an existing Maven wrapper cache. Java source/module compilation targets Java 11. The tested Apple Silicon desktop preview uses an installed JDK 17 and OpenJFX 17.0.18. On macOS, an installed JDK 17 is selected when `JAVA_HOME` is unset. Dependencies are resolved through Maven Central on the first build.

```sh
./scripts/package-desktop-macos.sh
```

The packaging command creates `cinematic/target/desktop/CinematicDX.app` with a local runtime. It requires an installed JDK with `jpackage` and refuses to overwrite an existing app. Move the previous generated app before rebuilding. For isolated settings use `./scripts/run-desktop.sh -Dcinematicdx.config=/path/to/preview.properties`; packaging accepts the equivalent `CINEMATICDX_CONFIG` environment variable. Normal launches keep the app-wide settings described below.

See [usage and screenshots](docs/gui/README.md), [GUI verification](docs/gui/VERIFICATION.md), and the [Upgrade pilot readiness audit](docs/upgrade_pilot_audit/CURRENT_STATE.md). The historical research outputs referenced by the audit remain local; their code and protocols are included.

## Metadata sources and setup

CinematicDX supports two parallel metadata sources: **Local directory** and **Database**. Choose a source in **CinematicDX Setup**, then select **Open CinematicDX**. Both sources support film editing, film CSV imports, typed attribute CSV imports, and media mappings. The main screen identifies the active source.

For local storage, choose an existing folder. Use **Create local catalog…** once to create a new catalog there, or open a folder containing an existing `catalog.json`. Choosing a folder or opening a missing catalog never creates metadata implicitly. A local setup requires no database server or database credentials. The original research inventory JSON is not imported automatically; populate a new catalog using the existing CSV workflows.

The source choice and remembered settings are stored app-wide in `~/.cinematicdx/cinematicdx.properties` and restored on the next launch. Setup still appears before a source opens. Existing configuration beside the application is read when the global configuration does not exist; the legacy file is left untouched. Choosing local storage preserves remembered database settings, and choosing the database preserves the remembered local directory. Change sources through setup on the next launch.

Local catalogs use a versioned JSON snapshot containing stable film IDs and keys, complete film fields, typed custom attributes, and media references. Writes replace the snapshot atomically, with `catalog.json.bak` retaining the immediately previous version. One application session can open a catalog at a time. Do not delete `.cinematicdx.lock` while a session is open; the lock file may remain after normal shutdown. External edits are detected and require reopening. Malformed catalogs and unsupported versions are rejected rather than replaced with empty metadata. If recovery is necessary, close all sessions and preserve copies of both catalog files before deliberately restoring a checked backup; recovery is never automatic.

Database mode retains the existing SQL repository and initialization behaviour; selecting it explicitly opens the configured database and may perform its existing table initialization or legacy compatibility operations. No new database schema is introduced by the source abstraction. The Python worker option is shared by both modes; the current worker remains a process placeholder, not an implemented film-analysis pipeline.

Build with Java 11 and Maven using `mvn test` from the `cinematic` directory, and launch with `mvn compile javafx:run`. Metadata tests use temporary local catalogs and in-memory H2 databases; a MariaDB server is not needed. JSON serialization uses the Jackson 2.21.8 BOM.

## Methodological Vision: LoD-Aware Corpus Design for Computational Film Analysis

The database-independent M2–M4 commands are documented in [analysis-python/README.md](analysis-python/README.md): source auditing and ingestion, PTS-preserving shot candidates and descriptive timelines, independent boundary validation, and narrative annotation/alignment tools. Automatic segmentations remain predictions until reviewed; real narrative comparisons require independently supplied annotations.

This project explores a **Level-of-Detail (LoD) aware corpus architecture** for moving-image research. The initial motivation comes from a methodological problem in digital film studies: how can a researcher move between distant reading and close reading without treating them as two separate or opposed modes of analysis?

In traditional film studies, close reading usually works through careful attention to individual films, scenes, shots, and frames. Distant reading, by contrast, works through abstraction, aggregation, and comparison across larger corpora. However, moving-image data complicates this distinction. A film corpus is not only a collection of titles or metadata; it is also a large-scale visual, temporal, and computational object. A corpus of hundreds of films may contain millions of frames, thousands of shots, and multiple layers of metadata, production history, formal features, and interpretive context.

This project treats **LoD not merely as a technical optimisation, but as a methodological and cultural concept**. LoD provides a way to define, store, visualise, and analyse film data at different scales:

Corpus → Film → [Scene] → Shot → Frame

The optional Scene level is included because it often functions as an interpretive bridge between machine-readable units such as shots and frames, and humanistic units such as narrative sequence, dramatic situation, or historical argument.

The central idea is that the space between distant reading and close reading should not be understood as a binary opposition. Instead, it can be modelled as a continuous analytical space in which different levels of detail are selected according to the research question, available evidence, and computational cost.
Corpus as Database, Not Just Metadata

A simplified conceptual structure is:
```
Corpus
  └── Film
        ├── Metadata
        ├── Optional media reference
        ├── Concepts / tags / historical categories
        ├── Segmentation data
        │     ├── Scene
        │     ├── Shot
        │     └── Frame / sampled frame
        ├── Feature layers
        │     ├── string
        │     ├── integer
        │     ├── float
        │     ├── boolean
        │     ├── vector
        │     └── other extensible data types
        └── Provenance / analysis history
```

The database is intended to support not only filmographic metadata, but also computationally generated features, manually curated annotations, imported tabular data, and future machine-learning outputs.

JavaFX as a Reading and Visualisation Interface

The main GUI is designed in JavaFX. Its primary role is not to perform heavy computation directly, but to provide a visual and interactive interface for reading the corpus.

### Why Distance and LoD Matter for Humanistic Evidence

A further theoretical motivation for this project concerns the nature of humanistic data itself.

Humanistic data is never simply neutral or objective material. It is usually produced, selected, preserved, classified, translated, and interpreted through particular historical, institutional, political, and cultural positions. A film corpus, an archive catalogue, a museum collection, a list of production credits, or a set of genre labels is always shaped by decisions about what counts, what is visible, what is excluded, and what is worth preserving.

This creates a familiar tension in the humanities: the tension between the canonical and the vernacular, the central and the local, the official and the marginal. One might argue that local histories, vernacular archives, and culturally specific categories deserve more attention precisely because they resist the simplifying force of grand narratives. However, this does not mean that the most local or most specific object is automatically the most meaningful object of study.

If classification depends only on qualitative interpretation, the possible subdivision of locality is almost endless. A “local” history may refer to a national cinema, a regional film industry, a city archive, a county museum, a community organisation, a family collection, or even the private collection of a single individual. Conversely, a supposedly “central” or “canonical” history may refer to a national archive, a state-sponsored filmography, a university collection, a global museum, or a large institutional database. Each of these positions can be challenged by a case that is either more central or more local.

In other words, the opposition between centre and locality is not a stable binary. It is a scale.

This matters because research projects are also shaped by imagined audiences. A digital humanities project may be designed for a local community, for specialists in a specific field, for comparative scholars, or for broader methodological debates. Yet these audiences do not always remain separate. A project that begins as a local or vernacular archive may later contribute to a wider discussion about digital method, corpus design, visualisation, or cultural analytics. Conversely, a large-scale methodological project may need to return to highly local evidence in order to remain historically responsible.

Binary language such as “canonical versus vernacular” or “distant versus close” can therefore obscure the more complex space between these positions. The relationship between centre and locality, like the relationship between distant reading and close reading, is better understood as a continuous and negotiable field of scale.

This is where LoD becomes methodologically useful.

LoD does not claim that all scales are equivalent, nor does it dissolve historical specificity into abstract data. Instead, it provides a way to make scale explicit. It allows a researcher to ask:

- At what level is this object being studied?
- Is the relevant unit a corpus, a film, a scene, a shot, a frame, a person, a production company, a local archive, or a historical concept?
- What is gained by moving outward toward aggregation?
- What is lost when detail is reduced?
- What becomes visible only when one moves inward toward local evidence?
- Can a local case contribute to a more general methodological problem?
- Can a large-scale pattern be returned to inspectable evidence?

In this sense, LoD is not only a computational strategy. It is a way of making the politics and epistemology of scale visible.
