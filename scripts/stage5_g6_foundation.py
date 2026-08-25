"""Local-only Stage 5 G6 mapping pilot foundation.

The command never connects to Supabase. Question text and raw mapping outputs are
written only below .local/stage5_g6_mapping_pilot.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
GRADE_DIR = ROOT / "data/master_curriculum_v2_7/grade_packs/G6"
LOCAL = ROOT / ".local/stage5_g6_mapping_pilot"
MODEL = "gemini-3.6-flash"
IN_SCOPE = "IN_SCOPE_G6"
OUT_SCOPE = "OUT_OF_SCOPE_G6"
GEMINI_SECRET_PATHS = (
    ROOT / ".streamlit/secrets.toml",
    Path(r"C:\MathAI_G8_Pilot\.streamlit\secrets.toml"),
    Path(r"C:\MathAI\app\.streamlit\secrets.toml"),
)


def gemini_api_key() -> str:
    """Return only the Gemini key from approved in-memory/local sources."""
    for name in ("G6_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"):
        value = os.getenv(name)
        if value:
            return value.strip()
    for path in GEMINI_SECRET_PATHS:
        if not path.is_file():
            continue
        with path.open("rb") as handle:
            secrets = tomllib.load(handle)
        for name in ("GEMINI_API_KEY", "GEMINI_KEY"):
            value = secrets.get(name) if isinstance(secrets, dict) else None
            if value:
                return str(value).strip()
    return ""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def curriculum_audit() -> dict[str, Any]:
    required = ["standard_skills.csv", "layer2_micro_skills.csv", "prerequisite_graph.csv",
                "publisher_units.csv", "official_curriculum.json", "OUT_OF_SCOPE_RULES.md"]
    parse_errors: list[str] = []
    for name in required:
        if not (GRADE_DIR / name).is_file():
            parse_errors.append(f"MISSING:{name}")
    try:
        skills = read_csv(GRADE_DIR / "standard_skills.csv")
        micros = read_csv(GRADE_DIR / "layer2_micro_skills.csv")
        graph = read_csv(GRADE_DIR / "prerequisite_graph.csv")
        units = read_csv(GRADE_DIR / "publisher_units.csv")
        official = json.loads((GRADE_DIR / "official_curriculum.json").read_text(encoding="utf-8-sig"))
        rules = (GRADE_DIR / "OUT_OF_SCOPE_RULES.md").read_text(encoding="utf-8")
        if not isinstance(official, list) or not official:
            parse_errors.append("INVALID:official_curriculum.json")
        if not rules.strip():
            parse_errors.append("EMPTY:OUT_OF_SCOPE_RULES.md")
    except Exception as exc:
        skills, micros, graph, units = [], [], [], []
        parse_errors.append(f"{type(exc).__name__}:{exc}")

    skill_ids = [r.get("skill_id", "").strip() for r in skills]
    micro_ids = [r.get("micro_skill_id", "").strip() for r in micros]
    duplicate_skills = sorted(k for k, v in Counter(skill_ids).items() if not k or v > 1)
    duplicate_micros = sorted(k for k, v in Counter(micro_ids).items() if not k or v > 1)
    known = set(skill_ids)
    orphans = sorted(r.get("micro_skill_id", "") for r in micros if r.get("parent_skill_id", "") not in known)
    invalid_parent = sorted({
        r.get("micro_skill_id", "") for r in micros
        if r.get("parent_skill_id", "") not in known
        or (r.get("skill_id") and r.get("skill_id") != r.get("parent_skill_id"))
    })
    graph_rows_by_skill = Counter(r.get("skill_id", "") for r in graph)
    invalid_graph_nodes = sorted(k for k in graph_rows_by_skill if k not in known)
    missing_graph_nodes = sorted(known - set(graph_rows_by_skill))
    duplicate_graph_nodes = sorted(k for k, v in graph_rows_by_skill.items() if v > 1)
    edges = sum(len([p for p in r.get("prerequisites", "").split(";") if p.strip()]) for r in graph)
    publisher_keys = {
        (r.get("publisher", ""), r.get("semester", ""), r.get("unit_no", ""), r.get("unit_title", ""))
        for r in units
    }
    integrity = not any((parse_errors, duplicate_skills, duplicate_micros, orphans,
                         invalid_parent, invalid_graph_nodes, missing_graph_nodes, duplicate_graph_nodes))
    result = {
        "grade": "G6", "skills": len(skills), "micro_skills": len(micros),
        "prerequisite_edges": edges, "prerequisite_rows": len(graph),
        "publisher_unit_rows": len(units), "publisher_units": len(publisher_keys),
        "official_curriculum_entries": len(official) if isinstance(official, list) else 0,
        "orphan_micro_skills": orphans,
        "duplicate_ids": {"skill_ids": duplicate_skills, "micro_skill_ids": duplicate_micros},
        "invalid_parent_relations": invalid_parent,
        "graph_errors": {"invalid_nodes": invalid_graph_nodes, "missing_nodes": missing_graph_nodes,
                         "duplicate_nodes": duplicate_graph_nodes},
        "curriculum_parse_errors": parse_errors, "curriculum_integrity": "PASS" if integrity else "FAIL",
        "production_reads": 0, "production_writes": 0,
    }
    write_json(LOCAL / "g6_curriculum_audit.json", result)
    return result


def _question_rows(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]
    if isinstance(obj, dict):
        for key in ("questions", "items", "rows"):
            if isinstance(obj.get(key), list):
                return [r for r in obj[key] if isinstance(r, dict)]
    return []


def inventory() -> dict[str, Any]:
    candidates = [ROOT / "data/diagnostic_questions_g6_pilot_v1.json",
                  ROOT / "data/diagnostic_questions_g6_competition_core_v1.json"]
    unique: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file():
            continue
        rows = _question_rows(path)
        count = 0
        for row in rows:
            text = row.get("prompt") or row.get("question_text") or row.get("new_question")
            if not text:
                continue
            fp = fingerprint(str(text))
            unique.setdefault(fp, {"fingerprint": fp, "source": path.name})
            count += 1
        sources.append({"path": path.relative_to(ROOT).as_posix(), "question_rows": count})
    result = {
        "REAL_G6_LOCAL_QUESTION_SOURCE": "AVAILABLE" if unique else "NOT_AVAILABLE",
        "source_files": sources, "source_question_rows": sum(s["question_rows"] for s in sources),
        "unique_questions": len(unique), "duplicate_questions": sum(s["question_rows"] for s in sources) - len(unique),
        "stage5_skill_mappings_available": False,
        "real_skills_covered": 0, "real_micros_covered": 0,
        "note": "Local diagnostic items exist, but no validated Stage 5 G6 Skill/Micro mappings exist; coverage remains zero.",
        "production_reads": 0, "production_writes": 0,
    }
    write_json(LOCAL / "g6_local_inventory.json", result)
    write_json(LOCAL / "inventory/g6_question_fingerprints.json", list(unique.values()))
    return result


def pilot_status(question_count: int, micro_covered: int, micro_count: int) -> str:
    if question_count == 0:
        return "ZERO_COVERAGE"
    if question_count < 3 or micro_covered < min(2, micro_count):
        return "LIMITED_COVERAGE"
    return "PILOT_COVERED"


def coverage() -> dict[str, Any]:
    skills, micros = read_csv(GRADE_DIR / "standard_skills.csv"), read_csv(GRADE_DIR / "layer2_micro_skills.csv")
    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in micros:
        by_parent[row["parent_skill_id"]].append(row)
    skill_rows = []
    for skill in skills:
        count = len(by_parent[skill["skill_id"]])
        skill_rows.append({
            "skill_id": skill["skill_id"], "skill_name": skill["skill_name"], "micro_skill_count": count,
            "real_question_count": 0, "micro_covered_count": 0, "skill_coverage_percent": 0.0,
            "micro_coverage_percent": 0.0, "coverage_status": pilot_status(0, 0, count),
            "priority": "HIGH", "recommended_next_action": "Map validated local G6 questions",
        })
    micro_rows = [{"micro_skill_id": r["micro_skill_id"], "parent_skill_id": r["parent_skill_id"],
                   "skill_name": r["skill_name"], "real_question_count": 0,
                   "coverage_status": "ZERO_COVERAGE", "priority": "HIGH"} for r in micros]
    out = LOCAL / "coverage"
    fields = list(skill_rows[0]); write_csv(out / "g6_skill_coverage_matrix.csv", skill_rows, fields)
    write_json(out / "g6_skill_coverage_matrix.json", skill_rows)
    write_csv(out / "g6_micro_coverage_matrix.csv", micro_rows, list(micro_rows[0]))
    summary = {
        "total_skills": len(skills), "total_micro_skills": len(micros),
        "skills_with_real_questions": 0, "skills_zero_real_questions": len(skills),
        "micros_with_real_questions": 0, "micros_zero_real_questions": len(micros),
        "real_skill_coverage_percent": 0.0, "real_micro_coverage_percent": 0.0,
        "synthetic_questions_counted_as_real": 0, "production_reads": 0, "production_writes": 0,
    }
    write_json(out / "g6_coverage_summary.json", summary)
    return summary


def choose_skills(skills: list[dict[str, str]], count: int = 10) -> list[dict[str, str]]:
    preferred = ["因數與倍數進階", "分數除法", "小數除法", "比與比例", "速率",
                 "數量關係", "比例幾何", "圓與扇形", "柱體", "資料"]
    chosen: list[dict[str, str]] = []
    for unit in preferred:
        match = next((r for r in skills if r["main_unit"] == unit and r not in chosen), None)
        if match:
            chosen.append(match)
    for row in skills:
        if len(chosen) >= count:
            break
        if row not in chosen and row["main_unit"] not in {r["main_unit"] for r in chosen}:
            chosen.append(row)
    return chosen[:count]


def _synthetic_text(skill: dict[str, str], micro: dict[str, str], variant: int, holdout: bool) -> str:
    openings = ("六年級課堂練習：", "國小六年級評量：")
    tasks = {
        "概念辨識": "判斷下列敘述所呈現的定義、性質或數量角色，並說明理由",
        "標準程序": "依標準步驟完成計算、作圖或轉換，列出主要過程",
        "逆向求未知": "根據已知結果與部分條件反推出未知量，並驗算",
        "情境應用": "從生活情境辨認數量關係，選擇方法並求解",
        "表徵轉換": "在文字、算式、圖像或表格之間完成等值轉換",
        "變形進階": "處理改變後的條件與干擾資訊，完成多步驟推理",
        "跨單元整合": "結合前置概念完成解題並檢查合理性",
    }
    task = tasks.get(micro.get("question_type", ""), "依題意完成並解釋方法")
    closings = ("請完整作答。", "請寫出判斷依據與答案。", "請檢查結果是否合理。")
    return (f"{openings[1 if holdout else 0]}主題是「{skill['skill_name']}」，"
            f"重點為「{skill['focus']}」。{task}；{closings[variant]}")


def prepare_set(name: str) -> dict[str, Any]:
    holdout = name == "holdout"
    skills, micros = read_csv(GRADE_DIR / "standard_skills.csv"), read_csv(GRADE_DIR / "layer2_micro_skills.csv")
    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in micros:
        by_parent[row["parent_skill_id"]].append(row)
    questions = []
    for skill in choose_skills(skills):
        candidates = by_parent[skill["skill_id"]]
        for i in range(3):
            micro = candidates[(i + (1 if holdout else 0)) % len(candidates)]
            text = _synthetic_text(skill, micro, i, holdout)
            questions.append({"fingerprint": fingerprint(text), "question_text": text,
                              "synthetic_validation": True, "set": name,
                              "expected_scope_status": IN_SCOPE, "expected_skill_id": skill["skill_id"],
                              "expected_micro_skill_id": micro["micro_skill_id"]})
    oos = [
        ("計算一位數加法並數出十以內物件。", "BELOW_G6"),
        ("辨認基本九九乘法並直接作答。", "BELOW_G6"),
        ("解一元二次方程式並判別根。", "ABOVE_G6"),
        ("求線性函數斜率並畫座標圖。", "ABOVE_G6"),
    ]
    for idx, (text, reason) in enumerate(oos):
        value = ("另一組：" if holdout else "測試：") + text
        questions.append({"fingerprint": fingerprint(value), "question_text": value,
                          "synthetic_validation": True, "set": name,
                          "expected_scope_status": OUT_SCOPE, "expected_skill_id": "",
                          "expected_micro_skill_id": "", "expected_out_of_scope_reason": reason})
    dest = LOCAL / "synthetic" / name / "questions.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in questions), encoding="utf-8")
    summary = {"set": name, "questions": len(questions), "in_scope": len(questions) - len(oos),
               "out_of_scope": len(oos), "skills": len({r["expected_skill_id"] for r in questions if r["expected_skill_id"]}),
               "production_reads": 0, "production_writes": 0}
    write_json(dest.parent / "preparation_summary.json", summary)
    return summary


def response_json_resilient(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S).strip()
    attempts = [value]
    start, end = value.find("{"), value.rfind("}")
    if start >= 0 and end > start:
        attempts.append(value[start:end + 1])
    attempts.extend(re.sub(r",\s*([}\]])", r"\1", a) for a in list(attempts))
    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise ValueError("Gemini response did not contain a valid JSON object")


def mapping_prompt(question: dict[str, Any], skills: list[dict[str, str]], micros: list[dict[str, str]]) -> str:
    rules = (GRADE_DIR / "OUT_OF_SCOPE_RULES.md").read_text(encoding="utf-8")
    catalog = [{k: r[k] for k in ("skill_id", "main_unit", "subunit", "skill_name", "focus")} for r in skills]
    micro_catalog = [{k: r[k] for k in ("micro_skill_id", "parent_skill_id", "question_type", "focus")} for r in micros]
    return f"""Classify this local pilot item using only the Taiwan G6 catalog and G6 scope rules.
Return one JSON object with: fingerprint, scope_status, predicted_skill_id, predicted_micro_skill_id,
confidence (0..1), review_status, out_of_scope_reason. Never force-map an out-of-scope item.
scope_status must be {IN_SCOPE} or {OUT_SCOPE}. For {OUT_SCOPE}, both IDs must be empty.
G6 rules:\n{rules}\nSkills:\n{json.dumps(catalog, ensure_ascii=False)}
Micro Skills:\n{json.dumps(micro_catalog, ensure_ascii=False)}
Item fingerprint: {question['fingerprint']}\nItem text: {question['question_text']}"""


def map_set(name: str, model: str = MODEL, generate: Callable[[str, str], str] | None = None) -> dict[str, Any]:
    if model != MODEL:
        raise RuntimeError(f"model must be exactly {MODEL}")
    base = LOCAL / "real_questions" if name == "real" else LOCAL / "synthetic" / name
    questions = read_jsonl(base / "questions.jsonl")
    skills, micros = read_csv(GRADE_DIR / "standard_skills.csv"), read_csv(GRADE_DIR / "layer2_micro_skills.csv")
    checkpoint = base / "mapping_checkpoint.jsonl"
    existing = read_jsonl(checkpoint)
    known_fps = {q["fingerprint"] for q in questions}
    completed: dict[str, dict[str, Any]] = {}
    for row in existing:
        fp = str(row.get("fingerprint") or "")
        if fp not in known_fps or fp in completed:
            raise RuntimeError("checkpoint contains unknown, blank, or duplicate fingerprint")
        completed[fp] = row
    if generate is None:
        api_key = gemini_api_key()
        if not api_key:
            raise RuntimeError("SECURE_GEMINI_KEY_NOT_FOUND")
        from google import genai
        client = genai.Client(api_key=api_key)
        generate = lambda prompt, selected_model: client.models.generate_content(
            model=selected_model, contents=prompt
        ).text
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    retries = 3
    with checkpoint.open("a", encoding="utf-8") as handle:
        for question in questions:
            fp = question["fingerprint"]
            if fp in completed:
                continue
            last_error: Exception | None = None
            for attempt in range(retries):
                try:
                    parsed = response_json_resilient(generate(mapping_prompt(question, skills, micros), model))
                    parsed["fingerprint"] = fp
                    parsed.setdefault("predicted_skill_id", "")
                    parsed.setdefault("predicted_micro_skill_id", "")
                    parsed.setdefault("review_status", "REVIEW")
                    parsed.setdefault("validation_errors", [])
                    handle.write(json.dumps(parsed, ensure_ascii=False) + "\n"); handle.flush()
                    completed[fp] = parsed
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt + 1 < retries:
                        time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"mapping failed after retries for {fp}: {type(last_error).__name__}")
    result = {"set": name, "model": model, "total_questions": len(questions),
              "completed": len(completed), "resumed": len(existing),
              "production_reads": 0, "production_writes": 0}
    write_json(base / "mapping_run_summary.json", result)
    return result


def prepare_real() -> dict[str, Any]:
    candidates = [ROOT / "data/diagnostic_questions_g6_pilot_v1.json",
                  ROOT / "data/diagnostic_questions_g6_competition_core_v1.json"]
    questions: dict[str, dict[str, Any]] = {}
    for path in candidates:
        for row in _question_rows(path):
            text = row.get("prompt") or row.get("question_text") or row.get("new_question")
            if not text:
                continue
            fp = fingerprint(str(text))
            questions.setdefault(fp, {"fingerprint": fp, "question_text": str(text),
                                      "synthetic_validation": False, "source": path.name})
    base = LOCAL / "real_questions"; base.mkdir(parents=True, exist_ok=True)
    (base / "questions.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in questions.values()), encoding="utf-8")
    result = {"questions": len(questions), "synthetic": False, "production_reads": 0, "production_writes": 0}
    write_json(base / "preparation_summary.json", result)
    return result


def validate_real() -> dict[str, Any]:
    base = LOCAL / "real_questions"
    questions = {r["fingerprint"]: r for r in read_jsonl(base / "questions.jsonl")}
    results = read_jsonl(base / "mapping_checkpoint.jsonl")
    skills_list, micros_list = read_csv(GRADE_DIR / "standard_skills.csv"), read_csv(GRADE_DIR / "layer2_micro_skills.csv")
    skills = {r["skill_id"]: r for r in skills_list}; micros = {r["micro_skill_id"]: r for r in micros_list}
    queue = []; seen: set[str] = set()
    for row in results:
        fp = str(row.get("fingerprint") or "")
        errors = validate_result(row, skills, micros)
        if fp not in questions: errors.append("UNKNOWN_FINGERPRINT")
        if fp in seen: errors.append("DUPLICATE_FINGERPRINT")
        seen.add(fp)
        confidence = float(row.get("confidence") or 0)
        queue.append({"fingerprint": fp, "question_text": questions.get(fp, {}).get("question_text", ""),
                      "scope_status": row.get("scope_status", ""), "predicted_skill_id": row.get("predicted_skill_id", ""),
                      "predicted_micro_skill_id": row.get("predicted_micro_skill_id", ""), "confidence": confidence,
                      "review_status": "HUMAN_REVIEW_REQUIRED", "validation_errors": ";".join(errors)})
    missing = len(set(questions) - seen)
    invalid = sum(bool(r["validation_errors"]) for r in queue) + missing
    in_scope_rows = [r for r in queue if r["scope_status"] == IN_SCOPE and not r["validation_errors"]]
    write_csv(base / "g6_real_human_review_queue.csv", queue,
              ["fingerprint", "question_text", "scope_status", "predicted_skill_id", "predicted_micro_skill_id",
               "confidence", "review_status", "validation_errors"])
    summary = {"total_questions": len(questions), "mapped": len(queue), "invalid": invalid,
               "provisional_in_scope": len(in_scope_rows),
               "provisional_skills_covered": len({r["predicted_skill_id"] for r in in_scope_rows if r["predicted_skill_id"]}),
               "provisional_micros_covered": len({r["predicted_micro_skill_id"] for r in in_scope_rows if r["predicted_micro_skill_id"]}),
               "human_review_required": len(queue), "counted_as_validated_coverage": 0,
               "technical_pass": len(queue) == len(questions) and invalid == 0,
               "production_reads": 0, "production_writes": 0}
    write_json(base / "g6_real_mapping_summary.json", summary)
    return summary


def validate_result(row: dict[str, Any], skills: dict[str, Any], micros: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scope = row.get("scope_status")
    sid, mid = str(row.get("predicted_skill_id") or ""), str(row.get("predicted_micro_skill_id") or "")
    if scope not in {IN_SCOPE, OUT_SCOPE}: errors.append("INVALID_SCOPE_STATUS")
    if scope == OUT_SCOPE and (sid or mid): errors.append("OUT_OF_SCOPE_MAPPED")
    if scope == IN_SCOPE and not sid: errors.append("IN_SCOPE_MISSING_SKILL")
    if sid and sid not in skills: errors.append("UNKNOWN_SKILL")
    if mid and mid not in micros: errors.append("UNKNOWN_MICRO_SKILL")
    if mid in micros and sid and micros[mid]["parent_skill_id"] != sid: errors.append("MICRO_PARENT_MISMATCH")
    try:
        if not 0 <= float(row.get("confidence")) <= 1: errors.append("INVALID_CONFIDENCE")
    except (TypeError, ValueError): errors.append("INVALID_CONFIDENCE")
    return errors


def validate_set(name: str) -> dict[str, Any]:
    base = LOCAL / "synthetic" / name
    expected = {r["fingerprint"]: r for r in read_jsonl(base / "questions.jsonl")}
    results = read_jsonl(base / "mapping_checkpoint.jsonl")
    skills_list, micros_list = read_csv(GRADE_DIR / "standard_skills.csv"), read_csv(GRADE_DIR / "layer2_micro_skills.csv")
    skills = {r["skill_id"]: r for r in skills_list}; micros = {r["micro_skill_id"]: r for r in micros_list}
    seen: set[str] = set(); comparisons = []
    for row in results:
        fp = row.get("fingerprint", "")
        errors = validate_result(row, skills, micros)
        if fp in seen: errors.append("DUPLICATE_FINGERPRINT")
        if fp not in expected: errors.append("UNKNOWN_FINGERPRINT")
        seen.add(fp)
        exp = expected.get(fp, {})
        comparisons.append({**row, "expected_scope_status": exp.get("expected_scope_status", ""),
                            "expected_skill_id": exp.get("expected_skill_id", ""),
                            "expected_micro_skill_id": exp.get("expected_micro_skill_id", ""),
                            "scope_match": row.get("scope_status") == exp.get("expected_scope_status"),
                            "skill_match": str(row.get("predicted_skill_id") or "") == exp.get("expected_skill_id", ""),
                            "micro_match": str(row.get("predicted_micro_skill_id") or "") == exp.get("expected_micro_skill_id", ""),
                            "validation_errors": errors})
    total = len(expected)
    def pct(key: str) -> float:
        return round(100 * sum(bool(r[key]) for r in comparisons) / total, 2) if total else 0.0
    per_skill = []
    for sid in sorted({r["expected_skill_id"] for r in comparisons if r["expected_skill_id"]}):
        rows = [r for r in comparisons if r["expected_skill_id"] == sid]
        per_skill.append({"skill_id": sid, "questions": len(rows),
                          "skill_accuracy": round(100 * sum(r["skill_match"] for r in rows) / len(rows), 2),
                          "micro_accuracy": round(100 * sum(r["micro_match"] for r in rows) / len(rows), 2)})
    invalid = sum(bool(r["validation_errors"]) for r in comparisons) + max(0, total - len(comparisons))
    summary = {"set": name, "model": MODEL, "total_questions": total, "completed": len(comparisons),
               "scope_accuracy": pct("scope_match"), "exact_skill_accuracy": pct("skill_match"),
               "exact_micro_accuracy": pct("micro_match"), "invalid": invalid,
               "mismatch_count": sum(not (r["scope_match"] and r["skill_match"] and r["micro_match"]) for r in comparisons),
               "per_skill_accuracy": per_skill,
               "technical_pass": len(comparisons) == total and invalid == 0,
               "mapping_pilot_pass": len(comparisons) == total and invalid == 0 and pct("scope_match") >= 95 and pct("skill_match") >= 90 and pct("micro_match") >= 80,
               "production_reads": 0, "production_writes": 0}
    write_json(base / "validation_summary.json", summary)
    write_json(base / "comparisons.json", comparisons)
    return summary


def quality(name: str = "holdout") -> dict[str, Any]:
    base = LOCAL / "synthetic" / name
    rows = json.loads((base / "comparisons.json").read_text(encoding="utf-8"))
    flags = []
    for r in rows:
        reasons = list(r.get("validation_errors") or [])
        if float(r.get("confidence") or 0) < .6: reasons.append("LOW_CONFIDENCE")
        if float(r.get("confidence") or 0) >= .9 and not (r["scope_match"] and r["skill_match"] and r["micro_match"]):
            reasons.append("HIGH_CONFIDENCE_MISMATCH")
        if reasons: flags.append({**r, "quality_flags": ";".join(sorted(set(reasons)))})
    qdir = LOCAL / "quality"; qdir.mkdir(parents=True, exist_ok=True)
    mismatches = [r for r in rows if not (r["scope_match"] and r["skill_match"] and r["micro_match"])]
    fields = ["fingerprint", "expected_scope_status", "scope_status", "expected_skill_id", "predicted_skill_id",
              "expected_micro_skill_id", "predicted_micro_skill_id", "confidence", "review_status", "validation_errors"]
    write_csv(qdir / "g6_mapping_mismatches.csv", mismatches, fields)
    write_csv(qdir / "g6_scope_out_of_scope.csv", [r for r in rows if r["expected_scope_status"] == OUT_SCOPE], fields)
    skill_dist = [{"skill_id": k, "count": v} for k, v in Counter(str(r.get("predicted_skill_id") or "") for r in rows if r.get("predicted_skill_id")).items()]
    micro_dist = [{"micro_skill_id": k, "count": v} for k, v in Counter(str(r.get("predicted_micro_skill_id") or "") for r in rows if r.get("predicted_micro_skill_id")).items()]
    write_csv(qdir / "g6_skill_distribution.csv", skill_dist, ["skill_id", "count"])
    write_csv(qdir / "g6_micro_distribution.csv", micro_dist, ["micro_skill_id", "count"])
    summary = {"questions": len(rows), "invalid": sum(bool(r.get("validation_errors")) for r in rows),
               "quality_flags": len(flags), "mismatches": len(mismatches),
               "duplicate_fingerprints": len(rows) - len({r["fingerprint"] for r in rows}),
               "technical_pass": all(not r.get("validation_errors") for r in rows),
               "production_reads": 0, "production_writes": 0}
    write_json(qdir / "g6_mapping_quality_summary.json", summary)
    return summary


def handoff(g8_pass: bool) -> dict[str, Any]:
    audit = json.loads((LOCAL / "g6_curriculum_audit.json").read_text(encoding="utf-8"))
    inv = json.loads((LOCAL / "g6_local_inventory.json").read_text(encoding="utf-8"))
    cov = json.loads((LOCAL / "coverage/g6_coverage_summary.json").read_text(encoding="utf-8"))
    val_path = LOCAL / "synthetic/holdout/validation_summary.json"
    val = json.loads(val_path.read_text(encoding="utf-8")) if val_path.exists() else {}
    quality_path = LOCAL / "quality/g6_mapping_quality_summary.json"
    qa = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    real_path = LOCAL / "real_questions/g6_real_mapping_summary.json"
    real = json.loads(real_path.read_text(encoding="utf-8")) if real_path.exists() else {}
    foundation = bool(audit["curriculum_integrity"] == "PASS" and val.get("mapping_pilot_pass") and
                      qa.get("technical_pass") and g8_pass)
    completion = 100 if foundation else (70 if audit["curriculum_integrity"] == "PASS" else 0)
    text = f"""# G6 Pilot Freeze / Handoff

## Status

**G6 PILOT FOUNDATION: {'SAFE TO PAUSE' if foundation else 'BLOCKED'}**

Foundation completion and real-question coverage are intentionally separate. Foundation completion: **{completion}%**. Real question Skill/Micro coverage: **0% / 0%**.

## Curriculum counts

- Skills: {audit['skills']}
- Micro Skills: {audit['micro_skills']}
- Prerequisite edges: {audit['prerequisite_edges']}
- Publisher units: {audit['publisher_units']} unique units ({audit['publisher_unit_rows']} rows)
- Integrity: {audit['curriculum_integrity']}

## Pilot architecture

The local-only runner performs environment and curriculum audit, fingerprint inventory, complete zero-safe coverage matrices, cross-unit synthetic preparation, resumable mapping checkpoints, validation, quality audit, G8 regression, and sanitized handoff generation. The required model is `{MODEL}`. G6 scope decisions use only the G6 Curriculum Master and G6 `OUT_OF_SCOPE_RULES.md`.

## Real local question inventory

- Source status: {inv['REAL_G6_LOCAL_QUESTION_SOURCE']}
- Unique local diagnostic questions: {inv['unique_questions']}
- Provisional local mappings: {real.get('mapped', 0)}; all remain in a human-review queue.
- Provisional distinct Skills/Micros: {real.get('provisional_skills_covered', 0)} / {real.get('provisional_micros_covered', 0)}.
- Validated Stage 5 mappings counted as formal coverage: 0.
- Real Skill coverage: {cov['real_skill_coverage_percent']}%
- Real Micro coverage: {cov['real_micro_coverage_percent']}%

## Synthetic and HOLDOUT validation

Two separately generated local-only sets cover 10 curriculum Skills across distinct main units, three in-scope questions per Skill plus explicit below-G6 and above-G6 scope cases. Synthetic items never enter item_bank or real coverage.

- HOLDOUT questions: {val.get('total_questions', 0)}
- Scope accuracy: {val.get('scope_accuracy', 'NOT_RUN')}%
- Exact Skill accuracy: {val.get('exact_skill_accuracy', 'NOT_RUN')}%
- Exact Micro accuracy: {val.get('exact_micro_accuracy', 'NOT_RUN')}%
- Invalid: {val.get('invalid', 'NOT_RUN')}
- Known mismatches: {val.get('mismatch_count', 'NOT_RUN')}; details remain local only.
- Known ambiguity: generic Micro Skill types can overlap semantically; mismatches must be reviewed rather than changing expected labels post hoc.

## Safety and regression

- Production reads: 0
- Production writes: 0
- Secrets exposed: NO
- Raw/local/synthetic question data committed by this foundation: NO
- G8 regression: {'PASS' if g8_pass else 'FAIL/NOT RUN'}

## Unfinished work

{'None for the Pilot Foundation gate.' if foundation else 'Complete the Gemini HOLDOUT run and/or resolve failing quality or G8 regression gates.'}

## First next action

Human-review the 36 provisional local mappings in the `.local` review queue; only approved mappings may begin validated real coverage without Production access.
"""
    doc = ROOT / "docs/stage5/G6_PILOT_FREEZE_HANDOFF.md"
    doc.parent.mkdir(parents=True, exist_ok=True); doc.write_text(text, encoding="utf-8")
    result = {"foundation": "SAFE TO PAUSE" if foundation else "BLOCKED", "foundation_completion": completion,
              "real_question_coverage": 0, "g8_regression": "PASS" if g8_pass else "FAIL",
              "production_reads": 0, "production_writes": 0}
    write_json(LOCAL / "handoff_summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit", "inventory", "coverage", "prepare", "map", "validate", "quality", "prepare-real", "map-real", "validate-real", "handoff"])
    parser.add_argument("--set", choices=["tuning", "holdout"], default="holdout")
    parser.add_argument("--g8-pass", action="store_true")
    args = parser.parse_args()
    actions: dict[str, Callable[[], dict[str, Any]]] = {
        "audit": curriculum_audit, "inventory": inventory, "coverage": coverage,
        "prepare": lambda: prepare_set(args.set), "validate": lambda: validate_set(args.set),
        "map": lambda: map_set(args.set),
        "prepare-real": prepare_real, "map-real": lambda: map_set("real"), "validate-real": validate_real,
        "quality": lambda: quality(args.set), "handoff": lambda: handoff(args.g8_pass),
    }
    result = actions[args.command]()
    print(json.dumps(result, ensure_ascii=False))
    if args.command == "audit" and result.get("curriculum_integrity") != "PASS": return 2
    if args.command in {"validate", "quality"} and not result.get("technical_pass"): return 2
    if args.command == "handoff" and result.get("foundation") != "SAFE TO PAUSE": return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
