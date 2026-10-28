"""Single-source ingestion contracts use tiny local bytes and a mocked media probe."""

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cinematicdx import ingest
from cinematicdx.probe import ProbeError


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "桥 原始文件.mp4"
        self.video.write_bytes(b"small source bytes; the probe is mocked\x00\xff")
        self.raw_record = {
            "key": "qiao-1949", "title": " 桥 ", "year": "1949",
            "directorNameArray": ["王滨"],
            "unknown_research_notes": {"provenance": None, "tags": ["待核查", 3]},
        }
        self.metadata = self.root / "原始研究目录.json"
        self.metadata.write_text(json.dumps({"films": [self.raw_record]}, ensure_ascii=False),
                                 encoding="utf-8")
        self.probe_response = {
            "schema_version": 1,
            "selected_video_stream_index": 2,
            "technical_summary": {
                "time_base": "1/90000", "source_start_pts": -7200,
                "source_start_time": "-0.080000", "avg_frame_rate": "24000/1001",
                "r_frame_rate": "30000/1001", "frame_rate_mode": "unknown",
                "reported_frame_count": None, "duration_seconds": None,
                "playback_origin": {"source": "stream.start_pts", "source_seconds": -0.08,
                                    "source_seconds_rational": "-2/25"},
            },
            "timestamp_sample": {
                "requested_frames": 12, "recorded_frames": 1, "coverage": "bounded_prefix",
                "frames": [{"pts": -7200, "time_base": "1/90000",
                            "source_seconds_rational": "-2/25", "playback_offset_seconds": 0.0}],
            },
            "raw_header": {"format": {"start_time": "-0.080000"}, "unknown": [1, "原样"]},
            "ffprobe": {"version": "ffprobe test fixture", "header_argv": ["fake-ffprobe", "-show_streams"],
                        "timestamp_sample_argv": ["fake-ffprobe", "-show_frames"]},
            "quality_flags": ["VFR_unknown", "sample_limited", "VFR_unknown"],
            "full_decode_requested": False,
        }
        self.software = {
            "pipeline_version": "test-version", "python_version": "3.test", "platform": "test-platform",
            "pipeline_source_sha256": "a" * 64, "git_revision": "b" * 40,
            "git_worktree_dirty": True,
        }
        probe_patch = mock.patch("cinematicdx.ingest.probe_video", return_value=self.probe_response)
        self.mock_probe = probe_patch.start()
        self.addCleanup(probe_patch.stop)
        software_patch = mock.patch("cinematicdx.ingest.software_provenance", return_value=self.software)
        software_patch.start()
        self.addCleanup(software_patch.stop)

    def run_ingest(self, output="run", **options):
        parameters = {"video_path": self.video, "metadata_path": self.metadata,
                      "film_id": "qiao-1949", "output_dir": self.root / output}
        parameters.update(options)
        return ingest.ingest_video(**parameters)

    def document(self, output, name):
        return json.loads((self.root / output / name).read_text(encoding="utf-8"))

    def test_complete_byte_hash_identifies_copies_and_renames_independently_of_run(self):
        copied = self.root / "renamed copy.MKV"
        copied.write_bytes(self.video.read_bytes())

        first = self.run_ingest("first")
        second = self.run_ingest("second", video_path=copied)

        self.assertEqual("sha256:" + hashlib.sha256(self.video.read_bytes()).hexdigest(),
                         first["video_version_id"])
        self.assertEqual(first["video_version_id"], second["video_version_id"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertNotEqual(self.document("first", "source_manifest.json")["source"]["resolved_path"],
                            self.document("second", "source_manifest.json")["source"]["resolved_path"])
        self.assertEqual("qiao-1949", first["film_id"])

    def test_one_byte_change_creates_new_video_version_without_changing_film_identity(self):
        first = self.run_ingest("before")
        original = self.video.read_bytes()
        self.video.write_bytes(bytes([original[0] ^ 1]) + original[1:])

        second = self.run_ingest("after")

        self.assertNotEqual(first["video_version_id"], second["video_version_id"])
        self.assertEqual(first["film_id"], second["film_id"])

    def test_explicit_unknown_film_fails_before_hash_probe_or_output_creation(self):
        with mock.patch("cinematicdx.ingest.hash_video") as hasher:
            with self.assertRaisesRegex(ingest.IngestError, "explicit film ID"):
                self.run_ingest(film_id="unknown")
            hasher.assert_not_called()
        self.mock_probe.assert_not_called()
        self.assertFalse((self.root / "run").exists())

    def test_raw_record_and_source_metadata_checksum_are_preserved_without_writes(self):
        before = self.metadata.read_bytes()
        source_before = self.video.read_bytes()
        self.run_ingest()

        manifest = self.document("run", "source_manifest.json")

        self.assertEqual(self.raw_record, manifest["metadata"]["raw_record"])
        self.assertEqual("1949", manifest["metadata"]["raw_record"]["year"])
        self.assertEqual(1949, manifest["production_year"])
        self.assertEqual("桥", manifest["film_title"])
        self.assertEqual(hashlib.sha256(before).hexdigest(), manifest["metadata"]["source_sha256"])
        self.assertEqual(before, self.metadata.read_bytes())
        self.assertEqual(source_before, self.video.read_bytes())

    def test_local_catalog_uuid_scopes_film_reference_and_overrides_research_namespace(self):
        catalog_id = "f2d14389-00ba-4cc6-9493-5c934245f785"
        raw = {"film_key": "桥-1949", "id": 7, "title_original": "桥", "production_year": 1949,
               "extensions": {"archive": "保留"}}
        self.metadata.write_text(json.dumps({"schema_version": 1, "catalog_id": catalog_id,
                                             "films": [raw]}, ensure_ascii=False), encoding="utf-8")

        self.run_ingest(film_id="桥-1949", metadata_namespace="should-not-override-catalog")

        manifest = self.document("run", "source_manifest.json")
        self.assertEqual({"namespace": catalog_id, "key": "桥-1949"}, manifest["film_reference"])
        self.assertEqual("local-catalog-v1", manifest["metadata"]["format"])
        self.assertEqual(raw, manifest["metadata"]["raw_record"])

    def test_explicit_research_namespace_is_recorded_separately_from_film_key(self):
        self.run_ingest(metadata_namespace="kcl-pilot-inventory")
        manifest = self.document("run", "source_manifest.json")
        self.assertEqual({"namespace": "kcl-pilot-inventory", "key": "qiao-1949"},
                         manifest["film_reference"])

    def test_complete_receipt_matches_artifact_bytes_and_records_provenance_and_parameters(self):
        expected_probe = copy.deepcopy(self.probe_response)
        result = self.run_ingest(source_description="Known archive transfer, technical history uncertain",
                                 source_uri="archive:pilot-copy", ffprobe="/test tools/ffprobe",
                                 stream_index=2, timestamp_sample_frames=8)
        receipt = self.document("run", "run.json")
        manifest = self.document("run", "source_manifest.json")
        probe = self.document("run", "probe.json")
        sample = self.document("run", "timestamp_sample.json")

        self.assertEqual("complete", receipt["status"])
        self.assertEqual(result["run_id"], receipt["run_id"])
        self.assertEqual(receipt["run_id"], manifest["run_id"])
        self.assertEqual(self.software, receipt["software"])
        self.assertTrue(receipt["started_at_utc"].endswith("+00:00"))
        self.assertTrue(receipt["completed_at_utc"].endswith("+00:00"))
        self.assertEqual({"film_id": "qiao-1949", "metadata_namespace": "research-inventory",
                          "ffprobe_executable": "/test tools/ffprobe", "stream_index": 2,
                          "timestamp_sample_frames": 8}, receipt["parameters"])
        self.assertEqual({"source_manifest.json", "probe.json", "timestamp_sample.json"},
                         set(receipt["outputs"]))
        for name, evidence in receipt["outputs"].items():
            content = (self.root / "run" / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), evidence["sha256"], name)
            self.assertEqual(len(content), evidence["size_bytes"], name)
        self.assertEqual(expected_probe, probe)
        self.assertEqual(expected_probe["timestamp_sample"], sample)
        self.assertEqual(expected_probe, self.probe_response, "ingestion must not mutate probe results")
        self.assertEqual(expected_probe["technical_summary"], manifest["timeline"])
        self.assertEqual(2, manifest["selected_video_stream_index"])
        self.assertEqual("bounded_sample_only", manifest["validation"]["timestamp_validation"])
        self.assertEqual("not_performed", manifest["validation"]["full_decode"])
        self.assertEqual("not_assessed", manifest["validation"]["source_authenticity"])
        self.assertEqual("entire_file_bytes", manifest["source"]["hash_scope"])
        self.assertEqual("archive:pilot-copy", manifest["source"]["source_uri"])
        self.assertNotIn("source_provenance_unknown", manifest["quality_flags"])
        self.assertEqual(["VFR_unknown", "sample_limited"], manifest["quality_flags"])
        self.mock_probe.assert_called_once_with(self.video.resolve(), ffprobe="/test tools/ffprobe",
                                                 stream_index=2, timestamp_sample_frames=8)

    def test_unknown_source_history_is_a_quality_flag_not_invented_provenance(self):
        self.run_ingest()
        manifest = self.document("run", "source_manifest.json")
        self.assertIn("source_provenance_unknown", manifest["quality_flags"])
        self.assertIsNone(manifest["source"]["description"])
        self.assertIsNone(manifest["source"]["transfer_history"])
        self.assertEqual("unknown", manifest["timeline"]["frame_rate_mode"])
        self.assertEqual(-7200, manifest["timeline"]["source_start_pts"])
        self.assertIsNone(manifest["timeline"]["reported_frame_count"])

    def test_whitespace_source_description_is_still_unknown_provenance(self):
        self.run_ingest(source_description="  \t ")
        manifest = self.document("run", "source_manifest.json")
        self.assertIn("source_provenance_unknown", manifest["quality_flags"])

    def test_source_replaced_during_probe_fails_without_publishing_a_run(self):
        def replace_source(*args, **kwargs):
            replacement = self.root / "replacement.mp4"
            replacement.write_bytes(self.video.read_bytes())
            replacement.replace(self.video)
            return self.probe_response

        self.mock_probe.side_effect = replace_source
        with self.assertRaisesRegex(ingest.IngestError, "changed or was replaced"):
            self.run_ingest()
        self.assertFalse((self.root / "run").exists())

    def test_source_replaced_just_after_hash_fails_without_publishing_a_run(self):
        real_hash = ingest.hash_video

        def hash_then_replace(path):
            result = real_hash(path)
            replacement = self.root / "replacement.mp4"
            replacement.write_bytes(self.video.read_bytes())
            replacement.replace(self.video)
            return result

        with mock.patch("cinematicdx.ingest.hash_video", side_effect=hash_then_replace):
            with self.assertRaisesRegex(ingest.IngestError, "changed or was replaced"):
                self.run_ingest()
        self.assertFalse((self.root / "run").exists())

    def test_metadata_replaced_during_probe_fails_without_publishing_a_run(self):
        def replace_metadata(*args, **kwargs):
            replacement = self.root / "replacement.json"
            replacement.write_bytes(self.metadata.read_bytes())
            replacement.replace(self.metadata)
            return self.probe_response

        self.mock_probe.side_effect = replace_metadata
        with self.assertRaisesRegex(ingest.IngestError, "Metadata changed"):
            self.run_ingest()
        self.assertFalse((self.root / "run").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links unavailable")
    def test_requested_symlink_retargeted_during_probe_is_rejected(self):
        linked = self.root / "selected.mp4"
        linked.symlink_to(self.video)
        other = self.root / "different-location.mp4"
        other.write_bytes(self.video.read_bytes())

        def retarget(*args, **kwargs):
            linked.unlink()
            linked.symlink_to(other)
            return self.probe_response

        self.mock_probe.side_effect = retarget
        with self.assertRaisesRegex(ingest.IngestError, "changed or was replaced"):
            self.run_ingest(video_path=linked)
        self.assertFalse((self.root / "run").exists())

    def test_existing_output_is_never_reused_or_overwritten(self):
        output = self.root / "run"
        output.mkdir()
        sentinel = output / "run.json"
        sentinel.write_bytes(b"existing result must remain unchanged")
        with mock.patch("cinematicdx.ingest.hash_video") as hasher:
            with self.assertRaisesRegex(ingest.IngestError, "Output already exists"):
                self.run_ingest()
            hasher.assert_not_called()
        self.assertEqual(b"existing result must remain unchanged", sentinel.read_bytes())
        self.assertEqual([sentinel], list(output.iterdir()))
        self.mock_probe.assert_not_called()

    def test_failed_probe_never_publishes_success_bundle_or_changes_inputs(self):
        source_before, metadata_before = self.video.read_bytes(), self.metadata.read_bytes()
        self.mock_probe.side_effect = ProbeError("fixture probe failure", code="tool_failed")
        with self.assertRaisesRegex(ProbeError, "fixture probe failure"):
            self.run_ingest()
        self.assertFalse((self.root / "run").exists())
        self.assertEqual(source_before, self.video.read_bytes())
        self.assertEqual(metadata_before, self.metadata.read_bytes())

    def test_empty_video_is_rejected_before_probe_and_output_creation(self):
        self.video.write_bytes(b"")
        with self.assertRaisesRegex(ingest.IngestError, "non-empty regular file"):
            self.run_ingest()
        self.mock_probe.assert_not_called()
        self.assertFalse((self.root / "run").exists())

    def test_hash_detects_file_state_changes_while_reading(self):
        original = self.video.stat()
        changed = mock.Mock(st_dev=original.st_dev, st_ino=original.st_ino,
                            st_mode=original.st_mode, st_size=original.st_size,
                            st_mtime_ns=original.st_mtime_ns + 1, st_ctime_ns=original.st_ctime_ns)
        with mock.patch("cinematicdx.ingest.os.fstat", side_effect=[original, changed]):
            with self.assertRaisesRegex(ingest.IngestError, "changed while its file checksum"):
                ingest.hash_video(self.video)

    def test_zero_sample_cannot_be_mislabeled_as_ingestion_timestamp_validation(self):
        with self.assertRaisesRegex(ingest.IngestError, "positive timestamp sample"):
            self.run_ingest(timestamp_sample_frames=0)
        self.mock_probe.assert_not_called()
        self.assertFalse((self.root / "run").exists())

    def test_publication_write_failure_removes_only_new_bundle_and_leaves_inputs_intact(self):
        source_before, metadata_before = self.video.read_bytes(), self.metadata.read_bytes()
        unrelated = self.root / "keep.txt"
        unrelated.write_bytes(b"unrelated file")
        with mock.patch("cinematicdx.ingest.os.fsync", side_effect=OSError("simulated write failure")):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                self.run_ingest()
        self.assertFalse((self.root / "run").exists())
        self.assertEqual(b"unrelated file", unrelated.read_bytes())
        self.assertEqual(source_before, self.video.read_bytes())
        self.assertEqual(metadata_before, self.metadata.read_bytes())


if __name__ == "__main__":
    unittest.main()
