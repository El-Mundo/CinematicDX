import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cinematicdx import probe
from cinematicdx.probe import ProbeError, probe_video


def video_stream(index=2, default=1):
    return {
        "index": index, "codec_type": "video", "codec_name": "h264",
        "width": 640, "height": 480, "pix_fmt": "yuv420p",
        "time_base": "1/1000", "avg_frame_rate": "25/1", "r_frame_rate": "25/1",
        "start_pts": 5000, "start_time": "5.000000",
        "duration_ts": 10500, "duration": "10.500000", "nb_frames": "263",
        "disposition": {"attached_pic": 0, "default": default},
    }


def header():
    return {"streams": [{"index": 0, "codec_type": "audio"}, video_stream()],
            "format": {"format_name": "mov,mp4", "start_time": "5.000000", "duration": "10.500000"}}


def frame(pts=5000, index=2):
    return {"stream_index": index, "pts": pts, "pts_time": "%.6f" % (pts / 1000),
            "best_effort_timestamp": pts, "best_effort_timestamp_time": "%.6f" % (pts / 1000)}


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cinematicdx-probe-test-")
        self.addCleanup(self.temporary.cleanup)
        self.video = Path(self.temporary.name) / "film with spaces ; literal.mp4"
        self.video.write_bytes(b"mock video input")
        probe._probe_version.cache_clear()
        self.addCleanup(probe._probe_version.cache_clear)

    def mocked_probe(self, source_header=None, frames=None, **options):
        source_header = header() if source_header is None else source_header
        frames = [frame(), frame(5040), frame(5080)] if frames is None else frames
        calls = []

        def run(argv, **kwargs):
            calls.append((list(argv), kwargs))
            if "-version" in argv:
                stdout = "ffprobe version 6.0 test build\nlibavformat test\n"
            elif "-show_streams" in argv:
                stdout = json.dumps(source_header)
            elif "-show_frames" in argv:
                stdout = json.dumps({"frames": frames})
            else:
                self.fail("Unexpected command: %r" % argv)
            return subprocess.CompletedProcess(argv, 0, stdout, "")

        with mock.patch.object(probe.subprocess, "run", side_effect=run):
            result = probe_video(self.video, **options)
        return result, calls

    def test_preserves_source_coordinates_and_separates_playback_offsets(self):
        source_header = header()
        original = copy.deepcopy(source_header)
        result, calls = self.mocked_probe(source_header)
        self.assertEqual(result["raw_header"], original)
        self.assertEqual(source_header, original)
        summary = result["technical_summary"]
        self.assertEqual(summary["time_base"], "1/1000")
        self.assertEqual(summary["avg_frame_rate"], "25/1")
        self.assertEqual(summary["duration_rational"], "21/2")
        self.assertEqual(summary["duration_source"], "stream.duration_ts")
        self.assertEqual(summary["source_start_pts"], 5000)
        first, second = result["timestamp_sample"]["frames"][:2]
        self.assertEqual(first["pts"], 5000)
        self.assertEqual(first["pts_time"], "5.000000")
        self.assertEqual(first["source_seconds_rational"], "5/1")
        self.assertEqual(first["playback_offset_rational"], "0/1")
        self.assertEqual(second["playback_offset_rational"], "1/25")
        self.assertEqual(first["timestamp_source"], "pts")
        self.assertEqual(first["best_effort_timestamp"], 5000)
        self.assertIn("VFR_unknown", result["quality_flags"])
        self.assertEqual(summary["frame_rate_mode"], "unknown")
        self.assertFalse(result["full_decode_requested"])
        self.assertEqual(result["integrity_certification"], "not_performed")
        self.assertEqual(result["ffprobe"]["version"], "ffprobe version 6.0 test build")
        self.assertEqual(result["ffprobe"]["header_argv"], calls[1][0])
        self.assertEqual(result["ffprobe"]["timestamp_sample_argv"], calls[2][0])
        for argv, kwargs in calls:
            self.assertFalse(kwargs.get("shell", False))
            self.assertGreater(kwargs["timeout"], 0)
        self.assertEqual(calls[2][0][-1], str(self.video.resolve()))
        self.assertEqual(calls[2][0][calls[2][0].index("-read_intervals") + 1], "%+#48")
        self.assertNotIn("-count_frames", calls[1][0])

    def test_header_only_does_not_decode_and_allows_unvalidated_time_base(self):
        source_header = header()
        source_header["streams"][1]["time_base"] = "0/0"
        result, calls = self.mocked_probe(source_header, timestamp_sample_frames=0)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("-show_frames" not in argv for argv, _ in calls))
        self.assertEqual(result["timestamp_sample"]["coverage"], "not_performed")
        self.assertEqual(result["timestamp_sample"]["frames"], [])
        self.assertIsNone(result["ffprobe"]["timestamp_sample_argv"])
        self.assertIn("timing_not_validated", result["quality_flags"])
        self.assertIn("VFR_unknown", result["quality_flags"])

    def test_version_is_cached_across_header_only_inventory_calls(self):
        result, first_calls = self.mocked_probe(timestamp_sample_frames=0)
        again, next_calls = self.mocked_probe(timestamp_sample_frames=0)
        self.assertEqual(sum("-version" in argv for argv, _ in first_calls + next_calls), 1)
        self.assertEqual(result["ffprobe"]["version_output"], again["ffprobe"]["version_output"])

    def test_attached_picture_is_not_a_video_candidate(self):
        source_header = header()
        cover = video_stream(1)
        cover["disposition"]["attached_pic"] = 1
        source_header["streams"].append(cover)
        result, _ = self.mocked_probe(source_header)
        self.assertEqual(result["selected_video_stream_index"], 2)
        self.assertEqual(result["technical_summary"]["genuine_video_stream_count"], 1)

    def test_unique_default_selected_or_absolute_override_used(self):
        source_header = header()
        source_header["streams"].append(video_stream(4, default=0))
        result, _ = self.mocked_probe(source_header)
        self.assertEqual(result["selected_video_stream_index"], 2)
        override, calls = self.mocked_probe(source_header, frames=[frame(index=4)], stream_index=4)
        self.assertEqual(override["selected_video_stream_index"], 4)
        sample_argv = calls[-1][0]
        self.assertEqual(sample_argv[sample_argv.index("-select_streams") + 1], "4")

    def test_ambiguous_video_is_explicit_error(self):
        source_header = header()
        source_header["streams"].append(video_stream(4, default=1))
        with self.assertRaises(ProbeError) as caught:
            self.mocked_probe(source_header)
        self.assertEqual(caught.exception.code, "ambiguous_video_stream")

    def test_audio_only_and_picture_only_inputs_are_rejected(self):
        for streams in ([{"index": 0, "codec_type": "audio"}],
                        [{"index": 0, "codec_type": "video", "disposition": {"attached_pic": 1}}]):
            with self.subTest(streams=streams), self.assertRaises(ProbeError) as caught:
                self.mocked_probe({"streams": streams})
            self.assertEqual(caught.exception.code, "no_video_stream")

    def test_explicit_audio_stream_is_rejected(self):
        with self.assertRaises(ProbeError) as caught:
            self.mocked_probe(stream_index=0)
        self.assertEqual(caught.exception.code, "invalid_stream")

    def test_missing_pts_uses_best_effort_but_keeps_it_distinct(self):
        fallback = frame()
        fallback.pop("pts")
        fallback.pop("pts_time")
        result, _ = self.mocked_probe(frames=[fallback])
        record = result["timestamp_sample"]["frames"][0]
        self.assertIsNone(record["pts"])
        self.assertEqual(record["best_effort_timestamp"], 5000)
        self.assertEqual(record["timestamp_source"], "best_effort_timestamp")
        self.assertEqual(record["source_seconds"], 5.0)
        self.assertIn("missing_pts", result["quality_flags"])
        self.assertIn("best_effort_timestamp_used", result["quality_flags"])

    def test_no_usable_timed_frames_is_not_success(self):
        for frames in ([], [{"stream_index": 2, "pts": "N/A", "pts_time": "N/A"}]):
            with self.subTest(frames=frames), self.assertRaises(ProbeError) as caught:
                self.mocked_probe(frames=frames)
            self.assertEqual(caught.exception.code, "no_timed_frames")

    def test_invalid_time_base_is_not_replaced_with_nominal_fps(self):
        source_header = header()
        source_header["streams"][1]["time_base"] = "0/0"
        with self.assertRaises(ProbeError) as caught:
            self.mocked_probe(source_header)
        self.assertEqual(caught.exception.code, "invalid_time_base")

    def test_packet_limited_sample_retains_at_most_requested_records(self):
        result, _ = self.mocked_probe(frames=[frame(5000 + index * 40) for index in range(8)],
                                      timestamp_sample_frames=3)
        sample = result["timestamp_sample"]
        self.assertEqual(sample["requested_frames"], 3)
        self.assertEqual(sample["decoded_frames_returned"], 8)
        self.assertEqual(sample["recorded_frames"], 3)
        self.assertEqual(len(sample["frames"]), 3)
        self.assertEqual(sample["packet_limit"], 32)
        self.assertIn("sample_records_truncated", result["quality_flags"])
        self.assertIn("sample_limited", result["quality_flags"])

    def test_varying_sample_intervals_and_header_rates_do_not_classify_whole_file(self):
        source_header = header()
        source_header["streams"][1]["avg_frame_rate"] = "24/1"
        result, _ = self.mocked_probe(source_header, frames=[frame(), frame(5040), frame(5090)])
        self.assertTrue(result["timestamp_sample"]["observed_intervals"]["varied"])
        self.assertIn("sample_intervals_vary", result["quality_flags"])
        self.assertIn("header_frame_rates_differ", result["quality_flags"])
        self.assertIn("VFR_unknown", result["quality_flags"])

    def test_timing_disagreement_is_reported_without_overwriting_source_values(self):
        source_header = header()
        source_header["streams"][1]["start_time"] = "4.000000"
        mismatched = frame()
        mismatched["pts_time"] = "3.000000"
        result, _ = self.mocked_probe(source_header, frames=[mismatched])
        self.assertIn("timing_discrepancy", result["quality_flags"])
        self.assertEqual(result["timestamp_sample"]["frames"][0]["pts_time"], "3.000000")
        self.assertEqual(result["timestamp_sample"]["frames"][0]["source_seconds"], 5.0)
        self.assertEqual(result["technical_summary"]["source_start_time"], "4.000000")
        self.assertEqual(result["technical_summary"]["playback_origin"]["source"], "stream.start_pts")

    def test_absent_declared_start_uses_explicit_sample_origin(self):
        source_header = header()
        selected = source_header["streams"][1]
        selected.pop("start_pts")
        selected.pop("start_time")
        result, _ = self.mocked_probe(source_header)
        self.assertEqual(result["technical_summary"]["playback_origin"]["source"],
                         "first_usable_sample_timestamp")
        self.assertIn("playback_origin_from_sample", result["quality_flags"])

    def test_missing_input_and_invalid_sample_options_fail_before_subprocess(self):
        with mock.patch.object(probe.subprocess, "run") as run:
            for size in (-1, 257, True, 1.5):
                with self.subTest(size=size), self.assertRaises(ProbeError):
                    probe_video(self.video, timestamp_sample_frames=size)
            with self.assertRaises(ProbeError):
                probe_video(self.video.with_name("missing.mp4"))
            run.assert_not_called()

    def test_missing_tool_timeout_nonzero_and_invalid_json_are_typed_errors(self):
        cases = [
            (FileNotFoundError("not installed"), "tool_missing"),
            (subprocess.TimeoutExpired(["ffprobe"], 10), "tool_timeout"),
            (subprocess.CompletedProcess(["ffprobe"], 1, "", "invalid video"), "tool_failed"),
        ]
        for response, code in cases:
            probe._probe_version.cache_clear()
            kwargs = {"side_effect": response} if isinstance(response, Exception) else {"return_value": response}
            with self.subTest(code=code), mock.patch.object(probe.subprocess, "run", **kwargs):
                with self.assertRaises(ProbeError) as caught:
                    probe_video(self.video)
                self.assertEqual(caught.exception.code, code)
        probe._probe_version.cache_clear()
        responses = [subprocess.CompletedProcess([], 0, "ffprobe version 6.0", ""),
                     subprocess.CompletedProcess([], 0, "{not json}", "")]
        with mock.patch.object(probe.subprocess, "run", side_effect=responses):
            with self.assertRaises(ProbeError) as caught:
                probe_video(self.video)
            self.assertEqual(caught.exception.code, "invalid_json")


@unittest.skipUnless(shutil.which("ffprobe") and shutil.which("ffmpeg"), "ffprobe and ffmpeg required")
class TinyFixtureProbeTest(unittest.TestCase):
    def test_existing_tools_probe_a_tiny_generated_video_without_corpus_access(self):
        probe._probe_version.cache_clear()
        self.addCleanup(probe._probe_version.cache_clear)
        with tempfile.TemporaryDirectory(prefix="cinematicdx-probe-fixture-") as directory:
            video = Path(directory) / "tiny.mkv"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=32x32:r=5", "-t", "1", "-c:v", "ffv1", str(video)],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            result = probe_video(video, timestamp_sample_frames=3)
            self.assertEqual(result["technical_summary"]["width"], 32)
            self.assertEqual(result["selected_video_stream_index"], 0)
            self.assertGreater(result["timestamp_sample"]["recorded_frames"], 0)
            self.assertLessEqual(result["timestamp_sample"]["recorded_frames"], 3)
            self.assertEqual(result["timestamp_sample"]["frames"][0]["pts"], 0)
            self.assertIn("VFR_unknown", result["quality_flags"])
            self.assertEqual(result["integrity_certification"], "not_performed")


if __name__ == "__main__":
    unittest.main()
