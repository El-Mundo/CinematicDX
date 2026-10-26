"""Finish dependent computations after all film attempts; visual interpretation stays pending."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--wait',action='store_true');args=p.parse_args();run=args.run.absolute()
    while not (run/'extraction_complete.json').exists():
        if not args.wait:raise ValueError('Extraction is still incomplete.')
        time.sleep(30)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'analysis-python'),OPENBLAS_NUM_THREADS='1',MPLCONFIGDIR='/tmp/cinematicdx-mpl')
    steps=[('aggregate','analyse_corpus_editing.py',run/'analysis/run.json'),
           ('visual_qa_frames','inspect_corpus_editing.py',run/'visual_qa/selection_and_receipt.json'),
           ('independent_numerical_audit','audit_corpus_editing.py',run/'numerical_audit.json')]
    for stage,script,completion in steps:
        if completion.exists():continue
        status=dict(stage=stage,started_at_utc=datetime.now(timezone.utc).isoformat(),assistant_visual_interpretation='pending')
        (run/'finishing_progress.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status),flush=True)
        subprocess.run([sys.executable,str(ROOT/'research/quantitative_exploration/scripts'/script),'--run',str(run)],cwd=ROOT,env=env,check=True)
    (run/'pipeline_ready.json').write_text(json.dumps(dict(status='numerical_outputs_ready_assistant_visual_review_pending',
        completed_at_utc=datetime.now(timezone.utc).isoformat(),source_material_modified=False),indent=2)+'\n')
    print('All dependent numerical outputs complete; assistant must still inspect saved contact sheets.',flush=True)


if __name__=='__main__':main()
