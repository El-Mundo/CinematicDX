"""Aggregate completed corpus measurements at film level and publish studio evidence."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
os.environ.setdefault('MPLCONFIGDIR','/tmp/cinematicdx-mpl')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from cinematicdx.corpus_luminance import representation_intervals,bin_samples,finite_change
from cinematicdx.corpus_studio_analysis import group_statistics,grouped_profile,year_cell_residuals,weighted_mean,resolve_job_film_keys
from cinematicdx.exploration import correlation

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x
def write(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csv_file(p,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in clean(rows):writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
def fmt(x,n=3):return '—' if x is None else f'{x:.{n}f}'


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--report-directory',type=Path);p.add_argument('--output-directory',type=Path);p.add_argument('--source-diagnostic-directory',type=Path);args=p.parse_args();run=args.run.absolute()
    plan=read(run/'plan.json');config=read(run/'config.json');done=read(run/'extraction_complete.json')
    assert len(done['completed'])+len(done['failed'])==len(plan['jobs'])
    assert sha(plan['metadata_path'])==plan['metadata_sha256']
    out=args.output_directory.absolute() if args.output_directory else run/'analysis';out.mkdir(exist_ok=False)
    jobs_by_key=defaultdict(list);raw_jobs_by_key=defaultdict(list);documents={};version_keys=defaultdict(set);original_version_keys=defaultdict(set);profile_lookup={};samples_lookup={}
    for job in plan['jobs']:
        raw_jobs_by_key[job['film_key']].append(job)
        path=run/'films'/job['job_id']/'summary.json'
        if path.exists():
            receipt=read(path.with_name('run.json'))
            for name,v in receipt['outputs'].items():assert sha(path.with_name(name))==v['sha256']
            doc=read(path);documents[job['job_id']]=doc;original_version_keys[doc['video_version_id']].add(job['film_key'])
    override_path=run/'identity_overrides.json';overrides=read(override_path) if override_path.exists() else {}
    if overrides and overrides['metadata_sha256']!=plan['metadata_sha256']:raise ValueError('Identity overrides refer to changed metadata.')
    resolved_jobs=resolve_job_film_keys(plan['jobs'],documents,overrides,{f['film_key'] for f in plan['films']})
    for job in resolved_jobs:
        jobs_by_key[job['film_key']].append(job)
        if job['job_id'] in documents:version_keys[documents[job['job_id']]['video_version_id']].add(job['film_key'])
    conflicts={version:sorted(keys) for version,keys in version_keys.items() if len(keys)>1}
    films=[];version_rows=[]
    for record in plan['films']:
        jobs=jobs_by_key.get(record['film_key'],[]);success=[j for j in jobs if j['job_id'] in documents]
        film=dict(record,video_available=bool(jobs),measured=bool(success),eligible=False,
                  status=('mislabelled_source_no_valid_video' if raw_jobs_by_key.get(record['film_key']) else 'missing_video') if not jobs else 'extraction_failed',
                  source_files_measured=len(success),source_versions_measured=len({documents[j['job_id']]['video_version_id'] for j in success}),
                  filename_claimed_video_files=len(raw_jobs_by_key.get(record['film_key'],[])))
        film['original_filename_linkage_available']=film.pop('video_available_by_current_linkage')
        if success:
            # Stable choice independent of measured brightness if multiple versions.
            selected=min(success,key=lambda j:(j['original_film_key']!=record['film_key'],j['relative_path']));doc=documents[selected['job_id']]
            film.update(doc['summary']);film.update(measured=True,eligible=doc['summary']['eligible_for_group_comparison'],
                 video_version_id=doc['video_version_id'],selected_job_id=selected['job_id'],relative_path=selected['relative_path'],
                 linkage_status=selected['linkage_status'],sampling_mode=doc['technical']['mode'],source_width=doc['technical']['width'],source_height=doc['technical']['height'],
                 sample_aspect_ratio=doc['technical']['sample_aspect_ratio'],colour_range=doc['technical']['color_range'],colour_space=doc['technical']['color_space'])
            if doc['video_version_id'] in conflicts:
                film['eligible']=False;film['quality_flags']=film['quality_flags']+['duplicate_bytes_across_film_keys']
            if selected['film_key'] is None:
                film['eligible']=False;film['quality_flags']=film['quality_flags']+['unresolved_identity']
            film['status']='measured_eligible' if film['eligible'] else 'measured_excluded'
            directory=run/'films'/selected['job_id']
            with np.load(directory/'profiles.npz',allow_pickle=False) as z:profile={k:z[k] for k in z.files}
            profile_lookup[film['film_key']]=profile['roi_z']
            film['full_vs_roi_profile_correlation']=correlation(profile['roi_z'],profile['full_z'])
            with np.load(directory/'samples.npz',allow_pickle=False) as z:arrays={k:z[k] for k in ['playback_seconds','full_mean','roi_mean']}
            left,right=representation_intervals(arrays['playback_seconds'],film['duration_seconds']);w=right-left
            mean=np.average(arrays['full_mean'],weights=w);sd=float(np.sqrt(np.average((arrays['full_mean']-mean)**2,weights=w)))
            edges=np.r_[np.arange(0,film['duration_seconds'],30),film['duration_seconds']]
            values,coverage=bin_samples(left,right,arrays['full_mean'],edges);values[coverage<.8]=np.nan;values[np.diff(edges)<15]=np.nan
            delta=finite_change(values);film['full_frame_mean_abs_change_30s_z']=delta/sd if delta is not None and sd>=1e-4 else None
            for scale in [10,60]:
                edges1=np.r_[np.arange(0,film['duration_seconds'],scale),film['duration_seconds']]
                values1,coverage1=bin_samples(left,right,arrays['roi_mean'],edges1);values1[coverage1<.8]=np.nan;values1[np.diff(edges1)<scale/2]=np.nan
                delta1=finite_change(values1);film[f'mean_abs_change_{scale}s_z']=delta1/film['gray_roi_temporal_sd'] if delta1 is not None and film['gray_roi_temporal_sd']>=1e-4 else None
        films.append(film)
        for job in jobs:
            doc=documents.get(job['job_id']);version_rows.append(dict(film_key=record['film_key'],job_id=job['job_id'],relative_path=job['relative_path'],
                original_filename_film_key=job['original_film_key'],filename_identity_corrected=job['original_film_key']!=record['film_key'],
                status='complete' if doc else 'failed',video_version_id=doc['video_version_id'] if doc else None,
                selected_as_primary=film.get('selected_job_id')==job['job_id']))
    residuals,cells=year_cell_residuals(films)
    for film in films:
        r=residuals.get(film['film_key'],{});film['year_colour_type_residual']=r.get('residual');film['year_cell_n']=r.get('cell_n')
    studios={s['studio_id']:s for f in plan['films'] for s in f['studios']}
    groups=[];strata=[];single=[];by_width=[]
    for sid,studio in studios.items():
        common=dict(studio_id=sid,studio=studio['chn'],studio_name=studio['name'],source_category=studio['category'])
        groups.append(dict(common,scope='all_types_all_colours',**group_statistics(films,sid)))
        single.append(dict(common,scope='single_production_only',**group_statistics(films,sid,single_studio=True)))
        group_films=[f for f in films if any(s['studio_id']==sid for s in f['studios'])]
        combinations=sorted({(f['year'],f['colour'] or 'Unknown',f['film_type'] or 'Unknown') for f in group_films})
        for year,colour,kind in combinations:
            pred=lambda f,y=year,c=colour,k=kind:f['year']==y and (f['colour'] or 'Unknown')==c and (f['film_type'] or 'Unknown')==k
            strata.append(dict(common,year=year,colour=colour,film_type=kind,**group_statistics(films,sid,predicate=pred)))
        for width in sorted({f.get('source_width') for f in group_films if f['measured']}):
            by_width.append(dict(common,source_width=width,**group_statistics(films,sid,predicate=lambda f,w=width:f.get('source_width')==w)))
    feature_bw=[];feature_colour=[]
    for sid,studio in studios.items():
        common=dict(studio_id=sid,studio=studio['chn'],studio_name=studio['name'])
        feature_bw.append(dict(common,scope='Feature_BW',**group_statistics(films,sid,predicate=lambda f:f['film_type']=='Feature' and f['colour']=='B&W')))
        feature_colour.append(dict(common,scope='Feature_Colour',**group_statistics(films,sid,predicate=lambda f:f['film_type']=='Feature' and f['colour']=='Colour')))
    profiles=[]
    for scope,predicate in [('all',None),('Feature_BW',lambda f:f['film_type']=='Feature' and f['colour']=='B&W'),('Feature_Colour',lambda f:f['film_type']=='Feature' and f['colour']=='Colour')]:
        for sid,studio in studios.items():
            for row in grouped_profile(films,profile_lookup,sid,predicate=predicate):profiles.append(dict(studio_id=sid,studio=studio['chn'],scope=scope,**row))
    csv_file(out/'film_measurements_and_coverage.csv',films);csv_file(out/'source_versions.csv',version_rows)
    csv_file(out/'studio_summary_all.csv',groups);csv_file(out/'studio_summary_feature_bw.csv',feature_bw);csv_file(out/'studio_summary_feature_colour.csv',feature_colour)
    csv_file(out/'studio_summary_single_production.csv',single);csv_file(out/'studio_year_colour_type.csv',strata);csv_file(out/'studio_source_width_sensitivity.csv',by_width)
    csv_file(out/'studio_temporal_scale_sensitivity.csv',[{k:g[k] for k in ['studio_id','studio','eligible_member_films','mean_abs_change_10s_z__mean','mean_abs_change_30s_z__mean','mean_abs_change_60s_z__mean','core_10_90_mean_abs_change_30s_z__mean']} for g in groups])
    csv_file(out/'year_colour_type_reference_cells.csv',cells);csv_file(out/'studio_relative_timeline.csv',profiles)
    eligible=[f for f in films if f['eligible']];measured=[f for f in films if f['measured']]
    assert abs(sum(g['metadata_fractional_films'] for g in groups)-len(films))<1e-7
    assert abs(sum(g['eligible_fractional_films'] for g in groups)-len(eligible))<1e-7
    source_sample_count=sum(doc['summary']['sample_count'] for doc in documents.values())
    primary_sample_count=sum(f['sample_count'] for f in measured)
    unique_durations={doc['video_version_id']:doc['summary']['duration_seconds'] for doc in documents.values()}
    summary=dict(status='PROVISIONAL',metadata_films=len(films),available_video_files=len(plan['jobs']),distinct_linked_films=len([k for k in jobs_by_key if k is not None]),
        videos_successfully_measured=len(documents),videos_failed=len(done['failed']),measured_films=len(measured),eligible_films=len(eligible),
        missing_video_films=sum(not f['video_available'] for f in films),measured_excluded_films=sum(f['measured'] and not f['eligible'] for f in films),
        total_measured_video_hours=sum(doc['summary']['duration_seconds'] for doc in documents.values())/3600,
        unique_video_version_hours=sum(unique_durations.values())/3600,unique_video_versions=len(unique_durations),
        total_timestamped_samples=primary_sample_count,total_timestamped_file_samples=source_sample_count,studios_in_metadata=len(studios),studios_with_eligible_films=sum(g['eligible_member_films']>0 for g in groups),
        sampling_modes=dict(Counter(doc['technical']['mode'] for doc in documents.values())),fallback_videos=sum(doc['sampling_fallback_performed'] for doc in documents.values()),
        identity_linkage_status_counts=dict(Counter(f.get('linkage_status','no_measured_video') for f in films)),
        duplicate_bytes_cross_key_conflicts=conflicts,original_filename_duplicate_conflicts={v:sorted(keys) for v,keys in original_version_keys.items() if len(keys)>1},
        derived_identity_overrides_used=bool(overrides),identity_override_sha256=sha(override_path) if override_path.exists() else None,
        film_type_measured_counts=dict(Counter(f['film_type'] for f in measured)),
        colour_measured_counts=dict(Counter(f['colour'] or 'Unknown' for f in measured)),
        quality_flag_counts=dict(Counter(flag for f in measured for flag in f.get('quality_flags',[]))),
        minimum_representation_coverage=min(f['temporal_representation_coverage'] for f in measured),
        full_vs_roi_profile_correlation_median=float(np.median([f['full_vs_roi_profile_correlation'] for f in eligible if f['full_vs_roi_profile_correlation'] is not None])),
        extraction_elapsed_seconds=done['elapsed_seconds'],sampling_validation=read(run/'sampling_validation.json'),
        main_metric='Mean absolute adjacent30s mean-gray changes / within-film temporal gray SD.',
        scope='Whole accessible digital corpus under existing provisional filename/credit linkage; not all732 source videos available.',
        interpretive_limit='Descriptive film-level differences; no causal studio style, recovered historical lighting, or full-corpus narrative inference.')
    diagnostic=None
    if args.source_diagnostic_directory:
        diagnostic=read(args.source_diagnostic_directory/'results.json')
        with (args.source_diagnostic_directory/'studio_chroma_flag_sensitivity.csv').open(encoding='utf-8-sig') as f:diagnostic['studio_sensitivity']=list(csv.DictReader(f))
        summary['post_result_source_quality_diagnostic']=dict(directory=str(args.source_diagnostic_directory.absolute()),
            successful=diagnostic['successful'],failures=diagnostic['failures'],sampled_frame_count=diagnostic['sampled_frame_count'],
            flagged_bw_count=diagnostic['flagged_bw_count'],results_sha256=sha(args.source_diagnostic_directory/'results.json'),
            warning='Chroma flags include tint and do not establish original colour process or justify relabelling.')
    write(out/'summary.json',summary)
    plot_results(out,groups,feature_bw,feature_colour,profiles,films)
    write_report(run,out,summary,groups,feature_bw,feature_colour,single,films,report_directory=args.report_directory,diagnostic=diagnostic)
    snapshots=out/'source_snapshot';snapshots.mkdir()
    sources=[Path(__file__),ROOT/'analysis-python/cinematicdx/corpus_luminance.py',ROOT/'analysis-python/cinematicdx/corpus_studio_analysis.py',
         ROOT/'research/quantitative_exploration/scripts/run_corpus_luminance.py',ROOT/'research/quantitative_exploration/scripts/validate_corpus_reference.py',
         ROOT/'analysis-python/tests/test_corpus_luminance.py',ROOT/'analysis-python/tests/test_corpus_studio_analysis.py',
         ROOT/'research/quantitative_exploration/scripts/check_corpus_colour_labels.py',ROOT/'research/quantitative_exploration/scripts/inspect_corpus_sources.py',
         ROOT/'research/quantitative_exploration/scripts/audit_studio_corpus.py']
    for source in sources:shutil.copy2(source,snapshots/source.name)
    artifacts=[p for p in out.rglob('*') if p.is_file()]
    write(out/'run.json',dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),metadata_sha256=plan['metadata_sha256'],plan_sha256=sha(run/'plan.json'),config_sha256=sha(run/'config.json'),identity_override_sha256=sha(override_path) if override_path.exists() else None,
         corpus_extraction_sha256=sha(run/'extraction_complete.json'),sources={str(p.relative_to(ROOT)):{'sha256':sha(p)} for p in sources},
         outputs={str(p.relative_to(out)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in artifacts},
         raw_source_videos_modified=False,metadata_modified=False,original_annotations_modified=False))
    print(json.dumps(clean(summary),ensure_ascii=False))


def plot_results(out,groups,bw,colour,profiles,films):
    font='/System/Library/Fonts/STHeiti Light.ttc';font_manager.fontManager.addfont(font);plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'axes.unicode_minus':False,'font.size':10})
    def save(fig,name):
        fig.savefig(out/(name+'.png'),dpi=170,bbox_inches='tight');fig.savefig(out/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
    shown=sorted([g for g in groups if g['metadata_member_films']>=10],key=lambda g:g['metadata_member_films'],reverse=True)
    x=np.arange(len(shown));fig,ax=plt.subplots(figsize=(12,5))
    ax.bar(x,[g['metadata_member_films'] for g in shown],color='#d9dee4',label='Metadata member films (co-productions may belong to several studios)')
    ax.bar(x,[g['measured_member_films'] for g in shown],color='#245a81',label='Measurable video available')
    ax.set_xticks(x,[g['studio'] for g in shown],rotation=45,ha='right');ax.set_ylabel('Member films');ax.legend(fontsize=8);ax.set_title('Production-institution coverage\nMissing-film distribution affects comparability');fig.tight_layout();save(fig,'studio_coverage')
    figures=[('all',groups,'All types / colours'),('Feature_BW',bw,'Features / B&W'),('Feature_Colour',colour,'Features / Colour')]
    for scope,rows,label in figures:
        chosen=sorted([g for g in rows if g['eligible_member_films']>=10],key=lambda g:g['mean_abs_change_30s_z__mean'],reverse=True)
        if not chosen:continue
        fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(chosen));means=np.asarray([g['mean_abs_change_30s_z__mean'] for g in chosen])
        ax.plot(x,means,'o',color='#245a81',label='Equal film weights / fractional co-production weights')
        for i,g in enumerate(chosen):
            ax.vlines(i,g['mean_abs_change_30s_z__q25'],g['mean_abs_change_30s_z__q75'],color='#8fa4b7',lw=4)
        ax.set_xticks(x,[g['studio']+'\nn='+str(g['eligible_member_films']) for g in chosen],rotation=35,ha='right')
        ax.set_ylabel('Adjacent 30-second mean change /\nwithin-film temporal gray SD');ax.set_title(label+'\nVertical lines: film IQRs, not population confidence intervals');ax.legend(fontsize=8);fig.tight_layout();save(fig,'studio_change_'+scope)
        curve_rows=[]
        for g in chosen:
            rows1=[r for r in profiles if r['studio_id']==g['studio_id'] and r['scope']==scope]
            curve_rows.append([np.nan if r['studio_z_mean'] is None else r['studio_z_mean'] for r in rows1])
        fig,ax=plt.subplots(figsize=(12,max(4,len(chosen)*.42)));image=ax.imshow(curve_rows,aspect='auto',cmap='RdBu_r',vmin=-1.5,vmax=1.5,extent=[0,100,len(chosen)-.5,-.5])
        ax.set_yticks(range(len(chosen)),[g['studio'] for g in chosen]);ax.set_xlabel('Relative film position / % (not predefined narrative acts)');ax.set_title(label+': within-film standardised gray-level profiles');fig.colorbar(image,ax=ax,label='Studio-weighted mean of within-film z scores');fig.tight_layout();save(fig,'studio_timeline_'+scope)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,metric,label in [(axes[0],'gray_roi_time_mean','Digital gray-level mean'),(axes[1],'mean_abs_change_30s_z','30-second change / within-film SD')]:
        for colour_value,c in [('B&W','#555e6a'),('Colour','#a26874')]:
            group=[f for f in films if f['eligible'] and f['colour']==colour_value];ax.scatter([f['year'] for f in group],[f[metric] for f in group],s=12,alpha=.4,color=c,label=colour_value)
        ax.set_xlabel('Production year (metadata)');ax.set_ylabel(label);ax.legend()
    fig.suptitle('Year and colour composition: alternative explanations for studio differences require examination');fig.tight_layout();save(fig,'year_colour_distributions')


def write_report(run,out,s,groups,bw,colour,single,films,*,report_directory=None,diagnostic=None):
    doc=report_directory or ROOT/'research/quantitative_exploration/corpus_studio';doc.mkdir(parents=True,exist_ok=True)
    rows=sorted([g for g in groups if g['eligible_member_films']>=10],key=lambda g:g['mean_abs_change_30s_z__mean'],reverse=True)
    table='| Production institution | Metadata/video available/included | Mean relative 30-second change | Central 10–90% | Year×colour×type centred residual |\n|---|---:|---:|---:|---:|\n'
    for g in rows:table+=f"| {g['studio']} | {g['metadata_member_films']}/{g['available_member_films']}/{g['eligible_member_films']} | {fmt(g['mean_abs_change_30s_z__mean'])} | {fmt(g['core_10_90_mean_abs_change_30s_z__mean'])} | {fmt(g['year_colour_type_residual__mean'])} (n={g['year_colour_type_residual__film_n']}) |\n"
    type_table='| Type | Measured films |\n|---|---:|\n'+''.join(f'| {k} | {v} |\n' for k,v in s['film_type_measured_counts'].items())
    colour_table='| Colour field | Measured films |\n|---|---:|\n'+''.join(f'| {k} | {v} |\n' for k,v in s['colour_measured_counts'].items())
    compare=[]
    for g in rows:
        b=next(x for x in bw if x['studio_id']==g['studio_id']);c=next(x for x in colour if x['studio_id']==g['studio_id']);one=next(x for x in single if x['studio_id']==g['studio_id'])
        compare.append(f"| {g['studio']} | {fmt(g['mean_abs_change_30s_z__mean'])} | {fmt(b['mean_abs_change_30s_z__mean'])} (n={b['eligible_member_films']}) | {fmt(c['mean_abs_change_30s_z__mean'])} (n={c['eligible_member_films']}) | {fmt(one['mean_abs_change_30s_z__mean'])} |")
    sensitivity='| Production institution | All | B&W features | Colour features | Single-studio films |\n|---|---:|---:|---:|---:|\n'+'\n'.join(compare)
    common_low=max(g['mean_abs_change_30s_z__q25'] for g in rows);common_high=min(g['mean_abs_change_30s_z__q75'] for g in rows)
    mean_low=min(g['mean_abs_change_30s_z__mean'] for g in rows);mean_high=max(g['mean_abs_change_30s_z__mean'] for g in rows)
    reuse_path=run/'measurement_reuse.json'
    refresh_text=''
    if reuse_path.exists():
        reuse=read(reuse_path)
        refresh_text=f"This version update re-extracted {len(reuse['new_job_ids'])} source files and inherited existing measurements for {len(reuse['inherited_jobs'])} source files. The reuse manifest retains the original run directory, receipt SHA and video version. Old and new extractions use identical measurement parameters. See this run's `plan.json` and the parent directory's `refresh.json` for the source manifest and update record."
    duplicate_count=len(s.get('original_filename_duplicate_conflicts',{}))
    unresolved_count=len(s['duplicate_bytes_cross_key_conflicts'])
    identity_text=f"This source-version check recorded {duplicate_count} groups of duplicate byte versions across film keys and {unresolved_count} unresolved conflicts in the analysis mapping. Per-file versions and selections are in `source_versions.csv`. Identity corrections apply only to versions matching their expected video SHA."
    scale_text=[]
    for scale in [10,30,60]:
        metric=f'mean_abs_change_{scale}s_z__mean'
        ordered=sorted([g for g in rows if g[metric] is not None],key=lambda g:g[metric],reverse=True)
        scale_text.append(f"the three highest groups at {scale} seconds are "+', '.join(g['studio'] for g in ordered[:3]))
    residual_text='; '.join(f"{g['studio']} {fmt(g['year_colour_type_residual__mean'])} (n={g['year_colour_type_residual__film_n']})" for g in rows if g['studio'] in ['上海电影制片厂','珠江电影制片厂'])
    history_text=''
    if (run/'analysis_revision2').is_dir():
        history_text='The earlier `analysis/` and `analysis_revision2/` directories retain prior analyses of this run. The current tables are in the directory specified above.'
    diagnostic_text='No additional colour-label diagnostic was run.'
    if diagnostic:
        drows=[x for x in diagnostic['studio_sensitivity'] if x['scope']=='all' and int(x['original_member_n'])>=10 and x['mean_change_after_exclusion']]
        change=max(abs(float(x['mean_change_after_exclusion'])) for x in drows)
        diagnostic_text=f'''Sampling found clearly multicoloured frames in 《刘三姐》, although its metadata label is B&W. Subsequent opening-credit inspection identified 《刘三姐》, 长春电影制片厂 and director 苏里, consistent with the existing record. No year was read. This observation independently establishes neither the original colour process nor a basis for automatic relabelling.

A subsequent **post-result source diagnostic** sampled fixed 20%/50%/80% positions in all {diagnostic['successful']} films, totalling {diagnostic['sampled_frame_count']} frames. Stronger-chroma flags occurred in {diagnostic['flagged_bw_count']} B&W-labelled videos. Earlier contact sheets show both clearly multicoloured images and nearly monochrome images with purple/green casts. Current per-film flags indicate digital chroma requiring inspection. The chroma rule has no independent human accuracy estimate, and absence of a flag does not establish that an entire film is B&W. The diagnostic remains PROVISIONAL. Original metadata, the main analysis and all films remain intact.

Used only as exclusion sensitivity, these flags change the primary 30-second studio means by at most {change:.6f} in absolute value among groups with at least 10 films. See `colour_label_qa/studio_chroma_flag_sensitivity.csv` for B&W, B&W-feature and all-type results. This indicates limited numerical sensitivity of these means to this exclusion operation, not unbiased colour/year strata across sources.'''
    report=f'''# CinematicDX: corpus-wide digital gray-level change by production institution

Status **PROVISIONAL**: coverage and numerical extraction have actual outputs and checks. Historical and institutional interpretation remains exploratory rather than a causal or general studio-style conclusion.

## Actual coverage

- Metadata: {s['metadata_films']} films. Available video files: {s['available_video_files']}. Successful extractions: {s['videos_successfully_measured']}. Failures: {s['videos_failed']}.
- No measurements were invented for the {s['missing_video_films']} metadata records lacking local video. Quality/identity exclusions: {s['measured_excluded_films']}. Final film-level comparison: {s['eligible_films']} films.
- Actual file processing covered about {s['total_measured_video_hours']:.2f} hours. Primary-film observations retain {s['total_timestamped_samples']:,} original PTS samples ({s['total_timestamped_file_samples']:,} samples extracted from {s['available_video_files']} files). Metadata contains {s['studios_in_metadata']} specific production institutions, of which {s['studios_with_eligible_films']} have included films.
- Processing duration counts {s['available_video_files']} files. After deduplication, {s.get('unique_video_versions',s['measured_films'])} digital byte versions cover about {s.get('unique_video_version_hours',s['total_measured_video_hours']):.2f} hours. Identity corrections use an evidence-preserving analysis mapping without changing original filenames or metadata.
- Identity associations based on existing unique filenames remain provisional. Four ambiguous same-title cases use earlier assistant opening-credit checks and file SHA. Not every film has independent human opening-credit identity validation.
- Videos, metadata and original Excel files serve only as inputs. Extraction and analysis run locally.

{refresh_text}

{identity_text}

{type_table}

{colour_table}

## Definition of studios

Specific institutional names in `production` remain distinct rather than being replaced by the regional/collective categories in `category`. 东北电影制片厂 and 长春电影制片厂, and Shanghai, Tianma and Haiyan, retain their separate metadata entries without an imposed institutional genealogy. Co-productions receive weight 1/k per institution. Films are not weighted by frame count or duration. Member counts can overlap across studios, while fractional weights across all institutions still sum to the included-film count. Single-studio and colour/type sensitivities are reported separately.

## Measurement and validation

Uniform approximately 1Hz reference-frame sampling preserves original PTS/time_base. Gray images have width<=160 with a fixed crop of 5% on each side and 10% at top/bottom. Full-frame measurements provide a sensitivity check. There is no per-frame histogram equalisation or claim to recover original photographic brightness. Nearest-observation temporal representation is capped at 5 seconds. Missing observations are not filled with 0, and inadequate coverage is not silently included.

The primary statistic is **the mean absolute difference between adjacent 30-second ROI gray-level means, divided by the film's temporal gray-level standard deviation**. It describes relatively slow gray-level variation, not a cutting rate, narrative-event detection or optical flow per second. Normalisation cannot eliminate differences in nonlinear tone mapping, scanning, restoration, compression or content composition.

The initial keyframe-only method passed only 21 of 24 fixed real validation clips because sparsely encoded sources introduced bias. The original failure and code are archived. Uniform reference-frame sampling retained the original thresholds and passed 24/24 clips. Compared with complete-decoding 1Hz sampling, the median 30-second mean error was {s['sampling_validation']['median_30s_bin_mae']:.6f} and the maximum {s['sampling_validation']['max_30s_bin_mae']:.6f}. This is neither frame-complete full-film ground truth nor historical-brightness calibration, and it does not cover every unknown transfer workflow.

## Main studio table (at least 10 included member films)

{table}

Higher values indicate more variation at the 30-second scale relative to the film's overall gray-level range. They cannot directly mean “brighter,” “more tense” or “more political.” The table is a descriptive ordering of current digital versions. Small institutional samples remain in the complete CSV without ranking their strength.

Year×colour×type residuals are differences from the mean for films with the same year, colour and type. They are computed only for cells containing at least 5 films and at least 2 institutions. The reported n is the available-film count. This is sensitivity to an alternative explanation, not an identified causal studio effect. Cinematographers, subjects, restoration batches and all source differences have not been matched.

## Composition and sensitivity

{sensitivity}

Absolute digital gray-level means for all institutions are descriptive and cannot independently explain historical lighting across studios. B&W/Colour and Feature/Opera/Artistic Documentary/Performance/Musical remain separate. CSV files preserve year details, source pixel widths and the 10/30/60-second scales without selecting the most favourable scale. The central 10–90% analysis is only an endpoint/opening/ending sensitivity check, not automatic identification of the narrative body. Single-studio means that metadata lists one production entry, not that all historical collaboration is known.

The 100-position-bin curves aggregate equally weighted, within-film-standardised profiles with fractional co-production weights. Relative position is a coordinate, not an assumed four-act structure or fixed narrative stage. Interquartile ranges across films show sample heterogeneity, not population confidence intervals or significance from independent frames.

## What these results support

1. For the {len(rows)} institutions with at least 10 films, the primary means range from {mean_low:.3f}–{mean_high:.3f}, a span of {mean_high-mean_low:.3f}. Their interquartile ranges across films share an overlap at {common_low:.3f}–{common_high:.3f}. A studio mean cannot replace within-studio variation. Overlap is not a significance test establishing “no difference.”
2. **Temporal-scale comparison**: {'; '.join(scale_text)}. `studio_temporal_scale_sensitivity.csv` preserves complete means at every scale. Each comparison concerns digital gray-level change at its specified timescale.
3. **Composition-conditioned comparison**: the same-year×colour×type centred residuals include {residual_text}. Each conditional comparison uses its own matchable film subset and still requires interpretation alongside subject, cinematographer and copy provenance.
4. Within-film profiles preserve positional differences lost in means. Brighter openings/endings in several groups are patterns for further investigation only. No independent opening/ending or event annotations were made here. Relative positions cannot be named as narrative stages, and co-occurrence is not treated as an institutional functional principle.

## Source-quality counterexample and supplementary checks

{diagnostic_text}

## Key limitations

1. Acquisition and preservation shape the visible sample. The {s['missing_video_films']} records lacking valid video are unevenly distributed across studios, so this sample cannot represent the complete population of 732 films.
2. Copy provenance and scanning/restoration histories are largely unknown. Identical encoding/dimensions do not guarantee the same transfer conditions, and within-film z standardisation cannot repair these issues.
3. Institutions intertwine with period, colour format, film type, people/locations and subject distributions. Observed group differences are not independent proof of studio style.
4. Only part of 《上甘岭》 has an independent narrative-event reference. The other films lack full-film narrative ground truth, so macro-level curves must not be treated as narrative structure.
5. Approximately 1Hz sampling and 30-second means overlook rapid flashes, short transitions and frame-level jitter. The project's hard-cut/gradual tasks remain separately validated.
6. File SHA identifies digital byte versions rather than authenticating historical copies. Provisional identity mappings remain marked. Original-filename mapping found {len(s.get('original_filename_duplicate_conflicts',{}))} groups of duplicate bytes across films, with {len(s['duplicate_bytes_cross_key_conflicts'])} currently unresolved conflicts.
7. “Full film” means the complete local-file timeline, not a verified complete historical release. Platform introductions, logos, subtitles, endings and incomplete versions can affect gray levels. No such content was automatically removed according to the curves.

## Outputs and reproduction

Experiment directory: `{run}`. All {s['available_video_files']} videos have attempt records. Each successful file's summary/samples/profiles/run binds original-file SHA, software, parameters and PTS. The main table, {s['metadata_films']}-film coverage table, year/colour/type and source-size tables, single-studio analyses, all-studio relative timelines and negative validation results are preserved.

Current analysis directory: `{out}`. Complete studio tables, per-film coverage and temporal profiles are respectively `studio_summary_all.csv`, `film_measurements_and_coverage.csv` and `studio_relative_timeline.csv`. PNG/PDF figures are in the same directory. {history_text}

`run_corpus_luminance.py` can resume from completed per-film receipts and rejects reuse after input or parameter changes. `analyse_studio_corpus.py` accepts only inputs whose complete attempt sequence has finished. It does not publish partial results as corpus-wide findings. Output snapshots retain core code and report-generation source.

These remain reproducible measurements of digital formal properties and temporal organisation. Source calibration, independent material and film-historical interpretation are required before institutional or historical arguments can be supported.
'''
    (doc/'REPORT.md').write_text(report);(out/'REPORT.md').write_text(report)
    if report_directory is None:
        with (ROOT/'research/quantitative_exploration/RESEARCH_LOG.md').open('a') as f:f.write(f"\n## {datetime.now(timezone.utc).isoformat()}: corpus-wide production-institution analysis completed\n\n{s['videos_successfully_measured']}/{s['available_video_files']} videos succeeded; {s['eligible_films']} films included and {s['missing_video_films']} metadata records lack video. The corpus covers about {s['total_measured_video_hours']:.2f} hours. Studio reports and coverage tables are in corpus_studio/REPORT.md. Films remain the analysis unit, with fractional co-production weights and year/colour/type sensitivities. Group differences are not interpreted as institutional causes or narrative identification.\n")


if __name__=='__main__':main()
