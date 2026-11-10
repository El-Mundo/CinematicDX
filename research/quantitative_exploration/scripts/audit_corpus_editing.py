"""Independent scalar/time provenance checks of complete editing outputs."""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import csv
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
import numpy as np
from cinematicdx.corpus_editing import sha,write_json
from cinematicdx.ingest import source_state


def read(p):return json.loads(Path(p).read_text())


def verify_configuration_binding(run, job, receipt, config, config_sha, reuse):
    """Accept inherited measurements only with their original receipt and method."""
    if receipt['config_sha256'] == config_sha:
        return False
    if reuse is None or reuse.get('schema_version') != 1:
        raise ValueError('A different measurement config requires a versioned reuse manifest.')
    matches = [entry for entry in reuse['inherited_jobs'] if entry['job_id'] == job['job_id']]
    if len(matches) != 1 or job['job_id'] in reuse['new_job_ids']:
        raise ValueError('Inherited job must have exactly one unambiguous reuse record.')
    inherited = matches[0]
    parent = Path(inherited['parent_run'])
    if not parent.is_absolute():
        parent = ROOT / parent
    parent_config_path = parent / 'config.json'
    parent_receipt_path = parent / 'films' / job['job_id'] / 'run.json'
    current_receipt_path = run / 'films' / job['job_id'] / 'run.json'
    if parent.resolve() == run.resolve():
        raise ValueError('A reused receipt must identify an earlier run.')
    if inherited['config_sha256'] != receipt['config_sha256'] or sha(parent_config_path) != inherited['config_sha256']:
        raise ValueError('Inherited config digest does not match the original run.')
    if sha(parent_receipt_path) != inherited['receipt_sha256'] or sha(current_receipt_path) != inherited['receipt_sha256']:
        raise ValueError('Inherited receipt differs from its preserved parent receipt.')
    if inherited['video_version_id'] != job['video_version_id'] or job['video_version_id'] != 'sha256:' + receipt['source_sha256']:
        raise ValueError('Inherited measurements refer to a different video version.')
    descriptive_fields = {'scope', 'job_count', 'grouping', 'refresh_parent_run'}
    parent_config = read(parent_config_path)
    current_method = {key: value for key, value in config.items() if key not in descriptive_fields}
    inherited_method = {key: value for key, value in parent_config.items() if key not in descriptive_fields}
    if current_method != inherited_method:
        raise ValueError('Inherited measurements use a different extraction method or parameter.')
    return True


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);args=p.parse_args();run=args.run.absolute()
    output=run/'numerical_audit.json'
    if output.exists():raise ValueError('Audit exists; preserve it.')
    plan=read(run/'plan.json');config=read(run/'config.json');summary=read(run/'analysis/summary.json');done=read(run/'effective_extraction_complete.json')
    config_sha=sha(run/'config.json')
    reuse_path=run/'measurement_reuse.json'
    reuse=read(reuse_path) if reuse_path.exists() else None
    inherited_jobs=[]
    for name,digest in config['source_hashes'].items():assert sha(ROOT/name)==digest
    assert sha(plan['metadata_path'])==plan['metadata_sha256']
    assert sha(ROOT/'outputs/01a17483-82c6-7510-8251-931dcb5d21d8/上甘岭_10分钟人工标注模板.xlsx')==config['original_excel_sha256']
    films=[];frames=0;counts=0;gradual_counts=0;modified=[];checks=[]
    with (run/'analysis/film_measurements_and_coverage.csv').open(encoding='utf-8-sig') as f:films=list(csv.DictReader(f))
    for job in plan['jobs']:
        directory=run/'films'/job['job_id']
        if not (directory/'run.json').exists():continue
        receipt=read(directory/'run.json');doc=read(directory/'summary.json');cut=read(directory/'cut_candidates.json')
        if verify_configuration_binding(run,job,receipt,config,config_sha,reuse):
            inherited_jobs.append(job['job_id'])
        assert doc['film_key']==job['film_key'] and doc['video_version_id']==job['video_version_id']=='sha256:'+receipt['source_sha256']
        assert doc['technical']['reached_eof'] and receipt['full_source_sha256_reverified']
        for name,digest in receipt['outputs'].items():assert sha(directory/name)==digest
        if source_state(job['source_path'])!=tuple(receipt['source_state']):modified.append(job['film_key'])
        with np.load(directory/'frame_features.npz',allow_pickle=False) as z:
            pts=z['pts'];next_pts=z['next_pts'];times=z['playback_seconds'];scores=z['v_mad']
        tb=Fraction(doc['technical']['time_base']);origin=Fraction(doc['technical']['playback_origin_rational'])
        assert np.all(np.diff(pts)>0) and np.array_equal(next_pts[:-1],pts[1:])
        assert np.max(np.abs(times-(pts.astype(float)*float(tb)-float(origin))))<1e-8
        assert len(pts)==doc['metrics']['frame_count'];frames+=len(pts)
        # Independent scalar rolling-window and chronological PTS suppression.
        candidates=[]
        for i in range(2,len(scores)-2):
            score=float(scores[i]);average=math.fsum(float(scores[j]) for j in [i-2,i-1,i+1,i+2])/4
            ratio=min(score/average,255.) if abs(average)>=1e-5 else 255. if score>=15 else 0.
            if score>=15 and ratio>=3:candidates.append(int(pts[i]))
        accepted=[]
        for tick in candidates:
            previous=accepted[-1] if accepted else int(pts[0])
            if tick>pts[0] and tick<next_pts[-1] and (tick-previous)*tb>=Fraction(12,100):accepted.append(tick)
        while accepted and (int(next_pts[-1])-accepted[-1])*tb<Fraction(12,100):accepted.pop()
        assert accepted==cut['primary']['pts']
        count=len(accepted);counts+=count;duration=(int(next_pts[-1])-int(pts[0]))*tb
        assert abs(60*count/float(duration)-doc['metrics']['primary_cut_candidates_per_minute'])<1e-9
        gradual=read(directory/'gradual_default.json');gradual_counts+=len(gradual['predictions'])
        assert len(gradual['predictions'])==doc['metrics']['default_gradual_candidates']
        checks.append(dict(film_key=job['film_key'],frame_count=len(pts),cut_candidates=count,scalar_exact_match=True))
    assert frames==summary['decoded_frames'] and counts==summary['total_cut_candidates'] and gradual_counts==summary['total_gradual_candidates']
    assert len(films)==732 and {f['film_key'] for f in films}=={f['film_key'] for f in plan['films']}
    with (run/'analysis/studio_summary_all.csv').open(encoding='utf-8-sig') as f:groups=list(csv.DictReader(f))
    weight_sum=0.;group_checks=[]
    for g in groups:
        members=[(f,s['fractional_weight']) for f in films if f['measured']=='True' for s in json.loads(f['studios']) if s['studio_id']==g['studio_id']]
        weight_sum+=math.fsum(w for f,w in members)
        if members:
            mean=math.fsum(float(f['primary_cut_candidates_per_minute'])*w for f,w in members)/math.fsum(w for f,w in members)
            assert abs(mean-float(g['primary_cut_candidates_per_minute__mean']))<1e-9
            group_checks.append(dict(studio=g['studio'],n=len(members),rate_mean_verified=True))
    assert abs(weight_sum-summary['measured_films'])<1e-8 and not modified
    write_json(output,dict(status='VERIFIED numerical/provenance assertions only',completed_at_utc=datetime.now(timezone.utc).isoformat(),
        decoded_frames=frames,cut_candidates=counts,gradual_candidates=gradual_counts,source_states_changed=modified,
        originals_sha256_unchanged=True,film_checks=checks,studio_checks=group_checks,metadata_rows_verified=732,
        inherited_receipts_verified=inherited_jobs,measurement_reuse_manifest_sha256=sha(reuse_path) if reuse_path.exists() else None,
        interpretation='This does not establish fullcorpus cut/transition precision, true photographic transitions or studio style.',script_sha256=sha(__file__)))
    print(json.dumps(dict(audit='passed',films=len(checks),frames=frames,cuts=counts,gradual_candidates=gradual_counts)))


if __name__=='__main__':main()
