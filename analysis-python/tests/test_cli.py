"""CLI routing and audit receipts need no running database or media executable."""

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cinematicdx import cli
from cinematicdx.ingest import IngestError
from cinematicdx.probe import ProbeError


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.sources.mkdir()
        (self.sources / "桥（1949）.mp4").write_bytes(b"first fake video")
        (self.sources / "unknown.mkv").write_bytes(b"second fake video")
        self.metadata = self.root / "metadata.json"
        self.metadata.write_text(json.dumps({"films": [{"key": "qiao", "title": "桥", "year": 1949}]},
                                             ensure_ascii=False), encoding="utf-8")
        self.output = self.root / "reports" / "audit"

    def call(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = cli.main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_ingestion_routes_explicit_identity_source_history_and_timing_options(self):
        expected = {"run_id": "test-run", "film_id": "qiao", "video_version_id": "sha256:test"}
        with mock.patch("cinematicdx.cli.ingest_video", return_value=expected) as ingestion:
            status, stdout, stderr = self.call([
                "ingest", "--video", "桥 selected.mp4", "--metadata", str(self.metadata),
                "--film-id", "qiao", "--metadata-namespace", "pilot",
                "--output", str(self.output), "--source-description", "Archive transfer",
                "--source-uri", "archive:copy1", "--ffprobe", "/test tools/ffprobe",
                "--stream-index", "2", "--timestamp-sample-frames", "8",
            ])
        self.assertEqual(0, status)
        self.assertEqual(expected, json.loads(stdout))
        self.assertEqual("", stderr)
        ingestion.assert_called_once_with(
            "桥 selected.mp4", str(self.metadata), "qiao", str(self.output),
            source_description="Archive transfer", source_uri="archive:copy1", metadata_namespace="pilot",
            ffprobe="/test tools/ffprobe", stream_index=2, timestamp_sample_frames=8)

    def test_ingestion_failures_return_error_status_and_never_print_a_success_result(self):
        arguments = ["ingest", "--video", "selected.mp4", "--metadata", str(self.metadata),
                     "--film-id", "qiao", "--output", str(self.output)]
        for failure in (IngestError("unknown film"), ProbeError("tool missing", code="tool_missing"),
                        OSError("read failure"), ValueError("malformed metadata")):
            with self.subTest(failure=type(failure).__name__):
                with mock.patch("cinematicdx.cli.ingest_video", side_effect=failure):
                    status, stdout, stderr = self.call(arguments)
                self.assertEqual(2, status)
                self.assertEqual("", stdout)
                self.assertIn("CinematicDX: " + str(failure), stderr)
                self.assertNotIn("Traceback", stderr)
        self.assertFalse(self.output.exists())

    def test_inventory_default_is_read_only_and_reports_expected_count_without_hashing_or_probing(self):
        before = {path.name: path.read_bytes() for path in self.sources.iterdir()}
        with mock.patch("cinematicdx.cli.probe_video") as probe, \
                mock.patch("cinematicdx.ingest.hash_video") as hasher, \
                mock.patch("cinematicdx.cli.software_provenance", return_value={"pipeline_version": "fixture"}):
            status, stdout, stderr = self.call([
                "inventory", "--root", str(self.sources), "--metadata", str(self.metadata),
                "--output", str(self.output), "--expected-count", "3",
            ])
        self.assertEqual(0, status)
        self.assertEqual("", stderr)
        probe.assert_not_called()
        hasher.assert_not_called()
        summary = json.loads(stdout)["summary"]
        self.assertEqual(2, summary["video_count"])
        self.assertEqual(3, summary["expected_video_count"])
        self.assertFalse(summary["expected_count_matches"])
        self.assertEqual("not_performed", summary["full_content_duplicate_check"])
        self.assertEqual("not_performed", summary["full_decode_validation"])
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.sources.iterdir()})
        self.assertEqual({"inventory.json", "inventory.csv", "run.json"},
                         {path.name for path in self.output.iterdir()})
        receipt = json.loads((self.output / "run.json").read_text(encoding="utf-8"))
        self.assertEqual("complete", receipt["status"])
        self.assertFalse(receipt["parameters"]["probe_headers"])
        self.assertEqual(str(self.metadata.resolve()), receipt["metadata"]["path"])
        self.assertEqual(hashlib.sha256(self.metadata.read_bytes()).hexdigest(),
                         receipt["metadata"]["sha256"])
        for name, details in receipt["outputs"].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(),
                             details["sha256"])

    def test_requested_header_probes_have_zero_timestamp_sample_and_preserve_individual_failures(self):
        success = {"technical_summary": {"frame_rate_mode": "unknown"}, "quality_flags": ["header_only"]}
        with mock.patch("cinematicdx.cli.probe_video",
                        side_effect=[success, ProbeError("cannot inspect this copy")]) as probe, \
                mock.patch("cinematicdx.cli.software_provenance", return_value={}):
            status, stdout, stderr = self.call([
                "inventory", "--root", str(self.sources), "--metadata", str(self.metadata),
                "--output", str(self.output),
                "--probe-headers", "--ffprobe", "explicit-ffprobe", "--expected-count", "2",
            ])
        self.assertEqual(0, status)
        self.assertEqual("", stderr)
        self.assertEqual(2, probe.call_count)
        for call in probe.call_args_list:
            self.assertEqual({"ffprobe": "explicit-ffprobe", "timestamp_sample_frames": 0}, call.kwargs)
        summary = json.loads(stdout)["summary"]
        self.assertTrue(summary["expected_count_matches"])
        self.assertEqual(1, summary["header_probes_passed"])
        self.assertEqual(1, summary["header_probes_failed"])
        inventory = json.loads((self.output / "inventory.json").read_text(encoding="utf-8"))
        self.assertEqual("passed", inventory["videos"][0]["header_probe_status"])
        self.assertEqual(success, inventory["videos"][0]["header_probe"])
        self.assertEqual("failed", inventory["videos"][1]["header_probe_status"])
        self.assertIn("cannot inspect this copy", inventory["videos"][1]["header_probe_error"])
        receipt = json.loads((self.output / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(self.metadata.read_bytes()).hexdigest(),
                         receipt["metadata"]["sha256"])

    def test_inventory_csv_round_trips_unicode_commas_newlines_and_candidate_records(self):
        unusual_name = "带,逗号\n桥.mp4"
        (self.sources / unusual_name).write_bytes(b"small fixture")
        with mock.patch("cinematicdx.cli.software_provenance", return_value={}):
            status, _, _ = self.call([
                "inventory", "--root", str(self.sources), "--metadata", str(self.metadata),
                "--output", str(self.output),
            ])
        self.assertEqual(0, status)
        with (self.output / "inventory.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(3, len(rows))
        self.assertIn(unusual_name, {row["relative_path"] for row in rows})
        matched = next(row for row in rows if row["relative_path"] == "桥（1949）.mp4")
        candidates = json.loads(matched["metadata_candidates"])
        self.assertEqual("qiao", candidates[0]["film_key"])
        self.assertEqual("candidate_only", candidates[0]["status"])
        for row in rows:
            self.assertIsInstance(json.loads(row["flags"]), list)

    def test_file_replacement_during_header_probe_is_a_reported_per_file_failure(self):
        def replace_source(path, **options):
            replacement = self.root / "replacement.mp4"
            replacement.write_bytes(Path(path).read_bytes())
            replacement.replace(path)
            return {"quality_flags": ["header_only"]}

        with mock.patch("cinematicdx.cli.probe_video", side_effect=replace_source), \
                mock.patch("cinematicdx.cli.software_provenance", return_value={}):
            status, stdout, _ = self.call([
                "inventory", "--root", str(self.sources), "--output", str(self.output), "--probe-headers",
            ])
        self.assertEqual(0, status)
        self.assertEqual(2, json.loads(stdout)["summary"]["header_probes_failed"])
        inventory = json.loads((self.output / "inventory.json").read_text(encoding="utf-8"))
        self.assertTrue(all(video["header_probe_status"] == "failed" for video in inventory["videos"]))
        self.assertTrue(all("changed during header probing" in video["header_probe_error"]
                            for video in inventory["videos"]))

    def test_metadata_replacement_during_inventory_prevents_audit_publication(self):
        def replace_metadata(*args, **options):
            replacement = self.root / "replacement.json"
            replacement.write_bytes(self.metadata.read_bytes())
            replacement.replace(self.metadata)
            return {"quality_flags": ["header_only"]}

        with mock.patch("cinematicdx.cli.probe_video", side_effect=replace_metadata):
            status, stdout, stderr = self.call([
                "inventory", "--root", str(self.sources), "--metadata", str(self.metadata),
                "--output", str(self.output), "--probe-headers",
            ])
        self.assertEqual(2, status)
        self.assertEqual("", stdout)
        self.assertIn("Metadata changed during inventory", stderr)
        self.assertFalse(self.output.exists())

    def test_real_unknown_film_error_is_reported_without_hash_probe_or_published_run(self):
        with mock.patch("cinematicdx.ingest.hash_video") as hasher, \
                mock.patch("cinematicdx.ingest.probe_video") as probe:
            status, stdout, stderr = self.call([
                "ingest", "--video", str(self.sources / "桥（1949）.mp4"),
                "--metadata", str(self.metadata), "--film-id", "unknown", "--output", str(self.output),
            ])
        self.assertEqual(2, status)
        self.assertEqual("", stdout)
        self.assertIn("explicit film ID", stderr)
        hasher.assert_not_called()
        probe.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_existing_audit_output_is_rejected_before_source_scan(self):
        self.output.mkdir(parents=True)
        sentinel = self.output / "keep.json"
        sentinel.write_bytes(b"original")
        with mock.patch("cinematicdx.cli.inventory_directory") as inventory:
            status, stdout, stderr = self.call([
                "inventory", "--root", str(self.sources), "--output", str(self.output),
            ])
        self.assertEqual(2, status)
        self.assertEqual("", stdout)
        self.assertIn("Output already exists", stderr)
        self.assertEqual(b"original", sentinel.read_bytes())
        inventory.assert_not_called()

    def test_explicit_film_id_is_required_and_never_inferred_from_video_filename(self):
        with mock.patch("cinematicdx.cli.ingest_video") as ingestion:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main(["ingest", "--video", "桥（1949）.mp4", "--metadata", str(self.metadata),
                              "--output", str(self.output)])
            self.assertEqual(2, error.exception.code)
        ingestion.assert_not_called()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
