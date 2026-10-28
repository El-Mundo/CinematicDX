"""Traceable ingestion of one explicitly identified source video; no transcoding."""

import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
from datetime import datetime, timezone
from uuid import uuid4

from . import __version__
from .inventory import load_metadata
from .probe import probe_video


class IngestError(Exception):
    """A source could not be registered without compromising provenance."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def source_state(path):
    info = Path(path).stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def hash_video(path):
    """Hash complete file bytes, checking the opened file did not change while read."""
    digest = hashlib.sha256()
    count = 0
    with Path(path).open("rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size == 0:
            raise IngestError("The video must be a non-empty regular file.")
        while True:
            chunk = source.read(4 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            count += len(chunk)
        after = os.fstat(source.fileno())
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                              value.st_mtime_ns, value.st_ctime_ns)
    if identity(before) != identity(after) or count != before.st_size:
        raise IngestError("The source changed while its file checksum was being calculated.")
    return digest.hexdigest(), count, identity(before)


def software_provenance():
    package = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(package.glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    result = {"pipeline_version": __version__, "python_version": platform.python_version(),
              "platform": platform.platform(), "pipeline_source_sha256": digest.hexdigest(),
              "git_revision": None, "git_worktree_dirty": None}
    repository = package.parent.parent
    try:
        revision = subprocess.run(["git", "-C", str(repository), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, timeout=5, check=True)
        status_result = subprocess.run(["git", "-C", str(repository), "status", "--porcelain"],
                                       capture_output=True, text=True, timeout=5, check=True)
        result.update(git_revision=revision.stdout.strip(),
                      git_worktree_dirty=bool(status_result.stdout.strip()))
    except (OSError, subprocess.SubprocessError):
        pass
    return result


def publish_bundle(output_dir, payloads):
    """Create an exclusive run directory; write its successful run receipt last.

    Existing directories are never reused. On write failure remove only files
    created by this invocation, without deleting unrelated files.
    """
    output = Path(output_dir).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise IngestError("Output already exists; choose a new run directory: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    owned_directory = False
    try:
        output.mkdir()
        owned_directory = True
        names = [name for name in payloads if name != "run.json"]
        if "run.json" in payloads:
            names.append("run.json")
        for name in names:
            if Path(name).name != name:
                raise IngestError("Artifact names must be simple filenames.")
            path = output / name
            with path.open("xb") as destination:
                created.append(path)
                destination.write(payloads[name])
                destination.flush()
                os.fsync(destination.fileno())
    except BaseException:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        if owned_directory:
            try:
                output.rmdir()
            except OSError:
                pass
        raise
    return output


def ingest_video(video_path, metadata_path, film_id, output_dir, *, source_description=None,
                 source_uri=None, metadata_namespace=None, ffprobe="ffprobe", stream_index=None,
                 timestamp_sample_frames=12):
    output = Path(output_dir).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise IngestError("Output already exists; choose a new run directory: " + str(output))
    if timestamp_sample_frames <= 0:
        raise IngestError("Single-film ingestion requires a positive timestamp sample size.")
    started = utc_now()
    requested_path = Path(video_path).expanduser().absolute()
    video = requested_path.resolve(strict=True)
    metadata_file = Path(metadata_path).expanduser().resolve(strict=True)
    metadata_before = source_state(metadata_file)
    metadata_bytes = metadata_file.read_bytes()
    metadata = load_metadata(metadata_file)
    records = {record["film_key"]: record for record in metadata["records"]}
    if film_id not in records:
        raise IngestError("The explicit film ID does not exist in the metadata source: " + film_id)
    if metadata_before != source_state(metadata_file):
        raise IngestError("Metadata changed while it was being read.")
    record = records[film_id]
    namespace = metadata.get("catalog_id") or metadata_namespace or "research-inventory"
    if not isinstance(namespace, str) or not namespace.strip():
        raise IngestError("A non-empty metadata namespace is required.")
    software = software_provenance()
    sha256, size, video_before = hash_video(video)
    probe = probe_video(video, ffprobe=ffprobe, stream_index=stream_index,
                        timestamp_sample_frames=timestamp_sample_frames)
    if video_before != source_state(video) or requested_path.resolve(strict=True) != video:
        raise IngestError("The video changed or was replaced during ingestion; no run was published.")
    if metadata_before != source_state(metadata_file):
        raise IngestError("Metadata changed during ingestion; no run was published.")
    run_id = str(uuid4())
    flags = list(probe.get("quality_flags", []))
    if not source_description or not source_description.strip():
        flags.append("source_provenance_unknown")
    technical = probe["technical_summary"]
    manifest = {
        "schema_version": 1, "artifact_kind": "source_video_manifest", "run_id": run_id,
        "film_id": film_id, "film_reference": {"namespace": namespace, "key": film_id},
        "film_title": record.get("title_original"), "production_year": record.get("production_year"),
        "video_version_id": "sha256:" + sha256,
        "source": {"requested_path": str(requested_path), "resolved_path": str(video),
                   "size_bytes": size, "sha256": sha256, "hash_scope": "entire_file_bytes",
                   "mtime_ns": video_before[3], "description": source_description,
                   "source_uri": source_uri, "transfer_history": None},
        "metadata": {"format": metadata["format"], "source_path": str(metadata_file),
                     "source_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                     "record_key": film_id, "raw_record": record["raw_record"]},
        "selected_video_stream_index": probe["selected_video_stream_index"],
        "timeline": technical,
        "quality_flags": sorted(set(flags)),
        "validation": {"film_link": "explicit_metadata_key", "source_bytes": "full_sha256_read",
                       "technical_probe": "passed", "timestamp_validation": "bounded_sample_only",
                       "full_decode": "not_performed", "source_authenticity": "not_assessed"},
    }
    artifacts = {"source_manifest.json": json_bytes(manifest), "probe.json": json_bytes(probe),
                 "timestamp_sample.json": json_bytes(probe["timestamp_sample"])}
    run = {
        "schema_version": 1, "artifact_kind": "ingestion_run", "run_id": run_id, "status": "complete",
        "started_at_utc": started, "completed_at_utc": utc_now(), "software": software,
        "parameters": {"film_id": film_id, "metadata_namespace": namespace,
                       "ffprobe_executable": ffprobe, "stream_index": stream_index,
                       "timestamp_sample_frames": timestamp_sample_frames},
        "outputs": {name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
                    for name, data in artifacts.items()},
        "limitations": ["Exact-file identity does not identify a historical print or restoration.",
                        "Probe and timestamp samples do not certify full-file decoding or constant frame rate.",
                        "No shot detection, transcoding or interpretation was performed."],
    }
    artifacts["run.json"] = json_bytes(run)
    publish_bundle(output, artifacts)
    return {"run_id": run_id, "film_id": film_id, "video_version_id": manifest["video_version_id"],
            "output_directory": str(output), "quality_flags": manifest["quality_flags"]}
