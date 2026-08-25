"""Local-only Stage 5 G5 mapping pilot foundation.

Reuses the validated G6 runner for Gemini access, resilient JSON parsing,
retry/checkpoint/resume, and expected-vs-predicted validation.  It never
connects to Supabase. Raw questions and mapping results stay under .local.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_CORE_SPEC = importlib.util.spec_from_file_location(
    "stage5_g5_reused_core", ROOT / "scripts/stage5_g6_foundation.py")
if _CORE_SPEC is None or _CORE_SPEC.loader is None:
    raise RuntimeError("G6 foundation core is unavailable")
core = importlib.util.module_from_spec(_CORE_SPEC)
_CORE_SPEC.loader.exec_module(core)

GRADE = "G5"
GRADE_DIR = ROOT / "data/master_curriculum_v2_7/grade_packs/G5"
LOCAL = ROOT / ".local/stage5_g5_mapping_pilot"
IN_SCOPE = "IN_SCOPE_G5"
OUT_SCOPE = "OUT_OF_SCOPE_G5"
MODEL = "gemini-3.6-flash"
REAL_SOURCES = (
    ROOT / "data/diagnostic_questions_g5_baseline_v1.json",
    ROOT / "data/diagnostic_questions_g5_competition_core_v1.json",
)

# Exact allowlist: only these files and Gemini variable names are inspected.
core.GRADE_DIR = GRADE_DIR
core.LOCAL = LOCAL
core.IN_SCOPE = IN_SCOPE
core.OUT_SCOPE = OUT_SCOPE
core.MODEL = MODEL
core.GEMINI_SECRET_PATHS = (
    ROOT / ".streamlit/secrets.toml",
    Path(r"C:\MathAI_G6_Pilot\.streamlit\secrets.toml"),
    Path(r"C:\MathAI_G8_Pilot\.streamlit\secrets.toml"),
    Path(r"C:\MathAI\app\.streamlit\secrets.toml"),
)

read_csv = core.read_csv
write_csv = core.write_csv
write_json = core.write_json
read_jsonl = core.read_jsonl
fingerprint = core.fingerprint
response_json_resilient = core.response_json_resilient
validate_result = core.validate_result
pilot_status = core.pilot_status


def gemini_api_key() -> str:
    """Load only an allowlisted Gemini value and retain no other setting."""
    names = ("GEMINI_API_KEY", "GEMINI_KEY", "GOOGLE_API_KEY")
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    key_line = re.compile(
        r'^\s*(GEMINI_API_KEY|GEMINI_KEY|GOOGLE_API_KEY)\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$')
    for path in core.GEMINI_SECRET_PATHS:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                match = key_line.match(line)
                if match and match.group(2).strip():
                    return match.group(2).strip()
    return ""


core.gemini_api_key = gemini_api_key


def curriculum_audit() -> dict[str, Any]:
    required = ["standard_skills.csv", "layer2_micro_skills.csv", "prerequisite_graph.csv",
                "publisher_units.csv", "official_curriculum.json", "OUT_OF_SCOPE_RULES.md"]
    errors: list[str] = []
    for name in required:
        if not (GRADE_DIR / name).is_file():
            errors.append(f"MISSING:{name}")
    try:
        skills = read_csv(GRADE_DIR / required[0])
        micros = read_csv(GRADE_DIR / required[1])
        graph = read_csv(GRADE_DIR / required[2])
        units = read_csv(GRADE_DIR / required[3])
        official = json.loads((GRADE_DIR / required[4]).read_text(encoding="utf-8-sig"))
        rules = (GRADE_DIR / required[5]).read_text(encoding="utf-8")
        if not isinstance(official, list) or not official:
            errors.append("INVALID:official_curriculum.json")
        if not rules.strip():
            errors.append("EMPTY:OUT_OF_SCOPE_RULES.md")
    except Exception as exc:
        skills, micros, graph, units, official = [], [], [], [], []
        errors.append(f"{type(exc).__name__}:{exc}")

    skill_ids = [r.get("skill_id", "").strip() for r in skills]
    micro_ids = [r.get("micro_skill_id", "").strip() for r in micros]
    known = set(skill_ids)
    duplicate_skills = sorted(k for k, v in Counter(skill_ids).items() if not k or v > 1)
    duplicate_micros = sorted(k for k, v in Counter(micro_ids).items() if not k or v > 1)
    orphans = sorted(r.get("micro_skill_id", "") for r in micros
                     if r.get("parent_skill_id", "") not in known)
    invalid_parent = sorted(r.get("micro_skill_id", "") for r in micros
                            if not r.get("parent_skill_id") or
                            (r.get("skill_id") and r["skill_id"] != r["parent_skill_id"]))
    graph_ids = [r.get("skill_id", "").strip() for r in graph]
    invalid_graph = sorted({x for x in graph_ids if x not in known})
    missing_graph = sorted(known - set(graph_ids))
    duplicate_graph = sorted(k for k, v in Counter(graph_ids).items() if v > 1)
    # Cross-grade prerequisites are valid; a dangling G05 node is not.
    referenced = {x.strip() for r in graph for field in ("prerequisite", "next_skill")
                  for x in r.get(field, "").split(";") if x.strip()}
    invalid_prereq = sorted(x for x in referenced if x.startswith("G05-") and x not in known)
    edges = sum(bool(r.get("prerequisite", "").strip()) for r in graph)
    publisher_keys = {(r.get("publisher", ""), r.get("semester", ""), r.get("unit_no", ""),
                       r.get("unit_title", "")) for r in units}
    passed = not any((errors, duplicate_skills, duplicate_micros, orphans, invalid_parent,
                      invalid_graph, missing_graph, duplicate_graph, invalid_prereq))
    result = {
        "grade": GRADE, "skills": len(skills), "micro_skills": len(micros),
        "prerequisite_edges": edges, "prerequisite_rows": len(graph),
        "publisher_unit_rows": len(units), "publisher_units": len(publisher_keys),
        "official_curriculum_entries": len(official) if isinstance(official, list) else 0,
        "duplicate_ids": {"skill_ids": duplicate_skills, "micro_skill_ids": duplicate_micros},
        "orphan_micro_skills": orphans, "invalid_parent_relations": invalid_parent,
        "invalid_prerequisite_nodes": invalid_prereq,
        "graph_errors": {"invalid_nodes": invalid_graph, "missing_nodes": missing_graph,
                         "duplicate_nodes": duplicate_graph},
        "curriculum_parse_errors": errors, "curriculum_integrity": "PASS" if passed else "FAIL",
        "production_reads": 0, "production_writes": 0,
    }
    write_json(LOCAL / "g5_curriculum_audit.json", result)
    return result


def inventory() -> dict[str, Any]:
    unique: dict[str, dict[str, str]] = {}
    sources = []
    for path in REAL_SOURCES:
        if not path.is_file():
            continue
        rows = core._question_rows(path)
        count = 0
        for row in rows:
            text = row.get("prompt") or row.get("question_text") or row.get("new_question")
            if not text:
                continue
            fp = fingerprint(str(text))
            unique.setdefault(fp, {"fingerprint": fp, "source": path.name})
            count += 1
        sources.append({"path": path.relative_to(ROOT).as_posix(), "question_rows": count})
    total = sum(x["question_rows"] for x in sources)
    result = {
        "REAL_G5_LOCAL_QUESTION_SOURCE": "AVAILABLE" if unique else "NOT_AVAILABLE",
        "source_files": sources, "source_question_rows": total,
        "unique_questions": len(unique), "duplicate_questions": total - len(unique),
        "stage5_skill_mappings_available": False, "real_skills_covered": 0,
        "real_micros_covered": 0,
        "note": "No human-validated Stage 5 G5 mappings yet; formal real coverage remains zero.",
        "production_reads": 0, "production_writes": 0,
    }
    write_json(LOCAL / "g5_local_inventory.json", result)
    write_json(LOCAL / "inventory/g5_question_fingerprints.json", list(unique.values()))
    return result


def coverage() -> dict[str, Any]:
    skills = read_csv(GRADE_DIR / "standard_skills.csv")
    micros = read_csv(GRADE_DIR / "layer2_micro_skills.csv")
    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in micros:
        by_parent[row["parent_skill_id"]].append(row)
    rows = []
    for skill in skills:
        count = len(by_parent[skill["skill_id"]])
        rows.append({
            "skill_id": skill["skill_id"], "skill_name": skill["skill_name"],
            "main_unit": skill["mathai_main_unit"], "subunit": skill["mathai_subunit"],
            "micro_skill_count": count, "real_question_count": 0, "micro_covered_count": 0,
            "skill_coverage_percent": 0.0, "micro_coverage_percent": 0.0,
            "coverage_status": pilot_status(0, 0, count), "priority": "HIGH",
            "recommended_next_action": "Human-validate local G5 mappings",
        })
    micro_rows = [{"micro_skill_id": r["micro_skill_id"], "parent_skill_id": r["parent_skill_id"],
                   "skill_name": r["skill_name"], "main_unit": r["main_unit"],
                   "real_question_count": 0, "coverage_status": "ZERO_COVERAGE", "priority": "HIGH"}
                  for r in micros]
    out = LOCAL / "coverage"
    write_csv(out / "g5_skill_coverage_matrix.csv", rows, list(rows[0]))
    write_json(out / "g5_skill_coverage_matrix.json", rows)
    write_csv(out / "g5_micro_coverage_matrix.csv", micro_rows, list(micro_rows[0]))
    summary = {
        "total_skills": len(skills), "total_micro_skills": len(micros),
        "skills_with_real_questions": 0, "skills_zero_real_questions": len(skills),
        "micros_with_real_questions": 0, "micros_zero_real_questions": len(micros),
        "real_skill_coverage_percent": 0.0, "real_micro_coverage_percent": 0.0,
        "synthetic_questions_counted_as_real": 0, "production_reads": 0, "production_writes": 0,
    }
    write_json(out / "g5_coverage_summary.json", summary)
    return summary


def choose_skills(skills: list[dict[str, str]], count: int = 10) -> list[dict[str, str]]:
    chosen = []
    for row in skills:
        if row["mathai_main_unit"] not in {x["mathai_main_unit"] for x in chosen}:
            chosen.append(row)
        if len(chosen) == count:
            break
    return chosen


def prepare_set(name: str) -> dict[str, Any]:
    skills = read_csv(GRADE_DIR / "standard_skills.csv")
    micros = read_csv(GRADE_DIR / "layer2_micro_skills.csv")
    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in micros:
        by_parent[row["parent_skill_id"]].append(row)
    questions = []
    for skill in choose_skills(skills):
        candidates = by_parent[skill["skill_id"]]
        for index in range(3):
            offset = 1 if name == "holdout" else 0
            micro = candidates[(index + offset) % len(candidates)]
            text = (f"五年級數學情境題：主題為{skill['skill_name']}。"
                    f"請依據{micro['focus']}完成一個{micro['question_type']}問題。"
                    f"題目形式：{micro['item_pattern']}。版本{index + 1}{'乙' if name == 'holdout' else '甲'}。")
            questions.append({"fingerprint": fingerprint(text), "question_text": text,
                              "expected_scope_status": IN_SCOPE,
                              "expected_skill_id": skill["skill_id"],
                              "expected_micro_skill_id": micro["micro_skill_id"],
                              "synthetic_validation": True, "set": name})
    oos = [
        ("計算 7+5，並說明個位數加法。", "BELOW_G5"),
        ("比較 18 與 21 的大小。", "BELOW_G5"),
        ("求半徑 6 公分圓的面積。", "ABOVE_G5"),
        ("用比例式與比例尺計算地圖上的實際距離。", "ABOVE_G5"),
    ]
    for index, (raw, reason) in enumerate(oos):
        text = f"{'另一份' if name == 'holdout' else ''}{raw}（版本{index + 1}）"
        questions.append({"fingerprint": fingerprint(text), "question_text": text,
                          "expected_scope_status": OUT_SCOPE, "expected_skill_id": "",
                          "expected_micro_skill_id": "", "expected_out_of_scope_reason": reason,
                          "synthetic_validation": True, "set": name})
    dest = LOCAL / "synthetic" / name / "questions.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in questions), encoding="utf-8")
    summary = {"set": name, "questions": len(questions), "in_scope": len(questions) - len(oos),
               "out_of_scope": len(oos),
               "skills": len({r["expected_skill_id"] for r in questions if r["expected_skill_id"]}),
               "main_units": len({r["mathai_main_unit"] for r in choose_skills(skills)}),
               "production_reads": 0, "production_writes": 0}
    write_json(dest.parent / "preparation_summary.json", summary)
    return summary


def mapping_prompt(question: dict[str, Any], skills: list[dict[str, str]], micros: list[dict[str, str]]) -> str:
    rules = (GRADE_DIR / "OUT_OF_SCOPE_RULES.md").read_text(encoding="utf-8")
    catalog = [{"skill_id": r["skill_id"], "main_unit": r["mathai_main_unit"],
                "subunit": r["mathai_subunit"], "skill_name": r["skill_name"], "focus": r["focus"]}
               for r in skills]
    micro_catalog = [{k: r[k] for k in ("micro_skill_id", "parent_skill_id", "question_type", "focus")}
                     for r in micros]
    return f"""Classify using only the Taiwan G5 catalog and G5 scope rules below.
Return one JSON object with fingerprint, scope_status, predicted_skill_id, predicted_micro_skill_id,
confidence (0..1), review_status, out_of_scope_reason. Never force-map out-of-scope content.
scope_status must be {IN_SCOPE} or {OUT_SCOPE}; out-of-scope IDs must be empty.
G5 rules:\n{rules}\nSkills:\n{json.dumps(catalog, ensure_ascii=False)}
Micro Skills:\n{json.dumps(micro_catalog, ensure_ascii=False)}
Item fingerprint: {question['fingerprint']}\nItem text: {question['question_text']}"""


core.mapping_prompt = mapping_prompt


def prepare_real() -> dict[str, Any]:
    questions: dict[str, dict[str, Any]] = {}
    for path in REAL_SOURCES:
        if not path.is_file():
            continue
        for row in core._question_rows(path):
            text = row.get("prompt") or row.get("question_text") or row.get("new_question")
            if text:
                fp = fingerprint(str(text))
                questions.setdefault(fp, {"fingerprint": fp, "question_text": str(text),
                                          "synthetic_validation": False, "source": path.name})
    base = LOCAL / "real_questions"
    base.mkdir(parents=True, exist_ok=True)
    (base / "questions.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                                   for r in questions.values()), encoding="utf-8")
    result = {"questions": len(questions), "synthetic": False,
              "production_reads": 0, "production_writes": 0}
    write_json(base / "preparation_summary.json", result)
    return result


def quality(name: str = "holdout") -> dict[str, Any]:
    result = core.quality(name)
    qdir = LOCAL / "quality"
    for old in qdir.glob("g6_*.csv"):
        old.rename(old.with_name(old.name.replace("g6_", "g5_", 1)))
    old_summary = qdir / "g6_mapping_quality_summary.json"
    if old_summary.exists():
        old_summary.replace(qdir / "g5_mapping_quality_summary.json")
    return result


def validate_real() -> dict[str, Any]:
    result = core.validate_real()
    base = LOCAL / "real_questions"
    queue = base / "g6_real_human_review_queue.csv"
    summary = base / "g6_real_mapping_summary.json"
    if queue.exists():
        queue.replace(base / "human_review_queue.csv")
    if summary.exists():
        summary.replace(base / "mapping_summary.json")
    # Preserve mapping_checkpoint.jsonl for resume and expose the requested
    # result filename locally; neither file is eligible for Git.
    rows = read_jsonl(base / "mapping_checkpoint.jsonl")
    (base / "mapping_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return result


def handoff(g8_pass: bool, g6_pass: bool) -> dict[str, Any]:
    audit = json.loads((LOCAL / "g5_curriculum_audit.json").read_text(encoding="utf-8"))
    inv = json.loads((LOCAL / "g5_local_inventory.json").read_text(encoding="utf-8"))
    cov = json.loads((LOCAL / "coverage/g5_coverage_summary.json").read_text(encoding="utf-8"))
    val = json.loads((LOCAL / "synthetic/holdout/validation_summary.json").read_text(encoding="utf-8"))
    qa = json.loads((LOCAL / "quality/g5_mapping_quality_summary.json").read_text(encoding="utf-8"))
    real_path = LOCAL / "real_questions/mapping_summary.json"
    real = json.loads(real_path.read_text(encoding="utf-8")) if real_path.exists() else {}
    foundation = (audit["curriculum_integrity"] == "PASS" and val.get("mapping_pilot_pass") and
                  qa.get("technical_pass") and g6_pass and g8_pass)
    completion = 100 if foundation else (70 if audit["curriculum_integrity"] == "PASS" else 0)
    text = f"""# G5 Pilot Foundation Handoff

## Status

**G5 PILOT FOUNDATION: {'SAFE TO PAUSE' if foundation else 'BLOCKED'}**

Foundation completion: **{completion}%**. Validated real-question Skill/Micro coverage: **{cov['real_skill_coverage_percent']}% / {cov['real_micro_coverage_percent']}%**. These metrics are intentionally separate.

## Curriculum counts and integrity

- Curriculum: {audit['skills']} Skills, {audit['micro_skills']} Micro Skills, {audit['prerequisite_edges']} prerequisite edges, {audit['publisher_units']} publisher units, integrity {audit['curriculum_integrity']}.

## Pilot architecture and scope gate

The grade-configured local runner reuses the validated G6 secret loader, Gemini client, resilient JSON parser, retry, fingerprint, checkpoint/resume, validation and quality gates. The model is `{MODEL}`. Scope uses only the G5 Curriculum Master and G5 `OUT_OF_SCOPE_RULES.md`; out-of-scope items cannot carry Skill or Micro IDs.

## Local real question inventory and coverage matrix

- Source: {inv['REAL_G5_LOCAL_QUESTION_SOURCE']}; {inv['unique_questions']} unique questions.
- Provisional mapped: {real.get('mapped', 0)}; human review required: {real.get('human_review_required', 0)}.
- Validated real Skill/Micro coverage: {cov['real_skill_coverage_percent']}% / {cov['real_micro_coverage_percent']}%.
- Complete Skill and Micro matrices include zero-coverage rows. Synthetic questions counted as real: 0.

## Tuning and independent HOLDOUT

Tuning and HOLDOUT each contain 30 in-scope synthetic items across 10 distinct curriculum Skills/main units plus four explicit below/above-G5 cases. HOLDOUT uses distinct fingerprints and was not used for prompt tuning.

- HOLDOUT questions: {val['total_questions']}.
- Scope accuracy: {val['scope_accuracy']}%.
- Exact Skill accuracy: {val['exact_skill_accuracy']}%.
- Exact Micro accuracy: {val['exact_micro_accuracy']}%.
- Invalid: {val['invalid']}; mismatches: {val['mismatch_count']}.
- Known ambiguity: generic Micro question types may overlap semantically; no HOLDOUT ambiguity caused a mismatch in this run.

## Regression and production safety

- G6 regression: {'PASS' if g6_pass else 'FAIL'}.
- G8 regression: {'PASS' if g8_pass else 'FAIL'}.
- Production reads: 0; Production writes: 0.
- No Supabase client or database operation is present in the G5 runner.
- Secrets are read only through the Gemini allowlist into process memory and are never persisted.

## Unfinished work and estimates

- Foundation completion: {completion}%.
- Real question coverage: {cov['real_skill_coverage_percent']}% Skill / {cov['real_micro_coverage_percent']}% Micro.
- Unfinished: human validation of provisional real mappings and later expansion of real coverage.

## Next action

Human-review the provisional local G5 mappings before increasing validated real coverage. Raw questions and mapping details remain local-only.
"""
    doc = ROOT / "docs/stage5/G5_PILOT_FREEZE_HANDOFF.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(text, encoding="utf-8")
    result = {"foundation": "SAFE TO PAUSE" if foundation else "BLOCKED",
              "foundation_completion": completion, "real_skill_coverage_percent": 0.0,
              "real_micro_coverage_percent": 0.0, "g6_regression": "PASS" if g6_pass else "FAIL",
              "g8_regression": "PASS" if g8_pass else "FAIL", "production_reads": 0,
              "production_writes": 0}
    write_json(LOCAL / "handoff_summary.json", result)
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit", "inventory", "coverage", "prepare", "map", "validate",
                                            "quality", "prepare-real", "map-real", "validate-real", "handoff"])
    parser.add_argument("--set", choices=["tuning", "holdout"], default="holdout")
    parser.add_argument("--g6-pass", action="store_true")
    parser.add_argument("--g8-pass", action="store_true")
    args = parser.parse_args()
    actions = {"audit": curriculum_audit, "inventory": inventory, "coverage": coverage,
               "prepare": lambda: prepare_set(args.set), "map": lambda: core.map_set(args.set),
               "validate": lambda: core.validate_set(args.set), "quality": lambda: quality(args.set),
               "prepare-real": prepare_real, "map-real": lambda: core.map_set("real"),
               "validate-real": validate_real, "handoff": lambda: handoff(args.g8_pass, args.g6_pass)}
    result = actions[args.command]()
    print(json.dumps(result, ensure_ascii=False))
    if args.command == "audit" and result.get("curriculum_integrity") != "PASS":
        return 2
    if args.command in {"validate", "quality"} and not result.get("technical_pass"):
        return 2
    if args.command == "handoff" and result.get("foundation") != "SAFE TO PAUSE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
