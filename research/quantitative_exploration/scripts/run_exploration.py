"""Bounded real-film exploration; no database, downloads, training or uploads.

Run from any directory with the existing .venv-m3 and the frozen protocol file.
Intermediate files are published per experiment; a complete receipt is last.
"""
import argparse
import csv
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'analysis-python'))
os.environ.setdefault('MPLCONFIGDIR','/tmp/cinematicdx-mpl')
import numpy as np
import cv2
import av
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter
from PIL import Image,ImageDraw,ImageFont
from cinematicdx import exploration as ex
from cinematicdx.ingest import hash_video,source_state,software_provenance


def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    return value
def write(p,value):Path(p).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def table(p,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in clean(rows):w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
def progress(stage,**extra):print(json.dumps(dict(stage=stage,utc=now(),**extra),ensure_ascii=False),flush=True)
def clock(x,pos=None):return f'{int(x//60):02d}:{int(x%60):02d}'
def fonts():
    font='/System/Library/Fonts/STHeiti Light.ttc'
    if Path(font).is_file():
        font_manager.fontManager.addfont(font);plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'font.size':10})
def savefig(fig,p):
    fig.savefig(p.with_suffix('.png'),dpi=160,bbox_inches='tight');fig.savefig(p.with_suffix('.pdf'),bbox_inches='tight');plt.close(fig)


def q01(out,reference,protocol):
    dest=out/'Q01_editing';dest.mkdir()
    rows=[];results=[];null_arrays={};interval_rows=[]
    for scenario in reference['scenarios']:
        prepared=ex.complete_hard_cut_runs(scenario['hard_cuts'],scenario['gradual_transitions'])
        runs=[[p['duration_seconds'] for p in run] for run in prepared['runs']]
        observed,null=ex.shuffled_sequence_controls(runs,draws=protocol['Q01']['draws'],seed=protocol['Q01']['seed'])
        durations=np.asarray([p['duration_seconds'] for p in prepared['intervals']])
        summaries={key:ex.null_summary(observed[key],[n[key] if n[key] is not None else np.nan for n in null])
                   for key in ['mean_absolute_log_ratio','lag1_log_correlation']}
        for key in summaries:null_arrays[scenario['scenario_id']+'__'+key]=np.asarray([n[key] if n[key] is not None else np.nan for n in null])
        record=dict(scenario_id=scenario['scenario_id'],frame_base=scenario['frame_base'],
                    usable_interval_count=len(durations),contiguous_run_lengths=[len(r) for r in runs],
                    usable_duration_sum_seconds=float(durations.sum()),mean_usable_interval_seconds=float(durations.mean()),
                    median_usable_interval_seconds=float(np.median(durations)),observed=observed,controls=summaries,
                    all_shuffles_preserve_each_run_duration_multiset=True,**prepared)
        results.append(record)
        for key,result in summaries.items():rows.append(dict(scenario_id=scenario['scenario_id'],statistic=key,**result))
        for i,run in enumerate(prepared['runs']):
            interval_rows.extend(dict(scenario_id=scenario['scenario_id'],run_index=i,**p) for p in run)
    write(dest/'results.json',dict(status='PROVISIONAL',property='Temporal ordering of complete hard-cut-bounded intervals',
          results=results,validation='Actual independently annotated timing reference; exact interval/gap checks and distribution-preserving controls.',
          limitation='Finite same-film interval, unresolved player frame basis, no attention/montage/narrative-function inference.'))
    table(dest/'summary.csv',rows);table(dest/'usable_intervals.csv',interval_rows)
    np.savez_compressed(dest/'shuffle_controls.npz',**null_arrays)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    first=results[0]
    for run in first['runs']:
        axes[0].plot([(r['start_seconds']+r['end_seconds'])/2 for r in run],[r['duration_seconds'] for r in run],'o-',ms=3,color='#245a81')
    axes[0].axhline(first['mean_usable_interval_seconds'],color='#a26874',ls='--',label='Mean usable interval')
    axes[0].set_yscale('log');axes[0].xaxis.set_major_formatter(FuncFormatter(clock));axes[0].set_xlabel('Source playback time');axes[0].set_ylabel('Complete hard-cut interval / seconds (log scale)');axes[0].legend()
    ns=null_arrays[reference['scenarios'][0]['scenario_id']+'__mean_absolute_log_ratio']
    axes[1].hist(ns,bins=30,color='#d4dee7');axes[1].axvline(first['observed']['mean_absolute_log_ratio'],color='#c56835',label='Observed order')
    axes[1].set_xlabel('Mean absolute adjacent log-duration difference');axes[1].set_ylabel('Within-block shuffles');axes[1].legend()
    fig.suptitle('Q01: Does ordering add information beyond the duration distribution?');fig.tight_layout();savefig(fig,dest/'sequence_and_controls')
    progress('Q01_complete',counts=[r['usable_interval_count'] for r in results],summary=rows)
    return results


def transition_mask(a,b,reference):
    flags=[]
    for scenario in reference['scenarios']:
        for c in scenario['hard_cuts']:
            if a<c['playback_seconds']<=b:flags.append('manual_hard_cut')
        for g in scenario['gradual_transitions']:
            if min(b,g['end_playback_seconds'])>max(a,g['start_playback_seconds']):flags.append('manual_gradual')
    return sorted(set(flags))


def compare_signal(series,centers,circular,matched,*,window,jitter):
    actual=ex.changes_at(series,np.asarray(centers)+jitter,window=window)
    values=np.asarray([r['absolute_change'] for r in actual]);observed=float(values.mean()) if np.isfinite(values).all() else np.nan
    pool,indices=np.unique(np.round(circular.ravel(),9),return_inverse=True)
    poolvalues=np.asarray([r['absolute_change'] for r in ex.changes_at(series,pool,window=window)])
    controls=poolvalues[indices].reshape(circular.shape)
    all_good=np.isfinite(controls).all(axis=1)
    result=dict(all_events_circular=ex.null_summary(observed,controls[all_good].mean(axis=1)),
                observed_event_count=len(actual),observed_valid_event_count=int(np.isfinite(values).sum()),
                circular_configuration_count=len(circular),cut_matched_status=matched['status'])
    if matched['centers'] is not None:
        event_indices=[s['event_index'] for s in matched['selected_events']]
        selected=values[event_indices];obs=float(selected.mean()) if np.isfinite(selected).all() else np.nan
        pool,indices=np.unique(np.round(matched['centers'].ravel(),9),return_inverse=True)
        pv=np.asarray([r['absolute_change'] for r in ex.changes_at(series,pool,window=window)])
        ctr=pv[indices].reshape(matched['centers'].shape);good=np.isfinite(ctr).all(axis=1)
        result['hard_cut_matched']=ex.null_summary(obs,ctr[good].mean(axis=1))
        result['hard_cut_matched']['event_count']=len(selected)
        result['hard_cut_matched']['mean_event_minus_control']=obs-float(ctr[good].mean()) if good.any() else None
    else:result['hard_cut_matched']=dict(status='BLOCKED',reason=matched.get('reason'))
    return result,actual


def q02(out,arrays,reference,narrative,protocol):
    dest=out/'Q02_timeline';dest.mkdir()
    t=arrays['playback_seconds'];end=(arrays['next_pts']/16000)-.043;frames=arrays['gray_cache']
    centers=[e['start_seconds'] for e in narrative['events'] if e['start_seconds']>150]
    event_ids=[e['event_id'] for e in narrative['events'] if e['start_seconds']>150]
    signals={k:ex.exposure_bins(t,end,arrays[k]) for k in ['roi_mean','full_mean','roi_std']}
    grid=np.arange(150,750,.4);indices=np.searchsorted(t,grid);indices=np.unique(np.clip(indices,0,len(t)-1))
    indices=indices[(t[indices]>=150)&(t[indices]<750)]
    pair_rows=[];started=time.perf_counter()
    for k,(ia,ib) in enumerate(zip(indices,indices[1:])):
        a,b=float(t[ia]),float(t[ib]);quality=transition_mask(a,b,reference)
        feature=ex.image_pair_features(frames[ia],frames[ib],b-a,cv2=cv2)
        if min(feature['previous_gray_std'],feature['next_gray_std'])<.01:quality.append('low_texture')
        if not .2<=b-a<=.6:quality.append('unexpected_pair_duration')
        pair_rows.append(dict(pair_id=f'pair-{k:05d}',start_pts=int(arrays['pts'][ia]),end_pts=int(arrays['pts'][ib]),
             time_base='1/16000',start_seconds=a,end_seconds=b,dt_seconds=b-a,quality_flags=quality,valid_measurement=not quality,**feature))
    progress('Q02_flow_measured',pairs=len(pair_rows),elapsed_seconds=time.perf_counter()-started)
    table(dest/'frame_pair_measurements.csv',pair_rows)
    ps=np.asarray([p['start_seconds'] for p in pair_rows]);pe=np.asarray([p['end_seconds'] for p in pair_rows])
    flow_keys=['mad','flicker_one_minus_correlation','flow_p90_diagonals_per_second','flow_residual_p90_diagonals_per_second','global_translation_diagonals_per_second']
    for key in flow_keys:
        val=np.asarray([p[key] if p['valid_measurement'] and p[key] is not None else np.nan for p in pair_rows])
        signals[key]=ex.exposure_bins(ps,pe,val)
    bin_rows=[]
    for i in range(600):
        row=dict(bin_start_seconds=150+i,bin_end_seconds=151+i)
        for key,s in signals.items():row[key]=s['values'][i];row[key+'__valid_exposure']=s['valid_exposure'][i]
        bin_rows.append(row)
    table(dest/'one_second_measurements.csv',bin_rows)
    np.savez_compressed(dest/'binned_signals.npz',**{k+'__'+q:np.asarray(v) for k,s in signals.items() for q,v in s.items()})
    rows=[];event_rows=[];designs=[];primary_keys=['roi_mean','roi_std','mad','flicker_one_minus_correlation','flow_p90_diagonals_per_second']
    for scenario in reference['scenarios']:
        for w in [5.,3.,10.]:
            for jitter in [-1.,0.,1.]:
                circular,offsets=ex.circular_centers(np.asarray(centers)+jitter,window=w)
                matched=ex.cut_matched_centers(centers,scenario['hard_cuts'],scenario['gradual_transitions'],window=w,jitter=jitter,
                                             draws=protocol['Q02']['cut_control_draws'],seed=protocol['Q02']['cut_control_seed'])
                designs.append(dict(scenario_id=scenario['scenario_id'],window_seconds=w,jitter_seconds=jitter,
                    circular_offsets_seconds=offsets,**{k:v for k,v in matched.items() if k!='centers'}))
                for key in primary_keys:
                    comparison,actual=compare_signal(signals[key],centers,circular,matched,window=w,jitter=jitter)
                    row=dict(scenario_id=scenario['scenario_id'],window_seconds=w,jitter_seconds=jitter,
                             primary=w==5 and jitter==0,signal=key,**comparison)
                    rows.append(row)
                    if scenario['frame_base']==0:
                        for eid,record in zip(event_ids,actual):event_rows.append(dict(event_id=eid,window_seconds=w,jitter_seconds=jitter,signal=key,**record))
    table(dest/'narrative_comparisons.csv',rows);table(dest/'per_event_changes.csv',event_rows)
    write(dest/'control_designs.json',designs)
    # Fixed 1Hz samples for digital-source sensitivity; not a restoration model.
    si=np.searchsorted(t,np.arange(150,750));sample=frames[si];baseline=sample.mean(axis=(1,2))/255
    variants={'gamma_0.8':np.power(sample/255,.8).mean(axis=(1,2)),
              'gamma_1.2':np.power(sample/255,1.2).mean(axis=(1,2)),
              'narrower_crop':sample[:,5:-5,7:-7].mean(axis=(1,2))/255}
    jpeg=[]
    for frame in sample:
        success,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,40]);assert success
        jpeg.append(cv2.imdecode(encoded,cv2.IMREAD_GRAYSCALE).mean()/255)
    variants['jpeg_q40']=np.asarray(jpeg)
    sensitivity=[dict(variant=k,pearson=ex.correlation(baseline,v),spearman=ex.spearman(baseline,v),
                      mean_absolute_digital_mean_difference=float(np.abs(v-baseline).mean())) for k,v in variants.items()]
    mechanism=[]
    for index in np.linspace(0,len(si)-1,12,dtype=int):
        frame=sample[index]; shifted=cv2.warpAffine(frame,np.float32([[1,0,1],[0,1,0]]),(frame.shape[1],frame.shape[0]),borderMode=cv2.BORDER_REFLECT)
        bright=np.minimum(frame.astype(np.int16)+10,255).astype(np.uint8)
        for name,other in [('same_image',frame),('one_pixel_shift',shifted),('plus_10_gray_levels',bright)]:
            mechanism.append(dict(source_sample_playback_seconds=float(t[si[index]]),perturbation=name,
                                  empirical_film_motion_truth=False,**ex.image_pair_features(frame,other,.4,cv2=cv2)))
    table(dest/'digital_sensitivity.csv',sensitivity);table(dest/'real_image_mechanism_checks.csv',mechanism)
    valid=[p for p in pair_rows if p['valid_measurement']]
    relations=[]
    for a,b in [('mad','flow_p90_diagonals_per_second'),('flicker_one_minus_correlation','flow_p90_diagonals_per_second'),
                ('flow_p90_diagonals_per_second','flow_residual_p90_diagonals_per_second')]:
        relations.append(dict(first=a,second=b,spearman=ex.spearman([p[a] for p in valid],[p[b] for p in valid]),pairs=len(valid)))
    result=dict(status='PROVISIONAL',film_reference=reference['film_reference'],video_version_id=reference['video_version_id'],
       source_coverage_seconds=[150,750],narrative_annotation_set_id=narrative['annotation_set_id'],event_onsets=len(centers),
       pair_count=len(pair_rows),valid_pair_count=len(valid),excluded_pair_count=len(pair_rows)-len(valid),
       pair_exclusion_counts={flag:sum(flag in p['quality_flags'] for p in pair_rows) for flag in ['manual_hard_cut','manual_gradual','low_texture','unexpected_pair_duration']},
       grayscale_full_vs_roi_spearman=ex.spearman(signals['roi_mean']['values'],signals['full_mean']['values']),
       digital_sensitivity=sensitivity,motion_relations=relations,comparisons=rows,
       motion_ground_truth_available=False,causal_or_confirmatory_test=False,
       controls='Circular common-shift reference and same-third hard-cut controls; retain offsets, overlap, missing support and blocked strata.',
       limitations=['All outcomes and windows exploratory; no best outcome selection or multiple-test significance claim.',
          'Random shifts do not establish exchangeability in nonstationary film data.',
          'Heterogeneous narrative events; visible transitions may participate in human event definitions.',
          'Flow is image displacement at 64x48 regridded ROI; no verified camera/subject/damage attribution.',
          'Pixel values and gamma/JPEG sensitivity are digital measurements, not recovered historical luminance.'])
    write(dest/'results.json',result)
    fig,axes=plt.subplots(3,1,figsize=(13,8),sharex=True)
    for axis,key,color in [(axes[0],'roi_mean','#245a81'),(axes[1],'mad','#c67d36'),(axes[2],'flow_p90_diagonals_per_second','#2b916f')]:
        axis.plot(signals[key]['starts'],signals[key]['values'],lw=1,color=color);axis.set_ylabel(key)
        for c in centers:axis.axvline(c,color='#a26874',alpha=.4,lw=.8)
        axis.spines[['top','right']].set_visible(False);axis.grid(alpha=.12)
    axes[-1].xaxis.set_major_formatter(FuncFormatter(clock));axes[-1].set_xlabel('Source playback time; vertical lines mark human-annotated event onsets; missing values remain missing')
    fig.suptitle('Q02: Digital grey-level and visual activity on an independent narrative timeline');fig.tight_layout();savefig(fig,dest/'narrative_timeline')
    progress('Q02_complete',primary=[r for r in rows if r['primary'] and r['scenario_id'].endswith('_0')],digital_sensitivity=sensitivity,motion_relations=relations)
    return result


def content_intervals(reference):
    scenario=reference['scenarios'][0];transitions=[]
    for c in scenario['hard_cuts']:transitions.append((c['playback_seconds'],c['playback_seconds'],c['cut_id']))
    for g in scenario['gradual_transitions']:transitions.append((g['start_playback_seconds'],g['end_playback_seconds'],g['transition_id']))
    cursor=150.;previous='coverage_left';rows=[]
    for a,b,identifier in sorted(transitions)+[(750.,750.,'coverage_right')]:
        if a>cursor:
            rows.append(dict(interval_id=f'content-{previous}__{identifier}',interval_index=len(rows),start_seconds=cursor,end_seconds=a,
                             duration_seconds=a-cursor,left_partial=previous=='coverage_left',right_partial=identifier=='coverage_right'))
        cursor=b;previous=identifier
    return rows


def contact_sheet(paths,labels,destination, *, boxes=None,cols=4,tile_width=320):
    rows=math.ceil(len(paths)/cols);tile_height=285
    sheet=Image.new('RGB',(cols*tile_width,rows*tile_height),'white');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',14)
    for i,(p,label) in enumerate(zip(paths,labels)):
        img=Image.open(p).convert('RGB')
        if boxes is not None:
            brush=ImageDraw.Draw(img)
            for x,y,w,h in boxes[i]:brush.rectangle((x,y,x+w,y+h),outline='#24d188',width=3)
        img.thumbnail((tile_width-8,tile_height-44));x=(i%cols)*tile_width;y=(i//cols)*tile_height
        sheet.paste(img,(x+(tile_width-img.width)//2,y));draw.text((x+4,y+tile_height-40),label,font=font,fill='black')
    sheet.save(destination)


def q03_q04(out,arrays,reference,narrative,manifest,protocol):
    dest=out/'Q03_recurrence';dest.mkdir();face_dir=out/'Q04_face_proxy';face_dir.mkdir()
    intervals=content_intervals(reference);complete=[p for p in intervals if not p['left_partial'] and not p['right_partial']]
    frames=arrays['gray_cache'];times=arrays['playback_seconds'];events=narrative['events'];onsets=[e['start_seconds'] for e in events if e['start_seconds']>150]
    representatives=[];descriptors={};event_lookup={}
    for fraction in [.25,.5,.75]:
        ds=[];hs=[];means=[];sample_rows=[]
        for p in complete:
            requested=p['start_seconds']+fraction*p['duration_seconds'];i=int(np.searchsorted(times,requested));frame=frames[i]
            actual=float(times[i]);label=next((e['event_id'] for e in events if e['observed_start_seconds']<=actual<e['observed_end_seconds']),None)
            safe=all(abs(actual-c)>1 for c in onsets)
            ds.append(ex.dct_descriptor(frame,cv2=cv2));hs.append(ex.dhash_descriptor(frame,cv2=cv2));means.append(float(frame.mean()/255))
            record=dict(representative_id=p['interval_id']+f'@{fraction}',fraction=fraction,**p,
                        target_seconds=requested,playback_seconds=actual,source_pts=int(arrays['pts'][i]),time_base='1/16000',
                        cache_frame_index=i,narrative_event_id=label,narrative_assignment_away_from_onset=safe)
            representatives.append(record);sample_rows.append(record)
        d=np.asarray(ds);h=np.asarray(hs);means=np.asarray(means)
        descriptors[fraction]={'dct':d@d.T,'dhash':1-np.mean(h[:,None,:]!=h[None,:,:],axis=2),
                               'brightness':-np.abs(means[:,None]-means[None,:]),'records':sample_rows}
    table(dest/'representatives.csv',representatives)
    top_sets={};ranking_rows=[];pair_rows=[];auc_rows=[]
    for fraction,record in descriptors.items():
        samples=record['records'];pairs=[(i,j) for i in range(len(samples)) for j in range(i+1,len(samples))
              if samples[j]['interval_index']-samples[i]['interval_index']>=2 and abs(samples[j]['playback_seconds']-samples[i]['playback_seconds'])>=10]
        for method in ['dct','dhash','brightness']:
            similarity=record[method]
            ranked=sorted([(float(similarity[i,j]),i,j) for i,j in pairs if np.isfinite(similarity[i,j])],reverse=True)
            top_sets[(fraction,method)]={(i,j) for score,i,j in ranked[:10]}
            for rank,(score,i,j) in enumerate(ranked[:10],1):
                ranking_rows.append(dict(fraction=fraction,method=method,rank=rank,first_id=samples[i]['interval_id'],second_id=samples[j]['interval_id'],
                    first_index=i,second_index=j,similarity=score,first_seconds=samples[i]['playback_seconds'],second_seconds=samples[j]['playback_seconds']))
            strata={}
            for i,j in pairs:
                if not (samples[i]['narrative_assignment_away_from_onset'] and samples[j]['narrative_assignment_away_from_onset']):continue
                if samples[i]['narrative_event_id'] is None or samples[j]['narrative_event_id'] is None:continue
                score=float(similarity[i,j]);lag=abs(samples[j]['playback_seconds']-samples[i]['playback_seconds']);group=int(lag//20)
                same=samples[i]['narrative_event_id']==samples[j]['narrative_event_id']
                strata.setdefault(group,{True:[],False:[]})[same].append(score)
                pair_rows.append(dict(fraction=fraction,method=method,first_id=samples[i]['interval_id'],second_id=samples[j]['interval_id'],
                    lag_seconds=lag,lag_bin_seconds=group*20,same_event_proxy=same,similarity=score))
            for group,values in sorted(strata.items()):
                auc_rows.append(dict(fraction=fraction,method=method,lag_bin_seconds=group*20,same_event_pairs=len(values[True]),different_event_pairs=len(values[False]),
                                     same_event_proxy_auc=ex.auc(values[True],values[False]),independent_pair_observations=False))
    stability=[]
    for method in ['dct','dhash','brightness']:
        for alternate in [.25,.75]:
            a,b=top_sets[(.5,method)],top_sets[(alternate,method)]
            stability.append(dict(method=method,primary_fraction=.5,alternate_fraction=alternate,
                                  top10_common_pairs=len(a&b),top10_jaccard=len(a&b)/len(a|b) if a|b else None))
    table(dest/'top_pairs.csv',ranking_rows);table(dest/'all_pair_scores.csv',pair_rows);table(dest/'lag_stratified_event_proxy_auc.csv',auc_rows);table(dest/'representative_stability.csv',stability)
    write(dest/'results.json',dict(status='PROVISIONAL',complete_interval_count=len(complete),representative_count=len(representatives),
          frame_base_used_for_sampling=0,frame_basis_confirmed=False,representative_stability=stability,lag_stratified_event_proxy_auc=auc_rows,
          limitations=['Low-level image configuration, not semantic motif/location/character identity.',
             'Same-event label is an independent narrative proxy, not visual recurrence truth.',
             'Lag stratification does not remove dependence among pairs or all source/brightness confounds.',
             'One/few representative frames cannot establish shot-level persistence.']))
    # Decode exactly this sample's span once for inspectable, larger representatives.
    image_dir=out/'representative_images';image_dir.mkdir();source=Path(manifest['source']['resolved_path'])
    targets=sorted([(r['target_seconds'],r) for r in representatives],key=lambda x:x[0]);pointer=0;decoded=0
    started=time.perf_counter();source_before=source_state(source)
    with av.open(str(source)) as container:
        stream=next(s for s in container.streams.video if s.index==manifest['selected_video_stream_index'])
        container.seek(int((Fraction(150)+Fraction(43,1000))/stream.time_base),stream=stream,backward=True,any_frame=False)
        for frame in container.decode(stream):
            if frame.pts is None:raise ValueError('Missing source PTS.')
            playback=float(Fraction(frame.pts)*frame.time_base-Fraction(43,1000))
            if playback>=750:break
            if playback<150:continue
            decoded+=1
            while pointer<len(targets) and playback>=targets[pointer][0]:
                target,row=targets[pointer]
                if playback>=row['end_seconds']:raise ValueError('Representative fell outside its content interval.')
                rgb=frame.to_ndarray(format='rgb24');height=round(rgb.shape[0]*480/rgb.shape[1]);rgb=cv2.resize(rgb,(480,height),interpolation=cv2.INTER_AREA)
                filename=f'image-{row["interval_index"]:03d}-{int(row["fraction"]*100):02d}.jpg'
                Image.fromarray(rgb).save(image_dir/filename,quality=90)
                row.update(image_path=str((image_dir/filename).relative_to(out)),image_width=480,image_height=height,
                           image_source_pts=int(frame.pts),image_playback_seconds=playback,image_target_offset_seconds=playback-target)
                pointer+=1
            if pointer==len(targets):break
    if pointer!=len(targets) or source_state(source)!=source_before:raise ValueError('Incomplete decode or changed source.')
    progress('representative_images_complete',images=pointer,decoded_frames=decoded,elapsed_seconds=time.perf_counter()-started)
    table(dest/'representatives.csv',representatives)
    # Uniform midpoint review images deliberately selected without detector scores.
    middle=[r for r in representatives if r['fraction']==.5];chosen=np.linspace(0,len(middle)-1,12,dtype=int)
    selected=[middle[i] for i in chosen];paths=[out/r['image_path'] for r in selected]
    labels=[f'R{k+1:02d}  {clock(r["image_playback_seconds"])}  '+r['interval_id'].replace('content-','') for k,r in enumerate(selected)]
    write(face_dir/'unboxed_review_selection.json',dict(selection='12 evenly spaced midpoint representatives, before face results',annotator_required='assistant qualitative inspection, not human ground truth',images=selected))
    contact_sheet(paths,labels,face_dir/'unboxed_uniform_review.png')
    # Ranking and random control sheets show actual source frames, never labels as truth.
    primary=[r for r in ranking_rows if r['fraction']==.5 and r['method']=='dct'][:8]
    pair_paths=[];pair_labels=[]
    for row in primary:
        for key in ['first_index','second_index']:
            sample=middle[row[key]];pair_paths.append(out/sample['image_path']);pair_labels.append(f'DCT #{row["rank"]} {clock(sample["image_playback_seconds"])} sim={row["similarity"]:.3f}')
    contact_sheet(pair_paths,pair_labels,dest/'top_dct_pairs.png',cols=4)
    # Non-identifying face detection: outputs remain predictions.
    model=Path(cv2.data.haarcascades)/'haarcascade_frontalface_default.xml';classifier=cv2.CascadeClassifier(str(model))
    if classifier.empty():raise ValueError('Existing cascade unavailable; no download permitted.')
    face_rows=[];boxes_by_id={};timing=time.perf_counter()
    for row in representatives:
        image=cv2.imread(str(out/row['image_path']),cv2.IMREAD_GRAYSCALE)
        for neighbors in [5,3]:
            boxes=classifier.detectMultiScale(image,scaleFactor=1.1,minNeighbors=neighbors,minSize=(24,24))
            boxes=np.asarray(boxes,dtype=int).reshape(-1,4).tolist()
            areas=[w*h/(image.shape[0]*image.shape[1]) for x,y,w,h in boxes]
            face_rows.append(dict(representative_id=row['representative_id'],interval_id=row['interval_id'],fraction=row['fraction'],
                  source_pts=row['image_source_pts'],playback_seconds=row['image_playback_seconds'],minNeighbors=neighbors,
                  face_box_count=len(boxes),max_face_box_fraction=max(areas) if areas else None,
                  boxes_xywh=boxes,zero_detection_meaning='No frontal-face detection; not absence of persons.',validation_status='unreviewed_prediction'))
            if neighbors==5:boxes_by_id[row['representative_id']]=boxes
    table(face_dir/'face_predictions.csv',face_rows)
    contact_sheet(paths,labels,face_dir/'boxed_uniform_review.png',boxes=[boxes_by_id[r['representative_id']] for r in selected])
    count_change=[]
    for row in representatives:
        matched=[p for p in face_rows if p['representative_id']==row['representative_id']]
        count_change.append(matched[0]['face_box_count']!=matched[1]['face_box_count'])
    write(face_dir/'results.json',dict(status='PROVISIONAL',source_representatives=len(representatives),model_path=str(model),model_sha256=sha(model),
         model_preexisting=True,no_model_download=True,elapsed_detection_seconds=time.perf_counter()-timing,
         parameter_count_change_frames=sum(count_change),parameter_count_change_fraction=float(np.mean(count_change)),
         primary_zero_detections=sum(r['face_box_count']==0 for r in face_rows if r['minNeighbors']==5),
         primary_detected_boxes=sum(r['face_box_count'] for r in face_rows if r['minNeighbors']==5),
         human_face_or_scale_ground_truth_available=False,identity_recognition_performed=False,
         limitations=['Frontal face count is neither person count nor character count.',
             'Face-box area is not a calibrated shot-scale class.',
             'Sensitivity checks and assistant inspection do not provide independent human detection accuracy.']))
    progress('Q03_Q04_complete',complete_intervals=len(complete),representatives=len(representatives),stability=stability,
             face_parameter_change_fraction=float(np.mean(count_change)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True);args=parser.parse_args()
    protocol=read(args.protocol);out=ROOT/protocol['output_directory']
    if (out/'run.json').exists() or any((out/name).exists() for name in ['Q01_editing','Q02_timeline','Q03_recurrence','Q04_face_proxy']):
        raise ValueError('Existing experiment outputs are immutable; inspect and use a new run directory.')
    fonts();began=now();started=time.perf_counter()
    for record in protocol['inputs'].values():assert sha(ROOT/record['path'])==record['sha256'],record['path']
    manifest=read(ROOT/protocol['inputs']['manifest']['path']);reference=read(ROOT/protocol['inputs']['manual_reference']['path']);narrative=read(ROOT/protocol['inputs']['narrative_reference']['path'])
    for item in [reference,narrative]:
        assert item['film_reference']==manifest['film_reference'] and item['video_version_id']==manifest['video_version_id']
    assert narrative['independent_of_visual_measurements'] and narrative['exhaustive_within_coverage']
    actual_sha,source_bytes,before=hash_video(manifest['source']['resolved_path']);assert actual_sha==manifest['source']['sha256']
    with np.load(ROOT/protocol['inputs']['gray_cache']['path'],allow_pickle=False) as archive:arrays={k:archive[k] for k in archive.files}
    assert str(arrays['video_version_id'])==manifest['video_version_id'];assert abs(arrays['evaluation_overlap_seconds'].sum()-600)<1e-8
    snapshots=out/'source_snapshot';snapshots.mkdir()
    sources=[Path(__file__),ROOT/'analysis-python/cinematicdx/exploration.py']
    code_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    for p in sources:shutil.copy2(p,snapshots/p.name)
    write(out/'start_receipt.json',dict(started_at_utc=began,protocol_sha256=sha(args.protocol),code_hashes=code_hashes,
        source_full_sha256=actual_sha,source_bytes=source_bytes,source_state=before,
        python=sys.version,numpy=np.__version__,opencv=cv2.__version__,pyav=av.__version__,software=software_provenance()))
    progress('inputs_verified',output=str(out),source_seconds=600)
    q01(out,reference,protocol)
    q02(out,arrays,reference,narrative,protocol)
    q03_q04(out,arrays,reference,narrative,manifest,protocol)
    for record in protocol['inputs'].values():assert sha(ROOT/record['path'])==record['sha256']
    assert source_state(manifest['source']['resolved_path'])==before
    assert code_hashes=={str(p.relative_to(ROOT)):sha(p) for p in sources}
    files=[p for p in out.rglob('*') if p.is_file() and p.name!='run.json']
    write(out/'run.json',dict(status='complete',artifact_kind='bounded_quantitative_exploration',started_at_utc=began,completed_at_utc=now(),
         elapsed_seconds=time.perf_counter()-started,film_reference=manifest['film_reference'],video_version_id=manifest['video_version_id'],
         source_coverage_seconds=[150,750],unique_source_video_seconds=600,source_and_annotation_hashes_unchanged=True,
         downloaded_models=False,video_uploaded=False,database_used=False,training=False,code_hashes=code_hashes,
         outputs={str(p.relative_to(out)):{'sha256':sha(p),'size_bytes':p.stat().st_size} for p in files}))
    progress('all_experiments_complete',elapsed_seconds=time.perf_counter()-started)


if __name__=='__main__':main()
