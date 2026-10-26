"""Compare point-cut predictions with explicitly independent, bounded references.

This module checks declarations and provenance; it cannot establish that an
annotator actually worked independently or labelled every cut in the interval.
All matching uses chronological one-to-one greedy pairing, not nearest-neighbor
optimization. A blank template is never treated as an annotated reference.
"""

import csv
import hashlib
import io
import json
import math
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from .ingest import (
    IngestError, json_bytes, publish_bundle, software_provenance, source_state, utc_now,
)


class ValidationError(ValueError):
    """Incompatible or incomplete annotations cannot establish validation results."""


MATCHING_POLICY = {
    "name": "chronological_one_to_one_greedy",
    "ordering": "Sort predictions and references by exact time, then boundary_id.",
    "pairing": "Pair the earliest remaining prediction and reference when their absolute "
               "time difference is at most tolerance; otherwise discard the earlier "
               "unmatchable point as FP or FN and continue.",
    "tolerance_inclusive": True,
    "one_to_one": True,
    "nearest_neighbor_optimization": False,
    "interval_convention": "[start,end)",
    "excluded_regions": "Remove predictions in excluded intervals before matching; "
                        "reference labels in those intervals are invalid.",
}


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(label + " must be nonempty text.")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(label + " must be an explicit finite number.")
    try:
        if not math.isfinite(float(value)):
            raise ValueError()
        return Fraction(str(value))
    except (ValueError, OverflowError) as exc:
        raise ValidationError(label + " must be an explicit finite number.") from exc


def _coordinate(record, field):
    value = _number(record.get(field), field)
    rational = record.get(field + "_rational")
    if rational is None:
        return value
    try:
        if not isinstance(rational, str):
            raise ValueError()
        exact = Fraction(rational)
        if not math.isfinite(float(exact)) or abs(float(exact - value)) > 1e-7:
            raise ValueError()
        return exact
    except (ValueError, OverflowError, ZeroDivisionError) as exc:
        raise ValidationError("Inconsistent rational timestamp: " + field) from exc


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def _load(path):
    requested = Path(path).expanduser().absolute()
    try:
        source = requested.resolve(strict=True)
        before = source_state(source)
        content = source.read_bytes()
        def invalid_constant(value):
            raise ValidationError("Nonfinite JSON number: " + value)
        data = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                          parse_constant=invalid_constant)
        if (source_state(source) != before or requested.resolve(strict=True) != source):
            raise ValidationError("An input changed while it was being read.")
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValidationError("Could not read validation input " + str(requested) + ": " + str(exc)) from exc
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValidationError("Validation inputs require a JSON object with schema_version 1.")
    provenance = {"path": str(source), "requested_path": str(requested),
                  "sha256": hashlib.sha256(content).hexdigest()}
    return data, provenance, before


def _film_reference(data):
    value = data.get("film_reference")
    if not isinstance(value, dict):
        raise ValidationError("A film_reference with namespace and key is required.")
    return {field: _text(value.get(field), "film_reference." + field) for field in ("namespace", "key")}


def _shots(data):
    if data.get("artifact_kind") != "shot_segmentation":
        raise ValidationError("shots_path must identify an M3 shot_segmentation artifact.")
    identity = {"film_reference": _film_reference(data),
                "video_version_id": _text(data.get("video_version_id"), "video_version_id"),
                "segmentation_id": _text(data.get("segmentation_id"), "segmentation_id")}
    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        raise ValidationError("The segmentation requires explicit source and playback coverage.")
    ranges = {}
    for reference in ("source_seconds", "playback_seconds"):
        start = _coordinate(coverage, "start_" + reference)
        end = _coordinate(coverage, "end_" + reference)
        if end <= start:
            raise ValidationError("Segmentation coverage must have positive duration.")
        ranges[reference] = (start, end)
    source_range, playback_range = ranges["source_seconds"], ranges["playback_seconds"]
    if abs(float((source_range[0] - playback_range[0]) - (source_range[1] - playback_range[1]))) > 1e-7:
        raise ValidationError("Segmentation source/playback coordinates have inconsistent offsets.")
    if not isinstance(data.get("shots"), list) or not data["shots"]:
        raise ValidationError("The segmentation must contain a nonempty shots array.")
    raw = data.get("boundaries")
    if not isinstance(raw, list):
        raise ValidationError("The segmentation must contain a boundaries array.")
    points, ids, times = [], set(), {name: set() for name in ranges}
    for record in raw:
        if not isinstance(record, dict):
            raise ValidationError("Predicted boundaries must be objects.")
        boundary_id = _text(record.get("boundary_id"), "predicted boundary_id")
        if boundary_id in ids:
            raise ValidationError("Duplicate predicted boundary_id: " + boundary_id)
        ids.add(boundary_id)
        point = {"boundary_id": boundary_id, "raw": record}
        for name, (start, end) in ranges.items():
            coordinate = _coordinate(record, name)
            if not start < coordinate < end:
                raise ValidationError("Predicted cuts must be strictly inside segmentation coverage.")
            if coordinate in times[name]:
                raise ValidationError("Duplicate predicted boundary timestamp.")
            times[name].add(coordinate)
            point[name] = coordinate
        if abs(float((point["source_seconds"] - point["playback_seconds"])
                     - (source_range[0] - playback_range[0]))) > 1e-7:
            raise ValidationError("A predicted boundary has inconsistent source/playback coordinates.")
        points.append(point)
    return identity, ranges, points


def _unchanged(provenance, before):
    path = Path(provenance["path"])
    try:
        if (source_state(path) != before
                or Path(provenance["requested_path"]).resolve(strict=True) != path
                or hashlib.sha256(path.read_bytes()).hexdigest() != provenance["sha256"]):
            raise ValidationError("An input changed during validation; no run was published.")
    except OSError as exc:
        raise ValidationError("An input disappeared during validation; no run was published.") from exc


def _publish(output_dir, artifacts, *, kind, inputs, parameters, status):
    output = Path(output_dir).expanduser().absolute()
    run_id = str(uuid4())
    run = {"schema_version": 1, "artifact_kind": kind, "run_id": run_id,
           "status": status, "completed_at_utc": utc_now(), "software": software_provenance(),
           "inputs": inputs, "parameters": parameters,
           "outputs": {name: {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
                       for name, content in artifacts.items()}}
    artifacts["run.json"] = json_bytes(run)
    try:
        publish_bundle(output, artifacts)
    except (IngestError, OSError) as exc:
        raise ValidationError("Could not publish validation artifacts: " + str(exc)) from exc
    return run_id, str(output)


def prepare_boundary_reference_template(shots_path, output_dir):
    """Publish an unfilled reference form; copy identifiers/coverage, never cuts."""
    data, provenance, before = _load(shots_path)
    identity, ranges, _ = _shots(data)
    start, end = ranges["playback_seconds"]
    template = {
        "schema_version": 1, "artifact_kind": "boundary_reference",
        **identity,
        "annotation_set_id": None, "annotator": None, "annotation_method": None,
        "independent_of_predictions": False, "exhaustive_within_coverage": False,
        "time_reference": "playback_seconds",
        "coverage": {"start_seconds": float(start), "end_seconds": float(end),
                     "start_seconds_rational": str(start), "end_seconds_rational": str(end)},
        "boundaries": [], "excluded_intervals": [],
        "instructions": [
            "This is an unfilled template, not an annotation or a validation result.",
            "Choose annotation_set_id and annotator; set annotation_method to human, assistant or synthetic.",
            "Review the video independently of predicted cut locations, then declare independent_of_predictions=true.",
            "List every point cut in the declared [start_seconds,end_seconds) coverage before declaring exhaustive_within_coverage=true.",
            "Narrow coverage if only part of the interval was exhaustively reviewed; update or remove its rational fields when editing endpoints.",
            "Each boundary needs a unique boundary_id, numeric time_seconds and transition_type='cut'.",
            "Keep uncertain gradual transitions outside point-cut scoring through excluded_intervals with start_seconds, end_seconds and reason.",
            "Do not copy predicted boundaries into this form and describe them as an independent reference.",
            "A genuinely reviewed zero-cut interval may keep boundaries empty; its precision, recall and F1 remain undefined.",
        ],
    }
    _unchanged(provenance, before)
    run_id, directory = _publish(output_dir, {"boundary_reference_template.json": json_bytes(template)},
                                 kind="boundary_reference_template_run", inputs={"shots": provenance},
                                 parameters={"time_reference": "playback_seconds"}, status="template_only")
    return {"run_id": run_id, "output_directory": directory, "status": "template_only",
            "reference_template_path": str(Path(directory) / "boundary_reference_template.json"),
            "boundary_label_count": 0, **identity}


def _annotation(data, identity, ranges):
    if _film_reference(data) != identity["film_reference"]:
        raise ValidationError("Reference and segmentation film namespace/key do not match.")
    if data.get("video_version_id") != identity["video_version_id"]:
        raise ValidationError("Reference and segmentation video versions do not match.")
    annotation_id = _text(data.get("annotation_set_id"), "annotation_set_id")
    if annotation_id == identity["segmentation_id"]:
        raise ValidationError("annotation_set_id must identify an annotation set, not the segmentation.")
    annotator = _text(data.get("annotator"), "annotator")
    method = _text(data.get("annotation_method"), "annotation_method")
    if method not in {"human", "assistant", "synthetic"}:
        raise ValidationError("annotation_method must be human, assistant or synthetic.")
    if data.get("independent_of_predictions") is not True:
        raise ValidationError("An explicit independent_of_predictions=true declaration is required.")
    if data.get("exhaustive_within_coverage") is not True:
        raise ValidationError("An explicit exhaustive_within_coverage=true declaration is required.")
    reference = _text(data.get("time_reference"), "time_reference")
    if reference not in ranges:
        raise ValidationError("time_reference must be playback_seconds or source_seconds.")
    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        raise ValidationError("Reference coverage with start_seconds/end_seconds is mandatory.")
    start = _coordinate(coverage, "start_seconds")
    end = _coordinate(coverage, "end_seconds")
    lower, upper = ranges[reference]
    if not lower <= start < end <= upper:
        raise ValidationError("Reference coverage must be positive and contained in segmentation coverage.")
    exclusions = data.get("excluded_intervals", [])
    if not isinstance(exclusions, list):
        raise ValidationError("excluded_intervals must be an array.")
    intervals = []
    for interval in exclusions:
        if not isinstance(interval, dict):
            raise ValidationError("Each excluded interval must be an object.")
        first = _coordinate(interval, "start_seconds")
        last = _coordinate(interval, "end_seconds")
        if not start <= first < last <= end:
            raise ValidationError("Excluded intervals must lie within reference coverage.")
        intervals.append({"start": first, "end": last,
                          "reason": _text(interval.get("reason"), "excluded interval reason")})
    intervals.sort(key=lambda row: (row["start"], row["end"]))
    previous = start
    for interval in intervals:
        if interval["start"] < previous:
            raise ValidationError("Excluded intervals must not overlap.")
        previous = interval["end"]
    if sum((row["end"] - row["start"] for row in intervals), Fraction(0)) >= end - start:
        raise ValidationError("No evaluated coverage remains after excluded intervals.")
    labels = data.get("boundaries")
    if not isinstance(labels, list):
        raise ValidationError("Reference boundaries must be an array.")
    points, ids, times = [], set(), set()
    for label in labels:
        if not isinstance(label, dict):
            raise ValidationError("Each reference boundary must be an object.")
        boundary_id = _text(label.get("boundary_id"), "reference boundary_id")
        second = _coordinate(label, "time_seconds")
        if boundary_id in ids or second in times:
            raise ValidationError("Duplicate reference boundary ID or timestamp.")
        ids.add(boundary_id)
        times.add(second)
        if label.get("transition_type") != "cut":
            raise ValidationError("Only point cuts may be reference boundaries; use excluded_intervals for uncertain gradual transitions.")
        if not start <= second < end:
            raise ValidationError("A reference boundary is outside declared [start,end) coverage.")
        if _excluded(second, intervals) is not None:
            raise ValidationError("A reference boundary lies inside an excluded interval.")
        points.append({"boundary_id": boundary_id, "time": second})
    details = {"annotation_set_id": annotation_id, "annotator": annotator,
               "annotation_method": method, "independent_of_predictions": True,
               "exhaustive_within_coverage": True}
    return details, reference, (start, end), intervals, points


def _excluded(second, intervals):
    return next((row for row in intervals if row["start"] <= second < row["end"]), None)


def _point(point):
    return {"boundary_id": point["boundary_id"], "time_seconds": float(point["time"]),
            "time_seconds_rational": str(point["time"])}


def _csv(rows, fields, identity, annotation):
    stream = io.StringIO(newline="")
    provenance = {"film_namespace": identity["film_reference"]["namespace"],
                  "film_key": identity["film_reference"]["key"],
                  "video_version_id": identity["video_version_id"],
                  "segmentation_id": identity["segmentation_id"],
                  "annotation_set_id": annotation["annotation_set_id"],
                  "annotation_method": annotation["annotation_method"]}
    writer = csv.DictWriter(stream, fieldnames=[*provenance, *fields])
    writer.writeheader()
    writer.writerows({**provenance, **row} for row in rows)
    return stream.getvalue().encode("utf-8")


def validate_shots(shots_path, reference_path, output_dir, *, tolerance_seconds):
    """Score only exhaustive, independently declared point-cut reference coverage."""
    tolerance = _number(tolerance_seconds, "tolerance_seconds")
    if tolerance <= 0:
        raise ValidationError("tolerance_seconds must be explicitly positive.")
    shots, shots_input, shots_before = _load(shots_path)
    reference, reference_input, reference_before = _load(reference_path)
    identity, ranges, predictions = _shots(shots)
    annotation, coordinate, (start, end), exclusions, labels = _annotation(reference, identity, ranges)
    active, excluded, outside = [], [], []
    for predicted in predictions:
        point = {"boundary_id": predicted["boundary_id"], "time": predicted[coordinate]}
        if not start <= point["time"] < end:
            outside.append(_point(point))
        else:
            interval = _excluded(point["time"], exclusions)
            if interval is None:
                active.append(point)
            else:
                excluded.append({**_point(point), "exclusion_reason": interval["reason"],
                                 "excluded_interval_start_seconds": float(interval["start"]),
                                 "excluded_interval_end_seconds": float(interval["end"])})
    ordering = lambda point: (point["time"], point["boundary_id"])
    active.sort(key=ordering)
    labels.sort(key=ordering)
    matches, missed, false_positive, errors = [], [], [], []
    predicted_index = reference_index = 0
    while predicted_index < len(active) and reference_index < len(labels):
        predicted, label = active[predicted_index], labels[reference_index]
        difference = predicted["time"] - label["time"]
        if abs(difference) <= tolerance:
            matches.append({"prediction_boundary_id": predicted["boundary_id"],
                            "reference_boundary_id": label["boundary_id"],
                            "prediction_time_seconds": float(predicted["time"]),
                            "prediction_time_seconds_rational": str(predicted["time"]),
                            "reference_time_seconds": float(label["time"]),
                            "reference_time_seconds_rational": str(label["time"]),
                            "signed_error_seconds": float(difference),
                            "signed_error_seconds_rational": str(difference),
                            "absolute_error_seconds": float(abs(difference))})
            errors.append(difference)
            predicted_index += 1
            reference_index += 1
        elif difference < 0:
            false_positive.append(_point(predicted))
            predicted_index += 1
        else:
            missed.append(_point(label))
            reference_index += 1
    false_positive.extend(_point(point) for point in active[predicted_index:])
    missed.extend(_point(point) for point in labels[reference_index:])
    tp, fp, fn = len(matches), len(false_positive), len(missed)
    if labels:
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn)
        f1 = 2 * tp / (2 * tp + fp + fn)
    else:
        precision = recall = f1 = None
    warnings = []
    if not labels:
        warnings.append("no_reference_cut_events; precision_recall_f1_undefined")
    if reference.get("segmentation_id") not in (None, identity["segmentation_id"]):
        warnings.append("reference_mentions_a_different_segmentation_id; film_and_video_identity_match")
    method = annotation["annotation_method"]
    if method != "human":
        warnings.append("synthetic_test_only" if method == "synthetic" else "assistant_reference_not_human_validation")
    signed_mean = sum(errors, Fraction(0)) / len(errors) if errors else None
    absolute_mean = sum((abs(error) for error in errors), Fraction(0)) / len(errors) if errors else None
    validation_id = str(uuid4())
    result = {
        "schema_version": 1, "artifact_kind": "shot_boundary_validation", "validation_id": validation_id,
        **identity, "annotation": annotation, "time_reference": coordinate,
        "coverage": {"start_seconds": float(start), "end_seconds": float(end),
                     "start_seconds_rational": str(start), "end_seconds_rational": str(end),
                     "interval_convention": "[start,end)",
                     "evaluated_seconds": float(end - start - sum(
                         (interval["end"] - interval["start"] for interval in exclusions), Fraction(0)))},
        "excluded_intervals": [{"start_seconds": float(row["start"]), "end_seconds": float(row["end"]),
                                "reason": row["reason"]} for row in exclusions],
        "tolerance_seconds": float(tolerance), "tolerance_seconds_rational": str(tolerance),
        "matching_policy": MATCHING_POLICY,
        "counts": {"true_positive": tp, "false_positive": fp, "false_negative": fn,
                   "reference_boundaries": len(labels), "scored_predictions": len(active),
                   "excluded_predictions": len(excluded), "outside_reference_coverage_predictions": len(outside),
                   "all_segmentation_predictions": len(predictions)},
        "metrics": {"precision": precision, "recall": recall, "f1": f1},
        "timing_errors": {"sign_convention": "prediction_minus_reference",
                          "mean_signed_seconds": float(signed_mean) if signed_mean is not None else None,
                          "mean_absolute_seconds": float(absolute_mean) if absolute_mean is not None else None,
                          "maximum_absolute_seconds": float(max(map(abs, errors))) if errors else None},
        "matches": matches, "missed": missed, "false_positive": false_positive,
        "excluded_predictions": excluded, "outside_reference_coverage_predictions": outside,
        "inputs": {"shots": shots_input, "reference": reference_input}, "warnings": warnings,
        "limitations": [
            "Results apply only to the supplied reference coverage after excluded intervals; they do not validate the entire film or corpus.",
            "Point-cut scoring does not assess gradual transitions, narrative segmentation, shot scale or film form.",
            "Independence and exhaustive annotation are declared by the reference author; this tool cannot verify those working conditions.",
            "Chronological greedy pairing is deterministic but does not minimize timing error among alternative valid pairings.",
            "Predictions outside review coverage remain unscored even when within tolerance of a label near its edge; use review margins accordingly.",
            "An assistant or synthetic reference is explicitly distinguished from human annotation.",
            "No p-values, theoretical montage classifications or interpretive validity claims are produced.",
        ],
    }
    match_fields = ["prediction_boundary_id", "reference_boundary_id", "prediction_time_seconds",
                    "prediction_time_seconds_rational", "reference_time_seconds", "reference_time_seconds_rational",
                    "signed_error_seconds", "signed_error_seconds_rational", "absolute_error_seconds"]
    point_fields = ["boundary_id", "time_seconds", "time_seconds_rational"]
    artifacts = {"validation.json": json_bytes(result),
                 "matches.csv": _csv(matches, match_fields, identity, annotation),
                 "missed.csv": _csv(missed, point_fields, identity, annotation),
                 "false_positive.csv": _csv(false_positive, point_fields, identity, annotation)}
    _unchanged(shots_input, shots_before)
    _unchanged(reference_input, reference_before)
    run_id, directory = _publish(output_dir, artifacts, kind="shot_boundary_validation_run",
                                 inputs=result["inputs"], parameters={"tolerance_seconds": float(tolerance),
                                 "time_reference": coordinate, "matching_policy": MATCHING_POLICY},
                                 status="comparison_complete" if labels else "no_reference_cut_events")
    return {"run_id": run_id, "validation_id": validation_id, "output_directory": directory,
            "annotation_method": method, "counts": result["counts"], "metrics": result["metrics"],
            "warnings": warnings, **identity}
