"""Pure, local pilot calculations for the confirmed 150--750 second annotations.

This module never reads media, edits annotations, snaps an onset to a cut, selects
the best sensitivity scenario, or manufactures an endpoint for a censored event.
The fixed design is exploratory: +/-30 seconds is the primary comparison;
+/-15 and +/-10 seconds and common onset shifts of -1/0/+1 seconds are declared
sensitivities. Counts and exposure both exclude the central +/-1 second.
"""

import copy
import random

from .narrative import NarrativeError, _number, _reference, _text, _validate_shots


class PilotCompareError(ValueError):
    """The declared local pilot cannot be computed from these inputs."""


START, END = 150.0, 750.0
WINDOWS = (30.0, 15.0, 10.0)
JITTERS = (-1.0, 0.0, 1.0)
CENTRAL_EXCLUSION = 1.0
EPSILON = 1e-6
CUT_TYPES = {"cut", "hard_cut", "unclassified_cut_candidate"}
LIMITATIONS = [
    "This is an exploratory comparison of one independently annotated 600-second interval, not a preregistered confirmatory test.",
    "The primary +/-30-second design is retained even when overlapping event windows or absent controls make it unidentifiable.",
    "The +/-15 and +/-10-second windows and -1/0/+1-second common onset shifts are sensitivities, not a calibrated uncertainty distribution or confidence interval.",
    "Second-level narrative times are never snapped to cuts or assigned millisecond confidence; event-to-cut coincidence is not assessed.",
    "The central +/-1 second is removed from both event/control cut counts and exposure, including the control anchor cut.",
    "Controls are hard-cut positions in the same third of this interval, with full nonoverlapping windows outside every event window.",
    "Control allocation is chronological, seeded greedy matching, with no reuse within each scenario/window/jitter design; optimal matching is not claimed.",
    "Different frame-base scenarios remain separate conditional analyses; their timing correspondence is not thereby confirmed.",
    "Gradual transitions remain separate interval observations and are not counted as hard cuts.",
    "Right-censored observed event intervals do not create true event endpoints or additional event onsets.",
    "Automatic and manual cut counts are descriptive; they are not precision/recall estimates or interchangeable ground truth.",
    "Independence from automatic measurements does not establish that event definitions ignored visible transitions; correspondence can partly reflect the annotation protocol.",
    "The analysis unit is a distinct event onset; overlapping windows and sensitivity runs are not independent samples.",
    "No p-values, causal claims, corpus-wide laws or historically specific montage principles are inferred.",
]


def _finite(value, name):
    try:
        return _number(value, name)
    except NarrativeError as exc:
        raise PilotCompareError(str(exc)) from exc


def _coverage(data, name):
    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        raise PilotCompareError(name+" needs an explicit coverage object.")
    first = _finite(coverage.get("start_seconds"), name+" coverage start")
    last = _finite(coverage.get("end_seconds"), name+" coverage end")
    if abs(first-START) > EPSILON or abs(last-END) > EPSILON:
        raise PilotCompareError(name+" must declare exactly playback seconds 150--750.")


def _identity(data, expected, name):
    try:
        if _reference(data) != _reference(expected):
            raise PilotCompareError(name+" film_reference does not match.")
        if _text(data.get("video_version_id"), "video_version_id") != expected["video_version_id"]:
            raise PilotCompareError(name+" exact video_version_id does not match.")
    except NarrativeError as exc:
        raise PilotCompareError(str(exc)) from exc


def _prepare_events(annotations):
    _coverage(annotations, "Narrative annotations")
    if annotations.get("annotation_method") != "human":
        raise PilotCompareError("This pilot requires explicitly human narrative annotations.")
    if (annotations.get("independent_of_visual_measurements") is not True
            or annotations.get("exhaustive_within_coverage") is not True):
        raise PilotCompareError("Narrative independence and completeness must be explicitly confirmed for this interval.")
    if annotations.get("time_reference") != "playback_seconds":
        raise PilotCompareError("Narrative times must use full-film playback seconds.")
    events = annotations.get("events")
    if not isinstance(events, list) or not events:
        raise PilotCompareError("No annotated events supplied.")
    prepared, seen = [], set()
    for event in events:
        if not isinstance(event, dict):
            raise PilotCompareError("Each event must be an object.")
        event_id = _text(event.get("event_id"), "event_id")
        if event_id in seen:
            raise PilotCompareError("Duplicate event_id: "+event_id)
        seen.add(event_id)
        onset = _finite(event.get("start_seconds"), "event start_seconds")
        observed_start = _finite(event.get("observed_start_seconds", onset), "observed event start")
        if not START-EPSILON <= onset < END or not START-EPSILON <= observed_start < END:
            raise PilotCompareError("An event start lies outside the declared local interval: "+event_id)
        if abs(observed_start-onset) > EPSILON:
            raise PilotCompareError("Observed and supplied start differ; this pilot requires an explicit within-window onset or coverage-edge record.")
        true_end = event.get("end_seconds")
        censored = event.get("end_right_censored") is True
        if true_end is None:
            if not censored or event.get("observed_end_seconds") is None:
                raise PilotCompareError("A missing true end needs an explicit right-censoring declaration and observed end.")
            observed_end = _finite(event["observed_end_seconds"], "observed right-censored end")
            if abs(observed_end-END) > EPSILON:
                raise PilotCompareError("The right-censored observed end must be the declared window end, 750 seconds.")
        else:
            true_end = _finite(true_end, "true event end")
            if true_end <= onset:
                raise PilotCompareError("True event ends must follow their starts.")
            observed_end = _finite(event.get("observed_end_seconds", min(true_end, END)), "observed event end")
            if abs(observed_end-min(true_end, END)) > EPSILON or censored != (true_end > END):
                raise PilotCompareError("Observed end and right-censoring disagree with the supplied true end.")
        if not observed_start < observed_end <= END+EPSILON:
            raise PilotCompareError("Observed event intervals must have positive within-window duration.")
        if event.get("certainty") not in ("certain", "uncertain"):
            raise PilotCompareError("Every event needs explicit certain/uncertain certainty.")
        # Raw boundary-kind fields are intentionally neither read nor reinterpreted.
        prepared.append({"event_id": event_id, "label": event.get("label"),
                         "original_record": copy.deepcopy(event), "start_seconds": onset,
                         "true_end_seconds": true_end, "observed_start_seconds": observed_start,
                         "observed_end_seconds": observed_end, "end_right_censored": censored,
                         "coverage_edge_onset": abs(onset-START) <= EPSILON,
                         "certainty": event["certainty"]})
    return sorted(prepared, key=lambda event: (event["start_seconds"], event["event_id"]))


def _prepare_scenarios(reference):
    _coverage(reference, "Manual cut reference")
    if (reference.get("annotation_method") != "human"
            or reference.get("independent_of_predictions") is not True
            or reference.get("exhaustive_within_coverage") is not True):
        raise PilotCompareError("The manual reference requires human method and confirmed independence/completeness for 150--750.")
    scenarios = reference.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise PilotCompareError("Manual timing scenarios are required.")
    normalized, seen_scenarios = [], set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise PilotCompareError("Each timing scenario must be an object.")
        scenario_id = _text(scenario.get("scenario_id"), "scenario_id")
        if scenario_id in seen_scenarios:
            raise PilotCompareError("Duplicate manual timing scenario_id.")
        seen_scenarios.add(scenario_id)
        if not isinstance(scenario.get("hard_cuts"), list) or not isinstance(scenario.get("gradual_transitions"), list):
            raise PilotCompareError("Each scenario needs hard_cuts and gradual_transitions arrays.")
        cuts, gradual, outside = [], [], copy.deepcopy(scenario.get("outside_coverage_observations", []))
        if not isinstance(outside, list):
            raise PilotCompareError("outside_coverage_observations must be an array.")
        ids, times = set(), set()
        for cut in scenario["hard_cuts"]:
            if not isinstance(cut, dict):
                raise PilotCompareError("Each manual hard cut must be an object.")
            cut_id = _text(cut.get("cut_id"), "cut_id")
            second = _finite(cut.get("playback_seconds"), "manual cut playback_seconds")
            if cut_id in ids or second in times:
                raise PilotCompareError("Duplicate hard-cut ID or timestamp in one scenario.")
            ids.add(cut_id)
            times.add(second)
            if START <= second < END:
                cuts.append(dict(copy.deepcopy(cut), playback_seconds=second))
            else:
                outside.append(dict(copy.deepcopy(cut), exclusion_reason="outside_150_750"))
        ids = set()
        for transition in scenario["gradual_transitions"]:
            if not isinstance(transition, dict):
                raise PilotCompareError("Each gradual transition must be an object.")
            transition_id = _text(transition.get("transition_id"), "transition_id")
            first = _finite(transition.get("start_playback_seconds"), "gradual start")
            last = _finite(transition.get("end_playback_seconds"), "gradual end")
            if transition_id in ids or last <= first:
                raise PilotCompareError("Gradual transition IDs must be unique and intervals positive.")
            ids.add(transition_id)
            if min(last, END) > max(first, START):
                gradual.append(dict(copy.deepcopy(transition), observed_start_seconds=max(first, START),
                                    observed_end_seconds=min(last, END),
                                    left_censored=first < START, right_censored=last > END))
            else:
                outside.append(dict(copy.deepcopy(transition), exclusion_reason="outside_150_750"))
        normalized.append({"scenario_id": scenario_id,
                           "time_basis_description": scenario.get("time_basis_description"),
                           "time_basis_confirmed": scenario.get("time_basis_confirmed") is True,
                           "hard_cuts": sorted(cuts, key=lambda cut: (cut["playback_seconds"], cut["cut_id"])),
                           "gradual_transitions": gradual, "outside_coverage_observations": outside})
    return normalized


def _overlap(first, second):
    return min(first[1], second[1])-max(first[0], second[0]) > EPSILON


def _rates(center, cuts, window):
    """Half-open outer window, inclusive central exclusion, actual exposed seconds."""
    left, right = max(START, center-window), min(END, center+window)
    pre_end, post_start = min(END, center-CENTRAL_EXCLUSION), max(START, center+CENTRAL_EXCLUSION)
    pre_exposure = max(0.0, pre_end-left)
    post_exposure = max(0.0, right-post_start)
    before = sum(left-EPSILON <= cut["playback_seconds"] < pre_end-EPSILON for cut in cuts) if pre_exposure else 0
    after = sum(post_start+EPSILON < cut["playback_seconds"] < right-EPSILON for cut in cuts) if post_exposure else 0
    central = sum(max(START, center-CENTRAL_EXCLUSION)-EPSILON <= cut["playback_seconds"]
                  <= min(END, center+CENTRAL_EXCLUSION)+EPSILON for cut in cuts)
    before_rate = 60*before/pre_exposure if pre_exposure > EPSILON else None
    after_rate = 60*after/post_exposure if post_exposure > EPSILON else None
    return {"before_cut_count": before, "after_cut_count": after,
            "central_excluded_cut_count": central,
            "before_exposure_seconds": pre_exposure, "after_exposure_seconds": post_exposure,
            "before_cut_rate_per_minute": before_rate, "after_cut_rate_per_minute": after_rate,
            "rate_change_per_minute": after_rate-before_rate if before_rate is not None and after_rate is not None else None,
            "window_cut_rate_per_minute": 60*(before+after)/(pre_exposure+post_exposure)
                if pre_exposure+post_exposure > EPSILON else None}


def _onsets(events, jitter):
    result = []
    for event in events:
        original = event["start_seconds"]
        shifted = original if event["coverage_edge_onset"] else original+jitter
        if result and abs(result[-1]["original_seconds"]-original) <= EPSILON:
            result[-1]["events"].append(event)
        else:
            result.append({"original_seconds": original, "seconds": shifted, "events": [event]})
    return result


def _design(events, scenario, window, jitter):
    onsets = _onsets(events, jitter)
    event_windows = [(onset["seconds"]-window, onset["seconds"]+window) for onset in onsets]
    reserved, rows = [], []
    rng = random.Random(0)
    region = lambda second: min(2, max(0, int((second-START)/(END-START)*3)))
    cuts = scenario["hard_cuts"]
    for index, onset in enumerate(onsets):
        second, grouped = onset["seconds"], onset["events"]
        event_rates = _rates(second, cuts, window)
        reasons = []
        if grouped[0]["coverage_edge_onset"]:
            reasons.append("coverage_edge_onset_not_evaluated")
        if any(event["certainty"] == "uncertain" for event in grouped):
            reasons.append("uncertain_event_annotation")
        if second-window < START-EPSILON or second+window > END+EPSILON:
            reasons.append("full_window_outside_declared_coverage")
        if any(other != index and _overlap(event_windows[index], interval)
               for other, interval in enumerate(event_windows)):
            reasons.append("overlapping_event_windows")
        control = None
        if not reasons:
            candidates = [cut for cut in cuts if region(cut["playback_seconds"]) == region(second)
                          and cut["playback_seconds"]-window >= START-EPSILON
                          and cut["playback_seconds"]+window <= END+EPSILON]
            rng.shuffle(candidates)
            for candidate in candidates:
                interval = (candidate["playback_seconds"]-window, candidate["playback_seconds"]+window)
                if any(_overlap(interval, excluded) for excluded in event_windows+reserved):
                    continue
                control = {"cut_id": candidate["cut_id"], "playback_seconds": candidate["playback_seconds"],
                           **_rates(candidate["playback_seconds"], cuts, window)}
                reserved.append(interval)
                break
            if control is None:
                reasons.append("no_nonoverlapping_non_event_control_in_same_third")
        matched = control is not None and not reasons
        rows.append({"scenario_id": scenario["scenario_id"], "window_seconds": window,
            "jitter_seconds": jitter, "design_role": "primary" if window==30 and jitter==0 else "exploratory_sensitivity",
            "event_id": grouped[0]["event_id"], "linked_event_ids": [event["event_id"] for event in grouped],
            "label": grouped[0]["label"], "original_onset_seconds": onset["original_seconds"],
            "analysis_onset_seconds": second, "event_to_cut_relationship": "not_assessed_second_level_annotation",
            "coverage_edge_onset": grouped[0]["coverage_edge_onset"],
            "timeline_third": region(second)+1, "event_rates": event_rates, "control": control,
            "event_rate_change_per_minute": event_rates["rate_change_per_minute"],
            "control_rate_change_per_minute": control["rate_change_per_minute"] if control else None,
            "event_minus_control_rate_change_per_minute": event_rates["rate_change_per_minute"]-control["rate_change_per_minute"]
                if matched else None,
            "event_minus_control_window_rate_per_minute": event_rates["window_cut_rate_per_minute"]-control["window_cut_rate_per_minute"]
                if matched else None,
            "comparison_status": "exploratory_matched" if matched else "unmatched_or_excluded", "reasons": reasons})
    matched = [row for row in rows if row["comparison_status"] == "exploratory_matched"]
    summary = {"scenario_id": scenario["scenario_id"], "window_seconds": window, "jitter_seconds": jitter,
               "design_role": "primary" if window==30 and jitter==0 else "exploratory_sensitivity",
               "distinct_onset_count": len(rows), "matched_event_onset_count": len(matched),
               "unmatched_or_excluded_onset_count": len(rows)-len(matched),
               "mean_event_minus_control_rate_change_per_minute": sum(row["event_minus_control_rate_change_per_minute"] for row in matched)/len(matched) if matched else None,
               "mean_event_minus_control_window_rate_per_minute": sum(row["event_minus_control_window_rate_per_minute"] for row in matched)/len(matched) if matched else None,
               "status": "exploratory_matched_diagnostics" if matched else "no_identifiable_matched_comparison",
               "p_value": None}
    return rows, summary


def compute_pilot_comparison(annotations, shots, manual_reference):
    """Return JSON-ready diagnostics from dictionaries, without I/O or mutation.

    ``annotations`` is the confirmed narrative JSON: scoped film/version,
    coverage.start_seconds/end_seconds=150/750, explicit human independence and
    exhaustive_within_coverage, playback events with observed intervals and an
    explicit end_right_censored=True whenever true end_seconds is null.

    ``shots`` is the full M3 shots.json. ``manual_reference`` shares identity and
    coverage, declares human/independent_of_predictions/exhaustive_within_coverage,
    and supplies scenarios:[{scenario_id,time_basis_description,hard_cuts:
    [{cut_id,playback_seconds}],gradual_transitions:[{transition_id,
    start_playback_seconds,end_playback_seconds}]}]. Timing scenarios are never
    pooled or selected from the observed effects.
    """
    if not all(isinstance(value, dict) for value in (annotations, shots, manual_reference)):
        raise PilotCompareError("All inputs must be JSON objects supplied as dictionaries.")
    if any(type(value.get("schema_version")) is not int or value["schema_version"] != 1
           for value in (annotations, shots, manual_reference)):
        raise PilotCompareError("All inputs require schema_version 1.")
    try:
        _validate_shots(shots)
    except NarrativeError as exc:
        raise PilotCompareError("Invalid source-bound M3 segmentation: "+str(exc)) from exc
    _identity(annotations, shots, "Narrative annotations")
    _identity(manual_reference, shots, "Manual cut reference")
    coverage = shots["coverage"]
    if coverage["start_playback_seconds"] > START+EPSILON or coverage["end_playback_seconds"] < END-EPSILON:
        raise PilotCompareError("M3 segmentation does not cover the whole 150--750-second pilot.")
    try:
        events = _prepare_events(annotations)
        scenarios = _prepare_scenarios(manual_reference)
    except NarrativeError as exc:
        raise PilotCompareError(str(exc)) from exc
    automatic = [boundary for boundary in shots["boundaries"] if boundary["transition_type"] in CUT_TYPES
                 and START <= boundary["playback_seconds"] < END]
    overlaps = []
    for event in events:
        for shot in shots["shots"]:
            first = max(START, event["observed_start_seconds"], shot["start_playback_seconds"])
            last = min(END, event["observed_end_seconds"], shot["end_playback_seconds"])
            if last-first > EPSILON:
                overlaps.append({"event_id": event["event_id"], "label": event["label"], "shot_id": shot["shot_id"],
                                 "overlap_start_playback_seconds": first, "overlap_end_playback_seconds": last,
                                 "overlap_seconds": last-first, "true_event_end_seconds": event["true_end_seconds"],
                                 "event_end_right_censored": event["end_right_censored"],
                                 "shot_validation_status": shot.get("validation_status"),
                                 "segmentation_id": shots["segmentation_id"]})
    comparisons, summaries, descriptions = [], [], []
    for scenario in scenarios:
        descriptions.append({"scenario_id": scenario["scenario_id"],
            "manual_hard_cut_count": len(scenario["hard_cuts"]),
            "manual_gradual_transition_count": len(scenario["gradual_transitions"]),
            "automatic_cut_candidate_count": len(automatic),
            "manual_minus_automatic_count": len(scenario["hard_cuts"])-len(automatic),
            "coverage_seconds": END-START, "accuracy_metrics_computed": False,
            "outside_coverage_observations": copy.deepcopy(scenario["outside_coverage_observations"])})
        for window in WINDOWS:
            for jitter in JITTERS:
                rows, summary = _design(events, scenario, window, jitter)
                comparisons.extend(rows)
                summaries.append(summary)
    flags = ["exploratory_single_interval_pilot", "second_level_event_times_not_cut_aligned",
             "boundary_kind_fields_not_used", "no_p_values_or_causal_inference",
             "sensitivity_settings_are_not_confidence_intervals", "player_clock_correspondence_not_subsecond_validated"]
    if any(not scenario["time_basis_confirmed"] for scenario in scenarios):
        flags.append("manual_frame_counter_time_basis_unconfirmed_conditional_scenarios")
    if any(event["end_right_censored"] for event in events):
        flags.append("right_censored_event_true_end_preserved_unknown_or_outside_coverage")
    if any(boundary.get("validation_status") not in ("human_reviewed", "human_verified") for boundary in automatic):
        flags.append("automatic_counts_are_unreviewed_predictions")
    primary = [summary for summary in summaries if summary["design_role"] == "primary"]
    return {"schema_version": 1, "artifact_kind": "local_coarse_time_censored_pilot_comparison",
            "status": "exploratory_diagnostics_only", "film_reference": copy.deepcopy(shots["film_reference"]),
            "video_version_id": shots["video_version_id"], "segmentation_id": shots["segmentation_id"],
            "annotation_set_id": annotations.get("annotation_set_id"),
            "coverage": {"start_seconds": START, "end_seconds": END, "time_reference": "playback_seconds"},
            "parameters": {"primary_window_seconds": 30, "exploratory_window_seconds": [15,10],
                "jitter_seconds": list(JITTERS), "jitter_definition": "common shift of supplied event onsets; coverage-edge onset remains fixed",
                "central_exclusion_seconds": CENTRAL_EXCLUSION,
                "full_window_effective_exposure_per_side_seconds": {"30":29,"15":14,"10":9},
                "control_count": 1, "seed": 0, "timeline_region_count": 3,
                "control_nonreuse_scope": "within_each_scenario_window_jitter_design",
                "allocation": "chronological distinct onsets; seeded greedy complete nonoverlapping controls",
                "analysis_unit": "distinct event onset", "boundary_kind_fields_used": False,
                "temporal_interval_convention": "[center-window,center-1) and (center+1,center+window)"},
            "event_count": len(events), "event_records": events, "event_shot_overlaps": overlaps,
            "manual_timing_scenarios": copy.deepcopy(scenarios), "cut_count_description": descriptions,
            "comparisons": comparisons, "design_summaries": summaries, "primary_summaries": primary,
            "quality_flags": sorted(flags), "p_value": None, "limitations": LIMITATIONS}
