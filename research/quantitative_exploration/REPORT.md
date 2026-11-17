# CinematicDX: quantitative evidence exploration report

Date: 2026-10-26. Working branch: `codex/quantitative-evidence-20261026`. This round completed five new experiments/challenges and assessed six candidates, meeting evidence-based stopping conditions.

The most useful new finding is that **digital brightness changes near this film's existing human-annotated events remain larger under conditional controls using ordinary hard cuts, warranting further validation.** This is not an automatic narrative recogniser and does not establish causation between film form and political context.

## Material, independence and scope

- 《上甘岭》(1956), `research-inventory:shang gan ling`, video version `sha256:a044ce2cd1b561bf2599f21b5415163e01f7abdd6313919ac1f8ed5e9657d9f0`. The actual file is on a local external drive, and its complete SHA was recalculated. Original provenance/transfer history remain unknown.
- The sole analysis interval is playback offset `[150,750)`, lasting 600 seconds. No other film is analysed. Existing per-frame caches were reused, with only 144 additional representative images decoded within the same interval, without expanding the 30-minute limit.
- Existing M2 records show successful header probes for 454 video candidates. This is an earlier inventory, not validation of 454 independent films, and this round did not rescan the whole corpus.
- Existing independent human references comprise 45 hard cuts, 4 gradual intervals and 11 events, including 10 onsets inside the interval. Narrative times retain their original second-level precision. E001 at the left edge is not a new event, and E011 has no actual end time and is observed only to 750 seconds.
- QuickTime frame numbers have not been independently calibrated against decoding order. Primary cut-based controls retain both 0/1 numbering conventions without choosing whichever fits best. Representative-frame sampling uses the 0-based scenario with this limitation explicitly retained.
- Original video, Excel, existing annotations and failed gradual-transition results are unchanged. No new models/data were downloaded, trained or uploaded. No database operations or paid services were used.
- New procedures were frozen before this round's outputs, but the annotation interval was already known. The whole round is therefore internal exploration, rather than blind testing or preregistered confirmation.

## Conclusions for the six candidates

| Property | Theoretical motivation | Implemented? | Experimental evidence | Reliability | Cost in this round | Narrative relevance | Recommendation |
|---|---|---|---|---|---|---|---|
| Hard-cut durations and ordering | Repetition, contrast and rhythm distribution beyond whole-film means | Yes, Q01 | 41 complete hard-cut intervals; 37 valid adjacent relations; 1999 blockwise permutations | Timing table and arithmetic checked; ordering claims PROVISIONAL | About 0.63 seconds using existing references | Can align with events; does not establish narrative, attention or metric montage | Retain as core; store intervals, sequences and truncation together |
| Digital grayscale mean and contrast | Brightness contrast and its organisation along the timeline | Yes, Q02/Q05 | Mean change 0.1012 for six cut-associated events versus control median 0.0185; retained across several challenges | Extraction VERIFIED; narrative correspondence PROVISIONAL | About 2.9 seconds including activity/controls, using cached data | Strongest exploratory lead in this round; E010 counterexample retained | Retain as core, restricted to the same digital version |
| Image-activity proxies | Motion/change distributions and relations with editing | Yes, Q02 | 1499 frame pairs, 1427 valid; correlation difference and optical-flow rank correlation 0.932; only 4/10 event windows sufficiently complete | PROVISIONAL, with no true motion labels; camera-movement classification unvalidated | Optical flow about 0.83 seconds at 64×48 and 2.5Hz | Missingness blocks existing narrow-window controls | First retain inexpensive correlation and quality flags; preserve optical flow for research |
| Configuration similarity | Visual returns, repetition and contrast | Yes, Q03 | 48 intervals × 3 representative frames; only 5/7 DCT top10 pairs retained after frame replacement; smoke/battlefield mismatches | PROVISIONAL; qualitative assistant inspection is not human ground truth | Lightweight descriptors; decoding 144 larger representative images about 12.93 seconds | Same-event proxy results vary by temporal gap | Retain as retrieval support without upgrading to motif/location recognition |
| Frontal-face box sizes/counts | Candidate proxies for characters' spatial salience | Yes, Q04 | Zero detections in 79 of 144 images; counts change with parameters in 31 images; torso false boxes and missed profiles | REJECTED: current configuration unsuitable for person-count/shot-scale proxies; original boxes remain predictions | About 3.14 seconds for both settings, using an existing model | Boxes cannot establish character configuration or character attention | Exclude from core measurements; future use requires independent box/shot-scale references |
| Complete gradual start/end intervals | Organisation of editing transitions | Existing G00, not rerun here | Primary tIoU≥0.5: rule-based 0/91/4, frozen pretrained 0/3/4 | REJECTED: automatic complete segmentation with these configurations | 0 inference runs this round | Errors would contaminate duration/event-boundary analysis | Keep candidates and human intervals separate; do not automatically merge into shot tables |

These statuses address stated uses. Reproducible numbers do not validate film-theoretical interpretation. Timings reflect reduced-resolution images/existing caches on this machine and cannot directly budget original-resolution full-corpus processing. The four initial real-material experiments took about 20.86 seconds overall; reporting, testing and reading are additional.

## Q01: information in ordering beyond means

The conservative analysis includes only 41 intervals bounded by hard cuts at both ends and crossing no gradual transition, totalling 366.763 seconds, with mean 8.945 seconds and median 4.960 seconds. **These are not average shot lengths for the complete 600-second interval or the whole film.** Other ranges are excluded from this complete-interval analysis because of adjacent gradual transitions, observation edges or related reasons.

The four consecutive usable blocks contain 6/1/7/27 intervals, with within-block means of about 1.280/29.640/6.006/10.645 seconds. A single overall mean hides these distinct rhythm regions, giving sequences and positions descriptive value.

The primary statistic, mean absolute adjacent log-duration difference, is 0.7788. Permutations retaining each block's duration distribution and total duration have median 0.8568 and a conditional 2.5%–97.5% range of 0.7060–1.0017. The observed value lies around the 14.5% position in the conditional reference and is not exceptional. Adjacent log-duration correlation is 0.4931, but within-block permutations already have median 0.4010. Positive correlation alone therefore cannot establish a fine-sequence principle.

The later, weaker global permutation preserves the overall histogram but mixes durations from different blocks. Its primary-statistic median rises to 1.2147, making the original ordering appear highly exceptional. **The controls answer different questions: rhythm differences between passages do not establish additional ordering within passages.** This is an important negative/boundary finding from this round. No 1/f fitting, audience-attention measurement or montage classification was performed.

## Q02/Q05: the most promising narrative lead

Digital grayscale is weighted by actual exposure from original PTS. The primary comparison is the absolute difference between means in `[−5,−1)` seconds before and `[+1,+5)` seconds after an event onset. Onsets are not snapped to cuts.

Mean change across all 10 onsets is 0.1693, versus median 0.0449 for 469 valid configurations generated by jointly shifting the event group. This weaker control mixes transition and non-transition conditions, so it cannot establish narrative correspondence on its own.

The more specific control includes 6 events, E006–E011, with a hard cut within 1 second and no neighbouring human-annotated gradual transition. They are matched to non-event hard cuts in the same temporal third, retaining onset-to-cut offsets without reusing cuts within a draw. Windows may overlap, and independent-sample inference is explicitly excluded. Results:

- Mean absolute event change **0.101233**; median of 1999 control groups **0.018460**, with conditional 2.5%–97.5% range **0.010977–0.037355**.
- After recalculating every sub-second control using original-PTS frame integration, the median is **0.018576**. The maximum possible control mean under the stated pools and no-reuse rule is **0.042148**. The gap therefore does not arise from 1-second binning or random sampling missing extreme configurations.
- Leaving out one event at a time gives remaining means of **0.086620–0.120670**, each above its corresponding conditional control upper bound. No single event explains the result.
- The direction remains under 3-second/5-second windows, joint onset shifts of ±1 second, full-frame/ROI comparisons, a 1Hz approximation, gamma0.8/1.2, JPEG40 and narrower crops. The 10-second hard-cut matched pools are insufficient and explicitly BLOCKED, rather than labelled as no effect.
- Grayscale standard deviation also differs conditionally, but it relates to the mean and scene/composition changes and cannot count as a second independent piece of narrative evidence.

Counterexamples remain: E010 near 726 seconds changes by only about **0.0040**, so clear brightness change does not accompany every event. Changes for the other six-event observations are recorded individually in figures and CSV.

**Supported claim:** Under this independent event table and the fixed controls, reproducible local correspondence with brightness reorganisation exists in this film. Its relations with composition, character configuration, location changes and editing warrant further research.

**Unsupported claims:** Narrative uniquely causes the changes, events can be recognised automatically, or the result is a general rule for Chinese political cinema. Controls do not match shot scale, character configuration, location or all non-stationarity. Event definitions may themselves draw on visible transitions. Digital grayscale is not historical cinematographic lighting ground truth, conditional sampling ranges are not confidence intervals, and empirical ranks are not directly publishable p-values.

## Q02 activity proxies: inexpensive methods already capture most coarse information

Of 1499 frame pairs about 0.4 seconds apart, 1427 are valid. 72 are flagged for crossing a cut/gradual transition or low texture, with categories permitted to overlap. Pixel differences and optical-flow p90 have rank correlation 0.8956, while `1−pixel correlation` and flow have correlation 0.9323. At the current coarse resolution, flow has not shown sufficient independent benefit and cannot yet distinguish camera from character motion.

Measurement-mechanism perturbations of real images show that adding 10 grayscale levels to the same frame gives median difference about 0.0392 while correlation difference stays near 0. A one-pixel translation substantially raises both measures and flow. Flow has a numerical floor even for identical frames. **These are controlled perturbations, not ground truth for actual film exposure changes or film jitter.** Global translation alone cannot distinguish panning from an unstable copy.

Under the strict 95% valid-exposure condition, only 4/10 events have complete activity measurements in the primary windows. A whole-group comparison is therefore impossible and remains missing. The threshold is not relaxed after the fact to rescue a result. Activity controls are currently BLOCKED by missingness, while the method remains PROVISIONAL.

## Q03: retrieval value without established semantic capability

Each of 48 complete continuous-content intervals contributes frames at 1/4, 1/2 and 3/4, giving 144 representative images. Low-frequency DCT without DC, dHash and brightness-only distance are compared in parallel. Among non-adjacent top10 pairs, DCT retains 5/7 pairs when replacing the representative with the 1/4 or 3/4 frame; dHash retains 5 in each case, and brightness-only distance retains 0/2. Spatial-configuration descriptors therefore contain information beyond mean brightness, while single-frame representation remains unstable.

Assistant inspection of the first 8 DCT pairs found several returns of similar single-/two-person compositions and clear mismatches, including smoke and terrain containing several people that share only low-frequency patterns. Observations are labelled as assistant inspections. There is no human retrieval ground truth, so precision is not reported.

Using independent event membership as a proxy and stratifying temporal gaps into 20-second bins, DCT/dHash/brightness-only AUC is about 0.707/0.696/0.363 at 20–40 seconds and 0.671/0.786/0.330 at 40–60 seconds. However, the brightness baseline is higher at 0–20 seconds, results are unstable beyond 60 seconds, and farther strata contain only 1–2 same-event pairs. **Every stratum is retained. Two favourable strata cannot establish general narrative retrieval, still less character, location or motif recognition.** Pairs share shots and cannot count as independent samples.

## Q04: rejection of the current person-count/shot-scale proxy

The installed Haar frontal-face model was tested with two parameter settings on 144 representative images. The primary setting produces zero detections in 79 images and 87 boxes in total. Changing minNeighbors changes face counts for 31/144 images (21.5%).

Assistant observations were recorded for a fixed set of 12 unboxed images before inspecting boxes. They show zero boxes for a two-person profile image, only one box in a two-person image, separate face/torso boxes for one person, and oversized boxes covering torso/background. Current model outputs are therefore unsuitable as person-count, group-composition or shot-scale data. **Without independent human box/shot-scale annotations, accuracy cannot be reported for those tasks.** Original predictions and counterexamples remain preserved despite rejection of the use.

Blank CSV sheets for future independent review contain 12 images and 8 randomly sampled pairs. Human fields remain blank and separate from assistant notes. The researcher is not being asked to rewatch or reannotate now.

## Minimum defensible combination and four levels of interpretation

1. **Property description:** Source version/original PTS/quality flags; hard-cut times checked against independent references; conservative duration sequences; fixed-ROI digital grayscale means and standard deviations. These are auditable and lightweight.
2. **Visual organisation:** Preserve individual ordering, local changes and cross-interval contrasts, with controls retaining appropriate structure. Low-frequency similarity supports retrieval only; numerical measures are not directly labelled as principles of form.
3. **Visual–narrative correspondence:** An independent event layer with narrow windows, ordinary-cut conditional controls, temporal uncertainty and missingness handling. Brightness is this round's strongest candidate, but the association remains PROVISIONAL.
4. **Corpus and historical interpretation:** No cross-film/cross-version validation or production-relations analysis is available at this stage. Period/institutional/political rules cannot be inferred. Later work requires source stratification, independent material, extraction validation and historical research. SNA was not implemented in this round.

Correlation-based activity proxies may be added in a second stage after resolving valid exposure near transitions. Optical flow, person counts, shot-scale classes, automatic motifs and complete gradual segmentation are excluded from the current core.

## Strongest next experiment

Freeze this brightness operational definition and test in independent material whether brightness reorganisation near narrative events exceeds ordinary editing. Subdivide references into location changes, character-configuration changes, action-goal changes and related categories, without deriving labels from image curves. Compare finer matching for shot scale/preceding brightness, retaining events without visual cues and non-events with visual changes. New independent references are required for a confirmatory test. This round neither asks the user for additional annotations nor presents that unexecuted step as complete.

## Reproduction, cost and stopping

Code is in this directory's `scripts/` and `analysis-python/cinematicdx/exploration.py`. The frozen protocol, cache bindings, source snapshots, all negative cases, bins, per-frame pairs, controls and contact sheets are in the local-only run directory `research-local/quantitative-exploration/round-20261026T001205Z/`, which is excluded from this repository. Original video and annotation checksums match. PTS and actual intervals for all 144 representative images were individually checked, with maximum temporal deviation about 0.040 seconds.

All 225 Python tests passed, including 17 new tests of actual exposure, missingness, gradual gaps, controls, descriptors and mechanisms. They do not replace film evidence. A second numerical implementation checked 1999 blockwise permutations and original-frame integration, with maximum primary event-change difference about 5.9×10⁻¹⁴.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v

PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/cinematicdx-mpl .venv-m3/bin/python research/quantitative_exploration/scripts/replay.py --from-run research-local/quantitative-exploration/round-20261026T001205Z --output research-local/quantitative-exploration/replay-001
```

Recomputation uses the existing isolated environment and the same caches/original video. `replay-001` must be a new directory, and existing outputs are not overwritten. Paths can be substituted, but input hashes cannot be changed arbitrarily. There are no hidden database or model-download steps. Receipts record principal dependency versions, code checksums and the source file's complete SHA.

Six candidates have been assessed, four real-material experiments and one challenge/frame-integration audit completed, failures retained, and rankings and follow-up procedures documented. Further tuning on the same clip would not add independent validity, so this round stops here without expanding to the full corpus.

See [candidates](CANDIDATES.md), [experiment log](EXPERIMENTS.md), [ranking](METHOD_RANKING.md), [next steps](NEXT_STEPS.md) and [verified sources](BIBLIOGRAPHY.md).

## Complete replay acceptance

A complete replay with the same frozen protocol in a new directory produced byte-identical results for 16 core JSON/CSV/array files. Later challenge numbers match after excluding declared times. Counts, maximum areas and coordinate sets match across all 288 face-box rows, but 10 rows return boxes in different orders, so the raw CSV is not byte-identical. Both original outputs are preserved, and box order cannot represent person identity. The replay took about 20.29 seconds. The sole material remains the same 600 seconds, and requested decoding intervals across the initial round and replay total 1200 seconds, below the 1800-second limit. This verifies numerical reproducibility rather than replication on independent films. See `reproducibility_verification.json`.
