"""Ingest PRIVATE_JH coverage batch 4 and harden contextual fraction checks."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.math_extraction_quality import assess_fraction_structure_loss, assess_multi_document_contamination
from services.stage7_private_jh_guidance import divisibility_extension_guidance
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES, load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST, GT, CLEANING, PILOT, _csv, _jsonl, _write_csv
from scripts.stage7_private_jh_coverage_batch3 import TEACHER_V4

TEACHER_V5 = PILOT / "PRIVATE_JH_TEACHER_COVERAGE_SET_V5.csv"
STATUS = PILOT / "coverage_review_batch4_status.json"
BATCH: dict[int, dict[str, Any]] = {
    7: {"scope": "SOURCE_INVALID_PENDING_REEXTRACTION", "skill": None, "micro": None,
        "secondary": [], "assessment": None, "reason": "MATH_FRACTION_NOTATION_LOST",
        "status": "NEEDS_REEXTRACTION", "note": "比例語境中的分數結構遺失；不得猜回原值。"},
    8: {"scope": "SOURCE_INVALID_PENDING_REEXTRACTION", "skill": None, "micro": None,
        "secondary": [], "assessment": None, "reason": "MULTI_DOCUMENT_CONTAMINATION",
        "status": "NEEDS_REEXTRACTION", "note": "跨題／跨文件串接污染。"},
    9: {"scope": "PRIVATE_JH", "skill": "G04-N-DEC2-ADD-01", "micro": "G04-N-DEC2-ADD-01-R1",
        "secondary": [], "assessment": "REVERSE_REASONING", "reason": None,
        "status": "HUMAN_VALIDATED", "note": "小數加法並依結果條件反推未知加數。"},
    10: {"scope": "PRIVATE_JH", "skill": "G05-N-MULTIPLE-01", "micro": "G05-N-MULTIPLE-01-R1",
         "secondary": ["G06-R-COUNT-01"], "assessment": "PRIVATE_JH_ADVANCED", "reason": None,
         "status": "HUMAN_VALIDATED", "note": "倍數／整除條件篩選；系統列舉為 supporting skill。"},
}


def _columns(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    fields = list(rows[0])
    if len(fields) < 4:
        raise RuntimeError("COVERAGE_SCHEMA_INVALID")
    return fields[0], fields[1], fields[3]


def _locate() -> dict[int, dict[str, Any]]:
    rows = _csv(TEACHER_V4)
    number_col, _, question_col = _columns(rows)
    numbered = {int(row[number_col]): row for row in rows}
    questions = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))["questions"]
    by_text: dict[str, list[dict[str, Any]]] = {}
    for question in questions:
        by_text.setdefault(question["question_text"], []).append(question)
    resolved: dict[int, dict[str, Any]] = {}
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
        resolved[number] = {"coverage": row, "question": question, "fingerprint": fingerprint}
    return resolved


def _validate_ids() -> None:
    skills, micros = load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES)
    for number in (9, 10):
        spec = BATCH[number]
        if spec["skill"] not in skills:
            raise RuntimeError(f"UNKNOWN_SKILL:{number}")
        micro = micros.get(spec["micro"])
        if micro is None:
            raise RuntimeError(f"UNKNOWN_MICRO:{number}")
        if micro.get("parent_skill_id") != spec["skill"]:
            raise RuntimeError(f"MICRO_PARENT_MISMATCH:{number}")
        if any(skill not in skills for skill in spec["secondary"]):
            raise RuntimeError(f"UNKNOWN_SECONDARY:{number}")
    guidance = divisibility_extension_guidance({"profile_type": "PRIVATE_JH",
        "divisibility_condition": True, "systematic_enumeration": True})
    if not guidance or guidance["foundation_skill_id"] != BATCH[10]["skill"]:
        raise RuntimeError("DIVISIBILITY_GUIDANCE_INVALID")


def _metadata(question: dict[str, Any], **extra: Any) -> dict[str, Any]:
    data = {"source_document": question.get("source_url"), "question_number": question.get("question_number")}
    data.update(extra)
    return data


def _verify_source_evidence(located: dict[int, dict[str, Any]]) -> None:
    fraction_question = located[7]["question"]
    fraction = assess_fraction_structure_loss(fraction_question["question_text"], source_metadata=_metadata(
        fraction_question, fraction_expected=True, ratio_context=True,
        literal_interpretation_implausible=True, concatenated_fraction_options=True),
        pdf_text_discrepancy=True)
    if fraction.status != "SOURCE_NEEDS_REEXTRACTION":
        raise RuntimeError("FRACTION_LOSS_EVIDENCE_NOT_REPRODUCED")
    contaminated = located[8]["question"]
    contamination = assess_multi_document_contamination(contaminated["question_text"],
        source_metadata=_metadata(contaminated, multiple_exam_headers=True, pdf_text_discrepancy=True,
                                  answer_table_detected=True, second_question_sequence=True))
    if contamination.status != "SOURCE_NEEDS_REEXTRACTION":
        raise RuntimeError("CONTAMINATION_EVIDENCE_NOT_REPRODUCED")


def ingest(*, force: bool = False) -> dict[str, Any]:
    successor = PILOT / "PRIVATE_JH_TEACHER_COVERAGE_SET_V6.csv"
    if (not force or successor.is_file()) and TEACHER_V5.is_file() and STATUS.is_file():
        status = json.loads(STATUS.read_text(encoding="utf-8-sig"))
        if CLEANING.is_file():
            status["source_quality"]["source_cleaning_queue_total"] = len(
                json.loads(CLEANING.read_text(encoding="utf-8-sig")).get("items", []))
        return status
    if not all(path.is_file() for path in (TEACHER_V4, MANIFEST, GT, CLEANING)):
        raise RuntimeError("MISSING_COVERAGE_BATCH4_INPUT")
    located = _locate()
    _validate_ids()
    _verify_source_evidence(located)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    by_text = {q["question_text"]: q for q in manifest["questions"]}
    gt = {row["fingerprint"]: row for row in _jsonl(GT)}
    now = datetime.now(timezone.utc).isoformat()
    for number, spec in BATCH.items():
        locator = located[number]
        fp = locator["fingerprint"]
        old = gt.get(fp, {})
        gt[fp] = {"fingerprint": fp, "coverage_set_version": "V4", "coverage_set_number": number,
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
    for number in (7, 8):
        locator, spec = located[number], BATCH[number]
        question = locator["question"]
        items[locator["fingerprint"]] = {"fingerprint": locator["fingerprint"],
            "coverage_set_version": "V4", "coverage_set_number": number,
            "source_school": question.get("source_school"), "source_year": question.get("source_year"),
            "source_document": question.get("source_url"), "question_number": question.get("question_number"),
            "page_number": None, "reason": spec["reason"], "status": spec["status"],
            "replacement_status": "PENDING", "detection_source": "TEACHER_APPROVED_SOURCE_QUALITY"}

    rows = _csv(TEACHER_V4)
    number_col, _, question_col = _columns(rows)
    processed = {entry["fingerprint"] for entry in located.values()}
    existing_cleaning = set(items)
    new_fraction: list[str] = []
    new_contamination: list[str] = []
    for row in rows:
        question = by_text.get(row[question_col])
        if not question or question["fingerprint"] in processed or question["fingerprint"] in existing_cleaning:
            continue
        fp = question["fingerprint"]
        fraction = assess_fraction_structure_loss(question["question_text"],
            source_metadata=_metadata(question, fraction_expected="分數" in (question.get("topic_groups") or [])),
            pdf_text_discrepancy=False)
        contamination = assess_multi_document_contamination(question["question_text"],
            source_metadata=_metadata(question))
        reason = None
        if fraction.status != "PASS":
            new_fraction.append(fp); reason = "MATH_FRACTION_NOTATION_LOST"
        elif contamination.status != "PASS":
            new_contamination.append(fp); reason = "MULTI_DOCUMENT_CONTAMINATION"
        if reason:
            items[fp] = {"fingerprint": fp, "source_school": question.get("source_school"),
                "source_year": question.get("source_year"), "source_document": question.get("source_url"),
                "question_number": question.get("question_number"), "page_number": None,
                "reason": reason, "status": "NEEDS_REEXTRACTION", "replacement_status": "PENDING",
                "detection_source": "DETERMINISTIC_SOURCE_QUALITY_GATE"}
    CLEANING.write_text(json.dumps({"items": list(items.values())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    additional = set(new_fraction + new_contamination)
    remove = processed | additional
    remaining = [row.copy() for row in rows if by_text[row[question_col]]["fingerprint"] not in remove]
    for index, row in enumerate(remaining, 1):
        row[number_col] = index
    _write_csv(TEACHER_V5, remaining, list(rows[0]))
    validated = [row for row in gt.values() if row.get("source_status") == "HUMAN_VALIDATED"]
    status = {"teacher_batch": {"reviewed": 4, "human_validated": 2, "source_reextraction": 2,
            "id_validation_failures": 0, "parent_failures": 0},
        "source_quality": {"fraction_loss_gate": "READY", "new_fraction_loss_risks": len(new_fraction),
            "new_contamination_risks": len(new_contamination), "source_cleaning_queue_total": len(items)},
        "private_jh_extension": {"divisibility_by_3_rule": "CANDIDATE_GUIDANCE_READY",
            "foundation_skill": "G05-N-MULTIPLE-01", "secondary_guidance": "G06-R-COUNT-01"},
        "human_coverage": {"direct_human_gt": len(validated),
            "unique_validated_skills": len({r["human_primary_skill_id"] for r in validated}),
            "unique_validated_micros": len({r["human_primary_micro_id"] for r in validated})},
        "teacher_review": {"previous_questions": len(rows), "removed_by_human_gt": 2,
            "removed_for_source_cleaning": 2, "additional_quality_gate_removals": len(additional),
            "remaining_questions": len(remaining)}, "api_calls": 0, "production_reads": 0,
        "production_writes": 0}
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    print(json.dumps(ingest(), ensure_ascii=False))
