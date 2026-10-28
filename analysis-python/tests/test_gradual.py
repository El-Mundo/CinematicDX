"""Synthetic mechanism tests; no research video, labels or reference paths read."""

import copy
import unittest

import numpy as np

from cinematicdx.gradual import (
    DEFAULT_CONFIG, GradualError, _motion, _nms, configuration_presets,
    detect_gradual_candidates,
)


class GradualTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1985)
        self.first = rng.uniform(0.12,0.88,(12,16))
        self.last = rng.uniform(0.12,0.88,(12,16))
        self.t = np.arange(200,dtype=float)/25

    def features(self, frames, times=None):
        times = self.t if times is None else np.asarray(times,dtype=float)
        frames = np.asarray(frames)
        gray = np.rint(np.clip(frames,0,1)*255).astype(np.uint8)
        gray = np.repeat(np.repeat(gray,4,axis=1),4,axis=2)
        normalized = gray.astype(float)/255
        delta = np.r_[np.diff(times),times[-1]-times[-2]]
        mad = np.r_[np.nan,np.abs(np.diff(normalized,axis=0)).mean(axis=(1,2))]
        return {"gray_cache":gray,"playback_seconds":times,"source_seconds":times+0.043,
                "frame_delta_seconds":delta,"pts":np.rint((times+0.043)*16000).astype(np.int64),
                "next_pts":np.rint((times+delta+0.043)*16000).astype(np.int64),
                "evaluation_mask":np.ones(len(times),dtype=bool),"evaluation_overlap_seconds":delta.copy(),
                "roi_mean":normalized.mean(axis=(1,2)),"roi_std":normalized.std(axis=(1,2)),
                "adjacent_mad":mad,"valid_mask":np.isfinite(mad)}

    def mix(self, times=None, first=None, last=None):
        times = self.t if times is None else times
        alpha = np.clip((times-2)/1.6,0,1)[:,None,None]
        first = self.first if first is None else first
        last = self.last if last is None else last
        return self.features((1-alpha)*first+alpha*last,times)

    def config(self, **values):
        return {"motion_diagnostics":False,**values}

    def overlaps(self, prediction, first, last):
        intersection = max(0,min(prediction["end_playback_seconds"],last)-max(prediction["start_playback_seconds"],first))
        union = max(prediction["end_playback_seconds"],last)-min(prediction["start_playback_seconds"],first)
        return intersection/union

    def test_linear_dissolve_is_detected_as_interval_with_inspectable_nonprobability_fit(self):
        result = detect_gradual_candidates(self.mix(),config=self.config())
        predictions = [row for row in result["predictions"] if row["predicted_type"]=="dissolve"]
        self.assertTrue(predictions)
        self.assertGreater(max(self.overlaps(row,2,3.6) for row in predictions),0.5)
        for row in predictions:
            self.assertEqual("heuristic_fit_not_probability",row["score_kind"])
            self.assertIn("normalized_blend_rms_residual",row["metrics"])
            self.assertEqual("unreviewed_algorithmic_prediction",row["validation_status"])
            self.assertGreater(row["end_pts"],row["start_pts"])
        self.assertGreater(result["diagnostics"]["endpoint_mixing_windows_scanned"],0)

    def test_fade_out_and_in_with_black_hold_are_distinct_from_general_dissolve(self):
        out = 1-np.clip((self.t-2)/1.6,0,1)
        incoming = np.clip((self.t-5)/1.6,0,1)
        frames = out[:,None,None]*self.first+incoming[:,None,None]*self.last
        result = detect_gradual_candidates(self.features(frames),config=self.config())
        self.assertTrue(result["black_holds"])
        types = {row["predicted_type"] for row in result["predictions"]}
        self.assertIn("fade_out",types)
        self.assertIn("fade_in",types)
        # Partial fade windows need not themselves contain black. The final NMS
        # output must retain the stronger complete fade branch, without treating
        # every raw subwindow as an already classified physical transition.
        self.assertTrue(all(row["predicted_type"]!="dissolve" for row in result["predictions"]
                            if row["start_playback_seconds"]>=1.5 and row["end_playback_seconds"]<=4))

    def test_fade_only_baseline_does_not_run_endpoint_mixing_scan(self):
        config = configuration_presets()["fade_only_baseline"]
        config["motion_diagnostics"] = False
        result = detect_gradual_candidates(self.mix(),config=config)
        self.assertEqual(0,result["diagnostics"]["endpoint_mixing_windows_scanned"])
        self.assertEqual([],result["predictions"])

    def test_mixing_branch_alone_types_a_constant_black_endpoint_as_fade(self):
        result = detect_gradual_candidates(self.mix(last=np.zeros((12,16))),
                                           config=self.config(enable_fades=False))
        self.assertTrue(result["predictions"])
        self.assertEqual({"fade_out"},{row["predicted_type"] for row in result["predictions"]})

    def test_hard_cut_is_not_relabelled_as_a_gradual_transition(self):
        frames = np.where((self.t<3)[:,None,None],self.first,self.last)
        result = detect_gradual_candidates(self.features(frames),config=self.config())
        self.assertEqual([],result["predictions"])
        self.assertGreater(result["diagnostics"]["rejection_counts"].get("alpha_trajectory_or_spike",0),0)

    def test_abrupt_cut_to_black_is_not_a_fade(self):
        frames = np.where((self.t<3)[:,None,None],self.first,np.zeros((12,16)))
        result = detect_gradual_candidates(self.features(frames),config=self.config())
        self.assertTrue(result["black_holds"])
        self.assertEqual([],result["predictions"])

    def test_brief_flash_returning_to_same_shot_is_not_a_gradual_transition(self):
        frames = np.repeat(self.first[None,:,:],len(self.t),axis=0)
        frames[(self.t>=3)&(self.t<3.12)] = 1
        result = detect_gradual_candidates(self.features(frames),config=self.config())
        self.assertEqual([],result["predictions"])

    def test_fast_textured_pan_has_high_blend_error_and_is_not_detected(self):
        # Discrete 12-pixel translation in 1.2 seconds, not a blended dissolve.
        shifts = np.floor(np.clip((self.t-2)/1.2,0,1)*12).astype(int)
        frames = np.array([np.roll(self.first,shift,axis=1) for shift in shifts])
        result = detect_gradual_candidates(self.features(frames),config=self.config())
        self.assertEqual([],result["predictions"])
        self.assertGreater(result["diagnostics"]["rejection_counts"].get("blend_residual",0),0)

    def test_correlated_photometric_ramp_is_flagged_as_a_known_nonidentifiability(self):
        # The same spatial structure with a brightness offset fits linear mixing;
        # this test records the weakness instead of tuning it away after scoring.
        first = self.first*0.5
        result = detect_gradual_candidates(self.mix(first=first,last=first+0.2),config=self.config())
        self.assertTrue(result["predictions"])
        self.assertTrue(any("high_endpoint_correlation_photometric_change_explanation_possible" in row["quality_flags"]
                            for row in result["predictions"]))
        self.assertTrue(any(row["metrics"]["variance_dip_auxiliary"]<0.05 for row in result["predictions"]))

    def test_irregular_vfr_timestamps_determine_coordinates_without_nominal_fps(self):
        times = np.r_[0,np.cumsum(np.tile([0.04,0.08],80))]
        result = detect_gradual_candidates(self.mix(times),config=self.config())
        self.assertTrue(result["predictions"])
        for row in result["predictions"]:
            self.assertAlmostEqual(row["start_pts"]/16000,row["start_source_seconds"])
            self.assertAlmostEqual(row["end_pts"]/16000,row["end_source_seconds"])
            self.assertAlmostEqual(0.043,row["start_source_seconds"]-row["start_playback_seconds"])

    def test_highly_overlapping_candidates_are_suppressed_with_an_audit_trail(self):
        rows = [{"candidate_id":"a","score":0.9,"start_playback_seconds":1,"end_playback_seconds":2},
                {"candidate_id":"b","score":0.8,"start_playback_seconds":1.02,"end_playback_seconds":2.04},
                {"candidate_id":"c","score":0.7,"start_playback_seconds":3,"end_playback_seconds":4}]
        accepted,suppressed = _nms(rows,DEFAULT_CONFIG)
        self.assertEqual(["a","c"],[row["candidate_id"] for row in accepted])
        self.assertEqual([{"candidate_id":"b","suppressed_by":"a","reason":"overlapping_interval_nms"}],suppressed)

    def test_four_presets_are_explicit_and_return_independent_copies(self):
        presets = configuration_presets()
        self.assertEqual({"fade_only_baseline","default","lenient","strict"},set(presets))
        self.assertFalse(presets["fade_only_baseline"]["enable_dissolves"])
        self.assertLess(presets["lenient"]["endpoint_rms_min"],presets["default"]["endpoint_rms_min"])
        self.assertLess(presets["strict"]["blend_residual_max"],presets["default"]["blend_residual_max"])
        presets["default"]["durations_seconds"].append(99)
        self.assertNotIn(99,configuration_presets()["default"]["durations_seconds"])

    def test_inputs_and_requested_config_are_not_mutated(self):
        features = self.mix()
        before = {key:value.copy() for key,value in features.items()}
        config = self.config()
        requested = copy.deepcopy(config)
        detect_gradual_candidates(features,config=config)
        self.assertEqual(requested,config)
        for key in features:
            np.testing.assert_array_equal(before[key],features[key],err_msg=key)

    def test_output_uses_only_candidate_intervals_intersecting_evaluation_coverage(self):
        features = self.mix()
        features["evaluation_mask"] = (self.t>=5)&(self.t<7)
        features["evaluation_overlap_seconds"] = features["frame_delta_seconds"]*features["evaluation_mask"]
        result = detect_gradual_candidates(features,config=self.config())
        self.assertEqual([],result["predictions"])
        self.assertAlmostEqual(2,result["diagnostics"]["evaluation_exposure_seconds"])

    def test_invalid_units_timestamps_masks_or_config_are_rejected(self):
        changes = [lambda data:data.update(gray_cache=data["gray_cache"].astype(float)),
                   lambda data:data["frame_delta_seconds"].__setitem__(10,0),
                   lambda data:data["source_seconds"].__setitem__(10,999),
                   lambda data:data["roi_mean"].__setitem__(10,255),
                   lambda data:data.update(evaluation_mask=np.zeros(len(self.t),dtype=bool)),
                   lambda data:data["next_pts"].__setitem__(10,data["pts"][10])]
        for change in changes:
            with self.subTest(change=change):
                features = self.mix()
                change(features)
                with self.assertRaises(GradualError):
                    detect_gradual_candidates(features,config=self.config())
        for config in ({"scan_stride_seconds":0},{"unexpected":1},{"blend_residual_max":float("nan")}):
            with self.subTest(config=config):
                with self.assertRaises(GradualError):
                    detect_gradual_candidates(self.mix(),config=config)

    def test_optional_translation_diagnostic_reports_its_units_and_explanation(self):
        result = _motion(self.first,np.roll(self.first,2,axis=1),DEFAULT_CONFIG)
        if result["status"]=="unavailable":
            self.skipTest("Optional OpenCV phase correlation unavailable")
        self.assertEqual("performed",result["status"])
        self.assertEqual("reduced_analysis_image",result["pixel_units"])
        self.assertTrue(result["translation_explanation"])


if __name__ == "__main__":
    unittest.main()
