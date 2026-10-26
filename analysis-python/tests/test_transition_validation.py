"""Synthetic interval matching tests; never run a real model or add research labels."""

import copy
import json
import random
import unittest
from fractions import Fraction

from cinematicdx.transition_validation import (
    TransitionValidationError, point_near_span_diagnostic, validate_gradual_transitions,
)


class TransitionValidationTests(unittest.TestCase):
    def identity(self):
        return {"schema_version": 1, "film_reference": {"namespace": "synthetic", "key": "film"},
                "video_version_id": "sha256:" + "a" * 64,
                "coverage": {"start_seconds": 150, "end_seconds": 750}}

    def predictions(self, intervals=()):
        return {**self.identity(), "prediction_set_id": "synthetic-proposals",
                "search_complete_within_coverage": True,
                "predictions": [{"transition_id": name, "start_playback_seconds": first,
                                 "end_playback_seconds": last, "predicted_type": kind}
                                for name, first, last, kind in intervals]}

    def references(self, intervals=(), hard_cuts=()):
        scenario = {"scenario_id": "base-0", "frame_base": 0,
                    "gradual_transitions": [{"transition_id": name,
                                             "start_playback_seconds": first,
                                             "end_playback_seconds": last,
                                             "transition_type": kind}
                                            for name, first, last, kind in intervals],
                    "hard_cuts": [{"cut_id": name, "playback_seconds": second}
                                  for name, second in hard_cuts]}
        return {**self.identity(), "annotation_method": "human", "independent_of_predictions": True,
                "exhaustive_within_coverage": True, "scenarios": [scenario]}

    def score(self, predictions, references, threshold=0.5):
        return validate_gradual_transitions(predictions, references, iou_threshold=threshold)["results"][0]

    def test_maximum_cardinality_precedes_best_individual_iou(self):
        refs = self.references((("a", 200, 210, "叠化"), ("b", 210, 220, "淡出")))
        predicted = self.predictions((("broad", 200, 216, "dissolve"),
                                      ("tight", 200, 207, "dissolve")))
        result = self.score(predicted, refs, threshold=0.3)
        self.assertEqual(2, result["counts"]["true_positive"])
        self.assertEqual({("tight", "a"), ("broad", "b")},
                         {(row["prediction_id"], row["reference_id"]) for row in result["matches"]})
        self.assertEqual("1", result["matching_objective"]["total_temporal_iou_rational"])

    def test_total_iou_breaks_ties_after_cardinality(self):
        refs = self.references((("a", 200, 210, "叠化"), ("b", 210, 220, "淡出")))
        predicted = self.predictions((("broad", 200, 220, "dissolve"),
                                      ("accurate", 210, 220, "fade_out")))
        result = self.score(predicted, refs)
        self.assertEqual({("broad", "a"), ("accurate", "b")},
                         {(row["prediction_id"], row["reference_id"]) for row in result["matches"]})
        self.assertEqual("3/2", result["matching_objective"]["total_temporal_iou_rational"])

    def test_exact_dp_matches_independent_bruteforce_small_graphs(self):
        rng = random.Random(17)
        for case in range(30):
            reference_spans = [(start, start + rng.randrange(2, 25))
                               for start in rng.sample(range(180, 245), 4)]
            prediction_spans = [(start, start + rng.randrange(2, 40))
                                for start in rng.sample(range(170, 250), 5)]
            threshold = Fraction(["0.3", "0.5", "0.75"][case % 3])
            def exhaustive(index, used):
                if index == len(reference_spans):
                    return 0, Fraction(0)
                best = exhaustive(index + 1, used)
                left, right = reference_spans[index]
                for p, (first, last) in enumerate(prediction_spans):
                    intersection = max(0, min(right, last) - max(left, first))
                    overlap = Fraction(intersection, right - left + last - first - intersection)
                    if p in used or overlap < threshold:
                        continue
                    count, total = exhaustive(index + 1, used | {p})
                    best = max(best, (count + 1, total + overlap))
                return best
            expected_count, expected_total = exhaustive(0, set())
            references = self.references(tuple(("r%d" % i, a, b, "叠化")
                                               for i, (a, b) in enumerate(reference_spans)))
            predictions = self.predictions(tuple(("p%d" % i, a, b, "dissolve")
                                                 for i, (a, b) in enumerate(prediction_spans)))
            result = self.score(predictions, references, float(threshold))
            self.assertEqual(expected_count, result["counts"]["true_positive"])
            self.assertEqual(expected_total, Fraction(result["matching_objective"]["total_temporal_iou_rational"]))

    def test_one_wide_prediction_cannot_satisfy_multiple_reference_intervals(self):
        refs = self.references((("a", 200, 210, "叠化"), ("b", 210, 220, "叠化")))
        result = self.score(self.predictions((("wide", 200, 220, "dissolve"),)), refs)
        self.assertEqual(1, result["counts"]["true_positive"])
        self.assertEqual(1, result["counts"]["false_negative"])
        self.assertEqual(0.5, result["localization_metrics"]["recall"])

    def test_wrong_type_still_counts_as_localization_match(self):
        refs = self.references((("fade", 200, 210, "淡出"),))
        result = self.score(self.predictions((("prediction", 200, 210, "dissolve"),)), refs)
        self.assertEqual(1, result["counts"]["true_positive"])
        self.assertEqual(1, result["localization_metrics"]["f1"])
        self.assertFalse(result["matches"][0]["type_correct"])
        self.assertEqual(0, result["type_confusion"]["type_accuracy_among_localized_matches"])
        self.assertEqual([{"reference_type": "fade_out", "predicted_type": "dissolve", "count": 1}],
                         result["type_confusion"]["cells"])

    def test_all_far_from_reference_proposals_are_false_positives(self):
        refs = self.references((("fade", 200, 210, "淡出"),))
        predicted = self.predictions((("correct", 200, 210, "fade_out"),
                                      ("far-1", 450, 460, "dissolve"),
                                      ("far-2", 650, 660, "fade_in")))
        result = self.score(predicted, refs)
        self.assertEqual(1, result["counts"]["true_positive"])
        self.assertEqual(2, result["counts"]["false_positive"])
        self.assertEqual(1 / 3, result["localization_metrics"]["precision"])
        self.assertEqual({"far-1", "far-2"}, {row["transition_id"] for row in result["false_positive"]})

    def test_boundary_clipping_and_fully_outside_proposals_are_explicit(self):
        refs = self.references((("edge", 150, 160, "淡入"),))
        predicted = self.predictions((("left", 140, 160, "fade_in"),
                                      ("outside", 100, 150, "fade_out"),
                                      ("right", 740, 760, "dissolve")))
        entire = validate_gradual_transitions(predicted, refs)
        result = entire["results"][0]
        self.assertEqual(2, entire["prediction_audit"]["clipped_count"])
        self.assertEqual(1, entire["prediction_audit"]["outside_count"])
        self.assertEqual(1, result["counts"]["false_positive"])
        self.assertTrue(result["matches"][0]["prediction"]["left_clipped"])
        self.assertEqual(0, result["boundary_errors"]["start_mae_seconds"])
        self.assertEqual(10, result["boundary_errors"]["raw_start_mae_seconds"])
        self.assertEqual(140, result["matches"][0]["prediction"]["raw_start_playback_seconds"])

    def test_start_end_mae_and_intersection_over_reference_are_recorded(self):
        refs = self.references((("a", 200, 210, "叠化"),))
        result = self.score(self.predictions((("p", 202, 212, "dissolve"),)), refs)
        self.assertEqual(2, result["boundary_errors"]["start_mae_seconds"])
        self.assertEqual(2, result["boundary_errors"]["end_mae_seconds"])
        self.assertAlmostEqual(2 / 3, result["matches"][0]["temporal_iou"])
        self.assertEqual(0.8, result["matches"][0]["intersection_over_reference"])

    def test_threshold_is_inclusive_and_sensitivities_are_not_auto_selected(self):
        refs = self.references((("a", 200, 210, "叠化"),))
        predicted = self.predictions((("p", 200, 220, "dissolve"),))
        self.assertEqual(1, self.score(predicted, refs, 0.5)["counts"]["true_positive"])
        self.assertEqual(0, self.score(predicted, refs, 0.50001)["counts"]["true_positive"])
        for threshold in (0.3, 0.5, 0.75):
            result = validate_gradual_transitions(predicted, refs, iou_threshold=threshold)
            self.assertEqual(threshold, result["iou_threshold"])
            self.assertNotIn("best_threshold", result)
        self.assertEqual(0.5, validate_gradual_transitions(predicted, refs)["iou_threshold"])

    def test_hard_cuts_inside_unmatched_proposals_are_only_confound_diagnostics(self):
        refs = self.references((("g", 200, 210, "叠化"),), (("cut-1", 401), ("cut-2", 405), ("at-end", 410)))
        result = self.score(self.predictions((("false", 400, 410, "dissolve"),)), refs)
        self.assertEqual(1, result["counts"]["false_positive"])
        diagnostic = result["hard_cut_confounds"]
        self.assertTrue(diagnostic["diagnostic_only"])
        self.assertEqual(1, diagnostic["unmatched_prediction_count_with_manual_hard_cut_inside"])
        self.assertEqual(2, diagnostic["predictions"][0]["contained_hard_cut_count"])

    def test_two_frame_base_scenarios_are_retained_without_best_score_selection(self):
        refs = self.references((("g", 200, 210, "叠化"),))
        alternate = copy.deepcopy(refs["scenarios"][0])
        alternate.update(scenario_id="base-1", frame_base=1)
        alternate["gradual_transitions"][0].update(start_playback_seconds=201, end_playback_seconds=211)
        refs["scenarios"].append(alternate)
        result = validate_gradual_transitions(self.predictions((("p", 200, 210, "dissolve"),)), refs)
        self.assertEqual(["base-0", "base-1"], [row["scenario_id"] for row in result["results"]])
        self.assertNotIn("best_scenario", result)
        self.assertTrue(all(row["time_basis_confirmed"] is False for row in result["results"]))

    def test_duplicate_geometry_proposals_are_not_silently_deduplicated(self):
        refs = self.references((("g", 200, 210, "叠化"),))
        result = self.score(self.predictions((("a", 200, 210, "dissolve"), ("b", 200, 210, "dissolve"))), refs)
        self.assertEqual(1, result["counts"]["true_positive"])
        self.assertEqual(1, result["counts"]["false_positive"])

    def test_permutations_and_conflicting_scores_do_not_change_matching(self):
        refs = self.references((("b", 210, 220, "淡出"), ("a", 200, 210, "叠化")))
        predicted = self.predictions((("broad", 200, 220, "dissolve"), ("accurate", 210, 220, "fade_out")))
        predicted["predictions"][0]["score"] = 999
        predicted["predictions"][1]["score"] = -999
        first = self.score(predicted, refs)
        predicted["predictions"].reverse(); refs["scenarios"][0]["gradual_transitions"].reverse()
        second = self.score(predicted, refs)
        self.assertEqual(first["matches"], second["matches"])

    def test_identity_coverage_and_independent_exhaustive_declarations_are_required(self):
        reference = self.references((("g", 200, 210, "叠化"),))
        prediction = self.predictions((("p", 200, 210, "dissolve"),))
        changes = [lambda d: d.update(video_version_id="wrong"),
                   lambda d: d["film_reference"].update(key="wrong"),
                   lambda d: d["coverage"].update(start_seconds=190),
                   lambda d: d.update(search_complete_within_coverage=False),
                   lambda d: d.update(search_scope="reference_neighborhoods"),
                   lambda d: d.update(prediction_set_id=None)]
        for change in changes:
            value = copy.deepcopy(prediction); change(value)
            with self.assertRaises(TransitionValidationError):
                validate_gradual_transitions(value, reference)
        for field in ("independent_of_predictions", "exhaustive_within_coverage"):
            value = copy.deepcopy(reference); value[field] = False
            with self.assertRaises(TransitionValidationError):
                validate_gradual_transitions(prediction, value)

    def test_invalid_numbers_durations_ids_and_point_substitution_are_rejected(self):
        reference = self.references((("g", 200, 210, "叠化"),))
        prediction = self.predictions((("p", 200, 210, "dissolve"),))
        changes = [lambda d: d["predictions"][0].update(start_playback_seconds=float("nan")),
                   lambda d: d["predictions"][0].update(end_playback_seconds=float("inf")),
                   lambda d: d["predictions"][0].update(score=float("nan")),
                   lambda d: d["predictions"][0].update(start_playback_seconds=True),
                   lambda d: d["predictions"][0].update(end_playback_seconds=200),
                   lambda d: d["predictions"][0].update(end_playback_seconds=199),
                   lambda d: d["predictions"].append(copy.deepcopy(d["predictions"][0])),
                   lambda d: d.pop("predictions")]
        for change in changes:
            value = copy.deepcopy(prediction); change(value)
            with self.assertRaises(TransitionValidationError):
                validate_gradual_transitions(value, reference)
        for threshold in (0, -0.1, 1.1, None, True, float("nan"), float("inf")):
            with self.assertRaises(TransitionValidationError):
                validate_gradual_transitions(prediction, reference, iou_threshold=threshold)

    def test_invalid_reference_duplicates_and_durations_are_rejected(self):
        refs = self.references((("g", 200, 210, "叠化"),))
        changes = [lambda d: d["scenarios"][0]["gradual_transitions"].append(copy.deepcopy(d["scenarios"][0]["gradual_transitions"][0])),
                   lambda d: d["scenarios"][0]["gradual_transitions"][0].update(end_playback_seconds=200),
                   lambda d: d["scenarios"][0]["gradual_transitions"][0].update(end_playback_seconds=800),
                   lambda d: d["scenarios"][0].update(frame_base=float("nan")),
                   lambda d: d["scenarios"].append(copy.deepcopy(d["scenarios"][0]))]
        for change in changes:
            value = copy.deepcopy(refs); change(value)
            with self.assertRaises(TransitionValidationError):
                validate_gradual_transitions(self.predictions(), value)

    def test_empty_predictions_and_empty_reference_do_not_create_perfect_scores(self):
        refs = self.references((("g", 200, 210, "叠化"),))
        result = self.score(self.predictions(), refs)
        self.assertEqual(1, result["counts"]["false_negative"])
        self.assertEqual(0, result["localization_metrics"]["recall"])
        self.assertEqual(0, result["localization_metrics"]["f1"])
        self.assertIsNone(result["boundary_errors"]["start_mae_seconds"])
        empty = self.score(self.predictions(), self.references())
        self.assertEqual({"precision": None, "recall": None, "f1": None}, empty["localization_metrics"])

    def test_input_records_are_not_modified_and_result_is_finite_json(self):
        refs = self.references((("g", 200, 210, "叠化"),))
        predicted = self.predictions((("p", 199, 211, "fade_out"),))
        before = copy.deepcopy((predicted, refs))
        result = validate_gradual_transitions(predicted, refs)
        self.assertEqual(before, (predicted, refs))
        json.dumps(result, allow_nan=False)

    def test_point_near_span_is_explicit_non_f1_diagnostic(self):
        refs = self.references((("g", 200, 210, "叠化"),))
        points = {**self.identity(), "prediction_set_id": "point-cuts", "search_complete_within_coverage": True,
                  "points": [{"boundary_id": "at-end", "playback_seconds": 210},
                             {"boundary_id": "near", "playback_seconds": 210.04},
                             {"boundary_id": "far", "playback_seconds": 450},
                             {"boundary_id": "outside", "playback_seconds": 800}]}
        result = point_near_span_diagnostic(points, refs)
        self.assertFalse(result["precision_recall_f1_computed"])
        self.assertFalse(result["is_gradual_detector_evaluation"])
        self.assertNotIn("localization_metrics", result)
        self.assertEqual(1, result["results"][0]["nearby_point_count_unique"])
        sensitivity = point_near_span_diagnostic(points, refs, margin_seconds=0.04)
        self.assertEqual(2, sensitivity["results"][0]["nearby_point_count_unique"])
        self.assertEqual(1, result["outside_coverage_point_count"])
        with self.assertRaises(TransitionValidationError):
            validate_gradual_transitions(points, refs)


if __name__ == "__main__":
    unittest.main()
