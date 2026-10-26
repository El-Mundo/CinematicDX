"""Declared follow-up challenges, after Q01--Q04; no redefinition of primaries."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'analysis-python'))
from cinematicdx import exploration as ex


def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
    return v
def write(p,v):Path(p).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def null_for_series(series,centers,matrix,window=5.):
    observed=np.asarray([x['absolute_change'] for x in ex.changes_at(series,centers,window=window)])
    values,indices=np.unique(np.round(matrix.ravel(),9),return_inverse=True)
    changes=np.asarray([x['absolute_change'] for x in ex.changes_at(series,values,window=window)])
    controls=changes[indices].reshape(matrix.shape)
    return observed,controls


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();run=args.run
    dest=run/'Q05_challenges';dest.mkdir(exist_ok=False)
    protocol=read(run/'protocol.json');reference=read(ROOT/protocol['inputs']['manual_reference']['path']);narrative=read(ROOT/protocol['inputs']['narrative_reference']['path'])
    design=dict(declared_at_utc=datetime.now(timezone.utc).isoformat(),after_Q01_Q04_results=True,
       purpose='Challenge promising brightness association and contrast conditional versus unrestricted order controls.',
       primary_results_remain_unchanged=True,
       questions=['Does dropping any one hard-cut-associated event erase the brightness contrast?',
           'Does it persist for full-frame gray, sampled gray, modest gamma, JPEG and narrower crops?',
           'Would an unrestricted duration shuffle appear stronger by failing to preserve gradual-separated regimes?'],
       no_new_video_seconds=True,no_new_annotation=True,no_threshold_optimisation=True)
    write(dest/'followup_design.json',design)
    with np.load(ROOT/protocol['inputs']['gray_cache']['path'],allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
    t=arrays['playback_seconds'];ends=arrays['next_pts']/16000-.043
    centers=np.asarray([e['start_seconds'] for e in narrative['events'] if e['start_seconds']>150],float)
    ids=[e['event_id'] for e in narrative['events'] if e['start_seconds']>150]
    with np.load(run/'Q02_timeline/binned_signals.npz',allow_pickle=False) as z:
        roi={k:z['roi_mean__'+k] for k in ['starts','ends','values','valid_exposure','total_exposure']}
        full={k:z['full_mean__'+k] for k in ['starts','ends','values','valid_exposure','total_exposure']}
    si=np.searchsorted(t,np.arange(150,750));sample=arrays['gray_cache'][si]
    # Exact unit bins here describe a fixed 1Hz sensitivity approximation, not
    # original-frame exposure means. Its approximation is compared explicitly.
    def sampled_series(values):return ex.exposure_bins(np.arange(150,750),np.arange(151,751),values)
    variants={'source_ROI_exposure_mean':roi,'source_full_frame_exposure_mean':full,
              'sampled_ROI_mean':sampled_series(sample.mean(axis=(1,2))/255),
              'sampled_gamma_0.8':sampled_series(np.power(sample/255,.8).mean(axis=(1,2))),
              'sampled_gamma_1.2':sampled_series(np.power(sample/255,1.2).mean(axis=(1,2))),
              'sampled_narrower_crop':sampled_series(sample[:,5:-5,7:-7].mean(axis=(1,2))/255)}
    import cv2
    jpeg=[]
    for frame in sample:
        ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,40]);assert ok
        jpeg.append(cv2.imdecode(encoded,cv2.IMREAD_GRAYSCALE).mean()/255)
    variants['sampled_JPEG_q40']=sampled_series(jpeg)
    brightness=[];loo=[];event_records=[];null_arrays={}
    for scenario in reference['scenarios']:
        matched=ex.cut_matched_centers(centers,scenario['hard_cuts'],scenario['gradual_transitions'],window=5,draws=1999,seed=20261026)
        selected=matched['selected_events'];selected_centers=np.asarray([s['event_seconds'] for s in selected]);selected_ids=[ids[s['event_index']] for s in selected]
        for variant,series in variants.items():
            observed,controls=null_for_series(series,selected_centers,matched['centers'])
            brightness.append(dict(scenario_id=scenario['scenario_id'],variant=variant,event_count=len(observed),
                                   **ex.null_summary(float(observed.mean()),controls.mean(axis=1))))
            if variant=='source_ROI_exposure_mean':
                null_arrays[scenario['scenario_id']+'__hardcut_controls']=controls
                for i,event_id in enumerate(selected_ids):
                    kept=np.arange(len(observed))!=i
                    loo.append(dict(scenario_id=scenario['scenario_id'],removed_event_id=event_id,remaining_event_count=int(kept.sum()),
                                    control_pool_held_fixed=True,**ex.null_summary(float(observed[kept].mean()),controls[:,kept].mean(axis=1))))
                for eid,c,value in zip(selected_ids,selected_centers,observed):event_records.append(dict(event_id=eid,center_seconds=c,absolute_gray_change=value,scenario_id=scenario['scenario_id']))
    # Deliberately weaker, post-hoc null: preserves global multiset and run sizes
    # but not run distributions or their elapsed durations. Never replaces Q01.
    q01=read(run/'Q01_editing/results.json');timing=[]
    for result in q01['results']:
        runs=[[p['duration_seconds'] for p in run] for run in result['runs']];sizes=[len(x) for x in runs];flat=np.concatenate(runs)
        rng=np.random.default_rng(20261026);null=[]
        for _ in range(1999):
            perm=rng.permutation(flat);split=np.split(perm,np.cumsum(sizes)[:-1]);null.append(ex.sequence_statistics(split))
        timing.append(dict(scenario_id=result['scenario_id'],alternative_null='Unrestricted global durations assigned back to fixed run sizes; does not preserve regime durations.',
                      mean_absolute_log_ratio=ex.null_summary(result['observed']['mean_absolute_log_ratio'],[n['mean_absolute_log_ratio'] for n in null]),
                      lag1_log_correlation=ex.null_summary(result['observed']['lag1_log_correlation'],[n['lag1_log_correlation'] for n in null]),
                      run_summaries=[dict(interval_count=len(x),duration_sum_seconds=float(sum(x)),mean_seconds=float(np.mean(x)),median_seconds=float(np.median(x))) for x in runs]))
    write(dest/'results.json',dict(status='PROVISIONAL',followup_design=design,leave_one_event_out=loo,
        brightness_variants=brightness,event_absolute_changes=event_records,unrestricted_shuffle_diagnostic=timing,
        limits=['Positive conditional contrasts do not establish narrative causation or transferable event detection.',
            'Controls match coarse time region and cut proximity, not shot scale, lighting set-up, locations or all temporal dependence.',
            'No significance level/CI inferred from dependent draws or multiple exploratory outcomes.',
            'Follow-up was selected after the initial results; no independent held-out validation.']))
    np.savez_compressed(dest/'controls_for_inspection.npz',**null_arrays)
    files=[p for p in dest.iterdir() if p.is_file()]
    write(dest/'run.json',dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),script_sha256=sha(__file__),
        initial_run_sha256=sha(run/'run.json'),protocol_sha256=sha(run/'protocol.json'),
        outputs={p.name:{'sha256':sha(p)} for p in files},unique_additional_video_seconds=0,original_annotations_unchanged=True))
    print(json.dumps(clean(dict(leave_one_out=loo[:6],brightness=brightness[:7],unrestricted_timing=timing[:1])),ensure_ascii=False))


if __name__=='__main__':main()
