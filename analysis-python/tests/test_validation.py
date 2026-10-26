"""Synthetic point-boundary cases; these do not validate any historical film."""

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cinematicdx.validation import (
    ValidationError, prepare_boundary_reference_template, validate_shots,
)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def shots(self, times=(10, 20, 30)):
        return {"schema_version": 1, "artifact_kind": "shot_segmentation",
                "film_reference": {"namespace": "synthetic-fixtures", "key": "film-1"},
                "video_version_id": "sha256:" + "1" * 64, "segmentation_id": "seg-1",
                "coverage": {"start_source_seconds": 100, "end_source_seconds": 160,
                             "start_playback_seconds": 0, "end_playback_seconds": 60},
                "shots": [{"shot_id": "synthetic-shot"}],
                "boundaries": [{"boundary_id": "p{}".format(index),
                                "source_seconds": 100 + second, "playback_seconds": second,
                                "transition_type": "unclassified_cut_candidate"}
                               for index, second in enumerate(times, 1)]}

    def reference(self, times=(10, 20, 30)):
        return {"schema_version": 1, "artifact_kind": "boundary_reference",
                "film_reference": {"namespace": "synthetic-fixtures", "key": "film-1"},
                "video_version_id": "sha256:" + "1" * 64,
                "annotation_set_id": "synthetic-reference-1", "annotator": "synthetic test fixture",
                "annotation_method": "synthetic", "independent_of_predictions": True,
                "exhaustive_within_coverage": True, "time_reference": "playback_seconds",
                "coverage": {"start_seconds": 0, "end_seconds": 60},
                "boundaries": [{"boundary_id": "r{}".format(index), "time_seconds": second,
                                "transition_type": "cut"} for index, second in enumerate(times, 1)]}

    def evaluate(self, shots=None, reference=None, tolerance=0.25, name="result"):
        shots_path = self.write("shots.json", shots if shots is not None else self.shots())
        reference_path = self.write("reference.json", reference if reference is not None else self.reference())
        result = validate_shots(shots_path, reference_path, self.root / name,
                                tolerance_seconds=tolerance)
        document = json.loads((self.root / name / "validation.json").read_text())
        return result, document

    def test_template_has_no_labels_or_fabricated_annotation_identity(self):
        shots_path = self.write("shots.json", self.shots())
        before = shots_path.read_bytes()
        receipt = prepare_boundary_reference_template(shots_path, self.root / "template")
        template = json.loads(Path(receipt["reference_template_path"]).read_text())
        self.assertEqual([], template["boundaries"])
        self.assertEqual([], template["excluded_intervals"])
        self.assertIsNone(template["annotation_set_id"])
        self.assertIsNone(template["annotator"])
        self.assertIsNone(template["annotation_method"])
        self.assertIs(template["independent_of_predictions"], False)
        self.assertIs(template["exhaustive_within_coverage"], False)
        self.assertEqual(0, template["coverage"]["start_seconds"])
        self.assertEqual(60, template["coverage"]["end_seconds"])
        self.assertEqual("template_only", receipt["status"])
        self.assertEqual(before, shots_path.read_bytes())
        with self.assertRaises(ValidationError):
            validate_shots(shots_path, receipt["reference_template_path"], self.root / "invalid",
                           tolerance_seconds=0.25)
        self.assertFalse((self.root / "invalid").exists())

    def test_one_to_one_counts_metrics_timing_and_partial_reference_scope(self):
        reference = self.reference((10, 20.1, 40))
        reference["coverage"] = {"start_seconds": 0, "end_seconds": 45}
        receipt, result = self.evaluate(self.shots((10.1, 10.2, 20, 35, 50)), reference)
        self.assertEqual({"true_positive": 2, "false_positive": 2, "false_negative": 1,
                          "reference_boundaries": 3, "scored_predictions": 4,
                          "excluded_predictions": 0, "outside_reference_coverage_predictions": 1,
                          "all_segmentation_predictions": 5}, result["counts"])
        self.assertEqual(0.5, result["metrics"]["precision"])
        self.assertAlmostEqual(2 / 3, result["metrics"]["recall"])
        self.assertAlmostEqual(4 / 7, result["metrics"]["f1"])
        self.assertEqual("p5", result["outside_reference_coverage_predictions"][0]["boundary_id"])
        self.assertEqual(["r3"], [row["boundary_id"] for row in result["missed"]])
        self.assertEqual([0.1, -0.1], [row["signed_error_seconds"] for row in result["matches"]])
        self.assertEqual(0, result["timing_errors"]["mean_signed_seconds"])
        self.assertEqual(0.1, result["timing_errors"]["mean_absolute_seconds"])
        self.assertEqual("synthetic", receipt["annotation_method"])
        self.assertIn("synthetic_test_only", result["warnings"])

    def test_matching_is_chronological_inclusive_and_not_nearest_neighbor(self):
        _, result = self.evaluate(self.shots((9.8, 10)), self.reference((10,)), tolerance=0.2)
        self.assertEqual("p1", result["matches"][0]["prediction_boundary_id"])
        self.assertEqual(-0.2, result["matches"][0]["signed_error_seconds"])
        self.assertEqual("p2", result["false_positive"][0]["boundary_id"])
        self.assertTrue(result["matching_policy"]["tolerance_inclusive"])
        self.assertFalse(result["matching_policy"]["nearest_neighbor_optimization"])

    def test_a_prediction_cannot_satisfy_two_reference_labels(self):
        _, result = self.evaluate(self.shots((10,)), self.reference((9.9, 10.1)), tolerance=0.2)
        self.assertEqual(1, result["counts"]["true_positive"])
        self.assertEqual(1, result["counts"]["false_negative"])
        self.assertEqual(0, result["counts"]["false_positive"])

    def test_unsorted_inputs_are_scored_in_sorted_chronological_order(self):
        first = self.shots((30, 10, 20))
        second = self.reference((20, 30, 10))
        _, result = self.evaluate(first, second)
        self.assertEqual([10, 20, 30], [row["prediction_time_seconds"] for row in result["matches"]])
        self.assertEqual(3, result["counts"]["true_positive"])

    def test_excluded_intervals_remove_predictions_without_counting_them_as_fp(self):
        reference = self.reference((10, 20, 36))
        reference["excluded_intervals"] = [{"start_seconds": 34, "end_seconds": 36,
                                             "reason": "uncertain gradual transition"}]
        _, result = self.evaluate(self.shots((10, 20, 34, 35, 36)), reference)
        self.assertEqual(3, result["counts"]["true_positive"])
        self.assertEqual(0, result["counts"]["false_positive"])
        self.assertEqual(2, result["counts"]["excluded_predictions"])
        self.assertEqual(58, result["coverage"]["evaluated_seconds"])
        self.assertTrue(all(row["exclusion_reason"] == "uncertain gradual transition"
                            for row in result["excluded_predictions"]))

    def test_source_coordinate_reference_is_not_mixed_with_playback_coordinates(self):
        reference = self.reference((110, 120, 130))
        reference["time_reference"] = "source_seconds"
        reference["coverage"] = {"start_seconds": 100, "end_seconds": 160}
        _, result = self.evaluate(reference=reference)
        self.assertEqual(3, result["counts"]["true_positive"])
        self.assertEqual([110, 120, 130], [row["prediction_time_seconds"] for row in result["matches"]])

    def test_reference_end_is_exclusive_and_predictions_after_review_are_not_false_positives(self):
        reference = self.reference((10,))
        reference["coverage"] = {"start_seconds": 10, "end_seconds": 20}
        _, result = self.evaluate(reference=reference)
        self.assertEqual(1, result["counts"]["true_positive"])
        self.assertEqual(0, result["counts"]["false_positive"])
        self.assertEqual(2, result["counts"]["outside_reference_coverage_predictions"])

    def test_exhaustively_reviewed_zero_cut_region_never_gets_perfect_metrics(self):
        _, result = self.evaluate(reference=self.reference(()))
        self.assertEqual({"precision": None, "recall": None, "f1": None}, result["metrics"])
        self.assertEqual(3, result["counts"]["false_positive"])
        self.assertEqual(0, result["counts"]["reference_boundaries"])
        self.assertIsNone(result["timing_errors"]["mean_absolute_seconds"])
        receipt = json.loads((self.root / "result" / "run.json").read_text())
        self.assertEqual("no_reference_cut_events", receipt["status"])

    def test_empty_predictions_give_recall_and_f1_zero_but_undefined_precision(self):
        _, result = self.evaluate(shots=self.shots(()))
        self.assertIsNone(result["metrics"]["precision"])
        self.assertEqual(0, result["metrics"]["recall"])
        self.assertEqual(0, result["metrics"]["f1"])
        self.assertEqual(3, result["counts"]["false_negative"])

    def test_invalid_tolerances_are_rejected_before_any_output_is_published(self):
        shots = self.write("shots.json", self.shots())
        reference = self.write("reference.json", self.reference())
        for tolerance in (None, True, False, 0, -0.1, float("nan"), float("inf"), "0.1"):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValidationError):
                validate_shots(shots, reference, self.root / "invalid", tolerance_seconds=tolerance)
            self.assertFalse((self.root / "invalid").exists())

    def test_identity_independence_exhaustiveness_and_reviewer_fields_are_required(self):
        mutations = [
            lambda data: data["film_reference"].update(namespace="another-inventory"),
            lambda data: data["film_reference"].update(key="another-film"),
            lambda data: data.update(video_version_id="different-video"),
            lambda data: data.update(annotation_set_id="seg-1"),
            lambda data: data.update(annotation_set_id=None),
            lambda data: data.update(annotator=None),
            lambda data: data.update(annotation_method="automatic"),
            lambda data: data.update(independent_of_predictions=False),
            lambda data: data.update(independent_of_predictions="true"),
            lambda data: data.update(exhaustive_within_coverage=False),
            lambda data: data.pop("coverage"),
            lambda data: data.update(time_reference="frames"),
        ]
        self.assert_invalid_references(mutations)

    def test_duplicate_invalid_and_out_of_scope_reference_labels_are_rejected(self):
        mutations = [
            lambda data: data["boundaries"][1].update(boundary_id="r1"),
            lambda data: data["boundaries"][1].update(time_seconds=10.0),
            lambda data: data["boundaries"][0].update(time_seconds=True),
            lambda data: data["boundaries"][0].update(time_seconds=60),
            lambda data: data["boundaries"][0].update(transition_type="dissolve"),
            lambda data: data.update(coverage={"start_seconds": -1, "end_seconds": 60}),
            lambda data: data.update(coverage={"start_seconds": 10, "end_seconds": 10}),
            lambda data: data.update(excluded_intervals=[{"start_seconds": 9, "end_seconds": 11,
                                                         "reason": "uncertain"}]),
            lambda data: data.update(excluded_intervals=[{"start_seconds": 40, "end_seconds": 61,
                                                         "reason": "outside"}]),
            lambda data: data.update(excluded_intervals=[{"start_seconds": 40, "end_seconds": 45,
                                                         "reason": "first"},
                                                        {"start_seconds": 44, "end_seconds": 46,
                                                         "reason": "overlap"}]),
            lambda data: data.update(excluded_intervals=[{"start_seconds": 40, "end_seconds": 45}]),
        ]
        self.assert_invalid_references(mutations)

    def assert_invalid_references(self, mutations):
        shots = self.write("shots.json", self.shots())
        for index, mutation in enumerate(mutations):
            reference = self.reference()
            mutation(reference)
            path = self.write("reference.json", reference)
            with self.subTest(case=index), self.assertRaises(ValidationError):
                validate_shots(shots, path, self.root / "invalid", tolerance_seconds=0.25)
            self.assertFalse((self.root / "invalid").exists())

    def test_malformed_prediction_boundaries_and_inconsistent_coordinate_offsets_are_rejected(self):
        mutations = [
            lambda data: data["boundaries"][1].update(boundary_id="p1"),
            lambda data: data["boundaries"][1].update(source_seconds=110, playback_seconds=10),
            lambda data: data["boundaries"][0].update(playback_seconds=11),
            lambda data: data["boundaries"][0].update(source_seconds=100, playback_seconds=0),
            lambda data: data["coverage"].update(end_playback_seconds=61),
        ]
        for index, mutate in enumerate(mutations):
            shots = self.shots()
            mutate(shots)
            path = self.write("shots.json", shots)
            with self.subTest(case=index), self.assertRaises(ValidationError):
                prepare_boundary_reference_template(path, self.root / "invalid")
            self.assertFalse((self.root / "invalid").exists())

    def test_output_receipt_checksums_csv_rows_and_inputs_are_preserved(self):
        shots_path = self.write("shots.json", self.shots())
        reference_path = self.write("reference.json", self.reference((10, 40)))
        before = {path: path.read_bytes() for path in (shots_path, reference_path)}
        validate_shots(shots_path, reference_path, self.root / "result", tolerance_seconds=0.25)
        run = json.loads((self.root / "result" / "run.json").read_text())
        self.assertEqual({"validation.json", "matches.csv", "missed.csv", "false_positive.csv"}, set(run["outputs"]))
        for name, details in run["outputs"].items():
            content = (self.root / "result" / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), details["sha256"])
            self.assertEqual(len(content), details["size_bytes"])
        for path, content in before.items():
            self.assertEqual(content, path.read_bytes())
        with (self.root / "result" / "matches.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(1, len(rows))
        self.assertEqual("synthetic-fixtures", rows[0]["film_namespace"])
        self.assertEqual("synthetic-reference-1", rows[0]["annotation_set_id"])
        with self.assertRaises(ValidationError):
            validate_shots(shots_path, reference_path, self.root / "result", tolerance_seconds=0.25)
        self.assertEqual(run, json.loads((self.root / "result" / "run.json").read_text()))

    def test_annotation_method_is_explicit_and_prior_segmentation_is_only_provenance(self):
        reference = self.reference()
        reference["annotation_method"] = "assistant"
        reference["segmentation_id"] = "previous-segmentation"
        _, result = self.evaluate(reference=reference)
        self.assertEqual("assistant", result["annotation"]["annotation_method"])
        self.assertIn("assistant_reference_not_human_validation", result["warnings"])
        self.assertTrue(any("different_segmentation_id" in warning for warning in result["warnings"]))

    def test_rational_sidecars_are_authoritative_but_inconsistency_is_rejected(self):
        shots = self.shots((10.1,))
        shots["boundaries"][0]["source_seconds_rational"] = "1101/10"
        shots["boundaries"][0]["playback_seconds_rational"] = "101/10"
        _, result = self.evaluate(shots=shots, reference=self.reference((10,)), tolerance=0.1)
        self.assertEqual(1, result["counts"]["true_positive"])
        self.assertEqual("1/10", result["matches"][0]["signed_error_seconds_rational"])
        shots["boundaries"][0]["playback_seconds_rational"] = "50"
        path = self.write("inconsistent.json", shots)
        with self.assertRaises(ValidationError):
            prepare_boundary_reference_template(path, self.root / "invalid")

    def test_duplicate_json_fields_and_nonfinite_reference_times_are_rejected(self):
        shots_path = self.write("shots.json", self.shots())
        path = self.root / "bad.json"
        for raw in ('{"schema_version":1,"schema_version":1}',
                    '{"schema_version":1,"bad":NaN}', "[]"):
            path.write_text(raw)
            with self.assertRaises(ValidationError):
                validate_shots(shots_path, path, self.root / "invalid", tolerance_seconds=0.25)
        self.assertFalse((self.root / "invalid").exists())


if __name__ == "__main__":
    unittest.main()
