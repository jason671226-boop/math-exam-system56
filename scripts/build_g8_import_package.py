"""Build a local-only G8 question ingestion CSV package.

This script never connects to Supabase.  Staging coverage is deliberately
reported as unavailable unless a separately authorised export is supplied.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "master_curriculum_v2_7" / "grade_packs" / "G8"
OUTPUT = ROOT / "data" / "question_ingestion" / "g8"
READY_BATCH = (
    ROOT / "data" / "question_ingestion" / "g8"
    / "our_g8_linear_model_batch_001.json"
)

QUESTION_FIELDS = (
    "question_key", "grade", "skill_id", "micro_skill_id", "skill_name",
    "micro_skill_name", "question_type", "difficulty", "question_text",
    "answer_text", "solution_text", "archetype_key", "item_pattern",
    "common_error", "source_key", "source_item_ref", "source_kind",
    "source_url", "rights_status", "content_hash", "quality_status", "is_active",
)


def _read_csv(name: str) -> list[dict[str, str]]:
    with (MASTER / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _content_hash(text: str) -> str:
    normalized = "".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _ready_rows(micro_map: dict[str, dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(READY_BATCH.read_text(encoding="utf-8"))
    source = payload["source"]
    rows = []
    for item in payload["questions"]:
        micro = micro_map[item["micro_skill_id"]]
        rows.append({
            "question_key": item["question_id"],
            "grade": 8,
            "skill_id": item["skill_id"],
            "micro_skill_id": item["micro_skill_id"],
            "skill_name": micro["skill_name"],
            "micro_skill_name": micro["focus"],
            "question_type": item["question_type"],
            "difficulty": item["difficulty"],
            "question_text": item["question_text"],
            "answer_text": item["answer"],
            "solution_text": item["solution"],
            "archetype_key": item["archetype_key"],
            "item_pattern": item["item_pattern"],
            "common_error": item["common_error"],
            "source_key": source["source_id"],
            "source_item_ref": item["source_item_ref"],
            "source_kind": item["source_kind"],
            "source_url": source["source_url"],
            "rights_status": item["rights_status"],
            "content_hash": item.get("content_hash") or _content_hash(item["question_text"]),
            "quality_status": item["quality_status"],
            "is_active": "true",
        })
    return rows, source


def _needs_review_rows(micro_map: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    micro = micro_map["G08-A-QUAD-FACT-01-P1"]
    source_url = "https://www.siyavula.com/downloads/books/maths/Gr9B_Mathematics_Learner_Eng.pdf"
    exercises = (
        ("1", "Determine the values of x: x^2 + 9x = -14.", "x = -7 or x = -2", "Rewrite as x^2+9x+14=0, factor to (x+7)(x+2)=0, then use the zero-product property."),
        ("2", "Determine the values of x: x^2 + 3x = 18.", "x = -6 or x = 3", "Rewrite as x^2+3x-18=0, factor to (x+6)(x-3)=0, then use the zero-product property."),
        ("3", "Determine the values of x: x^2 - 18x = -17.", "x = 1 or x = 17", "Rewrite as x^2-18x+17=0, factor to (x-1)(x-17)=0, then use the zero-product property."),
        ("4", "Determine the values of x: x^2 + 30 = 11x.", "x = 5 or x = 6", "Rewrite as x^2-11x+30=0, factor to (x-5)(x-6)=0, then use the zero-product property."),
        ("5", "Determine the values of x: x^2 = 13x + 30.", "x = -2 or x = 15", "Rewrite as x^2-13x-30=0, factor to (x+2)(x-15)=0, then use the zero-product property."),
        ("6", "Determine the values of x: x^2 + 7x = 30.", "x = -10 or x = 3", "Rewrite as x^2+7x-30=0, factor to (x+10)(x-3)=0, then use the zero-product property."),
    )
    rows = []
    for number, question, answer, solution in exercises:
        rows.append({
            "question_key": f"G8-SIY-QUAD-FACT-{int(number):03d}",
            "grade": 8,
            "skill_id": micro["parent_skill_id"],
            "micro_skill_id": micro["micro_skill_id"],
            "skill_name": micro["skill_name"],
            "micro_skill_name": micro["focus"],
            "question_type": micro["question_type"],
            "difficulty": micro["difficulty"],
            "question_text": question,
            "answer_text": answer,
            "solution_text": solution,
            "archetype_key": "QUADRATIC_FACTOR_ZERO_PRODUCT",
            "item_pattern": micro["item_pattern"],
            "common_error": micro["common_error"],
            "source_key": "SRC-SIYAVULA-G9B-2014",
            "source_item_ref": f"Grade 9 Term 3, section 3.3, exercise {number}",
            "source_kind": "OPEN_TEXTBOOK",
            "source_url": source_url,
            "rights_status": "NEEDS_RIGHTS_REVIEW_NONCOMMERCIAL",
            "content_hash": _content_hash(question),
            "quality_status": "NEEDS_REVIEW",
            "is_active": "false",
            "review_reason": "PDF copyright page states CC BY-NC; commercial reuse is not cleared.",
        })
    return rows


def build() -> dict[str, int]:
    skills = _read_csv("standard_skills.csv")
    micros = _read_csv("layer2_micro_skills.csv")
    skill_map = {row["skill_id"]: row for row in skills}
    micro_map = {row["micro_skill_id"]: row for row in micros}
    ready, ready_source = _ready_rows(micro_map)
    review = _needs_review_rows(micro_map)

    priority_ids = ["G08-F-MODEL-01-A1", "G08-A-QUAD-FACT-01-P1"]
    priority_ids.extend(
        row["micro_skill_id"] for row in sorted(micros, key=lambda row: row["micro_skill_id"])
        if row["micro_skill_id"] not in priority_ids
    )
    processed = set(priority_ids[:100])
    ready_count = {}
    review_count = {}
    for row in ready:
        ready_count[row["micro_skill_id"]] = ready_count.get(row["micro_skill_id"], 0) + 1
    for row in review:
        review_count[row["micro_skill_id"]] = review_count.get(row["micro_skill_id"], 0) + 1

    coverage_fields = (
        "priority_rank", "processed", "grade", "skill_id", "micro_skill_id",
        "main_unit", "subunit", "skill_name", "question_type", "item_pattern",
        "difficulty", "common_error", "staging_validated_count",
        "staging_count_status", "local_import_ready_count", "local_needs_review_count",
        "local_gap_to_five", "coverage_status", "priority_reason",
    )
    ranks = {micro_id: rank for rank, micro_id in enumerate(priority_ids[:100], 1)}
    coverage = []
    for micro in micros:
        local_ready = ready_count.get(micro["micro_skill_id"], 0)
        coverage.append({
            "priority_rank": ranks.get(micro["micro_skill_id"], ""),
            "processed": "true" if micro["micro_skill_id"] in processed else "false",
            "grade": 8,
            "skill_id": micro["parent_skill_id"],
            "micro_skill_id": micro["micro_skill_id"],
            "main_unit": micro["main_unit"],
            "subunit": micro["subunit"],
            "skill_name": micro["skill_name"],
            "question_type": micro["question_type"],
            "item_pattern": micro["item_pattern"],
            "difficulty": micro["difficulty"],
            "common_error": micro["common_error"],
            "staging_validated_count": "",
            "staging_count_status": "UNAVAILABLE_NO_STAGING_READ",
            "local_import_ready_count": local_ready,
            "local_needs_review_count": review_count.get(micro["micro_skill_id"], 0),
            "local_gap_to_five": max(0, 5 - local_ready),
            "coverage_status": "LOCAL_READY" if local_ready >= 5 else "LOCAL_GAP",
            "priority_reason": "SOURCE_ALIGNED_GAP" if micro["micro_skill_id"] in priority_ids[:2] else ("TOP_100_MASTER_GAP_REVIEW" if micro["micro_skill_id"] in processed else "NOT_IN_THIS_BATCH"),
        })

    source_fields = (
        "source_key", "source_name", "source_url", "source_type", "source_kind",
        "rights_status", "license", "retrieved_at", "attribution", "review_note",
    )
    sources = (
        {
            "source_key": ready_source["source_id"],
            "source_name": ready_source["source_name"],
            "source_url": ready_source["source_url"],
            "source_type": ready_source["source_type"],
            "source_kind": "OPEN_LICENSE",
            "rights_status": ready_source["rights_status"],
            "license": ready_source["license"],
            "retrieved_at": ready_source["retrieved_at"],
            "attribution": ready_source["attribution"],
            "review_note": "PDF pages and license footer visually verified.",
        },
        {
            "source_key": "SRC-SIYAVULA-G9B-2014",
            "source_name": "Siyavula Mathematics Grade 9 Book 2",
            "source_url": review[0]["source_url"],
            "source_type": "OPEN_EDUCATIONAL_RESOURCE",
            "source_kind": "OPEN_TEXTBOOK",
            "rights_status": "NEEDS_RIGHTS_REVIEW_NONCOMMERCIAL",
            "license": "CC BY-NC 4.0 (as stated inside PDF)",
            "retrieved_at": "2026-08-22",
            "attribution": "Ukuqonda Institute / Siyavula-linked textbook",
            "review_note": "Download page label conflicts with PDF; PDF copyright page governs. Excluded from import-ready.",
        },
    )
    candidate_fields = QUESTION_FIELDS + ("candidate_status", "review_reason")
    candidates = [dict(row, candidate_status="IMPORT_READY", review_reason="") for row in ready]
    candidates.extend(dict(row, candidate_status="NEEDS_REVIEW") for row in review)
    review_fields = QUESTION_FIELDS + ("review_reason",)

    _write_csv(OUTPUT / "g8_coverage_matrix.csv", coverage_fields, coverage)
    _write_csv(OUTPUT / "g8_question_candidates.csv", candidate_fields, candidates)
    _write_csv(OUTPUT / "g8_source_manifest.csv", source_fields, sources)
    _write_csv(OUTPUT / "g8_import_ready.csv", QUESTION_FIELDS, ready)
    _write_csv(OUTPUT / "g8_needs_review.csv", review_fields, review)
    return {
        "micro_skills": len(micros), "processed": len(processed),
        "ready": len(ready), "review": len(review), "sources": len(sources),
    }


if __name__ == "__main__":
    summary = build()
    print("G8 IMPORT PACKAGE:", " ".join(f"{key}={value}" for key, value in summary.items()))
