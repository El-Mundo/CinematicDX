# Traceable evidence inventory

## Data update, 10 November 2026

The [current corpus release](../../research/quantitative_exploration/corpus_refresh/20261110/README.md) covers 454 videos. Three replacement sources have new measurements, with 451 unchanged-source measurements inherited through their original receipts. Digital-gray extraction succeeded for all 454 videos and retains 2,390,266 timestamped observations. Of the 732 metadata records, 278 lack a local video.

The audit below is the 26 October snapshot. Its corpus totals and studio statistics retain that date, while current tables and figures are available in the release above. The *Shang Gan Ling* manual reference and narrative pilot use the same source version as the original study.

Inspected on 26 October 2026. VERIFIED means that the specified claim is supported, not that every downstream use is valid. PARTIAL denotes incomplete readiness; UNVERIFIED denotes an unconfirmed claim; ABSENT is limited to the stated searched scope; BLOCKED identifies an evaluation prevented by available resources. Research statuses such as PROVISIONAL/REJECTED in the original experiments describe method validity and are retained separately.

The inventory captures the pre-GUI-audit state. Subsequent Java build/test and native-window verification are recorded in [GUI verification](../gui/VERIFICATION.md); historical commit IDs below are not a claim that the later GUI/publication commit already existed during this inspection.

## Locations and inspection scope

Paths below are relative to the CinematicDX root unless explicitly external.

| ID | Canonical location |
|---|---|
| S | `analysis-python/cinematicdx/`, `analysis-python/tests/`, `research/quantitative_exploration/scripts/` |
| M2 | `research-local/m2/shang-gan-ling-20261025T202349Z/` |
| M3 | `research-local/m3/shang-gan-ling-full-luma-001/` |
| M3R | `research-local/m3/shang-gan-ling-full-report-001/` |
| A | `research-local/m4/human-annotation-intake-20261025T222517Z/user-confirmed-20261025T225631Z/` |
| P | `research-local/pilot-results/shang-gan-ling-150-750-20261025T225931Z/` |
| G | `research-local/gradual-pilot/experiment-20261025T233231Z/` |
| Q | `research-local/quantitative-exploration/round-20261026T001205Z/` |
| QR | `research-local/quantitative-exploration/replay-20261026-verification/` |
| L | `research-local/studio-luminance/corpus-20261026T083348Z/`, final tables in `analysis_final/` |
| C | `research-local/studio-editing/corpus-20261026T114911Z/`, final tables in `analysis/` |
| F | **External:** `/Users/caoshuangyuan/Desktop/Workspace/Python/Narrative Results/` |
| FC | **External:** `/Users/caoshuangyuan/Desktop/Workspace/Python/SimpleFaceClustering/` |
| D | **External:** `/Users/caoshuangyuan/Desktop/Workspace/Python/DirtyPilot/` |

The audit enumerated the repository roots, source/test files, dependencies, research records and output families; inspected relevant implementation functions and actual JSON/CSV/array contents; checked local branch/history refs; and checked current media availability and selected hashes. It did not read every binary database file, decode the corpus again, execute external notebooks, or claim a line-by-line review of every source. Sibling `CharacterSpace`/`SubmissionProject` and saved project locations were checked for related work; their presence does not establish CinematicDX results. No exact `FaceClusterDX` directory name was found in the inspected workspace inventory; the identifiable related code and study data are FC/F. No conclusion is made about unsearched machines or cloud storage.

## Component matrix

| Component | Purpose | Repository evidence | Actual execution evidence | Empirical output | Validation and scope | Status |
|---|---|---|---|---|---|---|
| Metadata inventory | Identify corpus entries | `ChineseSocialistFilms49-66.json`; `inventory.py` | JSON parsed now: 732 records/unique keys | Production/personnel and title/year fields | Record presence, not archival correctness or SQL row count | VERIFIED |
| Video availability/identity | Bind records to digital sources | `ingest.py`, `inventory.py`; L/C plans and `identity_overrides.json` | 453 current source states match C receipts; M2 video fully rehashed now | 454 paths, 453 distinct linked sources, 279 missing valid sources | Most links remain provisional filename matches; documented duplicate misnaming resolved separately | VERIFIED availability; PARTIAL identity/provenance |
| Source manifest/probing | Technical and version provenance | M2 `source_manifest.json`, `probe.json`, `timestamp_sample.json`, `run.json` | Current 542,116,030-byte video SHA matches manifest | H.264/852×656, stream 0, original start 0.043s, 1/16000 time base | Header probe flags were bounded; later M3/C establish EOF decoding, not historical authenticity | VERIFIED |
| Automatic segmentation | Candidate partition and timestamps | `shots.py`, M3 `shots.json`, `shots.csv`, `boundaries.csv`, `run.json` | 185,825 frames, EOF coverage 7,434.006s; C preflight full-film regression | 934 candidates, 935 partition intervals with IDs/durations | All 935 initially unreviewed; gradual omissions prevent true-shot census | VERIFIED extraction; PARTIAL shot truth |
| Shot statistics/timeline | Distribution and local rate | `reports.py`; M3R `summary.json`, `local_cutting_rate.csv`, `timeline.png/.pdf` | Tables read and actual figure viewed | Automatic mean 7.9508s, median 3.32s; 60s windows/15s steps | Same segmentation supplies durations and rates; not independent findings or metric montage | VERIFIED |
| Independent annotation intake | Human boundaries and events | Original Excel under `outputs/01a17483-82c6-7510-8251-931dcb5d21d8/`; intake `raw_cells.json`; A narrative JSON and `user_confirmation.json` | Exact workbook/protocol hashes checked; reconciled records and confirmation inspected | 45 cuts, four gradual spans, 11 events over 150–750s | Independence/completeness are the annotator's declarations; second-level event precision; boundary-kind misunderstanding retained | VERIFIED availability; PARTIAL annotation reliability |
| Hard-cut validation | One-to-one detection evaluation | `validation.py`; P manual scenarios; delivered `M3_validation_sensitivity.csv`; C `preflight/results.json` | Actual matched counts inspected; tests run now | 43/2/2 at ±0.08s, both origins; tolerance/threshold variants saved | Known development excerpt, not held-out/full-corpus accuracy; player origin unresolved | VERIFIED bounded evaluation |
| Original M4 cutting/event comparison | Test local editing changes around events | `pilot_compare.py`; delivered `M4_comparison.json`, `M4_design_summaries.csv` | Primary rows read: no identifiable matched comparison at ±30s | Missing contrasts retained; narrower sensitivities have sparse/mixed results | Not evidence of no narrative relationship | VERIFIED negative/design-limited result |
| Q01 interval organisation | Separate aggregate/run/order effects | `exploration.py`; Q `Q01_editing/results.json`, `usable_intervals.csv`, `summary.csv`, controls NPZ | Saved numerical audit and 16-pair replay checked; raw summary read | 41 intervals; 0.7788 observed adjacent log change vs 0.8568 shuffle median | Within-run controls do not support exceptional fine ordering; global shuffle is weaker | VERIFIED experiment; PARTIAL generalisation |
| Q02/Q05 gray/event correspondence | Relate visual reorganisation to independent event onsets | Q `protocol.json`, `Q02_timeline/` and `Q05_challenges/` | Six-event mean and 1,999-control median recalculated now; narrative and comparison figures viewed | 0.101233 vs 0.018460; frame-exact controls, leave-one-out/digital/timing variants; E006/E010 heterogeneity | Uses manual cuts for control selection. Overlapping windows, restricted pools, known development sample; not p-values, CIs or event recognition | VERIFIED empirical analytical pilot; interpretation PARTIAL |
| Visual activity | Compare cheap changes and flow | `exploration.py`; Q frame-pair CSV/results | Actual 1,499/1,427 pair counts and prior audit inspected | Correlation-change/flow rank correlation 0.932; only 4/10 event windows adequately supported | No human motion truth; event comparison incomplete, not camera classification | PARTIAL |
| Low-level recurrence | Retrieve similar configurations | Q `Q03_recurrence/`, DCT/dHash code | 144 representative images/48 intervals and saved assistant review | Representative-choice stability and false matches retained | No independent motif/location/identity truth; event-proxy pairs share shots | PARTIAL |
| Haar face/person/scale proxy | Trial of spatial prominence measurement | Q `Q04_face_proxy/`, model configuration in protocol | 144-image outputs and reviews inspected; current OpenCV dependency available | 79 zero-detection images; 31 parameter-sensitive counts | Negative examples reject use as person count/shot scale; no independent task accuracy | VERIFIED negative test; proposed proxy unsuitable |
| Classical gradual candidates | Test complete gradual intervals | `gradual.py`, `transition_validation.py`; G comparison/report files | Frozen configs, predictions and strict results inspected | Default 0/91/4 at tIoU≥0.5 | Local negative result; no all-transition taxonomy, no reliable complete intervals | VERIFIED failed experiment |
| TransNet V2 comparator | Compare a fixed pretrained method | G runner/protocol, pinned official source and six files | All six model/source file hashes checked now; saved scores/predictions/results and runtime receipt exist | Strict 0/3/4; tIoU≥0.3 gives 3/0/1; ~160s for 15,248 frames | Not rerun: TensorFlow absent in `.venv-m3`; recorded system runtime separate. Output is not fade/dissolve classification | VERIFIED past empirical output; current inference BLOCKED in audited venv |
| Corpus digital-gray analysis | Comparative organisation/scalability | `corpus_luminance.py`, `corpus_studio_analysis.py`; L plans, sampling validation, final tables/audit | 454-file extraction receipts, 453-film final summary and validation inspected | 2,380,794 unique-source samples; studio/scale/type/year/ROI curves/tables | 24/24 fixed-clip sampling-agreement checks; original keyframe-only failure retained; not historical photometry | VERIFIED comparative extraction; interpretation PARTIAL |
| Corpus editing analysis | Compare timestamped cut candidates | `corpus_editing.py`, `editing_comparison.py`; C receipts, tables, QA and audit | 453 current source states, 15 stage hashes, 492 aggregate outputs checked now | 59,478,844 frames; 194,243 main cuts; 252,711 default gradual candidates | Exact arithmetic/provenance, parameter/ROI/type/edge sensitivities; local-only human accuracy reference. Gradual count not truth | VERIFIED comparative candidate analysis; interpretation PARTIAL |
| Narrative/character annotation beyond excerpt | Cross-film/whole-film interpretation | Search of CinematicDX annotation/output families | Only the named 600s human narrative reference found; empty templates distinguished | No verified multi-film event reference | No automatic predictions counted as independent narrative labels | ABSENT within inspected CinematicDX scope |
| Validated person distribution/shot scale | Spatial-form measurement | Face trial and external precedent inspected | No acceptable CinematicDX person/shot-scale validation output found | Current Haar proxy explicitly rejected | Cannot substitute external character data or face size for shot scale | ABSENT as a validated CinematicDX capability |
| SNA and historical linkage | RQ2 relations | Personnel/studio metadata exist; Python modules/outputs searched | No CinematicDX network construction/analysis run found | No verified CV–network association result | Metadata fields do not establish a network experiment or causality | ABSENT in inspected CinematicDX; not Upgrade-critical |
| Java metadata stores/setup | Storage independence and editing | `MetadataStore`, JDBC/local stores, factory/setup service, FXML and tests | Static inspection; 57 main/6 test class files exist, not proof of current test success | No research measurements arise from setup/login | No Maven found in bounded searches; no Java/UI rerun | VERIFIED source presence; execution UNVERIFIED |
| Database contents | Assess live relational corpus | SQL in `FilmRepository.java`; `database/` storage tree | No live connection or logical table dump inspected | Actual film rows unknown | Server inspection unnecessary for pilot; no migration/start performed | UNVERIFIED |
| Worker | Optional process lifecycle | `analysis-python/worker.py`, Java manager | Source inspected; worker just sleeps until signal | No CV measurements | Do not count it as a film-analysis implementation | VERIFIED placeholder functionality |
| Tests | Engineering consistency | 20 Python test files; Java test sources | Python suite executed now, 255 pass, 7.411s, no skips | Fixtures and temporary synthetic videos, not film evidence | Human and real-film findings evaluated separately | VERIFIED Python execution; Java UNVERIFIED |
| Face-clustering precedent | Reuse adjudication/role/presence methodology | FC source/demo/PDE; F README/notebooks/metrics | Saved executed notebook cells, manual CSV and derived tables inspected, not rerun | 16 film CSVs; 432 rows each in primary temporal/face-height tables; 2,382-row Gilda adjudication CSV | Edition provenance explicitly incomplete; old extraction uses OpenCV sampled seek. DeepFace/MTCNN absent in current venv | VERIFIED accessible external evidence; PARTIAL reuse readiness |
| Older shot/TransNet exploration | Locate earlier claims | D notebooks, four CSVs each in shot and TransNet output folders; montage candidate exports | Executed cells exist; TransNet notebook also records KeyboardInterrupt | Outputs indicate prior experiments but lack equivalent audited version binding here | Not automatically imported, no montage principle validated by filenames | PARTIAL; not counted as CinematicDX completion |

## Face-clustering precedent: precise reuse boundary

F README identifies the study as “On Face Clustering in Digital Humanities: Love Triangle, Character Space, and Ideology in Postwar Film Narratives”. Its sixteen per-film CSVs and primary tables are accessible; the tables explicitly distinguish focal-character detection shares from conditional face-box height and mark missing sizes differently from zero presence. `gilda_c3_validation.ipynb` has saved outputs separating retention recall, end-to-end recall and final named-identity accuracy. The saved all-visible recall is much lower than named-identity accuracy, an important methodological precedent rather than a transferable performance claim. Role-coder comparison notebooks and sensitivity files also exist. Their metrics were not independently rerun in this audit.

Local repository identities are FC origin `github.com/El-Mundo/SimpleFaceClustering.git`, HEAD `1a8bea1474f4210b711d64513ef7f997c9e73a67`, and F origin `github.com/El-Mundo/Narrative-Results.git`, HEAD `810b638416bf956a736b6dec708484c7b3d00c9d`. These establish which accessible code/data were inspected; they do not independently establish that the precise label “FaceClusterDX” denotes a third repository or that its complete environment is available. F has an already modified tracked Python cache, so HEAD is an identifier rather than an assertion of a wholly clean checkout. No external notebook/module was executed.

Reusable ideas include manual identity adjudication, explicit eligibility denominators, conditional size measures, zero-versus-missing handling, normalised temporal bins, role-code sensitivity and error provenance. Reusing the extraction requires checking its runtime/weights and timestamp semantics: FC uses sampled OpenCV seeking and an index tied to the sampling interval, not the current CinematicDX source-PTS contract. Its old interactive t-SNE/clustering decisions need validation rather than direct adoption. No film video or result was copied into CinematicDX; no external face measurement is counted as Chinese-corpus evidence.

## Audit commands and verification notes

Executed from repository root:

```sh
git status --short
git branch --all
git log -8 --oneline
git rev-parse HEAD master origin/master
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python \
  .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v
PYTHONDONTWRITEBYTECODE=1 .venv-m3/bin/python \
  analysis-python/cinematicdx_cli.py --help
```

The suite log is `/tmp/cinematicdx-upgrade-audit-python-tests.log`, SHA-256 `6708bad6308a6bbbe9746eec74ff05ffaaee78abe454174e69b3a95cba176a12`; its observed terminal summary was `Ran 255 tests in 7.411s`, `OK`. This is a new executed check, not a repeated claim from an old report. The log and `/tmp/cinematicdx-upgrade-audit-checks.json` are temporary audit aids; preserve them with any later handover packet if needed.

Read-only digest checks at 18:05:31 UTC verified 177 Q initial output files, six Q protocol inputs, 16 paired Q/QR artifacts, all 453 current source states, 15 C stage artifacts, 492 C aggregate files and six pinned TransNet files. The current complete *Shang Gan Ling* digest matches the version above. Source state checks for the other 452 films are not fresh whole-video rehashes. No cached extraction was rerun or overwritten.

A subsequent read-only check matched all 39 L final aggregate output hashes and counted 454 current non-hidden MP4 paths in the actual external directory. The larger comparative evidence is therefore supported by inspected tables/arrays and receipts, not just statements in the research log.

Independent simple table/array checks recovered the six-event mean 0.10123300385086971 and control median 0.018460209085302947. E006=0.0465125 lies within its stored 0.0025248–0.1284771 conditional control range; E010=0.0040458 is below its control median 0.0126779. These are descriptive ranges, not confidence intervals. Existing original-frame integration checks and saved replay receipts support arithmetic/reproducibility, not new independent film replication.

Historical intermediate runs remain visible: L `analysis/` and `analysis_revision2/` precede `analysis_final/`; C retains initial failures, separate effective completion, seek failures and roundoff recovery. Use canonical final locations above. Do not silently combine numbers from earlier versions or old cache resolutions.
