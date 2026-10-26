"""Seeded studio-balanced qualitative audit frames, not independent accuracy labels."""
import argparse
from fractions import Fraction
import json
import shutil
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
import av
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from cinematicdx.corpus_editing import sha,write_json
from cinematicdx.ingest import source_state
from cinematicdx.shots import _source_ticks


def read(path):return json.loads(Path(path).read_text())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True,type=Path);args=parser.parse_args();run=args.run.absolute()
    plan=read(run/'plan.json');out=run/'visual_qa';out.mkdir(exist_ok=False)
    rng=np.random.default_rng(20261026);studios={s['studio_id']:s for f in plan['films'] for s in f['studios']};selected={};reasons={}
    for sid in sorted(studios):
        jobs=[j for j in plan['jobs'] if any(s['studio_id']==sid for s in j['studios']) and (run/'films'/j['job_id']/'run.json').exists()]
        if jobs:
            job=jobs[int(rng.integers(len(jobs)))];selected[job['job_id']]=job;reasons.setdefault(job['job_id'],[]).append(studios[sid]['chn'])
    records=[];tiles=[];font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',13)
    for job in selected.values():
        folder=run/'films'/job['job_id'];doc=read(folder/'summary.json');receipt=read(folder/'run.json')
        if source_state(job['source_path'])!=tuple(receipt['source_state']):raise ValueError('Source changed before QA.')
        with np.load(folder/'frame_features.npz',allow_pickle=False) as z:pts=z['pts'];times=z['playback_seconds']
        cuts=read(folder/'cut_candidates.json')['primary']['pts'];gradual=read(folder/'gradual_default.json')['predictions']
        strict=read(folder/'gradual_strict.json')['predictions'];events=[]
        if cuts:
            tick=cuts[int(rng.integers(len(cuts)))];i=int(np.searchsorted(pts,tick))
            events.append(('hard_cut_candidate',tick,[max(0,min(len(pts)-1,i+d)) for d in [-2,-1,0,1,2]]))
        if gradual:
            # Independent random choice, including candidates also emitted by strict.
            g=gradual[int(rng.integers(len(gradual)))];a,b=g['start_playback_seconds'],g['end_playback_seconds']
            indices=[int(np.argmin(np.abs(times-t))) for t in [a-.12,a,(a+b)/2,b,b+.12]]
            events.append(('gradual_candidate_'+g['predicted_type'],g['start_pts'],indices))
        with av.open(job['source_path']) as container:
            stream=next(s for s in container.streams.video if s.index==doc['technical']['stream_index']);stream.codec_context.thread_count=1;tb=Fraction(stream.time_base)
            for kind,anchor,indices in events:
                images=[];frame_records=[];wanted={int(pts[index]) for index in indices};found_images={}
                # Some MP4 indexes lead a direct seek past a B-frame. Decode
                # sequentially from earlier context; never substitute a later frame.
                for preroll in [2,10,60]:
                    seek_tick=max(stream.start_time or 0,min(wanted)-int(Fraction(preroll)/tb))
                    container.seek(seek_tick,stream=stream,backward=True,any_frame=False)
                    found_images={}
                    for frame in container.decode(stream):
                        if frame.pts is None:continue
                        tick=_source_ticks(frame.pts,frame.time_base,tb,'QA frame')
                        if tick in wanted:
                            found_images[tick]=Image.fromarray(frame.reformat(width=240,height=round(frame.height*240/frame.width),format='rgb24',interpolation='AREA').to_ndarray())
                        if tick>=max(wanted):break
                    if wanted.issubset(found_images):break
                if not wanted.issubset(found_images):raise ValueError(f'Exact QA source frames unavailable for {job["title"]}: missing{sorted(wanted-set(found_images))}')
                for column,index in enumerate(indices):
                    tick=int(pts[index]);image=found_images[tick]
                    name=f'{job["job_id"]}-{kind}-{column}.jpg';image.save(out/name,quality=90);images.append(image)
                    frame_records.append(dict(filename=name,source_pts=tick,time_base=str(tb),playback_seconds=float(times[index]),
                        earlier_seek_preroll_seconds=preroll,exact_original_pts_verified=True,sha256=sha(out/name)))
                label=' / '.join(reasons[job['job_id']])+' '+job['title']+' '+kind+' '+f'{float(anchor*tb-Fraction(doc["technical"]["playback_origin_rational"])):.3f}s'
                tiles.append((images,label))
                records.append(dict(film_key=job['film_key'],video_version_id=job['video_version_id'],studios=reasons[job['job_id']],kind=kind,anchor_pts=int(anchor),
                    frames=frame_records,assistant_interpretation='pending',independent_human_ground_truth=False))
        if source_state(job['source_path'])!=tuple(receipt['source_state']):raise ValueError('Source changed during QA.')
    for page in range((len(tiles)+5)//6):
        rows=tiles[page*6:(page+1)*6];sheet=Image.new('RGB',(1220,len(rows)*230),'white');draw=ImageDraw.Draw(sheet)
        for row,(images,label) in enumerate(rows):
            for column,image in enumerate(images):
                image.thumbnail((240,195));sheet.paste(image,(column*244,row*230))
            draw.text((2,row*230+201),label,font=font,fill='black')
        sheet.save(out/f'contact_sheet_{page+1:02d}.png')
    write_json(out/'selection_and_receipt.json',dict(status='assistant_review_pending',seed=20261026,source_video_modified=False,
        selection='One seeded available film per production institution, deduplicated; one random hardcut and one random default-gradual candidate per selected film.',
        limitation='Candidates only; no random no-candidate negative sample, no independently exhaustive annotations, cannot estimate fullcorpus precision/recall.',
        selected_films=len(selected),events=records,script_sha256=sha(__file__)))
    shutil.copy2(Path(__file__),out/'inspect_corpus_editing.py')
    print(json.dumps(dict(selected_films=len(selected),event_rows=len(records),contact_sheets=(len(tiles)+5)//6)))


if __name__=='__main__':main()
