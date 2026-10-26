"""Validate revised uniform reference-frame sampling against saved dense1Hz clips."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
from cinematicdx.corpus_luminance import extract_samples,representation_intervals,bin_samples
from cinematicdx.ingest import hash_video,source_state

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();run=args.run
    initial=json.loads((run/'rejected_keyframe_only/sampling_validation.json').read_text());plan=json.loads((run/'plan.json').read_text());jobs={j['film_key']:j for j in plan['jobs']}
    expected={s['film_key']:s['video_version_id'] for s in initial['sources']};rows=[];began=time.perf_counter();dest=run/'reference_validation';dest.mkdir(exist_ok=False)
    states={}
    for key in expected:
        digest,size,state=hash_video(jobs[key]['source_path']);assert 'sha256:'+digest==expected[key];states[key]=state
    for old in initial['cases']:
        job=jobs[old['film_key']];start,end=old['start_seconds'],old['end_seconds']
        arrays,metadata=extract_samples(job['source_path'],mode='reference_1hz',clip=(start,end))
        cached=run/'validation'/(job['job_id']+'-'+str(int(old['position_fraction']*100))+'.npz')
        with np.load(cached,allow_pickle=False) as z:dense={k[6:]:z[k] for k in z.files if k.startswith('dense_')}
        l,r=representation_intervals(arrays['playback_seconds']-start,60);dl,dr=representation_intervals(dense['playback_seconds']-start,60)
        v,c=bin_samples(l,r,arrays['roi_mean'],[0,30,60]);dv,dc=bin_samples(dl,dr,dense['roi_mean'],[0,30,60])
        v5,c5=bin_samples(l,r,arrays['roi_mean'],np.arange(0,61,5));dv5,dc5=bin_samples(dl,dr,dense['roi_mean'],np.arange(0,61,5))
        error=float(abs(np.average(arrays['roi_mean'],weights=r-l)-np.average(dense['roi_mean'],weights=dr-dl)))
        mae=float(np.abs(v-dv).mean());passed=error<=.02 and mae<=.02 and min(c)>=.98 and min(dc)>=.98
        row=dict(film_key=old['film_key'],title=old['title'],studio=old['studio'],colour=old['colour'],position_fraction=old['position_fraction'],
             start_seconds=start,end_seconds=end,sample_count=len(arrays['pts']),dense_sample_count=len(dense['pts']),
             clip_mean_absolute_error=error,mean_30s_bin_absolute_error=mae,rmse_5s_bins=float(np.sqrt(np.mean((v5-dv5)**2))),
             primary_case_passed=bool(passed),reference_decoder_frames=metadata['frames_returned_by_decoder'],elapsed_seconds=metadata['elapsed_seconds'])
        rows.append(row);np.savez_compressed(dest/cached.name,**arrays);print(json.dumps(row,ensure_ascii=False),flush=True)
    for key,state in states.items():assert source_state(jobs[key]['source_path'])==state
    fraction=sum(r['primary_case_passed'] for r in rows)/len(rows)
    result=dict(status='PROVISIONAL',sampling='Uniform approx1Hz from decoded reference frames, originalPTS retained.',revision=2,
           original_keyframe_only_passed=False,original_validation_preserved=True,primary_acceptance_passed=fraction>=.9,passing_clip_fraction=fraction,
           primary_criterion_unchanged='At least90% of24 clips, mean error<=.02 and30s MAE<=.02, coverage>=.98.',
           cases=rows,clip_count=len(rows),sources=initial['sources'],elapsed_seconds=time.perf_counter()-began,
           median_30s_bin_mae=float(np.median([r['mean_30s_bin_absolute_error'] for r in rows])),max_30s_bin_mae=max(r['mean_30s_bin_absolute_error'] for r in rows),
           scope='Sampling agreement for slow digital-gray curves in fixed real clips; no historical luminance calibration or narrative-event accuracy claim.')
    (run/'sampling_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    with (run/'sampling_validation.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:result[k] for k in ['primary_acceptance_passed','passing_clip_fraction','median_30s_bin_mae','max_30s_bin_mae','elapsed_seconds']}))

if __name__=='__main__':main()
