"""One bounded dependent pipeline: wait for extraction, aggregate once, create QA.

This is a single local job, not a recurring automation. Original files are read
only. A missing completion marker never becomes a successful research report.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--max-wait-hours',type=float,default=6);args=p.parse_args();run=args.run.absolute()
    started=time.monotonic()
    try:
        while not (run/'extraction_complete.json').exists():
            if time.monotonic()-started>args.max_wait_hours*3600:raise TimeoutError('Extraction has not published its completion record within the bounded wait.')
            time.sleep(10)
        for script,target in [('analyse_studio_corpus.py',run/'analysis/run.json'),('inspect_corpus_sources.py',run/'source_qa/selection_and_receipt.json'),('audit_studio_corpus.py',run/'corpus_audit.json')]:
            if not target.exists():subprocess.run([sys.executable,str(Path(__file__).with_name(script)),'--run',str(run)],cwd=ROOT,check=True)
        marker=dict(status='numerical_report_ready_visual_review_pending',completed_at_utc=datetime.now(timezone.utc).isoformat(),
            report=str(ROOT/'research/quantitative_exploration/corpus_studio/REPORT.md'),source_and_annotation_originals_modified=False)
        (run/'analysis_pipeline_complete.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2)+'\n');print(json.dumps(marker,ensure_ascii=False),flush=True)
    except Exception as exc:
        (run/'analysis_pipeline_error.json').write_text(json.dumps(dict(status='not_complete',utc=datetime.now(timezone.utc).isoformat(),error_type=type(exc).__name__,error=str(exc)),ensure_ascii=False,indent=2)+'\n')
        raise

if __name__=='__main__':main()
