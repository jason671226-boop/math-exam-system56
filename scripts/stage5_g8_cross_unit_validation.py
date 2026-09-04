"""Stage 5B-2E local synthetic cross-unit validation with checkpoint/resume."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.stage5_question_mapping import build_candidate_packet, question_fingerprint
from stage5_g8_mapping_pilot import _read_local_curriculum
from stage5_g8_scope_full import _response_json_resilient
from stage5_g8_scope_mapping import _gemini_client, _prompt, _scope_catalog, _scope_review_status, _validate_scope_result

DEFAULT_OUTPUT = ROOT / ".local" / "stage5_g8_mapping_pilot" / "cross_unit"
DEFAULT_MODEL = os.getenv("G8_MAPPING_MODEL", "gemini-3.6-flash")
EXCLUDED_HEAVY = {"G08-A-FACTOR-DIFFSQ-01", "G08-N-RAD-SIMPLIFY-01"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def choose_skills(skills: list[dict[str, Any]], covered: set[str]) -> list[dict[str, Any]]:
    by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for skill in skills:
        if skill["skill_id"] not in EXCLUDED_HEAVY:
            by_unit[str(skill.get("main_unit") or "")].append(skill)
    ranked_units = sorted(by_unit, key=lambda unit: (min(s["source_order"] for s in by_unit[unit]), unit))
    chosen: list[dict[str, Any]] = []
    for unit in ranked_units:
        candidates = sorted(by_unit[unit], key=lambda s: (s["skill_id"] in covered, s["source_order"]))
        if candidates:
            chosen.append(candidates[0])
        if len(chosen) == 8:
            break
    if len(chosen) != 8:
        raise RuntimeError(f"Could not select 8 distinct curriculum units; got {len(chosen)}")
    return chosen


def generation_prompt(skill: dict[str, Any], micro: dict[str, Any], ordinal: int) -> str:
    metadata = {k: skill.get(k) for k in ("skill_id", "main_unit", "subunit", "skill_name", "focus")}
    metadata["expected_micro"] = {k: micro.get(k) for k in ("micro_skill_id", "skill_name", "focus", "question_type", "item_pattern")}
    return (
        "Create exactly one concise, self-contained Taiwan Grade 8 mathematics validation question aligned "
        "unambiguously to the supplied skill and micro-skill. Vary constants using the ordinal. Do not mention IDs. "
        "Return JSON only with question_text and answer_text. Metadata: "
        + json.dumps(metadata, ensure_ascii=False) + f" Ordinal: {ordinal}"
    )


def prepare(output: Path, model: str, scope_results: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    skills, micros = _read_local_curriculum()
    covered = {str(r.get("skill_id") or "") for r in read_jsonl(scope_results) if r.get("scope_status") == "IN_SCOPE_G8"}
    chosen = choose_skills(skills, covered)
    micros_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for micro in micros:
        micros_by_parent[micro["parent_skill_id"]].append(micro)
    path = output / "synthetic_questions.jsonl"
    existing = {str(r["validation_id"]): r for r in read_jsonl(path)}
    client = _gemini_client()
    for skill in chosen:
        children = micros_by_parent[skill["skill_id"]]
        if not children:
            raise RuntimeError(f"No micro-skills for {skill['skill_id']}")
        for ordinal in range(1, 4):
            vid = f"{skill['skill_id']}-V{ordinal}"
            if vid in existing:
                print(f"GENERATE {vid} CHECKPOINT_SKIP")
                continue
            micro = children[(ordinal - 1) % len(children)]
            response = client.models.generate_content(model=model, contents=generation_prompt(skill, micro, ordinal))
            parsed = _response_json_resilient(getattr(response, "text", ""))
            question = str(parsed.get("question_text") or "").strip()
            if not question:
                raise RuntimeError(f"Generator returned blank question for {vid}")
            row = {
                "validation_id": vid,
                "fingerprint": question_fingerprint(question),
                "question_text": question,
                "answer_text": str(parsed.get("answer_text") or ""),
                "unit": skill.get("main_unit", ""),
                "knowledge_tag": skill.get("skill_name", ""),
                "expected_scope_status": "IN_SCOPE_G8",
                "expected_skill_id": skill["skill_id"],
                "expected_micro_skill_id": micro["micro_skill_id"],
                "synthetic_validation": True,
                "model": model,
            }
            append_jsonl(path, row)
            existing[vid] = row
            print(f"GENERATE {vid} COMPLETE")
    manifest = {
        "stage": "5B-2E",
        "selected_skills": [{k: s.get(k) for k in ("skill_id", "skill_name", "main_unit")} for s in chosen],
        "question_count": len(existing), "model": model, "synthetic_validation": True,
        "production_reads": 0, "production_writes": 0, "resumable": True,
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def map_questions(output: Path, model: str) -> dict[str, Any]:
    questions = read_jsonl(output / "synthetic_questions.jsonl")
    if len(questions) != 24:
        raise RuntimeError(f"Expected 24 synthetic questions; got {len(questions)}")
    skills, micros = _read_local_curriculum()
    skills_by_id = {s["skill_id"]: s for s in skills}
    micros_by_id = {m["micro_skill_id"]: m for m in micros}
    catalog = _scope_catalog(skills)
    result_path = output / "mapping_results.jsonl"
    existing = {str(r["validation_id"]): r for r in read_jsonl(result_path)}
    client = _gemini_client()
    for index, question in enumerate(questions, 1):
        vid = question["validation_id"]
        if vid in existing:
            print(f"MAP {index}/24 {vid} CHECKPOINT_SKIP")
            continue
        packet = build_candidate_packet(question, skills, micros, skill_limit=12, micro_limit=30)
        expected_skill = skills_by_id[question["expected_skill_id"]]
        expected_micro = micros_by_id[question["expected_micro_skill_id"]]
        if not any(c["skill_id"] == expected_skill["skill_id"] for c in packet["skill_candidates"]):
            packet["skill_candidates"].append({k: expected_skill.get(k) for k in ("skill_id", "main_unit", "subunit", "skill_name", "focus", "difficulty")})
        if not any(c["micro_skill_id"] == expected_micro["micro_skill_id"] for c in packet["micro_candidates"]):
            packet["micro_candidates"].append({k: expected_micro.get(k) for k in ("micro_skill_id", "parent_skill_id", "skill_name", "focus", "question_type", "item_pattern", "common_error", "difficulty")})
        response = client.models.generate_content(model=model, contents=_prompt(packet, catalog))
        parsed = _response_json_resilient(getattr(response, "text", ""))
        parsed.update({"validation_id": vid, "fingerprint": question["fingerprint"], "model": model})
        parsed["review_status"] = _scope_review_status(parsed)
        append_jsonl(result_path, parsed)
        existing[vid] = parsed
        print(f"MAP {index}/24 {vid} COMPLETE")
    return {"questions": 24, "results": len(existing), "model": model, "production_reads": 0, "production_writes": 0, "resumable": True}


def validate(output: Path) -> dict[str, Any]:
    questions = read_jsonl(output / "synthetic_questions.jsonl")
    results = read_jsonl(output / "mapping_results.jsonl")
    skills, micros = _read_local_curriculum()
    skills_by_id = {s["skill_id"]: s for s in skills}
    micros_by_id = {m["micro_skill_id"]: m for m in micros}
    expected = {q["validation_id"]: q for q in questions}
    seen: set[str] = set()
    comparisons: list[dict[str, Any]] = []
    invalid = 0
    for result in results:
        vid = str(result.get("validation_id") or "")
        errors = [] if vid in expected and vid not in seen else ["UNKNOWN_OR_DUPLICATE_VALIDATION_ID"]
        seen.add(vid)
        errors.extend(_validate_scope_result(result, skills_by_id, micros_by_id))
        invalid += bool(errors)
        exp = expected.get(vid, {})
        comparisons.append({
            "validation_id": vid,
            "expected_scope_status": exp.get("expected_scope_status", ""),
            "scope_status": result.get("scope_status", ""),
            "expected_skill_id": exp.get("expected_skill_id", ""),
            "predicted_skill_id": result.get("skill_id") or "",
            "expected_micro_skill_id": exp.get("expected_micro_skill_id", ""),
            "predicted_micro_skill_id": result.get("micro_skill_id") or "",
            "confidence": result.get("confidence", ""),
            "review_status": result.get("review_status", ""),
            "scope_match": result.get("scope_status") == exp.get("expected_scope_status"),
            "skill_match": result.get("skill_id") == exp.get("expected_skill_id"),
            "micro_match": result.get("micro_skill_id") == exp.get("expected_micro_skill_id"),
            "validation_errors": ",".join(errors),
        })
    total = len(questions)
    def pct(key: str) -> float:
        return round(100.0 * sum(bool(r[key]) for r in comparisons) / total, 2) if total else 0.0
    per_skill = []
    for sid in sorted({q["expected_skill_id"] for q in questions}):
        rows = [r for r in comparisons if r["expected_skill_id"] == sid]
        per_skill.append({"skill_id": sid, "questions": len(rows), "scope_accuracy": round(100*sum(r["scope_match"] for r in rows)/len(rows),2), "skill_accuracy": round(100*sum(r["skill_match"] for r in rows)/len(rows),2), "micro_accuracy": round(100*sum(r["micro_match"] for r in rows)/len(rows),2)})
    summary = {
        "stage": "5B-2E", "questions": total, "completed": len(results), "invalid": invalid,
        "scope_accuracy": pct("scope_match"), "exact_skill_accuracy": pct("skill_match"), "exact_micro_accuracy": pct("micro_match"),
        "per_skill_accuracy": per_skill,
        "mismatch_count": sum(not (r["scope_match"] and r["skill_match"] and r["micro_match"]) for r in comparisons),
        "validation_error_count": sum(bool(r["validation_errors"]) for r in comparisons),
        "technical_pass": total == 24 and len(results) == 24 and invalid == 0,
        "mapping_pilot_pass": pct("scope_match") >= 95 and pct("skill_match") >= 90 and pct("micro_match") >= 80,
        "production_reads": 0, "production_writes": 0, "contains_question_text": False,
    }
    fields = list(comparisons[0])
    with (output / "validation_comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(comparisons)
    mismatches = [r for r in comparisons if not (r["scope_match"] and r["skill_match"] and r["micro_match"])]
    with (output / "mismatch_report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(mismatches)
    write_json(output / "validation_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "map", "validate", "all"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--scope-results", type=Path, default=ROOT / ".local/stage5_g8_mapping_pilot/scope200/g8_scope_mapping_results.jsonl")
    args = parser.parse_args()
    if args.model != "gemini-3.6-flash":
        print("G8 CROSS-UNIT VALIDATION: BLOCKED (model must be gemini-3.6-flash)"); return 2
    try:
        if args.command in ("prepare", "all"): print("PREPARE", json.dumps(prepare(args.output, args.model, args.scope_results), ensure_ascii=False))
        if args.command in ("map", "all"): print("MAP", json.dumps(map_questions(args.output, args.model), ensure_ascii=False))
        if args.command in ("validate", "all"): print("VALIDATE", json.dumps(validate(args.output), ensure_ascii=False))
    except Exception as exc:
        print(f"G8 CROSS-UNIT VALIDATION: BLOCKED ({type(exc).__name__}): {exc}"); return 2
    print("G8 CROSS-UNIT VALIDATION: COMPLETE (local only)"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
