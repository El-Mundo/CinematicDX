"""Independent film-level arithmetic and source-binding checks, after aggregation."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
from fractions import Fraction
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
from cinematicdx.ingest import source_state

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--analysis-directory',type=Path);p.add_argument('--output-file',type=Path);args=p.parse_args();run=args.run
    analysis=args.analysis_directory or run/'analysis';output=args.output_file or run/'corpus_audit.json'
    if output.exists():raise ValueError('Audit already exists.')
    plan=read(run/'plan.json');config=read(run/'config.json');summary=read(analysis/'summary.json');done=read(run/'extraction_complete.json')
    assert sha(plan['metadata_path'])==plan['metadata_sha256'];assert sha(plan['identity_map_path'])==plan['identity_map_sha256']
    excel=ROOT/'outputs/01a17483-82c6-7510-8251-931dcb5d21d8/上甘岭_10分钟人工标注模板.xlsx'
    assert sha(excel)==config['original_excel_sha256']
    with (analysis/'film_measurements_and_coverage.csv').open(encoding='utf-8-sig') as f:films=list(csv.DictReader(f))
    with (analysis/'studio_summary_all.csv').open(encoding='utf-8-sig') as f:groups=list(csv.DictReader(f))
    assert len(films)==plan['metadata_count']
    assert {f['film_key'] for f in films}=={f['film_key'] for f in plan['films']}
    assert len(done['completed'])+len(done['failed'])==plan['video_file_count']
    arithmetic=[];input_changes=[];total_samples=0;group_values=defaultdict(list);fractional=0.
    all_file_samples=0
    for job in plan['jobs']:
        directory=run/'films'/job['job_id']
        if not (directory/'run.json').exists():continue
        record=read(directory/'run.json');document=read(directory/'summary.json')
        for name,value in record['outputs'].items():assert sha(directory/name)==value['sha256']
        if tuple(record['source_state'])!=source_state(job['source_path']):input_changes.append(job['relative_path'])
        all_file_samples+=document['summary']['sample_count']
    for f in films:
        if f['measured']!='True':continue
        directory=run/'films'/f['selected_job_id'];document=read(directory/'summary.json');receipt=read(directory/'run.json')
        for name,record in receipt['outputs'].items():assert sha(directory/name)==record['sha256']
        if tuple(receipt['source_state'])!=source_state(document['job']['source_path']):input_changes.append(f['film_key'])
        with np.load(directory/'samples.npz',allow_pickle=False) as z:a={k:z[k] for k in ['pts','source_seconds','playback_seconds','roi_mean']}
        t=a['playback_seconds'];tb=Fraction(document['technical']['time_base']);origin=Fraction(document['technical']['playback_origin_rational'])
        expected=a['pts'].astype(float)*float(tb)-float(origin)
        max_error=float(np.max(np.abs(expected-t)));assert max_error<1e-8
        assert np.all(np.diff(a['pts'])>0);total_samples+=len(t)
        # Independent scalar accumulation rather than the extractor's np.dot.
        duration=float(f['duration_seconds']);middle=[(float(x)+float(y))/2 for x,y in zip(t,t[1:])]
        boundaries_left=[0.]+middle;boundaries_right=middle+[duration]
        weights=[max(0,min(b,float(s)+2.5,duration)-max(a,float(s)-2.5,0)) for a,b,s in zip(boundaries_left,boundaries_right,t)]
        mean=math.fsum(w*float(v) for w,v in zip(weights,a['roi_mean']))/math.fsum(weights)
        sd=math.sqrt(math.fsum(w*(float(v)-mean)**2 for w,v in zip(weights,a['roi_mean']))/math.fsum(weights))
        assert abs(mean-float(f['gray_roi_time_mean']))<1e-11
        assert abs(sd-float(f['gray_roi_temporal_sd']))<1e-11
        arithmetic.append(dict(film_key=f['film_key'],source_pts_max_seconds_error=max_error,mean_error=abs(mean-float(f['gray_roi_time_mean'])),sd_error=abs(sd-float(f['gray_roi_temporal_sd'])),samples=len(t)))
        if f['eligible']=='True':
            studios=json.loads(f['studios']);assert abs(sum(s['fractional_weight'] for s in studios)-1)<1e-12
            value=float(f['mean_abs_change_30s_z'])
            for studio in studios:group_values[studio['studio_id']].append((value,studio['fractional_weight']));fractional+=studio['fractional_weight']
    assert total_samples==summary['total_timestamped_samples']
    assert all_file_samples==summary.get('total_timestamped_file_samples',summary['total_timestamped_samples'])
    assert abs(fractional-summary['eligible_films'])<1e-8
    group_checks=[]
    for group in groups:
        entries=group_values[group['studio_id']]
        if entries:
            mean=math.fsum(v*w for v,w in entries)/math.fsum(w for v,w in entries)
            error=abs(mean-float(group['mean_abs_change_30s_z__mean']));assert error<1e-11
            group_checks.append(dict(studio=group['studio'],member_films=len(entries),mean_error=error))
        else:assert group['mean_abs_change_30s_z__mean']==''
    result=dict(status='numerically_verified',completed_at_utc=datetime.now(timezone.utc).isoformat(),
          metadata_film_ids_verified=len(films),video_jobs_attempted=len(done['completed'])+len(done['failed']),
          video_jobs_successful=len(done['completed']),timestamped_samples_verified=total_samples,timestamped_file_samples_verified=all_file_samples,analysis_directory=str(analysis),
          original_metadata_and_excel_sha256_unchanged=True,source_files_changed_after_extraction=input_changes,
          film_arithmetic_checks=arithmetic,studio_mean_checks=group_checks,fractional_weights_equal_eligible_film_count=True,
          interpretation='Checks establish arithmetic/provenance, not historical photometry, independent human identities, or studio causality.',
          script_sha256=sha(__file__))
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['status','metadata_film_ids_verified','video_jobs_attempted','video_jobs_successful','timestamped_samples_verified','source_files_changed_after_extraction']},ensure_ascii=False))

if __name__=='__main__':main()
