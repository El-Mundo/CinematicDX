"""Post-result source QA: sparse chroma diagnostics, never historical relabelling."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'analysis-python'))
import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from cinematicdx.ingest import source_state
from cinematicdx.corpus_studio_analysis import weighted_mean

PROCEDURE = 'Three fixed source frames at20/50/80%; centralROI; at least10% pixels with RGB spread>20 and channel-centered spread>20 in at least2frames.'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cached_results(directory):
    """Load only intact results produced with the same diagnostic procedure."""
    directory = directory.resolve()
    receipt = read(directory / 'run.json')
    for relative, expected in receipt['outputs'].items():
        path = directory / relative
        if not path.resolve().is_relative_to(directory) or sha(path) != expected:
            raise ValueError('Changed or invalid cached chroma-QA output: ' + relative)
    result = read(directory / 'results.json')
    if result['procedure'] != PROCEDURE:
        raise ValueError('Cached chroma-QA procedure differs from the current procedure.')
    lookup = {}
    for row in result['results']:
        key = (row['video_version_id'], row['selected_job_id'], row['film_key'], row['metadata_colour'])
        if key in lookup:
            raise ValueError('Duplicate cached chroma-QA identity.')
        if row['usable_sample_count'] == 3 and [f['fraction'] for f in row['frames']] == [.2, .5, .8]:
            filenames = [row['selected_job_id'] + '-' + str(fraction) + '.png' for fraction in (.2, .5, .8)]
            hashes = {name: receipt['outputs']['frames/' + name] for name in filenames}
            lookup[key] = (row, hashes)
    return lookup, sha(directory / 'run.json')


def reuse_result(row, cached, run, previous, out):
    result, frame_hashes = cached
    directory = run / 'films' / row['selected_job_id']
    document = read(directory / 'summary.json')
    receipt = read(directory / 'run.json')
    source = Path(document['job']['source_path'])
    if document['video_version_id'] != row['video_version_id'] or receipt['video_version_id'] != row['video_version_id']:
        raise ValueError('Current source version differs from chroma-QA input row.')
    expected = tuple(receipt['source_state'])
    if source_state(source) != expected:
        raise ValueError('Source changed before cached chroma QA was reused.')
    for filename, expected_hash in frame_hashes.items():
        shutil.copy2(previous / 'frames' / filename, out / 'frames' / filename)
        if sha(out / 'frames' / filename) != expected_hash:
            raise ValueError('Cached chroma-QA frame changed during reuse.')
    if source_state(source) != expected:
        raise ValueError('Source changed while cached chroma QA was reused.')
    return dict(result, title=row['title'])


def inspect(row, run, out):
    directory = run / 'films' / row['selected_job_id']
    doc, receipt = read(directory / 'summary.json'), read(directory / 'run.json')
    source = Path(doc['job']['source_path'])
    expected = tuple(receipt['source_state'])
    if source_state(source) != expected:
        raise ValueError('Source changed before chroma QA.')
    frames = []
    with av.open(str(source)) as container:
        stream = next(s for s in container.streams.video if s.index == doc['technical']['stream_index'])
        stream.codec_context.thread_count = 1
        origin = Fraction(doc['technical']['playback_origin_rational'])
        for fraction in (.2, .5, .8):
            target = Fraction(str(float(row['duration_seconds']) * fraction))
            container.seek(int((origin + target) / stream.time_base), stream=stream, backward=True, any_frame=False)
            for frame in container.decode(stream):
                if frame.pts is None:
                    continue
                playback = Fraction(frame.pts) * frame.time_base - origin
                if playback < target:
                    continue
                w = min(160, frame.width)
                h = max(16, round(frame.height * w / frame.width))
                rgb = frame.reformat(width=w, height=h, format='rgb24', interpolation='AREA').to_ndarray()
                roi = rgb[(h + 9) // 10:h * 9 // 10, (w + 19) // 20:w * 19 // 20].astype(float)
                spread = np.max(roi, axis=2) - np.min(roi, axis=2)
                # Remove one constant channel offset: simple uniform tint is less likely to trigger.
                centered = roi - np.median(roi.reshape(-1, 3), axis=0)
                residual = np.max(centered, axis=2) - np.min(centered, axis=2)
                frames.append(dict(fraction=fraction, source_pts=int(frame.pts), time_base=str(frame.time_base),
                    playback_seconds=float(playback), rgb_spread_over20_fraction=float(np.mean(spread > 20)),
                    channel_centered_spread_over20_fraction=float(np.mean(residual > 20))))
                Image.fromarray(rgb).save(out / 'frames' / (row['selected_job_id'] + '-' + str(fraction) + '.png'))
                break
    if source_state(source) != expected:
        raise ValueError('Source changed during chroma QA.')
    positive = sum(f['rgb_spread_over20_fraction'] >= .10 and
                   f['channel_centered_spread_over20_fraction'] >= .10 for f in frames)
    return dict(film_key=row['film_key'], title=row['title'], metadata_colour=row['colour'],
        video_version_id=row['video_version_id'], selected_job_id=row['selected_job_id'], frames=frames,
        chromatic_content_in_at_least_two_samples=positive >= 2,
        metadata_bw_chroma_review_flag=row['colour'] == 'B&W' and positive >= 2,
        independent_human_validation=False, usable_sample_count=len(frames))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--analysis-directory', type=Path, required=True)
    p.add_argument('--output-directory', type=Path, required=True)
    p.add_argument('--reuse-directory', type=Path, help='Reuse intact diagnostics for unchanged source identities')
    args = p.parse_args()
    out = args.output_directory
    out.mkdir(exist_ok=False)
    (out / 'frames').mkdir()
    with (args.analysis_directory / 'film_measurements_and_coverage.csv').open(encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['eligible'] == 'True']
    results, failures, reused, newly_inspected = [], [], [], []
    cache, previous_receipt_sha = cached_results(args.reuse_directory) if args.reuse_directory else ({}, None)
    pending = []
    for row in rows:
        key = (row['video_version_id'], row['selected_job_id'], row['film_key'], row['colour'])
        if key in cache:
            results.append(reuse_result(row, cache[key], args.run, args.reuse_directory, out))
            reused.append(row['selected_job_id'])
        else:
            pending.append(row)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(inspect, row, args.run, out): row for row in pending}
        for future in as_completed(futures):
            try:
                results.append(future.result())
                newly_inspected.append(futures[future]['selected_job_id'])
            except Exception as exc:
                failures.append(dict(film_key=futures[future]['film_key'], error=str(exc)))
            if (len(results) + len(failures)) % 50 == 0:
                print(json.dumps(dict(completed=len(results), failed=len(failures))), flush=True)
    results.sort(key=lambda r:r['film_key'])
    flagged = {r['film_key'] for r in results if r['metadata_bw_chroma_review_flag']}
    with (args.analysis_directory / 'studio_summary_all.csv').open(encoding='utf-8-sig') as f:
        studios = list(csv.DictReader(f))
    sensitivity = []
    for studio in studios:
        members = [(r, s['fractional_weight']) for r in rows for s in json.loads(r['studios'])
                   if s['studio_id'] == studio['studio_id']]
        for scope in ('all', 'metadata_bw', 'feature_metadata_bw'):
            subset = [(r,w) for r,w in members if scope == 'all' or
                      r['colour'] == 'B&W' and (scope != 'feature_metadata_bw' or r['film_type'] == 'Feature')]
            kept = [(r,w) for r,w in subset if r['film_key'] not in flagged]
            raw = weighted_mean([float(r['mean_abs_change_30s_z']) for r,w in subset], [w for r,w in subset])
            checked = weighted_mean([float(r['mean_abs_change_30s_z']) for r,w in kept], [w for r,w in kept])
            sensitivity.append(dict(studio=studio['studio'], studio_id=studio['studio_id'], scope=scope,
                original_member_n=len(subset), flagged_member_n=len(subset)-len(kept), unflagged_member_n=len(kept),
                original_mean=raw, unflagged_mean=checked,
                mean_change_after_exclusion=None if raw is None or checked is None else checked-raw))
    with (out / 'studio_chroma_flag_sensitivity.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(sensitivity[0]));writer.writeheader();writer.writerows(sensitivity)
    chosen = [r for r in results if r['metadata_bw_chroma_review_flag']]
    font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 13)
    sheet = Image.new('RGB', (640, max(1, (len(chosen)+2)//3)*185), 'white')
    draw = ImageDraw.Draw(sheet)
    for i,row in enumerate(chosen):
        im = Image.open(out/'frames'/(row['selected_job_id']+'-0.5.png'));im.thumbnail((205,145))
        x,y=(i%3)*213,(i//3)*185;sheet.paste(im,(x,y))
        draw.text((x,y+147), row['title'], font=font, fill='black')
        draw.text((x,y+164), 'metadata B&W / review flag', font=font, fill='black')
    sheet.save(out/'flagged_contact_sheet.png')
    result = dict(status='PROVISIONAL', completed_at_utc=datetime.now(timezone.utc).isoformat(),
        triggered_by='Assistant QA found clearly chromatic content in metadata-B&W Liu San Jie; post-result diagnostic.',
        procedure=PROCEDURE,
        parameter_tuning='Thresholds specified before whole-corpus diagnostic; heuristic flags, not validated colour classification.',
        interpretation='Neither no-flag nor a flag proves original colour process, complete identity, colourisation or historical appearance. Do not relabel metadata.',
        film_count=len(rows), successful=len(results), failures=failures, sampled_frame_count=sum(len(r['frames']) for r in results),
        flagged_bw_count=len(flagged), flagged_titles=[r['title'] for r in chosen], results=results,
        input_analysis_sha256=sha(args.analysis_directory/'run.json'), script_sha256=sha(__file__),
        source_videos_and_original_metadata_modified=False)
    if args.reuse_directory:
        result['reuse_provenance'] = dict(previous_directory=str(args.reuse_directory.resolve()),
            previous_run_sha256=previous_receipt_sha, reused_job_ids=sorted(reused),
            newly_inspected_job_ids=sorted(newly_inspected), visual_review_status='pending_for_current_run')
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    artifacts=[p for p in out.rglob('*') if p.is_file()]
    receipt = dict(script_sha256=sha(__file__),outputs={str(p.relative_to(out)):sha(p) for p in artifacts})
    if args.reuse_directory:
        receipt['reuse_provenance'] = result['reuse_provenance']
    (out/'run.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','film_count','successful','failures','sampled_frame_count','flagged_bw_count','flagged_titles')},ensure_ascii=False))


if __name__ == '__main__':
    main()
