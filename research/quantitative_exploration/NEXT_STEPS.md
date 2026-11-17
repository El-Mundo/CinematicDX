# Stopping point and next steps for this round

## Current status, 2026-11-10

Brightness and frame-complete editing measurements for three changed sources were updated under the original protocol. Current results for 454 videos are in the [version update and results](corpus_refresh/20261110/README.md). The 451 unchanged sources retain their original measurement receipts, while studio aggregates and sensitivities were recomputed from the current inventory. The next research priorities remain visual–narrative correspondence in independent material and reliable gradual-transition localisation.

The stopping conditions and plans below retain their October experimental context. Their coverage numbers describe the versions available at that time.

## Stopping conditions met

Six candidates were assessed. Q01–Q04 were executable on 600 seconds of real 《上甘岭》 material. Q05 challenged the strong candidate, and an additional numerical audit used original-frame integration. Negative examples, rankings, reproducible code and reference samples are preserved. Original videos/annotations were unchanged, no new models were downloaded, and neither the corpus nor tuning was expanded indefinitely.

## Strongest next experiment (HYPOTHESIS, not yet run)

Freeze the operational definition of digital brightness reorganisation near events and compare it with ordinary hard cuts in independently referenced material. Add controls for preceding brightness, shot scale, character configuration or location. The aim is to distinguish which visual reorganisations accompany which independent narrative changes, rather than train automatic event recognition.

- Core hypothesis: some narrative boundaries involve brightness/spatial-configuration reorganisation beyond ordinary cuts, but events without brightness changes also exist.
- Existing E010 is a concrete counterexample and must not be removed to improve scores.
- New references should distinguish changes in location, character configuration, action goals and narrative time, permitting overlaps and absent low-level visual cues. Labels must not be generated from curves.
- Confirmatory tests require independent material/references. Any future additional decoding must again respect the researcher's resource limit. The user is not being asked to rewatch or reannotate these 10 minutes now.
- Current controls match only temporal thirds and proximity to cuts, without controlling shot scale, composition or all non-stationarity. This is the principal alternative explanation.

## Secondary questions

1. Configuration retrieval: use the prepared small blank independent-review sheets to validate similar compositions rather than character/symbolic semantics. Compare multiple representative frames with a single frame. Current status: PROVISIONAL.
2. Visual activity: first improve the operational definition of continuous valid exposure and human spot checks. Do not lower the 95% threshold after the main comparison is blocked by missingness. Do not output camera-movement classes without true motion annotations.
3. People/shot scale: reject the current Haar proxy. Better models also need validation for profiles, groups and occlusion in historical material. Do not download large models without approval.
4. Gradual transitions: retain original candidates and negative results. Complete-interval localisation is unresolved and must remain separate from validated hard-cut statistics.
5. Cross-film/historical comparison: no evidence is available at this stage. Start with source stratification and small independent validation samples, then consider personnel/institutional relations and SNA. Grayscale or other statistics alone cannot establish political causation.

## Current limitations

The 0/1 relationship between QuickTime displayed frame numbers and decoding order, original transfer history, per-frame person/shot-scale ground truth and semantic-motif ground truth remain unresolved. Insufficient pools for 10-second controls and missing motion-event windows are explicitly recorded. Blank independent-review templates are ready; blank fields do not represent completed annotation.

## Update following user authorisation of the full corpus (2026-10-26)

The statement above that cross-film/historical comparisons lack evidence describes the first 600-second round. Subsequently, all 454 corpus files were extracted. Digital brightness organisation can be compared descriptively across 453 films, with 279 records lacking valid sources and continuing gaps in source/institutional interpretation. The full report is in [corpus_studio/REPORT.md](corpus_studio/REPORT.md). Its REPRODUCE.md identifies the run and current-result pointers.

The task has completed studio-level analysis of the full available corpus. Studio-mean rankings will not be optimised indefinitely. The most useful next step remains conditional comparison of independent narrative boundaries: freeze the original ten-minute 《上甘岭》 experiment and use its existing independent reference and ordinary-hard-cut controls while retaining counterexamples. Cross-film confirmation requires separate independent event references; this brightness curve cannot generate its own labels. This round does not ask the researcher to rewatch or reannotate material.

Before later institutional comparisons, verify colour/year/version metadata against the copies, select overlapping samples from the same year and type, and leave institutional-lineage questions to film-historical judgement. Do not automatically merge 东北/长春. The 14 chroma flags are source-quality checks, including colour casts, rather than automatic identification of 14 originally colour films. The mislabelled duplicate source for 《永恒的友谊》 needs a replacement later; original videos and inventories remain unchanged in the current round.

## Stopping decision after corpus-wide hard-cut/transition testing

All 453 available films were decoded frame by frame to EOF. Complete institutional tables, timelines, parameter/composition/source-width/cadence sensitivities, conditional permutation references, independent numerical audits and actual assistant spot checks are complete. The 279 records without valid video cannot be measured, and no values are fabricated. See the final [assessment](corpus_editing/ASSESSMENT.md). Corpus computation and weak gradual-detector tuning stop here for this round.

The strongest next narrative experiment remains a joint description of brightness reorganisation and local cutting rates near independent event boundaries, compared with ordinary cuts under matching temporal/type conditions. It must distinguish transition presence from narrative-unit change. Existing 《上甘岭》 references can support exploratory challenges, retaining E010, boundary error and 0/1-frame scenarios without asking the user to rewatch or reannotate. The same development interval cannot supply new confirmatory evidence. Cross-film confirmation requires independent narrative references, not ground truth generated by these curves or clustering.

If independent-review resources become available, first freeze a compact sample stratified by colour, period, studio, motion and source quality, including random intervals without candidates, to estimate missed hard cuts and gradual start/end/type errors separately. Do not inspect only high-scoring candidates. Resolve counting units for compound fade-out–black–new-shot sequences before discussing true transition rates. Single-studio metadata does not prove exclusive collaboration. The 449 filename links remain provisional. Non-random missing films, version differences, institutional lineages and shared creative personnel require research judgement. These gaps do not justify repeatedly requesting user input or interpreting candidate studio rankings as historical causes.
