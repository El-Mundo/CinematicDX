import json
from pathlib import Path
import tempfile
import unittest

from cinematicdx.reports import ReportError, local_cutting_rates, summarize_shots


class ReportTests(unittest.TestCase):
    def test_windows_use_half_open_support_and_actual_edge_exposure(self):
        rows = local_cutting_rates([1, 2, 3, 5], 0, 6, 4, 2)
        self.assertEqual([r["cut_candidate_count"] for r in rows], [1, 3, 3, 1])
        self.assertEqual([r["actual_window_seconds"] for r in rows], [2, 4, 4, 2])
        self.assertEqual(rows[0]["cut_candidates_per_minute"], 30)
        self.assertTrue(rows[0]["edge_truncated"])
        self.assertFalse(rows[1]["edge_truncated"])

    def test_boundaries_must_be_distinct_internal_and_finite(self):
        for cuts in [[0], [6], [2, 2], [float("nan")]]:
            with self.subTest(cuts=cuts), self.assertRaises(ReportError):
                local_cutting_rates(cuts, 0, 6)

    def test_summary_preserves_prediction_status_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = {"film_reference": {"namespace": "test", "key": "fixture"},
                    "video_version_id": "sha256:fixture", "segmentation_id": "fixture-run",
                    "coverage": {"start_playback_seconds": 0, "end_playback_seconds": 6},
                    "shots": [{"start_playback_seconds": a, "end_playback_seconds": b,
                               "duration_seconds": b-a, "validation_status": "unreviewed_prediction"}
                              for a,b in [(0,1), (1,2), (2,3), (3,5), (5,6)]],
                    "boundaries": [{"playback_seconds": t} for t in [1,2,3,5]]}
            source = root / "shots.json"
            source.write_text(json.dumps(data))
            result = summarize_shots(source, root / "report", render=False)
            self.assertEqual(result["shot_count"], 5)
            summary = json.loads((root / "report/summary.json").read_text())
            self.assertEqual(summary["validation_status_counts"], {"unreviewed_prediction": 5})
            self.assertAlmostEqual(summary["mean_duration_seconds"], 1.2)
            with self.assertRaises(ReportError):
                summarize_shots(source, root / "report", render=False)

    def test_inconsistent_coverage_is_not_reported_as_valid_statistics(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "shots.json"
            source.write_text(json.dumps({"coverage": {"start_playback_seconds":0,"end_playback_seconds":10},
                "shots":[{"duration_seconds":3,"start_playback_seconds":0,"end_playback_seconds":3}], "boundaries":[]}))
            with self.assertRaises(ReportError):
                summarize_shots(source, Path(folder) / "report", render=False)


if __name__ == "__main__":
    unittest.main()
