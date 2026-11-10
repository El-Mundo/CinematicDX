"""Post-result file-edge sensitivity, from frozen cut candidates only.

Motivation: assistant contact-sheet review found an end-card candidate. This
is a post-hoc challenge, not a replacement for the complete-file analysis.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    out = args.run / "edge_challenge"
    out.mkdir(exist_ok=False)
    source = args.run / "analysis/film_measurements_and_coverage.csv"
    plan_path = args.run / "plan.json"
    completion_path = args.run / "effective_extraction_complete.json"
    plan = json.loads(plan_path.read_text())
    complete = json.loads(completion_path.read_text())["complete"]
    jobs = {job["job_id"]: job for job in plan["jobs"]}
    if len(jobs) != len(plan["jobs"]) or len({job["film_key"] for job in plan["jobs"]}) != len(jobs):
        raise ValueError("Expected unique job and film identifiers in the current plan.")
    if len(complete) != len(set(complete)) or not set(complete).issubset(jobs):
        raise ValueError("Completion identifiers must be unique members of the current plan.")
    inputs = {str(path): sha(path) for path in (source, plan_path, completion_path)}
    films, groups = [], {}
    with source.open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    for record in records:
        if not record["job_id"]:
            continue
        job = jobs[record["job_id"]]
        if record["film_key"] != job["film_key"] or record["video_version_id"] != job["video_version_id"]:
            raise ValueError("Measured row differs from the current job identity or video version.")
        path = args.run / "films" / record["job_id"] / "cut_candidates.json"
        inputs[str(path)] = sha(path)
        points = json.loads(path.read_text())["primary"]["playback_seconds"]
        start = float(record["observed_coverage_start_playback_seconds"])
        end = float(record["observed_coverage_end_playback_seconds"])
        span = end - start
        assert span > 0
        full_rate = len(points) * 60 / span
        assert abs(full_rate - float(record["primary_cut_candidates_per_minute"])) < 1e-9
        left, right = start + 0.1 * span, start + 0.9 * span
        count = sum(left <= point < right for point in points)
        rate = count * 60 / (right - left)
        row = {"film_key": record["film_key"], "video_version_id": record["video_version_id"],
               "job_id": record["job_id"], "full_rate": full_rate,
               "central_start_seconds": left, "central_end_seconds": right,
               "central_candidates": count, "central_rate": rate}
        films.append(row)
        for studio in json.loads(record["studios"]):
            name = studio["chn"] or studio["name"]
            groups.setdefault(name, []).append((float(studio["fractional_weight"]), row))
    if len(films) != len(complete) or {film["job_id"] for film in films} != set(complete):
        raise ValueError("Edge analysis must cover every completed job exactly once.")
    studios = []
    for name, members in groups.items():
        weight = sum(w for w, _ in members)
        full = sum(w * r["full_rate"] for w, r in members) / weight
        central = sum(w * r["central_rate"] for w, r in members) / weight
        studios.append({"studio": name, "member_n": len(members), "fractional_n": weight,
                        "full_mean": full, "central_mean": central,
                        "central_minus_full": central - full})
    studios.sort(key=lambda r: r["central_mean"], reverse=True)
    for name, rows in [("films.csv", films), ("studios.csv", studios)]:
        with (out / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    receipt = {"status": "PROVISIONAL post-hoc file-edge sensitivity",
               "completed_at_utc": datetime.now(timezone.utc).isoformat(),
               "reason": "Full-file profile and assistant review include ending/title material.",
               "definition": "Primary candidates within [10%,90%) of actual decoded coverage; same film weights.",
               "limitations": "Arbitrary file-relative trim is not verified narrative/credit segmentation. Main results remain unchanged.",
               "film_n": len(films), "script_sha256": sha(Path(__file__)), "inputs": inputs,
               "outputs": {name: sha(out / name) for name in ["films.csv", "studios.csv"]}}
    (out / "run.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([r for r in studios if r["member_n"] >= 10], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
