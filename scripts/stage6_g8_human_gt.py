"""Ingest saved human labels and propagate one exact structural G8 template locally."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".local" / "stage6_real_g8_pilot"
EXPECTED_SCOPE = "IN_SCOPE_G8"
EXPECTED_SKILL = "G08-A-MULFORM-APP-01"
EXPECTED_MICRO = "G08-A-MULFORM-APP-01-P1"
NUMBER = re.compile(r"(?<![A-Za-z0-9])\d+(?![A-Za-z0-9])")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _dict_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _simple_rows(path: Path) -> list[list[str]]:
    raw = path.read_bytes(); encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "cp950"
    with path.open(encoding=encoding, newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or len(rows[0]) != 11 or len(rows) != 57:
        raise RuntimeError("HUMAN_REVIEW_SIMPLE_SCHEMA_INVALID")
    return rows[1:]


def _signature(text: str) -> tuple[str, tuple[int, ...]]:
    values = tuple(int(value) for value in NUMBER.findall(str(text or "")))
    return NUMBER.sub("{N}", str(text or "").strip()), values


def exact_difference_of_squares_match(text: str, validated_skeleton: str) -> bool:
    skeleton, values = _signature(text)
    return skeleton == validated_skeleton and len(values) == 2 and values[1] == values[0] + 2


def _hashes(names: tuple[str, ...]) -> dict[str, str]:
    return {name: hashlib.sha256((PRIVATE / name).read_bytes()).hexdigest() for name in names}


def _review_rank(gemini: dict[str, Any], deepseek: dict[str, Any]) -> tuple[int, str]:
    if gemini.get("scope_status") != deepseek.get("scope_status"): return 1, "SCOPE_DISAGREEMENT"
    if (gemini.get("skill_id") or None) != (deepseek.get("skill_id") or None): return 2, "SKILL_DISAGREEMENT"
    if (gemini.get("micro_skill_id") or None) != (deepseek.get("micro_skill_id") or None): return 3, "MICRO_DISAGREEMENT"
    if "OUT_OF_SCOPE_G8" in {gemini.get("scope_status"), deepseek.get("scope_status")}: return 4, "OUT_OF_SCOPE"
    return 5, "OTHER_AUDIT"


def run() -> dict[str, Any]:
    immutable = ("G8_HUMAN_REVIEW_SIMPLE.csv", "G8_HUMAN_REVIEW_FOR_TEACHER.csv", "g8_pilot_sample.json",
                 "g8_scope_mapping_results.jsonl", "deepseek_results.jsonl", "human_review_private.csv")
    before = _hashes(immutable)
    simple = _simple_rows(PRIVATE / "G8_HUMAN_REVIEW_SIMPLE.csv")
    teacher = _dict_csv(PRIVATE / "G8_HUMAN_REVIEW_FOR_TEACHER.csv")
    if [row[0].strip() for row in simple[:5]] != [str(i) for i in range(1, 6)]:
        raise RuntimeError("HUMAN_LABEL_SEQUENCE_INVALID")
    expected = (EXPECTED_SCOPE, EXPECTED_SKILL, EXPECTED_MICRO)
    if not all(len(row) >= 11 and (row[7].strip(), row[8].strip(), row[9].strip()) == expected and row[10].strip() for row in simple[:5]):
        raise RuntimeError("HUMAN_LABELS_NOT_SAVED")
    validated_fps = [teacher[index]["fingerprint"] for index in range(5)]
    ground_truth = [{"fingerprint": fp, "human_scope": simple[index][7].strip(),
                     "human_skill_id": simple[index][8].strip(), "human_micro_id": simple[index][9].strip(),
                     "human_note": simple[index][10].strip(), "validated_by": "HUMAN", "validation_status": "VALIDATED"}
                    for index, fp in enumerate(validated_fps)]
    (PRIVATE / "human_ground_truth.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ground_truth), encoding="utf-8")
    samples = _json(PRIVATE / "g8_pilot_sample.json"); sample_by_fp = {row["fingerprint"]: row for row in samples}
    skeletons = {_signature(sample_by_fp[fp]["question_text"])[0] for fp in validated_fps}
    if len(skeletons) != 1 or not all(exact_difference_of_squares_match(sample_by_fp[fp]["question_text"], next(iter(skeletons))) for fp in validated_fps):
        raise RuntimeError("HUMAN_TEMPLATE_NOT_STRUCTURALLY_CONSISTENT")
    skeleton = next(iter(skeletons)); matches = {row["fingerprint"] for row in samples if exact_difference_of_squares_match(row["question_text"], skeleton)}
    inferred = matches - set(validated_fps); unsafe = {row["fingerprint"] for row in samples} - matches
    audit = {"total_questions": len(samples), "exact_structural_matches": len(matches), "human_validated": len(validated_fps),
             "structurally_inferred": len(inferred), "unsafe_matches_rejected": len(unsafe),
             "template": {"relation": "n*(n+2)_equivalent_to_(a-1)*(a+1)", "scope": EXPECTED_SCOPE,
                          "skill_id": EXPECTED_SKILL, "micro_skill_id": EXPECTED_MICRO,
                          "gate": "EXACT_SKELETON_AND_TWO_INTEGERS_DIFFER_BY_TWO"},
             "production_reads": 0, "production_writes": 0}
    (PRIVATE / "structural_template_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gemini = {row["fingerprint"]: row for row in _jsonl(PRIVATE / "g8_scope_mapping_results.jsonl")}
    deepseek = {row["fingerprint"]: row for row in _jsonl(PRIVATE / "deepseek_results.jsonl")}
    queue = _dict_csv(PRIVATE / "G8_HUMAN_REVIEW_FOR_TEACHER.csv")
    v2 = []
    for index, row in enumerate(queue):
        fp = row["fingerprint"]
        if fp in validated_fps: status, marker = "HUMAN_VALIDATED", "HUMAN_VALIDATED"
        elif fp in inferred: status, marker = "STRUCTURALLY_INFERRED", "STRUCTURAL_MATCH_TO_HUMAN_GT"
        else: status, marker = "REQUIRES_HUMAN_REVIEW", ""
        rank, detail = _review_rank(gemini[fp], deepseek[fp])
        v2.append({"fingerprint": fp, "review_status": status, "structural_marker": marker,
                   "review_priority": row["review_priority"], "disagreement_priority": detail,
                   "question_text": row["question_text"], "gemini_scope": row["gemini_scope"], "deepseek_scope": row["deepseek_scope"],
                   "gemini_skill_id": row["gemini_skill_id"], "deepseek_skill_id": row["deepseek_skill_id"],
                   "gemini_micro_id": row["gemini_micro_id"], "deepseek_micro_id": row["deepseek_micro_id"],
                   "human_scope": row["human_scope"] if fp not in validated_fps else EXPECTED_SCOPE,
                   "human_skill_id": row["human_skill_id"] if fp not in validated_fps else EXPECTED_SKILL,
                   "human_micro_id": row["human_micro_id"] if fp not in validated_fps else EXPECTED_MICRO,
                   "human_note": simple[index][10].strip() if fp in validated_fps else row["human_note"], "_rank": rank})
    v2.sort(key=lambda row: (0 if row["review_status"] == "REQUIRES_HUMAN_REVIEW" else 1, row["_rank"], row["review_priority"], row["fingerprint"]))
    fields = tuple(key for key in v2[0] if key != "_rank")
    with (PRIVATE / "G8_HUMAN_REVIEW_SIMPLE_V2.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows({key: row[key] for key in fields} for row in v2)
    queue_matches = {row["fingerprint"] for row in queue} & matches
    remaining_rows = [row for row in v2 if row["review_status"] == "REQUIRES_HUMAN_REVIEW"]
    priority_remaining = {f"{priority}_remaining": sum(row["review_priority"] == priority for row in remaining_rows) for priority in ("P0", "P1", "P2", "P3", "P4")}
    workload = {"original_review_queue": 56, "human_validated": 5,
                "structurally_inferred": len(queue_matches - set(validated_fps)), "remaining_human_review": len(remaining_rows),
                **priority_remaining, "production_reads": 0, "production_writes": 0}
    audit["review_workload"] = workload
    (PRIVATE / "structural_template_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if before != _hashes(immutable): raise RuntimeError("ORIGINAL_ARTIFACT_MODIFIED")
    return {"audit": audit, "workload": workload}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
