"""Publish compact derived tables and figures from a verified source refresh."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analysis-python"))
from cinematicdx.ingest import source_state


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--readme", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    output = args.output_directory.resolve()
    refresh = read(run / "refresh.json")
    lumi = run / "luminance"
    editing = run / "editing"
    lumi_audit = read(lumi / "corpus_audit.json")
    edit_audit = read(editing / "numerical_audit.json")
    sampling = read(lumi / "changed_source_sampling_validation.json")
    if lumi_audit["source_files_changed_after_extraction"] or edit_audit["source_states_changed"]:
        raise ValueError("A measured source changed after extraction.")
    if not sampling["primary_acceptance_passed"]:
        raise ValueError("New source sampling checks did not pass.")
    for name in ("luminance", "editing"):
        plan = read(run / name / "plan.json")
        if sha(Path(plan["metadata_path"])) != plan["metadata_sha256"]:
            raise ValueError("Metadata changed before publication.")
        for job in plan["jobs"]:
            directory = run / name / "films" / job["job_id"]
            receipt = read(directory / "run.json")
            if source_state(job["source_path"]) != tuple(receipt["source_state"]):
                raise ValueError("A source changed before publication: " + job["relative_path"])
            for filename, record in receipt["outputs"].items():
                expected = record["sha256"] if isinstance(record, dict) else record
                if sha(directory / filename) != expected:
                    raise ValueError("A measured output changed before publication.")
        analysis = run / name / "analysis"
        aggregate_receipt = read(analysis / "run.json")
        for filename, field in [("plan.json", "plan_sha256"), ("config.json", "config_sha256"),
                                ("extraction_complete.json", "corpus_extraction_sha256"),
                                ("identity_overrides.json", "identity_override_sha256")]:
            if field in aggregate_receipt and sha(run / name / filename) != aggregate_receipt[field]:
                raise ValueError("An aggregate input changed before publication: " + filename)
        for filename, record in aggregate_receipt["outputs"].items():
            digest = record["sha256"] if isinstance(record, dict) else record
            if sha(analysis / filename) != digest:
                raise ValueError("An aggregate changed before publication: " + filename)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.readme, output / "README.md")
    for name in ("luminance", "editing"):
        destination = output / name
        destination.mkdir()
        analysis = run / name / "analysis"
        for source in sorted(analysis.iterdir()):
            if source.suffix in {".csv", ".png", ".pdf"} or source.name in {
                "summary.json", "REPORT.md", "conditional_studio_reference.json", "conditional_source_width_reference.json"
            }:
                shutil.copy2(source, destination / source.name)
    shutil.copy2(lumi / "colour_label_qa/studio_chroma_flag_sensitivity.csv", output / "luminance")
    for filename in ("films.csv", "studios.csv"):
        shutil.copy2(editing / "edge_challenge" / filename, output / "editing" / ("central_10_90_" + filename))
    checks = output / "validation"
    checks.mkdir()
    for source, name in [
        (lumi / "corpus_audit.json", "luminance_numerical_audit.json"),
        (editing / "numerical_audit.json", "editing_numerical_audit.json"),
        (lumi / "changed_source_sampling_validation.json", "changed_source_sampling_validation.json"),
        (run / "identity_qa/assistant_review.json", "source_identity_review.json"),
        (lumi / "colour_label_qa/assistant_review.json", "chroma_assistant_review.json"),
        (editing / "visual_qa/assistant_review.json", "editing_assistant_review.json"),
    ]:
        shutil.copy2(source, checks / name)
    shutil.copy2(run / "python-tests.log", checks / "python-tests.log")
    old_lumi = Path(refresh["previous_luminance_run"])
    old_edit = Path(refresh["previous_editing_run"])
    old_bindings = {row["job_id"]: row["film_key"] for row in read(old_lumi / "identity_overrides.json")["bindings"]}
    changed = []
    for row in refresh["changed_sources"]:
        job_id = row["job_id"]
        previous = read(old_lumi / "films" / job_id / "summary.json")
        current = read(lumi / "films" / job_id / "summary.json")
        cuts = read(editing / "films" / job_id / "summary.json")
        old_edit_path = old_edit / "films" / job_id / "summary.json"
        previous_cuts = read(old_edit_path) if old_edit_path.exists() else None
        changed.append(dict(film_key=row["film_key"], title=row["title"], year=current["job"]["year"],
            relative_path=row["relative_path"], previous_effective_film_key=old_bindings.get(job_id, row["film_key"]),
            previous_video_version_id=row["previous_video_version_id"], video_version_id=row["video_version_id"],
            previous_size_bytes=row["previous_size_bytes"], size_bytes=row["size_bytes"],
            previous_file_duration_seconds=previous["summary"]["duration_seconds"], duration_seconds=current["summary"]["duration_seconds"],
            previous_width=previous["technical"]["width"], previous_height=previous["technical"]["height"],
            width=current["technical"]["width"], height=current["technical"]["height"],
            previous_file_gray_mean=previous["summary"]["gray_roi_time_mean"], gray_mean=current["summary"]["gray_roi_time_mean"],
            previous_file_l30=previous["summary"]["mean_abs_change_30s_z"], l30=current["summary"]["mean_abs_change_30s_z"],
            previous_cut_candidates=previous_cuts["metrics"]["primary_cut_candidates"] if previous_cuts else None,
            cut_candidates=cuts["metrics"]["primary_cut_candidates"],
            previous_gradual_candidates=previous_cuts["metrics"]["default_gradual_candidates"] if previous_cuts else None,
            gradual_candidates=cuts["metrics"]["default_gradual_candidates"]))
    write_csv(output / "changed_sources.csv", changed)
    plan = read(lumi / "plan.json")
    changed_ids = {row["job_id"] for row in refresh["changed_sources"]}
    source_versions = []
    for job in plan["jobs"]:
        directory = lumi / "films" / job["job_id"]
        receipt = read(directory / "run.json")
        source_versions.append(dict(film_key=job["film_key"], relative_path=job["relative_path"], job_id=job["job_id"],
            video_version_id=receipt["video_version_id"], size_bytes=receipt["source_bytes"],
            measurement_action="remeasured" if job["job_id"] in changed_ids else "inherited",
            luminance_receipt_sha256=sha(directory / "run.json"),
            editing_receipt_sha256=sha(editing / "films" / job["job_id"] / "run.json")))
    write_csv(output / "source_versions.csv", source_versions)
    config_digests = {name: sha(run/name/"config.json") for name in ("luminance", "editing")}
    provenance = dict(schema_version=1, video_count=refresh["video_count"], changed_source_count=len(changed),
        inherited_source_count=refresh["unchanged_sources"], metadata_sha256=refresh["metadata_sha256"],
        extraction_parameters_changed=False, changed_video_hash_scope="complete file bytes",
        unchanged_source_check="Original device/inode/size/mtime/ctime plus saved measurement output digests. Video bytes were not reread.",
        extraction_configuration_sha256=config_digests,
        reuse_manifest_sha256={name: sha(run/name/"measurement_reuse.json") for name in ("luminance", "editing")},
        local_run=str(run), publishing_script_sha256=sha(Path(__file__)),
        published_files={str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()})
    write_json(output / "provenance.json", provenance)
    print(json.dumps(dict(output=str(output),files=len(provenance["published_files"]),video_count=len(source_versions)),ensure_ascii=False))


if __name__ == "__main__":
    main()
