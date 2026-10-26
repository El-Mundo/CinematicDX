"""Whole-interval, fixed-ROI feature contracts use tiny synthetic source streams."""

from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from cinematicdx import transition_features as features
from cinematicdx.transition_features import TransitionFeatureError, extract_transition_features


class TransitionFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.dependencies = features._load_dependencies()
        except TransitionFeatureError as exc:
            raise unittest.SkipTest(str(exc))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cinematicdx-transition-features-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.video = self.folder / "vfr-gray.mkv"
        self.manifest_path = self.folder / "source_manifest.json"
        self.timestamps = [43, 83, 163, 203, 323, 363, 403, 523, 563, 643]
        av = self.dependencies["av"]
        with av.open(str(self.video), "w", format="matroska") as container:
            stream = container.add_stream("ffv1", rate=25)
            stream.width, stream.height, stream.pix_fmt = 160, 120, "gray"
            stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
            for index, pts in enumerate(self.timestamps):
                frame = av.VideoFrame(160, 120, "gray")
                for plane in frame.planes:
                    plane.update(bytes([16 + index * 8]) * plane.buffer_size)
                frame.pts, frame.time_base = pts, Fraction(1, 1000)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        stat = self.video.stat()
        checksum = hashlib.sha256(self.video.read_bytes()).hexdigest()
        manifest = {"schema_version": 1, "artifact_kind": "source_video_manifest",
                    "film_reference": {"namespace": "synthetic", "key": "gray-vfr-fixture"},
                    "video_version_id": "sha256:" + checksum,
                    "source": {"requested_path": str(self.video), "resolved_path": str(self.video),
                               "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": checksum},
                    "selected_video_stream_index": 0,
                    "timeline": {"time_base": "1/1000", "source_start_pts": 43,
                                 "duration_ts": None,
                                 "playback_origin": {"source_seconds_rational": "43/1000"}}}
        self.manifest_path.write_text(json.dumps(manifest))

    def extract(self, name="features", **overrides):
        options = {"start_seconds": 0.12, "end_seconds": 0.52, "pad_seconds": 0.12}
        options.update(overrides)
        return extract_transition_features(self.manifest_path, self.folder / name, **options)

    def test_fixed_roi_ignores_border_changes_while_full_intensity_preserves_control(self):
        np = self.dependencies["numpy"]
        geometry = features._roi_geometry(160, 120)
        first = np.zeros((120, 160), dtype=np.uint8)
        first[geometry["top"]:geometry["bottom"], geometry["left"]:geometry["right"]] = 64
        second = np.full((120, 160), 255, dtype=np.uint8)
        second[geometry["top"]:geometry["bottom"], geometry["left"]:geometry["right"]] = 64
        left, right = [features._signals(image, geometry, np) for image in (first, second)]
        self.assertEqual(left["roi_mean"], right["roi_mean"])
        self.assertNotEqual(left["full_mean"], right["full_mean"])
        self.assertEqual(0.0, left["roi_std"])
        self.assertEqual(0.0, left["edge_energy"])
        self.assertEqual(1.0, float(left["gray_hist"].sum()))
        self.assertEqual((8, 152, 12, 108),
                         tuple(geometry[key] for key in ("left", "right", "top", "bottom")))

    def test_vfr_cache_covers_full_evaluation_support_with_exact_source_ticks(self):
        np = self.dependencies["numpy"]
        source_before, manifest_before = self.video.read_bytes(), self.manifest_path.read_bytes()
        result = self.extract()
        run = json.loads(Path(result["run_path"]).read_text())
        with np.load(result["npz_path"], allow_pickle=False) as arrays:
            self.assertEqual(self.timestamps, arrays["pts"].tolist())
            self.assertEqual((10, 48, 64), arrays["gray_cache"].shape)
            self.assertEqual("uint8", str(arrays["gray_cache"].dtype))
            self.assertEqual(0.12, arrays["playback_seconds"][2])
            self.assertEqual(0.163, arrays["source_seconds"][2])
            self.assertEqual(0.08, arrays["frame_delta_seconds"][2])
            self.assertTrue(np.isnan(arrays["adjacent_mad"][0]))
            self.assertFalse(arrays["adjacent_mad_valid"][0])
            self.assertTrue(np.all(arrays["adjacent_mad_valid"][1:]))
            self.assertTrue(np.allclose(arrays["adjacent_mad"][1:], 8 / 255))
            self.assertTrue(np.allclose(arrays["gray_hist"].sum(axis=1), 1))
            self.assertEqual([False, False, True, True, True, True, True, True, False, False],
                             arrays["evaluation_mask"].tolist())
            self.assertAlmostEqual(0.4, float(arrays["evaluation_overlap_seconds"].sum()))
            self.assertEqual(683, arrays["next_pts"][-1])
            self.assertEqual(1, int(arrays["time_base_num"]))
            self.assertEqual(1000, int(arrays["time_base_den"]))
        self.assertEqual(0.4, run["evaluation_interval"]["duration_seconds"])
        self.assertEqual(0.4, run["evaluation_interval"]["verified_frame_support_seconds"])
        self.assertEqual([], run["parameters"]["annotation_inputs"])
        self.assertFalse(run["parameters"]["label_dependent_parameters"])
        self.assertEqual(hashlib.sha256(Path(result["npz_path"]).read_bytes()).hexdigest(),
                         run["outputs"]["features.npz"]["sha256"])
        self.assertEqual(source_before, self.video.read_bytes())
        self.assertEqual(manifest_before, self.manifest_path.read_bytes())
        with self.assertRaisesRegex(TransitionFeatureError, "completely cover"):
            self.extract("incomplete", end_seconds=2)
        self.assertFalse((self.folder / "incomplete").exists())

    def test_existing_output_is_never_overwritten_or_decoded(self):
        existing = self.folder / "existing"
        existing.mkdir()
        marker = existing / "keep.txt"
        marker.write_text("keep")
        with mock.patch.object(features, "hash_video") as hasher:
            with self.assertRaisesRegex(TransitionFeatureError, "already exists"):
                self.extract("existing")
            hasher.assert_not_called()
        self.assertEqual("keep", marker.read_text())

    def test_source_changed_with_same_size_mtime_fails_full_checksum_guard(self):
        stat = self.video.stat()
        content = bytearray(self.video.read_bytes())
        content[-1] ^= 1
        self.video.write_bytes(content)
        os.utime(self.video, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with self.assertRaisesRegex(TransitionFeatureError, "checksum"):
            self.extract()
        self.assertFalse((self.folder / "features").exists())

    def test_mid_measurement_manifest_or_source_mutation_cannot_publish(self):
        original = features._signals
        for changed_path in (self.manifest_path, self.video):
            original_bytes = changed_path.read_bytes()
            original_stat = changed_path.stat()
            mutated = False
            def mutate(*args, **kwargs):
                nonlocal mutated
                measured = original(*args, **kwargs)
                if not mutated:
                    changed_path.write_bytes(changed_path.read_bytes() + b" ")
                    mutated = True
                return measured
            with self.subTest(path=changed_path.name), mock.patch.object(features, "_signals", side_effect=mutate):
                with self.assertRaisesRegex(TransitionFeatureError, "changed during"):
                    self.extract()
            self.assertFalse((self.folder / "features").exists())
            changed_path.write_bytes(original_bytes)
            os.utime(changed_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    def test_missing_pts_cannot_be_replaced_by_nominal_fps(self):
        av = self.dependencies["av"]
        with av.open(str(self.video)) as container:
            decoded = list(container.decode(container.streams.video[0]))
        frames = [SimpleNamespace(pts=frame.pts, time_base=frame.time_base, duration=frame.duration,
                                  width=frame.width, height=frame.height, format=frame.format,
                                  color_range=frame.color_range, to_ndarray=frame.to_ndarray) for frame in decoded]
        frames[2].pts = None
        stream = SimpleNamespace(index=0, type="video", time_base=Fraction(1, 1000), start_time=43,
                                 duration=None, codec_context=SimpleNamespace(thread_count=0), thread_type=None)
        fake = mock.MagicMock()
        fake.__enter__.return_value = fake
        fake.streams, fake.decode.return_value = [stream], iter(frames)
        with mock.patch.object(av, "open", return_value=fake):
            with self.assertRaisesRegex(TransitionFeatureError, "integer PTS"):
                self.extract()
        self.assertFalse((self.folder / "features").exists())


if __name__ == "__main__":
    unittest.main()
