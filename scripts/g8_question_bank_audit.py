"""Audit the existing G8 Staging question bank against Master Curriculum v2.7.

The report contains metadata and aggregate counts only.  It never logs
credentials, endpoints, question text, answers, or solutions.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.staging_smoke import SmokeFailure, _load_config


MASTER = ROOT / "data" / "master_curriculum_v2_7" / "grade_packs" / "G8"
DEFAULT_JSON = ROOT / "app" / "data" / "g8_question_bank_coverage.json"
VALID_STATUSES = {"VALIDATED", "APPROVED", "PRODUCTION_READY", "READY"}


def _csv_rows(name: str) -> list[dict[str, str]]:
    with (MASTER / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _fetch_g8_rows(page_size: int = 1000) -> list[dict[str, Any]]:
    from supabase import create_client

    url, key = _load_config()
    client = create_client(url, key)
    columns = (
        "id,skill_id,micro_skill_id,question_type,item_pattern,difficulty,"
        "quality_status,rights_status,is_active,source_id,source_kind,"
        "content_hash,archetype_key"
    )
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        response = (
            client.table("question_bank")
            .select(columns)
            .eq("grade", 8)
            .range(start, start + page_size - 1)
            .execute()
        )
        page = response.data if isinstance(response.data, list) else []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size


def _is_validated(row: dict[str, Any]) -> bool:
    return (
        row.get("is_active") is True
        and str(row.get("quality_status") or "").upper() in VALID_STATUSES
        and str(row.get("rights_status") or "").upper() not in
        {"NEEDS_RIGHTS_REVIEW", "REJECTED", "UNKNOWN", ""}
    )


def _bucket(count: int) -> str:
    if count == 0:
        return "ZERO"
    if count < 5:
        return "LOW"
    if count < 10:
        return "READY"
    return "STRONG"


def build_report(bank_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    skills = _csv_rows("standard_skills.csv")
    micros = _csv_rows("layer2_micro_skills.csv")
    bank = list(bank_rows)
    by_micro: dict[str, list[dict[str, Any]]] = {}
    for row in bank:
        by_micro.setdefault(str(row.get("micro_skill_id") or ""), []).append(row)

    coverage = []
    for micro in micros:
        rows = by_micro.get(micro["micro_skill_id"], [])
        valid = [row for row in rows if _is_validated(row)]
        source_ids = {str(row.get("source_id")) for row in valid if row.get("source_id")}
        structures = {
            str(row.get("archetype_key") or row.get("content_hash"))
            for row in valid
            if row.get("archetype_key") or row.get("content_hash")
        }
        count = len(valid)
        coverage.append({
            "skill_id": micro["parent_skill_id"],
            "micro_skill_id": micro["micro_skill_id"],
            "main_unit": micro["main_unit"],
            "subunit": micro["subunit"],
            "question_type": micro["question_type"],
            "item_pattern": micro["item_pattern"],
            "difficulty": micro["difficulty"],
            "common_error": micro["common_error"],
            "validated_question_count": count,
            "source_count": len(source_ids),
            "unique_structure_count": len(structures),
            "coverage_status": _bucket(count),
            "gap_to_five": max(0, 5 - count),
        })

    status_counts = Counter(item["coverage_status"] for item in coverage)
    largest_gaps = sorted(
        coverage,
        key=lambda item: (
            -item["gap_to_five"], item["validated_question_count"],
            item["skill_id"], item["micro_skill_id"],
        ),
    )[:20]
    validated = [row for row in bank if _is_validated(row)]
    needs_review = [row for row in bank if not _is_validated(row)]
    source_kinds = Counter(str(row.get("source_kind") or "UNKNOWN") for row in validated)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grade": 8,
        "master_curriculum": "master_curriculum_v2_7/grade_packs/G8",
        "total_standard_skills": len(skills),
        "total_micro_skills": len(micros),
        "total_staging_questions": len(bank),
        "validated_questions": len(validated),
        "needs_review": len(needs_review),
        "total_sources_from_visible_questions": len({
            str(row.get("source_id")) for row in bank if row.get("source_id")
        }),
        "source_kind_counts": dict(sorted(source_kinds.items())),
        "coverage_status_counts": {
            name: status_counts.get(name, 0)
            for name in ("ZERO", "LOW", "READY", "STRONG")
        },
        "largest_20_gaps": largest_gaps,
        "coverage": coverage,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()
    try:
        report = build_report(_fetch_g8_rows())
    except (ImportError, SmokeFailure, OSError) as exc:
        print(f"G8 COVERAGE AUDIT: BLOCKED ({type(exc).__name__})")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts = report["coverage_status_counts"]
    print(
        "G8 COVERAGE AUDIT: PASS "
        f"questions={report['total_staging_questions']} "
        f"validated={report['validated_questions']} "
        f"ZERO={counts['ZERO']} LOW={counts['LOW']} "
        f"READY={counts['READY']} STRONG={counts['STRONG']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
