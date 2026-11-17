"""Publish complete studio-grouped editing candidates with explicit validation limits."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import csv
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
os.environ.setdefault('MPLCONFIGDIR','/tmp/cinematicdx-mpl')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from cinematicdx.corpus_editing import sha,write_json
from cinematicdx.corpus_studio_analysis import weighted_mean,weighted_quantiles
from cinematicdx.editing_comparison import conditional_studio_reference,transient_return_flags


def read(path):return json.loads(Path(path).read_text())
def csv_write(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
def number(x):return '—' if x is None else f'{x:.3f}'


METRICS=['primary_cut_candidates_per_minute','lenient_cut_candidates_per_minute','strict_cut_candidates_per_minute',
    'roi_cut_candidates_per_minute','median_cut_bounded_interval_seconds','mean_cut_bounded_interval_seconds',
    'mean_abs_adjacent_log_interval_change','default_gradual_candidates_per_minute','strict_gradual_candidates_per_minute',
    'fade_only_baseline_gradual_candidates_per_minute','default_gradual_candidate_union_fraction',
    'candidate_gradual_free_interval_median_seconds','transient_return_flags_per_minute','cut_rate_excluding_transient_flags_sensitivity',
    'digital_near_black_hold_starts_per_minute','digital_near_black_hold_fraction']


def summarize(films,sid,predicate=lambda f:True):
    members=[f for f in films if predicate(f) and any(s['studio_id']==sid for s in f['studios'])]
    measured=[f for f in members if f['measured']]
    weights=[next(s['fractional_weight'] for s in f['studios'] if s['studio_id']==sid) for f in measured]
    result=dict(metadata_n=len(members),available_n=sum(f['video_available'] for f in members),measured_n=len(measured),
        failed_n=sum(f['video_available'] and not f['measured'] for f in members),
        missing_n=sum(not f['video_available'] for f in members),fractional_measured_n=sum(weights))
    for name in METRICS:
        values=[f.get(name) for f in measured]
        result[name+'__mean']=weighted_mean(values,weights)
        q25,median,q75=weighted_quantiles([np.nan if x is None else x for x in values],weights)
        result.update({name+'__q25':q25,name+'__median':median,name+'__q75':q75})
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True,type=Path);parser.add_argument('--report-directory',type=Path);args=parser.parse_args();run=args.run.absolute()
    plan=read(run/'plan.json')
    if not (run/'effective_extraction_complete.json').exists():
        subprocess.run([sys.executable,str(Path(__file__).with_name('repair_corpus_editing.py')),'--run',str(run)],check=True)
    done=read(run/'effective_extraction_complete.json')
    assert done['attempted']==len(plan['jobs']) and len(done['complete'])+len(done['failed'])==len(plan['jobs'])
    assert sha(plan['metadata_path'])==plan['metadata_sha256']
    out=run/'analysis';out.mkdir(exist_ok=False);lookup={j['film_key']:j for j in plan['jobs']};films=[];profiles=[];total_frames=0
    for original in plan['films']:
        film={k:v for k,v in original.items() if k!='video_available_by_current_linkage'}
        job=lookup.get(film['film_key']);film.update(video_available=job is not None,measured=False,status='missing_effective_video' if job is None else 'extraction_failed')
        if job and (run/'films'/job['job_id']/'run.json').exists():
            directory=run/'films'/job['job_id'];receipt=read(directory/'run.json');doc=read(directory/'summary.json')
            if not doc['technical']['reached_eof']:raise ValueError('Declared stream duration stopped decoding before EOF; inspect and re-extract affected source before corpus publication.')
            for name,digest in receipt['outputs'].items():assert sha(directory/name)==digest
            film.update(doc['metrics'],measured=True,status='algorithmic_candidates_not_ground_truth',job_id=job['job_id'],video_version_id=job['video_version_id'])
            film['source_width']=doc['technical']['source_width'];film['source_height']=doc['technical']['source_height']
            cuts=read(directory/'cut_candidates.json')['primary']['playback_seconds'];duration=doc['metrics']['duration_seconds'];total_frames+=doc['metrics']['frame_count']
            film['observed_coverage_start_playback_seconds']=doc['technical']['actual_start_seconds']
            film['observed_coverage_end_playback_seconds']=doc['technical']['actual_end_seconds']
            with np.load(directory/'frame_features.npz',allow_pickle=False) as z:
                flags=transient_return_flags(z['playback_seconds'],z['gray_cache'],cuts)
                step=float(np.median(z['frame_delta_seconds']))
                film['observed_median_frame_step_seconds']=step
                film['observed_p95_frame_step_seconds']=float(np.quantile(z['frame_delta_seconds'],.95))
                film['observed_median_cadence_hz_rounded']=round(1/step,2)
                film['zero_v_change_pair_fraction']=float(np.mean(z['v_mad'][1:]==0))
            film['transient_return_flags_n']=len(flags);film['transient_return_flags_per_minute']=60*len(flags)/duration
            film['cut_rate_excluding_transient_flags_sensitivity']=60*(len(cuts)-len(flags))/duration
            write_json(out/('transient-flags-'+job['job_id']+'.json'),dict(film_key=film['film_key'],video_version_id=film['video_version_id'],flags=flags,main_cut_candidates_unchanged=True))
            gd=read(directory/'gradual_default.json');gradual=gd['predictions']
            holds=gd['black_holds']
            film['digital_near_black_hold_n']=len(holds)
            film['digital_near_black_hold_seconds']=sum(g['duration_seconds'] for g in holds)
            film['digital_near_black_hold_fraction']=film['digital_near_black_hold_seconds']/duration
            film['digital_near_black_hold_starts_per_minute']=60*len(holds)/duration
            film['default_predicted_transition_type_counts']=dict(Counter(p['predicted_type'] for p in gradual))
            for i in range(100):
                a=doc['technical']['actual_start_seconds']+i/100*duration;b=doc['technical']['actual_start_seconds']+(i+1)/100*duration
                profiles.append(dict(film_key=film['film_key'],position_bin=i,position_start_fraction=i/100,
                    cut_candidates_per_minute=60*sum(a<=t<b for t in cuts)/(b-a),
                    cut_density_relative_to_film_rate=100*sum(a<=t<b for t in cuts)/len(cuts) if cuts else None,
                    gradual_candidate_starts_per_minute=60*sum(a<=g['start_playback_seconds']<b for g in gradual)/(b-a)))
        films.append(film)
    measured=[f for f in films if f['measured']];studios={s['studio_id']:s for f in films for s in f['studios']}
    all_groups=[];feature_bw=[];feature_colour=[];single=[];strata=[];source_width=[];cadence=[];timeline=[]
    profiles_by_key={f['film_key']:[p for p in profiles if p['film_key']==f['film_key']] for f in measured}
    for sid,studio in studios.items():
        base=dict(studio_id=sid,studio=studio['chn'],studio_name=studio['name'])
        all_groups.append(dict(base,**summarize(films,sid)))
        feature_bw.append(dict(base,**summarize(films,sid,lambda f:f['film_type']=='Feature' and f['colour']=='B&W')))
        feature_colour.append(dict(base,**summarize(films,sid,lambda f:f['film_type']=='Feature' and f['colour']=='Colour')))
        single.append(dict(base,**summarize(films,sid,lambda f:len(f['studios'])==1)))
        members=[f for f in films if any(s['studio_id']==sid for s in f['studios'])]
        for year,kind,colour in sorted({(f['year'],f['film_type'],f['colour']) for f in members}):
            strata.append(dict(base,year=year,film_type=kind,colour=colour,**summarize(films,sid,lambda f,y=year,k=kind,c=colour:(f['year'],f['film_type'],f['colour'])==(y,k,c))))
        for width in sorted({f['source_width'] for f in members if f['measured']}):
            source_width.append(dict(base,source_width=width,**summarize(films,sid,lambda f,w=width:f.get('source_width')==w)))
        for hz in sorted({f['observed_median_cadence_hz_rounded'] for f in members if f['measured']}):
            cadence.append(dict(base,observed_median_cadence_hz_rounded=hz,**summarize(films,sid,lambda f,h=hz:f.get('observed_median_cadence_hz_rounded')==h)))
        effective=[f for f in members if f['measured']]
        weights=[next(s['fractional_weight'] for s in f['studios'] if s['studio_id']==sid) for f in effective]
        for i in range(100):
            row=dict(base,position_bin=i,position_start_fraction=i/100,film_n=len(effective))
            for name in ['cut_candidates_per_minute','cut_density_relative_to_film_rate','gradual_candidate_starts_per_minute']:
                values=[profiles_by_key[f['film_key']][i][name] for f in effective]
                row[name+'__mean']=weighted_mean(values,weights)
                q25,median,q75=weighted_quantiles([np.nan if v is None else v for v in values],weights)
                row.update({name+'__q25':q25,name+'__median':median,name+'__q75':q75})
                row[name+'__film_n']=sum(v is not None and np.isfinite(v) for v in values)
            timeline.append(row)
    assert abs(sum(g['fractional_measured_n'] for g in all_groups)-len(measured))<1e-8
    for name,rows in [('film_measurements_and_coverage',films),('studio_summary_all',all_groups),('studio_summary_feature_bw',feature_bw),
        ('studio_summary_feature_colour',feature_colour),('studio_summary_single_production',single),('studio_year_colour_type',strata),
        ('studio_source_width',source_width),('studio_frame_cadence',cadence),('film_relative_timeline',profiles),('studio_relative_timeline',timeline)]:csv_write(out/(name+'.csv'),rows)
    preflight=read(run/'preflight/results.json')
    summary=dict(status='PROVISIONAL hardcut comparisons; REJECTED gradual complete-segmentation validity',
        metadata_films=len(films),raw_video_paths=plan['raw_video_file_count'],distinct_sources_attempted=len(plan['jobs']),
        measured_films=len(measured),failed_films=len(done['failed']),missing_effective_video_films=sum(not f['video_available'] for f in films),
        measured_hours=sum(f['duration_seconds'] for f in measured)/3600,decoded_frames=total_frames,
        total_cut_candidates=sum(f['primary_cut_candidates'] for f in measured),
        total_gradual_candidates=sum(f['default_gradual_candidates'] for f in measured),
        studios_in_metadata=len(studios),studios_with_measured_films=sum(g['measured_n']>0 for g in all_groups),
        extraction_elapsed_seconds=done['elapsed_seconds'],preflight=preflight,
        initial_failed_films=len(done.get('initial_failed_jobs',[])),recovered_roundoff_films=len(done.get('recovered_roundoff_jobs',[])),
        roundoff_recovery_elapsed_seconds=done.get('recovery_elapsed_seconds',0),
        warning='Gradual candidate totals/rates are detector outputs, never estimated true transition counts or studio preferences. Hardcut accuracy only has within-film manual evidence.')
    write_json(out/'summary.json',summary)
    for width,name in [(False,'conditional_studio_reference'),(True,'conditional_source_width_reference')]:
        write_json(out/(name+'.json'),conditional_studio_reference(films,include_width=width))
    plot(out,all_groups,timeline)
    report=report_text(run,out,summary,all_groups,feature_bw)
    (out/'REPORT.md').write_text(report)
    docs=args.report_directory or ROOT/'research/quantitative_exploration/corpus_editing';docs.mkdir(parents=True,exist_ok=True)
    (docs/'REPORT.md').write_text(report)
    snap=out/'source_snapshot';snap.mkdir()
    sources=[Path(__file__),ROOT/'analysis-python/cinematicdx/corpus_editing.py',ROOT/'analysis-python/cinematicdx/gradual.py',
             ROOT/'research/quantitative_exploration/scripts/prepare_corpus_editing.py',ROOT/'research/quantitative_exploration/scripts/run_corpus_editing.py',
             ROOT/'analysis-python/cinematicdx/editing_comparison.py',ROOT/'research/quantitative_exploration/scripts/repair_corpus_editing.py',
             ROOT/'analysis-python/cinematicdx/corpus_studio_analysis.py',ROOT/'analysis-python/cinematicdx/ingest.py',ROOT/'analysis-python/cinematicdx/shots.py',
             ROOT/'analysis-python/tests/test_corpus_editing.py',ROOT/'analysis-python/tests/test_editing_comparison.py',
             ROOT/'research/quantitative_exploration/scripts/audit_corpus_editing.py',ROOT/'research/quantitative_exploration/scripts/inspect_corpus_editing.py',
             ROOT/'research/quantitative_exploration/scripts/finish_corpus_editing.py']
    for path in sources:shutil.copy2(path,snap/path.name)
    files=[p for p in out.rglob('*') if p.is_file()]
    write_json(out/'run.json',dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),config_sha256=sha(run/'config.json'),
        plan_sha256=sha(run/'plan.json'),sources={str(p.relative_to(ROOT)):sha(p) for p in sources},
        outputs={str(p.relative_to(out)):sha(p) for p in files},original_material_modified=False))
    print(json.dumps({k:summary[k] for k in summary if k!='preflight'},ensure_ascii=False))


def plot(out,groups,timeline):
    font='/System/Library/Fonts/STHeiti Light.ttc';font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'axes.unicode_minus':False})
    def save(fig,name):
        fig.savefig(out/(name+'.png'),dpi=170,bbox_inches='tight');fig.savefig(out/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
    chosen=sorted([g for g in groups if g['measured_n']>=10],key=lambda g:g['primary_cut_candidates_per_minute__mean'],reverse=True)
    if not chosen:return
    for metric,title,label,name in [('primary_cut_candidates_per_minute','Automatic hard-cut candidates/min','Hard-cut candidates: cross-film accuracy remains unestablished','studio_cut_candidates'),
        ('default_gradual_candidates_per_minute','Gradual candidates/min\n(not verified transition rates)','Gradual candidates: complete-interval validation failed','studio_gradual_candidates')]:
        fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(chosen))
        ax.plot(x,[g[metric+'__mean'] for g in chosen],'o',color='#245a81')
        for i,g in enumerate(chosen):ax.vlines(i,g[metric+'__q25'],g[metric+'__q75'],color='#97a9b8',lw=4)
        ax.set_xticks(x,[g['studio']+'\nn='+str(g['measured_n']) for g in chosen],rotation=35,ha='right')
        ax.set_ylabel(title);ax.set_title(label+'\nVertical lines show interquartile ranges across films');fig.tight_layout();save(fig,name)
    for metric,label,name in [('cut_candidates_per_minute__mean','Hard-cut candidates/min','studio_cut_timeline'),
        ('cut_density_relative_to_film_rate__mean','Rate relative to film mean\n(1 = film mean)','studio_cut_relative_profile'),
        ('gradual_candidate_starts_per_minute__mean','Gradual candidate starts/min\n(not verified transitions)','studio_gradual_timeline')]:
        data=[[np.nan if r[metric] is None else r[metric] for r in timeline if r['studio_id']==g['studio_id']] for g in chosen]
        fig,ax=plt.subplots(figsize=(12,5));image=ax.imshow(data,aspect='auto',cmap='viridis',extent=[0,100,len(chosen)-.5,-.5])
        ax.set_yticks(range(len(chosen)),[g['studio'] for g in chosen]);ax.set_xlabel('Relative position in complete local file / % (not narrative acts)')
        ax.set_title(label.replace('\n',' ')+'\nEqual film weights; fractional co-production weights');fig.colorbar(image,ax=ax,label=label);fig.tight_layout();save(fig,name)


def report_text(run,out,s,groups,bw):
    shown=sorted([g for g in groups if g['measured_n']>=10],key=lambda g:g['primary_cut_candidates_per_minute__mean'],reverse=True)
    table='| Studio | Metadata/measured | Hard-cut candidates/min | Lenient/strict | ROI | B&W features (n) | Gradual candidates/min* |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for g in shown:
        b=next(x for x in bw if x['studio_id']==g['studio_id'])
        table+=f"| {g['studio']} | {g['metadata_n']}/{g['measured_n']} | {number(g['primary_cut_candidates_per_minute__mean'])} | {number(g['lenient_cut_candidates_per_minute__mean'])}/{number(g['strict_cut_candidates_per_minute__mean'])} | {number(g['roi_cut_candidates_per_minute__mean'])} | {number(b['primary_cut_candidates_per_minute__mean'])} ({b['measured_n']}) | {number(g['default_gradual_candidates_per_minute__mean'])} |\n"
    primary=[r for r in s['preflight']['hard_cut_validation'] if r['detector']=='primary' and r['tolerance_seconds']==.08]
    gprimary=[r for r in s['preflight']['gradual_validation'] if r['detector']=='default' and r['iou']==.5]
    hard_table='| Configuration | Frame-number scenario | Matches/unmatched predictions/misses (±0.08 s) |\n|---|---|---:|\n'
    for r in s['preflight']['hard_cut_validation']:
        if r['tolerance_seconds']==.08:hard_table+=f"| {r['detector']} | {r['scenario_id']} | {r['tp']}/{r['fp']}/{r['fn']} |\n"
    gradual_table='| Configuration | Frame-number scenario | tIoU | Matches/unmatched predictions/misses |\n|---|---|---:|---:|\n'
    for r in s['preflight']['gradual_validation']:
        if r['iou'] in [.5,.3]:gradual_table+=f"| {r['detector']} | {r['scenario_id']} | {r['iou']} | {r['true_positive']}/{r['false_positive']}/{r['false_negative']} |\n"
    conditional=[]
    for name in ['conditional_studio_reference','conditional_source_width_reference']:
        test=read(out/(name+'.json'))
        if test['status']=='BLOCKED':conditional.append(f"{name}: BLOCKED, {test['reason']}")
        else:conditional.append(f"{name}: {test['film_n']} films, {test['cell_n']} matched cells, {test['studio_n']} institutions; between-studio residual share {test['observed_between_studio_residual_share']:.4f}, median across 999 permutations {test['null_median']:.4f}, 2.5–97.5% reference range {test['null_q025']:.4f}–{test['null_q975']:.4f}, reference fraction at least as large as the observed statistic {test['null_at_least_observed_fraction']:.4f}.")
    conditional_text='\n\n'.join(conditional)
    reuse_path=run/'measurement_reuse.json'
    refresh_text=''
    if reuse_path.exists():
        reuse=read(reuse_path)
        refresh_text=f"This version update re-extracted {len(reuse['new_job_ids'])} source files and inherited frame-complete measurements for {len(reuse['inherited_jobs'])} source files. The reuse manifest binds the original run directory, receipt SHA and video version. All institutional statistics, temporal profiles and conditional references were recomputed from the current film table. See this run's `plan.json` and the parent directory's `refresh.json` for source and update manifests."
    return f'''# Hard cuts and transitions across the available corpus, grouped by production institution

Hard-cut comparisons remain PROVISIONAL. The current gradual-transition model's claim to locate complete start/end intervals is REJECTED. Numerical detector output does not by itself constitute verified transition statistics.

## Coverage and actual computation

There are {s['metadata_films']} metadata records and {s['raw_video_paths']} video paths. Frame-complete measurements are available for the current {s['distinct_sources_attempted']} film sources: {s['measured_films']} succeeded, {s['failed_films']} failed, and {s['missing_effective_video_films']} records lack a valid video. Actual decoding covered {s['decoded_frames']:,} frames and {s['measured_hours']:.2f} hours. Measurements cover {s['studios_with_measured_films']}/{s['studios_in_metadata']} institutions. The current run binds each source association to its film key and video SHA.

{refresh_text}

Initially, {s['initial_failed_films']} jobs failed; {s['recovered_roundoff_films']} were completed through machine-precision boundary recovery while preserving their original caches. ROI values may be clipped back to the 0–1 boundary only when the excursion is no greater than 8×float64 machine precision. Larger deviations and NaN are rejected. The original video SHA, cache SHA and final frames at actual EOF are rechecked. Original failures and `extraction_complete.json` remain intact. A separate `effective_extraction_complete.json` records final coverage rather than silently erasing failures.

## Measurement and validation

Hard cuts use frame-by-frame HSV-V MAD at full-frame width ≤320. The MAD ratio to the mean of the preceding and following 2 frames must be ≥3, with MAD≥15. Original PTS impose a minimum interval of 0.12 seconds. Ratios 2.5/3.5 and a fixed ROI are separate sensitivity checks. This uses neither the luminance study's 1Hz sampling nor skipped decoded frames or times fabricated from nominal frame rates.

Uniform V-only processing avoids the many HSV false positives previously caused by unstable hue in near-gray images in this film. It may miss colour cuts with similar V but predominantly different hue. The algorithm does not switch automatically according to unreliable colour labels. The B&W 《上甘岭》 reference does not validate recall on colour material, so the B&W-feature tables must be read separately. The 0.12-second minimum interval also suppresses very short insert candidates, whose suppression records are preserved.

Candidates in 《上甘岭》 at 150–750 seconds match the original PySceneDetect0.7.1 baseline point by point. Both QuickTime frame-number interpretations are retained. At ±0.08 seconds, excluding independently annotated gradual intervals, each interpretation gives {primary[0]['tp']} matches/{primary[0]['fp']} false positives/{primary[0]['fn']} misses, with precision/recall {primary[0]['precision']:.4f}. Results at ±0.04/0.12 seconds and all other settings are preserved. Validation uses this film's ten-minute manual reference, which previously contributed to method development. Both frame-number origins remain explicit.

The gradual scan applies the existing endpoint-mixing/near-black fade rules to complete files, retaining default, strict and fade-only configurations. Its BGR2GRAY fixed-ROI cache is resized directly to 16×12, unlike the former 64×48 cache. This is not presented as a speed-only optimisation with an unchanged signal. At tIoU≥0.5, both frame-number interpretations still give {gprimary[0]['true_positive']} matches/{gprimary[0]['false_positive']} false positives/{gprimary[0]['false_negative']} misses. The earlier failure to locate complete start/end intervals remains documented. The corpus scan examines candidate density, failure and parameter sensitivity. **It cannot establish actual dissolve/fade preferences.**

This transition model operationalises only dissolve and fade candidates. It does not cover all transition types, including wipes, irises and occlusion transitions. Failure to match a complete interval does not establish that no transition occurred. Candidate localisation and complete-interval segmentation are distinct uses.

The already available local TransNetV2 model also failed strict interval validation. Its measured CPU run processed 15248 frames in about 160 seconds. Linear extrapolation to frame-complete processing of the corpus is about one week, so the existence of a model does not justify launching a multi-day job. No models were downloaded or trained, no material was uploaded, and no paid computation was used.

### Parameter comparisons on the same manual interval

{hard_table}

{gradual_table}

After scoring exclusions, the primary hard-cut setting and manual reference both contain 45 points, yet 2 predictions remain unmatched and 2 reference cuts are missed. Equal totals do not establish correct temporal organisation. Preserved original-frame error images show smoke/explosions, changes between similar gray levels, and areas near gradual-transition endpoints. Assistant observations explain possible failure mechanisms without changing labels or choosing the more favourable frame-number origin. Looser gradual tIoU can support local candidate use but cannot replace strict complete-interval evaluation.

The counting unit for composite transitions also needs specification. A near-black-to-new-image jump following a reference fade may be counted by a point detector. Whether “fade-out—black hold—new shot” is one composite event or separate fade, hold and hard-cut events is a research-protocol decision. This run retains the original annotation scoring rather than changing the reference to improve the figures.

## Studio comparisons

Specific institutions remain separate according to production.name. Films receive equal weight and co-productions receive 1/k per institution. Northeast/Changchun and other institutions are not automatically merged. The table below includes institutions with at least 10 measured films. CSV files retain all 60 institutions, including missing films. Year, type, colour labels and source conditions also shape institutional samples.

{table}

*The gradual column describes a detector that still makes many errors. It is a method diagnostic, not a ranking of actual transition rates. Full tables also contain interquartile ranges across films, single-studio subsets, year×colour×type strata and source-width strata. Small institutional samples are not ranked, and frames are not treated as independent samples. Source width does not identify scanning/restoration provenance.

The corpus produced {s['total_cut_candidates']:,} hard-cut candidates and {s['total_gradual_candidates']:,} gradual candidates. These are model outputs and cannot be added together as a verified total transition count. Conflicts where hard cuts fall inside gradual-candidate intervals are recorded separately. The weak gradual model does not automatically remove hard cuts.

## Composition-conditioned permutation references

Only single-studio films from institutions with at least 10 originally measured members enter same-year×type×metadata-colour cells (≥5 films and ≥2 institutions). The between-group residual share is computed after subtracting each cell mean. Film values are permuted within cells 999 times with seed 20261026. A second reference additionally requires equal source width without relaxing eligibility thresholds. Co-productions remain in descriptive tables but are not independent group members in this particular reference.

{conditional_text}

This is an exploratory conditional reference, not a guarantee of exchangeability in historical material. Actual sources, subjects, cinematographers and institutional selection may still confound the comparison. Tail fractions establish neither population patterns under random sampling nor causal studio effects or a particular institution's distinctive style. Matched subsets and full descriptive tables have different coverage and must be read with n.

## Temporal organisation and interpretive limits

Each film retains original candidate PTS, playback coordinates, all frame-level scores, small ROIs and local candidate rates in 100 position bins. Intervals bounded by two complete hard-cut candidates exclude file edges, but undetected gradual transitions may occur inside them. They are therefore candidate-cut-bounded intervals rather than verified average shot lengths. Intervals not intersecting gradual candidates are retained as a sensitivity check, not shot ground truth. Adjacent log-interval change is descriptive and identifies no montage principle, narrative event or cause by itself.

Relative profiles also show “local rate / film mean rate” (1 denotes the film mean), separating total switching volume from relative positional distribution. Films with zero candidates remain missing in this normalisation and have separately reported effective n. Given the same candidate set, the profile is invariant to uniform playback-speed scaling. It does not remove missed detections, source editing, nonuniform speed changes or minimum-interval filtering, and relative positions are not named as narrative stages.

Digital-file opening and ending material, advertising/logos, jitter, movement, flashes, colour casts, repeated frames and unknown transfer workflows can trigger or conceal transitions. Complete-film processing means the complete local file, not a verified complete historical version. The independent human transition reference remains ten minutes of 《上甘岭》, not automatically corpus-wide ground truth. No additional viewing or relabelling was requested.

The adaptive window is defined in frames, so digital frame intervals may also affect scores. Per-film median/p95 presentation intervals are retained, with `studio_frame_cadence.csv` as an additional table. They describe the current digital files' decoded cadence, not original camera/projection frame rates. The proportion of adjacent pairs with zero V-channel difference is also preserved and is not equated with exact duplication of full-colour frames.

An additional A–B–A return flag marks candidates whose small gray images at approximately 0.12 seconds before/after differ by ≤0.03 while the intervening peak difference is ≥0.10. Primary-table cuts remain unchanged. The pattern could be a flash, a real short insert or movement. Only flag rates and exclusion sensitivity are reported, not a verified false-positive rate.

The rules also retain digital near-black holds: ROI mean≤12/255, standard deviation≤0.04, lasting ≥0.08 seconds. These are explicitly thresholded pixel/time properties whose original frames can be inspected. They are not equivalent to actual fades, photographic black frames or narrative pauses. Predicted transition-type counts remain in per-film tables without validation as actual type distributions.

## Outputs and reproduction

Run directory: `{run}`. Current grouping directory: `{out}`. Per-film `frame_features.npz`, `cut_candidates.json`, `gradual_*.json`, `summary.json` and `run.json` bind complete-video SHA, original PTS, software and parameters. Complete coverage and studio CSV files, timeline PNG/PDF files and preflight results are preserved. Final numerical audits and assistant image inspections are recorded separately. Neither is presented as independent human accuracy validation across the corpus.
'''


if __name__=='__main__':main()
