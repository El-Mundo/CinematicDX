"""Descriptive shot timelines, with explicit temporal support and prediction status."""

from bisect import bisect_left
from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import tempfile

from .ingest import IngestError, json_bytes, publish_bundle, software_provenance, utc_now


class ReportError(IngestError):
    pass


def local_cutting_rates(cut_times, start, end, window_seconds=60.0, step_seconds=15.0):
    values = [start, end, window_seconds, step_seconds, *cut_times]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise ReportError("Cut times and window parameters must be finite numbers.")
    if end <= start or window_seconds <= 0 or step_seconds <= 0:
        raise ReportError("Coverage and window lengths must be positive.")
    cuts = sorted(cut_times)
    if any(value <= start or value >= end for value in cuts) or len(set(cuts)) != len(cuts):
        raise ReportError("Cut candidates must be distinct and internal to the analysed coverage.")
    count = int(math.floor((end - start) / step_seconds))
    if count > 1000000:
        raise ReportError("The requested cutting-rate grid is too large.")
    centers = [start + step_seconds * index for index in range(count + 1)]
    if end - centers[-1] > 1e-9:
        centers.append(end)
    rows = []
    for center in centers:
        left, right = max(start, center - window_seconds / 2), min(end, center + window_seconds / 2)
        exposure = right - left
        ncuts = bisect_left(cuts, right) - bisect_left(cuts, left)
        rows.append({"center_playback_seconds": center, "start_playback_seconds": left,
                     "end_playback_seconds": right, "actual_window_seconds": exposure,
                     "cut_candidate_count": ncuts, "cut_candidates_per_minute": 60 * ncuts / exposure,
                     "edge_truncated": exposure < window_seconds - 1e-9})
    return rows


def _csv_bytes(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _plots(data, durations, rates):
    cache = Path(tempfile.gettempdir()) / "cinematicdx-mpl-cache"
    cache.mkdir(exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
        from matplotlib.ticker import FuncFormatter
    except ImportError as error:
        raise ReportError("Plotting needs the optional M3 runtime; install requirements-m3.txt.") from error
    format_time = FuncFormatter(lambda value, position: "%02d:%02d:%02d" % (
        int(max(value, 0)) // 3600, int(max(value, 0)) % 3600 // 60, int(max(value, 0)) % 60))
    figure, axes = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True, constrained_layout=True)
    starts = [shot["start_playback_seconds"] for shot in data["shots"]]
    axes[0].plot(starts, durations, color="#32638a", linewidth=.65, marker=".", markersize=2)
    axes[0].set_ylabel("Detected interval duration (s)")
    axes[0].grid(alpha=.2)
    axes[1].plot([r["center_playback_seconds"] for r in rates],
                 [r["cut_candidates_per_minute"] for r in rates], color="#aa6236", linewidth=1)
    axes[1].set_ylabel("Cut candidates / minute")
    axes[1].set_xlabel("Playback position; original source timestamps remain in the tables")
    axes[1].xaxis.set_major_formatter(format_time)
    axes[1].grid(alpha=.2)
    figure.suptitle("%s — descriptive timeline; automated boundaries require review" % data["film_reference"]["key"], fontsize=11)
    output = {}
    for name, image_format in [("timeline.png", "png"), ("timeline.pdf", "pdf")]:
        stream = io.BytesIO()
        figure.savefig(stream, format=image_format, dpi=170)
        output[name] = stream.getvalue()
    plt.close(figure)
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    axis.hist(durations, bins=min(50, max(1, int(math.sqrt(len(durations))))), color="#32638a")
    axis.set_xlabel("Detected interval duration (s)")
    axis.set_ylabel("Number of intervals")
    axis.set_title("Duration distribution — descriptive, unreviewed segmentation")
    stream = io.BytesIO()
    figure.savefig(stream, format="png", dpi=170)
    output["duration_distribution.png"] = stream.getvalue()
    plt.close(figure)
    return output, matplotlib.__version__


def summarize_shots(shots_path, output_dir, *, window_seconds=60.0, step_seconds=15.0, render=True):
    output = Path(output_dir).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ReportError("Output already exists; choose a new report directory.")
    started = utc_now()
    source = Path(shots_path).expanduser().resolve(strict=True)
    raw = source.read_bytes()
    data = json.loads(raw)
    shots = data.get("shots", [])
    if not shots or not isinstance(shots, list):
        raise ReportError("A non-empty shot table is required.")
    try:
        start = float(data["coverage"]["start_playback_seconds"])
        end = float(data["coverage"]["end_playback_seconds"])
        durations = [float(shot["duration_seconds"]) for shot in shots]
        cuts = [float(boundary["playback_seconds"]) for boundary in data["boundaries"]]
        previous = start
        for shot, duration in zip(shots, durations):
            if not math.isfinite(duration) or duration <= 0 or abs(duration - (
                    shot["end_playback_seconds"] - shot["start_playback_seconds"])) > 1e-6:
                raise ReportError("Shot durations are invalid or inconsistent with their timestamps.")
            if abs(shot["start_playback_seconds"] - previous) > 1e-6:
                raise ReportError("Shot intervals must be ordered and contiguous.")
            previous = shot["end_playback_seconds"]
        if abs(sum(durations) - (end - start)) > 1e-5:
            raise ReportError("Shot durations do not reconcile with declared coverage.")
        rates = local_cutting_rates(cuts, start, end, window_seconds, step_seconds)
    except (KeyError, TypeError, ValueError) as error:
        raise ReportError("Invalid shot timeline: " + str(error)) from error
    summary = {"schema_version": 1, "artifact_kind": "descriptive_shot_report",
               "film_reference": data["film_reference"], "video_version_id": data["video_version_id"],
               "segmentation_id": data["segmentation_id"], "coverage": data["coverage"],
               "shot_count": len(shots), "cut_candidate_count": len(cuts),
               "mean_duration_seconds": statistics.mean(durations),
               "median_duration_seconds": statistics.median(durations),
               "minimum_duration_seconds": min(durations), "maximum_duration_seconds": max(durations),
               "validation_status_counts": dict(Counter(
                   shot.get("validation_status", "unspecified") for shot in shots)),
               "window_seconds": window_seconds, "step_seconds": step_seconds,
               "window_convention": "Centred, half-open windows; edge exposure is truncated and used as denominator.",
               "limitations": ["Durations and cutting rates derive from the same segmentation; they are not independent formal properties.",
                               "Intervals touching an excerpt edge may be censored parts of shots.",
                               "Distributions do not establish narrative organisation or metric montage."]}
    payloads = {"summary.json": json_bytes(summary), "local_cutting_rate.csv": _csv_bytes(rates, list(rates[0]))}
    plot_version = None
    if render:
        plots, plot_version = _plots(data, durations, rates)
        payloads.update(plots)
    run = {"schema_version": 1, "artifact_kind": "shot_report_run", "status": "complete",
           "started_at_utc": started, "completed_at_utc": utc_now(), "software": software_provenance(),
           "matplotlib_version": plot_version, "input": {"path": str(source), "sha256": hashlib.sha256(raw).hexdigest()},
           "parameters": {"window_seconds": window_seconds, "step_seconds": step_seconds, "render": render},
           "outputs": {name: {"sha256": hashlib.sha256(value).hexdigest(), "size_bytes": len(value)}
                       for name, value in payloads.items()}}
    payloads["run.json"] = json_bytes(run)
    publish_bundle(output, payloads)
    return {"output_directory": str(output), "shot_count": len(shots),
            "mean_duration_seconds": summary["mean_duration_seconds"],
            "median_duration_seconds": summary["median_duration_seconds"]}
