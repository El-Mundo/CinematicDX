"""Frame-complete editing measurements; predictions stay separate from truth.

The hard-cut score is exactly PySceneDetect's V-only pixel MAD, evaluated by a
vectorized five-score adaptive window. Original PTS supplies every coordinate.
The legacy endpoint-mixing gradual detector remains a diagnostic comparator.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .gradual import detect_gradual_candidates, configuration_presets
from .ingest import source_state, hash_video
from .shots import _filter_candidates, _source_ticks


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def adaptive_candidates(scores, pts, end_pts, time_base, *, ratio=3., minimum_content=15., minimum_seconds=.12):
    """Equivalent V-only AdaptiveDetector(window_width=2,min_scene_len=0) + PTS filter."""
    values=np.asarray(scores,float);ticks=np.asarray(pts,np.int64)
    if values.ndim!=1 or len(values)!=len(ticks) or len(ticks)<5:
        raise ValueError('At least five aligned scores/PTS required.')
    if not np.isfinite(values).all() or np.any(values<0) or np.any(np.diff(ticks)<=0):
        raise ValueError('Finite nonnegative scores and increasing PTS required.')
    neighbors=(values[:-4]+values[1:-3]+values[3:-1]+values[4:])/4
    target=values[2:-2]
    relative=np.zeros(len(target))
    normal=np.abs(neighbors)>=1e-5
    relative[normal]=np.minimum(target[normal]/neighbors[normal],255)
    relative[~normal & (target>=minimum_content)]=255
    indices=np.flatnonzero((relative>=ratio)&(target>=minimum_content))+2
    accepted,suppressed=_filter_candidates(ticks[indices].tolist(),ticks.tolist(),int(end_pts),Fraction(time_base),Fraction(str(minimum_seconds)))
    return np.asarray(accepted,np.int64),suppressed


def decode_features(path, *, clip=None, analysis_width=320):
    """Decode every presentation frame; keep a small ROI image and scalar signals."""
    import av
    from av.video.reformatter import VideoReformatter
    import cv2
    cv2.setNumThreads(1)
    shared_reformatter=VideoReformatter()
    began=time.perf_counter();ticks=[];scores=[];roi_scores=[];means=[];stds=[];mads=[];cache=[]
    previous_v=previous_roi_v=previous_tiny=None;last_decoded=None;last_duration=None;excluded=None
    with av.open(str(path)) as container:
        streams=[s for s in container.streams.video if not (s.disposition & av.stream.Disposition.attached_pic)]
        if len(streams)!=1:raise ValueError('Exactly one genuine video stream required.')
        stream=streams[0];stream.codec_context.thread_count=2;stream.thread_type='AUTO'
        tb=Fraction(stream.time_base);origin=Fraction(stream.start_time or 0)*tb
        declared_end=(stream.start_time or 0)+stream.duration if stream.duration is not None else None
        duration=float(declared_end*tb-origin) if declared_end is not None else float(container.duration/1e6)-float(origin)
        first,last=clip if clip else (0.,duration)
        technical=dict(stream_index=stream.index,time_base=str(tb),playback_origin_rational=str(origin),
            duration_seconds=duration,source_width=stream.width,source_height=stream.height,codec=stream.codec_context.name,
            pixel_format=stream.codec_context.format.name,analysis_width=min(analysis_width,stream.width),
            analysis_height=max(2,round(stream.height*min(analysis_width,stream.width)/stream.width)),
            software=dict(pyav=av.__version__,numpy=np.__version__,opencv=cv2.__version__,ffmpeg={k:list(v) for k,v in av.library_versions.items()}),
            frames_skipped=False,codec_threads=2,decoder='software CPU, AUTO, shared reformatter',
            cut_signal='Full resized BGR image HSV-V (max B,G,R), no hue/saturation score.',
            gradual_signal='BGR2GRAY centralROI5%sides10%top/bottom; directly AREA regridded16x12 uint8. Not the old64x48 cache.',
            requested_clip_seconds=clip)
        if first>0:container.seek(int((origin+Fraction(str(first)))/tb),stream=stream,backward=True,any_frame=False)
        for frame in container.decode(stream):
            p=_source_ticks(frame.pts,frame.time_base,tb,'Frame')
            if last_decoded is not None and p<=last_decoded:raise ValueError('Non-increasing source PTS; no fabricated timing.')
            last_decoded=p;playback=float(p*tb-origin)
            if playback<first:continue
            if playback>=last:
                excluded=p;break
            if (frame.width,frame.height)!=(technical['source_width'],technical['source_height']):raise ValueError('Geometry changed.')
            bgr=shared_reformatter.reformat(frame,width=technical['analysis_width'],height=technical['analysis_height'],format='bgr24',interpolation='AREA').to_ndarray()
            channels=cv2.split(bgr);v=cv2.max(cv2.max(channels[0],channels[1]),channels[2])
            h,w=v.shape;y0,y1=(h+9)//10,h*9//10;x0,x1=(w+19)//20,w*19//20
            roi_v=v[y0:y1,x0:x1]
            gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY);roi=gray[y0:y1,x0:x1]
            mean,sd=cv2.meanStdDev(roi);tiny=cv2.resize(roi,(16,12),interpolation=cv2.INTER_AREA)
            ticks.append(p);scores.append(cv2.mean(cv2.absdiff(v,previous_v))[0] if previous_v is not None else 0.)
            roi_scores.append(cv2.mean(cv2.absdiff(roi_v,previous_roi_v))[0] if previous_roi_v is not None else 0.)
            means.append(float(mean[0,0])/255);stds.append(float(sd[0,0])/255)
            mads.append(cv2.mean(cv2.absdiff(tiny,previous_tiny))[0]/255 if previous_tiny is not None else float('nan'))
            cache.append(tiny);previous_v=v;previous_roi_v=roi_v.copy();previous_tiny=tiny
            d=getattr(frame,'duration',None);last_duration=_source_ticks(d,frame.time_base,tb,'Duration') if isinstance(d,int) and d>0 else None
        if len(ticks)<5:raise ValueError('Not enough decoded frames.')
        if excluded is not None:end_pts=excluded;basis='first_excluded_frame'
        elif last_duration is not None:end_pts=ticks[-1]+last_duration;basis='last_PTS_plus_frame_duration'
        elif declared_end is not None and declared_end>ticks[-1]:end_pts=declared_end;basis='stream_end'
        else:raise ValueError('No timestamped EOF endpoint.')
    pts=np.asarray(ticks,np.int64);next_pts=np.r_[pts[1:],int(end_pts)]
    if np.any(next_pts<=pts):raise ValueError('Frame display support must be positive.')
    playback=pts.astype(float)*float(tb)-float(origin)
    technical.update(end_pts=int(end_pts),end_basis=basis,reached_eof=excluded is None,
        decoded_frame_count=len(pts),decode_elapsed_seconds=time.perf_counter()-began,
        actual_start_seconds=float(playback[0]),actual_end_seconds=float(end_pts*tb-origin),
        max_frame_support_seconds=float(np.max(next_pts-pts)*float(tb)))
    arrays=dict(pts=pts,next_pts=next_pts,source_seconds=pts.astype(float)*float(tb),playback_seconds=playback,
        frame_delta_seconds=(next_pts-pts).astype(float)*float(tb),v_mad=np.asarray(scores,np.float32),
        roi_v_mad=np.asarray(roi_scores,np.float32),roi_mean=np.asarray(means,float),roi_std=np.asarray(stds,float),
        adjacent_mad=np.asarray(mads,float),gray_cache=np.asarray(cache,np.uint8))
    return arrays,technical


def gradual_diagnostics(arrays, *, presets=('default','strict','fade_only_baseline')):
    features=dict(arrays,evaluation_mask=np.ones(len(arrays['pts']),bool),valid_mask=np.isfinite(arrays['adjacent_mad']))
    configs=configuration_presets();results={}
    for name in presets:
        results[name]=detect_gradual_candidates(features,config=configs[name])
    return results


def editing_measurements(arrays,technical,gradual):
    tb=Fraction(technical['time_base']);origin=float(Fraction(technical['playback_origin_rational']))
    duration=technical['actual_end_seconds']-technical['actual_start_seconds'];cuts={};metrics={}
    for name,ratio in [('primary',3.),('lenient',2.5),('strict',3.5),('roi',3.)]:
        pts,suppressed=adaptive_candidates(arrays['roi_v_mad' if name=='roi' else 'v_mad'],arrays['pts'],technical['end_pts'],tb,ratio=ratio)
        times=pts.astype(float)*float(tb)-origin
        cuts[name]=dict(pts=pts.tolist(),playback_seconds=times.tolist(),suppressed=suppressed)
        metrics[name+'_cut_candidates']=len(pts);metrics[name+'_cut_candidates_per_minute']=60*len(pts)/duration
    t=np.asarray(cuts['primary']['playback_seconds']);intervals=np.diff(t)
    metrics.update(duration_seconds=duration,frame_count=len(arrays['pts']),
        median_cut_bounded_interval_seconds=float(np.median(intervals)) if len(intervals) else None,
        mean_cut_bounded_interval_seconds=float(np.mean(intervals)) if len(intervals) else None,
        edge_intervals_excluded=True,intervals_are_verified_shots=False,
        mean_abs_adjacent_log_interval_change=float(np.mean(np.abs(np.diff(np.log(intervals))))) if len(intervals)>1 else None,
        max_frame_support_seconds=technical['max_frame_support_seconds'])
    for name,result in gradual.items():
        candidates=result['predictions'];spans=[(r['start_playback_seconds'],r['end_playback_seconds']) for r in candidates]
        union=[]
        for a,b in sorted(spans):
            if union and a<=union[-1][1]:union[-1][1]=max(b,union[-1][1])
            else:union.append([a,b])
        metrics[name+'_gradual_candidates']=len(spans);metrics[name+'_gradual_candidates_per_minute']=60*len(spans)/duration
        metrics[name+'_gradual_candidate_union_fraction']=sum(b-a for a,b in union)/duration
    primary_spans=[(p['start_playback_seconds'],p['end_playback_seconds']) for p in gradual['default']['predictions']]
    metrics['cut_candidates_in_gradual_candidate_spans']=sum(any(a<=x<b for a,b in primary_spans) for x in t)
    safe=[b-a for a,b in zip(t,t[1:]) if not any(min(b,y)>max(a,x) for x,y in primary_spans)]
    metrics['candidate_gradual_free_cut_bounded_interval_n']=len(safe)
    metrics['candidate_gradual_free_interval_median_seconds']=float(np.median(safe)) if safe else None
    return dict(cuts=cuts,metrics=metrics)


def run_job(job,run_directory,config_hash):
    run=Path(run_directory);out=run/'films'/job['job_id'];out.mkdir(parents=True,exist_ok=True)
    path=Path(job['source_path']);state=source_state(path)
    if (out/'run.json').exists():
        receipt=json.loads((out/'run.json').read_text())
        if receipt['config_sha256']!=config_hash or tuple(receipt['source_state'])!=state:raise ValueError('Changed job input/config; use new run.')
        for f,s in receipt['outputs'].items():
            if sha(out/f)!=s:raise ValueError('Changed derived output; cannot reuse.')
        return json.loads((out/'summary.json').read_text())
    began=time.perf_counter()
    checksum,size,hashed_state=hash_video(path)
    if 'sha256:'+checksum!=job['video_version_id']:raise ValueError('Original source bytes changed.')
    if tuple(job['previous_source_state'])!=state or hashed_state!=state:raise ValueError('Source changed from prior identity/measurement.')
    arrays,technical=decode_features(path)
    np.savez_compressed(out/'frame_features.npz',**arrays)
    gradual=gradual_diagnostics(arrays)
    measured=editing_measurements(arrays,technical,gradual)
    write_json(out/'cut_candidates.json',measured['cuts'])
    for name,data in gradual.items():write_json(out/('gradual_'+name+'.json'),data)
    document=dict(film_key=job['film_key'],video_version_id=job['video_version_id'],job_id=job['job_id'],
        technical=technical,metrics=measured['metrics'],elapsed_seconds=time.perf_counter()-began,
        prediction_status='PROVISIONAL hard cuts; REJECTED for validated complete gradual segmentation; candidates retained for diagnostics.')
    write_json(out/'summary.json',document)
    if source_state(path)!=state:raise ValueError('Source changed during processing; no success receipt.')
    names=['frame_features.npz','cut_candidates.json','summary.json']+['gradual_'+x+'.json' for x in gradual]
    write_json(out/'run.json',dict(config_sha256=config_hash,source_state=list(state),source_sha256=checksum,
        full_source_sha256_reverified=True,originals_modified=False,outputs={f:sha(out/f) for f in names}))
    return document
