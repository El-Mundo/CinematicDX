"""Inventory checks use temporary files and never need the research video corpus."""

import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cinematicdx.inventory import (
    VIDEO_SUFFIXES,
    inventory_directory,
    load_metadata,
    match_metadata_candidates,
    metadata_records,
)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write_metadata(self, data, name="metadata.json"):
        path = self.root / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def raw_metadata(self):
        return {"films": [
            {"key": "qiao", "title": "桥", "year": 1949, "directorNameArray": ["王滨"]},
            {"key": "daqiao", "title": "大桥", "year": 1950},
            {"key": "other-qiao", "title": "桥", "year": 1951},
        ]}

    def test_inventory_is_deterministic_and_counts_broad_extensions_bytes_and_empty_files(self):
        (self.root / "nested").mkdir()
        (self.root / "B.MKV").write_bytes(b"1234")
        (self.root / "a.mp4").write_bytes(b"123")
        (self.root / "nested" / "clip.RMVB").write_bytes(b"12")
        (self.root / "nested" / "empty.avi").touch()
        (self.root / "notes.txt").write_text("not a video", encoding="utf-8")
        result = inventory_directory(self.root)
        self.assertEqual(result, inventory_directory(self.root))
        self.assertEqual(4, result["summary"]["video_count"])
        self.assertEqual(9, result["summary"]["total_bytes"])
        self.assertEqual(1, result["summary"]["empty_file_count"])
        self.assertEqual(2, result["summary"]["directories_scanned"])
        self.assertTrue(result["scan_complete"])
        self.assertEqual(["a.mp4", "B.MKV", "nested/clip.RMVB", "nested/empty.avi"],
                         [item["relative_path"] for item in result["videos"]])
        self.assertEqual({".avi": 1, ".mkv": 1, ".mp4": 1, ".rmvb": 1},
                         result["summary"]["extension_totals"])
        self.assertIn("empty_file", result["videos"][-1]["flags"])
        self.assertIsInstance(result["videos"][0]["mtime_ns"], int)
        self.assertFalse(any("hash" in item for item in result["videos"]))
        for suffix in (".mp4", ".mkv", ".rmvb", ".m2ts", ".vob", ".3gp", ".mts"):
            self.assertIn(suffix, VIDEO_SUFFIXES)

    def test_hidden_and_system_entries_are_excluded_without_traversal(self):
        (self.root / ".hidden").mkdir()
        (self.root / ".hidden" / "secret.mp4").write_bytes(b"not scanned")
        (self.root / ".another.mp4").touch()
        (self.root / "__MACOSX").mkdir()
        (self.root / "__MACOSX" / "copy.mp4").touch()
        (self.root / ".DS_Store").write_bytes(b"finder")
        (self.root / "Thumbs.db").touch()
        result = inventory_directory(self.root)
        self.assertEqual(0, result["summary"]["video_count"])
        self.assertEqual(2, result["summary"]["excluded_entries"]["hidden"])
        self.assertEqual(3, result["summary"]["excluded_entries"]["system"])
        self.assertEqual(1, result["summary"]["directories_scanned"])
        self.assertEqual(5, len(result["skipped"]))

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links unavailable")
    def test_symlinks_to_files_directories_loops_and_missing_targets_are_not_followed(self):
        (self.root / "original.mp4").write_bytes(b"original")
        (self.root / "linked.mp4").symlink_to(self.root / "original.mp4")
        (self.root / "loop").symlink_to(self.root, target_is_directory=True)
        (self.root / "missing.mp4").symlink_to(self.root / "missing-target")
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside))
        (outside / "outside.mp4").write_bytes(b"not scanned")
        (self.root / "outside").symlink_to(outside, target_is_directory=True)
        result = inventory_directory(self.root)
        self.assertEqual(1, result["summary"]["video_count"])
        self.assertEqual(4, result["summary"]["excluded_entries"]["symlink"])
        self.assertEqual(1, result["summary"]["directories_scanned"])
        self.assertEqual([], result["errors"])
        with self.assertRaises(ValueError):
            inventory_directory(self.root / "loop")

    def test_permission_access_check_is_explicit_and_does_not_open_video(self):
        (self.root / "blocked.mp4").write_bytes(b"video bytes")
        with mock.patch("cinematicdx.inventory.os.access", return_value=False):
            result = inventory_directory(self.root)
        video = result["videos"][0]
        self.assertFalse(video["readable"])
        self.assertIn("unreadable", video["flags"])
        self.assertEqual(1, result["summary"]["unreadable_count"])
        self.assertIn("no media opened or decoded", result["readability_check"])

    def test_stat_failure_keeps_video_record_with_unknown_size_and_explicit_error(self):
        (self.root / "broken.mp4").write_bytes(b"video")
        real_scandir = os.scandir

        class StatFailure:
            name = "broken.mp4"
            path = str(self.root.resolve() / "broken.mp4")

            def stat(self, *, follow_symlinks):
                if follow_symlinks:
                    raise AssertionError("Inventory must not follow links")
                raise PermissionError("simulated stat failure")

        @contextlib.contextmanager
        def scanning(path):
            with real_scandir(path) as entries:
                yield [StatFailure() if entry.name == "broken.mp4" else entry for entry in entries]

        with mock.patch("cinematicdx.inventory.os.scandir", side_effect=scanning):
            result = inventory_directory(self.root)
        self.assertFalse(result["scan_complete"])
        self.assertEqual(1, result["summary"]["video_count"])
        self.assertEqual(1, result["summary"]["unknown_size_count"])
        self.assertEqual(0, result["summary"]["total_bytes"])
        self.assertIsNone(result["videos"][0]["size_bytes"])
        self.assertIsNone(result["videos"][0]["mtime_ns"])
        self.assertEqual("stat", result["errors"][0]["operation"])
        self.assertEqual("PermissionError", result["videos"][0]["stat_error"]["error_type"])

    def test_unreadable_subdirectory_is_reported_as_incomplete_scan(self):
        (self.root / "denied").mkdir()
        (self.root / "denied" / "hidden-by-error.mp4").touch()
        (self.root / "readable.mp4").write_bytes(b"1")
        real_scandir = os.scandir

        def scanning(path):
            if Path(path).name == "denied":
                raise PermissionError("simulated directory read failure")
            return real_scandir(path)

        with mock.patch("cinematicdx.inventory.os.scandir", side_effect=scanning):
            result = inventory_directory(self.root)
        self.assertFalse(result["scan_complete"])
        self.assertEqual(1, result["summary"]["video_count"])
        self.assertEqual("denied", result["errors"][0]["relative_path"])
        self.assertEqual("scandir", result["errors"][0]["operation"])

    def test_non_directory_and_missing_root_fail_without_creating_files(self):
        path = self.root / "file.mp4"
        path.touch()
        with self.assertRaises(ValueError):
            inventory_directory(path)
        with self.assertRaises(OSError):
            inventory_directory(self.root / "missing")
        self.assertFalse((self.root / "missing").exists())

    def test_research_metadata_retains_raw_fields_and_explicit_identity_without_writes(self):
        raw = self.raw_metadata()
        path = self.write_metadata(raw)
        before = path.read_bytes()
        metadata = load_metadata(path)
        self.assertEqual("research-json", metadata["format"])
        self.assertEqual("research-inventory", metadata["namespace"])
        self.assertEqual(3, metadata["record_count"])
        record = metadata_records(path)["qiao"]
        self.assertEqual("桥", record["title_original"])
        self.assertEqual(1949, record["production_year"])
        self.assertEqual(raw["films"][0], record["raw_record"])
        self.assertEqual(before, path.read_bytes())

    def test_local_metadata_uses_catalog_uuid_and_preserves_unknown_records(self):
        catalog_id = "a174e1e9-6338-4ab0-9454-9ac739652faa"
        path = self.write_metadata({"schema_version": 1, "catalog_id": catalog_id, "films": [
            {"id": 1, "film_key": "桥-1949", "title_original": "桥", "production_year": 1949,
             "director": "王滨", "unknown": {"source": True}},
        ]})
        metadata = load_metadata(path)
        self.assertEqual("local-catalog-v1", metadata["raw_source_format"])
        self.assertEqual(catalog_id, metadata["catalog_id"])
        self.assertEqual(catalog_id, metadata["namespace"])
        self.assertEqual({"source": True}, metadata["records"][0]["raw_record"]["unknown"])

    def test_duplicate_blank_and_invalid_metadata_identities_are_rejected(self):
        invalid = [
            {"films": [{"key": "x", "title": "A"}, {"key": "x", "title": "B"}]},
            {"films": [{"key": " ", "title": "A"}]},
            {"films": [{"key": " x ", "title": "A"}]},
            {"films": [{"key": 1, "title": "A"}]},
            {"films": [{"key": "x", "title": ""}]},
            {"films": [{"key": "x", "title": "A", "year": True}]},
            {"films": ["not a record"]},
            {"films": {}},
            {"schema_version": 2, "films": []},
            {"schema_version": True, "films": []},
            {"schema_version": 1, "films": []},
        ]
        for data in invalid:
            with self.subTest(data=data):
                path = self.write_metadata(data)
                before = path.read_bytes()
                with self.assertRaises(ValueError):
                    load_metadata(path)
                self.assertEqual(before, path.read_bytes())
        for source in ('{"films": [], "films": []}', '{"films":[{"key":"x","title":"A","year":NaN}]}'):
            path.write_text(source, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_metadata(path)

    def test_string_year_conversion_is_explicit_in_warnings_and_raw_record(self):
        path = self.write_metadata({"films": [{"key": "x", "title": "A", "year": "1949"}]})
        metadata = load_metadata(path)
        self.assertEqual(1949, metadata["records"][0]["production_year"])
        self.assertEqual("1949", metadata["records"][0]["raw_record"]["year"])
        self.assertEqual("year_parsed_from_text", metadata["warnings"][0]["code"])

    def test_filename_matching_is_candidate_only_exact_title_and_year_aware(self):
        records = metadata_records(self.write_metadata(self.raw_metadata()))
        matches = match_metadata_candidates("nested/001.桥（1949）.1080p.mp4", records)
        self.assertEqual(["qiao"], [item["film_key"] for item in matches])
        self.assertEqual("candidate_only", matches[0]["status"])
        self.assertEqual(1949, matches[0]["filename_year"])
        self.assertEqual([], match_metadata_candidates("桥（1962）.mp4", records))
        self.assertEqual(["other-qiao", "qiao"], [item["film_key"] for item in
                         match_metadata_candidates("桥.mp4", records)])
        self.assertEqual(["daqiao"], [item["film_key"] for item in
                         match_metadata_candidates("大桥（1950）.mp4", records)])
        self.assertEqual([], match_metadata_candidates("桥梁（1949）.mp4", records))
        self.assertEqual(["qiao"], [item["film_key"] for item in
                         match_metadata_candidates("qiao_1949.MKV", records)])

    def test_inventory_metadata_candidates_never_add_a_film_id(self):
        path = self.write_metadata(self.raw_metadata())
        (self.root / "桥 (1949).mp4").write_bytes(b"1")
        result = inventory_directory(self.root, path)
        self.assertEqual(1, result["summary"]["files_with_metadata_candidates"])
        self.assertNotIn("film_id", result["videos"][0])
        self.assertEqual("qiao", result["videos"][0]["metadata_candidates"][0]["film_key"])
        self.assertEqual(3, result["metadata_source"]["record_count"])


if __name__ == "__main__":
    unittest.main()
