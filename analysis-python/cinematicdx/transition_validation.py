"""Pure, exhaustive-coverage localization checks for interval transition proposals.

No media/model access, annotation changes, output writes, threshold selection or
point-to-interval fabrication occurs here. Localization ignores predicted type;
type confusion is a separate diagnostic conditional on localized matches.
"""

import math
from collections import Counter
from fractions import Fraction


class TransitionValidationError(ValueError):
    """Missing provenance or invalid intervals cannot establish evaluation results."""


MAX_REFERENCE_INTERVALS = 16
_TYPE_ALIASES = {
    "淡出": "fade_out", "fade_out": "fade_out", "fade-out": "fade_out", "fade out": "fade_out",
    "淡入": "fade_in", "fade_in": "fade_in", "fade-in": "fade_in", "fade in": "fade_in",
    "叠化": "dissolve", "溶解": "dissolve", "dissolve": "dissolve", "crossfade": "dissolve",
    "其他渐变": "other_gradual", "other_gradual": "other_gradual",
    "不确定": "unknown", "unknown": "unknown", "unclassified": "unknown",
    "硬切": "hard_cut", "cut": "hard_cut", "hard_cut": "hard_cut", "hard-cut": "hard_cut",
}


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise TransitionValidationError(name + " must be nonempty text.")
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransitionValidationError(name + " must be a finite number.")
    try:
        if not math.isfinite(float(value)):
            raise ValueError()
        return Fraction(str(value))
    except (ValueError, OverflowError) as exc:
        raise TransitionValidationError(name + " must be a finite number.") from exc


def _time(record, name):
    number = _number(record.get(name), name)
    raw = record.get(name + "_rational")
    if raw is None:
        return number
    try:
        if not isinstance(raw, str):
            raise ValueError()
        exact = Fraction(raw)
        if not math.isfinite(float(exact)) or abs(float(exact - number)) > 1e-7:
            raise ValueError()
        return exact
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise TransitionValidationError("Invalid or inconsistent rational time: " + name) from exc


def _identity(document):
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise TransitionValidationError("Each input must be a schema_version 1 object.")
    reference = document.get("film_reference")
    if not isinstance(reference, dict):
        raise TransitionValidationError("film_reference with namespace/key is required.")
    return {"film_reference": {name: _text(reference.get(name), "film_reference." + name)
                               for name in ("namespace", "key")},
            "video_version_id": _text(document.get("video_version_id"), "video_version_id")}


def _coverage(document):
    coverage = document.get("coverage")
    if not isinstance(coverage, dict):
        raise TransitionValidationError("Explicit full evaluation coverage is required.")
    if coverage.get("time_reference", "playback_seconds") != "playback_seconds":
        raise TransitionValidationError("Coverage must use playback_seconds.")
    start, end = _time(coverage, "start_seconds"), _time(coverage, "end_seconds")
    if start < 0 or end <= start:
        raise TransitionValidationError("Coverage must be nonnegative and have positive duration.")
    return start, end


def _kind(value):
    return _TYPE_ALIASES.get(value.strip().casefold(), value.strip().casefold())


def _interval(record, id_name, kind_name):
    if not isinstance(record, dict):
        raise TransitionValidationError("Every interval must be an object.")
    identifier = _text(record.get(id_name), id_name)
    first, last = _time(record, "start_playback_seconds"), _time(record, "end_playback_seconds")
    if last <= first:
        raise TransitionValidationError("Transition intervals must have strictly positive duration; points are not gradual intervals.")
    raw_type = _text(record.get(kind_name), kind_name)
    score = record.get("score")
    if score is not None:
        _number(score, "score")
    return {"id": identifier, "start": first, "end": last,
            "raw_start": first, "raw_end": last, "type": _kind(raw_type),
            "raw_type": raw_type, "score": score}


def _predictions(document, coverage):
    prediction_set = _text(document.get("prediction_set_id"), "prediction_set_id")
    if document.get("search_complete_within_coverage") is not True:
        raise TransitionValidationError("search_complete_within_coverage=true is required; label-neighborhood-only searches cannot be evaluated.")
    if document.get("search_scope", "entire_declared_coverage") != "entire_declared_coverage":
        raise TransitionValidationError("Only entire_declared_coverage searches can be scored.")
    records = document.get("predictions")
    if not isinstance(records, list):
        raise TransitionValidationError("An interval predictions array is required; point cuts are not valid gradual predictions.")
    start, end = coverage
    active, outside, seen = [], [], set()
    for record in records:
        interval = _interval(record, "transition_id", "predicted_type")
        if interval["id"] in seen:
            raise TransitionValidationError("Duplicate prediction transition_id: " + interval["id"])
        seen.add(interval["id"])
        if interval["end"] <= start or interval["start"] >= end:
            interval["status"] = "outside_evaluation_coverage"
            outside.append(interval)
            continue
        interval["start"] = max(start, interval["start"])
        interval["end"] = min(end, interval["end"])
        interval["left_clipped"] = interval["raw_start"] < start
        interval["right_clipped"] = interval["raw_end"] > end
        interval["status"] = "clipped_to_evaluation_coverage" if interval["left_clipped"] or interval["right_clipped"] else "within_evaluation_coverage"
        active.append(interval)
    order = lambda row: (row["start"], row["end"], row["id"])
    return prediction_set, sorted(active, key=order), sorted(outside, key=order)


def _references(document, coverage):
    if document.get("annotation_method") != "human":
        raise TransitionValidationError("The gradual reference must declare human annotation_method.")
    if document.get("independent_of_predictions") is not True or document.get("exhaustive_within_coverage") is not True:
        raise TransitionValidationError("Reference independence and exhaustive coverage must both be explicitly true.")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise TransitionValidationError("Reference scenarios are required.")
    start, end = coverage
    results, scenario_ids = [], set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise TransitionValidationError("Each reference scenario must be an object.")
        scenario_id = _text(scenario.get("scenario_id"), "scenario_id")
        if scenario_id in scenario_ids:
            raise TransitionValidationError("Duplicate scenario_id: " + scenario_id)
        scenario_ids.add(scenario_id)
        if scenario.get("frame_base") is not None and (type(scenario["frame_base"]) is not int or scenario["frame_base"] not in (0, 1)):
            raise TransitionValidationError("frame_base must be 0, 1 or null when supplied.")
        records = scenario.get("gradual_transitions")
        hard = scenario.get("hard_cuts")
        if not isinstance(records, list) or not isinstance(hard, list):
            raise TransitionValidationError("Each scenario needs gradual_transitions and hard_cuts arrays.")
        if len(records) > MAX_REFERENCE_INTERVALS:
            raise TransitionValidationError("The exact bitmask evaluator supports at most %d reference intervals per scenario." % MAX_REFERENCE_INTERVALS)
        intervals, ids, spans = [], set(), set()
        for record in records:
            interval = _interval(record, "transition_id", "transition_type")
            if interval["type"] == "hard_cut":
                raise TransitionValidationError("A hard-cut reference point cannot be a gradual reference interval.")
            span = (interval["start"], interval["end"])
            if interval["id"] in ids or span in spans:
                raise TransitionValidationError("Duplicate reference transition ID or interval.")
            if not start <= interval["start"] < interval["end"] <= end:
                raise TransitionValidationError("Reference intervals must lie entirely within declared coverage.")
            ids.add(interval["id"])
            spans.add(span)
            intervals.append(interval)
        cuts, cut_ids, cut_times = [], set(), set()
        for record in hard:
            if not isinstance(record, dict):
                raise TransitionValidationError("Hard-cut confounds must be objects.")
            cut_id = _text(record.get("cut_id"), "cut_id")
            second = _time(record, "playback_seconds")
            if cut_id in cut_ids or second in cut_times or cut_id in ids:
                raise TransitionValidationError("Duplicate hard-cut ID/time or ID shared with a gradual reference.")
            if not start <= second < end:
                raise TransitionValidationError("Hard-cut confounds must be within declared coverage; store outside observations separately.")
            cut_ids.add(cut_id)
            cut_times.add(second)
            cuts.append({"cut_id": cut_id, "time": second})
        results.append({"scenario_id": scenario_id, "frame_base": scenario.get("frame_base"),
                        "time_basis_confirmed": scenario.get("time_basis_confirmed") is True,
                        "time_basis_description": scenario.get("time_basis_description"),
                        "references": sorted(intervals, key=lambda row: (row["start"], row["end"], row["id"])),
                        "hard_cuts": sorted(cuts, key=lambda row: (row["time"], row["cut_id"]))})
    return results


def _public(interval):
    return {"transition_id": interval["id"],
            "start_playback_seconds": float(interval["start"]),
            "end_playback_seconds": float(interval["end"]),
            "start_playback_seconds_rational": str(interval["start"]),
            "end_playback_seconds_rational": str(interval["end"]),
            "raw_start_playback_seconds": float(interval["raw_start"]),
            "raw_end_playback_seconds": float(interval["raw_end"]),
            "type": interval["type"], "raw_type": interval["raw_type"],
            "score": interval["score"], "status": interval.get("status", "reference"),
            "left_clipped": interval.get("left_clipped", False),
            "right_clipped": interval.get("right_clipped", False)}


def _overlap(prediction, reference):
    intersection = max(Fraction(0), min(prediction["end"], reference["end"]) - max(prediction["start"], reference["start"]))
    union = prediction["end"] - prediction["start"] + reference["end"] - reference["start"] - intersection
    return intersection / union, intersection / (reference["end"] - reference["start"])


def _matching(predictions, references, threshold):
    """Exact objective: cardinality first, rational total tIoU second, stable IDs last."""
    edges = {(p, r): _overlap(prediction, reference) for p, prediction in enumerate(predictions)
             for r, reference in enumerate(references)}
    # mask -> (rational overlap sum, ordered assignment tuples). Processing each
    # prediction once prevents one broad proposal from satisfying several labels.
    states = {0: (Fraction(0), ())}
    for p in range(len(predictions)):
        updated = dict(states)
        for mask, (total, assignments) in states.items():
            for r in range(len(references)):
                tiou, _ = edges[p, r]
                if mask & (1 << r) or tiou < threshold:
                    continue
                new_mask = mask | (1 << r)
                candidate = (total + tiou, assignments + ((p, r),))
                existing = updated.get(new_mask)
                if existing is None or candidate[0] > existing[0] or (candidate[0] == existing[0] and candidate[1] < existing[1]):
                    updated[new_mask] = candidate
        states = updated
    winner = min(states, key=lambda mask: (-mask.bit_count(), -states[mask][0], states[mask][1]))
    return states[winner][1], edges, states[winner][0]


def validate_gradual_transitions(prediction_document, manual_reference_scenarios, *, iou_threshold=0.5):
    """Evaluate every local interval proposal against every supplied reference scenario.

    Caller owns receipts/file I/O. Threshold must be predefined; call separately
    at 0.3/0.5/0.75 without choosing the best (0.5 is the primary default).
    Partial boundary proposals are scored
    on their local clipped support and explicitly retain their original bounds.
    """
    identity = _identity(prediction_document)
    if _identity(manual_reference_scenarios) != identity:
        raise TransitionValidationError("Prediction/reference film or exact video identity mismatch.")
    coverage = _coverage(manual_reference_scenarios)
    if _coverage(prediction_document) != coverage:
        raise TransitionValidationError("Prediction search coverage must equal the entire reference coverage.")
    threshold = _number(iou_threshold, "iou_threshold")
    if not 0 < threshold <= 1:
        raise TransitionValidationError("iou_threshold must be in (0,1].")
    prediction_set, predictions, outside = _predictions(prediction_document, coverage)
    scenarios = _references(manual_reference_scenarios, coverage)
    results = []
    for scenario in scenarios:
        refs = scenario["references"]
        assignments, edges, total_tiou = _matching(predictions, refs, threshold)
        matched_predictions = {p for p, _ in assignments}
        matched_refs = {r for _, r in assignments}
        matches, start_errors, end_errors, raw_start_errors, raw_end_errors = [], [], [], [], []
        confusion = Counter()
        for p, r in sorted(assignments, key=lambda pair: (refs[pair[1]]["start"], refs[pair[1]]["id"], predictions[pair[0]]["id"])):
            predicted, reference = predictions[p], refs[r]
            tiou, ior = edges[p, r]
            first_error, last_error = predicted["start"] - reference["start"], predicted["end"] - reference["end"]
            raw_first, raw_last = predicted["raw_start"] - reference["start"], predicted["raw_end"] - reference["end"]
            start_errors.append(abs(first_error)); end_errors.append(abs(last_error))
            raw_start_errors.append(abs(raw_first)); raw_end_errors.append(abs(raw_last))
            correct_type = predicted["type"] == reference["type"]
            confusion[reference["type"], predicted["type"]] += 1
            matches.append({"prediction_id": predicted["id"], "reference_id": reference["id"],
                            "prediction": _public(predicted), "reference": _public(reference),
                            "temporal_iou": float(tiou), "temporal_iou_rational": str(tiou),
                            "intersection_over_reference": float(ior),
                            "start_error_seconds": float(first_error), "end_error_seconds": float(last_error),
                            "raw_start_error_seconds": float(raw_first), "raw_end_error_seconds": float(raw_last),
                            "localization_match": True, "type_correct": correct_type})
        tp, fp, fn = len(matches), len(predictions) - len(matches), len(refs) - len(matches)
        metrics = {"precision": tp / (tp + fp) if tp + fp and refs else None,
                   "recall": tp / (tp + fn) if refs else None,
                   "f1": 2 * tp / (2 * tp + fp + fn) if refs else None}
        mean = lambda values: float(sum(values, Fraction(0)) / len(values)) if values else None
        confounds = []
        for p, prediction in enumerate(predictions):
            contained = [{"cut_id": cut["cut_id"], "playback_seconds": float(cut["time"])}
                         for cut in scenario["hard_cuts"] if prediction["start"] <= cut["time"] < prediction["end"]]
            if contained:
                confounds.append({"prediction_id": prediction["id"], "localization_matched": p in matched_predictions,
                                  "contained_hard_cut_count": len(contained), "contained_manual_hard_cuts": contained})
        results.append({"scenario_id": scenario["scenario_id"], "frame_base": scenario["frame_base"],
                        "time_basis_confirmed": scenario["time_basis_confirmed"],
                        "counts": {"true_positive": tp, "false_positive": fp, "false_negative": fn,
                                   "scored_predictions": len(predictions), "reference_intervals": len(refs),
                                   "outside_coverage_predictions": len(outside)},
                        "localization_metrics": metrics,
                        "matching_objective": {"cardinality": tp, "total_temporal_iou": float(total_tiou),
                                               "total_temporal_iou_rational": str(total_tiou)},
                        "boundary_errors": {"basis": "scored clipped predictions minus reference; raw bounds also reported",
                                            "start_mae_seconds": mean(start_errors), "end_mae_seconds": mean(end_errors),
                                            "raw_start_mae_seconds": mean(raw_start_errors), "raw_end_mae_seconds": mean(raw_end_errors)},
                        "type_confusion": {"scope": "conditional on localization matches only; wrong types do not change localization TP",
                                           "correctly_typed_matches": sum(row["type_correct"] for row in matches),
                                           "type_accuracy_among_localized_matches": sum(row["type_correct"] for row in matches) / tp if tp else None,
                                           "cells": [{"reference_type": a, "predicted_type": b, "count": count}
                                                     for (a, b), count in sorted(confusion.items())]},
                        "matches": matches,
                        "false_positive": [_public(row) for p, row in enumerate(predictions) if p not in matched_predictions],
                        "missed": [_public(row) for r, row in enumerate(refs) if r not in matched_refs],
                        "hard_cut_confounds": {"diagnostic_only": True, "prediction_count_with_manual_hard_cut_inside": len(confounds),
                                               "unmatched_prediction_count_with_manual_hard_cut_inside": sum(not row["localization_matched"] for row in confounds),
                                               "predictions": confounds}})
    start, end = coverage
    return {"schema_version": 1, "artifact_kind": "gradual_transition_interval_validation", **identity,
            "prediction_set_id": prediction_set,
            "coverage": {"start_seconds": float(start), "end_seconds": float(end), "time_reference": "playback_seconds", "interval_convention": "[start,end)"},
            "search_complete_within_coverage": True, "iou_threshold": float(threshold),
            "matching_policy": {"algorithm": "exact bitmask bipartite dynamic programming", "one_to_one": True,
                                "objectives_in_order": ["maximum matched interval count", "maximum total rational temporal IoU", "deterministic sorted interval/index order"],
                                "threshold_inclusive": True, "type_used_for_localization_matching": False,
                                "score_used_for_localization_matching": False},
            "prediction_audit": {"input_count": len(prediction_document["predictions"]),
                                 "scored_count": len(predictions), "outside_count": len(outside),
                                 "clipped_count": sum(row["status"] == "clipped_to_evaluation_coverage" for row in predictions),
                                 "all_scored_predictions": [_public(row) for row in predictions],
                                 "outside_coverage_predictions": [_public(row) for row in outside]},
            "results": results,
            "limitations": [
                "Full-coverage processing and annotation independence/completeness are declarations; this evaluator cannot verify how proposals or labels were obtained.",
                "Every prediction with positive overlap with declared coverage is scored, including proposals far from every labelled interval; wholly outside proposals are separately listed.",
                "Clipped proposals have conditional local-support localization metrics; original bounds and raw boundary errors remain inspectable.",
                "Interval localization and transition-type classification are separate tasks; a wrong type can still localize a reference.",
                "Manual hard cuts inside a proposal are confound diagnostics, not proof of the cause of a false proposal.",
                "Frame-base alternatives and threshold sensitivities must remain separate; no best-scoring scenario is selected.",
                "These supplied references do not establish whole-film or cross-film validity; no additional research labels are created.",
            ]}


def point_near_span_diagnostic(point_document, manual_reference_scenarios, *, margin_seconds=0.0):
    """Describe point proximity to supplied spans without gradual-detection F1.

    ``points`` rows contain boundary_id and playback_seconds. Near means distance
    to the closed reported span is <= margin, including either reported endpoint.
    This explicitly differs from scoring interval overlap or transition type.
    """
    identity = _identity(point_document)
    if _identity(manual_reference_scenarios) != identity:
        raise TransitionValidationError("Point/reference film or video identity mismatch.")
    coverage = _coverage(manual_reference_scenarios)
    if _coverage(point_document) != coverage:
        raise TransitionValidationError("Point diagnostic coverage must equal reference coverage.")
    prediction_set = _text(point_document.get("prediction_set_id"), "prediction_set_id")
    if point_document.get("search_complete_within_coverage") is not True:
        raise TransitionValidationError("Point coverage must be declared fully processed.")
    if point_document.get("search_scope", "entire_declared_coverage") != "entire_declared_coverage":
        raise TransitionValidationError("A label-neighborhood search cannot establish point coverage over the full interval.")
    margin = _number(margin_seconds, "margin_seconds")
    if margin < 0:
        raise TransitionValidationError("margin_seconds must be nonnegative.")
    records = point_document.get("points")
    if not isinstance(records, list):
        raise TransitionValidationError("A points array is required for this non-F1 diagnostic.")
    start, end = coverage
    points, outside, ids = [], [], set()
    for record in records:
        if not isinstance(record, dict):
            raise TransitionValidationError("Point records must be objects.")
        identifier = _text(record.get("boundary_id"), "boundary_id")
        if identifier in ids:
            raise TransitionValidationError("Duplicate point boundary_id.")
        ids.add(identifier)
        second = _time(record, "playback_seconds")
        row = {"boundary_id": identifier, "time": second}
        (points if start <= second < end else outside).append(row)
    results = []
    for scenario in _references(manual_reference_scenarios, coverage):
        spans, near_ids = [], set()
        for reference in scenario["references"]:
            near = [row for row in points if max(reference["start"] - row["time"], row["time"] - reference["end"], Fraction(0)) <= margin]
            near_ids.update(row["boundary_id"] for row in near)
            spans.append({"reference": _public(reference),
                          "nearby_points": [{"boundary_id": row["boundary_id"], "playback_seconds": float(row["time"])} for row in near]})
        results.append({"scenario_id": scenario["scenario_id"], "frame_base": scenario["frame_base"],
                        "spans_with_any_nearby_point": sum(bool(row["nearby_points"]) for row in spans),
                        "nearby_point_count_unique": len(near_ids), "spans": spans})
    return {"schema_version": 1, "artifact_kind": "point_near_span_coverage_diagnostic", **identity,
            "prediction_set_id": prediction_set, "margin_seconds": float(margin),
            "point_count_within_coverage": len(points), "outside_coverage_point_count": len(outside),
            "definition": "distance from point to closed reported interval <= margin; not temporal IoU",
            "precision_recall_f1_computed": False, "is_gradual_detector_evaluation": False,
            "results": results,
            "limitation": "A point near a gradual interval does not identify its extent or type and is not an interval detection TP."}
