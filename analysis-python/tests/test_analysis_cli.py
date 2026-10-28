"""Analysis CLI dispatch preserves explicit timing, methods and annotation inputs."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from cinematicdx.cli import main
from cinematicdx.shots import ShotError


class AnalysisCliTests(unittest.TestCase):
    def invoke(self, arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_shot_cli_preserves_clip_source_choices_and_explicit_monochrome_mode(self):
        with patch("cinematicdx.shots.detect_shots", return_value={"shot_count": 8}) as detect:
            status, output, errors = self.invoke(["shots", "--manifest", "source.json", "--output", "new",
                "--start-seconds", "300.02", "--end-seconds", "420", "--luma-only", "--analysis-width", "360"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output), {"shot_count":8})
        self.assertEqual(errors, "")
        self.assertEqual(detect.call_args.args, ("source.json", "new"))
        self.assertEqual(detect.call_args.kwargs["start_seconds"], 300.02)
        self.assertTrue(detect.call_args.kwargs["luma_only"])
        self.assertIsNone(detect.call_args.kwargs["threshold"])
        self.assertEqual(detect.call_args.kwargs["analysis_width"], 360)

    def test_failed_detector_cannot_print_a_success_receipt(self):
        with patch("cinematicdx.shots.detect_shots", side_effect=ShotError("PTS missing")):
            status, output, errors = self.invoke(["shots", "--manifest", "source.json", "--output", "new"])
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("PTS missing", errors)

    def test_narrative_template_does_not_invoke_event_alignment(self):
        with patch("cinematicdx.narrative.prepare_annotation_template", return_value={"status":"annotation_required"}) as template, \
                patch("cinematicdx.narrative.align_narrative") as align:
            status, _, _ = self.invoke(["annotation-template", "--shots", "shots.json", "--output", "new"])
        self.assertEqual(status, 0)
        template.assert_called_once_with("shots.json", "new")
        align.assert_not_called()

    def test_alignment_uses_supplied_annotations_and_fixed_matching_parameters(self):
        with patch("cinematicdx.narrative.align_narrative", return_value={"status":"exploratory"}) as align:
            status, _, _ = self.invoke(["align-narrative", "--shots", "shots.json", "--annotations", "events.json",
                "--output", "new", "--window-seconds", "30", "--control-count", "3", "--seed", "7"])
        self.assertEqual(status, 0)
        align.assert_called_once_with("shots.json", "events.json", "new", window_seconds=30.0, control_count=3, seed=7)

    def test_boundary_evaluation_uses_an_explicit_reference_and_tolerance(self):
        with patch("cinematicdx.validation.validate_shots", return_value={"status":"scored"}) as validate:
            status, _, _ = self.invoke(["validate-shots", "--shots", "shots.json", "--reference", "reference.json",
                "--output", "new", "--tolerance-seconds", ".04"])
        self.assertEqual(status, 0)
        validate.assert_called_once_with("shots.json", "reference.json", "new", tolerance_seconds=.04)


if __name__ == "__main__":
    unittest.main()
