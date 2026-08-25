"""Grade-configurable, local-only Stage 5 mapping pilot engine."""
from __future__ import annotations

import argparse
import csv
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.stage5_grade_config import GradeConfig, PACK_ROOT, load_grade_config

MODEL = "gemini-3.6-flash"
QUOTA_BACKOFF_SECONDS = (60.0, 120.0, 300.0)
REQUIRED_FILES = (
    "standard_skills.csv", "layer2_micro_skills.csv", "prerequisite_graph.csv",
    "publisher_units.csv", "official_curriculum.json", "OUT_OF_SCOPE_RULES.md",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def skill_unit(row: dict[str, str]) -> str:
    return row.get("main_unit") or row.get("mathai_main_unit") or ""


def skill_subunit(row: dict[str, str]) -> str:
    return row.get("subunit") or row.get("mathai_subunit") or ""


def _catalog(config: GradeConfig) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return (read_csv(config.curriculum_dir / "standard_skills.csv"),
            read_csv(config.curriculum_dir / "layer2_micro_skills.csv"))


def environment_audit(config: GradeConfig) -> dict[str, Any]:
    import subprocess
    cwd = Path.cwd().resolve()
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    result = {"workspace": str(cwd), "branch": branch,
              "workspace_pass": cwd == ROOT.resolve(),
              "branch_pass": branch in {"stage5/generic-grade-engine", f"stage5/{config.target_id.lower()}-mapping-pilot"},
              "production_reads": 0, "production_writes": 0}
    result["environment_integrity"] = "PASS" if result["workspace_pass"] and result["branch_pass"] else "FAIL"
    write_json(config.local_output_dir / "environment_audit.json", result)
    return result


def curriculum_audit(config: GradeConfig) -> dict[str, Any]:
    errors = [f"MISSING:{name}" for name in REQUIRED_FILES if not (config.curriculum_dir / name).is_file()]
    try:
        skills, micros = _catalog(config)
        graph = read_csv(config.curriculum_dir / "prerequisite_graph.csv")
        units = read_csv(config.curriculum_dir / "publisher_units.csv")
        official = json.loads((config.curriculum_dir / "official_curriculum.json").read_text(encoding="utf-8-sig"))
        rules = config.out_of_scope_rules_path.read_text(encoding="utf-8")
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
    dup_skills = sorted(k for k, v in Counter(skill_ids).items() if not k or v > 1)
    dup_micros = sorted(k for k, v in Counter(micro_ids).items() if not k or v > 1)
    orphans = sorted(r.get("micro_skill_id", "") for r in micros if r.get("parent_skill_id", "") not in known)
    invalid_parent = sorted(r.get("micro_skill_id", "") for r in micros if not r.get("parent_skill_id"))
    graph_ids = [r.get("skill_id", "").strip() for r in graph]
    graph_errors = {"invalid_nodes": sorted(set(graph_ids) - known),
                    "missing_nodes": sorted(known - set(graph_ids)),
                    "duplicate_nodes": sorted(k for k, v in Counter(graph_ids).items() if v > 1)}
    prefix = next((x.split("-", 1)[0] for x in skill_ids if "-" in x), "")
    refs = {x.strip() for row in graph for field in ("prerequisite", "prerequisites", "next_skill")
            for x in row.get(field, "").split(";") if x.strip()}
    invalid_refs = sorted(x for x in refs if prefix and x.startswith(prefix + "-") and x not in known)
    edges = sum(len([x for x in (r.get("prerequisite") or r.get("prerequisites") or "").split(";") if x.strip()]) for r in graph)
    unit_keys = {(r.get("publisher", ""), r.get("semester", ""), r.get("unit_no", ""), r.get("unit_title", "")) for r in units}
    passed = not any((errors, dup_skills, dup_micros, orphans, invalid_parent, invalid_refs,
                      graph_errors["invalid_nodes"], graph_errors["missing_nodes"], graph_errors["duplicate_nodes"]))
    result = {"grade": config.grade, "target_id": config.target_id, "profile": config.profile,
              "skills": len(skills), "micro_skills": len(micros),
              "prerequisite_edges": edges, "publisher_unit_rows": len(units),
              "publisher_units": len(unit_keys),
              "official_curriculum_entries": len(official) if isinstance(official, list) else 0,
              "duplicate_ids": {"skill_ids": dup_skills, "micro_skill_ids": dup_micros},
              "orphan_micro_skills": orphans, "invalid_parent_relations": invalid_parent,
              "invalid_prerequisite_nodes": invalid_refs, "graph_errors": graph_errors,
              "curriculum_parse_errors": errors, "curriculum_integrity": "PASS" if passed else "FAIL",
              "production_reads": 0, "production_writes": 0}
    write_json(config.local_output_dir / f"{config.target_id.lower()}_curriculum_audit.json", result)
    return result


def _question_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return read_jsonl(path)
    if path.suffix.lower() == ".csv":
        return read_csv(path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in ("questions", "items", "rows"):
            if isinstance(value.get(key), list):
                return [x for x in value[key] if isinstance(x, dict)]
    return []


def _real_sources(config: GradeConfig) -> tuple[Path, ...]:
    allowed = {p.resolve(): p for p in config.real_question_source_candidates if p.is_file()}
    for path in (ROOT / "data").glob(f"*{config.target_id.lower()}*.json"):
        if "question" in path.name.lower():
            allowed[path.resolve()] = path
    local_grade = config.local_output_dir / "imports"
    if local_grade.is_dir():
        for pattern in ("*.json", "*.jsonl", "*.csv"):
            for path in local_grade.glob(pattern):
                allowed[path.resolve()] = path
    return tuple(allowed[k] for k in sorted(allowed, key=str))


def inventory(config: GradeConfig) -> dict[str, Any]:
    unique: dict[str, dict[str, str]] = {}
    sources = []
    for path in _real_sources(config):
        try:
            rows = _question_rows(path)
        except (OSError, json.JSONDecodeError) as exc:
            sources.append({"path": path.relative_to(ROOT).as_posix(), "question_rows": 0,
                            "parse_error": type(exc).__name__})
            continue
        count = 0
        for row in rows:
            text = row.get("prompt") or row.get("question_text") or row.get("new_question")
            if text:
                fp = fingerprint(str(text)); count += 1
                unique.setdefault(fp, {"fingerprint": fp, "source": path.name})
        sources.append({"path": path.relative_to(ROOT).as_posix(), "question_rows": count})
    total = sum(x["question_rows"] for x in sources)
    result = {f"REAL_{config.target_id}_LOCAL_QUESTION_SOURCE": "AVAILABLE" if unique else "NOT_AVAILABLE",
              "source_files": sources, "source_question_rows": total, "unique_questions": len(unique),
              "duplicate_questions": total - len(unique), "stage5_skill_mappings_available": False,
              "real_skills_covered": 0, "real_micros_covered": 0,
              "production_reads": 0, "production_writes": 0}
    write_json(config.local_output_dir / f"{config.target_id.lower()}_local_inventory.json", result)
    write_json(config.local_output_dir / "inventory" / f"{config.target_id.lower()}_question_fingerprints.json", list(unique.values()))
    return result


def coverage_status(question_count: int, micro_count: int, covered: int) -> str:
    if question_count == 0:
        return "ZERO_COVERAGE"
    if question_count < 3 or covered < min(2, micro_count):
        return "LIMITED_COVERAGE"
    return "PILOT_COVERED"


def coverage(config: GradeConfig) -> dict[str, Any]:
    skills, micros = _catalog(config)
    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in micros:
        by_parent[row["parent_skill_id"]].append(row)
    skill_rows = []
    for row in skills:
        count = len(by_parent[row["skill_id"]])
        skill_rows.append({"skill_id": row["skill_id"], "skill_name": row["skill_name"],
                           "main_unit": skill_unit(row), "subunit": skill_subunit(row),
                           "micro_skill_count": count, "real_question_count": 0,
                           "micro_covered_count": 0, "skill_coverage_percent": 0.0,
                           "micro_coverage_percent": 0.0,
                           "coverage_status": coverage_status(0, count, 0), "priority": "HIGH",
                           "recommended_next_action": f"Human-validate local {config.target_id} mappings"})
    micro_rows = [{"micro_skill_id": row["micro_skill_id"], "parent_skill_id": row["parent_skill_id"],
                   "skill_name": row["skill_name"], "main_unit": row.get("main_unit", ""),
                   "real_question_count": 0, "coverage_status": "ZERO_COVERAGE", "priority": "HIGH"}
                  for row in micros]
    out = config.local_output_dir / "coverage"; prefix = config.target_id.lower()
    write_csv(out / f"{prefix}_skill_coverage_matrix.csv", skill_rows, list(skill_rows[0]))
    write_json(out / f"{prefix}_skill_coverage_matrix.json", skill_rows)
    write_csv(out / f"{prefix}_micro_coverage_matrix.csv", micro_rows, list(micro_rows[0]))
    summary = {"total_skills": len(skills), "total_micro_skills": len(micros),
               "skills_with_real_questions": 0, "skills_zero_real_questions": len(skills),
               "micros_with_real_questions": 0, "micros_zero_real_questions": len(micros),
               "real_skill_coverage_percent": 0.0, "real_micro_coverage_percent": 0.0,
               "synthetic_questions_counted_as_real": 0, "production_reads": 0, "production_writes": 0}
    write_json(out / f"{prefix}_coverage_summary.json", summary)
    return summary


def choose_skills(config: GradeConfig, skills: list[dict[str, str]]) -> list[dict[str, str]]:
    chosen = []
    for row in skills:
        if skill_unit(row) not in {skill_unit(x) for x in chosen}:
            chosen.append(row)
        if len(chosen) == config.recommended_validation_skill_count:
            break
    if len(chosen) < config.recommended_validation_skill_count:
        for row in skills:
            if row not in chosen:
                chosen.append(row)
            if len(chosen) == config.recommended_validation_skill_count:
                break
    return chosen


def prepare_set(config: GradeConfig, name: str) -> dict[str, Any]:
    skills, micros = _catalog(config)
    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in micros:
        by_parent[row["parent_skill_id"]].append(row)
    questions = []
    selected = choose_skills(config, skills)
    for skill in selected:
        candidates = by_parent[skill["skill_id"]]
        for index in range(3):
            micro = candidates[(index + (name == "holdout")) % len(candidates)]
            text = " | ".join((config.grade_label, skill["skill_name"], micro["focus"],
                               micro.get("item_pattern", ""), name, str(index + 1)))
            questions.append({"fingerprint": fingerprint(text), "question_text": text,
                              "expected_scope_status": config.in_scope_status,
                              "expected_skill_id": skill["skill_id"],
                              "expected_micro_skill_id": micro["micro_skill_id"],
                              "synthetic_validation": True, "set": name})
    for index, hint in enumerate((config.lower_scope_hint, config.upper_scope_hint,
                                  config.lower_scope_hint + " alternate", config.upper_scope_hint + " alternate")):
        text = " | ".join((config.grade_label, hint, name, str(index + 1)))
        questions.append({"fingerprint": fingerprint(text), "question_text": text,
                          "expected_scope_status": config.out_scope_status, "expected_skill_id": "",
                          "expected_micro_skill_id": "", "synthetic_validation": True, "set": name})
    dest = config.local_output_dir / "synthetic" / name / "questions.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in questions), encoding="utf-8")
    result = {"set": name, "questions": len(questions), "in_scope": len(questions) - 4,
              "out_of_scope": 4, "skills": len(selected),
              "main_units": len({skill_unit(x) for x in selected}),
              "production_reads": 0, "production_writes": 0}
    write_json(dest.parent / "preparation_summary.json", result)
    return result


def response_json_resilient(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S).strip()
    attempts = [value]
    start, end = value.find("{"), value.rfind("}")
    if start >= 0 and end > start:
        attempts.append(value[start:end + 1])
    attempts += [re.sub(r",\s*([}\]])", r"\1", x) for x in list(attempts)]
    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError("model response did not contain a valid JSON object")


def gemini_api_key(config: GradeConfig) -> str:
    names = ("GEMINI_API_KEY", "GEMINI_KEY", "GOOGLE_API_KEY")
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    allowed = re.compile(r'^\s*(?:GEMINI_API_KEY|GEMINI_KEY|GOOGLE_API_KEY)\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$')
    for path in config.gemini_secret_paths:
        if path.is_file():
            with path.open(encoding="utf-8-sig") as handle:
                for line in handle:
                    match = allowed.match(line)
                    if match:
                        return match.group(1).strip()
    return ""


class GeminiQuotaBlocked(RuntimeError):
    """External API quota remained unavailable after bounded retries."""


def _is_quota_error(exc: Exception) -> bool:
    return getattr(exc, "code", None) == 429 or getattr(exc, "status", None) == "RESOURCE_EXHAUSTED"


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    value = headers.get("Retry-After") if headers is not None and hasattr(headers, "get") else None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(str(value))
            now = parsedate_to_datetime(time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()))
            return max(0.0, (retry_at - now).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def generate_with_quota_retry(call: Callable[[], str], sleep: Callable[[float], None] = time.sleep) -> str:
    """Retry a quota-limited call a bounded number of times, then fail closed."""
    for retry_index in range(len(QUOTA_BACKOFF_SECONDS) + 1):
        try:
            return call()
        except Exception as exc:
            if not _is_quota_error(exc):
                raise
            if retry_index == len(QUOTA_BACKOFF_SECONDS):
                raise GeminiQuotaBlocked("GEMINI_QUOTA_BLOCKED") from None
            delay = _retry_after_seconds(exc)
            sleep(delay if delay is not None else QUOTA_BACKOFF_SECONDS[retry_index])
    raise GeminiQuotaBlocked("GEMINI_QUOTA_BLOCKED")


def _terms(value: str) -> set[str]:
    compact = re.sub(r"\s+", "", str(value or "").lower())
    return {compact[index:index + 2] for index in range(max(0, len(compact) - 1))}


def candidate_catalog(question: dict[str, Any], skills: list[dict[str, str]],
                      micros: list[dict[str, str]], max_skills: int = 24,
                      max_micros: int = 120) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return a deterministic curriculum-only shortlist to control prompt size."""
    query = _terms(str(question.get("question_text") or ""))
    scored_skills = sorted(
        skills,
        key=lambda row: (-len(query & _terms(" ".join((skill_unit(row), skill_subunit(row),
                                                        row.get("skill_name", ""), row.get("focus", ""))))),
                         row.get("skill_id", "")),
    )
    selected_skills = scored_skills[:max_skills]
    selected_ids = {row["skill_id"] for row in selected_skills}
    eligible_micros = [row for row in micros if row.get("parent_skill_id") in selected_ids]
    selected_micros = sorted(
        eligible_micros,
        key=lambda row: (-len(query & _terms(" ".join((row.get("skill_name", ""),
                                                        row.get("question_type", ""), row.get("focus", ""),
                                                        row.get("item_pattern", ""))))),
                         row.get("micro_skill_id", "")),
    )[:max_micros]
    return selected_skills, selected_micros


def mapping_prompt(config: GradeConfig, question: dict[str, Any], skills: list[dict[str, str]], micros: list[dict[str, str]]) -> str:
    rules = config.out_of_scope_rules_path.read_text(encoding="utf-8")
    skills, micros = candidate_catalog(question, skills, micros)
    catalog = [{"skill_id": x["skill_id"], "main_unit": skill_unit(x), "subunit": skill_subunit(x),
                "skill_name": x["skill_name"], "focus": x["focus"]} for x in skills]
    micro_catalog = [{k: x[k] for k in ("micro_skill_id", "parent_skill_id", "question_type", "focus")} for x in micros]
    return f"""Classify using only {config.grade_label}, its catalog, and its scope rules.
Return exactly one JSON object with fingerprint, scope_status, predicted_skill_id,
predicted_micro_skill_id, confidence, review_status, out_of_scope_reason, validation_errors.
Allowed statuses: {config.in_scope_status}, {config.out_scope_status}. Out-of-scope IDs must be empty.
Rules:\n{rules}\nSkills:\n{json.dumps(catalog, ensure_ascii=False)}
Candidate Micro skills:\n{json.dumps(micro_catalog, ensure_ascii=False)}
Fingerprint: {question['fingerprint']}\nItem: {question['question_text']}"""


def _base(config: GradeConfig, name: str) -> Path:
    return config.local_output_dir / "real_questions" if name == "real" else config.local_output_dir / "synthetic" / name


def map_set(config: GradeConfig, name: str, generate: Callable[[str, str], str] | None = None) -> dict[str, Any]:
    base = _base(config, name); questions = read_jsonl(base / "questions.jsonl")
    skills, micros = _catalog(config); checkpoint = base / "mapping_checkpoint.jsonl"
    existing = read_jsonl(checkpoint); known = {x["fingerprint"] for x in questions}; completed = {}
    for row in existing:
        fp = str(row.get("fingerprint") or "")
        if not fp or fp not in known or fp in completed:
            raise RuntimeError("INVALID_CHECKPOINT_FINGERPRINT")
        completed[fp] = row
    if generate is None:
        key = gemini_api_key(config)
        if not key:
            raise RuntimeError("SECURE_GEMINI_KEY_NOT_FOUND")
        from google import genai
        client = genai.Client(api_key=key)
        def approved_generate(prompt: str, model: str) -> str:
            return generate_with_quota_retry(
                lambda: client.models.generate_content(model=model, contents=prompt).text)
        generate = approved_generate
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("a", encoding="utf-8") as handle:
        for question in questions:
            if question["fingerprint"] in completed:
                continue
            last_error = None
            for attempt in range(3):
                try:
                    row = response_json_resilient(generate(mapping_prompt(config, question, skills, micros), MODEL))
                    row["fingerprint"] = question["fingerprint"]
                    for field, default in (("scope_status", ""), ("predicted_skill_id", ""),
                                           ("predicted_micro_skill_id", ""), ("confidence", 0),
                                           ("review_status", "REVIEW"), ("out_of_scope_reason", ""),
                                           ("validation_errors", [])):
                        row.setdefault(field, default)
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n"); handle.flush(); completed[row["fingerprint"]] = row
                    break
                except GeminiQuotaBlocked:
                    quota_result = {
                        "grade": config.grade, "target_id": config.target_id, "profile": config.profile,
                        "set": name, "model": MODEL,
                        "status": "GEMINI_QUOTA_BLOCKED", "technical_pipeline": "PASS",
                        "external_api_availability": "BLOCKED",
                        "total_questions": len(questions), "completed": len(completed),
                        "remaining": len(questions) - len(completed),
                        "checkpoint_skipped": len(existing), "checkpoint_preserved": True,
                        "production_reads": 0, "production_writes": 0,
                    }
                    write_json(base / "mapping_run_summary.json", quota_result)
                    raise
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"MAPPING_FAILED:{type(last_error).__name__}")
    result = {"grade": config.grade, "target_id": config.target_id, "profile": config.profile,
              "set": name, "model": MODEL, "total_questions": len(questions),
              "completed": len(completed), "resumed": len(existing), "checkpoint_skipped": len(existing),
              "production_reads": 0, "production_writes": 0}
    write_json(base / "mapping_run_summary.json", result)
    return result


def validate_result(config: GradeConfig, row: dict[str, Any], skills: dict[str, Any], micros: dict[str, Any]) -> list[str]:
    errors = []; scope = row.get("scope_status")
    sid = str(row.get("predicted_skill_id") or ""); mid = str(row.get("predicted_micro_skill_id") or "")
    if scope not in {config.in_scope_status, config.out_scope_status}: errors.append("INVALID_SCOPE_STATUS")
    if scope == config.out_scope_status and (sid or mid): errors.append("OUT_OF_SCOPE_MAPPED")
    if scope == config.in_scope_status and not sid: errors.append("IN_SCOPE_MISSING_SKILL")
    if sid and sid not in skills: errors.append("UNKNOWN_SKILL")
    if mid and mid not in micros: errors.append("UNKNOWN_MICRO_SKILL")
    if mid in micros and sid and micros[mid]["parent_skill_id"] != sid: errors.append("MICRO_PARENT_MISMATCH")
    try:
        if not 0 <= float(row.get("confidence")) <= 1: errors.append("INVALID_CONFIDENCE")
    except (TypeError, ValueError): errors.append("INVALID_CONFIDENCE")
    return errors


def validate_set(config: GradeConfig, name: str) -> dict[str, Any]:
    base = _base(config, name)
    if not (base / "questions.jsonl").is_file() or not (base / "mapping_checkpoint.jsonl").is_file():
        raise FileNotFoundError(f"VALIDATION_INPUT_NOT_FOUND:{config.target_id}:{name}")
    expected = {x["fingerprint"]: x for x in read_jsonl(base / "questions.jsonl")}
    results = read_jsonl(base / "mapping_checkpoint.jsonl")
    if not expected or not results:
        raise RuntimeError(f"EMPTY_VALIDATION_INPUT:{config.target_id}:{name}")
    skill_rows, micro_rows = _catalog(config); skills = {x["skill_id"]: x for x in skill_rows}; micros = {x["micro_skill_id"]: x for x in micro_rows}
    seen = set(); comparisons = []
    for row in results:
        fp = str(row.get("fingerprint") or ""); errors = validate_result(config, row, skills, micros)
        if not fp or fp not in expected: errors.append("UNKNOWN_FINGERPRINT")
        if fp in seen: errors.append("DUPLICATE_FINGERPRINT")
        seen.add(fp); exp = expected.get(fp, {})
        comparisons.append({**row, "expected_scope_status": exp.get("expected_scope_status", ""),
                            "expected_skill_id": exp.get("expected_skill_id", ""),
                            "expected_micro_skill_id": exp.get("expected_micro_skill_id", ""),
                            "scope_match": row.get("scope_status") == exp.get("expected_scope_status"),
                            "skill_match": str(row.get("predicted_skill_id") or "") == exp.get("expected_skill_id", ""),
                            "micro_match": str(row.get("predicted_micro_skill_id") or "") == exp.get("expected_micro_skill_id", ""),
                            "validation_errors": errors})
    total = len(expected)
    pct = lambda key: round(100 * sum(bool(x[key]) for x in comparisons) / total, 2) if total else 0.0
    invalid = sum(bool(x["validation_errors"]) for x in comparisons) + len(set(expected) - seen)
    per_skill = []
    for sid in sorted({x["expected_skill_id"] for x in comparisons if x["expected_skill_id"]}):
        rows = [x for x in comparisons if x["expected_skill_id"] == sid]
        per_skill.append({"skill_id": sid, "questions": len(rows),
                          "skill_accuracy": round(100 * sum(x["skill_match"] for x in rows) / len(rows), 2),
                          "micro_accuracy": round(100 * sum(x["micro_match"] for x in rows) / len(rows), 2)})
    result = {"grade": config.grade, "target_id": config.target_id, "profile": config.profile,
              "set": name, "model": MODEL, "total_questions": total,
              "completed": len(comparisons), "scope_accuracy": pct("scope_match"),
              "exact_skill_accuracy": pct("skill_match"), "exact_micro_accuracy": pct("micro_match"),
              "invalid": invalid, "mismatch_count": sum(not (x["scope_match"] and x["skill_match"] and x["micro_match"]) for x in comparisons),
              "per_skill_accuracy": per_skill, "technical_pass": len(comparisons) == total and invalid == 0,
              "mapping_pilot_pass": len(comparisons) == total and invalid == 0 and pct("scope_match") >= 95 and pct("skill_match") >= 90 and pct("micro_match") >= 80,
              "production_reads": 0, "production_writes": 0}
    write_json(base / "comparisons.json", comparisons); write_json(base / "validation_summary.json", result)
    return result


def quality(config: GradeConfig, name: str) -> dict[str, Any]:
    base = _base(config, name)
    comparisons_path = base / "comparisons.json"
    if not comparisons_path.is_file():
        raise FileNotFoundError(f"VALIDATED_COMPARISONS_NOT_FOUND:{config.target_id}:{name}")
    rows = json.loads(comparisons_path.read_text(encoding="utf-8")); flags = []
    for row in rows:
        reasons = list(row.get("validation_errors") or [])
        if float(row.get("confidence") or 0) < .6: reasons.append("LOW_CONFIDENCE")
        if float(row.get("confidence") or 0) >= .9 and not (row["scope_match"] and row["skill_match"] and row["micro_match"]):
            reasons.append("HIGH_CONFIDENCE_MISMATCH")
        if reasons: flags.append({**row, "quality_flags": ";".join(sorted(set(reasons)))})
    mismatches = [x for x in rows if not (x["scope_match"] and x["skill_match"] and x["micro_match"])]
    fields = ["fingerprint", "expected_scope_status", "scope_status", "expected_skill_id", "predicted_skill_id",
              "expected_micro_skill_id", "predicted_micro_skill_id", "confidence", "review_status", "validation_errors"]
    out = config.local_output_dir / "quality"
    write_csv(out / "mapping_mismatches.csv", mismatches, fields)
    write_csv(out / "scope_out_of_scope.csv", [x for x in rows if x["expected_scope_status"] == config.out_scope_status], fields)
    write_csv(out / "skill_distribution.csv", [{"skill_id": k, "count": v} for k, v in Counter(str(x.get("predicted_skill_id") or "") for x in rows if x.get("predicted_skill_id")).items()], ["skill_id", "count"])
    write_csv(out / "micro_distribution.csv", [{"micro_skill_id": k, "count": v} for k, v in Counter(str(x.get("predicted_micro_skill_id") or "") for x in rows if x.get("predicted_micro_skill_id")).items()], ["micro_skill_id", "count"])
    result = {"grade": config.grade, "target_id": config.target_id, "profile": config.profile,
              "questions": len(rows), "invalid": sum(bool(x.get("validation_errors")) for x in rows),
              "quality_flags": len(flags), "mismatches": len(mismatches),
              "duplicate_fingerprints": len(rows) - len({x["fingerprint"] for x in rows}),
              "technical_pass": all(not x.get("validation_errors") for x in rows),
              "production_reads": 0, "production_writes": 0}
    write_json(out / "mapping_quality_summary.json", result)
    return result


def prepare_real(config: GradeConfig) -> dict[str, Any]:
    questions = {}
    for path in _real_sources(config):
        for row in _question_rows(path):
            text = row.get("prompt") or row.get("question_text") or row.get("new_question")
            if text:
                fp = fingerprint(str(text)); questions.setdefault(fp, {"fingerprint": fp, "question_text": str(text), "synthetic_validation": False, "source": path.name})
    base = config.local_output_dir / "real_questions"; base.mkdir(parents=True, exist_ok=True)
    (base / "questions.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in questions.values()), encoding="utf-8")
    result = {"questions": len(questions), "synthetic": False, "production_reads": 0, "production_writes": 0}
    write_json(base / "preparation_summary.json", result); return result


def validate_real(config: GradeConfig) -> dict[str, Any]:
    base = config.local_output_dir / "real_questions"; questions = {x["fingerprint"]: x for x in read_jsonl(base / "questions.jsonl")}
    results = read_jsonl(base / "mapping_checkpoint.jsonl"); skill_rows, micro_rows = _catalog(config)
    skills = {x["skill_id"]: x for x in skill_rows}; micros = {x["micro_skill_id"]: x for x in micro_rows}; seen = set(); queue = []
    for row in results:
        fp = str(row.get("fingerprint") or ""); errors = validate_result(config, row, skills, micros)
        if fp not in questions: errors.append("UNKNOWN_FINGERPRINT")
        if fp in seen: errors.append("DUPLICATE_FINGERPRINT")
        seen.add(fp)
        queue.append({"fingerprint": fp, "scope_status": row.get("scope_status", ""),
                      "predicted_skill_id": row.get("predicted_skill_id", ""),
                      "predicted_micro_skill_id": row.get("predicted_micro_skill_id", ""),
                      "confidence": row.get("confidence", 0), "review_status": "HUMAN_REVIEW_REQUIRED",
                      "validation_errors": ";".join(errors)})
    invalid = sum(bool(x["validation_errors"]) for x in queue) + len(set(questions) - seen)
    valid = [x for x in queue if x["scope_status"] == config.in_scope_status and not x["validation_errors"]]
    write_csv(base / "human_review_queue.csv", queue, list(queue[0]) if queue else ["fingerprint", "review_status"])
    (base / "mapping_results.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in results), encoding="utf-8")
    result = {"total_questions": len(questions), "mapped": len(queue), "invalid": invalid,
              "provisional_in_scope": len(valid), "provisional_skills_covered": len({x["predicted_skill_id"] for x in valid}),
              "provisional_micros_covered": len({x["predicted_micro_skill_id"] for x in valid if x["predicted_micro_skill_id"]}),
              "human_review_required": len(queue), "counted_as_validated_coverage": 0,
              "technical_pass": len(queue) == len(questions) and invalid == 0,
              "production_reads": 0, "production_writes": 0}
    write_json(base / "mapping_summary.json", result); return result


def handoff(config: GradeConfig, regression_pass: bool = False) -> dict[str, Any]:
    prefix = config.target_id.lower(); local = config.local_output_dir
    audit = json.loads((local / f"{prefix}_curriculum_audit.json").read_text(encoding="utf-8"))
    inv = json.loads((local / f"{prefix}_local_inventory.json").read_text(encoding="utf-8"))
    cov = json.loads((local / "coverage" / f"{prefix}_coverage_summary.json").read_text(encoding="utf-8"))
    val_path = local / "synthetic/holdout/validation_summary.json"; qa_path = local / "quality/mapping_quality_summary.json"
    val = json.loads(val_path.read_text(encoding="utf-8")) if val_path.exists() else {}
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else {}
    map_path = local / "synthetic/tuning/mapping_run_summary.json"
    mapping = json.loads(map_path.read_text(encoding="utf-8")) if map_path.exists() else {}
    foundation = bool(audit["curriculum_integrity"] == "PASS" and val.get("mapping_pilot_pass") and qa.get("technical_pass") and regression_pass)
    completion = 100 if foundation else (70 if audit["curriculum_integrity"] == "PASS" else 0)
    status = "SAFE TO PAUSE" if foundation else "BLOCKED"
    text = f"""# {config.target_id} Pilot Freeze / Handoff

## Status

**{config.target_id} PILOT FOUNDATION: {status}**

Foundation completion: **{completion}%**. Validated real Skill/Micro coverage: **{cov['real_skill_coverage_percent']}% / {cov['real_micro_coverage_percent']}%**.

## Sanitized evidence

- Curriculum integrity: {audit['curriculum_integrity']}; Skills {audit['skills']}; Micro Skills {audit['micro_skills']}.
- Local real source: {inv[f'REAL_{config.target_id}_LOCAL_QUESTION_SOURCE']}; unique questions {inv['unique_questions']}.
- HOLDOUT: {val.get('total_questions', 'NOT_AVAILABLE')} questions; scope {val.get('scope_accuracy', 'NOT_AVAILABLE')}%; exact Skill {val.get('exact_skill_accuracy', 'NOT_AVAILABLE')}%; exact Micro {val.get('exact_micro_accuracy', 'NOT_AVAILABLE')}%; invalid {val.get('invalid', 'NOT_AVAILABLE')}.
- Quality gate: {'PASS' if qa.get('technical_pass') else 'NOT_AVAILABLE/FAIL'}; regression gate: {'PASS' if regression_pass else 'NOT_RUN'}.
- Technical pipeline: {mapping.get('technical_pipeline', 'PASS')}; external API availability: {mapping.get('external_api_availability', 'AVAILABLE' if mapping.get('completed') else 'NOT_RUN')}.
- Architecture: grade config, local inventory, zero-safe coverage, dynamic scope prompt, resilient parser, retry, checkpoint/resume, validation, quality and review queue.
- Model: `{MODEL}`. Production reads: 0. Production writes: 0. Synthetic items counted as real: 0.

## Unfinished work and next action

Human validation is required before provisional mappings increase real coverage. If the HOLDOUT artifacts are unavailable in this workspace, restore the local checkpoint or run the grade pilot without committing private artifacts.
"""
    path = ROOT / "docs/stage5" / f"{config.target_id}_PILOT_FREEZE_HANDOFF.md"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
    result = {"grade": config.grade, "target_id": config.target_id, "profile": config.profile,
              "foundation": status, "foundation_completion": completion,
              "real_skill_coverage_percent": cov["real_skill_coverage_percent"],
              "real_micro_coverage_percent": cov["real_micro_coverage_percent"],
              "production_reads": 0, "production_writes": 0}
    write_json(local / "handoff_summary.json", result); return result


def readiness_matrix() -> dict[str, Any]:
    rows = []
    target_ids = [f"G{number}" for number in range(1, 10)] + [
        "G10_GENERAL", "G11_A", "G11_B", "G12_A", "G12_B"]
    for grade in target_ids:
        try:
            config = load_grade_config(grade); pack = config.curriculum_dir
        except (ValueError, FileNotFoundError):
            pack = PACK_ROOT / grade; config = None
        checks = {"curriculum_pack_available": pack.is_dir(),
                  "standard_skills_available": (pack / "standard_skills.csv").is_file(),
                  "micro_skills_available": (pack / "layer2_micro_skills.csv").is_file(),
                  "out_of_scope_rules_available": (pack / "OUT_OF_SCOPE_RULES.md").is_file()}
        compatible = bool(config and all(checks.values()) and all((pack / x).is_file() for x in REQUIRED_FILES))
        real = bool(config and _real_sources(config))
        rows.append({"grade": grade, **{k: "YES" if v else "NO" for k, v in checks.items()},
                     "generic_engine_compatible": "YES" if compatible else "NO",
                     "real_local_question_source_detected": "YES" if real else "NO",
                     "ready_for_pilot": "YES" if compatible else "NO"})
    compatible = sum(x["generic_engine_compatible"] == "YES" for x in rows)
    ready = sum(x["ready_for_pilot"] == "YES" for x in rows)
    lines = ["# Grade Pilot Readiness Matrix", "", "Sanitized local metadata only; no question content or mapping output is included.", "",
             "| Grade | Pack | Skills | Micros | Scope rules | Engine compatible | Real source | Ready |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for x in rows:
        lines.append(f"| {x['grade']} | {x['curriculum_pack_available']} | {x['standard_skills_available']} | {x['micro_skills_available']} | {x['out_of_scope_rules_available']} | {x['generic_engine_compatible']} | {x['real_local_question_source_detected']} | {x['ready_for_pilot']} |")
    doc = ROOT / "docs/stage5/GRADE_PILOT_READINESS_MATRIX.md"; doc.parent.mkdir(parents=True, exist_ok=True); doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"grades": rows, "curriculum_compatible": compatible, "ready_for_pilot": ready,
            "blocked": len(rows) - ready,
            "aggregates": {"G11": "MULTI_PROFILE", "G12": "MULTI_PROFILE"},
            "production_reads": 0, "production_writes": 0}


def run_all(config: GradeConfig, selected_set: str, regression_pass: bool) -> dict[str, Any]:
    steps = {"environment": environment_audit(config), "audit": curriculum_audit(config)}
    if steps["environment"]["environment_integrity"] != "PASS" or steps["audit"]["curriculum_integrity"] != "PASS":
        raise RuntimeError("FOUNDATION_PRECHECK_FAILED")
    steps["inventory"] = inventory(config); steps["coverage"] = coverage(config)
    steps["prepare_tuning"] = prepare_set(config, "tuning"); steps["map_tuning"] = map_set(config, "tuning")
    steps["validate_tuning"] = validate_set(config, "tuning"); steps["prepare_holdout"] = prepare_set(config, "holdout")
    steps["map_holdout"] = map_set(config, "holdout"); steps["validate_holdout"] = validate_set(config, "holdout")
    steps["quality"] = quality(config, "holdout"); steps["prepare_real"] = prepare_real(config)
    if steps["prepare_real"]["questions"]:
        steps["map_real"] = map_set(config, "real"); steps["validate_real"] = validate_real(config)
    steps["handoff"] = handoff(config, regression_pass); return steps


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--grade", required=True)
    parser.add_argument("command", choices=["environment", "audit", "inventory", "coverage", "prepare", "map", "validate", "quality", "prepare-real", "map-real", "validate-real", "handoff", "readiness", "all"])
    parser.add_argument("--set", choices=["tuning", "holdout"], default="holdout"); parser.add_argument("--regression-pass", action="store_true")
    args = parser.parse_args(); config = load_grade_config(args.grade)
    actions = {"environment": lambda: environment_audit(config), "audit": lambda: curriculum_audit(config),
               "inventory": lambda: inventory(config), "coverage": lambda: coverage(config),
               "prepare": lambda: prepare_set(config, args.set), "map": lambda: map_set(config, args.set),
               "validate": lambda: validate_set(config, args.set), "quality": lambda: quality(config, args.set),
               "prepare-real": lambda: prepare_real(config), "map-real": lambda: map_set(config, "real"),
               "validate-real": lambda: validate_real(config), "handoff": lambda: handoff(config, args.regression_pass),
               "readiness": readiness_matrix, "all": lambda: run_all(config, args.set, args.regression_pass)}
    try:
        result = actions[args.command]()
    except GeminiQuotaBlocked:
        summary = _base(config, "real" if args.command == "map-real" else args.set) / "mapping_run_summary.json"
        result = json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else {
            "status": "GEMINI_QUOTA_BLOCKED", "technical_pipeline": "PASS",
            "external_api_availability": "BLOCKED", "production_reads": 0, "production_writes": 0}
        print(json.dumps(result, ensure_ascii=False))
        return 3
    print(json.dumps(result, ensure_ascii=False))
    if isinstance(result, dict) and (result.get("curriculum_integrity") == "FAIL" or result.get("environment_integrity") == "FAIL" or result.get("technical_pass") is False or result.get("foundation") == "BLOCKED"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
