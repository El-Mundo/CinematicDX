# GUI verification — 26 October 2026

## Executed checks

- Existing metadata/store application baseline: 106 Java tests passed before the GUI changes.
- Updated application: 109 Java tests passed, including three new search/filter tests; all failures/errors/skips zero. Tests use temporary catalogs and in-memory H2, not a MariaDB server.
- Native package build: Maven package and runtime dependency assembly succeeded using JDK 17/OpenJFX 17.0.18 `mac-aarch64`; the resulting `CinematicDX.app` was launched from its actual macOS app bundle.
- After the worker compatibility fix, the final native package was rebuilt from a fresh dependency input directory, reopened, restored the saved local-source choice while still showing setup, and loaded the catalog again. The final production/year screenshot was recaptured from that build.
- Python regression suite: 255 tests passed in 7.350 seconds. No Python extraction code was changed by this GUI refresh.
- Java 11 compatibility rerun: 109 tests passed with the matching JavaFX dependency architecture; compiled application classes have major version 55. The native Apple Silicon UI uses JDK 17.
- Launch and packaging scripts passed `sh -n` syntax checks. A cached Maven distribution was found under `~/.m2/wrapper/dists/`; this is additional discovery after the earlier bounded Upgrade audit searches.

Logs are local: `/tmp/cinematicdx-gui-baseline.log`, `/tmp/cinematicdx-gui-tests.log`, `/tmp/cinematicdx-gui-package.log`, `/tmp/cinematicdx-gui-python-tests.log`. The native preview uses an isolated settings file; it does not overwrite the user's normal configuration.

The final native build log is `/tmp/cinematicdx-gui-package-final.log`; it also reports 109 passing Java tests. Source publication does not include either the generated runtime or these machine-local logs.

An additional Java 11 check initially forced ARM graphics artifacts into an x86 JDK and exposed an unnecessary toolkit-initialisation probe in worker status delivery. That failed log is preserved as `/tmp/cinematicdx-gui-java11-initial-failure.log`. Status delivery now queues through `Platform.runLater` without querying/initialising a missing toolkit. The corrected architecture rerun passed all 109 tests; its log is `/tmp/cinematicdx-gui-java11-final.log`.

## Actual UI interaction

The native app was operated through its accessibility surface and keyboard. Verified behaviours:

1. Fresh setup has no automatic source choice and disables opening until a source is selected.
2. Database and local-directory choices expose their respective controls. Merely selecting either choice does not open a connection or create a catalog.
3. Opening local mode with an empty directory field gives a visible error and remains on setup.
4. Opening the prepared local catalog loads 732 real metadata rows; no database service is used.
5. Searching `上甘岭` returns 1/732 and updates the selected-film information and its real local-video mapping.
6. Clearing filters restores 732 rows. Choosing 1956 gives 43 rows; adding the exact `长春电影制片厂` production label gives 15 rows. Both counts match an independent read of the preview CSV input.
7. A deliberately nonexistent literal search returns 0/732, displays the empty-result explanation and clears selected-film/media information.
8. Stable-key visibility toggles successfully. Existing column sorting/selection and source identification remain present.
9. Research records reports the actual availability of all three local evidence folders. The Upgrade action opens Finder at `upgrade_pilot_audit`, where the six audit Markdown files were observed.

Screenshots in `screenshots/` are actual native-window captures. The visible macOS capture indicator is part of the capture environment. The preview data are copies of basic metadata fields through the existing CSV workflow, not synthetic empirical findings; the original research JSON/Excel, videos and previously computed results were not modified. Media links point to existing files and do not copy media into the catalog.

## Scope and limits

No live MariaDB connection was made during visual verification. JDBC/local parity is covered by the executed H2/local contract tests; production-server settings, network authentication and platform-specific packaging outside this Mac were not manually tested. The optional Python worker's lifecycle is covered by existing tests; the GUI does not claim to run CV analysis through that placeholder worker. Research links open files/folders only.

An initial unbundled, sandboxed JavaFX 13 preview could not obtain a valid desktop screen; that attempt is not counted as a successful GUI run. The verified screenshots come from the subsequently built native app using the Apple Silicon runtime. No old screenshot or generated mock-up is substituted for the new interface.

Build output under `cinematic/target/`, local catalogs/configuration, videos, annotations and research caches are excluded from source publication. Previously tracked build outputs are removed from the Git index while retained locally. The repository carries the code, tests, scientific protocols, Upgrade audit and these visual-verification records.
