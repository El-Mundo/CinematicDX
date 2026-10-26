"""Recover completed raw caches rejected solely by epsilon ROI range overshoot.

Original failures and frame_features.npz stay unchanged. EOF is independently
checked from the source tail. A separate effective receipt supersedes failures.
"""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
import av
import cv2
import numpy as np
from cinematicdx.corpus_editing import sha,write_json,gradual_diagnostics,editing_measurements
from cinematicdx.editing_comparison import bounded_roundoff_copy
from cinematicdx.ingest import source_state,hash_video


def read(p):return json.loads(Path(p).read_text())


def recover(job,run):
    out=run/'films'/job['job_id'];began=time.perf_counter();path=Path(job['source_path']);state=source_state(path)
    if state!=tuple(job['previous_source_state']):raise ValueError('Source changed; cannot recover cached measurements.')
    checksum,size,before=hash_video(path)
    if 'sha256:'+checksum!=job['video_version_id'] or before!=state:raise ValueError('Source bytes changed.')
    cache_sha=sha(out/'frame_features.npz')
    with np.load(out/'frame_features.npz',allow_pickle=False) as z:raw={k:z[k] for k in z.files}
    fixed,normalization=bounded_roundoff_copy(raw)
    if not normalization['changes']:raise ValueError('No machine-epsilon range issue found; do not apply this recovery.')
    with av.open(str(path)) as container:
        genuine=[s for s in container.streams.video if not (s.disposition & av.stream.Disposition.attached_pic)]
        if len(genuine)!=1:raise ValueError('Ambiguous source stream.')
        stream=genuine[0];stream.codec_context.thread_count=2;stream.thread_type='AUTO'
        tb=Fraction(stream.time_base);origin=Fraction(stream.start_time or 0)*tb
        duration=float(stream.duration*tb) if stream.duration is not None else float(container.duration/1e6)-float(origin)
        stream_end=(stream.start_time or 0)+stream.duration if stream.duration is not None else None
        # Decode beyond the cached endpoint to actual EOF, never stop at a header duration.
        first=int(np.searchsorted(raw['playback_seconds'],max(0,float(raw['playback_seconds'][-1])-3)))
        container.seek(int(raw['pts'][first]),stream=stream,backward=True,any_frame=False)
        tail=[];last_duration=None
        for frame in container.decode(stream):
            if frame.pts is None:raise ValueError('Tail frame has no PTS.')
            p=Fraction(frame.pts)*frame.time_base/tb
            if p.denominator!=1:raise ValueError('Tail PTS time base mismatch.')
            tick=int(p)
            if tick<int(raw['pts'][first]):continue
            tail.append(tick)
            d=getattr(frame,'duration',None)
            last_duration=int(Fraction(d)*frame.time_base/tb) if isinstance(d,int) and d>0 else None
        if tail!=raw['pts'][first:].tolist():raise ValueError('Cached tail is incomplete or differs from actual source EOF.')
        end=tail[-1]+last_duration if last_duration is not None else stream_end
        if end!=int(raw['next_pts'][-1]):raise ValueError('Cached last display support differs from source EOF.')
        w=min(320,stream.width);h=max(2,round(stream.height*w/stream.width))
        technical=dict(stream_index=stream.index,time_base=str(tb),playback_origin_rational=str(origin),duration_seconds=duration,
            source_width=stream.width,source_height=stream.height,codec=stream.codec_context.name,pixel_format=stream.codec_context.format.name,
            analysis_width=w,analysis_height=h,frames_skipped=False,codec_threads=2,decoder='software CPU,AUTO2,sharedVideoReformatter; metadata reconstructed from header and original complete cache',
            software=dict(pyav=av.__version__,numpy=np.__version__,opencv=cv2.__version__,ffmpeg={k:list(v) for k,v in av.library_versions.items()}),
            cut_signal='Full BGR HSV-V pixelMAD; raw cache unchanged.',gradual_signal='Original16x12 BGR2GRAY ROI cache; only epsilon range overshoot clipped in ROImean/std scalars.',
            requested_clip_seconds=None,end_pts=int(end),end_basis='source_EOF_tail_reverified',reached_eof=True,decoded_frame_count=len(raw['pts']),
            decode_elapsed_seconds=None,actual_start_seconds=float(raw['playback_seconds'][0]),actual_end_seconds=float(end*tb-origin),
            max_frame_support_seconds=float(np.max(raw['frame_delta_seconds'])),tail_frames_reverified=len(tail))
    gradual=gradual_diagnostics(fixed);measured=editing_measurements(raw,technical,gradual)
    normalization.update(original_frame_features_sha256=cache_sha,source_EOF_tail_frames_verified=len(tail),
        script_sha256=sha(__file__),helper_sha256=sha(ROOT/'analysis-python/cinematicdx/editing_comparison.py'),
        original_failure_preserved=True,thresholds_or_annotations_changed=False)
    write_json(out/'roundoff_recovery.json',normalization);write_json(out/'cut_candidates.json',measured['cuts'])
    for name,value in gradual.items():write_json(out/('gradual_'+name+'.json'),value)
    doc=dict(film_key=job['film_key'],video_version_id=job['video_version_id'],job_id=job['job_id'],technical=technical,metrics=measured['metrics'],
        elapsed_seconds=time.perf_counter()-began,elapsed_basis='recovery only; original complete decode time not separately recorded',
        recovery='ROI machine-epsilon range overshoot only; original cache and failure retained',
        prediction_status='PROVISIONAL hardcuts; REJECTED complete gradual-segmentation validity.')
    write_json(out/'summary.json',doc)
    if source_state(path)!=state or sha(out/'frame_features.npz')!=cache_sha:raise ValueError('Source/raw cache changed during recovery.')
    files=['frame_features.npz','roundoff_recovery.json','cut_candidates.json','summary.json']+['gradual_'+name+'.json' for name in gradual]
    write_json(out/'run.json',dict(config_sha256=sha(run/'config.json'),source_state=list(state),source_sha256=checksum,
        full_source_sha256_reverified=True,originals_modified=False,recovery_script_sha256=sha(__file__),
        recovery_helper_sha256=normalization['helper_sha256'],outputs={name:sha(out/name) for name in files}))
    return doc


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();run=args.run.absolute()
    plan=read(run/'plan.json');lookup={j['job_id']:j for j in plan['jobs']};recovered=[];unresolved=[]
    for failure in sorted(run.glob('failure-*.json')):
        error=read(failure);job=lookup[error['job_id']];out=run/'films'/job['job_id']
        if (out/'run.json').exists() and (out/'roundoff_recovery.json').exists():
            recovered.append(job['job_id']);continue
        if 'ROI mean/std must use the declared 0--1 scale' not in error['error'] or not (out/'frame_features.npz').exists():
            unresolved.append(dict(job_id=job['job_id'],reason='Not an eligible completed-cache epsilon error.'));continue
        try:
            doc=recover(job,run);recovered.append(job['job_id'])
            print(json.dumps(dict(recovered=job['title'],frames=doc['metrics']['frame_count'],cut_candidates=doc['metrics']['primary_cut_candidates']),ensure_ascii=False),flush=True)
        except Exception as exc:unresolved.append(dict(job_id=job['job_id'],reason=str(exc)))
    record=dict(recovered_jobs=recovered,unresolved=unresolved,original_failures_and_caches_preserved=True,script_sha256=sha(__file__))
    write_json(run/'roundoff_repairs.json',record)
    if (run/'extraction_complete.json').exists():
        raw=read(run/'extraction_complete.json');effective=dict(raw)
        effective['complete']=list(raw['complete'])+[j for j in recovered if j not in raw['complete']]
        effective['failed']=[j for j in raw['failed'] if j not in recovered]
        effective.update(initial_failed_jobs=raw['failed'],recovered_roundoff_jobs=recovered,
            original_extraction_complete_sha256=sha(run/'extraction_complete.json'),recovery_record_sha256=sha(run/'roundoff_repairs.json'),
            recovery_elapsed_seconds=sum(read(run/'films'/j/'summary.json')['elapsed_seconds'] for j in recovered),
            finalized_at_utc=datetime.now(timezone.utc).isoformat())
        write_json(run/'effective_extraction_complete.json',effective)
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':main()
