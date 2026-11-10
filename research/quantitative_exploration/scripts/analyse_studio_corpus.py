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
    ax.bar(x,[g['metadata_member_films'] for g in shown],color='#d9dee4',label='元数据成员片数（合拍可属多厂）')
    ax.bar(x,[g['measured_member_films'] for g in shown],color='#245a81',label='有可测视频')
    ax.set_xticks(x,[g['studio'] for g in shown],rotation=45,ha='right');ax.set_ylabel('影片成员数');ax.legend();ax.set_title('制片机构覆盖率：缺片分布本身影响厂间可比性');fig.tight_layout();save(fig,'studio_coverage')
    figures=[('all',groups,'全部类型／色彩'),('Feature_BW',bw,'故事片／黑白'),('Feature_Colour',colour,'故事片／彩色')]
    for scope,rows,label in figures:
        chosen=sorted([g for g in rows if g['eligible_member_films']>=10],key=lambda g:g['mean_abs_change_30s_z__mean'],reverse=True)
        if not chosen:continue
        fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(chosen));means=np.asarray([g['mean_abs_change_30s_z__mean'] for g in chosen])
        ax.plot(x,means,'o',color='#245a81',label='影片等权／合拍分数权重均值')
        for i,g in enumerate(chosen):
            ax.vlines(i,g['mean_abs_change_30s_z__q25'],g['mean_abs_change_30s_z__q75'],color='#8fa4b7',lw=4)
        ax.set_xticks(x,[g['studio']+'\nn='+str(g['eligible_member_films']) for g in chosen],rotation=35,ha='right')
        ax.set_ylabel('相邻30秒均值变化／本片灰度时间标准差');ax.set_title(label+'：竖线为影片间四分位范围，不是总体置信区间');ax.legend();fig.tight_layout();save(fig,'studio_change_'+scope)
        curve_rows=[]
        for g in chosen:
            rows1=[r for r in profiles if r['studio_id']==g['studio_id'] and r['scope']==scope]
            curve_rows.append([np.nan if r['studio_z_mean'] is None else r['studio_z_mean'] for r in rows1])
        fig,ax=plt.subplots(figsize=(12,max(4,len(chosen)*.42)));image=ax.imshow(curve_rows,aspect='auto',cmap='RdBu_r',vmin=-1.5,vmax=1.5,extent=[0,100,len(chosen)-.5,-.5])
        ax.set_yticks(range(len(chosen)),[g['studio'] for g in chosen]);ax.set_xlabel('影片相对位置／%（不是预设叙事幕）');ax.set_title(label+'：片内标准化明暗时间曲线');fig.colorbar(image,ax=ax,label='片内z分数的分厂加权均值');fig.tight_layout();save(fig,'studio_timeline_'+scope)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,metric,label in [(axes[0],'gray_roi_time_mean','数字灰度均值'),(axes[1],'mean_abs_change_30s_z','30秒变化／本片标准差')]:
        for colour_value,c in [('B&W','#555e6a'),('Colour','#a26874')]:
            group=[f for f in films if f['eligible'] and f['colour']==colour_value];ax.scatter([f['year'] for f in group],[f[metric] for f in group],s=12,alpha=.4,color=c,label=colour_value)
        ax.set_xlabel('生产年份（元数据）');ax.set_ylabel(label);ax.legend()
    fig.suptitle('年份与色彩构成：厂间差异的替代解释仍需检查');fig.tight_layout();save(fig,'year_colour_distributions')


def write_report(run,out,s,groups,bw,colour,single,films,*,report_directory=None,diagnostic=None):
    doc=report_directory or ROOT/'research/quantitative_exploration/corpus_studio';doc.mkdir(parents=True,exist_ok=True)
    rows=sorted([g for g in groups if g['eligible_member_films']>=10],key=lambda g:g['mean_abs_change_30s_z__mean'],reverse=True)
    table='| 制片机构 | 元数据／有视频／纳入 | 30秒相对变化均值 | 中央10–90% | 年份×色彩×类型中心化残差 |\n|---|---:|---:|---:|---:|\n'
    for g in rows:table+=f"| {g['studio']} | {g['metadata_member_films']}/{g['available_member_films']}/{g['eligible_member_films']} | {fmt(g['mean_abs_change_30s_z__mean'])} | {fmt(g['core_10_90_mean_abs_change_30s_z__mean'])} | {fmt(g['year_colour_type_residual__mean'])}（n={g['year_colour_type_residual__film_n']}） |\n"
    type_table='| 类型 | 实测影片 |\n|---|---:|\n'+''.join(f'| {k} | {v} |\n' for k,v in s['film_type_measured_counts'].items())
    colour_table='| 色彩字段 | 实测影片 |\n|---|---:|\n'+''.join(f'| {k} | {v} |\n' for k,v in s['colour_measured_counts'].items())
    compare=[]
    for g in rows:
        b=next(x for x in bw if x['studio_id']==g['studio_id']);c=next(x for x in colour if x['studio_id']==g['studio_id']);one=next(x for x in single if x['studio_id']==g['studio_id'])
        compare.append(f"| {g['studio']} | {fmt(g['mean_abs_change_30s_z__mean'])} | {fmt(b['mean_abs_change_30s_z__mean'])}（n={b['eligible_member_films']}） | {fmt(c['mean_abs_change_30s_z__mean'])}（n={c['eligible_member_films']}） | {fmt(one['mean_abs_change_30s_z__mean'])} |")
    sensitivity='| 制片机构 | 全部 | 故事片黑白 | 故事片彩色 | 单厂片 |\n|---|---:|---:|---:|---:|\n'+'\n'.join(compare)
    common_low=max(g['mean_abs_change_30s_z__q25'] for g in rows);common_high=min(g['mean_abs_change_30s_z__q75'] for g in rows)
    mean_low=min(g['mean_abs_change_30s_z__mean'] for g in rows);mean_high=max(g['mean_abs_change_30s_z__mean'] for g in rows)
    reuse_path=run/'measurement_reuse.json'
    refresh_text=''
    if reuse_path.exists():
        reuse=read(reuse_path)
        refresh_text=f"本次版本更新重新提取{len(reuse['new_job_ids'])}个源文件，继承{len(reuse['inherited_jobs'])}个源文件的既有测量。继承清单保留原运行目录、原收据SHA和视频版本；新旧提取使用相同测量参数。来源清单与更新记录见本次运行的`plan.json`及上级目录`refresh.json`。"
    duplicate_count=len(s.get('original_filename_duplicate_conflicts',{}))
    unresolved_count=len(s['duplicate_bytes_cross_key_conflicts'])
    identity_text=f"本次源版本检查记录{duplicate_count}组跨影片key的重复字节版本，分析映射中未解决冲突{unresolved_count}组。逐文件版本和选择结果见`source_versions.csv`。身份修正仅应用于匹配其预期视频SHA的版本。"
    scale_text=[]
    for scale in [10,30,60]:
        metric=f'mean_abs_change_{scale}s_z__mean'
        ordered=sorted([g for g in rows if g[metric] is not None],key=lambda g:g[metric],reverse=True)
        scale_text.append(f"{scale}秒最高三组为"+'、'.join(g['studio'] for g in ordered[:3]))
    residual_text='；'.join(f"{g['studio']}{fmt(g['year_colour_type_residual__mean'])}（n={g['year_colour_type_residual__film_n']}）" for g in rows if g['studio'] in ['上海电影制片厂','珠江电影制片厂'])
    history_text=''
    if (run/'analysis_revision2').is_dir():
        history_text='此前的`analysis/`和`analysis_revision2/`保存本运行的早期分析，当前表的路径以上述目录为准。'
    diagnostic_text='未运行额外色彩标签诊断。'
    if diagnostic:
        drows=[x for x in diagnostic['studio_sensitivity'] if x['scope']=='all' and int(x['original_member_n'])>=10 and x['mean_change_after_exclusion']]
        change=max(abs(float(x['mean_change_after_exclusion'])) for x in drows)
        diagnostic_text=f'''抽样发现《刘三姐》的元数据为B&W，但实际帧有明显多色内容；随后片头读取到《刘三姐》、长春电影制片厂、导演苏里，与现有条目相符，未读到年份。此观察不独立证明原始色彩工艺，也不自动改标签。

随后固定全{diagnostic['successful']}片20%/50%/80%位置、共{diagnostic['sampled_frame_count']}帧作**事后来源诊断**：{diagnostic['flagged_bw_count']}个B&W标签视频出现较强色度旗标。此前接触表可见明显多色画面及紫/绿色偏的近单色画面；当前旗标逐片列在诊断结果中，表示需检查的数字色度。色度规则未取得独立人工准确率；无旗标也不证明全片黑白。标为PROVISIONAL，原始元数据、主分析与所有影片均保留。

将这些旗标仅作为排除敏感性，在至少10片的厂组中，30秒主均值最大绝对改变量{change:.6f}；详细B&W、故事片B&W和全类型结果见`colour_label_qa/studio_chroma_flag_sensitivity.csv`。这说明本次主均值对该排除操作的数值敏感性较小，不能证明跨来源色彩/年份分层已无偏。'''
    report=f'''# CinematicDX：全语料按制片机构分组的数字明暗变化

状态 **PROVISIONAL**：覆盖和数值提取有实际输出/校验；历史及机构解释仍是探索，不是因果或总体风格判定。

## 实际覆盖

- 元数据{s['metadata_films']}部；可用视频文件{s['available_video_files']}；成功提取{s['videos_successfully_measured']}；失败{s['videos_failed']}。
- 缺少本地视频的元数据{s['missing_video_films']}部没有被虚构测量；质量/身份排除{s['measured_excluded_films']}部，最终影片级比较{s['eligible_films']}部。
- 实际文件处理约{s['total_measured_video_hours']:.2f}小时；主影片原PTS观察{s['total_timestamped_samples']:,}个（按{s['available_video_files']}个文件提取共{s['total_timestamped_file_samples']:,}个）。元数据{s['studios_in_metadata']}个具体制片机构，{s['studios_with_eligible_films']}个有纳入影片。
- 处理时长按{s['available_video_files']}个文件计算；去重后{s.get('unique_video_versions',s['measured_films'])}个数字字节版本约{s.get('unique_video_version_hours',s['total_measured_video_hours']):.2f}小时。身份修正来自保留证据的分析映射，不改原始文件名或元数据。
- 按现有唯一文件名关联的身份仍暂定，四处同名片使用此前助手片头核对及文件SHA。不是所有影片都取得独立人类片头身份验证。
- 视频、元数据和原始Excel仅作输入；提取与分析在本地执行。

{refresh_text}

{identity_text}

{type_table}

{colour_table}

## 制片厂如何定义

使用`production`的具体机构名称，不用`category`地区/集合类别代替。东北电影制片厂与长春电影制片厂、上海与天马与海燕均按原元数据分别保留，不自行合并机构谱系。合拍片对每个机构分配1/k权重，影片不是按帧数/片长加权。成员片数可跨厂重复，分数权重在全机构上合计仍等于纳入影片数。单厂片和色彩/类型敏感性另报。

## 测量与验证

统一约1Hz参考帧采样，保留原PTS/time_base；宽<=160灰度，固定左右5%/上下10%裁切，全画面为敏感性。不作每帧直方图均衡，不声称恢复原版摄影亮度。最近观察的时间代表范围有5秒上限；缺测不填0，覆盖不足不静默纳入。

主统计量是**相邻30秒ROI灰度均值之差的绝对值取平均，再除以本片灰度时间标准差**。它描述相对慢速的明暗变化，不是切换率、叙事事件检测或单位秒光流。归一化不能消除非线性色调、扫描、修复、压缩和内容构成差异。

初始仅关键帧方法在24段固定真实验证片段中仅21段通过，稀疏编码片源造成偏差；原失败与代码封存。统一参考帧方案保持原阈值，24/24段通过，相较完整解码1Hz，30秒均值误差中位{s['sampling_validation']['median_30s_bin_mae']:.6f}、最大{s['sampling_validation']['max_30s_bin_mae']:.6f}。该验证不等于全片逐帧或历史亮度真值，也不涵盖每一种未知转录工作流。

## 分厂主表（至少10部纳入成员片）

{table}

较大的值表示相对于本片总体明暗跨度，30秒尺度上起伏较多；不能直接翻译为“更明亮”“更紧张”“政治性更强”。表为现有数字版本的描述性排序，小样本机构仍在完整CSV中，但不排强弱。

年份×色彩×类型残差是相对同年、同色彩、同类型影片均值的差；仅在该单元至少5片且至少2个机构时计算，n是可用影片数。它是替代解释敏感性，不是识别出的制片厂因果效应。未匹配摄影师、题材、修复批次或全部来源差异。

## 构成与敏感性

{sensitivity}

全部机构的数字灰度绝对均值仅作描述，不能凭其跨厂解释历史照明。黑白/彩色、故事片/戏曲/艺术纪录/演出/歌舞均分别保留；年份明细、源像素宽度及10/30/60秒尺度明细见CSV，不按有利尺度择优。片中中央10–90%的分析只是一项端点/片头片尾敏感性，不是自动识别叙事主体。单厂指元数据只列一个production条目，不是对完整合作关系的历史判定。

100位置箱曲线按影片等权及合拍分数权重汇总，每片先标准化；相对位置是坐标，不假定四幕或固定叙事阶段。图上影片间四分位范围表示样本异质性，不是总体置信区间或独立帧显著性。

## 本次结果支持什么

1. 至少10片的{len(rows)}家机构主均值为{mean_low:.3f}–{mean_high:.3f}，跨度{mean_high-mean_low:.3f}。各自影片间四分位区间在{common_low:.3f}–{common_high:.3f}有共同重叠；同厂差异不能被厂均值替代。重叠不是“无差异”的显著性检验。
2. **时间尺度比较**：{'；'.join(scale_text)}。各尺度的完整均值保留在`studio_temporal_scale_sensitivity.csv`，比较单位为具体时间尺度上的数字灰度变化。
3. **构成条件比较**：同年×色彩×类型中心化残差中，{residual_text}。这些条件比较使用各自可匹配的影片子集，仍需结合题材、摄影师和拷贝来源解释。
4. 片内时间曲线保存了平均值丢失的位置差异；多组曲线首尾偏亮只宜作为待查模式。当前未作独立片头/片尾或事件标注，不能据相对位置命名叙事阶段，也不将共现当制片厂功能原则。

## 来源质量反例与补充检查

{diagnostic_text}

## 关键局限

1. 可见样本受获取与保存影响：{s['missing_video_films']}个无有效视频条目按厂分布并不均匀，不能代表732部完整总体。
2. 拷贝来源/扫描修复历史大多未知；相同编码/尺寸也不保证同一转录条件，片内z标准化不能修复这些问题。
3. 制片机构与年代、色彩制式、影片类型、人物/场所和题材分布交织；观察到的组差异不是厂风格的独立证明。
4. 只有《上甘岭》局部有独立叙事事件参考，本次其余影片没有全片叙事真值；不得把宏观曲线当叙事结构。
5. 约1Hz与30秒均值会忽略快速闪光、短转场和帧级抖动；本项目的硬切/渐变任务依旧单独验证。
6. 文件SHA识别数字字节版本，不证明历史拷贝真实性。身份映射暂定处均有标记；原始文件名映射发现{len(s.get('original_filename_duplicate_conflicts',{}))}组字节跨片重复，当前未解决冲突{len(s['duplicate_bytes_cross_key_conflicts'])}组。
7. “全片”指完整本地文件的时间轴，不证明历史发行版完整。平台片头、台标、字幕、片尾和残缺版都可能影响明暗；没有据曲线自动删除这些内容。

## 输出与复算

实验目录 `{run}`；所有{s['available_video_files']}视频均有尝试记录，成功文件各自的summary/samples/profiles/run绑定原文件SHA、软件、参数与PTS。主表、{s['metadata_films']}部覆盖表、分年份/色彩/类型、来源尺寸、单厂、全厂相对时间曲线及负验证均保留。

当前分析目录 `{out}`。完整分厂表、逐片覆盖表和时间曲线分别为`studio_summary_all.csv`、`film_measurements_and_coverage.csv`、`studio_relative_timeline.csv`；PNG/PDF图在同目录。{history_text}

`run_corpus_luminance.py`可从已完成的逐片收据恢复；不同输入或参数拒绝复用。`analyse_studio_corpus.py`只接受完整尝试结束后的输入，不发布部分结果冒充全库。核心代码和报告生成源码随输出快照保存。

本次仍是可复算的数字形式属性与时间组织证据；需要来源校准、独立材料与电影史解释，才可能支持机构/历史论证。
'''
    (doc/'REPORT.md').write_text(report);(out/'REPORT.md').write_text(report)
    if report_directory is None:
        with (ROOT/'research/quantitative_exploration/RESEARCH_LOG.md').open('a') as f:f.write(f"\n## {datetime.now(timezone.utc).isoformat()}：全语料制片机构分析完成\n\n{s['videos_successfully_measured']}/{s['available_video_files']}视频成功；{s['eligible_films']}影片纳入，{s['missing_video_films']}元数据无视频。全库约{s['total_measured_video_hours']:.2f}小时，分厂报告和覆盖表见corpus_studio/REPORT.md。保持影片为分析单位、合拍分数权重及年份/色彩/类型敏感性，未将组差异解释为机构因果或叙事识别。\n")


if __name__=='__main__':main()
