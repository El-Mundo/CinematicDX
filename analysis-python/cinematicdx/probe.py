"""Small, inspectable ffprobe measurements; no whole-film timing certification.

The frame sample reads a bounded packet prefix, not a guaranteed number of frames.
FFmpeg documents ``-read_intervals ...%+#N`` as a packet count; stream discovery,
codec buffering and packet/frame relationships can change the returned frame count.
See https://ffmpeg.org/ffprobe.html#Main-options for the command semantics.
"""

import json
import subprocess
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Optional


MAX_TIMESTAMP_SAMPLE_FRAMES = 256
HEADER_TIMEOUT_SECONDS = 30
SAMPLE_TIMEOUT_SECONDS = 30
_DISCOVERY_OPTIONS = ["-probesize", "5000000", "-analyzeduration", "5000000"]


class ProbeError(RuntimeError):
    """A missing input/tool, failed probe, or unusable video/timing selection."""

    def __init__(self, message, *, code="probe_failed", argv=None, stderr=None):
        super().__init__(message)
        self.code = code
        self.argv = list(argv) if argv is not None else None
        self.stderr = stderr


def _run(argv, timeout):
    try:
        completed = subprocess.run(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError("ffprobe executable was not found: " + argv[0],
                         code="tool_missing", argv=argv) from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffprobe exceeded its %s-second time limit" % timeout,
                         code="tool_timeout", argv=argv) from exc
    except (OSError, ValueError) as exc:
        raise ProbeError("Could not run ffprobe: " + str(exc),
                         code="tool_failed", argv=argv) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()
        raise ProbeError("ffprobe failed (exit %s): %s" % (completed.returncode, detail[:2000]),
                         code="tool_failed", argv=argv, stderr=completed.stderr)
    return completed.stdout, completed.stderr or ""


@lru_cache(maxsize=8)
def _probe_version(executable):
    """Reuse executable provenance within one process (e.g. a folder inventory)."""
    argv = (executable, "-version")
    stdout, stderr = _run(list(argv), 10)
    if not stdout.strip():
        raise ProbeError("ffprobe returned no version information", code="invalid_response", argv=argv)
    return argv, stdout.strip(), stderr


def _read_json(argv, timeout):
    stdout, stderr = _run(argv, timeout)
    try:
        def reject_nonfinite(value):
            raise ValueError("non-finite JSON number: " + value)
        payload = json.loads(stdout, parse_constant=reject_nonfinite)
    except (ValueError, TypeError) as exc:
        raise ProbeError("ffprobe returned invalid JSON", code="invalid_json", argv=argv,
                         stderr=stderr) from exc
    if not isinstance(payload, dict):
        raise ProbeError("ffprobe JSON must be an object", code="invalid_json", argv=argv)
    return payload, stderr


def _integer(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value) if isinstance(value, (int, str)) else None
    except ValueError:
        return None


def _fraction(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Fraction(str(value).strip())
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def _rational(value):
    return None if value is None else "%s/%s" % (value.numerator, value.denominator)


def _seconds(value):
    return None if value is None else float(value)


def _positive_fraction(value):
    parsed = _fraction(value)
    return parsed if parsed is not None and parsed > 0 else None


def _select_video(header, stream_index):
    streams = header.get("streams", [])
    if not isinstance(streams, list) or any(not isinstance(item, dict) for item in streams):
        raise ProbeError("ffprobe returned an invalid stream list", code="invalid_response")
    if any(not isinstance(stream.get("disposition") or {}, dict) for stream in streams):
        raise ProbeError("ffprobe returned invalid stream dispositions", code="invalid_response")
    videos = [stream for stream in streams if stream.get("codec_type") == "video"
              and (stream.get("disposition") or {}).get("attached_pic") not in (1, "1", True)]
    if not videos:
        raise ProbeError("No genuine video stream was found (attached pictures are excluded)",
                         code="no_video_stream")
    if stream_index is not None:
        matches = [stream for stream in videos if _integer(stream.get("index")) == stream_index]
        if len(matches) != 1:
            raise ProbeError("Selected stream is absent, ambiguous, or is not genuine video: %s"
                             % stream_index, code="invalid_stream")
        selected = matches[0]
    elif len(videos) == 1:
        selected = videos[0]
    else:
        defaults = [stream for stream in videos
                    if (stream.get("disposition") or {}).get("default") in (1, "1", True)]
        if len(defaults) != 1:
            raise ProbeError("Multiple video streams require an explicit absolute stream index: %s"
                             % [stream.get("index") for stream in videos],
                             code="ambiguous_video_stream")
        selected = defaults[0]
    if _integer(selected.get("index")) is None or _integer(selected.get("index")) < 0:
        raise ProbeError("Selected video has no usable stream index", code="invalid_stream")
    return selected, len(videos)


def _discrepancy(records, field, first, second, tolerance):
    if first is not None and second is not None and abs(first - second) > tolerance:
        records.append({"field": field, "difference_seconds": float(first - second),
                        "difference_rational": _rational(first - second),
                        "tolerance_seconds": float(tolerance)})


def _frame_record(frame, sample_index, selected_index, time_base, discrepancies, flags):
    pts = _integer(frame.get("pts"))
    best_effort = _integer(frame.get("best_effort_timestamp"))
    pts_seconds = pts * time_base if pts is not None else None
    best_seconds = best_effort * time_base if best_effort is not None else None
    tolerance = max(time_base, Fraction(1, 1000000))
    _discrepancy(discrepancies, "frame[%s].pts_time" % sample_index,
                 pts_seconds, _fraction(frame.get("pts_time")), tolerance)
    _discrepancy(discrepancies, "frame[%s].best_effort_timestamp_time" % sample_index,
                 best_seconds, _fraction(frame.get("best_effort_timestamp_time")), tolerance)
    _discrepancy(discrepancies, "frame[%s].pts_vs_best_effort" % sample_index,
                 pts_seconds, best_seconds, Fraction(0))
    if pts is None:
        flags.add("missing_pts")
    source = "pts" if pts is not None else "best_effort_timestamp" if best_effort is not None else None
    if source == "best_effort_timestamp":
        flags.add("best_effort_timestamp_used")
    timestamp = pts if pts is not None else best_effort
    seconds = timestamp * time_base if timestamp is not None else None
    return {
        "sample_index": sample_index, "stream_index": selected_index,
        "time_base": _rational(time_base),
        "pts": pts, "pts_time": frame.get("pts_time"),
        "pts_seconds": _seconds(pts_seconds), "pts_seconds_rational": _rational(pts_seconds),
        "best_effort_timestamp": best_effort,
        "best_effort_timestamp_time": frame.get("best_effort_timestamp_time"),
        "best_effort_seconds": _seconds(best_seconds),
        "best_effort_seconds_rational": _rational(best_seconds),
        "timestamp_source": source, "source_timestamp": timestamp,
        "source_seconds": _seconds(seconds), "source_seconds_rational": _rational(seconds),
        "playback_offset_seconds": None, "playback_offset_rational": None,
    }


def probe_video(path: Path, ffprobe="ffprobe", stream_index: Optional[int] = None,
                timestamp_sample_frames: int = 12) -> dict:
    """Probe one local file and an optional bounded prefix of decoded timestamps.

    ``stream_index`` is the absolute ffprobe stream index, not the video ordinal.
    A sample size of zero is explicitly header-only. Positive requests record at
    most N frames after a packet-limited read; fewer frames may be available. Source
    PTS and best-effort coordinates remain separate. Playback offsets are derived
    from the declared selected-stream start, or the first usable sampled timestamp.
    Neither header rates nor this limited sample classify whole-file CFR/VFR.
    """
    if (isinstance(timestamp_sample_frames, bool) or not isinstance(timestamp_sample_frames, int)
            or not 0 <= timestamp_sample_frames <= MAX_TIMESTAMP_SAMPLE_FRAMES):
        raise ProbeError("Timestamp sample size must be an integer between 0 and %s"
                         % MAX_TIMESTAMP_SAMPLE_FRAMES, code="invalid_option")
    if stream_index is not None and (isinstance(stream_index, bool)
                                    or not isinstance(stream_index, int) or stream_index < 0):
        raise ProbeError("Stream index must be a non-negative integer", code="invalid_option")
    try:
        source_path = Path(path).expanduser().resolve(strict=True)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        raise ProbeError("Video input does not exist or cannot be resolved: %s" % path,
                         code="invalid_input") from exc
    if not source_path.is_file():
        raise ProbeError("Video input is not a regular file: %s" % source_path, code="invalid_input")
    executable = str(ffprobe)
    version_argv, version_output, version_stderr = _probe_version(executable)
    header_argv = [executable, "-v", "error", *_DISCOVERY_OPTIONS,
                   "-show_format", "-show_streams", "-of", "json", str(source_path)]
    header, header_stderr = _read_json(header_argv, HEADER_TIMEOUT_SECONDS)
    selected, video_count = _select_video(header, stream_index)
    selected_index = _integer(selected["index"])
    container = header.get("format") or {}
    if not isinstance(container, dict):
        raise ProbeError("ffprobe returned invalid container metadata", code="invalid_response")
    flags = {"VFR_unknown", "integrity_not_certified", "full_decode_not_requested"}
    discrepancies = []
    time_base = _positive_fraction(selected.get("time_base"))
    if time_base is None:
        flags.add("missing_or_invalid_time_base")
        if timestamp_sample_frames:
            raise ProbeError("Selected video lacks a valid positive time base", code="invalid_time_base")
    avg_rate = _positive_fraction(selected.get("avg_frame_rate"))
    nominal_rate = _positive_fraction(selected.get("r_frame_rate"))
    if avg_rate is None:
        flags.add("missing_or_invalid_avg_frame_rate")
    if nominal_rate is None:
        flags.add("missing_or_invalid_r_frame_rate")
    if avg_rate is not None and nominal_rate is not None and avg_rate != nominal_rate:
        flags.add("header_frame_rates_differ")
    start_pts = _integer(selected.get("start_pts"))
    start_from_pts = start_pts * time_base if start_pts is not None and time_base is not None else None
    reported_start = _fraction(selected.get("start_time"))
    origin = start_from_pts if start_from_pts is not None else reported_start
    origin_source = "stream.start_pts" if start_from_pts is not None else "stream.start_time" if reported_start is not None else None
    tolerance = max(time_base or Fraction(0), Fraction(1, 1000000))
    _discrepancy(discrepancies, "stream.start_pts_vs_start_time", start_from_pts, reported_start, tolerance)
    duration_ts = _integer(selected.get("duration_ts"))
    duration_from_ticks = duration_ts * time_base if duration_ts is not None and time_base is not None else None
    stream_duration = _positive_fraction(selected.get("duration"))
    format_duration = _positive_fraction(container.get("duration"))
    if duration_from_ticks is not None and duration_from_ticks <= 0:
        duration_from_ticks = None
    duration = duration_from_ticks if duration_from_ticks is not None else stream_duration if stream_duration is not None else format_duration
    duration_source = "stream.duration_ts" if duration_from_ticks is not None else "stream.duration" if stream_duration is not None else "format.duration" if format_duration is not None else None
    if duration is None:
        flags.add("missing_duration")
    _discrepancy(discrepancies, "stream.duration_ts_vs_duration", duration_from_ticks, stream_duration, tolerance)
    _discrepancy(discrepancies, "stream_vs_container_duration", duration_from_ticks or stream_duration,
                 format_duration, max(tolerance, Fraction(1, 1000)))
    if not _integer(selected.get("width")) or not _integer(selected.get("height")):
        flags.add("missing_video_dimensions")

    sample_argv = None
    sample_stderr = ""
    raw_sample = None
    frames = []
    packet_limit = 0
    decoded_count = 0
    if timestamp_sample_frames:
        flags.add("sample_limited")
        packet_limit = max(32, timestamp_sample_frames * 4)
        sample_argv = [executable, "-v", "error", *_DISCOVERY_OPTIONS, "-threads", "1",
                       "-select_streams", str(selected_index), "-read_intervals", "%+#" + str(packet_limit),
                       "-show_frames", "-show_entries",
                       "frame=stream_index,pts,pts_time,best_effort_timestamp,best_effort_timestamp_time",
                       "-of", "json", str(source_path)]
        raw_sample, sample_stderr = _read_json(sample_argv, SAMPLE_TIMEOUT_SECONDS)
        raw_frames = raw_sample.get("frames", [])
        if not isinstance(raw_frames, list) or any(not isinstance(frame, dict) for frame in raw_frames):
            raise ProbeError("ffprobe returned an invalid frame sample", code="invalid_response", argv=sample_argv)
        if any(_integer(frame.get("stream_index")) != selected_index for frame in raw_frames):
            raise ProbeError("Frame sample does not identify the selected video stream",
                             code="invalid_response", argv=sample_argv)
        decoded_count = len(raw_frames)
        for index, frame in enumerate(raw_frames[:timestamp_sample_frames]):
            frames.append(_frame_record(frame, index, selected_index, time_base, discrepancies, flags))
        usable = [frame for frame in frames if frame["source_timestamp"] is not None]
        if not usable:
            raise ProbeError("No usable PTS or best-effort timestamps were returned by the bounded sample",
                             code="no_timed_frames", argv=sample_argv, stderr=sample_stderr)
        if origin is None:
            origin = usable[0]["source_timestamp"] * time_base
            origin_source = "first_usable_sample_timestamp"
            flags.add("playback_origin_from_sample")
        for frame in frames:
            if frame["source_timestamp"] is not None:
                offset = frame["source_timestamp"] * time_base - origin
                frame["playback_offset_seconds"] = float(offset)
                frame["playback_offset_rational"] = _rational(offset)
                if offset < 0:
                    flags.add("sample_before_declared_stream_start")
        if len(frames) < timestamp_sample_frames:
            flags.add("fewer_frames_than_requested")
        if decoded_count > timestamp_sample_frames:
            flags.add("sample_records_truncated")
    else:
        flags.update({"header_only", "timing_not_validated"})

    intervals = []
    for first, second in zip(frames, frames[1:]):
        if first["source_timestamp"] is not None and second["source_timestamp"] is not None:
            intervals.append((second["source_timestamp"] - first["source_timestamp"]) * time_base)
    if any(value < 0 for value in intervals):
        flags.add("sample_timestamps_nonmonotonic")
    if any(value == 0 for value in intervals):
        flags.add("sample_timestamps_duplicate")
    varied = len(set(intervals)) > 1 if intervals else None
    if varied:
        flags.add("sample_intervals_vary")
    if discrepancies:
        flags.add("timing_discrepancy")
    if version_stderr or header_stderr or sample_stderr:
        flags.add("ffprobe_reported_stderr")
    summary = {
        "video_stream_index": selected_index, "genuine_video_stream_count": video_count,
        "format_name": container.get("format_name"), "codec_name": selected.get("codec_name"),
        "width": _integer(selected.get("width")), "height": _integer(selected.get("height")),
        "pixel_format": selected.get("pix_fmt"), "field_order": selected.get("field_order"),
        "sample_aspect_ratio": selected.get("sample_aspect_ratio"),
        "display_aspect_ratio": selected.get("display_aspect_ratio"),
        "time_base": _rational(time_base), "avg_frame_rate": _rational(avg_rate),
        "r_frame_rate": _rational(nominal_rate), "frame_rate_mode": "unknown",
        "reported_frame_count": _integer(selected.get("nb_frames")),
        "duration_ts": duration_ts, "duration_seconds": _seconds(duration),
        "duration_rational": _rational(duration), "duration_source": duration_source,
        "reported_stream_duration_seconds": _seconds(stream_duration),
        "reported_container_duration_seconds": _seconds(format_duration),
        "source_start_pts": start_pts, "source_start_time": selected.get("start_time"),
        "source_start_time_seconds": _seconds(reported_start),
        "source_start_pts_seconds": _seconds(start_from_pts),
        "container_start_time": container.get("start_time"),
        "playback_origin": {"source": origin_source, "source_seconds": _seconds(origin),
                            "source_seconds_rational": _rational(origin)},
    }
    for field in ("color_range", "color_space", "color_transfer", "color_primaries"):
        summary[field] = selected.get(field)
    return {
        "schema_version": 1, "path": str(source_path),
        "ffprobe": {"version": version_output.splitlines()[0], "version_output": version_output,
                    "version_argv": list(version_argv), "header_argv": header_argv,
                    "timestamp_sample_argv": sample_argv,
                    "stderr": {"version": version_stderr, "header": header_stderr, "timestamp_sample": sample_stderr}},
        "raw_header": header, "selected_video_stream_index": selected_index,
        "selected_video_stream": selected, "technical_summary": summary,
        "timestamp_sample": {
            "requested_frames": timestamp_sample_frames, "packet_limit": packet_limit,
            "decoded_frames_returned": decoded_count, "recorded_frames": len(frames),
            "coverage": "bounded_prefix" if timestamp_sample_frames else "not_performed",
            "frames": frames, "raw_ffprobe_output": raw_sample,
            "playback_offset_definition": "source_seconds minus technical_summary.playback_origin",
            "observed_intervals": {"seconds": [float(value) for value in intervals],
                                   "rational": [_rational(value) for value in intervals],
                                   "varied": varied,
                                   "variation_exceeds_one_tick": (max(intervals) - min(intervals) > time_base) if intervals else None},
        },
        "timing_discrepancies": discrepancies, "quality_flags": sorted(flags),
        "full_decode_requested": False, "integrity_certification": "not_performed",
        "limitations": [
            "Header rates and a bounded prefix do not establish whole-file CFR or VFR.",
            "The read interval limits packets, not an exact decoded-frame count; stream discovery and codec buffering also perform work, bounded by subprocess timeouts.",
            "Only the first requested frame records are retained; no resizing or re-encoding is performed.",
            "This probe does not certify full-file decodability, integrity, or historical source fidelity.",
        ],
    }
