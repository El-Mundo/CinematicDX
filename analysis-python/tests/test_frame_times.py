"""Frame-label conventions are tested independently from source presentation time."""

from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from cinematicdx import frame_times
from cinematicdx.frame_times import (FrameTimeError, frame_number_to_index,
                                    resolve_frame_base_candidates, resolve_frame_times)


class FrameNumberPolicyTests(unittest.TestCase):
    def test_base_is_explicit_and_does_not_supply_a_timestamp(self):
        self.assertEqual(2, frame_number_to_index(2, frame_base=0))
        self.assertEqual(1, frame_number_to_index(2, frame_base=1))
        for base in (None, 2, True, 1.0):
            with self.subTest(base=base), self.assertRaises(FrameTimeError):
                frame_number_to_index(2, frame_base=base)
        for number in (-1, 1.5, True, "f4926"):
            with self.subTest(number=number), self.assertRaises(FrameTimeError):
                frame_number_to_index(number, frame_base=0)
        with self.assertRaises(FrameTimeError):
            frame_number_to_index(0, frame_base=1)

    def test_negative_original_pts_and_origin_remain_exact(self):
        record = frame_times._time_record(SimpleNamespace(pts=-80, time_base=Fraction(1, 1000)),
                                          0, Fraction(1, 1000), Fraction(-2, 25))
        self.assertEqual(-80, record["pts"])
        self.assertEqual("-2/25", record["source_seconds_rational"])
        self.assertEqual("0/1", record["playback_seconds_rational"])

    def test_missing_pts_is_not_replaced_with_frame_over_fps(self):
        record = frame_times._time_record(SimpleNamespace(pts=None, time_base=Fraction(1, 1000)),
                                          100, Fraction(1, 1000), Fraction(0))
        self.assertEqual("unresolved_missing_pts", record["status"])
        self.assertIsNone(record["source_seconds"])


class TinyVfrFrameResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.av = frame_times._load_av()
        except FrameTimeError as exc:
            raise unittest.SkipTest(str(exc))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cinematicdx-frame-times-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.video = self.folder / "tiny-vfr.mkv"
        self.manifest_path = self.folder / "source_manifest.json"
        with self.av.open(str(self.video), "w", format="matroska") as container:
            stream = container.add_stream("ffv1", rate=25)
            stream.width, stream.height, stream.pix_fmt = 16, 16, "yuv420p"
            stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
            for pts in [43, 83, 163, 203, 323, 363]:
                frame = self.av.VideoFrame(16, 16, "yuv420p")
                for plane in frame.planes:
                    plane.update(bytes([128]) * plane.buffer_size)
                frame.pts, frame.time_base = pts, Fraction(1, 1000)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        state = self.video.stat()
        checksum = hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.manifest = {
            "schema_version": 1, "artifact_kind": "source_video_manifest",
            "film_reference": {"namespace": "test", "key": "vfr-frame-fixture"},
            "video_version_id": "sha256:" + checksum,
            "source": {"requested_path": str(self.video), "resolved_path": str(self.video),
                       "sha256": checksum, "size_bytes": state.st_size, "mtime_ns": state.st_mtime_ns},
            "selected_video_stream_index": 0,
            "timeline": {"time_base": "1/1000", "avg_frame_rate": "25/1",
                         "playback_origin": {"source_seconds_rational": "43/1000"}},
        }
        self.manifest_path.write_text(json.dumps(self.manifest))

    def test_both_bases_use_real_vfr_pts_and_only_the_required_prefix(self):
        source_before, manifest_before = self.video.read_bytes(), self.manifest_path.read_bytes()
        result = resolve_frame_base_candidates(self.manifest_path, [2])
        alternatives = result["frames"][0]["candidates"]
        self.assertEqual("awaiting_user_confirmation", result["frame_base_status"])
        self.assertIsNone(result["frame_base"])
        self.assertEqual(163, alternatives["0"]["pts"])
        self.assertEqual(83, alternatives["1"]["pts"])
        self.assertEqual("3/25", alternatives["0"]["playback_seconds_rational"])
        self.assertEqual("1/25", alternatives["1"]["playback_seconds_rational"])
        self.assertEqual(3, result["decode_audit"]["decoded_output_frame_count"])
        self.assertTrue(result["decode_audit"]["stopped_at_required_index"])
        self.assertFalse(result["method"]["fps_used_for_timestamps"])
        self.assertEqual(hashlib.sha256(manifest_before).hexdigest(), result["source_binding"]["manifest_sha256"])
        self.assertEqual(source_before, self.video.read_bytes())
        self.assertEqual(manifest_before, self.manifest_path.read_bytes())

    def test_explicit_one_based_start_and_repeated_requests_are_preserved(self):
        result = resolve_frame_times(self.manifest_path, [3, 1, 3], frame_base=1)
        self.assertEqual([3, 1, 3], [row["requested_frame"] for row in result["frames"]])
        self.assertEqual([163, 43, 163], [row["candidates"]["1"]["pts"] for row in result["frames"]])
        self.assertEqual("explicitly_selected", result["frame_base_status"])
        self.assertEqual(3, result["decode_audit"]["decoded_output_frame_count"])

    def test_zero_label_has_no_one_based_candidate(self):
        result = resolve_frame_base_candidates(self.manifest_path, [0])
        self.assertEqual("resolved", result["frames"][0]["candidates"]["0"]["status"])
        self.assertEqual("invalid_frame_for_base", result["frames"][0]["candidates"]["1"]["status"])
        self.assertEqual("partial", result["status"])
        with self.assertRaises(FrameTimeError):
            resolve_frame_times(self.manifest_path, [0], frame_base=1)

    def test_out_of_range_is_explicit_without_a_fps_estimate(self):
        result = resolve_frame_times(self.manifest_path, [100], frame_base=0)
        candidate = result["frames"][0]["candidates"]["0"]
        self.assertEqual("unresolved_frame_outside_decoded_source", candidate["status"])
        self.assertNotIn("source_seconds", candidate)
        self.assertEqual(6, result["decode_audit"]["decoded_output_frame_count"])
        self.assertTrue(result["decode_audit"]["reached_eof_before_required_index"])

    def test_source_changed_with_same_size_mtime_cannot_be_bound_to_old_hash(self):
        state = self.video.stat()
        raw = bytearray(self.video.read_bytes())
        raw[-1] ^= 1
        self.video.write_bytes(raw)
        os.utime(self.video, ns=(state.st_atime_ns, state.st_mtime_ns))
        with self.assertRaisesRegex(FrameTimeError, "checksum"):
            resolve_frame_base_candidates(self.manifest_path, [2])

    def test_manifest_changed_during_resolution_is_rejected(self):
        original = frame_times._time_record
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.manifest_path.write_bytes(self.manifest_path.read_bytes() + b" ")
            return result
        with mock.patch.object(frame_times, "_time_record", side_effect=mutate):
            with self.assertRaisesRegex(FrameTimeError, "changed during"):
                resolve_frame_base_candidates(self.manifest_path, [2])

    def test_source_changed_during_resolution_is_rejected(self):
        original = frame_times._time_record
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.video.write_bytes(self.video.read_bytes() + b"changed")
            return result
        with mock.patch.object(frame_times, "_time_record", side_effect=mutate):
            with self.assertRaisesRegex(FrameTimeError, "changed during"):
                resolve_frame_times(self.manifest_path, [2], frame_base=0)


if __name__ == "__main__":
    unittest.main()
