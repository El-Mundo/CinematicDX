# Pilot gap analysis

## Data update, 10 November 2026

The [current corpus release](../../research/quantitative_exploration/corpus_refresh/20261110/README.md) covers 454 videos. Three replacement sources have new measurements, with 451 unchanged-source measurements inherited through their original receipts. Digital-gray extraction succeeded for all 454 videos and retains 2,390,266 timestamped observations. Of the 732 metadata records, 278 lack a local video.

The audit below is the 26 October snapshot. Its corpus totals and studio statistics retain that date, while current tables and figures are available in the release above. The *Shang Gan Ling* manual reference and narrative pilot use the same source version as the original study.

The evidential baseline is not zero. A real analytical pilot and a qualified descriptive comparative extension already exist. No CRITICAL gap prevents presenting the bounded claims specified in [MINIMUM_PILOT_PLAN.md](MINIMUM_PILOT_PLAN.md). Stronger claims about complete shot censuses, narrative recognition, person distribution or historical causation would require substantial additional evidence. Absence of those capabilities is not a reason to rebuild the application before the Upgrade.

Readiness uses the audit categories; severity concerns the **immediate limited Upgrade pilot**, not the eventual dissertation. Evidence IDs refer to [the inventory](EVIDENCE_INVENTORY.md).

| Pilot requirement | Current evidence | Readiness | Missing elements | Severity | Smallest corrective action |
|---|---|---|---|---|---|
| A: identify real film and version | M2 manifest, original record, current full-video SHA; 1956 Changchun metadata | VERIFIED | Archival acquisition/transfer history unknown | MEDIUM | State recorded production metadata and unknown digital provenance; do not imply an authenticated historical print |
| A: technical temporal provenance | Original PTS/time base, 0.043s source offset, later complete EOF decoding | VERIFIED | Player-to-decoder frame-origin calibration unresolved | MEDIUM | Retain both frame-origin scenarios and timing sensitivity; avoid frame-exact narrative coincidence claims |
| A: define available corpus | 732 records; 454 paths/453 distinct linked versions; 279 missing | VERIFIED availability; PARTIAL identities | Most filename links not independently authenticated; missingness nonrandom | MEDIUM | Keep missing/identity flags and the duplicate correction; use one clearly bound primary film; qualify comparative extension |
| B: automatic segmentation outputs | Full M3 IDs, boundaries, interval starts/ends/durations and report | VERIFIED extraction | Not a complete verified shot census | MEDIUM | Label counts as automatic candidates/partition intervals; distinguish full-file execution from local accuracy |
| B: local human validation | 45 cuts/four graduals, 43/2/2 at ±0.08s, both scenarios | VERIFIED bounded test | No independent held-out/full-film/cross-film accuracy estimate | MEDIUM | Present existing scope and errors. The `heldout-luma-1800-1920` directory contains predictions, not a labelled accuracy test |
| B: complete gradual segmentation | Strict classical/TransNet interval tests fail; failures retained | PARTIAL implementation, unsuitable for complete intervals | Reliable full starts/ends and broader taxonomy | LOW | Exclude this capability from the core claim; use manual spans to protect the limited analysis, retain negative result |
| C: editing/sequence variables | Q01 intervals, run summaries, 1,999 conditional shuffles | VERIFIED numerical evidence | No demonstrated fine ordering beyond run structure | LOW | Report the negative comparison and run heterogeneity; do not claim metric montage or a universal rhythm law |
| C: version-relative gray organisation | Continuous measures, event windows and source/parameter challenges | VERIFIED extraction; interpretation PARTIAL | No historical photometric calibration | LOW | Call it digital gray change within a particular copy; no cross-copy absolute lighting inference |
| C: person distribution/shot scale | Haar trial and failure cases; external face study | PARTIAL | Validated CinematicDX method and task-specific reference | LOW | Omit from minimum pilot. Face count, character presence, face-box scale and shot scale remain distinct tasks |
| D: timeline and local change | Full-file M3 timeline; Q01 sequence and Q02 event timeline; corpus relative profiles | VERIFIED | A concise set of English captions/axes and clear units for presentation | MEDIUM | Reuse actual plots/tables; translate/re-export labels only if needed. State that relative position is not a narrative act |
| E: independent narrative reference | A original/reconciled events and direct user confirmation, ten internal onsets | VERIFIED availability; PARTIAL construct documentation | Explicit event-definition rationale; location/character/time fields largely blank; misused boundary-kind fields unresolved | HIGH | Document the existing labels as researcher-identified event shifts; disclose retrospective clarification and exclusions. Do not invent a prior codebook or demand reannotation |
| E: meaningful correspondence comparison | Q02/Q05 six event/cut controls, original-frame audit, sensitivities | VERIFIED exploratory pilot | Confirmatory independent material and richer confound control | MEDIUM | Present association under the existing restricted comparison; identify cut-proximity selection and overlap. Defer cross-film narrative confirmation |
| E: editing-rate/event correspondence | Original M4 ±30s has no matched estimate; narrow sensitivities sparse/mixed | VERIFIED unsuccessful design | Informative matched comparison for that particular question | LOW | Present failure as a design limitation, not a null association. Do not make it the headline result or launch another broad search |
| F: annotation reliability | One annotator's independence/completeness/confidence declarations | PARTIAL | Independent coder agreement and calibration of second-level event times | MEDIUM | State single-coder exploratory status, uncertainty and alternative event units; no invented agreement score |
| F: numerical reproducibility | Source/output receipts, saved replay, current hash checks and 255 tests | VERIFIED within stated local environment | Portable submission packet linking actual uncommitted code to selected data | HIGH | Assemble a small versioned/hash-bound packet and a root command list, excluding the original video; no database or architecture changes |
| F: controls support interpretation | Ordinary manual cuts, preserved offsets, same time-third; 3/5s and ±1s sensitivities | PARTIAL | Location, framing, pre-change tone and shared temporal dependence not fully controlled | MEDIUM | Explain the conditional estimand, effective sample of six onsets and E006/E010 exceptions; do not convert draw ranks into significance |
| G: film-studies argument | Quantitative correspondence, sequence-control contrast and counterexamples | PARTIAL | A compact passage-specific argument distinguishing device, function and interpretation | HIGH | Write two or three evidence-linked cases using existing event descriptions/frames, including a counterexample; mark function as interpretation |
| G/RQ2: institutional/historical context | Actual studio/year/type/source comparisons; personnel metadata | VERIFIED descriptive comparison; historical explanation UNVERIFIED | Archival/contextual evidence, collaboration network and causal design | LOW | Use as feasibility/selection evidence, not institutional determination; defer SNA and historical explanations |
| Delivery: separation of evidence versions | Final pointers, prior failures/revisions, actual model/cache differences recorded | PARTIAL presentation readiness | One Upgrade-facing canonical result set; some earlier narrative flags say generic alignment not ready | MEDIUM | Cite Q02's bounded runner rather than the generic CLI; explain legacy flags and freeze final locations in captions |
| Delivery: GUI/DB execution | Source-level parallel stores; independent Python success | PARTIAL Java verification | Current Java/Maven/UI rerun; live SQL contents unknown | LOW | Use Python for the empirical demonstration; postpone UI/database verification because it does not improve this pilot's inference |

## Claim-dependent critical blockers

These are not prerequisites of the recommended pilot, but become CRITICAL if the corresponding claim is asserted:

- **“All shots/transitions have been reliably counted.”** No complete-film transition reference or reliable gradual segmentation supports that statement. Use candidate labels instead.
- **“Characters/shot scale have been measured reliably in the Chinese corpus.”** The current proxy is rejected, and external FaceCluster results cannot fill this gap. Omit the claim.
- **“Narrative form has been recognised automatically or replicated across films.”** Only one independently annotated narrative excerpt supports correspondence analysis. Omit the claim.
- **“Institutions caused the observed style or political function.”** Descriptive studio association is insufficient. Reserve historical explanation for later evidence.

## Six Upgrade deliverables

| Deliverable | Can it be supplied now? | Existing basis | Remaining minimum |
|---|---|---|---|
| 1. Reproducible empirical demonstration | Yes, locally | M2/M3/Q protocols, inputs, outputs, saved replay; current CLI/tests/digest checks | Small canonical code/data packet and explicit external video requirement |
| 2. Quantitative results table | Yes | Q01 summaries, Q02 event/control CSV/NPZ, bounded validation; comparative L/C tables | Select a few rows and state denominators/units |
| 3. Temporal analysis figure | Yes | M3R full-file timeline; Q02 narrative timeline and six-event/control figure | Accurate caption and event-time uncertainty; optional English label export |
| 4. Film-level interpretation | Partly written already | Q01 run/order distinction; Q02 unequal event-associated gray changes; E010 | Passage-specific prose supported by existing annotation, without ideological inference |
| 5. Methodological validation | Yes, bounded | Hard-cut reference; failure cases; original-frame audit/replay; sensitivity results | Explain development-sample scope and distinguish engineering from measurement validation |
| 6. Feasibility/scalability | Yes, actually demonstrated | ~20.86s Q exploration with caches; ~8,161.6s L and ~21,098.8s C extraction | Keep different sampling/resolution/hardware costs separate; do not claim all inference scales equally |

The shortest route is therefore a disciplined presentation of existing evidence. New shot-scale models, more whole-corpus runs and database redesign have lower immediate research value than clarifying the current analytical claim.
