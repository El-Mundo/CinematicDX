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
    for metric,title,label,name in [('primary_cut_candidates_per_minute','自动硬切候选／分钟','硬切候选：跨片准确率未建立','studio_cut_candidates'),
        ('default_gradual_candidates_per_minute','渐变候选／分钟（不是实测转场频率）','渐变候选诊断：严格区间验证失败，不能作厂风格排名','studio_gradual_candidates')]:
        fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(chosen))
        ax.plot(x,[g[metric+'__mean'] for g in chosen],'o',color='#245a81')
        for i,g in enumerate(chosen):ax.vlines(i,g[metric+'__q25'],g[metric+'__q75'],color='#97a9b8',lw=4)
        ax.set_xticks(x,[g['studio']+'\nn='+str(g['measured_n']) for g in chosen],rotation=35,ha='right')
        ax.set_ylabel(title);ax.set_title(label+'；竖线为影片间四分位范围');fig.tight_layout();save(fig,name)
    for metric,label,name in [('cut_candidates_per_minute__mean','硬切候选／分钟','studio_cut_timeline'),
        ('cut_density_relative_to_film_rate__mean','相对本片平均候选率（1=本片均值）','studio_cut_relative_profile'),
        ('gradual_candidate_starts_per_minute__mean','渐变候选起点／分钟（非真实转场数）','studio_gradual_timeline')]:
        data=[[np.nan if r[metric] is None else r[metric] for r in timeline if r['studio_id']==g['studio_id']] for g in chosen]
        fig,ax=plt.subplots(figsize=(12,5));image=ax.imshow(data,aspect='auto',cmap='viridis',extent=[0,100,len(chosen)-.5,-.5])
        ax.set_yticks(range(len(chosen)),[g['studio'] for g in chosen]);ax.set_xlabel('完整本地文件相对位置／%，不代表叙事幕')
        ax.set_title(label+'；影片等权、合拍分数权重');fig.colorbar(image,ax=ax,label=label);fig.tight_layout();save(fig,name)


def report_text(run,out,s,groups,bw):
    shown=sorted([g for g in groups if g['measured_n']>=10],key=lambda g:g['primary_cut_candidates_per_minute__mean'],reverse=True)
    table='| 制片厂 | 元数据/实测 | 硬切候选/分 | 宽松/严格 | ROI | 黑白故事片（n） | 渐变候选/分* |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for g in shown:
        b=next(x for x in bw if x['studio_id']==g['studio_id'])
        table+=f"| {g['studio']} | {g['metadata_n']}/{g['measured_n']} | {number(g['primary_cut_candidates_per_minute__mean'])} | {number(g['lenient_cut_candidates_per_minute__mean'])}/{number(g['strict_cut_candidates_per_minute__mean'])} | {number(g['roi_cut_candidates_per_minute__mean'])} | {number(b['primary_cut_candidates_per_minute__mean'])}（{b['measured_n']}） | {number(g['default_gradual_candidates_per_minute__mean'])} |\n"
    primary=[r for r in s['preflight']['hard_cut_validation'] if r['detector']=='primary' and r['tolerance_seconds']==.08]
    gprimary=[r for r in s['preflight']['gradual_validation'] if r['detector']=='default' and r['iou']==.5]
    hard_table='| 配置 | 帧号情景 | 匹配/未匹配预测/漏检（±0.08秒） |\n|---|---|---:|\n'
    for r in s['preflight']['hard_cut_validation']:
        if r['tolerance_seconds']==.08:hard_table+=f"| {r['detector']} | {r['scenario_id']} | {r['tp']}/{r['fp']}/{r['fn']} |\n"
    gradual_table='| 配置 | 帧号情景 | tIoU | 匹配/未匹配预测/漏检 |\n|---|---|---:|---:|\n'
    for r in s['preflight']['gradual_validation']:
        if r['iou'] in [.5,.3]:gradual_table+=f"| {r['detector']} | {r['scenario_id']} | {r['iou']} | {r['true_positive']}/{r['false_positive']}/{r['false_negative']} |\n"
    conditional=[]
    for name in ['conditional_studio_reference','conditional_source_width_reference']:
        test=read(out/(name+'.json'))
        if test['status']=='BLOCKED':conditional.append(f"{name}：BLOCKED，{test['reason']}")
        else:conditional.append(f"{name}：{test['film_n']}影片、{test['cell_n']}匹配单元、{test['studio_n']}机构；组间残差份额{test['observed_between_studio_residual_share']:.4f}，999次置换中位{test['null_median']:.4f}，2.5–97.5%参照范围{test['null_q025']:.4f}–{test['null_q975']:.4f}，不小于观察量的参照比例{test['null_at_least_observed_fraction']:.4f}。")
    conditional_text='\n\n'.join(conditional)
    reuse_path=run/'measurement_reuse.json'
    refresh_text=''
    if reuse_path.exists():
        reuse=read(reuse_path)
        refresh_text=f"本次版本更新重新提取{len(reuse['new_job_ids'])}个源文件，继承{len(reuse['inherited_jobs'])}个源文件的逐帧测量。继承清单绑定原运行目录、原收据SHA和视频版本；全部机构统计、时间曲线和条件参照由当前影片表重新计算。来源与更新清单见本次`plan.json`及上级目录`refresh.json`。"
    return f'''# 按制片机构的全可用语料硬切与转场检验

硬切比较状态PROVISIONAL；当前渐变模型用于完整起止定位的主张REJECTED。检测器能输出数值不等于这些数值就是真实转场统计。

## 覆盖与实际计算

{s['metadata_films']}元数据、{s['raw_video_paths']}视频路径，当前{s['distinct_sources_attempted']}个影片源具有全片逐帧测量。成功{s['measured_films']}，失败{s['failed_films']}，无有效视频{s['missing_effective_video_films']}。实际解码{s['decoded_frames']:,}帧、{s['measured_hours']:.2f}小时；{s['studios_with_measured_films']}/{s['studios_in_metadata']}机构有测量。来源对应关系由当前运行的影片key与视频SHA绑定。

{refresh_text}

首次作业失败{s['initial_failed_films']}个，其中{s['recovered_roundoff_films']}个通过保留原缓存的机器精度边界修复补齐。只允许ROI数值在0–1边界外不超过8×float64机器精度时裁回边界，较大偏差/NaN拒绝；原视频SHA、原缓存SHA及真实EOF尾帧重新核验。原失败记录、原`extraction_complete.json`保留，最终覆盖由单独`effective_extraction_complete.json`记录，不将失败悄悄抹掉。

## 测量和验证

硬切为全画面宽≤320的HSV-V逐帧MAD，相对前后各2帧均值的比值≥3且MAD≥15，按原PTS最小间隔0.12秒过滤。比值2.5/3.5与固定ROI分别作敏感性。没有用明暗研究的1Hz采样，没有跳过解码帧，没有按名义帧率造时间。

统一V-only避免了本片此前近灰色色相不稳定造成的大量HSV误检，但可能漏掉V接近、主要色相改变的彩色切点。没有自动依据不可靠的色彩标签切换算法；彩色材料的召回率没有由黑白《上甘岭》验证，黑白故事片分表必须单独读取。0.12秒最短间隔也会抑制极短插镜候选，抑制记录保留。

与原PySceneDetect0.7.1基线在《上甘岭》150–750秒的候选逐点相同。保留两种QuickTime帧号解释，±0.08秒并排除独立人工渐变区间后，两种解释均为{primary[0]['tp']}匹配/{primary[0]['fp']}误报/{primary[0]['fn']}漏检，精确率/召回率{primary[0]['precision']:.4f}。±0.04/0.12秒和其他设置全部保存。验证材料为该片十分钟人工参考，区间先前参与方法开发，QuickTime帧号保留两种起算情景。

渐变为现有端点混合/近黑渐隐渐现规则的全片候选扫描，保留default、strict、fade-only。缓存为BGR2GRAY固定ROI直接16×12，区别于旧64×48缓存；不声称仅优化速度而信号完全不变。复测tIoU≥0.5，两种解释仍为{gprimary[0]['true_positive']}匹配/{gprimary[0]['false_positive']}误报/{gprimary[0]['false_negative']}漏检。原先完整起止定位失败得到保留；全库扫描用于检验候选密度、失败和参数敏感性，**不能推断真实叠化/淡出偏好**。

这里的转场模型只操作化叠化及渐隐/渐现候选，不覆盖划变、虹膜、遮挡等全部转场类型。严格区间未匹配也不等于实际转场不存在；位置候选用途与完整区间分割用途分开。

本地已有TransNetV2严格区间验证也失败；其实际CPU运行15248帧约160秒，线性外推全库逐帧约一周，不因已有模型而发动多日任务。没有下载模型、训练、上传或付费计算。

### 同一人工区间的参数对照

{hard_table}

{gradual_table}

硬切主设置在评分排除区间后预测数与人工数均为45，但仍有2处未匹配预测和2处漏检：总数相同不意味着时间组织正确。已保存的原帧错误图涉及烟雾/爆炸、灰度相近变化和渐变端点附近；助手观察只解释可能的失败机制，不改原标签或依此挑选帧号起算方式。较宽松渐变tIoU可支持局部候选用途，不能替代严格完整起止评价。

还需明确复合转场的计数单位：参考淡出后的近黑→新画面跳变也可能被点检测器记一次。把“淡出—黑场—新镜头”视为一个复合事件，还是分别计淡出、停留及硬切，需要研究协议判断；本次沿用原标注评分，不通过改真值来改善数字。

## 制片厂比较

按production.name保留具体机构，影片等权，合拍1/k，东北/长春等不自动合并。以下仅至少10部实测的机构；全部60机构含缺片留在CSV。机构间样本还受到年份、类型、色彩标签及来源条件影响。

{table}

*渐变列只描述错误尚多的检测器输出，是方法诊断，不是真实转场率排名。完整表另含影片间四分位范围、单厂、年份×色彩×类型及源宽度分层。小样本机构不排名，不用帧数充当独立样本。源宽度也不等同扫描/修复来源。

全库共产生硬切候选{s['total_cut_candidates']:,}、渐变候选{s['total_gradual_candidates']:,}。这两个数量是模型输出，不能相加称为已验证总转场数。硬切落入渐变候选区间的冲突另存，不根据弱渐变模型自动删除硬切。

## 构成条件下的置换参照

只对单厂影片、原实测至少10片机构，取同年×类型×元数据色彩单元（≥5片、≥2机构）。扣除单元均值后比较组间残差份额，在单元内置换影片值999次，种子20261026。第二项再要求源宽度相同，门槛不放宽。合拍片保留在描述表，不在此特定参照中充当独立组成员。

{conditional_text}

这是探索性条件参照，不保证历史材料中的交换性；实际片源、题材、摄影师和机构选择仍可能混杂。尾部比例不证明随机抽样总体规律、制片厂因果效应或某个机构的独特风格。匹配子集与完整描述表的覆盖不同，必须连同n读取。

## 时间组织和可解释范围

每片保存候选原PTS、playback坐标、所有逐帧分数、小尺寸ROI及100位置箱的局部候选率。完整两端硬切限定间隔不包括文件两端；但其间可能有漏检渐变，因此称候选切点限定间隔，不直接称真实平均镜头长度。渐变候选不相交的区间另存为敏感性，仍不是镜头真值。相邻log间隔变化是描述量，未由它识别蒙太奇原则、叙事事件或因果。

同时给出“局部率／本片平均率”的相对曲线（1表示本片均值），分离总体切换量与相对位置分布；零候选影片在该归一化中保持缺测并单报有效n。给定同一候选集合，该曲线不受统一播放速度缩放影响，但不能消除漏检、源剪辑、非均匀变速或最低间隔过滤影响。它不把相对位置命名为叙事阶段。

数字文件片头、片尾、广告/台标、抖动、运动、闪光、色偏、逐帧重复和未知转录流程仍可能触发或掩盖转场。全片指完整本地文件，不证明历史版本完整。独立人类转场参考仍只有《上甘岭》十分钟，没有自动扩展成全库真值；未请求补看或重标。

自适应窗口由帧数定义，因此不同数字帧间隔也可能影响分数；逐片保存实际显示间隔中位/p95，另给`studio_frame_cadence.csv`。这些是当前数字文件的解码节律，不证明原始摄影/放映帧率。相邻V通道差为零的比例也保留，不把它等同全彩帧完全重复。

补充A–B–A返回警示：候选前后约0.12秒的小灰度图差≤0.03、其间峰值差≥0.10时标记，主表切点不删。它既可能是闪光，也可能是真实短插镜或运动；只报告警示率及排除敏感性，不能称已确认误报率。

另保留规则已计算的数字近黑停留：ROI均值≤12/255、标准差≤0.04、连续≥0.08秒。它是明确阈值的像素/时间属性，可查原帧，不等同真实淡出、摄影黑场或叙事停顿。模型预测的转场类别计数也留在逐片表，但未验证为实际类型分布。

## 产物与复算

运行目录`{run}`；当前分组目录`{out}`。逐片`frame_features.npz`、`cut_candidates.json`、`gradual_*.json`、`summary.json`和`run.json`绑定完整视频SHA、原PTS、软件和参数；完整覆盖与分厂CSV、时间轴PNG/PDF及预检结果均保留。最终数值审计和助手图像检查单独记录，二者都不冒充全库独立人类准确率。
'''


if __name__=='__main__':main()
