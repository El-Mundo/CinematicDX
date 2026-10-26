"""Pure synthetic fixtures validate the local coarse-time pilot protocol."""

import copy
import json
import unittest

from cinematicdx.pilot_compare import PilotCompareError, compute_pilot_comparison


class PilotCompareTests(unittest.TestCase):
    def setUp(self):
        reference = {"namespace": "synthetic-unit-fixture", "key": "film"}
        version = "sha256:"+"1"*64
        self.annotations = {"schema_version": 1, "film_reference": reference, "video_version_id": version,
            "annotation_set_id": "synthetic-branch-fixture", "annotation_method": "human",
            "independent_of_visual_measurements": True, "exhaustive_within_coverage": True,
            "time_reference": "playback_seconds", "coverage": {"start_seconds":150,"end_seconds":750},
            "events": [self.event("E001",150,200), self.event("E002",300,350),
                       self.event("E003",500,550), self.event("E011",700,None)]}
        self.shots = {"schema_version": 1, "film_reference": reference, "video_version_id": version,
            "segmentation_id": "synthetic-shots", "coverage": {"start_source_seconds":0.043,
            "end_source_seconds":900.043,"start_playback_seconds":0,"end_playback_seconds":900},
            "shots": [], "boundaries": []}
        for index in range(45):
            first, last = index*20, (index+1)*20
            self.shots["shots"].append({"shot_id":"s"+str(index),"start_pts":first*1000+43,
                "end_pts":last*1000+43,"time_base":"1/1000","start_source_seconds":first+0.043,
                "end_source_seconds":last+0.043,"start_playback_seconds":first,"end_playback_seconds":last,
                "duration_seconds":20,"validation_status":"unreviewed_prediction"})
            if index:
                self.shots["boundaries"].append({"boundary_id":"b"+str(index),"pts":first*1000+43,
                    "time_base":"1/1000","source_seconds":first+0.043,"playback_seconds":first,
                    "transition_type":"unclassified_cut_candidate","validation_status":"unreviewed_prediction"})
        self.reference = {"schema_version":1,"film_reference":reference,"video_version_id":version,
            "coverage":{"start_seconds":150,"end_seconds":750},"annotation_method":"human",
            "independent_of_predictions":True,"exhaustive_within_coverage":True,
            "scenarios":[{"scenario_id":"base0","time_basis_description":"synthetic unconfirmed basis",
                          "hard_cuts":[{"cut_id":"c"+str(index),"playback_seconds":second}
                              for index,second in enumerate([180,220,240,260,280,300,400,420,440,480,500,600,620,640,660,700,720])],
                          "gradual_transitions":[],"outside_coverage_observations":[]}]}

    def event(self, event_id, first, last):
        event = {"event_id":event_id,"label":"synthetic test event","start_seconds":first,
                 "end_seconds":last,"observed_start_seconds":first,
                 "observed_end_seconds":750 if last is None else last,"certainty":"certain",
                 "start_boundary_kind":None,"end_boundary_kind":None}
        if last is None:
            event.update(end_right_censored=True,end_boundary_kind="window_truncated")
        return event

    def compute(self):
        return compute_pilot_comparison(self.annotations,self.shots,self.reference)

    def design_rows(self,result,window=30,jitter=0,scenario="base0"):
        return [row for row in result["comparisons"] if row["window_seconds"]==window
                and row["jitter_seconds"]==jitter and row["scenario_id"]==scenario]

    def test_pure_api_preserves_inputs_and_returns_json_serializable_diagnostics(self):
        originals = copy.deepcopy((self.annotations,self.shots,self.reference))
        result = self.compute()
        self.assertEqual(originals,(self.annotations,self.shots,self.reference))
        json.dumps(result,allow_nan=False)
        self.assertEqual("exploratory_diagnostics_only",result["status"])
        self.assertIsNone(result["p_value"])
        self.assertEqual(4,result["event_count"])
        self.assertEqual(9,len(result["design_summaries"]))
        self.assertEqual(36,len(result["comparisons"]))

    def test_right_censored_true_end_remains_null_and_750_is_not_an_extra_event(self):
        result = self.compute()
        last = next(event for event in result["event_records"] if event["event_id"]=="E011")
        self.assertIsNone(last["true_end_seconds"])
        self.assertIsNone(last["original_record"]["end_seconds"])
        self.assertEqual(750,last["observed_end_seconds"])
        self.assertTrue(last["end_right_censored"])
        rows = [row for row in result["event_shot_overlaps"] if row["event_id"]=="E011"]
        self.assertAlmostEqual(50,sum(row["overlap_seconds"] for row in rows))
        self.assertTrue(all(row["true_event_end_seconds"] is None for row in rows))
        self.assertTrue(all(row["overlap_end_playback_seconds"]<=750 for row in rows))
        self.assertNotIn(750,{row["original_onset_seconds"] for row in result["comparisons"]})

    def test_coverage_start_record_is_not_jittered_into_an_inferred_narrative_boundary(self):
        result = self.compute()
        rows = [row for row in result["comparisons"] if row["event_id"]=="E001"]
        self.assertEqual({150},{row["analysis_onset_seconds"] for row in rows})
        self.assertTrue(all("coverage_edge_onset_not_evaluated" in row["reasons"] for row in rows))
        self.assertTrue(all(row["control"] is None for row in rows))

    def test_misinterpreted_boundary_kind_fields_have_no_effect(self):
        before = self.compute()
        for event in self.annotations["events"]:
            event["start_boundary_kind"]="真实边界"
            event["end_boundary_kind"]="时间连续"
        after = self.compute()
        self.assertEqual(before["comparisons"],after["comparisons"])
        self.assertEqual(before["design_summaries"],after["design_summaries"])
        self.assertFalse(after["parameters"]["boundary_kind_fields_used"])

    def test_central_plus_minus_one_second_is_excluded_from_counts_and_exposure(self):
        seconds = [220,270,298,299,299.5,300,300.5,301,302,330,400,600]
        self.reference["scenarios"][0]["hard_cuts"] = [
            {"cut_id":"edge"+str(index),"playback_seconds":second} for index,second in enumerate(seconds)]
        result = self.compute()
        row = next(row for row in self.design_rows(result) if row["event_id"]=="E002")
        rates = row["event_rates"]
        self.assertEqual(2,rates["before_cut_count"])
        self.assertEqual(1,rates["after_cut_count"])
        self.assertEqual(5,rates["central_excluded_cut_count"])
        self.assertEqual(29,rates["before_exposure_seconds"])
        self.assertEqual(29,rates["after_exposure_seconds"])
        self.assertAlmostEqual(120/29,rates["before_cut_rate_per_minute"])
        self.assertAlmostEqual(-60/29,rates["rate_change_per_minute"])
        self.assertEqual(29,row["control"]["before_exposure_seconds"])
        self.assertGreaterEqual(row["control"]["central_excluded_cut_count"],1)

    def test_all_exploratory_windows_have_correct_reduced_exposure(self):
        result = self.compute()
        for window,exposure in ((30,29),(15,14),(10,9)):
            row = next(row for row in self.design_rows(result,window) if row["event_id"]=="E002")
            self.assertEqual(exposure,row["event_rates"]["before_exposure_seconds"])
            self.assertEqual(exposure,row["event_rates"]["after_exposure_seconds"])

    def test_controls_stay_in_interval_and_region_and_are_nonoverlapping_nonreused(self):
        result = self.compute()
        for summary in result["design_summaries"]:
            rows = self.design_rows(result,summary["window_seconds"],summary["jitter_seconds"])
            window = summary["window_seconds"]
            controls = []
            for row in rows:
                if row["control"] is None:
                    continue
                second = row["control"]["playback_seconds"]
                self.assertGreaterEqual(second-window,150)
                self.assertLessEqual(second+window,750)
                self.assertEqual(row["timeline_third"],min(2,int((second-150)/200))+1)
                for event_row in rows:
                    self.assertGreaterEqual(abs(second-event_row["analysis_onset_seconds"])+1e-6,2*window)
                for previous in controls:
                    self.assertGreaterEqual(abs(second-previous["playback_seconds"])+1e-6,2*window)
                controls.append(row["control"])
            self.assertEqual(len(controls),len({control["cut_id"] for control in controls}))

    def test_crowded_primary_windows_return_no_comparison_without_tuning_design(self):
        onsets = [150,198,247,303,360,549,591,611,664,726,734]
        self.annotations["events"] = [self.event("E%03d"%(index+1),first,
            onsets[index+1] if index+1<len(onsets) else None) for index,first in enumerate(onsets)]
        result = self.compute()
        self.assertEqual(0,result["primary_summaries"][0]["matched_event_onset_count"])
        self.assertIsNone(result["primary_summaries"][0]["mean_event_minus_control_rate_change_per_minute"])
        self.assertEqual("no_identifiable_matched_comparison",result["primary_summaries"][0]["status"])
        for row in self.design_rows(result):
            self.assertTrue(row["reasons"])
            self.assertIsNone(row["event_minus_control_rate_change_per_minute"])
        self.assertEqual([15,10],result["parameters"]["exploratory_window_seconds"])
        self.assertEqual(30,result["parameters"]["primary_window_seconds"])

    def test_jitter_is_explicit_global_sensitivity_and_never_snaps_to_cuts(self):
        result = self.compute()
        for jitter in (-1,0,1):
            row = next(row for row in self.design_rows(result,jitter=jitter) if row["event_id"]=="E002")
            self.assertEqual(300+jitter,row["analysis_onset_seconds"])
            self.assertEqual(300,row["original_onset_seconds"])
            self.assertEqual("not_assessed_second_level_annotation",row["event_to_cut_relationship"])
        self.assertIn("sensitivity_settings_are_not_confidence_intervals",result["quality_flags"])

    def test_frame_base_hypotheses_are_separate_and_never_selected_or_pooled(self):
        alternative = copy.deepcopy(self.reference["scenarios"][0])
        alternative["scenario_id"]="base1"
        for cut in alternative["hard_cuts"]:
            cut["playback_seconds"] -= 0.04
        self.reference["scenarios"].append(alternative)
        result = self.compute()
        self.assertEqual({"base0","base1"},{summary["scenario_id"] for summary in result["primary_summaries"]})
        self.assertEqual(18,len(result["design_summaries"]))
        self.assertEqual(2,len(result["cut_count_description"]))
        self.assertNotIn("best_scenario",result)
        self.assertIn("manual_frame_counter_time_basis_unconfirmed_conditional_scenarios",result["quality_flags"])

    def test_gradual_transitions_and_outside_observations_are_not_hard_cut_counts(self):
        before = self.compute()
        self.reference["scenarios"][0]["gradual_transitions"] = [
            {"transition_id":"g1","start_playback_seconds":280,"end_playback_seconds":282}]
        self.reference["scenarios"][0]["hard_cuts"].append({"cut_id":"outside","playback_seconds":754.8})
        result = self.compute()
        self.assertEqual(before["comparisons"],result["comparisons"])
        description = result["cut_count_description"][0]
        self.assertEqual(1,description["manual_gradual_transition_count"])
        self.assertEqual(17,description["manual_hard_cut_count"])
        self.assertEqual(30,description["automatic_cut_candidate_count"])
        self.assertEqual("outside",description["outside_coverage_observations"][0]["cut_id"])
        self.assertFalse(description["accuracy_metrics_computed"])

    def test_deterministic_matching_has_no_random_or_input_side_effects(self):
        self.assertEqual(self.compute(),self.compute())

    def test_missing_independence_or_completeness_is_not_silently_accepted(self):
        for data,field in ((self.annotations,"independent_of_visual_measurements"),
                           (self.annotations,"exhaustive_within_coverage"),
                           (self.reference,"independent_of_predictions"),
                           (self.reference,"exhaustive_within_coverage")):
            with self.subTest(field=field):
                data[field]=None
                with self.assertRaises(PilotCompareError):
                    self.compute()
                data[field]=True

    def test_wrong_film_video_or_coverage_cannot_be_compared(self):
        for name,value in (("video_version_id","sha256:"+"2"*64),
                           ("film_reference",{"namespace":"other","key":"film"}),
                           ("coverage",{"start_seconds":0,"end_seconds":900})):
            with self.subTest(field=name):
                original = self.annotations[name]
                self.annotations[name]=value
                with self.assertRaises(PilotCompareError):
                    self.compute()
                self.annotations[name]=original

    def test_missing_end_without_censoring_and_invented_observed_end_are_rejected(self):
        last = self.annotations["events"][-1]
        last["end_right_censored"]=False
        with self.assertRaises(PilotCompareError):
            self.compute()
        last["end_right_censored"]=True
        last["observed_end_seconds"]=740
        with self.assertRaises(PilotCompareError):
            self.compute()

    def test_duplicate_event_ids_and_cut_ids_or_times_fail_explicitly(self):
        self.annotations["events"].append(copy.deepcopy(self.annotations["events"][0]))
        with self.assertRaises(PilotCompareError):
            self.compute()
        self.annotations["events"].pop()
        cuts = self.reference["scenarios"][0]["hard_cuts"]
        cuts.append(copy.deepcopy(cuts[0]))
        with self.assertRaises(PilotCompareError):
            self.compute()
        cuts[-1]["cut_id"]="another-id-same-time"
        with self.assertRaises(PilotCompareError):
            self.compute()

    def test_shared_event_onset_does_not_create_two_independent_analysis_units(self):
        self.annotations["events"].append(self.event("layer",300,400))
        result = self.compute()
        self.assertEqual(5,result["event_count"])
        self.assertEqual(4,result["primary_summaries"][0]["distinct_onset_count"])
        row = next(row for row in self.design_rows(result) if row["event_id"]=="E002")
        self.assertEqual(["E002","layer"],row["linked_event_ids"])
        self.assertTrue(any(row["event_id"]=="layer" for row in result["event_shot_overlaps"]))


if __name__ == "__main__":
    unittest.main()
