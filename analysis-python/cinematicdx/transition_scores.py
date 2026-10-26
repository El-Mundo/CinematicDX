"""Convert aligned many-hot sigmoid scores into timestamped interval proposals.

This pure adapter neither loads a model nor reads labels/media. Input indices
refer to the supplied score/PTS sequence, not inferred full-film frame numbers.
Actual source PTS and the caller's explicit playback origin determine all times.
"""

import math
from fractions import Fraction
from numbers import Integral, Real


class TransitionScoresError(ValueError):
    """Scores and source display supports must describe the same valid frames."""


def _real(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TransitionScoresError(name + " must be a finite real number.")
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError()
        return result
    except (ValueError, OverflowError) as exc:
        raise TransitionScoresError(name + " must be a finite real number.") from exc


def _fraction(value, name):
    if isinstance(value, bool) or not isinstance(value, (str, Real)):
        raise TransitionScoresError(name + " must be an explicit finite rational time.")
    try:
        result = value if isinstance(value, Fraction) else Fraction(str(value))
        if not math.isfinite(float(result)):
            raise ValueError()
        return result
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise TransitionScoresError(name + " must be an explicit finite rational time.") from exc


def _sequence(values, name):
    if isinstance(values, (str, bytes, dict)):
        raise TransitionScoresError(name + " must be a one-dimensional sequence.")
    try:
        return list(values)
    except TypeError as exc:
        raise TransitionScoresError(name + " must be a one-dimensional sequence.") from exc


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TransitionScoresError(name + " must contain integer PTS values, without booleans.")
    return int(value)


def _time_fields(name, value):
    try:
        approximate = float(value)
        if not math.isfinite(approximate):
            raise ValueError()
    except (ValueError, OverflowError) as exc:
        raise TransitionScoresError("Source times must remain finite.") from exc
    return {name: approximate, name + "_rational": str(value)}


def scores_to_transition_intervals(scores, pts, next_pts, *, time_base,
                                   playback_origin, threshold=0.5,
                                   min_duration_seconds=0.4):
    """Return uninterrupted strict-threshold runs using real display supports.

    ``time_base`` is seconds per source PTS tick; ``playback_origin`` is an
    explicit offset in source seconds, so playback = PTS*time_base - origin.
    Fractions and rational strings preserve exact offsets and durations. PTS
    may be negative (valid source coordinates); each display support must have
    positive duration and end exactly where the following source frame starts.

    Every run is retained: duration >= the minimum goes to gradual_predictions,
    shorter runs go to short_transition_events without a hard-cut assertion.
    There is no smoothing, gap closing, maximum duration, threshold fitting,
    confidence calibration, or reference-dependent type assignment.
    """
    cutoff = _real(threshold, "threshold")
    if not 0 <= cutoff <= 1:
        raise TransitionScoresError("threshold must lie within [0, 1].")
    minimum = _fraction(min_duration_seconds, "min_duration_seconds")
    base = _fraction(time_base, "time_base")
    origin = _fraction(playback_origin, "playback_origin")
    if minimum <= 0 or base <= 0:
        raise TransitionScoresError("time_base and min_duration_seconds must be positive.")

    values = [_real(value, "scores") for value in _sequence(scores, "scores")]
    first_pts = [_integer(value, "pts") for value in _sequence(pts, "pts")]
    after_pts = [_integer(value, "next_pts") for value in _sequence(next_pts, "next_pts")]
    if len(values) != len(first_pts) or len(values) != len(after_pts):
        raise TransitionScoresError("scores, pts and next_pts must have identical lengths.")
    if any(value < 0 or value > 1 for value in values):
        raise TransitionScoresError("Sigmoid scores must lie within [0, 1].")
    for index, (first, after) in enumerate(zip(first_pts, after_pts)):
        if after <= first:
            raise TransitionScoresError("Every source display support must have positive duration.")
        if index and (first <= first_pts[index - 1] or after_pts[index - 1] != first):
            raise TransitionScoresError("PTS must increase with contiguous next_pts display supports.")

    gradual, short = [], []
    event_count = 0

    def append_run(start, stop):
        nonlocal event_count
        event_count += 1
        source_start = first_pts[start] * base
        source_end = after_pts[stop - 1] * base
        duration = source_end - source_start
        run_scores = values[start:stop]
        is_gradual = duration >= minimum
        event = {
            "transition_id": "transition-event-%06d" % event_count,
            "start_frame_index": start,
            "end_frame_index_exclusive": stop,
            "frame_index_reference": "zero_based_input_score_sequence",
            "frame_count": stop - start,
            "start_pts": first_pts[start], "end_pts": after_pts[stop - 1],
            "time_base": str(base), "playback_origin_seconds_rational": str(origin),
            "interval_convention": "[start,end)",
            "predicted_type": "unknown_gradual" if is_gradual else "unclassified_short_transition",
            "event_classification": "gradual_prediction" if is_gradual else "short_transition_event",
            "score_min": min(run_scores),
            "score_mean": math.fsum(run_scores) / len(run_scores),
            "score_max": max(run_scores),
            "score_kind": "uncalibrated_many_hot_sigmoid",
            "score_uncalibrated": True,
            "validation_status": "unreviewed_algorithmic_prediction",
        }
        for name, value in (("start_source_seconds", source_start),
                            ("end_source_seconds", source_end),
                            ("start_playback_seconds", source_start - origin),
                            ("end_playback_seconds", source_end - origin),
                            ("duration_seconds", duration)):
            event.update(_time_fields(name, value))
        (gradual if is_gradual else short).append(event)

    start = None
    for index, score in enumerate(values):
        if score > cutoff:
            if start is None:
                start = index
        elif start is not None:
            append_run(start, index)
            start = None
    if start is not None:
        append_run(start, len(values))

    return {
        "schema_version": 1,
        "artifact_kind": "thresholded_transition_score_intervals",
        "time_base": str(base),
        "playback_origin_seconds_rational": str(origin),
        "conversion_policy": {
            "threshold": cutoff, "comparison": "score > threshold",
            "min_duration_seconds": float(minimum),
            "min_duration_seconds_rational": str(minimum),
            "minimum_duration_comparison": "duration >= min_duration_seconds",
            "smoothing": False, "gap_closing": False, "maximum_duration_seconds": None,
            "duration_basis": "original source PTS to last actual next_pts",
            "score_uncalibrated": True,
            "short_events_are_not_classified_as_hard_cuts": True,
        },
        "counts": {"frames": len(values),
                   "above_threshold_frames": sum(value > cutoff for value in values),
                   "threshold_runs": event_count,
                   "gradual_predictions": len(gradual), "short_transition_events": len(short)},
        "gradual_predictions": gradual,
        "short_transition_events": short,
    }
