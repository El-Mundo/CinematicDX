# Minimum Defensible Upgrade Pilot

## Decision and scope

Use **one complete digital film for extraction/context, with an independently annotated ten-minute analytical case**. This adapts the preferred pipeline to evidence already available; it does not pretend that the complete film has narrative annotation or verified complete shot segmentation. The central experiment has already run. The remaining work is limited interpretation and delivery, not a new CV system.

**Question:** In the existing independently identified event shifts of *Shang Gan Ling*, do local changes in digital gray organisation exceed changes around ordinary hard cuts under an explicit comparison design, and what do exceptions reveal about the limits of a low-level visual account? A second question asks whether observed shot-interval order contains information beyond aggregate and run-specific duration distributions.

This concerns relations between measured properties and annotated organisation. It does not equate gray change with narrative function, shot statistics with metric montage, or file-wide averages with film form.

## Specification grounded in existing data

| Element | Minimum specification | Existing evidence / limitation |
|---|---|---|
| Film | *Shang Gan Ling* (上甘岭), production metadata 1956, Changchun | Stable key `shang gan ling`; production context recorded, archival source history unknown |
| Digital version | SHA-256 `a044ce2cd1b561bf2599f21b5415163e01f7abdd6313919ac1f8ed5e9657d9f0` | Rehashed in this audit; original 852×656 H.264, 7,434.006s decoded coverage |
| Full-film layer | Candidate segmentation and local editing timeline over the complete file | 934 candidates/935 automatic intervals; no claim of a true shot census |
| Analytical layer | `[150,750)` playback seconds; retain source PTS and 0.043s source offset | Only this 600s has independent narrative/cut reference |
| Primary unit | Independent event onset, six eligible hard-cut-associated onsets | Not frames, control draws or hundreds of films; ten internal onsets described separately |
| Secondary unit | Complete two-manual-cut-bounded intervals excluding annotated gradual intersections | 41 intervals, four runs; excluded/edge intervals kept separately |
| Narrative reference | Original/reconciled 11 event records, single human annotator, explicit independence/completeness declaration | E001 starts at observation edge; E011 right-censored; event times approximately one second; boundary-kind fields excluded |
| Image procedure | Existing annotation-blind gray extraction, fixed 5% side/10% top-bottom ROI, original-frame support, exposure-weighted bins | Digital gray mean on 0–1 scale, not recovered historical luminance; cache and receipt bound in Q protocol |
| Primary variable | Absolute difference of ROI gray means over `[t−5,t−1)` and `[t+1,t+5)` | Central exclusion avoids treating one transition frame as the whole comparison; onset is not snapped to a cut |
| Controls | Ordinary manually referenced hard cuts in the same time-third, outside event/gradual neighbourhoods; preserve event-to-cut offset | Sampling without cut reuse per draw; overlapping windows allowed; 1,999 dependent assignments, seed 20261026 |
| Editing variable | Mean absolute adjacent log-duration change within gradual-separated runs | 1,999 within-run shuffles preserve relevant duration distributions; global shuffle retained as a weaker challenge |
| Validation | Manual cut matching at saved tolerance range; two frame-origin scenarios; error examples; exact-PTS arithmetic and saved independent implementation | Development sample only; no arbitrary new accuracy target or false inter-coder claim |
| Robustness | Existing ±1s timing shift; 3/5s windows; ROI/full image; sampled gray/gamma/JPEG/crop; leave-one-event-out; original-frame control integration | Ten-second matched design lacks support; controlled distortions are mechanism tests, not historical transfer truth |

Evidence roots and filenames are defined in [the inventory](EVIDENCE_INVENTORY.md). No new annotation is required to make these **limited exploratory** claims. The researcher has explicitly declined further viewing/reannotation of the ten-minute passage; that decision is preserved. A later independent replication is a separate study, not a hidden completion requirement.

## Results that already exist

| Existing result | Defensible reading |
|---|---|
| Six-onset gray change 0.101233; matched-assignment median 0.018460, descriptive 2.5–97.5% range 0.010977–0.037355 | Association within this source, annotation and restricted control design; not a population confidence interval or causal effect |
| Exact original-frame integration control median 0.018576; maximum fixed-pool assignment mean 0.042148 | One-second bins/random assignment sampling do not account for the observed difference within that fixed pool; the pool itself remains a substantive assumption |
| E006 0.046513 inside its broad control range; E010 0.004046 below its control median | An event need not show a distinctive brightness change; aggregate contrast conceals heterogeneity |
| 41 eligible interval mean 8.945s; observed adjacent-log change 0.7788 vs conditional median 0.8568 | Run/segment differences matter, but fine order is not exceptional under the stronger baseline |
| 43/2/2 manual cut matching at ±0.08s, both frame-origin scenarios | Bounded internal detection feasibility, not full-film accuracy |
| Strict gradual test fails; person/scale proxy unsuitable | Transparent method rejection prevents those outputs contaminating the interpretation |

Suggested interpretive cases are E007 (cook interrupts), E009 (renewed discussion/telephone interruption) and E010 (cook interrupts again), as described in the original annotation. E011 includes leaving the earlier setting and a diary conversation. Unequal gray changes across these labels motivate an investigation of framing, visible space and device function. **Those functions are not established by the numbers**; use existing representative frames/annotation for carefully qualified prose. Do not infer a new event taxonomy from peaks or silently recode the original labels.

## Outputs and completion criteria

The Upgrade packet should contain:

1. A source/technical table and complete-file candidate timeline, clearly separated from the annotated excerpt.
2. A six-event table with actual onset, label, gray change, control summary and an exception; existing Q02/Q05 data supply it.
3. The existing event/gray timeline and six-event conditional-control figure, with appropriate captions.
4. A small interval-order table/figure showing the stronger and weaker baseline distinction.
5. A local validation table and representative failure discussion, retaining gradual and face-proxy failures.
6. A short reproducibility appendix: input hashes, protocol/source snapshot identifiers, current test command, saved replay comparison, runtime and external source requirements.

Call this pilot sufficiently complete when every displayed number is traceable; automatic intervals are never silently relabelled true shots; the six-onset estimand and conditional controls are explained; uncertainty and E006/E010 are visible; a passage-specific interpretation distinguishes observation from hypothesis; and another researcher can inspect/replay the selected analysis with the same permitted source. No new accuracy threshold is warranted from the current small reference. Most empirical criteria are met already; final narrative argument, selection and packaging remain.

## Optional comparative supplement, not a prerequisite

The existing 453-film digital-gray extension already supplies a qualified comparative pilot. Prefer one compact within-film-normalised studio/scale comparison with sample sizes and IQRs over a large ranking exercise. Describe nonrandom missingness, transfer histories, metadata uncertainty and scale sensitivity. No new processing is needed.

If a two-film illustration is preferable, existing C rows provide *Shang Gan Ling* and *Guo Qing Shi Dian Zhong* (国庆十点钟), both recorded as 1956 Changchun black-and-white features: 934 candidates/7,434.006s/7.538 per minute versus 627/5,566.759s/6.758 per minute. The latter source version is `sha256:939b4320454481f4aef010e5b7ef8a106c69073c3e77abd71c3e3978de81fffd`. These are actual candidate measurements, not validated shot rates or a narrative replication. Same year/studio/type does not control genre, content or source differences; the second identity link still requires appropriate qualification. This supplement cannot establish an institutional effect.

## Stop rule

Do not add new models or optimise failed methods merely to increase the number of results. Stop preparation once the bounded empirical argument and traceable packet are coherent. Broader narrative confirmation, person/scale methods, historical explanation and CV–SNA integration belong to the later programme.
