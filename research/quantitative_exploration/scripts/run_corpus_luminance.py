"""Checkpointed, local, whole-corpus gray extraction; max four one-thread decoders."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
from cinematicdx.corpus_luminance import run_film_job

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--workers',type=int,default=4);args=p.parse_args()
    if not 1<=args.workers<=4:raise ValueError('Use one to four workers.')
    run=args.run.absolute();plan=json.loads((run/'plan.json').read_text());config=json.loads((run/'config.json').read_text());config_sha=sha(run/'config.json')
    if sha(ROOT/'analysis-python/cinematicdx/corpus_luminance.py')!=config['source_hashes']['analysis-python/cinematicdx/corpus_luminance.py']:raise ValueError('Frozen extractor changed.')
    if sha(plan['metadata_path'])!=plan['metadata_sha256'] or sha(plan['identity_map_path'])!=plan['identity_map_sha256']:raise ValueError('Frozen metadata changed.')
    validation=json.loads((run/'sampling_validation.json').read_text())
    if not validation['primary_acceptance_passed']:raise ValueError('Sampling validation did not pass; do not launch corpus extraction.')
    began=time.perf_counter();completed=[];failed=[];(run/'films').mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_film_job,job,str(run),config_sha):job for job in plan['jobs']}
        for future in as_completed(futures):
            job=futures[future]
            try:
                result=future.result();completed.append(dict(job_id=job['job_id'],film_key=job['film_key'],video_version_id=result['video_version_id']))
                info=dict(title=job['title'],sample_count=result['summary']['sample_count'],fallback=result['sampling_fallback_performed'],seconds=round(result['elapsed_seconds'],2))
            except Exception as exc:
                error=dict(job_id=job['job_id'],film_key=job['film_key'],title=job['title'],error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
                failed.append(error);write(run/('failure-'+job['job_id']+'.json'),error);info=dict(title=job['title'],error=str(exc))
            status=dict(utc=datetime.now(timezone.utc).isoformat(),total=len(plan['jobs']),complete=len(completed),failed=len(failed),elapsed_seconds=time.perf_counter()-began,last=info)
            temp=run/'progress.partial.json';write(temp,status);temp.replace(run/'progress.json')
            print(json.dumps(status,ensure_ascii=False),flush=True)
    write(run/'extraction_complete.json',dict(utc=datetime.now(timezone.utc).isoformat(),completed=completed,failed=failed,
        elapsed_seconds=time.perf_counter()-began,workers=args.workers,source_originals_modified=False,full_corpus_attempted=len(plan['jobs']),
        extractor_sha256=config['source_hashes']['analysis-python/cinematicdx/corpus_luminance.py'],config_sha256=config_sha))
    if sha(plan['metadata_path'])!=plan['metadata_sha256']:raise ValueError('Metadata changed during corpus processing.')

if __name__=='__main__':main()
