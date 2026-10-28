"""Annotation-blind grayscale measurements over a complete requested time interval.

A fixed central ROI is applied identically to every decoded frame. The cache is
an inspectable measurement layer, not a transition or narrative classifier.
"""

from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

from .ingest import (IngestError, hash_video, json_bytes, publish_bundle,
                     software_provenance, source_state, utc_now)
from .shots import ShotError, _load_manifest, _number, _rational, _source_ticks


class TransitionFeatureError(Exception):
    """A complete, source-bound transition-feature cache cannot be published."""


def _load_dependencies():
    try:
        import av
        import cv2
        import numpy
    except (ImportError, OSError) as exc:
        raise TransitionFeatureError("Feature extraction needs the isolated PyAV/OpenCV/NumPy environment: %s" % exc) from exc
    return {"av": av, "cv2": cv2, "numpy": numpy}


def _roi_geometry(width, height):
    # Exact ceil/floor rules; right/bottom are excluded. No label-dependent crop.
    left, right = (width + 19) // 20, width * 19 // 20
    top, bottom = (height + 9) // 10, height * 9 // 10
    if right - left < 2 or bottom - top < 2:
        raise TransitionFeatureError("Fixed ROI is too small for spatial differences")
    return {"left": left, "right": right, "top": top, "bottom": bottom,
            "width": right - left, "height": bottom - top,
            "interval_convention": "[left,right) x [top,bottom)"}


def _signals(gray, geometry, np):
    roi = gray[geometry["top"]:geometry["bottom"], geometry["left"]:geometry["right"]]
    normalized = roi.astype(np.float32) / 255.0
    histogram = np.bincount((roi.reshape(-1) // 8), minlength=32).astype(np.float32)
    histogram /= roi.size
    energy = 0.5 * (np.abs(np.diff(normalized, axis=1)).mean()
                    + np.abs(np.diff(normalized, axis=0)).mean())
    return {"roi": roi, "normalized_roi": normalized,
            "full_mean": float(gray.mean(dtype=np.float64) / 255.0),
            "roi_mean": float(normalized.mean(dtype=np.float64)),
            "roi_std": float(normalized.std(dtype=np.float64, ddof=0)),
            "gray_hist": histogram, "edge_energy": float(energy)}


def extract_transition_features(manifest_path: Path, output_dir: Path, *,
                                start_seconds=150.0, end_seconds=750.0,
                                pad_seconds=5.0, analysis_width=160,
                                cache_width=64, cache_height=48) -> dict:
    """Cache every frame over the whole interval plus fixed optional context.

    Arguments are zero-based playback seconds. The evaluation interval is exactly
    [start_seconds,end_seconds); padding never enters its declared denominator.
    No annotations or candidate intervals are accepted or read by this API.
    """
    output = Path(output_dir).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise TransitionFeatureError("Output already exists; choose a new feature directory: " + str(output))
    try:
        start = _number(start_seconds, "evaluation start", minimum=0)
        end = _number(end_seconds, "evaluation end", positive=True)
        padding = _number(pad_seconds, "context padding", minimum=0)
    except ShotError as exc:
        raise TransitionFeatureError(str(exc)) from exc
    if end <= start:
        raise TransitionFeatureError("Evaluation end must be later than start")
    for value, name, lower, upper in ((analysis_width, "analysis_width", 16, 640),
                                      (cache_width, "cache_width", 2, 256),
                                      (cache_height, "cache_height", 2, 256)):
        if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
            raise TransitionFeatureError("%s must be an integer from %s to %s" % (name, lower, upper))
    started_at, started = utc_now(), time.perf_counter()
    requested_manifest = Path(manifest_path).expanduser().absolute()
    cache_start, cache_end = max(Fraction(0), start - padding), end + padding
    try:
        manifest_file, manifest_before, raw, manifest, time_base, origin = _load_manifest(requested_manifest)
        source = manifest["source"]
        video = Path(source["resolved_path"]).resolve(strict=True)
        video_request = Path(source.get("requested_path") or source["resolved_path"])
        if video_request.resolve(strict=True) != video:
            raise TransitionFeatureError("Source path no longer resolves to the ingested file")
        state = source_state(video)
        if (state[2], state[3]) != (source["size_bytes"], source["mtime_ns"]):
            raise TransitionFeatureError("Source size/mtime differs from M2; re-ingest first")
        checksum, size, video_before = hash_video(video)
        if checksum != source["sha256"]:
            raise TransitionFeatureError("Source checksum differs from the ingested video version")
        dependencies = _load_dependencies()
        av, cv2, np = (dependencies[name] for name in ("av", "cv2", "numpy"))
        software = software_provenance()
        pts_values, caches, means, roi_means, deviations, mads, histograms, histogram_changes, energies = ([] for _ in range(9))
        previous_roi, previous_histogram, previous_pts = None, None, None
        geometry, first_excluded, last_duration = None, None, None
        decoded, preroll = 0, 0
        decode_started, last_progress = time.perf_counter(), time.perf_counter()
        with av.open(str(video), mode="r") as container:
            matches = [stream for stream in container.streams
                       if stream.index == manifest["selected_video_stream_index"]]
            if len(matches) != 1 or matches[0].type != "video":
                raise TransitionFeatureError("Manifest-selected video stream is unavailable")
            stream = matches[0]
            if stream.time_base is None or Fraction(stream.time_base) != time_base:
                raise TransitionFeatureError("Decoder time base differs from the M2 manifest")
            stream.codec_context.thread_count, stream.thread_type = 2, "AUTO"
            if cache_start > 0:
                seek_ticks = (origin + cache_start) / time_base
                container.seek(seek_ticks.numerator // seek_ticks.denominator,
                               backward=True, any_frame=False, stream=stream)
            for frame in container.decode(stream):
                decoded += 1
                if frame.time_base is None:
                    raise TransitionFeatureError("Decoded frame has no time base")
                pts = _source_ticks(frame.pts, frame.time_base, time_base, "Decoded frame")
                if previous_pts is not None and pts <= previous_pts:
                    raise TransitionFeatureError("Decoded source PTS must be strictly increasing")
                previous_pts = pts
                playback = pts * time_base - origin
                if playback < cache_start:
                    preroll += 1
                    continue
                if playback >= cache_end:
                    first_excluded = pts
                    break
                if geometry is None:
                    if frame.width < 4 or frame.height < 4:
                        raise TransitionFeatureError("Source geometry is too small")
                    width = min(analysis_width, frame.width)
                    height = max(2, round(frame.height * width / frame.width))
                    roi = _roi_geometry(width, height)
                    geometry = {"source_width": frame.width, "source_height": frame.height,
                                "source_pixel_format": frame.format.name,
                                "source_color_range": str(getattr(frame, "color_range", None)),
                                "analysis_width": width, "analysis_height": height,
                                "analysis_pixel_format": "gray8", "interpolation": "AREA",
                                "analysis_scale_x": _rational(Fraction(width, frame.width)),
                                "analysis_scale_y": _rational(Fraction(height, frame.height)),
                                "roi_nominal_fractions": {"left_removed": "1/20", "right_removed": "1/20",
                                                          "top_removed": "1/10", "bottom_removed": "1/10"},
                                "roi_rounding": "ceil removed edges / floor far edges",
                                "roi_analysis_pixels": roi,
                                "roi_source_pixels_nominal": _roi_geometry(frame.width, frame.height),
                                "roi_mapped_source_bounds": {
                                    key: _rational(Fraction(roi[key] * (frame.width if key in ("left", "right") else frame.height),
                                                                     width if key in ("left", "right") else height))
                                    for key in ("left", "right", "top", "bottom")},
                                "cache_width": cache_width, "cache_height": cache_height,
                                "cache_content": "fixed central ROI", "cache_pixel_format": "gray8",
                                "cache_regrid_scale_x": _rational(Fraction(cache_width, roi["width"])),
                                "cache_regrid_scale_y": _rational(Fraction(cache_height, roi["height"])),
                                "cache_aspect_regridding": Fraction(cache_width, cache_height) != Fraction(roi["width"], roi["height"]),
                                "rotation_applied": False}
                elif (frame.width, frame.height) != (geometry["source_width"], geometry["source_height"]):
                    raise TransitionFeatureError("Source dimensions change within the interval")
                gray = frame.to_ndarray(format="gray", width=geometry["analysis_width"],
                                        height=geometry["analysis_height"], interpolation="AREA")
                signals = _signals(gray, geometry["roi_analysis_pixels"], np)
                pts_values.append(pts)
                caches.append(cv2.resize(signals["roi"], (cache_width, cache_height), interpolation=cv2.INTER_AREA))
                means.append(signals["full_mean"])
                roi_means.append(signals["roi_mean"])
                deviations.append(signals["roi_std"])
                histograms.append(signals["gray_hist"])
                energies.append(signals["edge_energy"])
                mads.append(float(np.abs(signals["normalized_roi"] - previous_roi).mean(dtype=np.float64))
                            if previous_roi is not None else float("nan"))
                histogram_changes.append(float(np.abs(signals["gray_hist"] - previous_histogram).sum(dtype=np.float64))
                                         if previous_histogram is not None else float("nan"))
                previous_roi, previous_histogram = signals["normalized_roi"], signals["gray_hist"]
                duration = getattr(frame, "duration", None)
                last_duration = (_source_ticks(duration, frame.time_base, time_base, "Frame duration")
                                 if isinstance(duration, int) and duration > 0 else None)
                now = time.perf_counter()
                if len(pts_values) % 5000 == 0 or now - last_progress >= 60:
                    print(json.dumps({"stage": "transition_feature_extraction", "processed_frames": len(pts_values),
                                      "playback_seconds": float(playback), "elapsed_seconds": now - decode_started}),
                          file=sys.stderr, flush=True)
                    last_progress = now
            if not pts_values:
                raise TransitionFeatureError("Requested interval contains no decoded video frames")
            if first_excluded is not None:
                end_pts, end_basis = first_excluded, "first_excluded_decoded_frame_pts"
            elif last_duration is not None and last_duration > 0:
                end_pts, end_basis = pts_values[-1] + last_duration, "last_frame_pts_plus_duration"
            elif (stream.start_time == manifest["timeline"].get("source_start_pts")
                  and stream.duration == manifest["timeline"].get("duration_ts")
                  and isinstance(stream.start_time, int) and isinstance(stream.duration, int)
                  and stream.start_time + stream.duration > pts_values[-1]):
                end_pts, end_basis = stream.start_time + stream.duration, "manifest_validated_stream_end"
            else:
                raise TransitionFeatureError("No exact endpoint is available; FPS-derived durations are forbidden")
        decode_elapsed = time.perf_counter() - decode_started
        if (source_state(video) != video_before or video_request.resolve(strict=True) != video
                or source_state(manifest_file) != manifest_before
                or requested_manifest.resolve(strict=True) != manifest_file or manifest_file.read_bytes() != raw):
            raise TransitionFeatureError("Source video or manifest changed during feature extraction")
        next_values = pts_values[1:] + [end_pts]
        source_times = [pts * time_base for pts in pts_values]
        playback_times = [value - origin for value in source_times]
        overlaps = [max(Fraction(0), min(next_pts * time_base - origin, end) - max(current, start))
                    for current, next_pts in zip(playback_times, next_values)]
        overlap_total = sum(overlaps, Fraction(0))
        if overlap_total != end - start:
            raise TransitionFeatureError("Decoded cache does not completely cover the requested evaluation interval; use sufficient context padding")
        valid = np.ones(len(pts_values), dtype=np.bool_)
        valid[0] = False
        delta_seconds = np.asarray([float("nan")] +
                                   [float((right - left) * time_base) for left, right in zip(pts_values, pts_values[1:])], dtype=np.float64)
        arrays = {"pts": np.asarray(pts_values, dtype=np.int64),
                  "next_pts": np.asarray(next_values, dtype=np.int64),
                  "source_seconds": np.asarray([float(value) for value in source_times], dtype=np.float64),
                  "playback_seconds": np.asarray([float(value) for value in playback_times], dtype=np.float64),
                  "frame_delta_seconds": delta_seconds,
                  "evaluation_mask": np.asarray([start <= value < end for value in playback_times], dtype=np.bool_),
                  "evaluation_overlap_seconds": np.asarray([float(value) for value in overlaps], dtype=np.float64),
                  "gray_cache": np.stack(caches).astype(np.uint8, copy=False),
                  "full_mean": np.asarray(means, dtype=np.float32),
                  "roi_mean": np.asarray(roi_means, dtype=np.float32),
                  "roi_std": np.asarray(deviations, dtype=np.float32),
                  "adjacent_mad": np.asarray(mads, dtype=np.float32),
                  "adjacent_mad_valid": valid,
                  "gray_hist": np.stack(histograms).astype(np.float32, copy=False),
                  "adjacent_hist_l1": np.asarray(histogram_changes, dtype=np.float32),
                  "edge_energy": np.asarray(energies, dtype=np.float32),
                  "time_base_num": np.asarray(time_base.numerator, dtype=np.int64),
                  "time_base_den": np.asarray(time_base.denominator, dtype=np.int64),
                  "playback_origin_num": np.asarray(origin.numerator, dtype=np.int64),
                  "playback_origin_den": np.asarray(origin.denominator, dtype=np.int64),
                  "video_version_id": np.asarray(manifest["video_version_id"]),
                  "film_namespace": np.asarray(manifest["film_reference"]["namespace"]),
                  "film_key": np.asarray(manifest["film_reference"]["key"]),
                  "manifest_sha256": np.asarray(hashlib.sha256(raw).hexdigest())}
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **arrays)
        payload = buffer.getvalue()
    except TransitionFeatureError:
        raise
    except (ShotError, IngestError, OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise TransitionFeatureError("Cannot extract source-bound transition features: %s" % exc) from exc
    except Exception as exc:
        raise TransitionFeatureError("Grayscale decoding or measurement failed: %s" % exc) from exc
    run_id = str(uuid4())
    run = {"schema_version": 1, "artifact_kind": "transition_feature_run", "run_id": run_id,
           "status": "complete", "started_at_utc": started_at, "completed_at_utc": utc_now(),
           "elapsed_seconds": time.perf_counter() - started,
           "film_reference": manifest["film_reference"], "video_version_id": manifest["video_version_id"],
           "inputs": {"source_manifest": {"path": str(manifest_file), "sha256": hashlib.sha256(raw).hexdigest()},
                      "source_video": {"path": str(video), "sha256": checksum, "size_bytes": size,
                                       "hash_scope": "entire_file_bytes_reverified_before_decode"}},
           "evaluation_interval": {"start_playback_seconds": float(start), "end_playback_seconds": float(end),
                                   "start_playback_rational": _rational(start), "end_playback_rational": _rational(end),
                                   "duration_seconds": float(end - start), "interval_convention": "[start,end)",
                                   "verified_frame_support_seconds": float(overlap_total)},
           "cache_interval": {"requested_start_playback_seconds": float(cache_start),
                              "requested_end_playback_seconds": float(cache_end),
                              "start_pts": pts_values[0], "end_pts": end_pts, "time_base": _rational(time_base),
                              "start_playback_seconds": float(playback_times[0]),
                              "end_playback_seconds": float(end_pts * time_base - origin), "end_basis": end_basis},
           "parameters": {"analysis_width_limit": analysis_width, "context_pad_seconds": float(padding),
                          "gray_hist_bins": 32, "geometry": geometry, "frame_skipping": False,
                          "annotation_inputs": [], "label_dependent_parameters": False},
           "feature_definitions": {
               "full_mean": "Mean digital gray8 intensity over the full 160-width analysis image, divided by 255.",
               "roi_mean": "Fixed-ROI gray8 mean divided by 255.",
               "roi_std": "Fixed-ROI population standard deviation (ddof=0) of gray8/255.",
               "adjacent_mad": "Mean absolute per-pixel difference between consecutive fixed-ROI gray8/255 images; first value NaN.",
               "adjacent_mad_valid": "False only at the first cached frame, whose predecessor is not cached.",
               "gray_hist": "32 equal gray8 bins [0,8),...,[248,256), normalized to sum to one.",
               "adjacent_hist_l1": "L1 distance between consecutive normalized gray histograms; first value NaN.",
               "edge_energy": "Half the sum of mean absolute horizontal and vertical adjacent-pixel differences of ROI gray8/255.",
               "gray_cache": "Fixed-ROI gray8 regridded with AREA interpolation to the declared cache geometry.",
               "frame_delta_seconds": "Current minus previous original source PTS times time_base; first value NaN.",
               "evaluation_mask": "Strict frame-presentation point mask: evaluation_start <= playback_seconds < evaluation_end.",
               "evaluation_overlap_seconds": "Intersection of [current PTS,next PTS) frame support with the exact evaluation interval; sums to its duration."},
           "arrays": {name: {"dtype": str(value.dtype), "shape": list(value.shape)} for name, value in arrays.items()},
           "decode": {"decoded_frame_count": decoded, "processed_frame_count": len(pts_values),
                      "evaluation_point_frame_count": int(arrays["evaluation_mask"].sum()),
                      "preroll_frame_count": preroll, "first_excluded_frame_pts": first_excluded,
                      "last_included_frame_pts": pts_values[-1], "last_frame_duration_ticks": last_duration,
                      "decode_elapsed_seconds": decode_elapsed, "decoder_thread_count": 2,
                      "decoder_thread_type": "AUTO", "frame_skipping": False},
           "software": {**software, "pyav_version": av.__version__, "opencv_version": cv2.__version__,
                        "numpy_version": np.__version__,
                        "pyav_ffmpeg_libraries": {key: list(value) for key, value in av.library_versions.items()}},
           "outputs": {"features.npz": {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}},
           "limitations": ["Digital grayscale intensity is not calibrated historical film luminance.",
                           "Fixed cropping reduces watermark/border influence but also excludes image content at the margins.",
                           "Motion, camera changes, compression, exposure changes and editing can all affect these measurements.",
                           "This cache contains no gradual-transition predictions, narrative annotations or interpreted film-form conclusions."]}
    try:
        publish_bundle(output, {"features.npz": payload, "run.json": json_bytes(run)})
    except (IngestError, OSError) as exc:
        raise TransitionFeatureError("Could not publish feature cache: %s" % exc) from exc
    return {"run_id": run_id, "film_reference": manifest["film_reference"],
            "video_version_id": manifest["video_version_id"], "npz_path": str(output / "features.npz"),
            "run_path": str(output / "run.json"), "frame_count": len(pts_values),
            "evaluation_frame_count": int(arrays["evaluation_mask"].sum()),
            "evaluation_support_seconds": float(overlap_total), "elapsed_seconds": time.perf_counter() - started}
