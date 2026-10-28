"""Checkpointed full-corpus frame-complete extraction, four CPU workers maximum."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
from cinematicdx.corpus_editing import run_job,sha,write_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);p.add_argument('--workers',type=int,default=4);args=p.parse_args()
    if not 1<=args.workers<=4:raise ValueError('Use1–4 workers.')
    run=args.run.absolute();config=json.loads((run/'config.json').read_text());plan=json.loads((run/'plan.json').read_text())
    for path,digest in config['source_hashes'].items():
        if sha(ROOT/path)!=digest:raise ValueError('Frozen source changed.')
    if not json.loads((run/'preflight/results.json').read_text())['hard_cut_preflight_passed']:raise ValueError('Pilot preflight failed.')
    if sha(plan['metadata_path'])!=plan['metadata_sha256']:raise ValueError('Metadata changed.')
    (run/'films').mkdir(exist_ok=True);began=time.perf_counter();complete=[];failed=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_job,j,str(run),sha(run/'config.json')):j for j in plan['jobs']}
        for future in as_completed(futures):
            job=futures[future]
            try:
                doc=future.result();complete.append(job['job_id']);last=dict(title=job['title'],seconds=round(doc['elapsed_seconds'],2),
                    cuts=doc['metrics']['primary_cut_candidates'],gradual_candidates=doc['metrics']['default_gradual_candidates'])
            except Exception as exc:
                error=dict(job_id=job['job_id'],title=job['title'],error=str(exc),traceback=traceback.format_exc())
                write_json(run/('failure-'+job['job_id']+'.json'),error);failed.append(job['job_id']);last=error
            progress=dict(utc=datetime.now(timezone.utc).isoformat(),total=len(plan['jobs']),complete=len(complete),failed=len(failed),
                elapsed_seconds=time.perf_counter()-began,last=last)
            write_json(run/'progress.partial.json',progress);(run/'progress.partial.json').replace(run/'progress.json')
            print(json.dumps(progress,ensure_ascii=False),flush=True)
    write_json(run/'extraction_complete.json',dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),complete=complete,failed=failed,
        attempted=len(plan['jobs']),elapsed_seconds=time.perf_counter()-began,config_sha256=sha(run/'config.json'),workers=args.workers))


if __name__=='__main__':main()
