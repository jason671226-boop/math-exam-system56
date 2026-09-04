"""Build the Stage 5B-2D G8 coverage matrices from local-only artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "master_curriculum_v2_7" / "grade_packs" / "G8"
DEFAULT_SCOPE = ROOT / ".local" / "stage5_g8_mapping_pilot" / "scope200"
DEFAULT_OUTPUT = ROOT / ".local" / "stage5_g8_mapping_pilot" / "freeze"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def pilot_status(question_count: int, micro_covered: int, micro_count: int) -> str:
    if question_count == 0:
        return "ZERO_COVERAGE"
    # A pilot-covered skill needs more than a single accidental hit and some L2 breadth.
    if question_count >= 3 and micro_covered >= min(2, micro_count):
        return "PILOT_COVERED"
    return "LIMITED_COVERAGE"


def build(scope_dir: Path, output: Path) -> dict[str, Any]:
    skills = read_csv(MASTER / "standard_skills.csv")
    micros = read_csv(MASTER / "layer2_micro_skills.csv")
    results = read_jsonl(scope_dir / "g8_scope_mapping_results.jsonl")
    report = json.loads((scope_dir / "scope_validation_report.json").read_text(encoding="utf-8"))
    if len(skills) != 102 or len(micros) != 660 or len(results) != 200:
        raise RuntimeError(f"Input count mismatch: skills={len(skills)} micros={len(micros)} results={len(results)}")
    if report.get("production_reads") != 0 or report.get("production_writes") != 0:
        raise RuntimeError("Safety stop: source report does not prove zero production access")

    output.mkdir(parents=True, exist_ok=True)
    skill_counts = Counter(str(r.get("skill_id") or "") for r in results if r.get("scope_status") == "IN_SCOPE_G8")
    micro_counts = Counter(str(r.get("micro_skill_id") or "") for r in results if r.get("scope_status") == "IN_SCOPE_G8")
    micros_by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for micro in micros:
        micros_by_parent[micro["parent_skill_id"]].append(micro)

    skill_rows: list[dict[str, Any]] = []
    for order, skill in enumerate(skills, 1):
        sid = skill["skill_id"]
        children = micros_by_parent[sid]
        q_count = skill_counts[sid]
        micro_covered = sum(1 for m in children if micro_counts[m["micro_skill_id"]] > 0)
        status = pilot_status(q_count, micro_covered, len(children))
        priority = "HIGH" if q_count == 0 and order <= 60 else ("MEDIUM" if q_count == 0 else "LOW")
        action = {
            "ZERO_COVERAGE": "ADD_CROSS_UNIT_PILOT_ITEMS",
            "LIMITED_COVERAGE": "EXPAND_MICRO_SKILL_BREADTH",
            "PILOT_COVERED": "RETAIN_AND_MONITOR",
        }[status]
        skill_rows.append({
            "skill_id": sid,
            "skill_name": skill.get("skill_name", ""),
            "main_unit": skill.get("main_unit", ""),
            "micro_skill_count": len(children),
            "current_in_scope_question_count": q_count,
            "current_micro_covered_count": micro_covered,
            "skill_coverage_percent": 100.0 if q_count else 0.0,
            "micro_coverage_percent": round(100.0 * micro_covered / len(children), 2) if children else 0.0,
            "pilot_status": status,
            "recommended_next_action": action,
            "priority": priority,
        })

    micro_rows = []
    skill_by_id = {s["skill_id"]: s for s in skills}
    for micro in micros:
        count = micro_counts[micro["micro_skill_id"]]
        parent = skill_by_id[micro["parent_skill_id"]]
        micro_rows.append({
            "micro_skill_id": micro["micro_skill_id"],
            "parent_skill_id": micro["parent_skill_id"],
            "parent_skill_name": parent.get("skill_name", ""),
            "micro_skill_name": micro.get("skill_name", ""),
            "main_unit": micro.get("main_unit", ""),
            "current_in_scope_question_count": count,
            "covered": bool(count),
            "pilot_status": "PILOT_COVERED" if count >= 3 else ("LIMITED_COVERAGE" if count else "ZERO_COVERAGE"),
            "recommended_next_action": "RETAIN_AND_MONITOR" if count >= 3 else "ADD_TARGETED_PILOT_ITEMS",
            "priority": "LOW" if count else "HIGH",
        })

    covered_skills = sum(1 for row in skill_rows if row["current_in_scope_question_count"] > 0)
    covered_micros = sum(1 for row in micro_rows if row["covered"])
    top10 = sorted(skill_rows, key=lambda r: (-r["current_in_scope_question_count"], r["skill_id"]))[:10]
    high_zero = [r for r in skill_rows if r["priority"] == "HIGH" and r["pilot_status"] == "ZERO_COVERAGE"]
    summary = {
        "stage": "5B-2D",
        "total_skills": 102,
        "skills_zero_questions": 102 - covered_skills,
        "skills_with_questions": covered_skills,
        "total_micro_skills": 660,
        "micro_skills_zero_questions": 660 - covered_micros,
        "micro_skills_covered": covered_micros,
        "skill_coverage_percent": round(100.0 * covered_skills / 102, 2),
        "micro_coverage_percent": round(100.0 * covered_micros / 660, 2),
        "top_10_skills_by_question_count": [{k: r[k] for k in ("skill_id", "skill_name", "current_in_scope_question_count")} for r in top10],
        "high_priority_zero_coverage_skills": [{k: r[k] for k in ("skill_id", "skill_name", "main_unit", "recommended_next_action")} for r in high_zero],
        "production_reads": 0,
        "production_writes": 0,
        "contains_question_text": False,
    }
    skill_fields = list(skill_rows[0])
    micro_fields = list(micro_rows[0])
    write_csv(output / "g8_skill_coverage_matrix.csv", skill_rows, skill_fields)
    write_json(output / "g8_skill_coverage_matrix.json", skill_rows)
    write_csv(output / "g8_micro_coverage_matrix.csv", micro_rows, micro_fields)
    write_json(output / "g8_coverage_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope-dir", type=Path, default=DEFAULT_SCOPE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.scope_dir, args.output), ensure_ascii=False))
    except Exception as exc:
        print(f"G8 COVERAGE MATRIX: BLOCKED ({type(exc).__name__}): {exc}")
        return 2
    print("G8 COVERAGE MATRIX: PASS (local only; no question text)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
