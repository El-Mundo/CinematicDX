"""Build compact evidence artifacts and update the explicitly requested research record."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import matplotlib.pyplot as plt
from run_exploration import ROOT,fonts,contact_sheet,savefig,read,write,table,clock,sha

DOC=ROOT/'research/quantitative_exploration'


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();run=args.run.absolute();fonts()
    q1=read(run/'Q01_editing/results.json');q2=read(run/'Q02_timeline/results.json');q3=read(run/'Q03_recurrence/results.json');q4=read(run/'Q04_face_proxy/results.json');q5=read(run/'Q05_challenges/results.json');audit=read(run/'numerical_audit.json');receipt=read(run/'run.json')
    output=run/'research_delivery';output.mkdir(exist_ok=True)
    # Blank human fields remain blank; assistant judgements are in separate files.
    review=read(run/'Q04_face_proxy/unboxed_review_selection.json')['images'];rows=[]
    for i,r in enumerate(review,1):
        rows.append(dict(review_id=f'R{i:02d}',film_key='shang gan ling',video_version_id=receipt['video_version_id'],
             representative_id=r['representative_id'],source_pts=r['image_source_pts'],time_base='1/16000',playback_seconds=r['image_playback_seconds'],image_path=r['image_path'],
             human_visible_person_count='',human_face_notes='',human_shot_scale='',human_certainty='',human_annotator='',human_review_complete=''))
    table(output/'future_human_frame_review_blank.csv',rows)
    with (run/'Q03_recurrence/representatives.csv').open(encoding='utf-8-sig') as f:reps=list(csv.DictReader(f))
    middle=[r for r in reps if float(r['fraction'])==.5]
    eligible=[(i,j) for i in range(len(middle)) for j in range(i+1,len(middle)) if int(middle[j]['interval_index'])-int(middle[i]['interval_index'])>=2
              and float(middle[j]['playback_seconds'])-float(middle[i]['playback_seconds'])>=10]
    rng=np.random.default_rng(20261026);chosen=rng.choice(len(eligible),8,replace=False)
    images=[];labels=[];pairs=[]
    for k,index in enumerate(chosen,1):
        i,j=eligible[index]
        for side,n in [('A',i),('B',j)]:
            r=middle[n];images.append(run/r['image_path']);labels.append(f'Random #{k}{side} '+clock(float(r['image_playback_seconds'])))
        pairs.append(dict(pair_id=f'random-{k:02d}',first_id=middle[i]['interval_id'],second_id=middle[j]['interval_id'],first_image=middle[i]['image_path'],second_image=middle[j]['image_path'],
                          human_composition_recurrence='',human_setting_relation='',human_certainty='',human_annotator='',human_review_complete=''))
    table(output/'future_human_recurrence_review_blank.csv',pairs)
    contact_sheet(images,labels,output/'random_recurrence_control_pairs.png',cols=4)
    write(output/'review_template_policy.json',dict(human_review_requested_now=False,blank_fields_intentional=True,
           assistant_observations_are_not_human_truth=True,random_control_selection_seed=20261026,
           purpose='Compact later independent validation sample; no request to rewatch or relabel the existing 10-minute annotation.'))
    # Conditional reference distribution and actual per-event measurements.
    with np.load(run/'Q05_challenges/controls_for_inspection.npz',allow_pickle=False) as z:controls=z['decoded_ordinal_base_0__hardcut_controls']
    events=[r for r in q5['event_absolute_changes'] if r['scenario_id'].endswith('_0')]
    fig,axes=plt.subplots(1,2,figsize=(13,4.6))
    obs=np.asarray([r['absolute_gray_change'] for r in events]);x=np.arange(len(events));lo=np.quantile(controls,.025,axis=0);hi=np.quantile(controls,.975,axis=0);median=np.median(controls,axis=0)
    axes[0].plot(x,obs,'o',color='#c56835',label='Change at annotated event onsets')
    axes[0].errorbar(x,median,yerr=np.stack([median-lo,hi-median]),fmt='o',color='#245a81',capsize=4,label='Conditional ranges for ordinary hard cuts')
    axes[0].set_xticks(x,[r['event_id'] for r in events]);axes[0].set_ylabel('|Post-mean − pre-mean|, digital grayscale 0–1');axes[0].legend(fontsize=9)
    axes[1].hist(controls.mean(axis=1),bins=25,color='#d4dee7',label='1999 hard-cut control groups')
    axes[1].axvline(obs.mean(),color='#c56835',lw=2,label=f'Six-event mean {obs.mean():.3f}');axes[1].set_xlabel('Mean absolute digital grayscale change');axes[1].set_ylabel('Conditional draws');axes[1].legend(fontsize=9)
    for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.12)
    fig.suptitle('Exploratory brightness changes near events, with E010 as a counterexample')
    fig.text(.02,.01,'Five-second windows before/after, excluding central ±1 second. Conditional ranges are not confidence intervals or population significance.',fontsize=9)
    fig.tight_layout(rect=[0,.035,1,.95]);savefig(fig,output/'brightness_event_controls')
    # Preserve full observed lag strata, including reversals and tiny positive sets.
    ar=[r for r in q3['lag_stratified_event_proxy_auc'] if r['fraction']==.5 and r['same_event_proxy_auc'] is not None]
    fig,ax=plt.subplots(figsize=(10,4))
    for method,color in [('dct','#245a81'),('dhash','#2b916f'),('brightness','#a26874')]:
        r=[x for x in ar if x['method']==method];ax.plot([x['lag_bin_seconds'] for x in r],[x['same_event_proxy_auc'] for x in r],'o-',label=method,color=color)
    ax.axhline(.5,color='gray',ls='--',lw=.8);ax.set_ylim(0,1.05);ax.set_xlabel('Lower bound of representative-frame gap / seconds (20-second strata)');ax.set_ylabel('Same-event proxy AUC; not motif-retrieval accuracy');ax.legend()
    ax.set_title('Low-level similarity and narrative-proxy correspondence vary with temporal gap');ax.spines[['top','right']].set_visible(False)
    fig.text(.02,.01,'Longer-gap strata contain only 1–2 same-event pairs. Pairs share shots and are not independent samples.',fontsize=9);fig.tight_layout(rect=[0,.03,1,1]);savefig(fig,output/'recurrence_lag_controls')
    # Log and source records are small and remain outside source control.
    for source,name in [('/tmp/cinematicdx-quantitative-tests-all.log','tests_225.log'),('/tmp/cinematicdx-quantitative-exploration.log','initial_execution.log'),('/tmp/cinematicdx-quantitative-challenges.log','followup_execution.log'),('/tmp/cinematicdx-quantitative-audit.log','audit_execution.log')]:
        shutil.copy2(source,output/name)
    links='../../'+str(run.relative_to(ROOT))
    report=f'''# CinematicDX: quantitative evidence exploration report

Date: 2026-10-26. Working branch: `codex/quantitative-evidence-20261026`. This round completed five new experiments/challenges and assessed six candidates, meeting evidence-based stopping conditions.

The most useful new finding is that **digital brightness changes near this film's existing human-annotated events remain larger under conditional controls using ordinary hard cuts, warranting further validation.** This is not an automatic narrative recogniser and does not establish causation between film form and political context.

## Material, independence and scope

- 《上甘岭》(1956), `research-inventory:shang gan ling`, video version `{receipt['video_version_id']}`. The actual file is on a local external drive, and its complete SHA was recalculated. Original provenance/transfer history remain unknown.
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

These statuses address stated uses. Reproducible numbers do not validate film-theoretical interpretation. Timings reflect reduced-resolution images/existing caches on this machine and cannot directly budget original-resolution full-corpus processing. The four initial real-material experiments took about {receipt['elapsed_seconds']:.2f} seconds overall; reporting, testing and reading are additional.

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

Code is in this directory's `scripts/` and `analysis-python/cinematicdx/exploration.py`. The frozen protocol, cache bindings, source snapshots, all negative cases, bins, per-frame pairs, controls and contact sheets are in [{run.name}]({links}/run.json). Original video and annotation checksums match. PTS and actual intervals for all 144 representative images were individually checked, with maximum temporal deviation about 0.040 seconds.

All 225 Python tests passed, including 17 new tests of actual exposure, missingness, gradual gaps, controls, descriptors and mechanisms. They do not replace film evidence. A second numerical implementation checked 1999 blockwise permutations and original-frame integration, with maximum primary event-change difference about 5.9×10⁻¹⁴.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v

PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/cinematicdx-mpl .venv-m3/bin/python research/quantitative_exploration/scripts/replay.py --from-run {run.relative_to(ROOT)} --output research-local/quantitative-exploration/replay-001
```

Recomputation uses the existing isolated environment and the same caches/original video. `replay-001` must be a new directory, and existing outputs are not overwritten. Paths can be substituted, but input hashes cannot be changed arbitrarily. There are no hidden database or model-download steps. Receipts record principal dependency versions, code checksums and the source file's complete SHA.

Six candidates have been assessed, four real-material experiments and one challenge/frame-integration audit completed, failures retained, and rankings and follow-up procedures documented. Further tuning on the same clip would not add independent validity, so this round stops here without expanding to the full corpus.

See [candidates](CANDIDATES.md), [experiment log](EXPERIMENTS.md), [ranking](METHOD_RANKING.md), [next steps](NEXT_STEPS.md) and [verified sources](BIBLIOGRAPHY.md).
'''
    (DOC/'REPORT.md').write_text(report)
    ranking=f'''# Method ranking supported by evidence (2026-10-26)

| Rank | Candidate | Current status and evidence | Decision |
|---|---|---|---|
| 1 | C01 hard-cut timing, conservative durations and ordering | Timing/distribution arithmetic VERIFIED; additional fine-sequence organisation PROVISIONAL. 41 intervals, 37 adjacent relations; within-block permutations show no exceptional ordering | Core data; retain timelines and controls without montage labels |
| 2 | C02 within-version digital brightness/contrast | Extraction VERIFIED; narrative correspondence PROVISIONAL. Six cut-associated events: 0.1012 versus controls around 0.0185, retained under frame integration, leave-one-out and source perturbations | Strongest new narrative candidate; conditional association does not establish a general rule |
| 3 | C04 low-frequency configuration-similarity retrieval | PROVISIONAL. Changing representative frames retains 5–7 of the top10 pairs, with clear mismatches; advantage over brightness baseline varies by temporal gap | Assist visual-relation retrieval; not yet a semantic motif/location tool |
| 4 | C03 visual-activity proxy | PROVISIONAL. Correlation and optical-flow rank correlation 0.932; complete event exposure for only 4/10 | Prefer inexpensive correlation and missingness flags; defer camera-movement classification/full-event comparisons |
| 5 | C05 current Haar boxes as person-count/shot-scale proxies | REJECTED for this use. Missed profiles and torso false boxes; parameters affect counts for 21.5% of representative images | Exclude from core; retain face boxes as predictions only |
| 6 | C06 current automatic complete gradual segmentation | REJECTED for this use. Existing strict-interval primary scoring failed | Stop optimising around 4 examples; do not automatically change the shot table |

This is not a cross-film accuracy leaderboard. VERIFIED covers only the stated measurement/numerical claims. Character identity, narrative function, attention mechanisms and political meaning have not been automatically validated.

Minimum combination: source version/PTS/quality and missingness + reference-checked hard cuts/conservative duration sequences + same-copy grayscale mean/contrast + an independent narrative-event layer and conditional controls. Activity is optional, and similarity supports exploration.

Full evidence: [report](REPORT.md). This round's outputs: `{run.relative_to(ROOT)}`.
'''
    (DOC/'METHOD_RANKING.md').write_text(ranking)
    next_steps='''# Stopping point and next steps for this round

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
'''
    (DOC/'NEXT_STEPS.md').write_text(next_steps)
    additions=f'''
## Actual execution and results for this round (current status)

Run: `{run.relative_to(ROOT)}`. Input/output SHA records are in `protocol.json`, `run.json` and `numerical_audit.json`. Both frame-number conventions are retained.

| Experiment | Current status | Actual outputs and bounded conclusion |
|---|---|---|
| Q01 | PROVISIONAL (numerical checks VERIFIED) | 41 complete hard-cut intervals in four blocks of 6/1/7/27, mean 8.945 seconds; adjacent log difference 0.7788 versus within-block permutation median 0.8568, without exceptional additional sequence organisation. Weaker global permutations exaggerate differences |
| Q02 grayscale/narrative | PROVISIONAL (extraction VERIFIED) | Six cut-associated events: 0.1012 versus conditional median 0.0185; weaker joint-shift controls for ten events: 0.1693 versus 0.0449. E010 is only 0.0040, precluding general event detection |
| Q02 visual activity | PROVISIONAL; full-group event controls BLOCKED by missingness | 1499 frame pairs, 1427 valid; flow/correlation-difference rank correlation 0.932. Only 4/10 events meet complete-exposure requirements; do not fill with zero or lower the threshold |
| Q03 | PROVISIONAL | 48 continuous-content intervals, 144 representative images; DCT top10 retains 5/7 pairs after frame replacement, with low-frequency mismatch counterexamples retained. Same-event proxy advantage varies by gap and does not supply semantic ground truth |
| Q04 | REJECTED for person-count/shot-scale use | Zero detections in 79/144 images; parameters change face counts in 31/144. Assistant review of 12 unboxed images followed by boxes finds missed profiles/torso false boxes. No independent human accuracy estimates |
| Q05 | PROVISIONAL, explicitly declared challenge after the initial round | Leaving out any one event gives mean 0.0866–0.1207; gamma/JPEG/crop challenges preserve direction without replacing primary results |
| Numerical audit | VERIFIED only for numerical/provenance claims | Separate implementation checks 1999 blockwise permutations; original-frame integration event difference <6e-14; maximum exact control-pool mean 0.04215; PTS checked for all 144 representative images |

Initial Q01–Q04 execution took about {receipt['elapsed_seconds']:.2f} seconds, including source verification, existing caches and decoding 144 representatives. Optical flow took about 0.83 seconds, representative decoding 12.93 seconds, and both face-box settings 3.14 seconds. Passing 225 tests does not replace empirical validation. Digital-source sensitivities, individual events, every window and unfavourable pairs are retained. See the [full report](REPORT.md).
'''
    with (DOC/'EXPERIMENTS.md').open('a') as f:f.write(additions)
    with (DOC/'CANDIDATES.md').open('a') as f:f.write('''
## Update after measurements in this round

C01–C05 were run. C06 cites and preserves the existing failure without repeating inference. The current evidence ordering is C01/C02/C04/C03/C05/C06. C01 is numerically auditable, but its fine-sequence claims remain weak. C02 provides the strongest new narrative-control lead. C04 can retrieve visual configurations, but is unstable and lacks semantic ground truth. C03 largely duplicates inexpensive correlation and lacks the main event comparison because of missing observations. Explicit counterexamples reject the current C05 for person-count/shot-scale use. The complete eight-dimensional assessment is in the [report](REPORT.md), and statuses and uses are in the [ranking](METHOD_RANKING.md).
''')
    with (DOC/'RESEARCH_LOG.md').open('a') as f:f.write(f'''
## {datetime.now(timezone.utc).isoformat()}: round completed and stopped

- Experiment directory: `{run.relative_to(ROOT)}`. Q01–Q04, the Q05 challenge and a second numerical-implementation check are complete. Unique film material remains 600 seconds without expanding to other films.
- The strongest new evidence is conditional brightness reorganisation in this film. Retain E010, low-level-similarity mismatches and failures of the character proxy.
- Ordering controls show that global permutations and preservation of passage differences produce conclusions of different strength. Positive correlation alone cannot establish a principle of form.
- Missing activity windows remain blank. Insufficient 10-second hard-cut control pools are BLOCKED, without post-hoc metric rescue.
- Engineering tests first identified normalisation of numerical DCT residuals for constant images. This was corrected to missingness before producing actual film outputs. Duplicate descriptive-field names in the first supplementary audit prevented receipt publication; correcting those names allowed it to pass without changing original statistics or thresholds.
- All 225 Python tests passed. Original video/Excel/reference SHA values match, and PTS checks passed for all 144 images. Assistant observations remain distinct from researcher annotations, and future human-review sheets stay blank.
- No commits/pushes, database connections or additional dependency/model downloads. Stop development on this film after completing the task's conditions. The next confirmatory experiment remains HYPOTHESIS.
''')
    # Complete final package inventory, including later reviews and scripts.
    source_snapshot=output/'final_source_snapshot';source_snapshot.mkdir(exist_ok=True)
    sources=[ROOT/'analysis-python/cinematicdx/exploration.py',ROOT/'analysis-python/tests/test_exploration.py']+list((DOC/'scripts').glob('*.py'))
    for source in sources:shutil.copy2(source,source_snapshot/source.name)
    artifacts=[p for p in run.rglob('*') if p.is_file() and p.name!='research_record_receipt.json']
    write(run/'research_record_receipt.json',dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),
        initial_run_sha256=sha(run/'run.json'),original_annotation_sha256=read(run/'protocol.json')['inputs']['original_excel']['sha256'],
        source_and_annotation_unchanged=True,unique_source_seconds=600,tests_passed=225,completion_conditions_met=True,
        research_documents={p.name:{'sha256':sha(p)} for p in DOC.glob('*.md')},
        sources={str(p.relative_to(ROOT)):{'sha256':sha(p)} for p in sources},
        artifacts={str(p.relative_to(run)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in artifacts},
        no_push_or_commit=True,models_downloaded=False,cloud_upload=False))
    print(json.dumps({'report':str(DOC/'REPORT.md'),'artifact_count':len(artifacts),'status':'Research stopping conditions met; no generalisation claim.'},ensure_ascii=False))


if __name__=='__main__':main()
