"""Version a source refresh and remeasure only changed film files.

Existing measurements retain their original receipts. A new run links to them
only after checking file state, extractor configuration and output digests.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analysis-python"))
from cinematicdx.corpus_luminance import build_plan, run_film_job
from cinematicdx.corpus_editing import run_job
from cinematicdx.ingest import hash_video, source_state


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def validate_outputs(directory):
    receipt = read(directory / "run.json")
    for filename, record in receipt["outputs"].items():
        expected = record["sha256"] if isinstance(record, dict) else record
        if sha(directory / filename) != expected:
            raise ValueError(f"Changed saved measurement: {directory / filename}")
    return receipt


def prepare(args):
    out = args.output_directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    parent = args.luminance_parent.resolve()
    old_plan = read(parent / "plan.json")
    plan = build_plan(old_plan["metadata_path"], old_plan["video_root"], old_plan["identity_map_path"])
    if plan["video_file_count"] != args.expected_videos:
        raise ValueError("Current video count differs from the requested inventory.")
    old_jobs = {job["relative_path"]: job for job in old_plan["jobs"]}
    if set(old_jobs) != {job["relative_path"] for job in plan["jobs"]}:
        raise ValueError("Paths were added or removed. Review identity links before refreshing.")
    changed, unchanged = [], []
    versions = {}
    for job in plan["jobs"]:
        previous = old_jobs[job["relative_path"]]
        receipt = read(parent / "films" / previous["job_id"] / "run.json")
        state = source_state(job["source_path"])
        version = receipt["video_version_id"]
        if state != tuple(receipt["source_state"]):
            digest, size, checked_state = hash_video(job["source_path"])
            version = "sha256:" + digest
            changed.append(dict(job_id=job["job_id"], film_key=job["film_key"], title=job["title"],
                relative_path=job["relative_path"], previous_video_version_id=receipt["video_version_id"],
                video_version_id=version, previous_size_bytes=receipt["source_bytes"], size_bytes=size,
                previous_source_state=receipt["source_state"], source_state=list(checked_state),
                bytes_changed=version != receipt["video_version_id"]))
        else:
            unchanged.append(job["job_id"])
        versions[job["job_id"]] = version
    if len(changed) != args.expected_changes:
        raise ValueError(f"Expected {args.expected_changes} changed sources, found {len(changed)}.")
    changed_ids = {row["job_id"] for row in changed}
    for name, old_run in [("luminance", parent), ("editing", args.editing_parent.resolve())]:
        run = out / name
        run.mkdir()
        (run / "films").mkdir()
        config = read(old_run / "config.json")
        for filename, expected in config["source_hashes"].items():
            if sha(ROOT / filename) != expected:
                raise ValueError(f"Frozen extraction code differs: {filename}")
        if name == "luminance":
            shutil.copy2(old_run / "config.json", run / "config.json")
            shutil.copy2(old_run / "sampling_validation.json", run / "sampling_validation.json")
            config_films = set(config["sampling_validation"]["film_keys"])
            if config_films.intersection(row["film_key"] for row in changed):
                raise ValueError("A sampling-validation source changed. Revalidate before extraction.")
            current_plan = plan
        else:
            config.update(scope="454 researcher-curated source videos, complete frame decoding.",
                job_count=len(plan["jobs"]), grouping="Exact production.name; equal film; co-production 1/k; retain all metadata rows.",
                refresh_parent_run=str(old_run))
            write(run / "config.json", config)
            current_plan = dict(plan, artifact_kind="studio_editing_corpus_plan", raw_video_file_count=len(plan["jobs"]), jobs=[dict(job,
                video_version_id=versions[job["job_id"]], previous_source_state=list(source_state(job["source_path"])))
                for job in plan["jobs"]])
            (run / "preflight").symlink_to(old_run / "preflight", target_is_directory=True)
            reference = read(old_run / "preflight/results.json")
            if reference["source_version"] not in {versions[j["job_id"]] for j in plan["jobs"] if j["film_key"] == "shang gan ling"}:
                raise ValueError("The manually validated source changed. Review annotation alignment.")
        write(run / "plan.json", current_plan)
        inherited = []
        for job in plan["jobs"]:
            if job["job_id"] in changed_ids:
                continue
            directory = old_run / "films" / job["job_id"]
            receipt = validate_outputs(directory)
            if tuple(receipt["source_state"]) != source_state(job["source_path"]):
                raise ValueError("Unchanged source state changed during preparation.")
            (run / "films" / job["job_id"]).symlink_to(directory, target_is_directory=True)
            inherited.append(dict(job_id=job["job_id"], parent_run=str(old_run),
                receipt_sha256=sha(directory / "run.json"), config_sha256=receipt["config_sha256"],
                video_version_id=versions[job["job_id"]]))
        write(run / "measurement_reuse.json", dict(schema_version=1, inherited_jobs=inherited,
            new_job_ids=sorted(changed_ids), state_checks="device/inode/size/mtime/ctime against original extraction receipts",
            unchanged_video_bytes_rehashed=False, inherited_receipts_modified=False))
    old_overrides = read(parent / "identity_overrides.json")
    valid = [binding for binding in old_overrides["bindings"]
             if versions.get(binding["job_id"]) == binding["expected_video_version_id"]]
    write(out / "luminance/identity_overrides.json", dict(old_overrides, bindings=valid,
        retained_only_for_matching_video_versions=True))
    write(out / "refresh.json", dict(schema_version=1, created_at_utc=datetime.now(timezone.utc).isoformat(),
        previous_luminance_run=str(parent), previous_editing_run=str(args.editing_parent.resolve()),
        metadata_sha256=plan["metadata_sha256"], video_count=plan["video_file_count"],
        changed_sources=changed, unchanged_sources=len(unchanged),
        extraction_parameters_changed=False, script_sha256=sha(__file__)))
    print(json.dumps(dict(output=str(out),changed=changed,unchanged=len(unchanged)), ensure_ascii=False),flush=True)


def extract(out):
    refresh = read(out / "refresh.json")
    changed_ids = {row["job_id"] for row in refresh["changed_sources"]}
    for name, worker in [("luminance", run_film_job), ("editing", run_job)]:
        run = out / name
        plan = read(run / "plan.json")
        config = read(run / "config.json")
        reuse = read(run / "measurement_reuse.json")
        if set(reuse["new_job_ids"]) != changed_ids:
            raise ValueError("The extraction selection differs from the recorded source refresh.")
        for filename, expected in config["source_hashes"].items():
            if sha(ROOT / filename) != expected:
                raise ValueError(f"Frozen extraction code changed: {filename}")
        if sha(plan["metadata_path"]) != plan["metadata_sha256"]:
            raise ValueError("Metadata changed after refresh preparation.")
        if sha(plan["identity_map_path"]) != plan["identity_map_sha256"]:
            raise ValueError("Identity mapping changed after refresh preparation.")
        validation = read(run / ("sampling_validation.json" if name == "luminance" else "preflight/results.json"))
        passed = validation["primary_acceptance_passed"] if name == "luminance" else validation["hard_cut_preflight_passed"]
        if not passed:
            raise ValueError("The inherited method validation did not pass.")
        config_hash = sha(run / "config.json")
        jobs = [job for job in plan["jobs"] if job["job_id"] in changed_ids]
        if len(jobs) != len(changed_ids):
            raise ValueError("The refresh contains missing or duplicate extraction jobs.")
        for job in jobs:
            directory = run / "films" / job["job_id"]
            if directory.exists() and not (directory / "run.json").exists():
                raise ValueError(f"Preserve and inspect the incomplete job before retrying: {directory}")
        completion_path = run / "extraction_complete.json"
        if completion_path.exists():
            completion = read(completion_path)
            completed_ids = ({item["job_id"] for item in completion["completed"]} if name == "luminance"
                             else set(completion["complete"]))
            if completion["failed"] or completed_ids != {job["job_id"] for job in plan["jobs"]}:
                raise ValueError("Preserve and inspect the incomplete extraction receipt before retrying.")
            for job in jobs:
                receipt = validate_outputs(run / "films" / job["job_id"])
                if receipt["config_sha256"] != config_hash or tuple(receipt["source_state"]) != source_state(job["source_path"]):
                    raise ValueError("A completed refresh job changed before resume.")
            print(json.dumps(dict(stage=name,status="existing_completion_verified",jobs=len(plan["jobs"]))),flush=True)
            continue
        with ProcessPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(worker, job, str(run), config_hash): job for job in jobs}
            for future in as_completed(futures):
                document = future.result()
                print(json.dumps(dict(stage=name,title=futures[future]["title"],status="complete",
                    elapsed_seconds=document["elapsed_seconds"]),ensure_ascii=False),flush=True)
        if name == "luminance":
            completed = [dict(job_id=job["job_id"],film_key=job["film_key"],
                video_version_id=read(run/"films"/job["job_id"]/"summary.json")["video_version_id"]) for job in plan["jobs"]]
            done = dict(completed=completed,failed=[],full_corpus_attempted=len(completed),
                remeasured_jobs=len(jobs),inherited_jobs=len(completed)-len(jobs),config_sha256=config_hash)
        else:
            done = dict(complete=[j["job_id"] for j in plan["jobs"]], failed=[],attempted=len(plan["jobs"]),
                remeasured_jobs=len(jobs),inherited_jobs=len(plan["jobs"])-len(jobs),config_sha256=config_hash)
        done["elapsed_seconds"] = sum(read(run/"films"/job["job_id"]/"summary.json")["elapsed_seconds"] for job in jobs)
        done["elapsed_seconds_basis"] = "Sum of measured elapsed times for the newly extracted jobs. Inherited extraction cost excluded."
        if name == "editing":
            write(run/"effective_extraction_complete.json",done)
        write(run/"extraction_complete.json",done)
        print(json.dumps(dict(stage=name,status="extraction_complete",jobs=len(plan["jobs"])),ensure_ascii=False),flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--luminance-parent",type=Path)
    parser.add_argument("--editing-parent",type=Path)
    parser.add_argument("--expected-videos",type=int,default=454)
    parser.add_argument("--expected-changes",type=int,default=3)
    parser.add_argument("--extract",action="store_true")
    args = parser.parse_args()
    if args.extract:
        extract(args.output_directory.resolve())
    else:
        if args.luminance_parent is None or args.editing_parent is None:
            parser.error("Preparation requires both parent runs.")
        prepare(args)


if __name__ == "__main__":
    main()
