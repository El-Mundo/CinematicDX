"""File-based research commands; optional analysis dependencies are loaded on demand."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

from .ingest import (IngestError, ingest_video, json_bytes, publish_bundle,
                     software_provenance, source_state, utc_now)
from .inventory import inventory_directory
from .probe import ProbeError, probe_video


def inventory_command(args):
    output = Path(args.output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise IngestError("Output already exists; choose a new audit directory: " + str(output))
    started = utc_now()
    metadata_file = Path(args.metadata).expanduser().resolve(strict=True) if args.metadata else None
    metadata_state = source_state(metadata_file) if metadata_file else None
    metadata_hash = hashlib.sha256(metadata_file.read_bytes()).hexdigest() if metadata_file else None
    data = inventory_directory(Path(args.root), metadata_file)
    videos = data["videos"]
    if args.probe_headers:
        for index, video in enumerate(videos):
            path = Path(data["root"]) / video["relative_path"]
            try:
                before = source_state(path)
                if (before[2], before[3]) != (video["size_bytes"], video["mtime_ns"]):
                    raise IngestError("The file changed after directory listing.")
                video["header_probe"] = probe_video(path, ffprobe=args.ffprobe, timestamp_sample_frames=0)
                if before != source_state(path):
                    raise IngestError("The file changed during header probing.")
                video["header_probe_status"] = "passed"
            except (OSError, ValueError, ProbeError, IngestError) as error:
                video["header_probe_status"] = "failed"
                video["header_probe_error"] = str(error)
            if (index + 1) % 25 == 0:
                print("Header probes: " + str(index + 1) + "/" + str(len(videos)), file=sys.stderr)
    if metadata_file and metadata_state != source_state(metadata_file):
        raise IngestError("Metadata changed during inventory; no audit was published.")
    summary = data.setdefault("summary", {})
    summary.update(expected_video_count=args.expected_count,
                   expected_count_matches=(len(videos) == args.expected_count)
                   if args.expected_count is not None else None,
                   header_probes_passed=sum(v.get("header_probe_status") == "passed" for v in videos),
                   header_probes_failed=sum(v.get("header_probe_status") == "failed" for v in videos),
                   full_content_duplicate_check="not_performed", full_decode_validation="not_performed")
    fields = ["relative_path", "size_bytes", "mtime_ns", "readable", "flags", "metadata_candidates",
              "header_probe_status"]
    table = io.StringIO(newline="")
    writer = csv.DictWriter(table, fieldnames=fields)
    writer.writeheader()
    for video in videos:
        row = {field: video.get(field) for field in fields}
        for field in ["flags", "metadata_candidates"]:
            row[field] = json.dumps(row[field], ensure_ascii=False)
        writer.writerow(row)
    payloads = {"inventory.json": json_bytes(data), "inventory.csv": table.getvalue().encode("utf-8")}
    receipt = {"schema_version": 1, "artifact_kind": "directory_audit_run", "status": "complete",
               "started_at_utc": started, "completed_at_utc": utc_now(), "software": software_provenance(),
               "root": data["root"], "metadata": {"path": str(metadata_file) if metadata_file else None,
               "sha256": metadata_hash}, "parameters": {"probe_headers": args.probe_headers,
               "expected_count": args.expected_count, "ffprobe": args.ffprobe},
               "outputs": {name: {"sha256": hashlib.sha256(value).hexdigest()}
                           for name, value in payloads.items()},
               "limitations": ["Filename matches are candidates, not confirmed film identities.",
                               "No complete-file checksums, full decoding or shot analysis were performed."]}
    payloads["run.json"] = json_bytes(receipt)
    publish_bundle(output, payloads)
    return {"output_directory": str(output), "summary": summary}


def main(argv=None):
    parser = argparse.ArgumentParser(description="CinematicDX: ingestion, shot timelines and independent narrative alignment")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory", help="Read-only directory audit; no full-video hashing")
    inventory.add_argument("--root", required=True)
    inventory.add_argument("--metadata")
    inventory.add_argument("--output", required=True, help="New output directory, outside raw source storage")
    inventory.add_argument("--expected-count", type=int)
    inventory.add_argument("--probe-headers", action="store_true", help="Probe headers only, without timestamp samples")
    inventory.add_argument("--ffprobe", default="ffprobe")
    ingestion = commands.add_parser("ingest", help="Hash and probe one explicitly identified video")
    ingestion.add_argument("--video", required=True)
    ingestion.add_argument("--metadata", required=True)
    ingestion.add_argument("--film-id", required=True, help="Explicit inventory key or local catalog film_key")
    ingestion.add_argument("--metadata-namespace")
    ingestion.add_argument("--output", required=True, help="New run directory")
    ingestion.add_argument("--source-description")
    ingestion.add_argument("--source-uri")
    ingestion.add_argument("--ffprobe", default="ffprobe")
    ingestion.add_argument("--stream-index", type=int)
    ingestion.add_argument("--timestamp-sample-frames", type=int, default=12)
    shots = commands.add_parser("shots", help="M3: detect shot candidates using original PyAV timestamps")
    shots.add_argument("--manifest", required=True)
    shots.add_argument("--output", required=True)
    shots.add_argument("--detector", choices=["adaptive", "content"], default="adaptive")
    shots.add_argument("--threshold", type=float)
    shots.add_argument("--min-shot-seconds", type=float, default=.12)
    shots.add_argument("--start-seconds", type=float, default=0.0, help="Playback offset; source PTS are retained")
    shots.add_argument("--end-seconds", type=float)
    shots.add_argument("--analysis-width", type=int, default=320)
    shots.add_argument("--luma-only", action="store_true", help="Use HSV V intensity differences; useful to calibrate monochrome copies")
    shots.add_argument("--min-content-value", type=float, default=15.0, help="Minimum absolute content score for Adaptive detector")
    report = commands.add_parser("shot-report", help="Descriptive timeline, duration statistics and windowed cutting rates")
    report.add_argument("--shots", required=True)
    report.add_argument("--output", required=True)
    report.add_argument("--window-seconds", type=float, default=60.0)
    report.add_argument("--step-seconds", type=float, default=15.0)
    report.add_argument("--no-plot", action="store_true")
    for command, description in [("annotation-template", "M4: empty independent narrative annotation template"),
                                 ("boundary-reference-template", "M3: empty independent boundary validation template")]:
        template = commands.add_parser(command, help=description)
        template.add_argument("--shots", required=True)
        template.add_argument("--output", required=True)
    narrative = commands.add_parser("align-narrative", help="Align separately supplied narrative events and compare matched intervals")
    narrative.add_argument("--shots", required=True)
    narrative.add_argument("--annotations", required=True)
    narrative.add_argument("--output", required=True)
    narrative.add_argument("--window-seconds", type=float, default=30.0)
    narrative.add_argument("--control-count", type=int, default=3)
    narrative.add_argument("--seed", type=int, default=0)
    validation = commands.add_parser("validate-shots", help="Evaluate cut candidates against an independent exhaustive reference interval")
    validation.add_argument("--shots", required=True)
    validation.add_argument("--reference", required=True)
    validation.add_argument("--output", required=True)
    validation.add_argument("--tolerance-seconds", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory_command(args)
        elif args.command == "ingest":
            result = ingest_video(args.video, args.metadata, args.film_id, args.output,
                                  source_description=args.source_description, source_uri=args.source_uri,
                                  metadata_namespace=args.metadata_namespace, ffprobe=args.ffprobe,
                                  stream_index=args.stream_index,
                                  timestamp_sample_frames=args.timestamp_sample_frames)
        elif args.command == "shots":
            from .shots import ShotError, detect_shots
            try:
                result = detect_shots(args.manifest, args.output, detector=args.detector,
                                      threshold=args.threshold, min_shot_seconds=args.min_shot_seconds,
                                      start_seconds=args.start_seconds, end_seconds=args.end_seconds,
                                      analysis_width=args.analysis_width, luma_only=args.luma_only,
                                      min_content_value=args.min_content_value)
            except ShotError as error:
                raise IngestError(str(error)) from error
        elif args.command == "shot-report":
            from .reports import summarize_shots
            result = summarize_shots(args.shots, args.output, window_seconds=args.window_seconds,
                                     step_seconds=args.step_seconds, render=not args.no_plot)
        elif args.command in {"annotation-template", "align-narrative"}:
            from .narrative import NarrativeError, prepare_annotation_template, align_narrative
            try:
                if args.command == "annotation-template":
                    result = prepare_annotation_template(args.shots, args.output)
                else:
                    result = align_narrative(args.shots, args.annotations, args.output,
                                             window_seconds=args.window_seconds,
                                             control_count=args.control_count, seed=args.seed)
            except NarrativeError as error:
                raise IngestError(str(error)) from error
        else:
            from .validation import ValidationError, prepare_boundary_reference_template, validate_shots
            try:
                if args.command == "boundary-reference-template":
                    result = prepare_boundary_reference_template(args.shots, args.output)
                else:
                    result = validate_shots(args.shots, args.reference, args.output,
                                            tolerance_seconds=args.tolerance_seconds)
            except ValidationError as error:
                raise IngestError(str(error)) from error
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, IngestError, ProbeError) as error:
        print("CinematicDX: " + str(error), file=sys.stderr)
        return 2
    except ImportError as error:
        print("CinematicDX: optional analysis runtime unavailable. Use the isolated M3 environment "
              "with requirements-m3.txt. " + str(error), file=sys.stderr)
        return 2
