"""Ingest PRIVATE_JH coverage batch 3 and apply deterministic source gates."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.math_extraction_quality import (
    assess_expression_completeness,
    assess_missing_required_chart,
    assess_multi_document_contamination,
)
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES, load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST, GT, CLEANING, PILOT, _csv, _jsonl, _write_csv
from scripts.stage7_private_jh_coverage_batch2 import TEACHER_V3

TEACHER_V4 = PILOT / "PRIVATE_JH_TEACHER_COVERAGE_SET_V4.csv"
STATUS = PILOT / "coverage_review_batch3_status.json"

BATCH: dict[int, dict[str, Any]] = {
    8: {"scope": "SOURCE_INVALID_PENDING_REEXTRACTION", "skill": None, "micro": None,
        "secondary": [], "assessment": None, "reason": "MULTI_DOCUMENT_CONTAMINATION",
        "status": "NEEDS_REEXTRACTION", "note": "多文件／多題串接污染；不得建立 Skill GT。"},
    9: {"scope": "PRIVATE_JH", "skill": "G05-N-FACTOR-01", "micro": "G05-N-FACTOR-01-C1",
        "secondary": [], "assessment": "HIGH_DIFFICULTY", "reason": None,
        "status": "HUMAN_VALIDATED", "note": "整除關係、因數關係與條件篩選。"},
    10: {"scope": "SOURCE_INVALID_PENDING_REEXTRACTION", "skill": None, "micro": None,
         "secondary": [], "assessment": None, "reason": "MATH_EXPRESSION_INCOMPLETE",
         "status": "NEEDS_REEXTRACTION", "note": "核心運算式缺失；等待完整題幹。"},
    11: {"scope": "SOURCE_INVALID_PENDING_REEXTRACTION", "skill": None, "micro": None,
         "secondary": [], "assessment": None, "reason": "MISSING_REQUIRED_CHART",
         "status": "NEEDS_IMAGE_REEXTRACTION", "note": "折線圖點位與月份對應未保存。"},
}


def _columns(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    fields = list(rows[0])
    if len(fields) < 4:
        raise RuntimeError("COVERAGE_SCHEMA_INVALID")
    return fields[0], fields[1], fields[3]


def _locate() -> dict[int, dict[str, Any]]:
    rows = _csv(TEACHER_V3)
    number_col, _, question_col = _columns(rows)
    numbered = {int(row[number_col]): row for row in rows}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    by_text: dict[str, list[dict[str, Any]]] = {}
    for question in manifest["questions"]:
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
    spec = BATCH[9]
    if spec["skill"] not in skills:
        raise RuntimeError("UNKNOWN_SKILL:9")
    micro = micros.get(spec["micro"])
    if micro is None:
        raise RuntimeError("UNKNOWN_MICRO:9")
    if micro.get("parent_skill_id") != spec["skill"]:
        raise RuntimeError("MICRO_PARENT_MISMATCH:9")
    # C1 is the catalog's concept/relationship-recognition child; no ID is invented.
    searchable = " ".join(str(micro.get(k, "")) for k in ("skill_name", "focus", "question_type"))
    if not searchable.strip():
        raise RuntimeError("MICRO_SEMANTICS_UNAVAILABLE:9")


def _metadata(question: dict[str, Any], **extra: Any) -> dict[str, Any]:
    result = {"source_document": question.get("source_url"),
              "question_number": question.get("question_number")}
    result.update(extra)
    return result


def _verify_teacher_quality_evidence(located: dict[int, dict[str, Any]]) -> None:
    q8 = located[8]["question"]
    contamination = assess_multi_document_contamination(
        q8["question_text"], source_metadata=_metadata(q8, multiple_exam_headers=True,
                                                        pdf_text_discrepancy=True))
    if contamination.status != "SOURCE_NEEDS_REEXTRACTION":
        raise RuntimeError("CONTAMINATION_EVIDENCE_NOT_REPRODUCED")
    q10 = located[10]["question"]
    expression = assess_expression_completeness(
        q10["question_text"], source_metadata=_metadata(q10, expression_expected=True,
                                                         expression_incomplete_verified=True),
        pdf_text_discrepancy=True)
    if expression.status != "SOURCE_NEEDS_REEXTRACTION":
        raise RuntimeError("EXPRESSION_LOSS_EVIDENCE_NOT_REPRODUCED")
    q11 = located[11]["question"]
    chart = assess_missing_required_chart(q11["question_text"], extracted_record={
        **q11, "chart_expected": True, "chart_dependency_verified": True})
    if chart.status != "SOURCE_IMAGE_REQUIRED":
        raise RuntimeError("MISSING_CHART_EVIDENCE_NOT_REPRODUCED")


def ingest(*, force: bool = False) -> dict[str, Any]:
    if not force and TEACHER_V4.is_file() and STATUS.is_file():
        return json.loads(STATUS.read_text(encoding="utf-8-sig"))
    if not all(path.is_file() for path in (TEACHER_V3, MANIFEST, GT, CLEANING)):
        raise RuntimeError("MISSING_COVERAGE_BATCH3_INPUT")
    located = _locate()
    _validate_ids()
    _verify_teacher_quality_evidence(located)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    manifest_by_fp = {q["fingerprint"]: q for q in manifest["questions"]}
    gt = {row["fingerprint"]: row for row in _jsonl(GT)}
    now = datetime.now(timezone.utc).isoformat()
    for number, spec in BATCH.items():
        fp = located[number]["fingerprint"]
        old = gt.get(fp, {})
        gt[fp] = {
            "fingerprint": fp, "coverage_set_version": "V3", "coverage_set_number": number,
            "source_review_number": int(located[number]["coverage"][list(located[number]["coverage"])[1]]),
            "human_scope": spec["scope"], "human_primary_skill_id": spec["skill"],
            "human_primary_micro_id": spec["micro"], "human_secondary_skill_ids": spec["secondary"],
            "human_assessment_style": spec["assessment"], "human_note": spec["note"],
            "validation_source": "TEACHER_APPROVED", "validated_at": old.get("validated_at") or now,
            "source_status": "HUMAN_VALIDATED" if spec["skill"] else "SOURCE_INVALID_PENDING_REEXTRACTION",
        }
    GT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sorted(
        gt.values(), key=lambda x: (int(x.get("source_review_number") or 0), x["fingerprint"]))), encoding="utf-8")

    cleaning_doc = json.loads(CLEANING.read_text(encoding="utf-8-sig"))
    items = {item["fingerprint"]: item for item in cleaning_doc.get("items", [])}
    for number in (8, 10, 11):
        locator = located[number]
        question, spec = locator["question"], BATCH[number]
        items[locator["fingerprint"]] = {
            "fingerprint": locator["fingerprint"], "coverage_set_version": "V3",
            "coverage_set_number": number, "source_school": question.get("source_school"),
            "source_year": question.get("source_year"), "source_document": question.get("source_url"),
            "question_number": question.get("question_number"), "page_number": 2 if number == 11 else None,
            "reason": spec["reason"], "status": spec["status"], "replacement_status": "PENDING",
            "detection_source": "TEACHER_APPROVED_SOURCE_QUALITY",
        }

    processed = {entry["fingerprint"] for entry in located.values()}
    existing_cleaning = set(items)
    rows = _csv(TEACHER_V3)
    number_col, _, question_col = _columns(rows)
    by_text = {q["question_text"]: q for q in manifest["questions"]}
    new_contamination: list[str] = []
    new_expression: list[str] = []
    new_chart: list[str] = []
    for row in rows:
        question = by_text.get(row[question_col])
        if not question or question["fingerprint"] in processed or question["fingerprint"] in existing_cleaning:
            continue
        fp = question["fingerprint"]
        contamination = assess_multi_document_contamination(question["question_text"],
            source_metadata=_metadata(question))
        expression = assess_expression_completeness(question["question_text"],
            source_metadata=_metadata(question), pdf_text_discrepancy=False)
        chart = assess_missing_required_chart(question["question_text"], extracted_record=question)
        reason = status = None
        if contamination.status != "PASS":
            new_contamination.append(fp); reason = "MULTI_DOCUMENT_CONTAMINATION"; status = "NEEDS_REEXTRACTION"
        elif expression.status != "PASS":
            new_expression.append(fp); reason = "MATH_EXPRESSION_INCOMPLETE"; status = "NEEDS_REEXTRACTION"
        elif chart.status != "PASS":
            new_chart.append(fp); reason = "MISSING_REQUIRED_CHART"; status = "NEEDS_IMAGE_REEXTRACTION"
        if reason:
            items[fp] = {"fingerprint": fp, "source_school": question.get("source_school"),
                "source_year": question.get("source_year"), "source_document": question.get("source_url"),
                "question_number": question.get("question_number"), "page_number": None,
                "reason": reason, "status": status, "replacement_status": "PENDING",
                "detection_source": "DETERMINISTIC_SOURCE_QUALITY_GATE"}
    CLEANING.write_text(json.dumps({"items": list(items.values())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    additional = set(new_contamination + new_expression + new_chart)
    removed = processed | additional
    remaining = [row.copy() for row in rows if by_text[row[question_col]]["fingerprint"] not in removed]
    for index, row in enumerate(remaining, 1):
        row[number_col] = index
    _write_csv(TEACHER_V4, remaining, list(rows[0]))
    validated = [row for row in gt.values() if row.get("source_status") == "HUMAN_VALIDATED"]
    status_doc = {
        "teacher_batch": {"reviewed": 4, "human_validated": 1, "source_reextraction": 2,
            "image_chart_reextraction": 1, "id_validation_failures": 0, "parent_failures": 0},
        "source_quality": {"multi_document_gate": "READY", "expression_completeness_gate": "READY",
            "missing_chart_gate": "READY", "new_contamination_risks": len(new_contamination),
            "new_expression_risks": len(new_expression), "new_chart_risks": len(new_chart),
            "source_cleaning_queue_total": len(items)},
        "human_coverage": {"direct_human_gt": len(validated),
            "unique_validated_skills": len({r["human_primary_skill_id"] for r in validated}),
            "unique_validated_micros": len({r["human_primary_micro_id"] for r in validated})},
        "teacher_review": {"previous_questions": len(rows), "removed_by_human_gt": 1,
            "removed_for_source_cleaning": 3, "additional_quality_gate_removals": len(additional),
            "remaining_questions": len(remaining)},
        "api_calls": 0, "production_reads": 0, "production_writes": 0,
    }
    STATUS.write_text(json.dumps(status_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status_doc


if __name__ == "__main__":
    print(json.dumps(ingest(), ensure_ascii=False))
