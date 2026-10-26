"""Replay a saved design into a fresh directory, keeping previous runs immutable."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--from-run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.expanduser().absolute()
    output.relative_to(ROOT/'research-local')
    if output.exists():raise ValueError('Replay output must not exist.')
    protocol=json.loads((args.from_run/'protocol.json').read_text())
    protocol['output_directory']=str(output.relative_to(ROOT));protocol['replay_of']=str(args.from_run.absolute())
    output.mkdir(parents=True);(output/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
    subprocess.run([sys.executable,str(Path(__file__).with_name('run_exploration.py')),'--protocol',str(output/'protocol.json')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(Path(__file__).with_name('challenge_results.py')),'--run',str(output)],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(Path(__file__).with_name('audit_results.py')),'--run',str(output)],check=True,cwd=ROOT)

if __name__=='__main__':main()
