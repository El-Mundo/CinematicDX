"""Compare keyframe sampling with dense-decode 1Hz sampling on fixed real clips."""
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
from cinematicdx.exploration import correlation
from cinematicdx.ingest import hash_video,source_state

def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();run=args.run
    config=json.loads((run/'config.json').read_text());plan=json.loads((run/'plan.json').read_text());lookup={j['film_key']:j for j in plan['jobs']}
    old=json.loads((ROOT/'research-local/m2/headers-20261025T202246Z/inventory.json').read_text());durations={r['relative_path']:r['header_probe']['technical_summary']['duration_seconds'] for r in old['videos']}
    rows=[];sources=[];began=time.perf_counter();dest=run/'validation';dest.mkdir(exist_ok=False)
    for key in config['sampling_validation']['film_keys']:
        job=lookup[key];digest,size,state=hash_video(job['source_path']);sources.append(dict(film_key=key,video_version_id='sha256:'+digest,size_bytes=size))
        for position in [.25,.5,.75]:
            start=durations[job['relative_path']]*position;end=start+60
            k,km=extract_samples(job['source_path'],mode='keyframes',clip=(start,end))
            d,dm=extract_samples(job['source_path'],mode='dense_1hz',clip=(start,end))
            values={};coverages={}
            for name,a in [('keyframe',k),('dense1hz',d)]:
                left,right=representation_intervals(a['playback_seconds']-start,60)
                values[name],coverages[name]=bin_samples(left,right,a['roi_mean'],np.arange(0,61,5))
            leftk,rightk=representation_intervals(k['playback_seconds']-start,60);leftd,rightd=representation_intervals(d['playback_seconds']-start,60)
            vk,ck=bin_samples(leftk,rightk,k['roi_mean'],[0,30,60]);vd,cd=bin_samples(leftd,rightd,d['roi_mean'],[0,30,60])
            clipmeanerror=float(abs(np.average(k['roi_mean'],weights=rightk-leftk)-np.average(d['roi_mean'],weights=rightd-leftd)))
            error30=float(np.abs(vk-vd).mean());rmse5=float(np.sqrt(np.mean((values['keyframe']-values['dense1hz'])**2)))
            okay=clipmeanerror<=.02 and error30<=.02 and np.min(ck)>=.98 and np.min(cd)>=.98
            row=dict(film_key=key,title=job['title'],studio=job['studios'][0]['chn'],colour=job['colour'],position_fraction=position,
                start_seconds=start,end_seconds=end,keyframe_samples=len(k['pts']),dense_samples=len(d['pts']),
                clip_mean_absolute_error=clipmeanerror,mean_30s_bin_absolute_error=error30,rmse_5s_bins=rmse5,
                correlation_5s_bins=correlation(values['keyframe'],values['dense1hz']),primary_case_passed=bool(okay))
            rows.append(row);filename=job['job_id']+'-'+str(int(position*100))+'.npz'
            np.savez_compressed(dest/filename,**{'key_'+name:value for name,value in k.items()},**{'dense_'+name:value for name,value in d.items()})
            print(json.dumps(clean(row),ensure_ascii=False),flush=True)
        if source_state(job['source_path'])!=state:raise ValueError('Validation source changed.')
    fraction=sum(r['primary_case_passed'] for r in rows)/len(rows)
    result=dict(status='PROVISIONAL',primary_acceptance_passed=fraction>=.9,passing_clip_fraction=fraction,
         criterion='At least90% of24 clips: whole-clip mean error<=.02 AND30s-bin MAE<=.02 AND representation>=.98 for both methods.',
         clip_count=len(rows),total_distinct_video_seconds=len(rows)*60,sources=sources,cases=rows,elapsed_seconds=time.perf_counter()-began,
         median_30s_bin_mae=float(np.median([r['mean_30s_bin_absolute_error'] for r in rows])),max_30s_bin_mae=max(r['mean_30s_bin_absolute_error'] for r in rows),
         limitation='Dense1Hz is a sampling reference, not every-frame luminance truth. Clip selection is fixed purposive validation, not random corpus validation.')
    (run/'sampling_validation.json').write_text(json.dumps(clean(result),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    with (run/'sampling_validation.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(primary_acceptance_passed=result['primary_acceptance_passed'],passing_clip_fraction=fraction,elapsed_seconds=result['elapsed_seconds']),ensure_ascii=False))

if __name__=='__main__':main()
