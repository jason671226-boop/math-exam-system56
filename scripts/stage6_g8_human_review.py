"""Prepare private, teacher-friendly CSVs from the Stage 6C review queue."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".local" / "stage6_real_g8_pilot"
PRIORITIES = (
    ("P0", "INVALID"),
    ("P1", "PROVIDER_DISAGREEMENT"),
    ("P2", "OUT_OF_SCOPE"),
    ("P3", "SUSPICIOUS"),
    ("P4", "AGREEMENT_AUDIT_SAMPLE"),
)
IMMUTABLE_INPUTS = (
    "human_review_private.csv", "g8_pilot_sample.json", "g8_mapping_input.jsonl",
    "g8_scope_mapping_results.jsonl", "deepseek_results.jsonl",
    "g8_curriculum_skills.json", "g8_curriculum_micro_skills.json",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _hashes() -> dict[str, str]:
    return {name: hashlib.sha256((PRIVATE / name).read_bytes()).hexdigest() for name in IMMUTABLE_INPUTS}


def _priority(reasons: set[str]) -> str:
    for priority, reason in PRIORITIES:
        if reason in reasons:
            return priority
    raise RuntimeError("REVIEW_REASON_WITHOUT_PRIORITY")


def _name(row: dict[str, Any] | None, *, micro: bool = False) -> str:
    if row is None:
        return "INVALID_ID"
    if micro:
        # G8 micro catalog has no dedicated name column; focus is its specific Chinese label.
        return str(row.get("focus") or row.get("skill_name") or "INVALID_ID")
    return str(row.get("skill_name") or "INVALID_ID")


def _id_name(value: Any, catalog: dict[str, dict[str, Any]], *, micro: bool = False) -> tuple[str, str]:
    identifier = str(value or "")
    if not identifier:
        return "", ""
    return identifier, _name(catalog.get(identifier), micro=micro)


def _validation_errors(row: dict[str, Any], skills: dict[str, Any], micros: dict[str, Any]) -> list[str]:
    errors = []; scope = str(row.get("scope_status") or ""); sid = str(row.get("skill_id") or ""); mid = str(row.get("micro_skill_id") or "")
    if scope not in {"IN_SCOPE_G8", "OUT_OF_SCOPE_G8"}: return ["INVALID_SCOPE_STATUS"]
    try:
        if not 0 <= float(row.get("confidence")) <= 1: errors.append("CONFIDENCE_OUT_OF_RANGE")
    except (TypeError, ValueError): errors.append("INVALID_CONFIDENCE")
    if scope == "OUT_OF_SCOPE_G8":
        if sid: errors.append("OUT_OF_SCOPE_HAS_SKILL")
        if mid: errors.append("OUT_OF_SCOPE_HAS_MICRO")
    else:
        if sid not in skills: errors.append("INVALID_SKILL")
        if mid and mid not in micros: errors.append("INVALID_MICRO")
        if mid in micros and micros[mid].get("parent_skill_id") != sid: errors.append("MICRO_PARENT_MISMATCH")
    return errors


def _suggestion(reasons: set[str]) -> str:
    prompts = []
    if "INVALID" in reasons: prompts.append("確認 Skill 與 Micro 的父子關係及 ID 有效性")
    if "PROVIDER_DISAGREEMENT" in reasons: prompts.append("比較兩者 Scope、Skill、Micro 差異並選定人工正解")
    if "OUT_OF_SCOPE" in reasons: prompts.append("確認題目是否確實超出八年級課綱")
    if "SUSPICIOUS" in reasons: prompts.append("檢查低信心或異常欄位")
    if "AGREEMENT_AUDIT_SAMPLE" in reasons: prompts.append("抽查兩者一致結果是否正確")
    return "；".join(prompts)


def prepare() -> dict[str, Any]:
    before = _hashes()
    queue = _csv(PRIVATE / "human_review_private.csv")
    if len(queue) != 56 or len({row["fingerprint"] for row in queue}) != 56:
        raise RuntimeError("REVIEW_QUEUE_INTEGRITY_FAILED")
    sample = {row["fingerprint"]: row for row in _json(PRIVATE / "g8_pilot_sample.json")}
    packets = {row["fingerprint"]: row for row in _jsonl(PRIVATE / "g8_mapping_input.jsonl")}
    gemini = {row["fingerprint"]: row for row in _jsonl(PRIVATE / "g8_scope_mapping_results.jsonl")}
    deepseek = {row["fingerprint"]: row for row in _jsonl(PRIVATE / "deepseek_results.jsonl")}
    skills = {row["skill_id"]: row for row in _json(PRIVATE / "g8_curriculum_skills.json")}
    micros = {row["micro_skill_id"]: row for row in _json(PRIVATE / "g8_curriculum_micro_skills.json")}
    expected = {row["fingerprint"] for row in queue}
    if any(not expected.issubset(source) for source in (sample, packets, gemini, deepseek)):
        raise RuntimeError("REVIEW_SOURCE_JOIN_FAILED")
    rows = []
    for queued in queue:
        fp = queued["fingerprint"]; reasons = set(filter(None, queued["reasons"].split("|")))
        g, d, source = gemini[fp], deepseek[fp], sample[fp]
        gsid, gsname = _id_name(g.get("skill_id"), skills); dsid, dsname = _id_name(d.get("skill_id"), skills)
        gmid, gmname = _id_name(g.get("micro_skill_id"), micros, micro=True); dmid, dmname = _id_name(d.get("micro_skill_id"), micros, micro=True)
        rows.append({
            "fingerprint": fp, "review_priority": _priority(reasons), "review_reason": "|".join(sorted(reasons)),
            "question_text": source.get("question_text", ""), "source_unit": source.get("unit", ""),
            "source_knowledge_tag": source.get("knowledge_tag", ""), "gemini_scope": g.get("scope_status", ""),
            "deepseek_scope": d.get("scope_status", ""), "gemini_skill_id": gsid, "gemini_skill_name": gsname,
            "deepseek_skill_id": dsid, "deepseek_skill_name": dsname, "gemini_micro_id": gmid,
            "gemini_micro_name": gmname, "deepseek_micro_id": dmid, "deepseek_micro_name": dmname,
            "gemini_confidence": g.get("confidence", ""), "deepseek_confidence": d.get("confidence", ""),
            "validation_error": "|".join(_validation_errors(d, skills, micros)),
            "human_scope": "", "human_skill_id": "", "human_micro_id": "", "human_decision": "", "human_note": "",
            "suggested_check": _suggestion(reasons),
        })
    rows.sort(key=lambda row: (row["review_priority"], row["fingerprint"]))
    teacher_fields = (
        "fingerprint", "review_priority", "review_reason", "question_text", "source_unit", "source_knowledge_tag",
        "gemini_scope", "deepseek_scope", "gemini_skill_id", "gemini_skill_name", "deepseek_skill_id", "deepseek_skill_name",
        "gemini_micro_id", "gemini_micro_name", "deepseek_micro_id", "deepseek_micro_name", "gemini_confidence",
        "deepseek_confidence", "validation_error", "human_scope", "human_skill_id", "human_micro_id", "human_decision", "human_note",
    )
    teacher_path = PRIVATE / "G8_HUMAN_REVIEW_FOR_TEACHER.csv"
    with teacher_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=teacher_fields); writer.writeheader(); writer.writerows({k: row[k] for k in teacher_fields} for row in rows)
    simple_fields = ("序號", "優先級", "題目", "Gemini判斷", "DeepSeek判斷", "差異原因", "建議檢查點", "人工正確Scope", "人工正確Skill", "人工正確Micro", "人工備註")
    simple_path = PRIVATE / "G8_HUMAN_REVIEW_SIMPLE.csv"
    with simple_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=simple_fields); writer.writeheader()
        for index, row in enumerate(rows, 1):
            writer.writerow({"序號": index, "優先級": row["review_priority"], "題目": row["question_text"],
                "Gemini判斷": " / ".join(filter(None, (row["gemini_scope"], row["gemini_skill_name"], row["gemini_micro_name"]))),
                "DeepSeek判斷": " / ".join(filter(None, (row["deepseek_scope"], row["deepseek_skill_name"], row["deepseek_micro_name"]))),
                "差異原因": row["review_reason"], "建議檢查點": row["suggested_check"], "人工正確Scope": "",
                "人工正確Skill": "", "人工正確Micro": "", "人工備註": ""})
    counts = {priority: sum(row["review_priority"] == priority for row in rows) for priority, _ in PRIORITIES}
    status = {"total_review": len(rows), **counts, "completed": 0, "remaining": len(rows),
              "duplicate_fingerprints": len(rows) - len({row["fingerprint"] for row in rows}),
              "production_reads": 0, "production_writes": 0}
    (PRIVATE / "human_review_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if before != _hashes(): raise RuntimeError("ORIGINAL_MAPPING_ARTIFACT_MODIFIED")
    return status


if __name__ == "__main__":
    print(json.dumps(prepare(), sort_keys=True))
