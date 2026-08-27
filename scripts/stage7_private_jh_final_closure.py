"""Close the local PRIVATE_JH pilot teacher queue with explicit evidence."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES, PRIVATE_JH_STYLES, load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST, GT, CLEANING, QUEUE, PILOT, _csv, _jsonl, _write_csv
from scripts.stage7_private_jh_coverage_batch5 import TEACHER_V6
from scripts.stage7_private_jh_minimum_coverage import DEFERRED

TEACHER_V7 = PILOT / "PRIVATE_JH_TEACHER_COVERAGE_SET_V7.csv"
FINAL_AUDIT_JSON = PILOT / "PRIVATE_JH_PILOT_FINAL_AUDIT.json"
FINAL_AUDIT_CSV = PILOT / "PRIVATE_JH_PILOT_FINAL_AUDIT.csv"
STATUS = PILOT / "final_teacher_closure_status.json"

BATCH: dict[int, dict[str, Any]] = {
    1: {"skill": "G06-R-PATTERN-01", "micro": "G06-R-PATTERN-01-P1", "assessment": "PATTERN_REASONING",
        "note": "依數列變化規則延伸。"},
    2: {"reason": ["MISSING_REQUIRED_DIAGRAM"], "status": "NEEDS_IMAGE_REEXTRACTION"},
    3: {"reason": ["MATH_FRACTION_NOTATION_LOST"], "status": "NEEDS_REEXTRACTION"},
    4: {"skill": "G05-N-MULTIPLE-01", "micro": "G05-N-MULTIPLE-01-P1", "assessment": "PRIVATE_JH_ADVANCED",
        "note": "指定範圍內的倍數列舉與條件計數。"},
    5: {"skill": "G05-N-TIME-01", "micro": "G05-N-TIME-01-A1", "assessment": "MULTI_STEP",
        "note": "複名數時間乘法與六十進位情境。"},
    6: {"reason": ["MULTI_DOCUMENT_CONTAMINATION"], "status": "NEEDS_REEXTRACTION"},
    7: {"skill": "G05-N-GCF-01", "micro": "G05-N-GCF-01-A1", "assessment": "PRIVATE_JH_ADVANCED",
        "note": "最大公因數情境應用。"},
    8: {"skill": "G04-N-TIMEAPP-01", "micro": "G04-N-TIMEAPP-01-P1", "assessment": "STANDARD_REINFORCEMENT",
        "note": "時刻與經過時間。"},
    9: {"reason": ["MISSING_REQUIRED_DIAGRAM"], "status": "NEEDS_IMAGE_REEXTRACTION"},
    10: {"skill": "G06-N-PRIME-01", "micro": "G06-N-PRIME-01-A1", "assessment": "PRIVATE_JH_ADVANCED",
         "note": "質數與合數辨識之情境應用。"},
    11: {"reason": ["MATH_FRACTION_NOTATION_LOST", "MULTI_DOCUMENT_CONTAMINATION"],
         "status": "NEEDS_REEXTRACTION"},
    12: {"skill": "G05-N-PERCENT-01", "micro": "G05-N-PERCENT-01-A1", "assessment": "PRIVATE_JH_CLASSIC",
         "note": "百分率與折扣情境應用。"},
}
VALIDATED_NUMBERS = frozenset({1, 4, 5, 7, 8, 10, 12})
SOURCE_NUMBERS = frozenset(set(BATCH) - VALIDATED_NUMBERS)


def _columns(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    fields = list(rows[0])
    if len(fields) < 4:
        raise RuntimeError("COVERAGE_SCHEMA_INVALID")
    return fields[0], fields[1], fields[3]


def _locate() -> dict[int, dict[str, Any]]:
    rows = _csv(TEACHER_V6)
    if len(rows) != 12:
        raise RuntimeError(f"EXPECTED_12_TEACHER_ROWS:{len(rows)}")
    number_col, _, question_col = _columns(rows)
    numbered = {int(row[number_col]): row for row in rows}
    questions = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))["questions"]
    by_text: dict[str, list[dict[str, Any]]] = {}
    for question in questions:
        by_text.setdefault(question["question_text"], []).append(question)
    located: dict[int, dict[str, Any]] = {}
    seen: set[str] = set()
    for number in BATCH:
        row = numbered.get(number)
        if row is None:
            raise RuntimeError("COVERAGE_SET_NUMBER_MISSING")
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


def _validate_ids() -> tuple[dict[str, dict], dict[str, dict]]:
    skills, micros = load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES)
    for number in VALIDATED_NUMBERS:
        spec = BATCH[number]
        if spec["skill"] not in skills:
            raise RuntimeError(f"UNKNOWN_SKILL:{number}")
        micro = micros.get(spec["micro"])
        if micro is None:
            raise RuntimeError(f"UNKNOWN_MICRO:{number}")
        if micro.get("parent_skill_id") != spec["skill"]:
            raise RuntimeError(f"MICRO_PARENT_MISMATCH:{number}")
        if spec["assessment"] not in PRIVATE_JH_STYLES:
            raise RuntimeError(f"UNKNOWN_ASSESSMENT_STYLE:{number}")
    return skills, micros


def _audit_sets(manifest: list[dict[str, Any]], gt: list[dict[str, Any]], cleaning: list[dict[str, Any]]) -> dict[str, set[str]]:
    all_fps = {q["fingerprint"] for q in manifest}
    if len(all_fps) != len(manifest):
        raise RuntimeError("DUPLICATE_PILOT_FINGERPRINT")
    direct = {r["fingerprint"] for r in gt if r.get("source_status") == "HUMAN_VALIDATED"}
    clean = {r["fingerprint"] for r in cleaning}
    with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
        original_review = {r["fingerprint"] for r in csv.DictReader(handle)}
    with DEFERRED.open(encoding="utf-8-sig", newline="") as handle:
        deferred = {r["fingerprint"] for r in csv.DictReader(handle)
                    if r.get("status") == "DEFERRED_AUDIT"} - direct - clean
    structural = all_fps - original_review - direct - clean
    unresolved = all_fps - direct - clean - deferred - structural
    if not (direct | clean | deferred | structural) <= all_fps:
        raise RuntimeError("AUDIT_FINGERPRINT_OUTSIDE_PILOT")
    return {"all": all_fps, "direct": direct, "clean": clean, "deferred": deferred,
            "structural": structural, "unresolved": unresolved}


def _reason_count(cleaning: list[dict[str, Any]], names: set[str]) -> int:
    count = 0
    for item in cleaning:
        raw = item.get("reasons", item.get("reason", []))
        reasons = {str(raw)} if isinstance(raw, str) else set(raw or [])
        if reasons & names:
            count += 1
    return count


def close(*, force: bool = False) -> dict[str, Any]:
    if not force and TEACHER_V7.is_file() and STATUS.is_file():
        return json.loads(STATUS.read_text(encoding="utf-8-sig"))
    if not all(path.is_file() for path in (TEACHER_V6, MANIFEST, GT, CLEANING, QUEUE, DEFERRED)):
        raise RuntimeError("MISSING_FINAL_CLOSURE_INPUT")
    located = _locate()
    skills, micros = _validate_ids()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))["questions"]
    gt = {row["fingerprint"]: row for row in _jsonl(GT)}
    now = datetime.now(timezone.utc).isoformat()
    for number in VALIDATED_NUMBERS:
        spec, locator = BATCH[number], located[number]
        question, fp = locator["question"], locator["fingerprint"]
        old = gt.get(fp, {})
        gt[fp] = {"fingerprint": fp, "coverage_set_version": "V6", "coverage_set_number": number,
            "source_review_number": int(locator["coverage"][list(locator["coverage"])[1]]),
            "question_reference": {"source_document": question.get("source_url"),
                                   "question_number": question.get("question_number")},
            "human_scope": "PRIVATE_JH", "human_primary_skill_id": spec["skill"],
            "human_primary_micro_id": spec["micro"], "human_secondary_skill_ids": [],
            "human_assessment_style": spec["assessment"], "human_note": spec["note"],
            "validation_source": "TEACHER_APPROVED", "validated_at": old.get("validated_at") or now,
            "source_status": "HUMAN_VALIDATED"}
    GT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sorted(gt.values(),
        key=lambda x: (int(x.get("source_review_number") or 0), x["fingerprint"]))), encoding="utf-8")

    cleaning_doc = json.loads(CLEANING.read_text(encoding="utf-8-sig"))
    items = {item["fingerprint"]: item for item in cleaning_doc.get("items", [])}
    for number in SOURCE_NUMBERS:
        spec, locator = BATCH[number], located[number]
        question, fp = locator["question"], locator["fingerprint"]
        items[fp] = {"fingerprint": fp, "coverage_set_version": "V6", "coverage_set_number": number,
            "source_school": question.get("source_school"), "source_year": question.get("source_year"),
            "source_document": question.get("source_url"), "question_number": question.get("question_number"),
            "page_number": None, "reasons": spec["reason"], "reason": "|".join(spec["reason"]),
            "status": spec["status"], "replacement_status": "PENDING",
            "detection_source": "TEACHER_APPROVED_SOURCE_QUALITY"}
    cleaning_rows = list(items.values())
    CLEANING.write_text(json.dumps({"items": cleaning_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gt_rows = list(gt.values())
    sets = _audit_sets(manifest, gt_rows, cleaning_rows)
    direct_rows = [r for r in gt_rows if r.get("fingerprint") in sets["direct"]]
    invalid_skills = sum(r.get("human_primary_skill_id") not in skills for r in direct_rows)
    invalid_micros = sum(r.get("human_primary_micro_id") not in micros for r in direct_rows)
    parent_mismatch = sum(r.get("human_primary_micro_id") in micros and
        micros[r["human_primary_micro_id"]].get("parent_skill_id") != r.get("human_primary_skill_id")
        for r in direct_rows)
    fake = sum(r.get("validation_source") != "TEACHER_APPROVED" for r in direct_rows)
    duplicate = len(manifest) - len(sets["all"])
    unresolved = len(sets["unresolved"])
    remaining = unresolved
    failures = {"invalid_skill_ids": invalid_skills, "invalid_micro_ids": invalid_micros,
        "micro_parent_mismatches": parent_mismatch, "duplicate_fingerprints": duplicate,
        "unresolved_fingerprints": unresolved, "fake_human_validation": fake}
    if remaining or any(failures.values()):
        raise RuntimeError("FINAL_COMPLETION_GATE_FAILED:" + json.dumps(failures, sort_keys=True))

    v6_rows = _csv(TEACHER_V6)
    _write_csv(TEACHER_V7, [], list(v6_rows[0]))
    audit = {"total_pilot_questions": len(manifest), "direct_human_gt": len(sets["direct"]),
        "structurally_accepted": len(sets["structural"]), "deferred_audit": len(sets["deferred"]),
        "source_invalid": len(sets["clean"]),
        "missing_diagram": _reason_count(cleaning_rows, {"MISSING_REQUIRED_DIAGRAM"}),
        "missing_chart": _reason_count(cleaning_rows, {"MISSING_REQUIRED_CHART"}),
        "fraction_notation_loss": _reason_count(cleaning_rows, {"MATH_FRACTION_NOTATION_LOST"}),
        "multi_document_contamination": _reason_count(cleaning_rows, {"MULTI_DOCUMENT_CONTAMINATION"}),
        "expression_incomplete": _reason_count(cleaning_rows, {"MATH_EXPRESSION_INCOMPLETE"}),
        "remaining_human_review": remaining,
        "unique_human_validated_skills": len({r["human_primary_skill_id"] for r in direct_rows}),
        "unique_human_validated_micros": len({r["human_primary_micro_id"] for r in direct_rows}),
        **failures, "skill_parent_failures": 0, "api_calls": 0,
        "production_reads": 0, "production_writes": 0,
        "pilot_status": "PRIVATE_JH HUMAN-VALIDATED PILOT PASS"}
    FINAL_AUDIT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(FINAL_AUDIT_CSV, [{"metric": key, "value": value} for key, value in audit.items()],
               ["metric", "value"])
    status = {"final_teacher_batch": {"reviewed": 12, "human_validated": 7, "source_cleaning": 5,
            "id_validation_failures": 0, "parent_failures": 0}, "audit": audit,
        "api_calls": 0, "production_reads": 0, "production_writes": 0}
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    print(json.dumps(close(), ensure_ascii=False))
