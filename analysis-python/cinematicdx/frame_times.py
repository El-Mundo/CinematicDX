"""Resolve explicitly based frame labels through original decoded presentation PTS.

Frame labels are ordinals in the selected complete source stream, starting at its
first decoded output frame. They are not converted through nominal/average FPS.
"""

from fractions import Fraction
import hashlib
import json
from numbers import Integral
from pathlib import Path
import re
import time

from .ingest import (IngestError, hash_video, software_provenance, source_state, utc_now)


class FrameTimeError(Exception):
    """Frame labels cannot be safely resolved against their ingested source."""


def frame_number_to_index(frame_number, *, frame_base):
    """Convert a label convention to a decoder ordinal, without deriving time."""
    if isinstance(frame_base, bool) or not isinstance(frame_base, Integral) or frame_base not in (0, 1):
        raise FrameTimeError("frame_base must explicitly be 0 or 1")
    if isinstance(frame_number, bool) or not isinstance(frame_number, Integral):
        raise FrameTimeError("Requested frame numbers must be integers")
    index = int(frame_number) - int(frame_base)
    if index < 0:
        raise FrameTimeError("Frame %s is invalid for frame_base=%s" % (frame_number, frame_base))
    return index


def _fraction(value, label):
    try:
        if isinstance(value, bool):
            raise ValueError()
        return Fraction(str(value))
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise FrameTimeError("Invalid %s" % label) from exc


def _rational(value):
    return "%s/%s" % (value.numerator, value.denominator)


def _read_manifest(requested):
    path = requested.resolve(strict=True)
    before = source_state(path)
    raw = path.read_bytes()
    try:
        manifest = json.loads(raw)
        if manifest.get("artifact_kind") != "source_video_manifest":
            raise ValueError("expected an M2 source video manifest")
        reference = manifest["film_reference"]
        if not all(isinstance(reference.get(key), str) and reference[key].strip()
                   for key in ("namespace", "key")):
            raise ValueError("film reference needs its namespace and existing key")
        checksum = manifest["source"]["sha256"]
        if not isinstance(checksum, str) or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            raise ValueError("invalid source SHA-256")
        if manifest["video_version_id"] != "sha256:" + checksum:
            raise ValueError("video version and source SHA-256 disagree")
        selected_index = manifest["selected_video_stream_index"]
        if isinstance(selected_index, bool) or not isinstance(selected_index, int) or selected_index < 0:
            raise ValueError("invalid selected video stream index")
        time_base = _fraction(manifest["timeline"]["time_base"], "manifest time base")
        if time_base <= 0:
            raise ValueError("time base must be positive")
        playback = manifest["timeline"]["playback_origin"]
        origin = _fraction(playback.get("source_seconds_rational", playback.get("source_seconds")),
                           "manifest playback origin")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise FrameTimeError("Invalid M2 manifest: %s" % exc) from exc
    if before != source_state(path) or requested.resolve(strict=True) != path:
        raise FrameTimeError("Source manifest changed while it was being read")
    return path, before, raw, manifest, time_base, origin


def _time_record(frame, index, stream_time_base, origin):
    record = {"decoded_frame_index": index, "pts": frame.pts, "time_base": None,
              "stream_time_base": _rational(stream_time_base), "stream_pts": None,
              "source_seconds": None, "source_seconds_rational": None,
              "playback_seconds": None, "playback_seconds_rational": None,
              "timestamp_method": "PyAV decoded VideoFrame.pts multiplied by its own time_base"}
    if frame.time_base is None:
        return {**record, "status": "unresolved_missing_time_base"}
    base = Fraction(frame.time_base)
    if base <= 0:
        return {**record, "status": "unresolved_invalid_time_base"}
    record["time_base"] = _rational(base)
    if isinstance(frame.pts, bool) or not isinstance(frame.pts, Integral):
        return {**record, "status": "unresolved_missing_pts"}
    source_seconds = int(frame.pts) * base
    stream_ticks = source_seconds / stream_time_base
    playback_seconds = source_seconds - origin
    return {**record, "status": "resolved", "pts": int(frame.pts),
            "stream_pts": stream_ticks.numerator if stream_ticks.denominator == 1 else None,
            "source_seconds": float(source_seconds), "source_seconds_rational": _rational(source_seconds),
            "playback_seconds": float(playback_seconds), "playback_seconds_rational": _rational(playback_seconds)}


def _load_av():
    try:
        import av
    except (ImportError, OSError) as exc:
        raise FrameTimeError("Frame timing resolution needs the isolated PyAV environment: %s" % exc) from exc
    return av


def _resolve(manifest_path, frame_numbers, bases):
    requested = list(frame_numbers)
    if not requested:
        raise FrameTimeError("At least one frame number is required")
    for number in requested:
        frame_number_to_index(number, frame_base=0)
    requested = [int(number) for number in requested]
    if len(bases) == 1:
        for number in requested:
            frame_number_to_index(number, frame_base=bases[0])
    targets = {number - base for number in requested for base in bases if number >= base}
    maximum_index = max(targets)
    started_at, started = utc_now(), time.perf_counter()
    manifest_request = Path(manifest_path).expanduser().absolute()
    try:
        manifest_file, manifest_before, raw, manifest, stream_base, origin = _read_manifest(manifest_request)
        source = manifest["source"]
        video = Path(source["resolved_path"]).resolve(strict=True)
        video_request = Path(source.get("requested_path") or source["resolved_path"])
        if video_request.resolve(strict=True) != video:
            raise FrameTimeError("Requested source path no longer resolves to the ingested file")
        state = source_state(video)
        if (state[2], state[3]) != (source["size_bytes"], source["mtime_ns"]):
            raise FrameTimeError("Source size/mtime differs from M2; re-ingest before conversion")
        checksum, size, video_before = hash_video(video)
        if checksum != source["sha256"]:
            raise FrameTimeError("Source checksum differs from the ingested video version")
        av = _load_av()
        software = software_provenance()
        records, flags = {}, set()
        count, exhausted, previous_time = 0, True, None
        with av.open(str(video), mode="r") as container:
            matches = [stream for stream in container.streams
                       if stream.index == manifest["selected_video_stream_index"]]
            if len(matches) != 1 or matches[0].type != "video":
                raise FrameTimeError("Manifest-selected video stream is unavailable")
            stream = matches[0]
            if stream.time_base is None or Fraction(stream.time_base) != stream_base:
                raise FrameTimeError("Decoder time base differs from the M2 manifest")
            stream.codec_context.thread_count = 1
            stream.thread_type = "SLICE"
            # No seek: ordinals must be counted from the first decoded output frame.
            for index, frame in enumerate(container.decode(stream)):
                count = index + 1
                if frame.pts is None:
                    flags.add("missing_pts_in_decoded_prefix")
                elif frame.time_base is not None:
                    source_time = int(frame.pts) * Fraction(frame.time_base)
                    if previous_time is not None and source_time <= previous_time:
                        flags.add("nonincreasing_pts_in_decoded_prefix")
                    previous_time = source_time
                if index in targets:
                    records[index] = _time_record(frame, index, stream_base, origin)
                if index >= maximum_index:
                    exhausted = False  # EOF was not requested/probed after the final required output.
                    break
        if (source_state(video) != video_before or video_request.resolve(strict=True) != video
                or source_state(manifest_file) != manifest_before
                or manifest_request.resolve(strict=True) != manifest_file
                or manifest_file.read_bytes() != raw):
            raise FrameTimeError("Source video or manifest changed during frame timing resolution")
    except FrameTimeError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IngestError) as exc:
        raise FrameTimeError("Cannot resolve source-bound frame timings: %s" % exc) from exc
    except Exception as exc:
        raise FrameTimeError("PyAV frame decoding failed: %s" % exc) from exc
    rows = []
    for number in requested:
        candidates = {}
        for base in bases:
            index = number - base
            if index < 0:
                candidate = {"decoded_frame_index": None, "status": "invalid_frame_for_base"}
            else:
                candidate = records.get(index, {"decoded_frame_index": index,
                                                "status": "unresolved_frame_outside_decoded_source"})
            candidates[str(base)] = {"frame_base": base, **candidate}
        rows.append({"requested_frame": number, "candidates": candidates})
    if any(candidate["status"] != "resolved" for row in rows for candidate in row["candidates"].values()):
        flags.add("some_requested_frames_unresolved")
    if len(bases) > 1:
        flags.add("frame_base_unconfirmed")
    return {
        "schema_version": 1, "artifact_kind": "frame_time_resolution",
        "status": "partial" if "some_requested_frames_unresolved" in flags else "complete",
        "film_reference": manifest["film_reference"], "video_version_id": manifest["video_version_id"],
        "frame_base": bases[0] if len(bases) == 1 else None,
        "frame_base_status": "explicitly_selected" if len(bases) == 1 else "awaiting_user_confirmation",
        "frames": rows, "quality_flags": sorted(flags),
        "method": {"frame_number_scope": "entire selected source video stream from its first decoded output frame",
                   "ordinal_order": "PyAV container.decode(selected_stream) output (presentation order)",
                   "decoded_index_base": 0, "formula": "decoded_frame_index = requested_frame - frame_base",
                   "timestamp_source": "original decoded frame PTS and its own rational time_base",
                   "playback_offset_rule": "source seconds minus the M2 manifest playback origin",
                   "fps_used_for_timestamps": False, "seeking": False, "frame_skipping": False,
                   "image_conversion": False, "full_decode_requested": False,
                   "decoder_note": "Codec packet reordering/lookahead may internally decode buffered frames beyond the final emitted ordinal."},
        "timeline": {"stream_time_base": _rational(stream_base),
                     "playback_origin_source_seconds": float(origin),
                     "playback_origin_source_seconds_rational": _rational(origin)},
        "source_binding": {"manifest_path": str(manifest_file),
                           "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                           "video_path": str(video), "source_sha256": checksum,
                           "source_size_bytes": size, "source_mtime_ns": source["mtime_ns"],
                           "selected_video_stream_index": manifest["selected_video_stream_index"],
                           "hash_scope": "entire_source_file_bytes_reverified_before_decode",
                           "source_state_verified_before_and_after": True,
                           "manifest_unchanged_after_decode": True},
        "decode_audit": {"decoded_output_frame_count": count, "maximum_requested_decoded_index": maximum_index,
                         "stopped_at_required_index": not exhausted, "reached_eof_before_required_index": exhausted,
                         "decoder_thread_count": 1, "decoder_thread_type": "SLICE"},
        "software": {**software, "pyav_version": av.__version__,
                     "pyav_ffmpeg_libraries": {key: list(value) for key, value in av.library_versions.items()}},
        "started_at_utc": started_at, "completed_at_utc": utc_now(),
        "elapsed_seconds": time.perf_counter() - started,
        "limitations": ["Two-base results remain alternative candidates until the user's display convention is confirmed.",
                        "A frame ordinal refers to this exact video version and selected stream, not a shot-local counter.",
                        "This operation maps frame labels to measured timestamps; it does not create or reinterpret narrative annotations.",
                        "Only the required decoded prefix is inspected; no whole-file timing or decoding certificate is issued."],
    }


def resolve_frame_times(manifest_path: Path, frame_numbers, *, frame_base: int) -> dict:
    """Resolve labels only after explicitly choosing a zero- or one-based convention."""
    # Validate independently of list contents, including an empty iterable.
    frame_number_to_index(frame_base, frame_base=frame_base)
    return _resolve(manifest_path, frame_numbers, (int(frame_base),))


def resolve_frame_base_candidates(manifest_path: Path, frame_numbers) -> dict:
    """Measure both base candidates in one bounded prefix decode, without choosing one."""
    return _resolve(manifest_path, frame_numbers, (0, 1))
