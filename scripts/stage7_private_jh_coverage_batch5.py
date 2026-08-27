"""Ingest PRIVATE_JH coverage batch 5 and add core-structure guidance."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.math_extraction_quality import assess_missing_required_image
from services.stage7_private_jh_guidance import core_structure_guidance
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES, load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST, GT, CLEANING, PILOT, _csv, _jsonl, _write_csv
from scripts.stage7_private_jh_coverage_batch4 import TEACHER_V5

TEACHER_V6 = PILOT / "PRIVATE_JH_TEACHER_COVERAGE_SET_V6.csv"
STATUS = PILOT / "coverage_review_batch5_status.json"
BATCH: dict[int, dict[str, Any]] = {
    1: {"scope": "PRIVATE_JH", "skill": "G05-R-LAW-01", "micro": "G05-R-LAW-01-T1",
        "secondary": [], "assessment": "PRIVATE_JH_ADVANCED", "reason": None,
        "status": "HUMAN_VALIDATED", "note": "共同因數與乘法分配律簡化。"},
    2: {"scope": "PRIVATE_JH", "skill": "G05-R-MULTISTEP-01", "micro": "G05-R-MULTISTEP-01-A1",
        "secondary": [], "assessment": "MULTI_STEP", "reason": None,
        "status": "HUMAN_VALIDATED", "note": "多段文字情境計算並合成總量。"},
    3: {"scope": "PRIVATE_JH", "skill": "G06-R-COUNT-01", "micro": "G06-R-COUNT-01-P1",
        "secondary": [], "assessment": "PRIVATE_JH_ADVANCED", "reason": None,
        "status": "HUMAN_VALIDATED", "note": "系統列舉搭配並去除重複結果。"},
    4: {"scope": "SOURCE_INVALID_PENDING_REEXTRACTION", "skill": None, "micro": None,
        "secondary": [], "assessment": None, "reason": "MISSING_REQUIRED_DIAGRAM",
        "status": "NEEDS_IMAGE_REEXTRACTION", "note": "塗色面積所需圖形未保存。"},
    5: {"scope": "SOURCE_INVALID_PENDING_REEXTRACTION", "skill": None, "micro": None,
        "secondary": [], "assessment": None, "reason": "MISSING_REQUIRED_DIAGRAM",
        "status": "NEEDS_IMAGE_REEXTRACTION", "note": "立體排列圖未保存。"},
    6: {"scope": "PRIVATE_JH", "skill": "G06-N-SPEED-APP-01", "micro": "G06-N-SPEED-APP-01-T1",
        "secondary": [], "assessment": "MULTI_STEP", "reason": None,
        "status": "HUMAN_VALIDATED", "note": "去回程平均速率使用總距離除以總時間。"},
}


def _columns(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    fields = list(rows[0])
    if len(fields) < 4:
        raise RuntimeError("COVERAGE_SCHEMA_INVALID")
    return fields[0], fields[1], fields[3]


def _locate() -> dict[int, dict[str, Any]]:
    rows = _csv(TEACHER_V5)
    number_col, _, question_col = _columns(rows)
    numbered = {int(row[number_col]): row for row in rows}
    questions = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))["questions"]
    by_text: dict[str, list[dict[str, Any]]] = {}
    for question in questions:
        by_text.setdefault(question["question_text"], []).append(question)
    located: dict[int, dict[str, Any]] = {}
    seen: set[str] = set()
    for number in BATCH:
        if number not in numbered:
            raise RuntimeError("COVERAGE_SET_NUMBER_MISSING")
        row = numbered[number]
        matches = by_text.get(row[question_col], [])
        if len(matches) != 1:
            raise RuntimeError("COVERAGE_QUESTION_NOT_UNIQUE")
        question = matches[0]
        fingerprint = question["fingerprint"]
        if fingerprint in seen or question["question_text"] != row[question_col]:
            raise RuntimeError("COVERAGE_LOCATOR_MISMATCH")
        seen.add(fingerprint)
        located[number] = {"coverage": row, "question": question, "fingerprint": fingerprint}
    return located


def _validate_ids() -> None:
    skills, micros = load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES)
    for number, spec in BATCH.items():
        if spec["skill"] is None:
            continue
        if spec["skill"] not in skills:
            raise RuntimeError(f"UNKNOWN_SKILL:{number}")
        micro = micros.get(spec["micro"])
        if micro is None:
            raise RuntimeError(f"UNKNOWN_MICRO:{number}")
        if micro.get("parent_skill_id") != spec["skill"]:
            raise RuntimeError(f"MICRO_PARENT_MISMATCH:{number}")


def _verify_diagram_evidence(located: dict[int, dict[str, Any]]) -> None:
    for number in (4, 5):
        question = located[number]["question"]
        gate = assess_missing_required_image(question["question_text"], extracted_record={
            **question, "diagram_dependency_verified": True})
        if gate.status != "SOURCE_IMAGE_REQUIRED":
            raise RuntimeError(f"MISSING_DIAGRAM_EVIDENCE_NOT_REPRODUCED:{number}")


def _verify_guidance() -> None:
    cases = (
        ({"common_factor_structure": True, "decimal_surface": True}, "G05-R-LAW-01"),
        ({"segmented_quantities": True, "asks_total": True, "daily_word": True,
          "distance_time_relation": False}, "G05-R-MULTISTEP-01"),
        ({"distinct_combinations": True, "deduplicate_results": True}, "G06-R-COUNT-01"),
        ({"round_trip": True, "average_speed": True}, "G06-N-SPEED-APP-01"),
    )
    for evidence, expected in cases:
        result = core_structure_guidance({"profile_type": "PRIVATE_JH", **evidence})
        if not result or result["foundation_skill_id"] != expected or result["human_validated"]:
            raise RuntimeError("CORE_GUIDANCE_INVALID")


def ingest(*, force: bool = False) -> dict[str, Any]:
    successor = PILOT / "PRIVATE_JH_TEACHER_COVERAGE_SET_V7.csv"
    if (not force or successor.is_file()) and TEACHER_V6.is_file() and STATUS.is_file():
        status = json.loads(STATUS.read_text(encoding="utf-8-sig"))
        if CLEANING.is_file():
            status["source_quality"]["source_cleaning_queue_total"] = len(
                json.loads(CLEANING.read_text(encoding="utf-8-sig")).get("items", []))
        return status
    if not all(path.is_file() for path in (TEACHER_V5, MANIFEST, GT, CLEANING)):
        raise RuntimeError("MISSING_COVERAGE_BATCH5_INPUT")
    located = _locate()
    _validate_ids()
    _verify_diagram_evidence(located)
    _verify_guidance()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    by_text = {q["question_text"]: q for q in manifest["questions"]}
    gt = {row["fingerprint"]: row for row in _jsonl(GT)}
    now = datetime.now(timezone.utc).isoformat()
    for number, spec in BATCH.items():
        locator, fp = located[number], located[number]["fingerprint"]
        old = gt.get(fp, {})
        gt[fp] = {"fingerprint": fp, "coverage_set_version": "V5", "coverage_set_number": number,
            "source_review_number": int(locator["coverage"][list(locator["coverage"])[1]]),
            "human_scope": spec["scope"], "human_primary_skill_id": spec["skill"],
            "human_primary_micro_id": spec["micro"], "human_secondary_skill_ids": spec["secondary"],
            "human_assessment_style": spec["assessment"], "human_note": spec["note"],
            "validation_source": "TEACHER_APPROVED", "validated_at": old.get("validated_at") or now,
            "source_status": "HUMAN_VALIDATED" if spec["skill"] else "SOURCE_INVALID_PENDING_REEXTRACTION"}
    GT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sorted(gt.values(),
        key=lambda x: (int(x.get("source_review_number") or 0), x["fingerprint"]))), encoding="utf-8")

    cleaning = json.loads(CLEANING.read_text(encoding="utf-8-sig"))
    items = {item["fingerprint"]: item for item in cleaning.get("items", [])}
    for number in (4, 5):
        locator, spec = located[number], BATCH[number]
        question = locator["question"]
        items[locator["fingerprint"]] = {"fingerprint": locator["fingerprint"],
            "coverage_set_version": "V5", "coverage_set_number": number,
            "source_school": question.get("source_school"), "source_year": question.get("source_year"),
            "source_document": question.get("source_url"), "question_number": question.get("question_number"),
            "page_number": None, "reason": spec["reason"], "status": spec["status"],
            "replacement_status": "PENDING", "detection_source": "TEACHER_APPROVED_SOURCE_QUALITY"}

    rows = _csv(TEACHER_V5)
    number_col, _, question_col = _columns(rows)
    processed = {entry["fingerprint"] for entry in located.values()}
    existing_cleaning = set(items)
    new_diagrams: list[str] = []
    for row in rows:
        question = by_text.get(row[question_col])
        if not question or question["fingerprint"] in processed or question["fingerprint"] in existing_cleaning:
            continue
        gate = assess_missing_required_image(question["question_text"], extracted_record=question)
        if gate.status == "SOURCE_IMAGE_REQUIRED":
            fp = question["fingerprint"]
            new_diagrams.append(fp)
            items[fp] = {"fingerprint": fp, "source_school": question.get("source_school"),
                "source_year": question.get("source_year"), "source_document": question.get("source_url"),
                "question_number": question.get("question_number"), "page_number": None,
                "reason": "MISSING_REQUIRED_DIAGRAM", "status": "NEEDS_IMAGE_REEXTRACTION",
                "replacement_status": "PENDING", "detection_source": "DETERMINISTIC_MISSING_IMAGE_GATE"}
    CLEANING.write_text(json.dumps({"items": list(items.values())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    remove = processed | set(new_diagrams)
    remaining = [row.copy() for row in rows if by_text[row[question_col]]["fingerprint"] not in remove]
    for index, row in enumerate(remaining, 1):
        row[number_col] = index
    _write_csv(TEACHER_V6, remaining, list(rows[0]))
    validated = [row for row in gt.values() if row.get("source_status") == "HUMAN_VALIDATED"]
    status = {"teacher_batch": {"reviewed": 6, "human_validated": 4, "image_reextraction": 2,
            "id_validation_failures": 0, "parent_failures": 0},
        "disambiguation": {"common_factor_rule": "READY", "multi_step_vs_speed_rule": "READY",
            "counting_rule": "READY", "average_speed_rule": "READY"},
        "source_quality": {"missing_diagram_gate": "READY", "new_missing_diagram_risks": len(new_diagrams),
            "source_cleaning_queue_total": len(items)},
        "human_coverage": {"direct_human_gt": len(validated),
            "unique_validated_skills": len({r["human_primary_skill_id"] for r in validated}),
            "unique_validated_micros": len({r["human_primary_micro_id"] for r in validated})},
        "teacher_review": {"previous_questions": len(rows), "removed_by_human_gt": 4,
            "removed_for_source_cleaning": 2, "additional_quality_gate_removals": len(new_diagrams),
            "remaining_questions": len(remaining)}, "api_calls": 0, "production_reads": 0,
        "production_writes": 0}
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    print(json.dumps(ingest(), ensure_ascii=False))
