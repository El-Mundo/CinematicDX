"""Align independently supplied narrative intervals without inferring events.

Exploratory comparisons use distinct event onsets. Onsets at cut candidates are
matched to non-event cuts in the same third of the processed coverage. Windows
around all supplied onsets and already matched controls are excluded. Inside-shot
onsets retain their exact times and form a separate, unmatched stratum. All rates
exclude the anchor cut. No p-values, causal claims or automatic narrative labels
are produced.
"""

import csv
import hashlib
import io
import json
import math
from pathlib import Path
import random
from fractions import Fraction
from uuid import uuid4

from .ingest import json_bytes, publish_bundle, software_provenance, source_state, utc_now


class NarrativeError(ValueError):
    """Invalid or incompatible input cannot be turned into research evidence."""


EPSILON = 1e-6
CUT_TYPES = {"cut", "hard_cut", "unclassified_cut_candidate"}
HUMAN_REVIEW_STATUSES = {"human_reviewed", "human_verified"}
LIMITATIONS = [
    "Event labels and functions are supplied annotations, not inferred from visual measurements.",
    "Only event onsets are compared; adjacent event ends are not counted a second time.",
    "At-cut classification does not move or round the independently annotated onset.",
    "Matching uses the same third of the processed coverage, a declared pilot design choice.",
    "Controls exclude windows around every annotated onset and previously matched controls.",
    "Partial controls for unmatched onsets are diagnostic only; they are not reserved and may recur in a later matched unit.",
    "Inside-shot onsets are retained and reported separately, without matched cut controls.",
    "Greedy deterministic matching can leave events unmatched; no optimal matching is claimed.",
    "Contrasts are descriptive event-level diagnostics, with no p-values or causal interpretation.",
    "Unclassified cut candidates may supply provisional cutting rates; their predicted status is retained.",
    "Measurements and correspondences do not by themselves establish film form or narrative function.",
]


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise NarrativeError(name + " must be nonempty text.")
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NarrativeError(name + " must be a finite number.")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise NarrativeError(name + " must be a finite number.") from exc
    if not math.isfinite(result):
        raise NarrativeError(name + " must be a finite number.")
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NarrativeError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def _load(path):
    source = Path(path).expanduser().resolve(strict=True)
    before = source_state(source)
    content = source.read_bytes()
    def invalid_constant(value):
        raise NarrativeError("Nonfinite JSON number: " + value)
    try:
        data = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                          parse_constant=invalid_constant)
    except (UnicodeError, ValueError) as exc:
        raise NarrativeError("Invalid JSON input: " + str(source) + ": " + str(exc)) from exc
    if before != source_state(source):
        raise NarrativeError("An input changed while it was being read.")
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise NarrativeError("Input requires schema_version 1 and a JSON object.")
    return data, {"path": str(source), "sha256": hashlib.sha256(content).hexdigest()}, before


def _reference(data):
    reference = data.get("film_reference")
    if not isinstance(reference, dict):
        raise NarrativeError("A scoped film_reference is required.")
    return {key: _text(reference.get(key), "film_reference." + key) for key in ("namespace", "key")}


def _same(first, second, label, tolerance=EPSILON):
    if not math.isfinite(first) or not math.isfinite(second) or abs(first - second) > tolerance:
        raise NarrativeError("Inconsistent " + label + ".")


def _pts_check(record, prefix, source_seconds):
    pts = record.get(prefix + "pts")
    if type(pts) is not int:
        raise NarrativeError(prefix + "pts must be an integer.")
    try:
        time_base = Fraction(_text(record.get("time_base"), "time_base"))
    except (ValueError, ZeroDivisionError) as exc:
        raise NarrativeError("A valid rational time_base is required.") from exc
    if time_base <= 0:
        raise NarrativeError("time_base must be positive.")
    try:
        coordinate, tick = float(pts*time_base), float(time_base)
    except OverflowError as exc:
        raise NarrativeError("PTS and time_base exceed finite timestamp range.") from exc
    if not math.isfinite(coordinate) or not math.isfinite(tick) or tick <= 0:
        raise NarrativeError("PTS and time_base exceed finite timestamp range.")
    _same(coordinate, source_seconds, "PTS and source seconds", max(tick, EPSILON))


def _validate_shots(data):
    _reference(data)
    _text(data.get("video_version_id"), "video_version_id")
    _text(data.get("segmentation_id"), "segmentation_id")
    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        raise NarrativeError("Shot coverage is required.")
    values = {key: _number(coverage.get(key), "coverage." + key) for key in (
        "start_source_seconds", "end_source_seconds", "start_playback_seconds", "end_playback_seconds")}
    start, end = values["start_source_seconds"], values["end_source_seconds"]
    if end <= start:
        raise NarrativeError("Shot coverage must have positive duration.")
    offset = start - values["start_playback_seconds"]
    _same(end - values["end_playback_seconds"], offset, "coverage coordinate offset")
    shots, boundaries = data.get("shots"), data.get("boundaries")
    if not isinstance(shots, list) or not shots or not isinstance(boundaries, list):
        raise NarrativeError("Nonempty shots and a boundaries array are required.")
    seen = set()
    previous = start
    for shot in shots:
        if not isinstance(shot, dict):
            raise NarrativeError("Each shot must be an object.")
        shot_id = _text(shot.get("shot_id"), "shot_id")
        if shot_id in seen:
            raise NarrativeError("Duplicate shot_id: " + shot_id)
        seen.add(shot_id)
        first = _number(shot.get("start_source_seconds"), "shot start_source_seconds")
        last = _number(shot.get("end_source_seconds"), "shot end_source_seconds")
        duration = _number(shot.get("duration_seconds"), "shot duration_seconds")
        if last <= first or duration <= 0:
            raise NarrativeError("Shot durations must be positive.")
        _same(first, previous, "contiguous shot coverage")
        _same(last - first, duration, "shot duration")
        for prefix, coordinate in (("start_", first), ("end_", last)):
            _same(coordinate - _number(shot.get(prefix + "playback_seconds"), prefix + "playback_seconds"),
                  offset, "shot coordinate offset")
            _pts_check(shot, prefix, coordinate)
        if shot["end_pts"] <= shot["start_pts"]:
            raise NarrativeError("Shot end_pts must follow start_pts.")
        previous = last
    _same(previous, end, "last shot and coverage end")
    if len(boundaries) != len(shots) - 1:
        raise NarrativeError("Shot boundary count must equal the number of inter-shot joins.")
    seen = set()
    for boundary, following in zip(boundaries, shots[1:]):
        if not isinstance(boundary, dict):
            raise NarrativeError("Each boundary must be an object.")
        boundary_id = _text(boundary.get("boundary_id"), "boundary_id")
        if boundary_id in seen:
            raise NarrativeError("Duplicate boundary_id: " + boundary_id)
        seen.add(boundary_id)
        second = _number(boundary.get("source_seconds"), "boundary source_seconds")
        _same(second, following["start_source_seconds"], "boundary and following shot start")
        _same(second - _number(boundary.get("playback_seconds"), "boundary playback_seconds"),
              offset, "boundary coordinate offset")
        _pts_check(boundary, "", second)
        _text(boundary.get("transition_type"), "transition_type")
        for field in ("adjacent_frame_duration_seconds", "local_frame_interval_seconds"):
            if boundary.get(field) is not None and _number(boundary[field], field) <= 0:
                raise NarrativeError(field + " must be positive when supplied.")
    return start, end, offset


def _validate_annotations(data, shots, start, end, offset):
    if _reference(data) != _reference(shots):
        raise NarrativeError("Annotation film_reference does not match the shots.")
    if _text(data.get("video_version_id"), "video_version_id") != shots["video_version_id"]:
        raise NarrativeError("Annotation video_version_id does not match the exact source version.")
    _text(data.get("annotation_set_id"), "annotation_set_id")
    _text(data.get("annotator"), "annotator")
    if data.get("annotation_method") not in ("human", "assistant", "synthetic"):
        raise NarrativeError("annotation_method must explicitly be human, assistant or synthetic.")
    reference = data.get("time_reference")
    if reference not in ("playback_seconds", "source_seconds"):
        raise NarrativeError("An explicit source_seconds or playback_seconds time_reference is required.")
    if data.get("independent_of_visual_measurements") is not None and type(data["independent_of_visual_measurements"]) is not bool:
        raise NarrativeError("independent_of_visual_measurements must be a boolean or null.")
    events = data.get("events")
    if not isinstance(events, list) or not events:
        raise NarrativeError("No narrative events supplied; complete an independent annotation set first.")
    normalized, seen = [], set()
    for event in events:
        if not isinstance(event, dict):
            raise NarrativeError("Each event must be an object.")
        event_id = _text(event.get("event_id"), "event_id")
        if event_id in seen:
            raise NarrativeError("Duplicate event_id: " + event_id)
        seen.add(event_id)
        _text(event.get("label"), "event label")
        if event.get("certainty") not in ("certain", "uncertain"):
            raise NarrativeError("Every event needs explicit certain/uncertain certainty.")
        first = _number(event.get("start_seconds"), "event start_seconds")
        last = _number(event.get("end_seconds"), "event end_seconds")
        if last <= first:
            raise NarrativeError("Event durations must be positive.")
        source_first = first + offset if reference == "playback_seconds" else first
        source_last = last + offset if reference == "playback_seconds" else last
        if (source_first < start - EPSILON or source_last > end + EPSILON
                or source_first >= end or source_last <= start):
            raise NarrativeError("Event lies outside processed shot coverage: " + event_id)
        normalized.append(dict(event, start_source_seconds=source_first, end_source_seconds=source_last,
                               start_playback_seconds=source_first - offset, end_playback_seconds=source_last - offset))
    return sorted(normalized, key=lambda event: (event["start_source_seconds"], event["event_id"]))


def _csv_bytes(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False, allow_nan=False)
                         if isinstance(value, (dict, list)) else value for key, value in row.items()})
    return output.getvalue().encode("utf-8")


def _output_path(output_dir):
    output = Path(output_dir).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise NarrativeError("Output already exists; choose a new narrative run directory.")
    return output


def _publish(output, payloads, inputs, states, started, kind, parameters, run_id):
    for evidence, state in zip(inputs.values(), states):
        if source_state(evidence["path"]) != state:
            raise NarrativeError("An input changed; no narrative bundle was published.")
    run = {"schema_version": 1, "artifact_kind": kind, "run_id": run_id, "status": "complete",
           "started_at_utc": started, "completed_at_utc": utc_now(), "software": software_provenance(),
           "inputs": inputs, "parameters": parameters,
           "outputs": {name: {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
                       for name, content in payloads.items()}, "limitations": LIMITATIONS}
    payloads["run.json"] = json_bytes(run)
    publish_bundle(output, payloads)


def prepare_annotation_template(shots_path, output_dir):
    """Produce an explicitly empty, unusable-as-evidence annotation template."""
    output, started = _output_path(output_dir), utc_now()
    shots, source, state = _load(shots_path)
    _validate_shots(shots)
    run_id = str(uuid4())
    template = {"schema_version": 1, "film_reference": _reference(shots),
                "video_version_id": shots["video_version_id"],
                "annotation_set_id": str(uuid4()), "annotator": None, "annotation_method": None,
                "independent_of_visual_measurements": None, "time_reference": "playback_seconds",
                "annotation_status": "template_not_ready", "events": [],
                "guidance": {"coverage": shots["coverage"],
                    "required_event_fields": ["event_id", "start_seconds", "end_seconds", "label", "certainty"],
                    "optional_event_fields": ["location", "characters", "narrative_time", "notes"],
                    "instructions": ["Define events using a separate narrative annotation protocol before inspecting feature curves.",
                                     "Preserve starts and ends within shots; do not snap annotations to detected cuts.",
                                     "Record uncertainty and the actual human/assistant/synthetic annotation method.",
                                     "A year or narrative event is never inferred from shot metrics by this template."]}}
    summary = {"schema_version": 1, "status": "annotation_required", "run_id": run_id,
               "event_count": 0, "research_comparison_performed": False,
               "quality_flags": ["no_narrative_annotations", "template_not_research_evidence"],
               "film_reference": _reference(shots), "video_version_id": shots["video_version_id"],
               "segmentation_id": shots["segmentation_id"]}
    _publish(output, {"annotation_template.json": json_bytes(template), "summary.json": json_bytes(summary)},
             {"shots": source}, [state], started, "narrative_annotation_template_run", {}, run_id)
    return dict(summary, output_directory=str(output))


def _overlap(first, second):
    return min(first[1], second[1]) - max(first[0], second[0]) > EPSILON


def _rates(center, boundaries, anchor_id, start, end, window):
    before_duration = max(0, min(window, center-start))
    after_duration = max(0, min(window, end-center))
    before = sum(center - before_duration - EPSILON <= boundary["source_seconds"] < center-EPSILON
                 for boundary in boundaries if boundary["boundary_id"] != anchor_id)
    after = sum(center+EPSILON < boundary["source_seconds"] < center + after_duration-EPSILON
                for boundary in boundaries if boundary["boundary_id"] != anchor_id)
    before_rate = 60 * before / before_duration if before_duration > EPSILON else None
    after_rate = 60 * after / after_duration if after_duration > EPSILON else None
    return {"before_cut_count": before, "after_cut_count": after,
            "before_exposure_seconds": before_duration, "after_exposure_seconds": after_duration,
            "window_cutting_rate_per_minute": 60 * (before + after) / (before_duration + after_duration),
            "before_cutting_rate_per_minute": before_rate, "after_cutting_rate_per_minute": after_rate,
            "rate_change_per_minute": after_rate - before_rate if before_rate is not None and after_rate is not None else None}


def _boundary_match(second, boundaries, fallback):
    candidates = []
    for boundary in boundaries:
        tolerance = (boundary.get("adjacent_frame_duration_seconds") or
                     boundary.get("local_frame_interval_seconds") or fallback)
        distance = abs(second - boundary["source_seconds"])
        if distance <= tolerance + EPSILON:
            candidates.append((distance, boundary["boundary_id"], boundary, tolerance))
    return min(candidates, key=lambda item: (item[0], item[1]))[2:] if candidates else (None, fallback)


def align_narrative(shots_path, annotations_path, output_dir, *, window_seconds=30.0,
                    control_count=3, seed=0, boundary_tolerance_seconds=0.08):
    """Publish timestamp-preserving overlaps and exploratory, onset-level contrasts."""
    output, started = _output_path(output_dir), utc_now()
    window = _number(window_seconds, "window_seconds")
    fallback = _number(boundary_tolerance_seconds, "boundary_tolerance_seconds")
    if window <= 0 or fallback <= 0:
        raise NarrativeError("Window and fallback boundary tolerance must be positive.")
    if type(control_count) is not int or control_count <= 0 or type(seed) is not int:
        raise NarrativeError("control_count must be a positive integer and seed an integer.")
    shots, shots_evidence, shots_state = _load(shots_path)
    start, end, offset = _validate_shots(shots)
    annotations, annotation_evidence, annotation_state = _load(annotations_path)
    events = _validate_annotations(annotations, shots, start, end, offset)
    common = {"film_namespace": shots["film_reference"]["namespace"], "film_key": shots["film_reference"]["key"],
              "video_version_id": shots["video_version_id"], "segmentation_id": shots["segmentation_id"],
              "annotation_set_id": annotations["annotation_set_id"]}
    alignment = []
    for event in events:
        for shot in shots["shots"]:
            first = max(event["start_source_seconds"], shot["start_source_seconds"])
            last = min(event["end_source_seconds"], shot["end_source_seconds"])
            if last > first:
                alignment.append(dict(common, event_id=event["event_id"], event_label=event["label"],
                    certainty=event["certainty"], annotation_time_reference=annotations["time_reference"],
                    annotation_start_seconds=event["start_seconds"], annotation_end_seconds=event["end_seconds"],
                    event_start_source_seconds=event["start_source_seconds"], event_end_source_seconds=event["end_source_seconds"],
                    event_start_playback_seconds=event["start_playback_seconds"], event_end_playback_seconds=event["end_playback_seconds"],
                    shot_id=shot["shot_id"], overlap_start_source_seconds=first, overlap_end_source_seconds=last,
                    overlap_seconds=last-first, overlap_fraction_of_shot=(last-first)/shot["duration_seconds"],
                    overlap_fraction_of_event=(last-first)/(event["end_source_seconds"]-event["start_source_seconds"]),
                    location=event.get("location"), characters=event.get("characters"),
                    narrative_time=event.get("narrative_time"), notes=event.get("notes")))
    cuts = [boundary for boundary in shots["boundaries"] if boundary["transition_type"] in CUT_TYPES]
    onsets = []
    for event in events:
        if onsets and abs(onsets[-1]["second"] - event["start_source_seconds"]) <= EPSILON:
            onsets[-1]["events"].append(event)
        else:
            onsets.append({"second": event["start_source_seconds"], "events": [event]})
    event_windows = [(onset["second"]-window, onset["second"]+window) for onset in onsets]
    chosen_control_windows, rows = [], []
    fallback_used = any(not (cut.get("adjacent_frame_duration_seconds") or cut.get("local_frame_interval_seconds"))
                        for cut in cuts)
    rng = random.Random(seed)
    region = lambda second: min(2, max(0, int((second-start)/(end-start)*3)))
    for index, onset in enumerate(onsets):
        second, grouped = onset["second"], onset["events"]
        anchor, tolerance = _boundary_match(second, shots["boundaries"], fallback)
        position = ("coverage_start" if abs(second-start) <= EPSILON else
                    "at_cut" if anchor and anchor["transition_type"] in CUT_TYPES else
                    "at_transition" if anchor else "within_shot")
        if anchor and not (anchor.get("adjacent_frame_duration_seconds") or anchor.get("local_frame_interval_seconds")):
            fallback_used = True
        event_rates = _rates(second, cuts, anchor["boundary_id"] if anchor else None, start, end, window)
        reasons = []
        if position != "at_cut":
            reasons.append("within_shot_separate_stratum" if position == "within_shot" else
                           "non_cut_transition_separate_stratum" if position == "at_transition" else "coverage_start")
        if any(event["certainty"] == "uncertain" for event in grouped):
            reasons.append("uncertain_event_onset")
        if second-window < start-EPSILON or second+window > end+EPSILON:
            reasons.append("edge_truncated_window")
        if any(other != index and _overlap(event_windows[index], interval)
               for other, interval in enumerate(event_windows)):
            reasons.append("overlapping_event_windows")
        controls, staged_control_windows = [], []
        if not reasons:
            candidates = [boundary for boundary in cuts if region(boundary["source_seconds"]) == region(second)
                          and boundary["source_seconds"]-window >= start-EPSILON
                          and boundary["source_seconds"]+window <= end+EPSILON]
            rng.shuffle(candidates)
            for boundary in candidates:
                interval = (boundary["source_seconds"]-window, boundary["source_seconds"]+window)
                if any(_overlap(interval, excluded) for excluded in
                       event_windows+chosen_control_windows+staged_control_windows):
                    continue
                controls.append({"boundary_id": boundary["boundary_id"], "source_seconds": boundary["source_seconds"],
                                 "playback_seconds": boundary["source_seconds"]-offset,
                                 "transition_type": boundary["transition_type"],
                                 "validation_status": boundary.get("validation_status"),
                                 **_rates(boundary["source_seconds"], cuts, boundary["boundary_id"], start, end, window)})
                staged_control_windows.append(interval)
                if len(controls) == control_count:
                    break
            if len(controls) < control_count:
                reasons.append("insufficient_nonoverlapping_controls")
            else:
                chosen_control_windows.extend(staged_control_windows)
        controls_reserved = not reasons and len(controls) == control_count
        for control in controls:
            control["reserved_for_matched_analysis"] = controls_reserved
        control_rate = sum(control["window_cutting_rate_per_minute"] for control in controls)/len(controls) if controls else None
        control_change = sum(control["rate_change_per_minute"] for control in controls)/len(controls) if controls else None
        rows.append(dict(common, event_id=grouped[0]["event_id"], linked_event_ids=[event["event_id"] for event in grouped],
                    source_seconds=second, playback_seconds=second-offset, boundary_position=position,
                    matched_boundary_id=anchor["boundary_id"] if anchor else None,
                    matched_transition_type=anchor["transition_type"] if anchor else None,
                    matched_boundary_validation_status=anchor.get("validation_status") if anchor else None,
                    boundary_tolerance_seconds=tolerance, timeline_third=region(second)+1,
                    certainty="uncertain" if any(event["certainty"]=="uncertain" for event in grouped) else "certain",
                    **event_rates, control_count=len(controls), controls=controls,
                    controls_reserved_for_matched_analysis=controls_reserved,
                    control_mean_cutting_rate_per_minute=control_rate,
                    event_minus_control_rate_per_minute=event_rates["window_cutting_rate_per_minute"]-control_rate if control_rate is not None else None,
                    control_mean_rate_change_per_minute=control_change,
                    event_minus_control_rate_change_per_minute=event_rates["rate_change_per_minute"]-control_change
                        if control_change is not None and event_rates["rate_change_per_minute"] is not None else None,
                    comparison_status="exploratory_matched" if not reasons else "unmatched_or_excluded", reasons=reasons))
    flags = ["exploratory_only", "no_inferential_test"]
    human_shots = all(shot.get("validation_status") in HUMAN_REVIEW_STATUSES for shot in shots["shots"])
    human_boundaries = all(boundary.get("validation_status") in HUMAN_REVIEW_STATUSES for boundary in shots["boundaries"])
    if not (human_shots and human_boundaries):
        flags.append("shots_or_boundaries_not_human_reviewed")
    if annotations["annotation_method"] != "human":
        flags.append(annotations["annotation_method"] + "_annotations_not_human_ground_truth")
    if annotations.get("independent_of_visual_measurements") is not True:
        flags.append("annotation_independence_not_confirmed")
    annotation_ready = annotations.get("annotation_status") not in ("template_not_ready", "draft", "not_ready")
    if not annotation_ready:
        flags.append("annotations_declared_not_ready")
    if annotations.get("segmentation_id") is not None and annotations["segmentation_id"] != shots["segmentation_id"]:
        flags.append("annotation_provenance_refers_to_different_segmentation")
    if any(event["certainty"] == "uncertain" for event in events):
        flags.append("uncertain_narrative_annotations")
    if fallback_used:
        flags.append("boundary_tolerance_fallback_seconds_used")
    if any(boundary["transition_type"] not in CUT_TYPES for boundary in shots["boundaries"]):
        flags.append("non_cut_transitions_excluded_from_cutting_rates")
    if any(boundary["transition_type"] == "unclassified_cut_candidate" for boundary in shots["boundaries"]):
        flags.append("cutting_rates_use_unreviewed_cut_candidates")
    matched = [row for row in rows if row["comparison_status"] == "exploratory_matched"]
    if not matched:
        flags.append("no_eligible_matched_event_onsets")
    run_id = str(uuid4())
    parameters = {"window_seconds": window, "control_count": control_count, "seed": seed,
                  "fallback_boundary_tolerance_seconds": fallback, "timeline_region_count": 3,
                  "event_boundary_definition": "distinct_event_onsets", "anchor_cut_excluded": True,
                  "window_interval_convention": "[center-window,center+window); anchor excluded",
                  "control_allocation_policy": "chronological_event_onsets; greedy_seeded_shuffle; reserve_only_complete_matches",
                  "control_nonreuse_scope": "fully_matched_event_onsets_only"}
    summary = {"schema_version": 1, "artifact_kind": "narrative_alignment_summary", "run_id": run_id,
               "status": "exploratory", "film_reference": _reference(shots),
               "video_version_id": shots["video_version_id"], "segmentation_id": shots["segmentation_id"],
               "annotation_set_id": annotations["annotation_set_id"], "annotation_method": annotations["annotation_method"],
               "annotator": annotations["annotator"], "event_count": len(events), "distinct_onset_count": len(rows),
               "alignment_row_count": len(alignment), "matched_event_onset_count": len(matched),
               "within_shot_onset_count": sum(row["boundary_position"]=="within_shot" for row in rows),
               "at_transition_onset_count": sum(row["boundary_position"]=="at_transition" for row in rows),
               "quality_flags": sorted(flags), "parameters": parameters,
               "research_interpretation_status": "review_required" if annotations["annotation_method"]=="human"
                    and annotations.get("independent_of_visual_measurements") is True and annotation_ready
                    and human_shots and human_boundaries
                    else "blocked_pending_independent_human_annotations_and_shot_review",
               "mean_event_minus_control_rate_per_minute": sum(row["event_minus_control_rate_per_minute"] for row in matched)/len(matched) if matched else None,
               "mean_event_minus_control_rate_change_per_minute": sum(row["event_minus_control_rate_change_per_minute"] for row in matched)/len(matched) if matched else None,
               "matched_control_count": len(chosen_control_windows),
               "analysis_unit": "distinct_matched_event_onset_with_nonreused_controls", "p_value": None,
               "limitations": LIMITATIONS}
    alignment_fields = list(alignment[0])
    contrast_fields = list(rows[0])
    _publish(output, {"alignment.csv": _csv_bytes(alignment, alignment_fields),
                      "event_contrasts.csv": _csv_bytes(rows, contrast_fields), "summary.json": json_bytes(summary)},
             {"shots": shots_evidence, "annotations": annotation_evidence}, [shots_state, annotation_state],
             started, "narrative_alignment_run", parameters, run_id)
    return dict(summary, output_directory=str(output))
