"""Synthetic timestamps exercise alignment; fixtures are never film annotations."""

import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cinematicdx import narrative


class NarrativeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.shots_path = self.root / "shots.json"
        self.annotations_path = self.root / "annotations.json"
        self.origin = 0.043
        self.shots = self.make_shots([0, 100, 200, 300, 305, 400, 500, 600, 700, 800,
                                     900, 1000, 1200, 1500, 1800, 2100, 2400, 2700, 3000])
        self.annotations = {
            "schema_version": 1, "film_reference": {"namespace": "synthetic-unit-fixture", "key": "film"},
            "video_version_id": "sha256:" + "1"*64, "annotation_set_id": "synthetic-events",
            "annotator": "unit-test-fixture", "annotation_method": "synthetic",
            "independent_of_visual_measurements": True, "time_reference": "playback_seconds",
            "events": [self.event("event1", 300, 350)],
        }
        self.save_inputs()
        software = mock.patch("cinematicdx.narrative.software_provenance", return_value={"fixture": True})
        software.start()
        self.addCleanup(software.stop)

    def make_shots(self, times):
        result = {"schema_version": 1, "film_reference": {"namespace": "synthetic-unit-fixture", "key": "film"},
                  "video_version_id": "sha256:"+"1"*64, "segmentation_id": "synthetic-segmentation",
                  "coverage": {"start_source_seconds": times[0]+self.origin,
                               "end_source_seconds": times[-1]+self.origin,
                               "start_playback_seconds": times[0], "end_playback_seconds": times[-1]},
                  "shots": [], "boundaries": []}
        for index, (first, last) in enumerate(zip(times, times[1:])):
            result["shots"].append({"shot_id": "shot"+str(index), "start_pts": round((first+self.origin)*1000),
                "end_pts": round((last+self.origin)*1000), "time_base": "1/1000",
                "start_source_seconds": first+self.origin, "end_source_seconds": last+self.origin,
                "start_playback_seconds": first, "end_playback_seconds": last,
                "duration_seconds": last-first, "validation_status": "automated_unreviewed"})
            if index:
                result["boundaries"].append({"boundary_id": "cut"+str(index), "pts": round((first+self.origin)*1000),
                    "time_base": "1/1000", "source_seconds": first+self.origin, "playback_seconds": first,
                    "transition_type": "cut", "validation_status": "automated_unreviewed",
                    "local_frame_interval_seconds": 0.04})
        return result

    def event(self, event_id, first, last, **values):
        return {"event_id": event_id, "start_seconds": first, "end_seconds": last,
                "label": "synthetic event", "certainty": "certain", **values}

    def save_inputs(self):
        self.shots_path.write_text(json.dumps(self.shots, ensure_ascii=False), encoding="utf-8")
        self.annotations_path.write_text(json.dumps(self.annotations, ensure_ascii=False), encoding="utf-8")

    def align(self, name="alignment", **parameters):
        return narrative.align_narrative(self.shots_path, self.annotations_path, self.root/name,
                                         **parameters)

    def rows(self, name="alignment", artifact="alignment.csv"):
        with (self.root/name/artifact).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def document(self, artifact, name="alignment"):
        return json.loads((self.root/name/artifact).read_text(encoding="utf-8"))

    def test_template_is_empty_not_ready_and_independent_of_shot_segmentation_identity(self):
        before = self.shots_path.read_bytes()
        summary = narrative.prepare_annotation_template(self.shots_path, self.root/"template")
        template = self.document("annotation_template.json", "template")
        self.assertEqual("annotation_required", summary["status"])
        self.assertEqual([], template["events"])
        self.assertIsNone(template["annotator"])
        self.assertIsNone(template["annotation_method"])
        self.assertEqual("template_not_ready", template["annotation_status"])
        self.assertNotIn("segmentation_id", template)
        self.assertEqual(self.shots["film_reference"], template["film_reference"])
        self.assertFalse(summary["research_comparison_performed"])
        self.assertEqual(before, self.shots_path.read_bytes())
        with self.assertRaises(narrative.NarrativeError):
            narrative.align_narrative(self.shots_path, self.root/"template/annotation_template.json",
                                     self.root/"must-not-publish")
        self.assertFalse((self.root/"must-not-publish").exists())

    def test_interval_overlap_keeps_exact_inside_shot_starts_and_annotations(self):
        self.annotations["events"] = [self.event("inside", 302.125, 312.5,
            label="假设事件，仅供测试", location="测试地点", characters=["甲", "乙"],
            narrative_time="later", notes="independently supplied fixture")]
        self.save_inputs()
        summary = self.align(window_seconds=10)
        rows = self.rows()
        self.assertEqual(2, len(rows))
        self.assertAlmostEqual(302.125+self.origin, float(rows[0]["event_start_source_seconds"]))
        self.assertAlmostEqual(302.125, float(rows[0]["event_start_playback_seconds"]))
        self.assertAlmostEqual(2.875, float(rows[0]["overlap_seconds"]))
        self.assertAlmostEqual(7.5, float(rows[1]["overlap_seconds"]))
        self.assertAlmostEqual(10.375, sum(float(row["overlap_seconds"]) for row in rows))
        self.assertEqual(["甲", "乙"], json.loads(rows[0]["characters"]))
        self.assertEqual("测试地点", rows[0]["location"])
        contrast = self.rows(artifact="event_contrasts.csv")[0]
        self.assertEqual("within_shot", contrast["boundary_position"])
        self.assertEqual(0, int(contrast["control_count"]))
        self.assertEqual(1, summary["within_shot_onset_count"])

    def test_source_and_playback_annotations_align_to_identical_original_coordinates(self):
        self.align("playback", window_seconds=10, control_count=2)
        self.annotations["time_reference"] = "source_seconds"
        self.annotations["events"][0]["start_seconds"] += self.origin
        self.annotations["events"][0]["end_seconds"] += self.origin
        self.save_inputs()
        self.align("source", window_seconds=10, control_count=2)
        playback, source = self.rows("playback"), self.rows("source")
        self.assertEqual([row["shot_id"] for row in playback], [row["shot_id"] for row in source])
        self.assertEqual([row["overlap_seconds"] for row in playback], [row["overlap_seconds"] for row in source])
        self.assertEqual(playback[0]["event_start_source_seconds"], source[0]["event_start_source_seconds"])

    def test_event_cut_and_control_anchor_cuts_are_excluded_from_rates(self):
        summary = self.align(window_seconds=10, control_count=2, seed=7)
        row = self.rows(artifact="event_contrasts.csv")[0]
        self.assertEqual("at_cut", row["boundary_position"])
        self.assertEqual("exploratory_matched", row["comparison_status"])
        self.assertEqual(0, int(row["before_cut_count"]))
        self.assertEqual(1, int(row["after_cut_count"]))
        self.assertAlmostEqual(3, float(row["window_cutting_rate_per_minute"]))
        self.assertAlmostEqual(6, float(row["rate_change_per_minute"]))
        self.assertAlmostEqual(3, float(row["event_minus_control_rate_per_minute"]))
        self.assertEqual(1, summary["matched_event_onset_count"])
        self.assertAlmostEqual(6, summary["mean_event_minus_control_rate_change_per_minute"])
        for control in json.loads(row["controls"]):
            self.assertEqual(0, control["before_cut_count"]+control["after_cut_count"])
            self.assertEqual(0, control["window_cutting_rate_per_minute"])
            self.assertNotEqual(row["matched_boundary_id"], control["boundary_id"])

    def test_controls_match_region_exclude_all_event_windows_and_do_not_overlap_each_other(self):
        self.annotations["events"].append(self.event("event2", 600, 650))
        self.save_inputs()
        self.align(window_seconds=10, control_count=3, seed=10)
        controls = []
        for row in self.rows(artifact="event_contrasts.csv"):
            for control in json.loads(row["controls"]):
                self.assertLess(control["playback_seconds"], 1000)
                for event in self.annotations["events"]:
                    self.assertGreaterEqual(abs(control["playback_seconds"]-event["start_seconds"]), 20)
                controls.append(control)
        self.assertGreater(len(controls), 0)
        self.assertEqual(len(controls), len({control["boundary_id"] for control in controls}))
        for index, first in enumerate(controls):
            for second in controls[index+1:]:
                self.assertGreaterEqual(abs(first["source_seconds"]-second["source_seconds"]), 20)

    def test_seed_makes_matching_deterministic(self):
        self.align("first", window_seconds=10, control_count=3, seed=42)
        self.align("second", window_seconds=10, control_count=3, seed=42)
        self.assertEqual((self.root/"first/event_contrasts.csv").read_bytes(),
                         (self.root/"second/event_contrasts.csv").read_bytes())

    def test_touching_half_open_windows_do_not_count_a_shared_edge_cut_twice(self):
        self.annotations["events"].append(self.event("event2", 500, 550))
        self.save_inputs()
        summary = self.align(window_seconds=100, control_count=1)
        rows = self.rows(artifact="event_contrasts.csv")
        # [200,400): cuts 200 and 305, excluding anchor 300 and outer edge 400.
        self.assertEqual(2, int(rows[0]["before_cut_count"])+int(rows[0]["after_cut_count"]))
        # [400,600): cut 400 belongs only to this window; anchor 500 is excluded.
        self.assertEqual(1, int(rows[1]["before_cut_count"])+int(rows[1]["after_cut_count"]))
        self.assertIn("[center-window,center+window)", summary["parameters"]["window_interval_convention"])

    def test_actual_local_frame_tolerance_classifies_without_snapping_and_fallback_is_flagged(self):
        self.annotations["events"] = [self.event("near", 300.02, 350)]
        self.save_inputs()
        self.align("actual", window_seconds=10, control_count=1)
        row = self.rows("actual", "event_contrasts.csv")[0]
        self.assertEqual("at_cut", row["boundary_position"])
        self.assertAlmostEqual(300.02+self.origin, float(row["source_seconds"]))
        self.assertAlmostEqual(0.04, float(row["boundary_tolerance_seconds"]))
        for boundary in self.shots["boundaries"]:
            boundary.pop("local_frame_interval_seconds")
        self.save_inputs()
        summary = self.align("fallback", window_seconds=10, control_count=1)
        self.assertIn("boundary_tolerance_fallback_seconds_used", summary["quality_flags"])
        self.assertAlmostEqual(0.08, float(self.rows("fallback", "event_contrasts.csv")[0]["boundary_tolerance_seconds"]))

    def test_inside_shot_onset_outside_one_actual_frame_is_not_called_at_cut(self):
        self.annotations["events"] = [self.event("inside", 300.06, 350)]
        self.save_inputs()
        self.align(window_seconds=10)
        self.assertEqual("within_shot", self.rows(artifact="event_contrasts.csv")[0]["boundary_position"])

    def test_non_cut_transition_is_a_separate_boundary_stratum_not_a_within_shot_onset(self):
        boundary = next(boundary for boundary in self.shots["boundaries"] if boundary["playback_seconds"]==300)
        boundary["transition_type"] = "fade"
        self.save_inputs()
        summary = self.align(window_seconds=10, control_count=1)
        row = self.rows(artifact="event_contrasts.csv")[0]
        self.assertEqual("at_transition", row["boundary_position"])
        self.assertEqual("fade", row["matched_transition_type"])
        self.assertEqual("0", row["control_count"])
        self.assertIn("non_cut_transition_separate_stratum", json.loads(row["reasons"]))
        self.assertEqual(1, summary["at_transition_onset_count"])
        self.assertIn("non_cut_transitions_excluded_from_cutting_rates", summary["quality_flags"])

    def test_edges_uncertainty_and_overlapping_event_windows_are_explicit_exclusions(self):
        self.annotations["events"] = [self.event("beginning", 0, 10), self.event("uncertain", 100, 150, certainty="uncertain"),
                                      self.event("close1", 300, 320), self.event("close2", 305, 330)]
        self.save_inputs()
        summary = self.align(window_seconds=10)
        rows = {row["event_id"]:row for row in self.rows(artifact="event_contrasts.csv")}
        self.assertIn("edge_truncated_window", json.loads(rows["beginning"]["reasons"]))
        self.assertIn("uncertain_event_onset", json.loads(rows["uncertain"]["reasons"]))
        self.assertIn("overlapping_event_windows", json.loads(rows["close1"]["reasons"]))
        self.assertIn("overlapping_event_windows", json.loads(rows["close2"]["reasons"]))
        self.assertIn("uncertain_narrative_annotations", summary["quality_flags"])
        self.assertEqual(0, summary["matched_event_onset_count"])
        self.assertIsNone(summary["mean_event_minus_control_rate_per_minute"])

    def test_shared_onset_is_one_analysis_unit_but_both_event_segments_are_aligned(self):
        self.annotations["events"].append(self.event("overlapping-layer", 300, 450))
        self.save_inputs()
        summary = self.align(window_seconds=10, control_count=1)
        self.assertEqual(2, summary["event_count"])
        self.assertEqual(1, summary["distinct_onset_count"])
        self.assertEqual({"event1", "overlapping-layer"}, {row["event_id"] for row in self.rows()})
        row = self.rows(artifact="event_contrasts.csv")[0]
        self.assertEqual(["event1", "overlapping-layer"], json.loads(row["linked_event_ids"]))

    def test_insufficient_controls_are_not_silently_pooled_into_summary_effect(self):
        summary = self.align(window_seconds=10, control_count=100)
        row = self.rows(artifact="event_contrasts.csv")[0]
        self.assertIn("insufficient_nonoverlapping_controls", json.loads(row["reasons"]))
        self.assertEqual("unmatched_or_excluded", row["comparison_status"])
        self.assertEqual(0, summary["matched_event_onset_count"])
        self.assertIsNone(summary["mean_event_minus_control_rate_per_minute"])
        self.assertIsNone(summary["mean_event_minus_control_rate_change_per_minute"])
        self.assertEqual("False", row["controls_reserved_for_matched_analysis"])
        self.assertTrue(all(not control["reserved_for_matched_analysis"] for control in json.loads(row["controls"])))

    def test_partial_unmatched_control_set_does_not_exhaust_later_eligible_onset(self):
        # A greedy first choice of 115 blocks both 100 and 130 for a +/-10s window.
        # The next seeded shuffle chooses the disjoint pair 130 and 100 instead.
        self.shots = self.make_shots([0, 100, 115, 130, 300, 600, 3000])
        self.annotations["events"].append(self.event("event2", 600, 650))
        self.save_inputs()
        summary = self.align(window_seconds=10, control_count=2, seed=13)
        first, second = self.rows(artifact="event_contrasts.csv")
        self.assertEqual("unmatched_or_excluded", first["comparison_status"])
        self.assertEqual(1, int(first["control_count"]))
        self.assertEqual("False", first["controls_reserved_for_matched_analysis"])
        partial = json.loads(first["controls"])
        self.assertEqual(115, partial[0]["playback_seconds"])
        self.assertFalse(partial[0]["reserved_for_matched_analysis"])
        self.assertEqual("exploratory_matched", second["comparison_status"])
        self.assertEqual("True", second["controls_reserved_for_matched_analysis"])
        complete = json.loads(second["controls"])
        self.assertEqual({100, 130}, {control["playback_seconds"] for control in complete})
        self.assertTrue(all(control["reserved_for_matched_analysis"] for control in complete))
        self.assertEqual(1, summary["matched_event_onset_count"])
        self.assertEqual(2, summary["matched_control_count"])
        self.assertEqual("fully_matched_event_onsets_only", summary["parameters"]["control_nonreuse_scope"])
        self.assertIn("chronological_event_onsets", summary["parameters"]["control_allocation_policy"])

    def test_synthetic_and_assistant_annotations_cannot_become_confirmed_research_evidence(self):
        for method in ("synthetic", "assistant"):
            with self.subTest(method=method):
                self.annotations["annotation_method"] = method
                self.save_inputs()
                summary = self.align(method, window_seconds=10, control_count=1)
                self.assertEqual("exploratory", summary["status"])
                self.assertTrue(summary["research_interpretation_status"].startswith("blocked"))
                self.assertIn(method+"_annotations_not_human_ground_truth", summary["quality_flags"])
                self.assertIsNone(summary["p_value"])

    def test_actual_m3_unclassified_candidates_supply_only_explicitly_provisional_rates(self):
        for boundary in self.shots["boundaries"]:
            boundary["transition_type"] = "unclassified_cut_candidate"
            boundary["validation_status"] = "unreviewed_prediction"
        self.save_inputs()
        summary = self.align(window_seconds=10, control_count=1)
        row = self.rows(artifact="event_contrasts.csv")[0]
        self.assertEqual("at_cut", row["boundary_position"])
        self.assertAlmostEqual(3, float(row["window_cutting_rate_per_minute"]))
        self.assertEqual("unclassified_cut_candidate", row["matched_transition_type"])
        self.assertEqual("unreviewed_prediction", row["matched_boundary_validation_status"])
        self.assertIn("cutting_rates_use_unreviewed_cut_candidates", summary["quality_flags"])
        self.assertTrue(summary["research_interpretation_status"].startswith("blocked"))
        self.assertEqual("unclassified_cut_candidate", json.loads(row["controls"])[0]["transition_type"])

    def test_human_annotations_and_human_reviewed_shots_still_require_interpretation_review(self):
        self.annotations["annotation_method"] = "human"  # Explicitly synthetic fixture exercising a branch.
        for record in self.shots["shots"]+self.shots["boundaries"]:
            record["validation_status"] = "human_reviewed"
        self.save_inputs()
        summary = self.align(window_seconds=10, control_count=1)
        self.assertEqual("review_required", summary["research_interpretation_status"])
        self.assertEqual("exploratory", summary["status"])
        self.assertIsNone(summary["p_value"])

    def test_annotation_set_declared_draft_cannot_pass_research_review_gate(self):
        self.annotations["annotation_method"] = "human"  # Synthetic branch fixture, no real human annotation.
        self.annotations["annotation_status"] = "template_not_ready"
        for record in self.shots["shots"]+self.shots["boundaries"]:
            record["validation_status"] = "human_reviewed"
        self.save_inputs()
        summary = self.align(window_seconds=10, control_count=1)
        self.assertIn("annotations_declared_not_ready", summary["quality_flags"])
        self.assertTrue(summary["research_interpretation_status"].startswith("blocked"))

    def test_shot_segmentation_revision_does_not_invalidate_independent_time_annotations(self):
        self.annotations["segmentation_id"] = "earlier-shot-segmentation"
        self.save_inputs()
        summary = self.align(window_seconds=10, control_count=1)
        self.assertEqual(self.shots["segmentation_id"], summary["segmentation_id"])
        self.assertIn("annotation_provenance_refers_to_different_segmentation", summary["quality_flags"])

    def test_wrong_film_scope_or_exact_video_version_is_rejected_without_output(self):
        for field, value in (("film_reference", {"namespace": "different-catalog", "key": "film"}),
                             ("video_version_id", "sha256:"+"2"*64)):
            with self.subTest(field=field):
                original = self.annotations[field]
                self.annotations[field] = value
                self.save_inputs()
                with self.assertRaises(narrative.NarrativeError):
                    self.align(field)
                self.assertFalse((self.root/field).exists())
                self.annotations[field] = original

    def test_invalid_annotations_fail_without_fabricating_or_dropping_events(self):
        baseline = copy.deepcopy(self.annotations)
        alternatives = [
            {"events": []}, {"annotator": ""}, {"annotation_method": "automatic"},
            {"time_reference": "frame_number"}, {"independent_of_visual_measurements": 1},
            {"events": [self.event("bad", -1, 20)]}, {"events": [self.event("bad", 200, 3001)]},
            {"events": [self.event("bad", 300, 300)]}, {"events": [self.event("bad", True, 300)]},
            {"events": [self.event("bad", 300, 350, certainty="probably")]},
            {"events": [self.event("same", 300, 350), self.event("same", 400, 450)]},
        ]
        for index, changes in enumerate(alternatives):
            with self.subTest(changes=changes):
                self.annotations = dict(copy.deepcopy(baseline), **changes)
                self.save_inputs()
                with self.assertRaises(narrative.NarrativeError):
                    self.align("invalid"+str(index))
                self.assertFalse((self.root/("invalid"+str(index))).exists())

    def test_invalid_shot_timing_duplicate_ids_and_boundary_joins_are_rejected(self):
        baseline = copy.deepcopy(self.shots)
        for index, mutation in enumerate((
            lambda data:data["shots"][0].update(duration_seconds=-1),
            lambda data:data["shots"][1].update(shot_id="shot0"),
            lambda data:data["shots"][1].update(start_source_seconds=100.5),
            lambda data:data["shots"][0].update(start_pts=9999),
            lambda data:data["boundaries"][0].update(source_seconds=200),
            lambda data:data["boundaries"][0].update(local_frame_interval_seconds=0),
            lambda data:data.update(boundaries=[]),
        )):
            with self.subTest(index=index):
                self.shots = copy.deepcopy(baseline)
                mutation(self.shots)
                self.save_inputs()
                with self.assertRaises(narrative.NarrativeError):
                    self.align("badshot"+str(index))
                self.assertFalse((self.root/("badshot"+str(index))).exists())

    def test_outputs_include_input_and_artifact_checksums_without_modifying_annotations(self):
        shots_before, annotations_before = self.shots_path.read_bytes(), self.annotations_path.read_bytes()
        summary = self.align(window_seconds=10, control_count=1)
        run = self.document("run.json")
        self.assertEqual(summary["run_id"], run["run_id"])
        self.assertEqual(hashlib.sha256(shots_before).hexdigest(), run["inputs"]["shots"]["sha256"])
        self.assertEqual(hashlib.sha256(annotations_before).hexdigest(), run["inputs"]["annotations"]["sha256"])
        for artifact, evidence in run["outputs"].items():
            content = (self.root/"alignment"/artifact).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), evidence["sha256"])
            self.assertEqual(len(content), evidence["size_bytes"])
        self.assertEqual(shots_before, self.shots_path.read_bytes())
        self.assertEqual(annotations_before, self.annotations_path.read_bytes())

    def test_existing_output_is_preserved_and_invalid_parameters_do_not_publish(self):
        directory = self.root/"existing"
        directory.mkdir()
        sentinel = directory/"keep"
        sentinel.write_bytes(b"previous output")
        with self.assertRaises(narrative.NarrativeError):
            self.align("existing")
        self.assertEqual(b"previous output", sentinel.read_bytes())
        for index, parameters in enumerate(({"window_seconds": 0}, {"window_seconds": float("nan")},
                {"control_count": 0}, {"control_count": True}, {"seed": True}, {"boundary_tolerance_seconds": 0})):
            with self.subTest(parameters=parameters):
                with self.assertRaises(narrative.NarrativeError):
                    self.align("invalidparameter"+str(index), **parameters)
                self.assertFalse((self.root/("invalidparameter"+str(index))).exists())


if __name__ == "__main__":
    unittest.main()
