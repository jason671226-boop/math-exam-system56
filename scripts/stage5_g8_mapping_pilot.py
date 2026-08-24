"""Stage 5B-2A: local-only G8 question mapping pilot.

Safety guarantees:
- Production reads use anon credentials and SELECT only.
- Pending G8 rows hidden by RLS are never bypassed on the user's machine.
- A management-exported sample may be supplied as a local JSON file.
- Curriculum Skills/Micro Skills come from the Stage-4-validated local G8 snapshot.
- No insert/update/delete/upsert/RPC/DDL calls exist in this script.
- All generated artifacts stay under .local/stage5_g8_mapping_pilot.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.stage5_question_mapping import (
    build_candidate_packet,
    deduplicate_questions,
    mapping_review_status,
    normalize_question_text,
    question_fingerprint,
    stratified_sample,
    validate_mapping,
)

PRODUCTION_PROJECT_REF = "igttuijrtwbtefhyeokp"
RELEASE_ID = "CURRICULUM_V27_EA0E6735"
G8_PROFILE_ID = "CURRICULUM_V27:PREHIGH:G8:COMMON"
G8_MASTER = ROOT / "data" / "master_curriculum_v2_7" / "grade_packs" / "G8"
DEFAULT_OUTPUT = ROOT / ".local" / "stage5_g8_mapping_pilot"
DEFAULT_SAMPLE_SOURCE = DEFAULT_OUTPUT / "g8_management_sample_200.json"
DEFAULT_MODEL = os.getenv("G8_MAPPING_MODEL", "gemini-2.5-flash")
PRODUCTION_AUDIT_RAW_ROWS = 12010
PRODUCTION_AUDIT_UNIQUE_QUESTIONS = 955


def _load_toml_secrets() -> dict[str, Any]:
    for path in (
        ROOT / ".streamlit" / "secrets.toml",
        ROOT / "app" / ".streamlit" / "secrets.toml",
    ):
        if path.exists():
            with path.open("rb") as handle:
                data = tomllib.load(handle)
            if isinstance(data, dict):
                return data
    return {}


def _secret(name: str, *aliases: str) -> str:
    candidates = (name,) + aliases
    for candidate in candidates:
        value = os.getenv(candidate)
        if value:
            return value.strip()
    secrets = _load_toml_secrets()
    for candidate in candidates:
        value = secrets.get(candidate)
        if value:
            return str(value).strip()
    return ""


def _production_supabase_client():
    from supabase import create_client

    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_KEY", "SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL/SUPABASE_KEY in env or .streamlit/secrets.toml")
    if PRODUCTION_PROJECT_REF not in url:
        raise RuntimeError(
            "Safety stop: G8 pilot only permits read-only extraction from production project "
            f"{PRODUCTION_PROJECT_REF}; got a different URL."
        )
    return create_client(url, key)


def _fetch_all(page_factory, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        response = page_factory(start, start + page_size - 1).execute()
        page = response.data if isinstance(response.data, list) else []
        rows.extend(dict(row) for row in page)
        if len(page) < page_size:
            return rows
        start += page_size


def _read_csv(name: str) -> list[dict[str, Any]]:
    path = G8_MASTER / name
    if not path.exists():
        raise RuntimeError(f"Missing verified local curriculum snapshot: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_local_curriculum() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_skills = _read_csv("standard_skills.csv")
    raw_micros = _read_csv("layer2_micro_skills.csv")

    skills: list[dict[str, Any]] = []
    for source_order, row in enumerate(raw_skills, 1):
        skills.append({
            "release_id": RELEASE_ID,
            "profile_id": G8_PROFILE_ID,
            "skill_id": row.get("skill_id", ""),
            "official_code_raw": row.get("official_code", ""),
            "main_unit_id": "",
            "subunit_id": "",
            "main_unit": row.get("main_unit", ""),
            "subunit": row.get("subunit", ""),
            "skill_name": row.get("skill_name", ""),
            "focus": row.get("focus", ""),
            "difficulty": int(row.get("difficulty") or 0),
            "source_order": source_order,
        })

    micros: list[dict[str, Any]] = []
    for source_order, row in enumerate(raw_micros, 1):
        micros.append({
            "release_id": RELEASE_ID,
            "profile_id": G8_PROFILE_ID,
            "micro_skill_id": row.get("micro_skill_id", ""),
            "parent_skill_id": row.get("parent_skill_id", ""),
            "official_code_raw": row.get("official_code", ""),
            "main_unit_id": "",
            "subunit_id": "",
            "skill_name": row.get("skill_name", ""),
            "question_type": row.get("question_type", ""),
            "focus": row.get("focus", ""),
            "item_pattern": row.get("item_pattern", ""),
            "common_error": row.get("common_error", ""),
            "difficulty": int(row.get("difficulty") or 0),
            "source_order": source_order,
        })

    skill_ids = {str(row["skill_id"]) for row in skills}
    broken = [
        str(row["micro_skill_id"])
        for row in micros
        if str(row.get("parent_skill_id") or "") not in skill_ids
    ]
    if broken:
        raise RuntimeError("Broken micro-skill parents in local G8 snapshot: " + ", ".join(broken[:10]))
    if len(skills) != 102 or len(micros) != 660:
        raise RuntimeError(
            f"G8 curriculum snapshot count mismatch: {len(skills)}/{len(micros)} expected 102/660"
        )
    return skills, micros


def _read_production_approved_rows() -> list[dict[str, Any]]:
    client = _production_supabase_client()

    def item_page(start: int, end: int):
        return (
            client.table("item_bank")
            .select("id,index_code,grade,unit,knowledge_tag,new_question,correct_answer,status")
            .in_("grade", ["國中八年級", "8"])
            .order("id")
            .range(start, end)
        )

    return _fetch_all(item_page)


def _read_management_sample(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Local management sample not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Management sample must be a JSON list")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload, 1):
        if isinstance(item, list):
            if len(item) != 6:
                raise RuntimeError(f"Compact sample row {index} must contain 6 values")
            rep_id, question, answer, unit, tag, dup_count = item
            row = {
                "representative_id": int(rep_id),
                "question_text": normalize_question_text(question),
                "answer_text": str(answer or ""),
                "unit": str(unit or ""),
                "knowledge_tag": str(tag or ""),
                "duplicate_count": int(dup_count or 1),
            }
        elif isinstance(item, dict):
            row = {
                "representative_id": int(item.get("representative_id") or item.get("id") or 0),
                "question_text": normalize_question_text(item.get("question_text") or item.get("new_question") or ""),
                "answer_text": str(item.get("answer_text") or item.get("correct_answer") or ""),
                "unit": str(item.get("unit") or ""),
                "knowledge_tag": str(item.get("knowledge_tag") or ""),
                "duplicate_count": int(item.get("duplicate_count") or 1),
            }
        else:
            raise RuntimeError(f"Unsupported sample row type at {index}")
        if not row["representative_id"] or not row["question_text"]:
            raise RuntimeError(f"Management sample row {index} is missing id/question")
        row.update({
            "fingerprint": question_fingerprint(row["question_text"]),
            "representative_index_code": f"MGMT-{row['representative_id']}",
            "source_row_ids": [row["representative_id"]],
            "source_index_codes": [f"MGMT-{row['representative_id']}"],
            "unit_variants": [row["unit"]] if row["unit"] else [],
            "knowledge_tag_variants": [row["knowledge_tag"]] if row["knowledge_tag"] else [],
            "answer_variants": [row["answer_text"]] if row["answer_text"] else [],
            "has_metadata_conflict": False,
        })
        rows.append(row)

    fingerprints = [str(row["fingerprint"]) for row in rows]
    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("Management sample contains duplicate normalized question fingerprints")
    if len(rows) != 200:
        raise RuntimeError(f"Management G8 Pilot sample must contain exactly 200 unique rows; got {len(rows)}")
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            clean = dict(row)
            for key, value in list(clean.items()):
                if isinstance(value, (list, dict)):
                    clean[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(clean)


def prepare(output: Path, sample_size: int, sample_source: Path | None = None) -> dict[str, Any]:
    skills, micros = _read_local_curriculum()

    if sample_source is not None:
        unique = _read_management_sample(sample_source)
        sample = list(unique)
        raw_rows = PRODUCTION_AUDIT_RAW_ROWS
        unique_count = PRODUCTION_AUDIT_UNIQUE_QUESTIONS
        mode = "LOCAL_EXPORTED_PENDING_G8_SAMPLE"
        input_rows = len(unique)
    else:
        item_rows = _read_production_approved_rows()
        if not item_rows:
            raise RuntimeError(
                "FAIL-CLOSED: item_bank returned 0 visible G8 rows. Production audit shows 12,010 G8 rows, "
                "all pending and hidden by RLS. Do not relax RLS; use --sample-source with the local management export."
            )
        unique = deduplicate_questions(item_rows)
        sample = stratified_sample(unique, sample_size=sample_size)
        if not sample:
            raise RuntimeError("FAIL-CLOSED: G8 sample is empty")
        raw_rows = len(item_rows)
        unique_count = len(unique)
        mode = "PRODUCTION_APPROVED_READ_ONLY"
        input_rows = len(item_rows)

    packets = [build_candidate_packet(row, skills, micros) for row in sample]
    if len(packets) != len(sample):
        raise RuntimeError("Candidate packet count mismatch")

    _write_json(output / "g8_curriculum_skills.json", skills)
    _write_json(output / "g8_curriculum_micro_skills.json", micros)
    _write_json(output / "g8_pilot_sample.json", sample)
    _write_jsonl(output / "g8_mapping_input.jsonl", packets)

    sample_fields = [
        "fingerprint", "representative_id", "representative_index_code", "question_text",
        "answer_text", "unit", "knowledge_tag", "duplicate_count", "has_metadata_conflict",
    ]
    _write_csv(output / "g8_pilot_sample.csv", sample, sample_fields)

    manifest = {
        "stage": "5B-2A",
        "mode": mode,
        "production_project_ref": PRODUCTION_PROJECT_REF,
        "release_id": RELEASE_ID,
        "profile_id": G8_PROFILE_ID,
        "curriculum_source": "LOCAL_STAGE4_VALIDATED_MASTER_V27_G8",
        "production_audit_raw_rows": PRODUCTION_AUDIT_RAW_ROWS,
        "production_audit_unique_questions": PRODUCTION_AUDIT_UNIQUE_QUESTIONS,
        "input_rows": input_rows,
        "raw_rows": raw_rows,
        "unique_questions": unique_count,
        "sample_size": len(sample),
        "skills": len(skills),
        "micro_skills": len(micros),
        "metadata_conflicts_in_sample": sum(1 for row in sample if row.get("has_metadata_conflict")),
        "production_writes": 0,
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def _gemini_client():
    from google import genai

    api_key = _secret("GEMINI_API_KEY", "GEMINI_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GEMINI_KEY in env/.streamlit/secrets.toml")
    return genai.Client(api_key=api_key)


def _response_json(text: str) -> Any:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else value
        if value.endswith("```"):
            value = value[:-3]
        value = value.strip()
        if value.lower().startswith("json"):
            value = value[4:].lstrip("\n ")
    return json.loads(value)


def _mapping_prompt(packet: dict[str, Any]) -> str:
    payload = json.dumps(packet, ensure_ascii=False)
    return f"""You are a Taiwan G8 mathematics curriculum classifier for MathAI.
Choose exactly one primary skill_id from skill_candidates. Choose a micro_skill_id only from micro_candidates and only if it belongs to the chosen skill_id; otherwise return null.
Do not invent IDs. Use mathematical content as primary evidence; unit and knowledge_tag are hints and may be noisy.
Return JSON only with keys: fingerprint, skill_id, micro_skill_id, question_type, difficulty, confidence, rationale_short.
confidence must be 0..1. difficulty must be integer 1..5.
Question packet:
{payload}
"""


def run_mapping(output: Path, model: str, limit: int | None = None) -> dict[str, Any]:
    packets = _read_jsonl(output / "g8_mapping_input.jsonl")
    if not packets:
        raise RuntimeError("No mapping input. Run prepare successfully first.")
    if limit is not None:
        packets = packets[:limit]
    results_path = output / "g8_mapping_results.jsonl"
    existing = {row.get("fingerprint"): row for row in _read_jsonl(results_path)}
    client = _gemini_client()
    written = 0
    with results_path.open("a", encoding="utf-8") as handle:
        for index, packet in enumerate(packets, 1):
            fingerprint = packet["fingerprint"]
            if fingerprint in existing:
                continue
            response = client.models.generate_content(model=model, contents=_mapping_prompt(packet))
            parsed = _response_json(getattr(response, "text", ""))
            parsed["fingerprint"] = fingerprint
            parsed["model"] = model
            parsed["review_status"] = mapping_review_status(float(parsed.get("confidence") or 0.0))
            handle.write(json.dumps(parsed, ensure_ascii=False) + "\n")
            handle.flush()
            written += 1
            print(f"Mapped {index}/{len(packets)} {fingerprint[:10]} {parsed['review_status']}")
    return {
        "requested": len(packets),
        "newly_mapped": written,
        "total_results": len(_read_jsonl(results_path)),
        "model": model,
    }


def validate(output: Path) -> dict[str, Any]:
    skills = json.loads((output / "g8_curriculum_skills.json").read_text(encoding="utf-8"))
    micros = json.loads((output / "g8_curriculum_micro_skills.json").read_text(encoding="utf-8"))
    sample = json.loads((output / "g8_pilot_sample.json").read_text(encoding="utf-8"))
    results = _read_jsonl(output / "g8_mapping_results.jsonl")
    skills_by_id = {str(row["skill_id"]): row for row in skills}
    micros_by_id = {str(row["micro_skill_id"]): row for row in micros}
    sample_by_fp = {str(row["fingerprint"]): row for row in sample}

    review_rows: list[dict[str, Any]] = []
    invalid = 0
    statuses = {"AUTO_CANDIDATE": 0, "REVIEW": 0, "REJECT": 0}
    for result in results:
        errors = validate_mapping(result, skills_by_id, micros_by_id)
        if errors:
            invalid += 1
        status = mapping_review_status(float(result.get("confidence") or 0.0))
        statuses[status] += 1
        question = sample_by_fp.get(str(result.get("fingerprint") or ""), {})
        review_rows.append({
            "fingerprint": result.get("fingerprint"),
            "question_text": question.get("question_text", ""),
            "unit": question.get("unit", ""),
            "knowledge_tag": question.get("knowledge_tag", ""),
            "skill_id": result.get("skill_id", ""),
            "micro_skill_id": result.get("micro_skill_id", ""),
            "question_type": result.get("question_type", ""),
            "difficulty": result.get("difficulty", ""),
            "confidence": result.get("confidence", ""),
            "review_status": status,
            "validation_errors": ",".join(errors),
            "human_verdict": "",
            "human_note": "",
        })

    _write_csv(output / "g8_human_review_queue.csv", review_rows, [
        "fingerprint", "question_text", "unit", "knowledge_tag", "skill_id", "micro_skill_id",
        "question_type", "difficulty", "confidence", "review_status", "validation_errors",
        "human_verdict", "human_note",
    ])
    report = {
        "sample_size": len(sample),
        "mapped": len(results),
        "unmapped": max(0, len(sample) - len(results)),
        "invalid_fk_or_parent": invalid,
        "status_counts": statuses,
        "production_writes": 0,
        "ready_for_human_review": len(results) > 0 and invalid == 0,
    }
    _write_json(output / "validation_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="MathAI Stage 5B-2A local G8 mapping pilot")
    parser.add_argument("command", choices=("prepare", "map", "validate", "all"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--sample-source", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None, help="Map only the first N sample questions")
    args = parser.parse_args()
    try:
        if args.command in ("prepare", "all"):
            print("PREPARE:", json.dumps(prepare(args.output, args.sample_size, args.sample_source), ensure_ascii=False))
        if args.command in ("map", "all"):
            print("MAP:", json.dumps(run_mapping(args.output, args.model, args.limit), ensure_ascii=False))
        if args.command in ("validate", "all"):
            print("VALIDATE:", json.dumps(validate(args.output), ensure_ascii=False))
    except Exception as exc:
        print(f"STAGE5 G8 PILOT: BLOCKED ({type(exc).__name__}): {exc}")
        return 2
    print("STAGE5 G8 PILOT: PASS (local artifacts only; production writes=0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
