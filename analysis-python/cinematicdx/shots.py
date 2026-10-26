"""Shot-boundary predictions tied to an ingested video's original presentation ticks.

PyAV supplies timestamps. PySceneDetect proposes cuts from every included decoded
frame; its required fps argument is an unused compatibility value, never a clock.
"""

import bisect
import csv
import hashlib
import io
import json
from fractions import Fraction
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from .ingest import (IngestError, hash_video, json_bytes, publish_bundle,
                     software_provenance, source_state, utc_now)


class ShotError(Exception):
    """Detection cannot safely publish a source-bound segmentation."""


def _rational(value):
    return "%s/%s" % (value.numerator, value.denominator)


def _number(value, name, *, minimum=None, positive=False):
    try:
        if isinstance(value, bool):
            raise ValueError()
        parsed = Fraction(str(value))
        if (minimum is not None and parsed < minimum) or (positive and parsed <= 0):
            raise ValueError()
        return parsed
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise ShotError("Invalid %s: %r" % (name, value)) from exc


def _load_dependencies():
    try:
        import av
        import cv2
        import numpy
        import scenedetect
        from scenedetect.common import FrameTimecode, Timecode
        from scenedetect.detectors import AdaptiveDetector, ContentDetector
    except (ImportError, OSError) as exc:
        raise ShotError("Shot detection needs the isolated M3 PyAV/PySceneDetect environment: %s" % exc) from exc
    return {"av": av, "cv2": cv2, "numpy": numpy, "scenedetect": scenedetect,
            "FrameTimecode": FrameTimecode, "Timecode": Timecode,
            "AdaptiveDetector": AdaptiveDetector, "ContentDetector": ContentDetector}


def _load_manifest(requested):
    path = requested.resolve(strict=True)
    before = source_state(path)
    raw = path.read_bytes()
    try:
        manifest = json.loads(raw)
        if manifest.get("artifact_kind") != "source_video_manifest":
            raise ValueError("not an M2 source manifest")
        reference = manifest["film_reference"]
        if not all(isinstance(reference.get(field), str) and reference[field].strip()
                   for field in ("namespace", "key")):
            raise ValueError("film_reference needs a namespace and key")
        checksum = manifest["source"]["sha256"]
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError("invalid source SHA-256")
        if manifest["video_version_id"] != "sha256:" + checksum:
            raise ValueError("video_version_id and source SHA-256 disagree")
        timeline = manifest["timeline"]
        time_base = _number(timeline["time_base"], "manifest time_base", positive=True)
        playback = timeline["playback_origin"]
        origin = _number(playback.get("source_seconds_rational", playback.get("source_seconds")),
                         "playback origin")
        index = manifest["selected_video_stream_index"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("invalid selected stream index")
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ShotError("Invalid M2 source manifest: %s" % exc) from exc
    if source_state(path) != before or requested.resolve(strict=True) != path:
        raise ShotError("Source manifest changed while it was being read")
    return path, before, raw, manifest, time_base, origin


def _source_ticks(value, frame_time_base, source_time_base, description):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ShotError("%s is missing a usable integer PTS/duration" % description)
    converted = Fraction(value) * Fraction(frame_time_base) / source_time_base
    if converted.denominator != 1:
        raise ShotError("%s cannot be represented exactly in the manifest time base" % description)
    return converted.numerator


def _decode(video, manifest, time_base, origin, start, end, algorithm, dependencies,
            analysis_width=320, progress_callback=None):
    av = dependencies["av"]
    beginning = origin + start
    ending = origin + end if end is not None else None
    frame_pts = []
    candidates = []
    first_excluded = None
    last_duration = None
    last_decoded = None
    adapter_origin = None
    decoded = 0
    preroll = 0
    scale = None
    flags = set()
    started = time.perf_counter()
    last_progress = started
    selected_index = manifest["selected_video_stream_index"]
    timeline = manifest["timeline"]
    try:
        with av.open(str(video), mode="r") as container:
            selected = [stream for stream in container.streams if stream.index == selected_index]
            if len(selected) != 1 or selected[0].type != "video":
                raise ShotError("Manifest-selected video stream is unavailable")
            stream = selected[0]
            if stream.time_base is None or Fraction(stream.time_base) != time_base:
                raise ShotError("Decoder stream time base differs from the source manifest")
            stream.codec_context.thread_count = 2
            stream.thread_type = "AUTO"
            stream_start = stream.start_time
            stream_duration = stream.duration
            if stream_start != timeline.get("source_start_pts"):
                flags.add("decoder_stream_start_differs_from_manifest")
            if start > 0:
                seek_ticks = beginning / time_base
                container.seek(seek_ticks.numerator // seek_ticks.denominator,
                               backward=True, any_frame=False, stream=stream)
            for frame in container.decode(stream):
                decoded += 1
                if frame.time_base is None:
                    raise ShotError("Decoded frame has no time base; timestamps will not be fabricated")
                pts = _source_ticks(frame.pts, frame.time_base, time_base, "Decoded frame")
                if last_decoded is not None and pts <= last_decoded:
                    raise ShotError("Decoded PTS must be strictly increasing; duplicate/discontinuous timing needs review")
                last_decoded = pts
                seconds = pts * time_base
                if seconds < beginning:
                    preroll += 1
                    continue
                if ending is not None and seconds >= ending:
                    first_excluded = pts
                    break
                if adapter_origin is None:
                    adapter_origin = pts
                if scale is None:
                    width, height = frame.width, frame.height
                    if width <= 0 or height <= 0:
                        raise ShotError("Decoded video dimensions are invalid")
                    target_width = min(analysis_width, width)
                    target_height = max(1, round(height * target_width / width))
                    scale = {"source_width": width, "source_height": height,
                             "analysis_width": target_width, "analysis_height": target_height,
                             "scale_x": _rational(Fraction(target_width, width)),
                             "scale_y": _rational(Fraction(target_height, height)),
                             "interpolation": "AREA", "analysis_pixel_format": "bgr24",
                             "source_pixel_format": frame.format.name,
                             "source_color_range": str(getattr(frame, "color_range", None)),
                             "crop": None, "rotation_applied": False}
                elif (frame.width, frame.height) != (scale["source_width"], scale["source_height"]):
                    raise ShotError("Video dimensions change mid-stream; one analysis geometry is required")
                frame_pts.append(pts)
                duration = getattr(frame, "duration", None)
                last_duration = (_source_ticks(duration, frame.time_base, time_base, "Decoded frame duration")
                                 if isinstance(duration, int) and not isinstance(duration, bool) and duration > 0 else None)
                image = frame.to_ndarray(format="bgr24", width=scale["analysis_width"],
                                         height=scale["analysis_height"], interpolation="AREA")
                timecode = dependencies["FrameTimecode"](
                    dependencies["Timecode"](pts - adapter_origin, time_base), fps=Fraction(1, 1))
                for candidate in algorithm.process_frame(timecode, image):
                    candidates.append(_source_ticks(candidate.pts, candidate.time_base, time_base,
                                                    "Detector candidate") + adapter_origin)
                now = time.perf_counter()
                if len(frame_pts) % 5000 == 0 or now - last_progress >= 60:
                    update = {"stage": "shot_detection", "processed_frames": len(frame_pts),
                              "playback_seconds": float(seconds - origin),
                              "elapsed_seconds": now - started}
                    if progress_callback is not None:
                        progress_callback(update)
                    else:
                        print(json.dumps(update), file=sys.stderr, flush=True)
                    last_progress = now
            if not frame_pts:
                raise ShotError("Requested interval contains no usable decoded video frames")
            final_timecode = dependencies["FrameTimecode"](
                dependencies["Timecode"](frame_pts[-1] - adapter_origin, time_base), fps=Fraction(1, 1))
            for candidate in algorithm.post_process(final_timecode):
                candidates.append(_source_ticks(candidate.pts, candidate.time_base, time_base,
                                                "Detector candidate") + adapter_origin)
            if first_excluded is not None:
                end_pts, end_basis = first_excluded, "first_excluded_decoded_frame_pts"
            elif last_duration is not None and last_duration > 0:
                end_pts, end_basis = frame_pts[-1] + last_duration, "last_decoded_frame_pts_plus_duration"
            elif (isinstance(stream_start, int) and isinstance(stream_duration, int) and stream_duration > 0
                  and stream_start == timeline.get("source_start_pts")
                  and stream_duration == timeline.get("duration_ts")
                  and stream_start + stream_duration > frame_pts[-1]):
                end_pts, end_basis = stream_start + stream_duration, "manifest_validated_stream_start_plus_duration"
                flags.add("eof_endpoint_from_stream_duration")
            else:
                raise ShotError("EOF has no positive frame duration or manifest-validated stream end; no FPS-derived end will be invented")
            if end_pts <= frame_pts[-1]:
                raise ShotError("Decoded coverage endpoint is not after the final frame PTS")
            if first_excluded is None and isinstance(stream_start, int) and isinstance(stream_duration, int):
                if end_pts != stream_start + stream_duration:
                    flags.add("decoded_frame_end_differs_from_declared_stream_end")
    except ShotError:
        raise
    except Exception as exc:
        raise ShotError("Video decoding or cut prediction failed: %s" % exc) from exc
    if frame_pts[0] * time_base != beginning:
        flags.add("requested_start_snapped_to_next_decoded_frame")
    if ending is not None and end_pts * time_base != ending:
        flags.add("requested_end_differs_from_actual_frame_endpoint")
    if ending is not None and first_excluded is None:
        flags.add("requested_end_reached_video_eof")
    return {"frame_pts": frame_pts, "end_pts": end_pts, "candidates": candidates,
            "end_basis": end_basis, "scale": scale, "flags": flags,
            "audit": {"decoded_frame_count": decoded, "processed_frame_count": len(frame_pts),
                      "preroll_frame_count": preroll, "first_excluded_frame_pts": first_excluded,
                      "last_included_frame_pts": frame_pts[-1], "last_frame_duration_ticks": last_duration,
                      "source_time_base": _rational(time_base), "frame_skipping": False,
                      "decoder_thread_count": 2, "decoder_thread_type": "AUTO",
                      "reached_eof": first_excluded is None, "end_basis": end_basis,
                      "decode_elapsed_seconds": time.perf_counter() - started,
                      "detector_adapter_origin_source_pts": adapter_origin,
                      "detector_adapter_fps_argument": "1/1",
                      "detector_adapter_fps_role": "required API compatibility only; never used to derive timestamps"}}


def _filter_candidates(candidates, frame_pts, end_pts, time_base, minimum):
    known = set(frame_pts)
    if any(candidate not in known for candidate in candidates):
        raise ShotError("Detector returned a boundary that is not an actually processed source frame")
    accepted = []
    suppressed = []
    beginning = frame_pts[0]
    for candidate in sorted(set(candidates)):
        previous = accepted[-1] if accepted else beginning
        if candidate <= beginning or candidate >= end_pts:
            suppressed.append({"pts": candidate, "reason": "at_or_outside_coverage_edge"})
        elif (candidate - previous) * time_base < minimum:
            suppressed.append({"pts": candidate, "reason": "shorter_than_minimum_since_previous_boundary"})
        else:
            accepted.append(candidate)
    while accepted and (end_pts - accepted[-1]) * time_base < minimum:
        suppressed.append({"pts": accepted.pop(), "reason": "terminal_interval_shorter_than_minimum"})
    return accepted, suppressed


def _position(pts, time_base, origin):
    seconds = pts * time_base
    return {"pts": pts, "time_base": _rational(time_base), "source_seconds": float(seconds),
            "source_seconds_rational": _rational(seconds),
            "playback_seconds": float(seconds - origin),
            "playback_seconds_rational": _rational(seconds - origin)}


def _quantile(ordered, probability):
    index = (len(ordered) - 1) * probability
    lower = index.numerator // index.denominator
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _summary(shots, boundaries, coverage, time_base):
    durations = sorted((shot["end_pts"] - shot["start_pts"]) * time_base for shot in shots)
    support = sum(durations, Fraction(0))
    values = [Fraction(boundary["playback_seconds_rational"]) for boundary in boundaries]
    start = Fraction(coverage["start_playback_seconds_rational"])
    end = Fraction(coverage["end_playback_seconds_rational"])
    windows = []
    window_start = start
    while window_start < end:
        window_end = min(window_start + 60, end)
        actual_support = window_end - window_start
        count = sum(window_start <= value < window_end for value in values)
        windows.append({"start_playback_seconds": float(window_start),
                        "end_playback_seconds": float(window_end),
                        "support_seconds": float(actual_support), "cut_count": count,
                        "cuts_per_minute": float(Fraction(count * 60) / actual_support),
                        "truncated_window": actual_support < 60})
        window_start += 30
    return {"schema_version": 1, "artifact_kind": "shot_measurement_summary",
            "validation_status": "derived_from_unreviewed_predictions",
            "shot_count": len(shots), "cut_count": len(boundaries), "support_seconds": float(support),
            "average_shot_length_seconds": float(support / len(durations)),
            "median_shot_length_seconds": float(_quantile(durations, Fraction(1, 2))),
            "quantiles_seconds": {str(float(p)): float(_quantile(durations, p)) for p in
                                  [Fraction(1, 10), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(9, 10), Fraction(19, 20)]},
            "quantile_method": "linear interpolation at (n-1)*p",
            "overall_cuts_per_minute": float(Fraction(len(boundaries) * 60) / support),
            "local_cut_rate_parameters": {"window_seconds": 60, "stride_seconds": 30,
                                          "anchor": "actual_coverage_start", "interval_convention": "[start,end)",
                                          "denominator": "actual observed temporal support"},
            "local_cut_rates": windows,
            "limitations": ["Shot intervals and rates depend on unreviewed boundary predictions.",
                            "Clipped edge intervals can be partial shots.",
                            "Cutting rate and average shot length do not identify metric montage."]}


def _csv_bytes(rows, fields, reference, video_version, segmentation):
    output = io.StringIO(newline="")
    prefix = ["film_namespace", "film_key", "video_version_id", "segmentation_id"]
    writer = csv.DictWriter(output, fieldnames=prefix + fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "film_namespace": reference["namespace"], "film_key": reference["key"],
                         "video_version_id": video_version, "segmentation_id": segmentation})
    return output.getvalue().encode("utf-8")


def detect_shots(manifest_path: Path, output_dir: Path, *, detector="adaptive", threshold=None,
                 min_shot_seconds=0.12, start_seconds=0.0, end_seconds=None,
                 analysis_width=320, luma_only=False, min_content_value=15.0,
                 progress_callback=None) -> dict:
    """Publish one segmentation; clip arguments are zero-based playback seconds.

    Actual coverage uses included decoded-frame PTS and the next excluded frame,
    or an explicit EOF duration. Existing output directories are never reused.
    """
    output = Path(output_dir).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ShotError("Output already exists; choose a new run directory: " + str(output))
    if detector not in {"adaptive", "content"}:
        raise ShotError("Detector must be adaptive or content")
    if (isinstance(analysis_width, bool) or not isinstance(analysis_width, int)
            or not 1 <= analysis_width <= 1920):
        raise ShotError("Analysis width must be an integer between 1 and 1920")
    if progress_callback is not None and not callable(progress_callback):
        raise ShotError("Progress callback must be callable")
    if not isinstance(luma_only, bool):
        raise ShotError("luma_only must be a boolean")
    if threshold is None:
        threshold = 3.0 if detector == "adaptive" else 27.0
    cutoff = _number(threshold, "threshold", positive=True)
    minimum_content = _number(min_content_value, "minimum content value", minimum=0)
    minimum = _number(min_shot_seconds, "minimum shot duration", minimum=0)
    start = _number(start_seconds, "clip start", minimum=0)
    end = _number(end_seconds, "clip end", positive=True) if end_seconds is not None else None
    if end is not None and end <= start:
        raise ShotError("Clip end must be later than clip start")
    started_at = utc_now()
    started_clock = time.perf_counter()
    requested_manifest = Path(manifest_path).expanduser().absolute()
    try:
        path, manifest_before, raw, manifest, time_base, origin = _load_manifest(requested_manifest)
        requested_video = Path(manifest["source"].get("requested_path") or manifest["source"]["resolved_path"])
        video = Path(manifest["source"]["resolved_path"]).resolve(strict=True)
        if requested_video.resolve(strict=True) != video:
            raise ShotError("Source video path no longer resolves to the ingested file")
        prior = source_state(video)
        if (prior[2], prior[3]) != (manifest["source"]["size_bytes"], manifest["source"]["mtime_ns"]):
            raise ShotError("Source size/mtime differs from M2; re-ingest before detecting shots")
        digest, size, before = hash_video(video)
        if digest != manifest["source"]["sha256"]:
            raise ShotError("Source checksum differs from the ingested video version")
        dependencies = _load_dependencies()
        algorithm = (dependencies["AdaptiveDetector"](
                        adaptive_threshold=float(cutoff), min_scene_len=0.0,
                        min_content_val=float(minimum_content), luma_only=luma_only)
                     if detector == "adaptive" else
                     dependencies["ContentDetector"](
                        threshold=float(cutoff), min_scene_len=0.0, luma_only=luma_only))
        software = software_provenance()
        decoded = _decode(video, manifest, time_base, origin, start, end, algorithm, dependencies,
                          analysis_width=analysis_width, progress_callback=progress_callback)
        if (source_state(video) != before or requested_video.resolve(strict=True) != video
                or source_state(path) != manifest_before or requested_manifest.resolve(strict=True) != path
                or path.read_bytes() != raw):
            raise ShotError("Source video or manifest changed during detection; no run was published")
    except ShotError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IngestError) as exc:
        raise ShotError("Cannot bind shot extraction to the ingested source: %s" % exc) from exc
    segmentation = str(uuid4())
    pts = decoded["frame_pts"]
    end_pts = decoded["end_pts"]
    cuts, suppressed = _filter_candidates(decoded["candidates"], pts, end_pts, time_base, minimum)
    flags = set(decoded["flags"]) | {"unreviewed_predictions", "gradual_transitions_not_classified"}
    if detector == "adaptive":
        flags.add("adaptive_edge_context_incomplete")
    if suppressed:
        flags.add("boundary_candidates_suppressed_by_minimum_duration_or_edges")
    if (end_pts - pts[0]) * time_base < minimum:
        flags.add("coverage_shorter_than_minimum_shot_duration")
    first_position = _position(pts[0], time_base, origin)
    end_position = _position(end_pts, time_base, origin)
    coverage = {"start_pts": pts[0], "end_pts": end_pts, "time_base": _rational(time_base),
                "start_source_seconds": first_position["source_seconds"],
                "end_source_seconds": end_position["source_seconds"],
                "start_source_seconds_rational": first_position["source_seconds_rational"],
                "end_source_seconds_rational": end_position["source_seconds_rational"],
                "start_playback_seconds": first_position["playback_seconds"],
                "end_playback_seconds": end_position["playback_seconds"],
                "start_playback_seconds_rational": first_position["playback_seconds_rational"],
                "end_playback_seconds_rational": end_position["playback_seconds_rational"],
                "requested_start_playback_seconds": float(start),
                "requested_end_playback_seconds": float(end) if end is not None else None,
                "interval_convention": "[start,end)", "end_basis": decoded["end_basis"],
                "reached_eof": decoded["audit"]["reached_eof"]}
    frame_edges = pts + [end_pts]
    boundaries = []
    for index, cut in enumerate(cuts, 1):
        location = bisect.bisect_left(frame_edges, cut)
        adjacent = [frame_edges[location] - frame_edges[location - 1],
                    frame_edges[location + 1] - frame_edges[location]]
        interval = max(adjacent) * time_base
        boundaries.append({"boundary_id": "%s:boundary:%06d" % (segmentation, index),
                           **_position(cut, time_base, origin),
                           "local_frame_interval_seconds": float(interval),
                           "local_frame_interval_rational": _rational(interval),
                           "local_frame_interval_basis": "maximum adjacent decoded source PTS gap",
                           "transition_type": "unclassified_cut_candidate",
                           "validation_status": "unreviewed_prediction", "confidence": None})
    shots = []
    edges = [pts[0], *cuts, end_pts]
    for index, (left, right) in enumerate(zip(edges, edges[1:]), 1):
        left_position, right_position = _position(left, time_base, origin), _position(right, time_base, origin)
        shots.append({"shot_id": "%s:shot:%06d" % (segmentation, index), "start_pts": left,
                      "end_pts": right, "time_base": _rational(time_base),
                      "start_source_seconds": left_position["source_seconds"],
                      "end_source_seconds": right_position["source_seconds"],
                      "start_source_seconds_rational": left_position["source_seconds_rational"],
                      "end_source_seconds_rational": right_position["source_seconds_rational"],
                      "start_playback_seconds": left_position["playback_seconds"],
                      "end_playback_seconds": right_position["playback_seconds"],
                      "start_playback_seconds_rational": left_position["playback_seconds_rational"],
                      "end_playback_seconds_rational": right_position["playback_seconds_rational"],
                      "duration_seconds": float((right - left) * time_base),
                      "duration_rational": _rational((right - left) * time_base),
                      "left_censored": index == 1 and (start > 0 or left * time_base > origin),
                      "right_censored": index == len(edges) - 1 and not coverage["reached_eof"],
                      "validation_status": "unreviewed_prediction"})
    document = {"schema_version": 1, "artifact_kind": "shot_segmentation",
                "film_reference": manifest["film_reference"], "video_version_id": manifest["video_version_id"],
                "segmentation_id": segmentation, "coverage": coverage, "shots": shots, "boundaries": boundaries,
                "suppressed_candidates": [{**_position(row["pts"], time_base, origin), "reason": row["reason"]}
                                          for row in suppressed],
                "quality_flags": sorted(flags), "decode_audit": decoded["audit"],
                "limitations": ["Cuts are unreviewed algorithmic predictions, not narrative scenes or events.",
                                "Gradual transitions and historical montage principles are not classified.",
                                "Adaptive detection lacks full neighboring context at interval edges.",
                                "Minimum duration suppression can hide genuine very short shots."]}
    summary = {**_summary(shots, boundaries, coverage, time_base),
               "film_reference": manifest["film_reference"], "video_version_id": manifest["video_version_id"],
               "segmentation_id": segmentation, "coverage": coverage}
    reference, version = manifest["film_reference"], manifest["video_version_id"]
    artifacts = {"shots.json": json_bytes(document), "summary.json": json_bytes(summary),
                 "shots.csv": _csv_bytes(shots, list(shots[0]), reference, version, segmentation),
                 "boundaries.csv": _csv_bytes(boundaries,
                     ["boundary_id", "pts", "time_base", "source_seconds", "source_seconds_rational",
                      "playback_seconds", "playback_seconds_rational", "local_frame_interval_seconds",
                      "local_frame_interval_rational", "local_frame_interval_basis", "transition_type",
                      "validation_status", "confidence"], reference, version, segmentation)}
    run = {"schema_version": 1, "artifact_kind": "shot_detection_run", "run_id": segmentation,
           "segmentation_id": segmentation, "status": "complete", "started_at_utc": started_at,
           "completed_at_utc": utc_now(), "elapsed_seconds": time.perf_counter() - started_clock,
           "film_reference": reference, "video_version_id": version,
           "inputs": {"source_manifest": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
                      "source_video": {"path": str(video), "sha256": digest, "size_bytes": size,
                                       "hash_scope": "entire_file_bytes_reverified_before_decode"}},
           "software": {**software, "pyscenedetect_version": dependencies["scenedetect"].__version__,
                        "pyav_version": dependencies["av"].__version__,
                        "opencv_version": dependencies["cv2"].__version__,
                        "numpy_version": dependencies["numpy"].__version__,
                        "pyav_ffmpeg_libraries": {key: list(value) for key, value in dependencies["av"].library_versions.items()}},
           "parameters": {"detector": detector, "threshold": float(cutoff),
                          "threshold_units": "adaptive_ratio" if detector == "adaptive" else "mean_HSV_pixel_difference",
                          "min_shot_seconds": float(minimum), "library_min_scene_len": 0.0,
                          "minimum_duration_filter_policy": "chronological greedy suppression, then merge a short terminal interval",
                          "adaptive_window_width_frames": 2 if detector == "adaptive" else None,
                          "adaptive_min_content_val": float(minimum_content) if detector == "adaptive" else None,
                          "luma_only": luma_only,
                          "luma_only_signal": "PySceneDetect HSV V intensity channel" if luma_only else None,
                          "component_weights": {"delta_hue": 0.0 if luma_only else 1.0,
                                                "delta_sat": 0.0 if luma_only else 1.0,
                                                "delta_lum": 1.0, "delta_edges": 0.0},
                          "start_playback_seconds": float(start), "end_playback_seconds": float(end) if end is not None else None,
                          "analysis_width_limit": analysis_width,
                          "scaling": decoded["scale"], "frame_skipping": False},
           "decode": decoded["audit"], "coverage": coverage,
           "detector_candidate_count": len(decoded["candidates"]), "suppressed_candidate_count": len(suppressed),
           "quality_flags": sorted(flags),
           "outputs": {name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
                       for name, data in artifacts.items()}}
    artifacts["run.json"] = json_bytes(run)
    try:
        publish_bundle(output, artifacts)
    except (IngestError, OSError) as exc:
        raise ShotError("Could not publish shot extraction: %s" % exc) from exc
    return {"segmentation_id": segmentation, "film_reference": reference, "video_version_id": version,
            "output_directory": str(output), "shot_count": len(shots), "boundary_count": len(boundaries),
            "quality_flags": sorted(flags)}
