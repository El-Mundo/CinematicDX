"""Small, source-bound visual QA sample; no automatic historical interpretation."""
import argparse
import csv
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis-python'))
import av
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from cinematicdx.ingest import source_state

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--analysis-directory',type=Path);p.add_argument('--output-directory',type=Path);args=p.parse_args();run=args.run
    analysis=args.analysis_directory or run/'analysis'
    with (analysis/'film_measurements_and_coverage.csv').open(encoding='utf-8-sig') as f:films=[r for r in csv.DictReader(f) if r['eligible']=='True']
    rng=np.random.default_rng(20261026);selected={};reasons={}
    for i in rng.choice(len(films),min(8,len(films)),replace=False):
        row=films[i];selected[row['film_key']]=row;reasons.setdefault(row['film_key'],[]).append('seeded_random')
    for row in sorted(films,key=lambda r:float(r['full_vs_roi_profile_correlation']) if r['full_vs_roi_profile_correlation'] else 1)[:4]:
        selected[row['film_key']]=row;reasons.setdefault(row['film_key'],[]).append('crop_sensitive_profile')
    for row in sorted(films,key=lambda r:float(r['mean_abs_change_30s_z']) if r['mean_abs_change_30s_z'] else -1,reverse=True)[:2]:
        selected[row['film_key']]=row;reasons.setdefault(row['film_key'],[]).append('high_relative_change')
    out=args.output_directory or run/'source_qa';out.mkdir(exist_ok=False);records=[];pictures=[];font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',13)
    for index,row in enumerate(selected.values(),1):
        directory=run/'films'/row['selected_job_id'];doc=read(directory/'summary.json');receipt=read(directory/'run.json');source=Path(doc['job']['source_path'])
        if tuple(receipt['source_state'])!=source_state(source):raise ValueError('Source changed since this film was measured.')
        with av.open(str(source)) as container:
            stream=next(s for s in container.streams.video if s.index==doc['technical']['stream_index']);stream.codec_context.thread_count=1
            origin=Fraction(doc['technical']['playback_origin_rational']);target=Fraction(str(float(row['duration_seconds'])/2))
            container.seek(int((origin+target)/stream.time_base),stream=stream,backward=True,any_frame=False)
            for frame in container.decode(stream):
                if frame.pts is None:continue
                playback=Fraction(frame.pts)*frame.time_base-origin
                if playback<target:continue
                w=480;h=round(frame.height*w/frame.width);rgb=frame.reformat(width=w,height=h,format='rgb24',interpolation='AREA').to_ndarray()
                image=Image.fromarray(rgb);filename=f'{index:02d}-{row["selected_job_id"]}.jpg';image.save(out/filename,quality=90)
                overlay=image.copy();draw=ImageDraw.Draw(overlay)
                analysis_width=min(160,frame.width);analysis_height=max(16,round(frame.height*analysis_width/frame.width))
                box=((analysis_width+19)//20/analysis_width*w,(analysis_height+9)//10/analysis_height*h,
                     (analysis_width*19//20)/analysis_width*w,(analysis_height*9//10)/analysis_height*h)
                draw.rectangle(box,outline='#20d68a',width=3)
                pictures.append((overlay,row))
                records.append(dict(film_key=row['film_key'],title=row['title'],year=row['year'],reasons=reasons[row['film_key']],
                    video_version_id=row['video_version_id'],source_pts=int(frame.pts),time_base=str(frame.time_base),
                    playback_seconds=float(playback),image_filename=filename,image_sha256=sha(out/filename),
                    selection_fraction=.5,has_independent_human_annotation=False))
                break
        if tuple(receipt['source_state'])!=source_state(source):raise ValueError('Source changed during QA.')
    tilew=320;tileh=300;sheet=Image.new('RGB',(tilew*4,tileh*math.ceil(len(pictures)/4)),'white');draw=ImageDraw.Draw(sheet)
    for i,(image,row) in enumerate(pictures):
        image.thumbnail((312,248));x=(i%4)*tilew;y=(i//4)*tileh;sheet.paste(image,(x+(tilew-image.width)//2,y))
        draw.text((x+4,y+250),row['title']+' '+row['year']+' '+row['colour'],font=font,fill='black')
        reason='/'.join(reasons[row['film_key']]);draw.text((x+4,y+271),reason,font=font,fill='black')
    sheet.save(out/'source_qa_contact_sheet.png')
    (out/'selection_and_receipt.json').write_text(json.dumps(dict(status='assistant_review_pending',diagnostic_sample_not_unbiased_validation=True,
        seed=20261026,raw_video_modified=False,images=records,contact_sheet_sha256=sha(out/'source_qa_contact_sheet.png')),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(source_qa_images=len(records),output=str(out)),ensure_ascii=False))

if __name__=='__main__':main()
