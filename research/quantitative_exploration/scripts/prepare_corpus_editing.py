"""Freeze a complete source plan and replay existing independent pilot labels."""
from datetime import datetime,timezone
from fractions import Fraction
import csv
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
import numpy as np
from cinematicdx.corpus_editing import decode_features,gradual_diagnostics,editing_measurements,sha,write_json
from cinematicdx.transition_validation import validate_gradual_transitions
from cinematicdx.ingest import source_state


def read(path):return json.loads(Path(path).read_text())


def score_points(predicted,reference,tolerance):
    predictions=sorted(predicted);truth=sorted(reference);i=j=tp=0;errors=[]
    while i<len(predictions) and j<len(truth):
        error=predictions[i]-truth[j]
        if abs(error)<=tolerance+1e-8:tp+=1;errors.append(error);i+=1;j+=1
        elif error<0:i+=1
        else:j+=1
    fp=len(predictions)-tp;fn=len(truth)-tp
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,
        recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        signed_timing_errors_seconds=errors)


def main():
    old=ROOT/'research-local/studio-luminance/corpus-20261026T083348Z'
    plan=read(old/'plan.json')
    with (old/'analysis_final/film_measurements_and_coverage.csv').open(encoding='utf-8-sig') as f:films=list(csv.DictReader(f))
    measured=[r for r in films if r['eligible']=='True'];lookup={j['job_id']:j for j in plan['jobs']};jobs=[]
    for film in measured:
        job=dict(lookup[film['selected_job_id']]);receipt=read(old/'films'/job['job_id']/'run.json')
        job.update(film_key=film['film_key'],video_version_id=film['video_version_id'],previous_source_state=receipt['source_state'])
        if tuple(job['previous_source_state'])!=source_state(job['source_path']):raise ValueError('Prior source state changed.')
        jobs.append(job)
    run=ROOT/'research-local/studio-editing'/('corpus-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run.mkdir(parents=True,exist_ok=False);(run/'preflight').mkdir()
    config=dict(schema_version=1,scope='All accessible distinct453 film sources, complete frame decoding.454 raw paths, one byte-identical alias.',
        cut_algorithm='PySceneDetect0.7.1 V-only adaptive equivalent; vectorized neighbor width2; all originalPTS; no frame skipping.',
        primary_ratio=3.,sensitivity_ratios=[2.5,3.5],minimum_content=15.,minimum_interval_seconds=.12,analysis_width=320,
        crop_sensitivity='Fixed5%sides10%top/bottom V-only score',
        gradual='Legacy endpoint-mixing default/strict/fade-only, directly16x12 BGR2GRAY ROI cache. Diagnostic, not validated transition counts.',
        near_black_semantics='Thresholded digital gray, not verified photographic fade or original black.',
        job_count=len(jobs),workers=4,codec_threads=2,models_downloaded=False,paid_or_cloud_services=False,
        execution_revision=2,performance_equivalence='Shared VideoReformatter + AUTO2threads; all11 arrays,15248 frames equal to original SLICE1 implementation on frozen pilot. Evidence in corpus-20261026T114005Z/preflight/fast_equivalence_result.json. Original partial run retained.',
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'analysis-python/cinematicdx/corpus_editing.py',ROOT/'analysis-python/cinematicdx/gradual.py',ROOT/'analysis-python/cinematicdx/shots.py']},
        earlier_sampling_not_reused='Prior1Hz luminance samples cannot detect frame-level cuts/transitions; decode every frame.',
        grouping='Exact production.name; equalfilm; coproduction1/k; retain all732 metadata and missing279.',
        validation='Existing ShangGanLing150–750 independent labels, both frame-origin scenarios; not external generalisation.',
        full_neural_policy='Do not launch multi-day TransNetV2 whole-corpus job. Existing15248-frame CPU inference160.39s implies roughly7days serial for661hours at25fps. Existing strict interval validation failed; retain comparator as negative evidence.',
        original_metadata_sha256=plan['metadata_sha256'],original_excel_sha256=read(old/'config.json')['original_excel_sha256'])
    write_json(run/'config.json',config)
    write_json(run/'plan.json',dict(metadata_path=plan['metadata_path'],metadata_sha256=plan['metadata_sha256'],
        previous_luminance_run=str(old),previous_analysis_sha256=sha(old/'analysis_final/run.json'),jobs=jobs,films=plan['films'],
        unavailable_films=[r['film_key'] for r in films if r['video_available']!='True'],
        raw_video_file_count=454,distinct_film_source_count=len(jobs),duplicate_alias_policy='永恒的友谊.mp4 is same bytes as延安游击队.mp4; inherited hash-bound assistant-reviewed mapping, no raw renaming.'))
    (ROOT/'research/quantitative_exploration/ACTIVE_EDITING_RUN.txt').write_text(str(run.relative_to(ROOT))+'\n')
    Path('/tmp/cinematicdx-editing-run').write_text(str(run)+'\n')
    job=next(j for j in jobs if j['film_key']=='shang gan ling')
    print(json.dumps(dict(run=str(run),stage='pilot_preflight_started'),ensure_ascii=False),flush=True)
    arrays,technical=decode_features(job['source_path'],clip=(145.,755.))
    np.savez_compressed(run/'preflight/frame_features.npz',**arrays)
    gradual=gradual_diagnostics(arrays);measured=editing_measurements(arrays,technical,gradual)
    reference_path=ROOT/'research-local/pilot-results/shang-gan-ling-150-750-20261025T225931Z/manual_reference_scenarios.json'
    reference=read(reference_path);hard=[];gradual_scores=[]
    for scenario in reference['scenarios']:
        excludes=[(g['start_playback_seconds'],g['end_playback_seconds']) for g in scenario['gradual_transitions']]
        truth=[c['playback_seconds'] for c in scenario['hard_cuts']]
        for name,data in measured['cuts'].items():
            p=[x for x in data['playback_seconds'] if 150<=x<750 and not any(a<=x<b for a,b in excludes)]
            for tolerance in [.08,.04,.12]:hard.append(dict(scenario_id=scenario['scenario_id'],detector=name,tolerance_seconds=tolerance,**score_points(p,truth,tolerance)))
    for name,result in gradual.items():
        prediction=dict(schema_version=1,prediction_set_id='corpus-preflight-'+name,film_reference=reference['film_reference'],
            video_version_id=reference['video_version_id'],coverage=reference['coverage'],search_complete_within_coverage=True,
            search_scope='entire_declared_coverage',predictions=[dict(item,transition_id=item['candidate_id']) for item in result['predictions']])
        for iou in [.5,.3,.75]:
            scored=validate_gradual_transitions(prediction,reference,iou_threshold=iou)
            for row in scored['results']:gradual_scores.append(dict(detector=name,iou=iou,scenario_id=row['scenario_id'],**row['counts'],**row['localization_metrics']))
        write_json(run/'preflight'/('gradual_'+name+'.json'),result)
    old_cuts=read(ROOT/'research-local/m3/shang-gan-ling-full-luma-001/shots.json')
    old_times=[b['playback_seconds'] for b in old_cuts['boundaries'] if 150<=b['playback_seconds']<750]
    new_times=[x for x in measured['cuts']['primary']['playback_seconds'] if 150<=x<750]
    exact=len(old_times)==len(new_times) and np.allclose(old_times,new_times,rtol=0,atol=1e-9)
    primary=[r for r in hard if r['detector']=='primary' and r['tolerance_seconds']==.08]
    passed=exact and all(r['precision']>=.8 and r['recall']>=.8 for r in primary)
    result=dict(status='PROVISIONAL',hard_cut_preflight_passed=passed,legacy_point_predictions_exactly_reproduced=bool(exact),
        legacy_candidate_count=len(old_times),new_candidate_count=len(new_times),technical=technical,
        hard_cut_validation=hard,gradual_validation=gradual_scores,
        manual_reference_sha256=sha(reference_path),source_version=job['video_version_id'],
        interpretation='Existing within-film developer pilot. Generalisation across studios unverified. Gradual F1 failure means corpus counts are candidate diagnostics only.')
    write_json(run/'preflight/results.json',result)
    write_json(run/'preflight/cuts.json',measured['cuts'])
    snap=run/'source_snapshot';snap.mkdir()
    for file in config['source_hashes']:shutil.copy2(ROOT/file,snap/Path(file).name)
    print(json.dumps(dict(run=str(run),passed=passed,exact_legacy=bool(exact),primary=primary,
        gradual_primary=[r for r in gradual_scores if r['detector']=='default' and r['iou']==.5]),ensure_ascii=False),flush=True)
    if not passed:raise ValueError('Preflight did not meet frozen cut conditions; do not start whole corpus silently.')


if __name__=='__main__':main()
