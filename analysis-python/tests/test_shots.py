"""Known synthetic cuts exercise source PTS, clipping, EOF and publication guards."""

import csv
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from cinematicdx import shots
from cinematicdx.shots import ShotError, detect_shots


class ShotPolicyTests(unittest.TestCase):
    def test_exact_duration_filter_records_suppressed_short_and_terminal_intervals(self):
        accepted, rejected = shots._filter_candidates(
            [40, 120, 220], [0, 40, 80, 120, 160, 200, 220], 240,
            Fraction(1, 1000), Fraction(1, 10))
        self.assertEqual([120], accepted)
        self.assertEqual({40, 220}, {row["pts"] for row in rejected})
        self.assertIn("terminal_interval_shorter_than_minimum", [row["reason"] for row in rejected])

    def test_detector_candidates_must_be_real_processed_frame_coordinates(self):
        with self.assertRaisesRegex(ShotError, "actually processed"):
            shots._filter_candidates([41], [0, 40, 80], 120, Fraction(1, 1000), Fraction(0))

    def test_invalid_options_are_rejected_before_reading_or_decoding(self):
        cases = [{"detector": "narrative"}, {"threshold": float("nan")},
                 {"threshold": 0}, {"min_shot_seconds": -1}, {"analysis_width": True},
                 {"analysis_width": 0}, {"start_seconds": -1},
                 {"start_seconds": 2, "end_seconds": 1},
                 {"luma_only": "true"}, {"min_content_value": -1}]
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(shots, "_load_manifest") as reader:
                for options in cases:
                    with self.subTest(options=options), self.assertRaises(ShotError):
                        detect_shots(Path(directory) / "missing.json", Path(directory) / "out", **options)
                reader.assert_not_called()


class SyntheticVideoShotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.dependencies = shots._load_dependencies()
        except ShotError as exc:
            raise unittest.SkipTest("Optional M3 environment unavailable: %s" % exc)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cinematicdx-shot-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.video = self.folder / "synthetic-source.mkv"
        self.manifest_path = self.folder / "source_manifest.json"
        self.make_fixture([1000 + index * 40 for index in range(15)])

    def make_fixture(self, timestamps, pixel_values=None, pixel_format="yuv420p"):
        av = self.dependencies["av"]
        numpy = self.dependencies["numpy"]
        with av.open(str(self.video), "w", format="matroska",
                     options={"avoid_negative_ts": "disabled"}) as container:
            stream = container.add_stream("ffv1", rate=25)
            stream.width, stream.height, stream.pix_fmt = 384, 96, pixel_format
            stream.time_base = Fraction(1, 1000)
            stream.codec_context.time_base = Fraction(1, 1000)
            for index, timestamp in enumerate(timestamps):
                pixels = (pixel_values(index) if pixel_values is not None else
                          numpy.full((96, 384, 3), 255 if 5 <= index < 10 else 0, dtype=numpy.uint8))
                frame = av.VideoFrame.from_ndarray(pixels, format="bgr24")
                frame.pts, frame.time_base = timestamp, Fraction(1, 1000)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        self.register_fixture()

    def register_fixture(self):
        av = self.dependencies["av"]
        with av.open(str(self.video)) as container:
            stream = container.streams.video[0]
            self.decoded_frames = list(container.decode(stream))
            self.stream_start, self.stream_duration = stream.start_time, stream.duration
            self.time_base = Fraction(stream.time_base)
        self.timestamps = [frame.pts for frame in self.decoded_frames]
        checksum = hashlib.sha256(self.video.read_bytes()).hexdigest()
        state = self.video.stat()
        self.manifest = {
            "schema_version": 1, "artifact_kind": "source_video_manifest",
            "film_reference": {"namespace": "synthetic-fixtures", "key": "known-three-shots"},
            "video_version_id": "sha256:" + checksum,
            "source": {"requested_path": str(self.video), "resolved_path": str(self.video),
                       "sha256": checksum, "size_bytes": state.st_size, "mtime_ns": state.st_mtime_ns},
            "selected_video_stream_index": 0,
            "timeline": {"time_base": str(self.time_base), "source_start_pts": self.stream_start,
                         "duration_ts": self.stream_duration,
                         "playback_origin": {"source_seconds_rational": str(self.timestamps[0] * self.time_base)}},
        }
        self.write_manifest()

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def document(self, output, name="shots.json"):
        return json.loads((self.folder / output / name).read_text(encoding="utf-8"))

    def run_detection(self, output="run", **parameters):
        return detect_shots(self.manifest_path, self.folder / output, **parameters)

    def test_known_cut_fixture_preserves_offsets_and_half_open_shots(self):
        source_bytes, manifest_bytes = self.video.read_bytes(), self.manifest_path.read_bytes()
        result = self.run_detection()
        document = self.document("run")
        self.assertEqual(3, result["shot_count"])
        self.assertEqual([1200, 1400], [row["pts"] for row in document["boundaries"]])
        self.assertEqual([(1000, 1200), (1200, 1400), (1400, 1600)],
                         [(row["start_pts"], row["end_pts"]) for row in document["shots"]])
        self.assertEqual("[start,end)", document["coverage"]["interval_convention"])
        self.assertEqual(1.0, document["coverage"]["start_source_seconds"])
        self.assertEqual(0.0, document["coverage"]["start_playback_seconds"])
        self.assertEqual(15, document["decode_audit"]["processed_frame_count"])
        self.assertFalse(document["decode_audit"]["frame_skipping"])
        self.assertEqual("last_decoded_frame_pts_plus_duration", document["coverage"]["end_basis"])
        self.assertTrue(all(row["validation_status"] == "unreviewed_prediction" for row in document["shots"]))
        self.assertTrue(all(row["transition_type"] == "unclassified_cut_candidate" for row in document["boundaries"]))
        self.assertTrue(all(row["confidence"] is None for row in document["boundaries"]))
        self.assertEqual(source_bytes, self.video.read_bytes())
        self.assertEqual(manifest_bytes, self.manifest_path.read_bytes())

    def test_vfr_boundary_times_and_eof_do_not_come_from_frame_count_or_fps(self):
        self.make_fixture([1000, 1040, 1080, 1160, 1200, 1280, 1320, 1440, 1480, 1520,
                           1640, 1680, 1760, 1800, 1880])
        self.run_detection()
        document = self.document("run")
        self.assertEqual([1280, 1640], [row["pts"] for row in document["boundaries"]])
        self.assertEqual([0.28, 0.64], [row["playback_seconds"] for row in document["boundaries"]])
        self.assertEqual(1920, document["coverage"]["end_pts"])
        self.assertEqual([0.08, 0.12], [row["local_frame_interval_seconds"] for row in document["boundaries"]])
        self.assertEqual("7/25", document["shots"][0]["duration_rational"])
        self.assertEqual("1/1", document["decode_audit"]["detector_adapter_fps_argument"])

    def test_fractional_origin_and_non_frame_aligned_clip_are_explicit(self):
        self.make_fixture([43 + index * 40 for index in range(15)])
        self.run_detection(start_seconds=0.1, end_seconds=0.31, min_shot_seconds=0)
        document = self.document("run")
        coverage = document["coverage"]
        self.assertEqual((163, 363), (coverage["start_pts"], coverage["end_pts"]))
        self.assertEqual("163/1000", coverage["start_source_seconds_rational"])
        self.assertEqual("3/25", coverage["start_playback_seconds_rational"])
        self.assertEqual("8/25", coverage["end_playback_seconds_rational"])
        self.assertEqual("first_excluded_decoded_frame_pts", coverage["end_basis"])
        self.assertFalse(coverage["reached_eof"])
        self.assertEqual(5, document["decode_audit"]["processed_frame_count"])
        self.assertTrue(document["shots"][0]["left_censored"])
        self.assertTrue(document["shots"][-1]["right_censored"])
        self.assertIn("requested_start_snapped_to_next_decoded_frame", document["quality_flags"])
        self.assertIn("requested_end_differs_from_actual_frame_endpoint", document["quality_flags"])

    def test_content_detector_has_its_own_default_threshold_and_scaling_is_recorded(self):
        self.run_detection(detector="content", analysis_width=360)
        run = self.document("run", "run.json")
        self.assertEqual(27.0, run["parameters"]["threshold"])
        self.assertEqual(360, run["parameters"]["scaling"]["analysis_width"])
        self.assertEqual(90, run["parameters"]["scaling"]["analysis_height"])
        self.assertEqual("15/16", run["parameters"]["scaling"]["scale_x"])
        self.assertEqual("AREA", run["parameters"]["scaling"]["interpolation"])
        self.assertEqual(2, self.document("run", "summary.json")["cut_count"])

    def test_near_gray_hue_noise_is_distinct_from_intensity_cuts(self):
        numpy = self.dependencies["numpy"]
        def near_gray(index):
            color = [130, 128, 128] if 5 <= index < 10 else [128, 128, 130]
            return numpy.broadcast_to(numpy.array(color, dtype=numpy.uint8), (96, 384, 3)).copy()
        self.make_fixture([1000 + index * 40 for index in range(15)],
                          pixel_values=near_gray, pixel_format="bgr0")

        hsv = self.run_detection("hsv")
        intensity = self.run_detection("intensity", luma_only=True, min_content_value=15.0)

        self.assertEqual(2, hsv["boundary_count"])
        self.assertEqual(0, intensity["boundary_count"])
        parameters = self.document("intensity", "run.json")["parameters"]
        self.assertTrue(parameters["luma_only"])
        self.assertEqual({"delta_hue": 0.0, "delta_sat": 0.0, "delta_lum": 1.0, "delta_edges": 0.0},
                         parameters["component_weights"])
        self.assertEqual("PySceneDetect HSV V intensity channel", parameters["luma_only_signal"])
        self.assertEqual(15.0, parameters["adaptive_min_content_val"])

    def test_intensity_only_still_detects_known_grayscale_cuts(self):
        result = self.run_detection(luma_only=True)
        self.assertEqual(2, result["boundary_count"])
        self.assertEqual([1200, 1400], [row["pts"] for row in self.document("run")["boundaries"]])

    def test_h264_b_frames_preserve_noninteger_cut_positions(self):
        av, numpy = self.dependencies["av"], self.dependencies["numpy"]
        self.video = self.folder / "synthetic-h264.mp4"
        with av.open(str(self.video), "w", format="mp4") as container:
            stream = container.add_stream("libx264", rate=25)
            stream.width, stream.height, stream.pix_fmt = 384, 96, "yuv420p"
            stream.time_base, stream.codec_context.time_base = Fraction(1, 12800), Fraction(1, 25)
            stream.options = {"crf": "18", "g": "25", "bf": "2", "sc_threshold": "0"}
            for index in range(50):
                pixels = numpy.full((96, 384, 3), 255 if 12 <= index < 31 else 0, dtype=numpy.uint8)
                frame = av.VideoFrame.from_ndarray(pixels, format="bgr24")
                frame.pts, frame.time_base = index, Fraction(1, 25)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        self.register_fixture()

        self.run_detection()

        boundaries = self.document("run")["boundaries"]
        self.assertEqual([0.48, 1.24], [row["playback_seconds"] for row in boundaries])
        self.assertEqual([6144, 15872], [row["pts"] for row in boundaries])

    def test_summary_uses_actual_timestamp_support_and_csv_retains_identity(self):
        result = self.run_detection()
        summary = self.document("run", "summary.json")
        self.assertEqual(0.2, summary["average_shot_length_seconds"])
        self.assertEqual(0.2, summary["median_shot_length_seconds"])
        self.assertEqual(0.6, summary["local_cut_rates"][0]["support_seconds"])
        self.assertEqual(200.0, summary["local_cut_rates"][0]["cuts_per_minute"])
        rows = list(csv.DictReader(io.StringIO((self.folder / "run/shots.csv").read_text())))
        self.assertEqual(3, len(rows))
        self.assertEqual("synthetic-fixtures", rows[0]["film_namespace"])
        self.assertEqual(self.manifest["video_version_id"], rows[0]["video_version_id"])
        self.assertEqual(result["segmentation_id"], rows[0]["segmentation_id"])
        self.assertEqual("1000", rows[0]["start_pts"])
        run = self.document("run", "run.json")
        for name, receipt in run["outputs"].items():
            self.assertEqual(hashlib.sha256((self.folder / "run" / name).read_bytes()).hexdigest(), receipt["sha256"])
        self.assertEqual(hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
                         run["inputs"]["source_manifest"]["sha256"])
        self.assertIn("pyav_ffmpeg_libraries", run["software"])

    def test_existing_output_is_never_reused_even_before_decoding(self):
        output = self.folder / "existing"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("unchanged")
        with mock.patch.object(shots, "hash_video") as hasher:
            with self.assertRaisesRegex(ShotError, "already exists"):
                self.run_detection("existing")
            hasher.assert_not_called()
        self.assertEqual("unchanged", sentinel.read_text())

    def test_changed_source_with_same_size_and_mtime_is_caught_by_checksum(self):
        before = self.video.stat()
        raw = bytearray(self.video.read_bytes())
        raw[-1] ^= 1
        self.video.write_bytes(raw)
        os.utime(self.video, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(ShotError, "checksum"):
            self.run_detection()
        self.assertFalse((self.folder / "run").exists())

    def test_source_mutation_during_decode_cannot_publish(self):
        original = shots._decode
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.video.write_bytes(self.video.read_bytes() + b"changed")
            return result
        with mock.patch.object(shots, "_decode", side_effect=mutate):
            with self.assertRaisesRegex(ShotError, "changed during detection"):
                self.run_detection()
        self.assertFalse((self.folder / "run").exists())

    def test_manifest_mutation_during_decode_cannot_publish(self):
        original = shots._decode
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.manifest_path.write_bytes(self.manifest_path.read_bytes() + b" ")
            return result
        with mock.patch.object(shots, "_decode", side_effect=mutate):
            with self.assertRaisesRegex(ShotError, "changed during detection"):
                self.run_detection()
        self.assertFalse((self.folder / "run").exists())

    def fake_frames(self):
        return [SimpleNamespace(pts=frame.pts, time_base=frame.time_base, duration=frame.duration,
                                width=frame.width, height=frame.height, format=frame.format,
                                color_range=frame.color_range, to_ndarray=frame.to_ndarray)
                for frame in self.decoded_frames]

    def fake_container(self, frames, duration=None):
        stream = SimpleNamespace(index=0, type="video", time_base=self.time_base,
                                 start_time=self.stream_start, duration=duration,
                                 codec_context=SimpleNamespace(thread_count=0), thread_type=None)
        container = mock.MagicMock()
        container.__enter__.return_value = container
        container.streams = [stream]
        container.decode.return_value = iter(frames)
        return container

    def test_missing_and_duplicate_frame_pts_fail_without_nominal_rate_fallback(self):
        for missing in (True, False):
            frames = self.fake_frames()
            frames[5].pts = None if missing else frames[4].pts
            container = self.fake_container(frames)
            with self.subTest(missing=missing), mock.patch.object(self.dependencies["av"], "open", return_value=container):
                with self.assertRaises(ShotError):
                    self.run_detection()
            self.assertFalse((self.folder / "run").exists())

    def test_eof_without_frame_duration_or_validated_stream_end_fails(self):
        frames = self.fake_frames()
        frames[-1].duration = 0
        with mock.patch.object(self.dependencies["av"], "open", return_value=self.fake_container(frames)):
            with self.assertRaisesRegex(ShotError, "no FPS-derived end"):
                self.run_detection()
        self.assertFalse((self.folder / "run").exists())

    def test_eof_can_use_an_explicit_manifest_validated_stream_end(self):
        frames = self.fake_frames()
        frames[-1].duration = 0
        self.manifest["timeline"]["duration_ts"] = 600
        self.write_manifest()
        container = self.fake_container(frames, duration=600)
        with mock.patch.object(self.dependencies["av"], "open", return_value=container):
            self.run_detection()
        document = self.document("run")
        self.assertEqual(1600, document["coverage"]["end_pts"])
        self.assertEqual("manifest_validated_stream_start_plus_duration", document["coverage"]["end_basis"])
        self.assertIn("eof_endpoint_from_stream_duration", document["quality_flags"])

    def test_clip_after_eof_is_not_an_empty_success(self):
        with self.assertRaisesRegex(ShotError, "no usable decoded"):
            self.run_detection(start_seconds=10)
        self.assertFalse((self.folder / "run").exists())


if __name__ == "__main__":
    unittest.main()
