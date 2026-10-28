"""Read-only video inventory and explicit metadata identities, using only the stdlib."""

import json
import os
import re
import stat
import unicodedata
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


VIDEO_SUFFIXES = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".mpeg", ".mpg", ".m4v", ".webm", ".ts",
    ".vob", ".wmv", ".m2ts", ".flv", ".rm", ".rmvb", ".asf", ".3gp", ".mts",
})
_SYSTEM_NAMES = frozenset({
    ".ds_store", "thumbs.db", "desktop.ini", "icon\r", "__macosx", "$recycle.bin",
    "system volume information", "recycled", "recycler", "lost+found",
})
_YEAR_TOKEN = re.compile(r"(?<![^\W_])((?:18|19|20)\d{2})(?:年)?(?![^\W_])")
_TECHNICAL_TOKEN = re.compile(
    r"(?<![^\W_])(?:\d{3,4}p|[248]k|[hx][ ._-]?26[45]|hevc|avc|bluray|blu[ ._-]?ray|"
    r"webrip|web[ ._-]?dl|dvdrip|bdrip|remux)(?![^\W_])", re.IGNORECASE
)
_LEADING_INDEX = re.compile(r"^\s*\d{1,3}[\s._、-]+")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key: {!r}".format(key))
        result[key] = value
    return result


def _invalid_json_constant(value):
    raise ValueError("Non-finite JSON number is not supported: " + value)


def load_metadata(path: Path) -> Dict[str, Any]:
    """Read research JSON or catalog v1 without writing or silently merging identities.

    Normalized records retain the complete original record in ``raw_record``. IDs are
    supplied by metadata, never generated from a title, array index or filename.
    """
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Metadata source must be a JSON file: " + str(source))
    with source.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle, object_pairs_hook=_unique_json_object,
                         parse_constant=_invalid_json_constant)
    if not isinstance(data, dict) or not isinstance(data.get("films"), list):
        raise ValueError("Metadata JSON must contain a films array.")
    if "schema_version" in data:
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported local metadata catalog schema version.")
        source_format = "local-catalog-v1"
        key_field, title_field, year_field = "film_key", "title_original", "production_year"
        catalog_id = data.get("catalog_id")
        try:
            if not isinstance(catalog_id, str):
                raise ValueError("missing catalog ID")
            uuid.UUID(catalog_id)
        except ValueError as exc:
            raise ValueError("A local catalog requires a valid catalog_id UUID.") from exc
    else:
        source_format = "research-json"
        key_field, title_field, year_field = "key", "title", "year"
        catalog_id = None
    records, warnings, seen_keys = [], [], set()
    for index, raw in enumerate(data["films"]):
        if not isinstance(raw, dict):
            raise ValueError("Film record {} must be a JSON object.".format(index + 1))
        key = raw.get(key_field)
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Film record {} requires a nonempty stable key.".format(index + 1))
        if key != key.strip():
            raise ValueError("Film key {!r} contains surrounding whitespace.".format(key))
        if key in seen_keys:
            raise ValueError("Duplicate film key: {!r}".format(key))
        seen_keys.add(key)
        title = raw.get(title_field)
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Film {!r} requires an original title.".format(key))
        year = raw.get(year_field)
        if isinstance(year, str) and re.fullmatch(r"[0-9]{4}", year.strip()):
            year = int(year.strip())
            warnings.append({"film_key": key, "code": "year_parsed_from_text"})
        if year is not None and type(year) is not int:
            raise ValueError("Film {!r} year must be an integer or null.".format(key))
        records.append({
            "film_key": key,
            "title_original": title.strip(),
            "production_year": year,
            "raw_source_format": source_format,
            "raw_record": raw,
        })
    return {
        "format": source_format,
        "raw_source_format": source_format,
        "source_path": str(source),
        "catalog_id": catalog_id,
        "namespace": catalog_id if catalog_id is not None else "research-inventory",
        "record_count": len(records),
        "records": records,
        "warnings": warnings,
    }


def metadata_records(path: Path) -> Dict[str, Dict[str, Any]]:
    """Return normalized records indexed by their explicitly supplied stable key."""
    return {record["film_key"]: record for record in load_metadata(path)["records"]}


def normalize_title(value: str) -> str:
    """Comparison-only Unicode normalization; never used to create a stable ID."""
    return "".join(character for character in unicodedata.normalize("NFKC", value).casefold()
                   if character.isalnum())


def match_metadata_candidates(relative_path, records: Mapping[str, Mapping[str, Any]]):
    """Offer conservative filename candidates; these are never confirmed identities.

    Exact normalized title/key equality is required after removal of bounded year,
    index and technical tokens. A short title is never matched as a substring of a
    different title. An explicit conflicting filename year excludes a candidate.
    """
    stem = unicodedata.normalize("NFKC", Path(relative_path).stem)
    years = sorted({int(match.group(1)) for match in _YEAR_TOKEN.finditer(stem)})
    stripped = _TECHNICAL_TOKEN.sub(" ", stem)
    stripped = _YEAR_TOKEN.sub(" ", stripped)
    stripped = _LEADING_INDEX.sub("", stripped)
    full_name, clean_name = normalize_title(stem), normalize_title(stripped)
    candidates = []
    for key, record in records.items():
        title = normalize_title(record["title_original"])
        if title and full_name == title:
            basis = "exact_filename_title"
            candidate_year = None  # A year token may be part of the title itself.
        elif title and clean_name == title:
            basis = "normalized_filename_title"
            candidate_year = years[0] if len(years) == 1 else None
        elif normalize_title(key) and normalize_title(key) in (full_name, clean_name):
            basis = "normalized_filename_key"
            candidate_year = years[0] if len(years) == 1 else None
        else:
            continue
        record_year = record.get("production_year")
        if candidate_year is not None and record_year is not None and candidate_year != record_year:
            continue
        candidates.append({
            "film_key": key,
            "title_original": record["title_original"],
            "production_year": record_year,
            "status": "candidate_only",
            "match_basis": basis,
            "filename_year": candidate_year,
            "flags": ["multiple_filename_years"] if len(years) > 1 else [],
        })
    return sorted(candidates, key=lambda candidate: candidate["film_key"])


def inventory_directory(root: Path, metadata_path: Optional[Path] = None) -> Dict[str, Any]:
    """Inventory a supplied directory without following links, hashing or decoding.

    ``readable`` reports a permission/access check, not successful media decoding.
    Excluded directory counts refer to encountered entries; their contents are not
    traversed. Incomplete scans remain explicit through errors and scan_complete.
    """
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("The inventory root must not be a symbolic link.")
    root_stat = requested.lstat()
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ValueError("The inventory root must be an existing directory.")
    directory = requested.resolve(strict=True)
    metadata = load_metadata(metadata_path) if metadata_path is not None else None
    records = {record["film_key"]: record for record in metadata["records"]} if metadata else {}
    videos, skipped, errors = [], [], []
    exclusions = Counter({"hidden": 0, "system": 0, "symlink": 0,
                          "non_video": 0, "non_regular": 0})
    counts = {"directories_scanned": 0, "entries_seen": 0}

    def relative(path):
        return Path(path).relative_to(directory).as_posix()

    def skip(path, reason):
        exclusions[reason] += 1
        skipped.append({"relative_path": relative(path), "reason": reason})

    def error(path, operation, exception):
        errors.append({"relative_path": relative(path), "operation": operation,
                       "error_type": type(exception).__name__, "message": str(exception)})

    def video_record(path, details=None, failure=None):
        flags = []
        if details is None:
            flags.extend(["stat_error", "unreadable"])
            size, mtime, readable = None, None, False
        else:
            size, mtime = details.st_size, details.st_mtime_ns
            try:
                readable = bool(details.st_mode & 0o444) and os.access(path, os.R_OK)
            except OSError as exc:
                readable = False
                error(path, "access", exc)
            if not readable:
                flags.append("unreadable")
            if size == 0:
                flags.append("empty_file")
        item = {"relative_path": relative(path), "extension": Path(path).suffix.lower(),
                "size_bytes": size, "mtime_ns": mtime, "readable": readable,
                "flags": flags, "metadata_candidates": match_metadata_candidates(relative(path), records)}
        if failure is not None:
            item["stat_error"] = {"error_type": type(failure).__name__, "message": str(failure)}
        videos.append(item)

    pending = [directory]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as handle:
                entries = sorted(handle, key=lambda entry: (entry.name.casefold(), entry.name))
            counts["directories_scanned"] += 1
        except OSError as exc:
            error(current, "scandir", exc)
            continue
        child_directories = []
        for entry in entries:
            counts["entries_seen"] += 1
            path = Path(entry.path)
            if entry.name.casefold() in _SYSTEM_NAMES:
                skip(path, "system")
                continue
            if entry.name.startswith("."):
                skip(path, "hidden")
                continue
            try:
                details = entry.stat(follow_symlinks=False)
            except OSError as exc:
                error(path, "stat", exc)
                if path.suffix.lower() in VIDEO_SUFFIXES:
                    video_record(path, failure=exc)
                continue
            if stat.S_ISLNK(details.st_mode):
                skip(path, "symlink")
            elif stat.S_ISDIR(details.st_mode):
                child_directories.append(path)
            elif not stat.S_ISREG(details.st_mode):
                skip(path, "non_regular")
            elif path.suffix.lower() not in VIDEO_SUFFIXES:
                skip(path, "non_video")
            else:
                video_record(path, details=details)
        pending.extend(reversed(child_directories))
    order = lambda item: (item["relative_path"].casefold(), item["relative_path"])
    videos.sort(key=order)
    skipped.sort(key=order)
    errors.sort(key=lambda item: (item["relative_path"], item["operation"], item["error_type"]))
    extension_totals = Counter(item["extension"] for item in videos)
    metadata_summary = None
    if metadata:
        metadata_summary = {key: metadata[key] for key in
                            ("format", "raw_source_format", "source_path", "catalog_id", "namespace",
                             "record_count", "warnings")}
    return {
        "schema_version": 1,
        "root": str(directory),
        "scan_complete": not errors,
        "readability_check": "mode_read_bits_and_os_access; no media opened or decoded",
        "metadata_source": metadata_summary,
        "summary": {
            **counts,
            "video_count": len(videos),
            "total_bytes": sum(item["size_bytes"] for item in videos if item["size_bytes"] is not None),
            "unknown_size_count": sum(item["size_bytes"] is None for item in videos),
            "empty_file_count": sum("empty_file" in item["flags"] for item in videos),
            "unreadable_count": sum(not item["readable"] for item in videos),
            "files_with_metadata_candidates": sum(bool(item["metadata_candidates"]) for item in videos),
            "extension_totals": dict(sorted(extension_totals.items())),
            "excluded_entries": dict(exclusions),
            "error_count": len(errors),
        },
        "videos": videos,
        "skipped": skipped,
        "errors": errors,
    }
