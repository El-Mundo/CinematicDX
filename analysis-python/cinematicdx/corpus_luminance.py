"""Read-only whole-video digital-gray measurements and explicit studio membership.

Keyframe samples are timestamped observations, not shots. Temporal weights are a
bounded nearest-observation approximation, never claimed as decoded frame truth.
"""
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from .ingest import hash_video, source_state, utc_now, publish_bundle, json_bytes
from .inventory import inventory_directory, load_metadata


def studio_memberships(production):
    rows=[];seen=set()
    for raw in production or []:
        name=raw.get('name')
        if not isinstance(name,str) or not name.strip():continue
        name=name.strip()
        if name in seen:continue
        seen.add(name)
        rows.append(dict(studio_id='studio:'+hashlib.sha256(name.encode()).hexdigest()[:16],name=name,
                         chn=raw.get('chn') or name,eng=raw.get('eng'),category=raw.get('category')))
    if not rows:rows=[dict(studio_id='studio:unknown',name='Unknown',chn='未知制片机构',eng=None,category=None)]
    for row in rows:row['fractional_weight']=1/len(rows)
    return rows


def build_plan(metadata_path,video_root,identity_map_path):
    metadata=load_metadata(metadata_path);inventory=inventory_directory(video_root,metadata_path)
    identities=json.loads(Path(identity_map_path).read_text())
    metadata_sha=hashlib.sha256(Path(metadata_path).read_bytes()).hexdigest()
    if identities['metadata_source_sha256']!=metadata_sha:raise ValueError('Existing identity map refers to different metadata.')
    overrides={b['relative_path']:b for b in identities['bindings']};records={r['film_key']:r for r in metadata['records']}
    jobs=[];linked=set()
    for item in inventory['videos']:
        rel=item['relative_path'];candidates=item['metadata_candidates'];override=overrides.get(rel)
        if override:
            key=override['film_key']
            if key not in {c['film_key'] for c in candidates}:raise ValueError('Explicit binding conflicts with filename candidates.')
            status=override['validation_status'];expected=override['video_version_id']
        elif len(candidates)==1:key=candidates[0]['film_key'];status='provisional_unique_filename_match';expected=None
        else:key=None;status='unresolved_identity';expected=None
        record=records.get(key)
        jobs.append(dict(job_id=hashlib.sha256(rel.encode()).hexdigest()[:16],relative_path=rel,
             source_path=str(Path(video_root)/rel),size_bytes=item['size_bytes'],mtime_ns=item['mtime_ns'],
             film_key=key,title=record['title_original'] if record else None,year=record['production_year'] if record else None,
             colour=record['raw_record'].get('colour') if record else None,film_type=record['raw_record'].get('filmType') if record else None,
             linkage_status=status,expected_video_version_id=expected,
             metadata_candidates=candidates,studios=studio_memberships(record['raw_record'].get('production')) if record else []))
        if key:linked.add(key)
    films=[]
    for record in metadata['records']:
        raw=record['raw_record'];films.append(dict(film_key=record['film_key'],title=record['title_original'],year=record['production_year'],
               colour=raw.get('colour'),film_type=raw.get('filmType'),studios=studio_memberships(raw.get('production')),
               video_available_by_current_linkage=record['film_key'] in linked))
    return dict(schema_version=1,artifact_kind='studio_luminance_corpus_plan',created_at_utc=utc_now(),
        metadata_path=str(Path(metadata_path).resolve()),metadata_sha256=metadata_sha,video_root=str(Path(video_root).resolve()),
        identity_map_path=str(Path(identity_map_path).resolve()),identity_map_sha256=hashlib.sha256(Path(identity_map_path).read_bytes()).hexdigest(),
        metadata_count=len(films),video_file_count=len(jobs),distinct_linked_film_count=len(linked),
        inventory_summary=inventory['summary'],films=films,jobs=jobs,
        linkage_limitation='Unique filename links are provisional; only four prior ambiguous files have assistant opening-credit review. No blanket human identity confirmation.')


def measurement(gray):
    h,w=gray.shape;x0=(w+19)//20;x1=w*19//20;y0=(h+9)//10;y1=h*9//10
    roi=gray[y0:y1,x0:x1].astype(np.float64)/255
    return dict(roi_mean=float(roi.mean()),full_mean=float(gray.mean()/255),roi_spatial_std=float(roi.std()),
                roi_near_black_fraction=float((roi<=5/255).mean()),roi_near_white_fraction=float((roi>=250/255).mean()))


def representation_intervals(times,duration,max_gap=5.):
    t=np.asarray(times,float)
    if len(t)<2 or not np.isfinite(t).all() or np.any(np.diff(t)<=0) or duration<=0:raise ValueError('Ordered distinct timestamps and positive duration required.')
    mid=(t[:-1]+t[1:])/2
    left=np.maximum(np.r_[0,mid],t-max_gap/2)
    right=np.minimum(np.r_[mid,duration],t+max_gap/2)
    left=np.maximum(left,0);right=np.minimum(right,duration)
    if np.any(right<=left):raise ValueError('Sample lies outside source duration.')
    return left,right


def bin_samples(left,right,values,edges):
    left,right,values=np.asarray(left),np.asarray(right),np.asarray(values)
    result=[];coverage=[]
    for a,b in zip(edges,edges[1:]):
        w=np.maximum(0,np.minimum(right,b)-np.maximum(left,a));valid=np.isfinite(values);support=w[valid].sum()
        coverage.append(float(support/(b-a)));result.append(float(np.dot(w[valid],values[valid])/support) if support>0 else np.nan)
    return np.asarray(result),np.asarray(coverage)


def finite_change(values):
    values=np.asarray(values,float);ok=np.isfinite(values[:-1])&np.isfinite(values[1:])
    return float(np.abs(np.diff(values))[ok].mean()) if ok.any() else None


def summarize_samples(arrays,duration):
    t=arrays['playback_seconds'];left,right=representation_intervals(t,duration);weights=right-left
    mean=float(np.dot(weights,arrays['roi_mean'])/weights.sum())
    sd=float(np.sqrt(np.dot(weights,(arrays['roi_mean']-mean)**2)/weights.sum()))
    edges=np.linspace(0,duration,101);curve,cover=bin_samples(left,right,arrays['roi_mean'],edges)
    curve[cover<.8]=np.nan
    full_curve,full_cover=bin_samples(left,right,arrays['full_mean'],edges);full_curve[full_cover<.8]=np.nan
    contrast,contrast_cover=bin_samples(left,right,arrays['roi_spatial_std'],edges);contrast[contrast_cover<.8]=np.nan
    e30=np.r_[np.arange(0,duration,30.),duration];b30,c30=bin_samples(left,right,arrays['roi_mean'],e30);b30[c30<.8]=np.nan
    widths=np.diff(e30);b30[widths<15]=np.nan
    core=(e30[:-1]>=.1*duration)&(e30[1:]<=.9*duration);core_values=b30.copy();core_values[~core]=np.nan
    raw_change=finite_change(b30);core_change=finite_change(core_values)
    coverage=float(weights.sum()/duration);gaps=np.diff(t)
    quality=[]
    if coverage<.98:quality.append('temporal_representation_coverage_below_98pct')
    if np.nanmean(cover>=.8)<.98:quality.append('insufficient_position_bins')
    if sd<1e-4:quality.append('near_constant_temporal_gray')
    if len(t)<30:quality.append('too_few_samples')
    z=(curve-mean)/sd if sd>=1e-4 else np.full(100,np.nan)
    z_full=(full_curve-np.dot(weights,arrays['full_mean'])/weights.sum())
    full_sd=float(np.sqrt(np.dot(weights,(arrays['full_mean']-np.dot(weights,arrays['full_mean'])/weights.sum())**2)/weights.sum()))
    z_full=z_full/full_sd if full_sd>=1e-4 else np.full(100,np.nan)
    result=dict(duration_seconds=float(duration),sample_count=len(t),first_sample_seconds=float(t[0]),last_sample_seconds=float(t[-1]),
         median_sample_gap_seconds=float(np.median(gaps)),p95_sample_gap_seconds=float(np.quantile(gaps,.95)),max_sample_gap_seconds=float(gaps.max()),
         temporal_representation_coverage=coverage,gray_roi_time_mean=mean,gray_roi_temporal_sd=sd,
         gray_full_time_mean=float(np.dot(weights,arrays['full_mean'])/weights.sum()),
         roi_spatial_contrast_mean=float(np.dot(weights,arrays['roi_spatial_std'])/weights.sum()),
         roi_near_black_fraction=float(np.dot(weights,arrays['roi_near_black_fraction'])/weights.sum()),
         roi_near_white_fraction=float(np.dot(weights,arrays['roi_near_white_fraction'])/weights.sum()),
         mean_abs_change_30s_raw=raw_change,mean_abs_change_30s_z=raw_change/sd if raw_change is not None and sd>=1e-4 else None,
         core_10_90_mean_abs_change_30s_z=core_change/sd if core_change is not None and sd>=1e-4 else None,
         usable_30s_bin_count=int(np.isfinite(b30).sum()),valid_position_bin_count=int(np.isfinite(curve).sum()),
         quality_flags=quality,eligible_for_group_comparison=not quality)
    profiles=dict(position_bin_start_fraction=np.arange(100)/100,position_bin_end_fraction=np.arange(1,101)/100,
                  roi_gray_mean=curve,roi_z=z,full_gray_mean=full_curve,full_z=z_full,roi_spatial_contrast=contrast,
                  representation_fraction=cover,bin30_start_seconds=e30[:-1],bin30_end_seconds=e30[1:],bin30_roi_gray=b30,bin30_representation_fraction=c30)
    return result,profiles


def needs_dense_fallback(summary):
    return (summary['temporal_representation_coverage']<.98 or summary['median_sample_gap_seconds']>1.5
            or summary['p95_sample_gap_seconds']>2 or summary['valid_position_bin_count']<98)


def extract_samples(path,*,mode='keyframes',clip=None):
    import av
    rows=[];counts=0;began=time.perf_counter()
    with av.open(str(path)) as container:
        genuine=[s for s in container.streams.video if not (s.disposition & av.stream.Disposition.attached_pic)]
        if len(genuine)!=1:raise ValueError('A unique genuine video stream is required.')
        stream=genuine[0];stream.codec_context.thread_count=1;stream.thread_type='SLICE'
        tb=Fraction(stream.time_base);origin=Fraction(stream.start_time or 0)*tb
        duration=float(stream.duration*tb) if stream.duration is not None else float(container.duration/1e6)-float(origin)
        metadata=dict(stream_index=stream.index,time_base=str(tb),playback_origin_rational=str(origin),duration_seconds=duration,
             width=stream.width,height=stream.height,codec=stream.codec_context.name,pixel_format=stream.codec_context.format.name,
             sample_aspect_ratio=str(stream.sample_aspect_ratio),reported_frame_rate=str(stream.average_rate),
             color_range=str(stream.codec_context.color_range),color_space=str(stream.codec_context.colorspace),
             software=dict(pyav=av.__version__,numpy=np.__version__,ffmpeg_libraries={k:list(v) for k,v in av.library_versions.items()}))
        if mode=='keyframes':stream.codec_context.skip_frame='NONKEY'
        elif mode=='reference_1hz':stream.codec_context.skip_frame='NONREF'
        elif mode!='dense_1hz':raise ValueError('Unknown sampling mode.')
        if clip:
            start,end=clip;container.seek(int((Fraction(str(start))+origin)/tb),stream=stream,backward=True,any_frame=False)
        else:start,end=0.,duration
        target=start
        for frame in container.decode(stream):
            if frame.pts is None:raise ValueError('A decoded frame lacks PTS.')
            source=Fraction(frame.pts)*frame.time_base;playback=float(source-origin)
            if playback<start-1e-8:continue
            if playback>=end:break
            counts+=1
            if mode in ('dense_1hz','reference_1hz') and playback+1e-8<target:continue
            if mode in ('dense_1hz','reference_1hz'):target=math.floor(playback-start+1e-8)+start+1
            w=min(160,frame.width);h=max(16,round(frame.height*w/frame.width))
            gray=frame.reformat(width=w,height=h,format='gray',interpolation='AREA').to_ndarray()
            rows.append(dict(pts=int(frame.pts),source_seconds=float(source),playback_seconds=playback,**measurement(gray)))
        metadata.update(mode=mode,decode_eof_or_clip_end=True,frames_returned_by_decoder=counts,elapsed_seconds=time.perf_counter()-began,
                        gray_resize='libswscale AREA, width<=160, preserved coded aspect; fixed5% horizontal/10% vertical ROI',
                        all_frames_decoded_within_requested_range=mode=='dense_1hz',requested_clip_seconds=clip,
                        sampling_is_not_shot_detection=True)
    if len(rows)<2:raise ValueError('Too few timestamped observations.')
    arrays={k:np.asarray([r[k] for r in rows],dtype=np.int64 if k=='pts' else np.float64) for k in rows[0]}
    if np.any(np.diff(arrays['pts'])<=0):raise ValueError('Nonmonotonic or duplicate source PTS.')
    return arrays,metadata


def run_film_job(job,run_dir,config_sha):
    destination=Path(run_dir)/'films'/job['job_id'];receipt_path=destination/'run.json'
    if receipt_path.exists():
        old=json.loads(receipt_path.read_text());summary=json.loads((destination/'summary.json').read_text())
        if old['config_sha256']!=config_sha or tuple(old['source_state'])!=source_state(job['source_path']):raise ValueError('Resume input/config changed.')
        for filename,record in old['outputs'].items():
            if hashlib.sha256((destination/filename).read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Saved film result changed.')
        return summary
    if destination.exists():raise ValueError('Partial film directory exists; preserve and inspect it.')
    began=time.perf_counter();digest,size,before=hash_video(job['source_path']);version='sha256:'+digest
    if job.get('expected_video_version_id') and job['expected_video_version_id']!=version:raise ValueError('Previously reviewed identity binding SHA no longer matches.')
    arrays,technical=extract_samples(job['source_path'],mode='reference_1hz');summary,profiles=summarize_samples(arrays,technical['duration_seconds'])
    initial_summary=summary;initial_arrays=None
    if needs_dense_fallback(summary):
        initial_arrays=arrays;arrays,technical=extract_samples(job['source_path'],mode='dense_1hz');summary,profiles=summarize_samples(arrays,technical['duration_seconds'])
    if source_state(job['source_path'])!=before:raise ValueError('Source changed during measurement.')
    doc=dict(schema_version=1,artifact_kind='film_digital_gray_measurements',film_reference={'namespace':'research-inventory','key':job['film_key']},
             video_version_id=version,job=job,summary=summary,technical=technical,
             sampling_fallback_performed=initial_arrays is not None,initial_reference_summary=initial_summary,
             historical_transfer_provenance='unknown',validation_status='PROVISIONAL',elapsed_seconds=time.perf_counter()-began)
    import io
    def npz_bytes(values):
        stream=io.BytesIO();np.savez_compressed(stream,**values);return stream.getvalue()
    payloads={'summary.json':json_bytes(doc),'samples.npz':npz_bytes(arrays),'profiles.npz':npz_bytes(profiles)}
    if initial_arrays is not None:payloads['initial_reference_samples.npz']=npz_bytes(initial_arrays)
    receipt=dict(schema_version=1,status='complete',completed_at_utc=utc_now(),video_version_id=version,source_bytes=size,
          source_state=before,config_sha256=config_sha,source_modified=False,
          outputs={name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in payloads.items()})
    payloads['run.json']=json_bytes(receipt);publish_bundle(destination,payloads)
    return doc
