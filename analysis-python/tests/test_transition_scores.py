"""Synthetic score-adapter tests; no real model, media or annotations are read."""

import copy
import json
import math
import unittest
from fractions import Fraction

from cinematicdx.transition_scores import TransitionScoresError, scores_to_transition_intervals


class TransitionScoresTests(unittest.TestCase):
    def convert(self, scores, pts=None, next_pts=None, **kwargs):
        if pts is None:
            pts = list(range(len(scores)))
        if next_pts is None:
            next_pts = [value + 1 for value in pts]
        return scores_to_transition_intervals(scores, pts, next_pts,
                                             time_base=kwargs.pop("time_base", Fraction(1, 5)),
                                             playback_origin=kwargs.pop("playback_origin", 0), **kwargs)

    def test_strict_threshold_and_uncalibrated_score_summary(self):
        result = self.convert([0.5, 0.6, 0.7, 0.5, 0.8])
        event, = result["gradual_predictions"]
        self.assertEqual((1, 3), (event["start_frame_index"], event["end_frame_index_exclusive"]))
        self.assertEqual("2/5", event["duration_seconds_rational"])
        self.assertEqual("unknown_gradual", event["predicted_type"])
        self.assertEqual((0.6, 0.7), (event["score_min"], event["score_max"]))
        self.assertAlmostEqual(0.65, event["score_mean"])
        self.assertTrue(event["score_uncalibrated"])
        self.assertEqual(2, result["counts"]["threshold_runs"])
        self.assertEqual("unclassified_short_transition", result["short_transition_events"][0]["predicted_type"])

    def test_source_offset_and_vfr_support_use_exact_pts(self):
        result = self.convert([0, 0.8, 0.9, 0], [1000, 1002, 1005, 1009],
                              [1002, 1005, 1009, 1014], time_base="1/10", playback_origin="100")
        event, = result["gradual_predictions"]
        self.assertEqual((1002, 1009), (event["start_pts"], event["end_pts"]))
        self.assertEqual("501/5", event["start_source_seconds_rational"])
        self.assertEqual("1009/10", event["end_source_seconds_rational"])
        self.assertEqual("1/5", event["start_playback_seconds_rational"])
        self.assertEqual("9/10", event["end_playback_seconds_rational"])
        self.assertEqual("7/10", event["duration_seconds_rational"])

    def test_edge_and_trailing_runs_preserved_without_maximum_duration(self):
        result = self.convert([0.9] * 6, [0, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 500],
                              time_base=1)
        event, = result["gradual_predictions"]
        self.assertEqual((0, 6), (event["start_frame_index"], event["end_frame_index_exclusive"]))
        self.assertEqual(500, event["end_pts"])
        self.assertEqual(500, event["duration_seconds"])
        self.assertIsNone(result["conversion_policy"]["maximum_duration_seconds"])
        self.assertEqual([], self.convert([0.5, 0.5])["gradual_predictions"])

    def test_one_false_frame_is_never_gap_closed(self):
        result = self.convert([0.9, 0.1, 0.9], min_duration_seconds=0.3)
        self.assertEqual([], result["gradual_predictions"])
        self.assertEqual([0, 2], [x["start_frame_index"] for x in result["short_transition_events"]])
        self.assertEqual(2, result["counts"]["threshold_runs"])

    def test_minimum_duration_inclusive_and_short_events_retained(self):
        result = self.convert([0.9, 0, 0.9], [0, 400, 500], [400, 500, 899], time_base="1/1000")
        self.assertEqual(1, len(result["gradual_predictions"]))
        self.assertEqual("2/5", result["gradual_predictions"][0]["duration_seconds_rational"])
        self.assertEqual("399/1000", result["short_transition_events"][0]["duration_seconds_rational"])

    def test_empty_sequences_and_mismatched_lengths(self):
        result = self.convert([])
        self.assertEqual(0, result["counts"]["frames"])
        self.assertEqual([], result["gradual_predictions"])
        for scores, pts, after in [([0.6], [], []), ([], [0], [1]), ([0.6], [0], [])]:
            with self.subTest(values=(scores, pts, after)), self.assertRaises(TransitionScoresError):
                self.convert(scores, pts, after)

    def test_non_sigmoid_nonfinite_boolean_and_nested_scores_rejected(self):
        for bad in [True, False, math.nan, math.inf, -math.inf, -0.01, 1.01, "0.7", None, [0.7], 1j]:
            with self.subTest(score=bad), self.assertRaises(TransitionScoresError):
                self.convert([bad])

    def test_invalid_source_pts_and_discontinuous_support_rejected(self):
        cases = [([True], [2]), ([0.0], [1]), ([0], [True]), ([0], [0]), ([2], [1]),
                 ([0, 0], [0, 1]), ([1, 0], [2, 1]), ([0, 2], [1, 3]),
                 ([0, 2], [3, 4]), ([0], [1.0])]
        for pts, after in cases:
            with self.subTest(pts=pts, next_pts=after), self.assertRaises(TransitionScoresError):
                self.convert([0.7] * len(pts), pts, after)

    def test_invalid_policy_parameters_rejected(self):
        for name, bad in [("threshold", True), ("threshold", math.nan), ("threshold", -0.1),
                          ("threshold", 1.1), ("min_duration_seconds", 0),
                          ("min_duration_seconds", -1), ("min_duration_seconds", True),
                          ("time_base", 0), ("time_base", "-1/25"), ("time_base", "1/0"),
                          ("time_base", math.inf), ("playback_origin", math.nan),
                          ("playback_origin", False)]:
            with self.subTest(parameter=name, value=bad), self.assertRaises(TransitionScoresError):
                self.convert([0.7], **{name: bad})

    def test_negative_source_coordinates_iterables_and_inputs_unchanged(self):
        original = [[0.7, 0.8], [-2, -1], [-1, 0]]
        saved = copy.deepcopy(original)
        first = self.convert(*original, time_base="1/4", playback_origin="-1/2")
        second = scores_to_transition_intervals(*(iter(row) for row in original),
                                                time_base=Fraction(1, 4), playback_origin=Fraction(-1, 2))
        self.assertEqual(saved, original)
        self.assertEqual(first, second)
        self.assertEqual("0", first["gradual_predictions"][0]["start_playback_seconds_rational"])
        self.assertEqual(first, json.loads(json.dumps(first, allow_nan=False)))


if __name__ == "__main__":
    unittest.main()
