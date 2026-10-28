"""Second numerical implementation and frame-exact audit of the real outputs.

This audits measurements and conditional controls; it is not new independent
human annotation, a held-out film, or validation of narrative interpretation.
"""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'analysis-python'))
from cinematicdx import exploration as ex

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();run=args.run
    if (run/'numerical_audit.json').exists():raise ValueError('Audit output already exists.')
    protocol=read(run/'protocol.json');receipt=read(run/'run.json')
    for name,record in receipt['outputs'].items():assert sha(run/name)==record['sha256'],name
    for record in protocol['inputs'].values():assert sha(ROOT/record['path'])==record['sha256'],record['path']
    reference=read(ROOT/protocol['inputs']['manual_reference']['path']);narrative=read(ROOT/protocol['inputs']['narrative_reference']['path'])
    q1=read(run/'Q01_editing/results.json');timing_audit=[]
    # Independent list-based construction, including all discarded gap intervals.
    for scenario,result in zip(reference['scenarios'],q1['results']):
        cuts=sorted(scenario['hard_cuts'],key=lambda x:x['playback_seconds']);runs=[];current=[]
        for a,b in zip(cuts,cuts[1:]):
            ta,tb=a['playback_seconds'],b['playback_seconds']
            crosses=any(ta<g['end_playback_seconds'] and tb>g['start_playback_seconds'] for g in scenario['gradual_transitions'])
            if crosses:
                if current:runs.append(current);current=[]
            else:current.append(tb-ta)
        if current:runs.append(current)
        differences=[abs(math.log(b)-math.log(a)) for run in runs for a,b in zip(run,run[1:])]
        observed=sum(differences)/len(differences)
        assert abs(observed-result['observed']['mean_absolute_log_ratio'])<1e-12
        rng=np.random.default_rng(20261026);null=[]
        for _ in range(1999):
            shuffled=[rng.permutation(r).tolist() for r in runs]
            assert all(sorted(a)==sorted(b) for a,b in zip(runs,shuffled))
            ds=[abs(math.log(b)-math.log(a)) for r in shuffled for a,b in zip(r,r[1:])]
            null.append(sum(ds)/len(ds))
        with np.load(run/'Q01_editing/shuffle_controls.npz',allow_pickle=False) as z:
            assert np.max(np.abs(np.asarray(null)-z[scenario['scenario_id']+'__mean_absolute_log_ratio']))<1e-12
        timing_audit.append(dict(scenario_id=scenario['scenario_id'],verified_interval_count=sum(map(len,runs)),verified_adjacencies=len(differences),
                                observed_recalculated=observed,all_1999_permutations_multisets_verified=True))
    # Pixel exposure integral: arbitrary subsecond controls are measured directly
    # from original frame support, rather than piecewise-constant 1-second bins.
    with np.load(ROOT/protocol['inputs']['gray_cache']['path'],allow_pickle=False) as z:
        starts=z['playback_seconds'];ends=z['next_pts']/16000-.043;gray=z['roi_mean'].astype(float)
    assert np.max(np.abs(ends[:-1]-starts[1:]))<1e-9
    cumulative=np.r_[0,np.cumsum((ends-starts)*gray)]
    def integral(x):
        x=np.asarray(x);i=np.searchsorted(starts,x,side='right')-1
        assert (i>=0).all() and (i<len(starts)).all()
        return cumulative[i]+(x-starts[i])*gray[i]
    def exact_changes(centers):
        centers=np.asarray(centers,float)
        pre=(integral(centers-1)-integral(centers-5))/4
        post=(integral(centers+5)-integral(centers+1))/4
        return np.abs(post-pre)
    centers=[e['start_seconds'] for e in narrative['events'] if e['start_seconds']>150]
    selected_ids=[e['event_id'] for e in narrative['events'] if e['start_seconds']>150]
    raw_csv=list(csv.DictReader((run/'Q02_timeline/per_event_changes.csv').open(encoding='utf-8-sig')))
    recorded=[float(r['absolute_change']) for r in raw_csv if r['signal']=='roi_mean' and r['window_seconds']=='5.0' and r['jitter_seconds']=='0.0']
    exact=exact_changes(centers);assert np.max(np.abs(exact-recorded))<1e-10
    challenges=[]
    for scenario in reference['scenarios']:
        matched=ex.cut_matched_centers(centers,scenario['hard_cuts'],scenario['gradual_transitions'],window=5,draws=1999,seed=20261026)
        selected=matched['selected_events'];actual=float(exact_changes([s['event_seconds'] for s in selected]).mean())
        null=exact_changes(matched['centers']).mean(axis=1)
        # Exact maximum assignment with candidate reuse forbidden within a draw.
        # States assign a subset of the region's event slots. No giant permutation
        # enumeration, downloads, or numerical optimizer is necessary.
        best_total=0;max_anchors={}
        for region in range(3):
            slots=[s for s in selected if s['region']==region]
            if not slots:continue
            candidates=matched['pools'][region];states={0:(0.,[])}
            for anchor in candidates:
                old=dict(states)
                for mask,(total,chosen) in old.items():
                    for i,slot in enumerate(slots):
                        if mask&(1<<i):continue
                        value=float(exact_changes([anchor+slot['event_to_cut_offset']])[0]);newmask=mask|(1<<i)
                        if newmask not in states or states[newmask][0]<total+value:
                            states[newmask]=(total+value,chosen+[(selected_ids[slot['event_index']],anchor)])
            maximum,anchors=states[(1<<len(slots))-1];best_total+=maximum;max_anchors[str(region)]=anchors
        maximum_mean=best_total/len(selected)
        challenges.append(dict(scenario_id=scenario['scenario_id'],method='Original-frame exposure integral; no 1s approximation for control windows.',
             **ex.null_summary(actual,null),maximum_possible_control_mean_under_fixed_pool=maximum_mean,
             maximising_control_anchors=max_anchors,observed_exceeds_maximum_fixed_pool_control=actual>maximum_mean,
             conditional_scope='Conditional descriptive contrast only; constraints/pools remain substantive assumptions, not population inference.'))
    all_images=list(csv.DictReader((run/'Q03_recurrence/representatives.csv').open(encoding='utf-8-sig')))
    pts_to_time={int(round((t+.043)*16000)):t for t in starts}
    image_offsets=[]
    for image in all_images:
        pts=int(image['image_source_pts']);value=float(image['image_playback_seconds']);target=float(image['target_seconds'])
        assert abs(pts/16000-.043-value)<1e-9
        assert float(image['start_seconds'])<=value<float(image['end_seconds'])
        assert 0<=value-target<.1
        assert pts in pts_to_time
        image_offsets.append(value-target)
    with (run/'Q02_timeline/frame_pair_measurements.csv').open(encoding='utf-8-sig') as f:pairs=list(csv.DictReader(f))
    assert sum(p['valid_measurement']=='True' for p in pairs)==1427
    result=dict(artifact_kind='second_implementation_numerical_audit',completed_at_utc=datetime.now(timezone.utc).isoformat(),
        source_and_annotation_digests_unchanged=True,initial_output_digests_unchanged=True,
        editing=timing_audit,primary_event_frame_exact_max_difference=float(np.max(np.abs(exact-recorded))),
        frame_exact_cut_controls=challenges,representative_images_verified=len(all_images),max_target_to_frame_offset_seconds=max(image_offsets),
        motion_valid_pair_count_verified=1427,
        evidence_scope='Numerical/provenance verification; no independent human annotations or theoretical generalisation.',
        script_sha256=sha(__file__))
    write(run/'numerical_audit.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
