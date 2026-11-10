# Preliminary Pilot Study: Computational Extraction and Analysis of Cinematic Formal Properties

## Data update, 10 November 2026

The [current corpus release](../../research/quantitative_exploration/corpus_refresh/20261110/README.md) covers 454 videos. Three replacement sources have new measurements, with 451 unchanged-source measurements inherited through their original receipts. Digital-gray extraction succeeded for all 454 videos and retains 2,390,266 timestamped observations. Of the 732 metadata records, 278 lack a local video.

The audit below is the 26 October snapshot. Its corpus totals and studio statistics retain that date, while current tables and figures are available in the release above. The *Shang Gan Ling* manual reference and narrative pilot use the same source version as the original study.

This outline contains statements supported by inspected outputs. It can be adapted into the Upgrade Report; it is not a claim of official Upgrade compliance. Numerical details are traceable through [EVIDENCE_INVENTORY.md](EVIDENCE_INVENTORY.md). Proposed work and missing interpretive evidence are explicitly marked.

## 1. Aim and research question

The pilot investigates whether computational measurements can provide interpretable evidence about the temporal organisation of visual properties and their correspondence with independently identified narrative events. It distinguishes measurement of an isolable property from an account of film form. The immediate question is whether digital-gray reorganisation near researcher-identified event shifts differs from changes around ordinary hard cuts in the same passage. A related analysis asks whether the ordering of shot-bounded intervals contributes information beyond their overall and run-specific distributions.

This is an exploratory feasibility study. It does not test automatic narrative recognition, identify a historically specific montage principle, or infer political function from visual measurements.

## 2. Pilot corpus and data provenance

The primary case is *Shang Gan Ling* (上甘岭), recorded in the research inventory as a 1956 Changchun Film Studio production directed by Sha Meng and Lin Shan. The analysed H.264 file has 852×656 coded resolution and 7,434.006 seconds of decoded video coverage. Its identity is bound to inventory key `shang gan ling` and complete-file SHA-256 `a044ce2cd1b561bf2599f21b5415163e01f7abdd6313919ac1f8ed5e9657d9f0`. Acquisition and scan/restoration history are unknown. Technical reproducibility is therefore stronger than edition-level archival provenance.

Automatic candidate segmentation covers the complete file. The analytical and manual-validation case is restricted to playback 02:30–12:30, with independently supplied annotations of 11 narrative events, 45 hard cuts and four gradual transitions. There are ten event onsets inside the window; the initial observed boundary is excluded as a new event, and the final event continues beyond the observation window. Event times have approximately one-second precision. Both possible origins of the player's full-film frame numbering are retained.

The wider inventory contains 732 records and 454 available paths, corresponding to 453 distinct linked video versions after a documented duplicate/misnaming correction. This supplies a comparative feasibility extension, not 453 independent narrative replications.

## 3. Method and implementation

The analysis uses standalone Python modules, independent of the Java metadata application and MariaDB. Source manifests and run receipts preserve file digests, original presentation timestamps, time bases, parameters and software versions. Candidate hard cuts are obtained with an adaptive intensity-change baseline. The option named `luma-only` measures HSV V differences and is not a calibrated historical luminance measure. The complete-file output contains 934 candidate boundaries and 935 automatic partition intervals; these are not asserted to be a verified shot census.

For the local analytical case, gray measurements were extracted without reading the narrative labels. Fixed ROI measurements were mapped to actual frame exposure, then to one-second bins. The primary event statistic is the absolute difference between mean gray before and after each onset, using `[t−5,t−1)` and `[t+1,t+5)`. Event onsets are not snapped to shot boundaries. The six eligible onsets lie within one second of a manually annotated hard cut and outside the annotated gradual-transition neighbourhoods.

The comparison uses non-event manual hard cuts in the same time-third, preserving each event-to-cut offset and excluding event/gradual neighbourhoods. There are 1,999 control assignments with fixed seed 20261026 and no reuse of a cut within an assignment. Windows may overlap; the assignments are dependent reference configurations, not independent research observations. A separate duration-sequence experiment shuffles intervals within gradual-separated runs, preserving the duration distributions relevant to that question.

## 4. Measurements and validation

| Measurement/check | Actual result | Scope |
|---|---|---|
| Automatic complete-file partition | 934 candidate cuts; 935 intervals; mean interval 7.9508s, median 3.32s | Unreviewed automatic intervals, not validated true ASL |
| Manual hard-cut comparison, ±0.08s | TP=43, FP=2, FN=2; precision=recall=F1=0.9556 | Same known development excerpt; both frame-origin scenarios |
| Conservative manual interval subset | 41 intervals; mean 8.945s, median 4.960s; four runs | Omits edges and intervals intersecting annotated gradual spans; not full-film ASL |
| Default gradual interval localisation, tIoU≥0.5 | TP=0, FP=91, FN=4 | Rejects current complete-interval use in this passage |
| Saved pretrained TransNet V2 interval comparison | TP=0, FP=3, FN=4 at tIoU≥0.5 | Fixed comparator/interval conversion; no fade/dissolve classification claim |
| Reproducibility | 16 principal saved artifacts match a separate replay byte for byte | Same source/parameters, not external empirical replication |
| Current engineering checks | 255 Python tests passed in this audit | Fixtures and code consistency; not film-theoretical validation |

Original-frame integration reproduced the event changes to numerical precision and changed the control median only slightly. Leave-one-event-out, timing, crop and digital-image sensitivity checks retain the aggregate contrast under their stated conditions. These challenges do not reconstruct historical appearance or remove all confounding. Haar face detection was also tested, but its observed omissions and false boxes prevent its use here as person count or shot scale.

## 5. Preliminary results

### Event-associated gray reorganisation

Across the six selected onsets, average absolute gray change is **0.101233**, compared with a median **0.018460** across the matched reference assignments (descriptive 2.5–97.5% range 0.010977–0.037355). The original-frame integration check gives a reference median of 0.018576. These values describe a restricted conditional comparison within one digital copy and annotation set. They are not confidence intervals or a population significance test.

The following audit readout is calculated from existing per-event CSV values and saved control arrays; no new film experiment was run:

| Event | Onset, playback s | Absolute gray change | Event-specific control median | Descriptive control 2.5–97.5% |
|---|---:|---:|---:|---:|
| E006 | 549 | 0.046513 | 0.026159 | 0.002525–0.128477 |
| E007 | 591 | 0.083526 | 0.021815 | 0.000837–0.039863 |
| E008 | 611 | 0.129132 | 0.017478 | 0.002534–0.037515 |
| E009 | 664 | 0.174296 | 0.018005 | 0.002459–0.037730 |
| E010 | 726 | 0.004046 | 0.012678 | 0.001583–0.035338 |
| E011 | 734 | 0.169886 | 0.013794 | 0.000621–0.036011 |

Units are absolute changes of normalised digital gray on a 0–1 scale. These six onsets are not six independent films. E006 lies within a broad conditional range and E010 shows little change. Their inclusion demonstrates that the aggregate result is not a claim that every event boundary has a distinctive brightness signature.

### Duration organisation and choice of baseline

The observed mean absolute adjacent log-duration change is **0.7788**, compared with a within-run shuffled median **0.8568** and descriptive range **0.7060–1.0017**. It is not exceptional under that baseline. A weaker global shuffle, which removes run-specific differences, produces a much larger reference median of **1.2147**. The result distinguishes variation between temporal regimes from evidence of additional fine ordering within them. Neither positive autocorrelation nor a shot-length distribution alone establishes a montage principle.

### Unsuccessful tests and comparative extension

The original ±30-second event/cutting-rate comparison lacks an identifiable matched estimate; smaller-window results are sparse and unstable. This is a design/support limitation, not evidence that editing and narrative are unrelated. Strict gradual localisation and the face/person/scale proxy also provide substantive negative methodological findings.

A separate descriptive extension measures within-copy gray variation in 453 linked films. Studio means of the normalised 30-second change statistic range from approximately 0.388 to 0.426, with substantial within-group overlap and rankings that change with timescale and sample composition. Full-frame cut-candidate extraction is also complete. These findings demonstrate computational scalability and the need for conditional comparison; they do not explain institutional or political causation.

## 6. Theoretical and historical relevance

The pilot demonstrates a route from numerical properties to questions about their organisation: the same aggregate interval distribution can support different comparisons when temporal regimes are preserved, and independently annotated event shifts can have unequal visual correlates. It supports using computation to locate and challenge candidate relationships, followed by film-historical interpretation.

The event descriptions identify interruptions, discussion and movement between situations. The contrast between E007/E009/E011 and E010 warrants closer consideration of how framing, space and narrative information are organised. The measurements do not determine which device is dominant, what narrative function it performs, or how it should be situated politically.

[Requires the researcher's passage-specific interpretation, anchored in the existing annotation and saved images; no new viewing/reannotation is required by this pilot specification.]

[Requires an appropriate film-historical source before making a particular claim about production policy, institutional practice or political function.]

The external sixteen-film face-clustering study may be discussed separately as methodological precedent for identity adjudication, denominators and temporal role coding. It must not be described as CinematicDX's validation on this corpus.

## 7. Limitations

- One known development excerpt and one annotator support the narrative comparison; there is no independent cross-film narrative replication or inter-coder agreement estimate.
- Event definitions are heterogeneous; the original boundary-kind fields were misunderstood and are not used as intended labels. Confidence/completeness declarations do not resolve temporal precision or construct validity.
- The controls address ordinary hard cuts and coarse position, not all differences in framing, setting, pre-change gray level, personnel or temporal dependence. Eligibility conditions select a particular subset of event shifts.
- Gray measurements refer to the current digital copy; transfer history, compression, cropping and nonlinear tonal changes constrain historical interpretation.
- Hard cuts are locally assessed; full-file candidate intervals are not verified shots, and gradual transitions remain a major segmentation limitation.
- Broader samples are affected by missing videos, provisional identity links and uncertain metadata. Institutional association is not historical causation.

## 8. Next stages

For the Upgrade, the immediate tasks are to select the canonical tables/figures, clarify the existing event and control definitions, complete a bounded interpretation including exceptions, and preserve a compact reproducible packet. No additional CV model is necessary to substantiate the statements above.

Later research will require independent narrative material and validation of any additional formal property before cross-film confirmation. Person prominence, recurring configurations and CV–SNA/historical interpretation remain prospective. They have not been established by this pilot.

[Requires independent narrative reference on additional material before claiming cross-film narrative correspondence.]

[Not yet established in CinematicDX: validated shot scale/person distributions, automatic semantic motifs, or a CV–SNA historical explanation.]

## Suggested presentation items

| Item | Existing artifact | Available now? | Necessary qualification / remaining work |
|---|---|---|---|
| Source and validation table | M2 manifest, M3R summary, hard-cut validation, table above | Yes | Separate recorded metadata, technical provenance and unknown transfer history |
| Full-file candidate timeline | M3R `timeline.png/.pdf` | Yes; figure viewed | Caption as candidate intervals/local rates; no whole-film narrative interpretation |
| Event/gray timeline | Q `Q02_timeline/narrative_timeline.png/.pdf` | Yes; figure viewed | Mark 150–750s, approximate onsets and missing activity windows; do not use motion as confirmed event evidence |
| Six-event conditional comparison | Q `research_delivery/brightness_event_controls.png/.pdf` | Yes; figure viewed | Ranges are conditional reference distributions, not CIs; keep E006/E010. English re-export is presentation-only |
| Sequence and baseline comparison | Q `Q01_editing/sequence_and_controls.png/.pdf`, Q05 global-shuffle results | Yes | State eligible intervals/run structure; optional English caption/export |
| Small comparative supplement | L `analysis_final/studio_summary_all.csv`, `studio_change_all.png/.pdf`, `studio_temporal_scale_sensitivity.csv`; C `analysis/studio_summary_all.csv` | Yes | Prefer actual IQR/sample-size table or existing figure. No new corpus processing; no style/causality claim |
| Cross-film narrative replication figure | No independent second-film event reference found | No | Requires new independent reference and a frozen comparison, not a decorative extrapolation |

Suggested caption for the central figure: “Absolute change in exposure-weighted digital gray around six independently annotated event onsets in *Shang Gan Ling*, compared with ordinary hard-cut reference assignments from the same broad temporal region. Onset times are approximate; controls preserve onset-to-cut offsets and may overlap. The ranges summarise the conditional assignments rather than population uncertainty. E006 and E010 demonstrate heterogeneous event–visual correspondence.”
