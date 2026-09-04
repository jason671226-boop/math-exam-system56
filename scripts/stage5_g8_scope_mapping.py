"""Scope-aware G8 mapping smoke test for MathAI Stage 5B-2A.

Purpose:
- Detect questions that do not belong to the G8 curriculum before mapping them.
- Prevent dirty/out-of-grade questions from being force-mapped into the nearest G8 skill.

Safety:
- Reads local pilot artifacts only.
- Calls Gemini only for classification.
- No Supabase/database reads or writes.
- All outputs stay under the supplied local output directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.stage5_question_mapping import mapping_review_status, validate_mapping

DEFAULT_MODEL = os.getenv("G8_MAPPING_MODEL", "gemini-3.6-flash")


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
    for candidate in (name,) + aliases:
        value = os.getenv(candidate)
        if value:
            return value.strip()
    secrets = _load_toml_secrets()
    for candidate in (name,) + aliases:
        value = secrets.get(candidate)
        if value:
            return str(value).strip()
    return ""


def _gemini_client():
    from google import genai

    api_key = _secret("GEMINI_API_KEY", "GEMINI_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GEMINI_KEY in env/.streamlit/secrets.toml")
    return genai.Client(api_key=api_key)


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required local artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Missing required local artifact: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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


def _scope_catalog(skills: list[dict[str, Any]]) -> dict[str, Any]:
    main_units = sorted({str(row.get("main_unit") or "") for row in skills if str(row.get("main_unit") or "")})
    skill_names = sorted({str(row.get("skill_name") or "") for row in skills if str(row.get("skill_name") or "")})
    return {"main_units": main_units, "skill_names": skill_names}


def _prompt(packet: dict[str, Any], scope_catalog: dict[str, Any]) -> str:
    compact_packet = {
        "fingerprint": packet.get("fingerprint"),
        "question_text": packet.get("question_text"),
        "answer_text": packet.get("answer_text"),
        "unit": packet.get("unit"),
        "knowledge_tag": packet.get("knowledge_tag"),
        "skill_candidates": packet.get("skill_candidates", []),
        "micro_candidates": packet.get("micro_candidates", []),
    }
    payload = json.dumps(compact_packet, ensure_ascii=False)
    catalog = json.dumps(scope_catalog, ensure_ascii=False)
    return f"""You are a Taiwan Grade 8 mathematics curriculum scope checker and classifier for MathAI.

STEP 1 — Scope gate:
Decide whether the mathematical content itself belongs to the supplied G8 curriculum catalog.
The source unit/knowledge_tag may be dirty or from a wrong grade, so treat them only as weak hints.
Earlier-grade prerequisite exercises should be OUT_OF_SCOPE_G8 unless the question genuinely tests a G8 skill.

Critical guardrails discovered in pilot data:
- Integer factors/multiples, prime factorization, GCD/LCM are NOT the same as G8 polynomial factorization. Do not map integer GCD/LCM questions to G8 polynomial 因式分解.
- G7 two-variable linear equations / simultaneous linear equations are NOT G8 one-variable quadratic equations. Do not force them into G8 一元二次方程式.
- A question may be mathematically valid but still OUT_OF_SCOPE_G8.

STEP 2 — Mapping only if IN_SCOPE_G8:
Choose exactly one primary skill_id from skill_candidates.
Choose micro_skill_id only from micro_candidates and only when it belongs to the chosen skill_id; otherwise null.
Do not invent IDs.

Return JSON only with keys:
fingerprint, scope_status, out_of_scope_reason, skill_id, micro_skill_id, question_type, difficulty, confidence, rationale_short

Rules:
- scope_status must be exactly IN_SCOPE_G8 or OUT_OF_SCOPE_G8.
- If OUT_OF_SCOPE_G8: skill_id=null, micro_skill_id=null, question_type="OUT_OF_SCOPE", difficulty=null.
- If IN_SCOPE_G8: skill_id must be one supplied candidate; micro_skill_id must obey parent relation.
- confidence is 0..1 and represents confidence in the combined scope+mapping decision.

G8 curriculum catalog:
{catalog}

Question packet:
{payload}
"""


def _scope_review_status(result: dict[str, Any]) -> str:
    confidence = float(result.get("confidence") or 0.0)
    scope_status = str(result.get("scope_status") or "")
    if scope_status == "OUT_OF_SCOPE_G8":
        return "AUTO_OUT_OF_SCOPE" if confidence >= 0.85 else "REVIEW_SCOPE"
    return mapping_review_status(confidence)


def _validate_scope_result(
    result: dict[str, Any],
    skills_by_id: dict[str, dict[str, Any]],
    micros_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    scope_status = str(result.get("scope_status") or "")
    if scope_status not in {"IN_SCOPE_G8", "OUT_OF_SCOPE_G8"}:
        errors.append("INVALID_SCOPE_STATUS")
        return errors

    try:
        confidence = float(result.get("confidence"))
        if not 0.0 <= confidence <= 1.0:
            errors.append("CONFIDENCE_OUT_OF_RANGE")
    except (TypeError, ValueError):
        errors.append("INVALID_CONFIDENCE")

    if scope_status == "OUT_OF_SCOPE_G8":
        if result.get("skill_id") not in (None, ""):
            errors.append("OUT_OF_SCOPE_HAS_SKILL")
        if result.get("micro_skill_id") not in (None, ""):
            errors.append("OUT_OF_SCOPE_HAS_MICRO")
        return errors

    errors.extend(validate_mapping(result, skills_by_id, micros_by_id))
    return errors


def run_mapping(output: Path, model: str) -> dict[str, Any]:
    packets = _read_jsonl(output / "g8_mapping_input.jsonl")
    skills = _read_json(output / "g8_curriculum_skills.json")
    if not packets:
        raise RuntimeError("No mapping input")
    if len(packets) != 20:
        raise RuntimeError(f"Scope smoke expects exactly 20 packets; got {len(packets)}")

    scope_catalog = _scope_catalog(skills)
    client = _gemini_client()
    results: list[dict[str, Any]] = []
    for index, packet in enumerate(packets, 1):
        response = client.models.generate_content(model=model, contents=_prompt(packet, scope_catalog))
        parsed = _response_json(getattr(response, "text", ""))
        parsed["fingerprint"] = packet["fingerprint"]
        parsed["model"] = model
        parsed["review_status"] = _scope_review_status(parsed)
        results.append(parsed)
        print(
            f"Scoped {index}/20 {str(packet['fingerprint'])[:10]} "
            f"{parsed.get('scope_status')} {parsed.get('review_status')}"
        )

    _write_jsonl(output / "g8_scope_mapping_results.jsonl", results)
    return {
        "requested": 20,
        "mapped": len(results),
        "model": model,
        "production_reads": 0,
        "production_writes": 0,
    }


def validate(output: Path) -> dict[str, Any]:
    skills = _read_json(output / "g8_curriculum_skills.json")
    micros = _read_json(output / "g8_curriculum_micro_skills.json")
    sample = _read_json(output / "g8_pilot_sample.json")
    results = _read_jsonl(output / "g8_scope_mapping_results.jsonl")
    if len(results) != 20:
        raise RuntimeError(f"Expected 20 scope results; got {len(results)}")

    skills_by_id = {str(row["skill_id"]): row for row in skills}
    micros_by_id = {str(row["micro_skill_id"]): row for row in micros}
    sample_by_fp = {str(row["fingerprint"]): row for row in sample}

    invalid = 0
    scope_counts = {"IN_SCOPE_G8": 0, "OUT_OF_SCOPE_G8": 0}
    review_counts: dict[str, int] = {}
    review_rows: list[dict[str, Any]] = []

    for result in results:
        errors = _validate_scope_result(result, skills_by_id, micros_by_id)
        if errors:
            invalid += 1
        scope_status = str(result.get("scope_status") or "")
        if scope_status in scope_counts:
            scope_counts[scope_status] += 1
        review_status = _scope_review_status(result)
        review_counts[review_status] = review_counts.get(review_status, 0) + 1
        question = sample_by_fp.get(str(result.get("fingerprint") or ""), {})
        review_rows.append({
            "fingerprint": result.get("fingerprint", ""),
            "question_text": question.get("question_text", ""),
            "source_unit": question.get("unit", ""),
            "source_knowledge_tag": question.get("knowledge_tag", ""),
            "scope_status": scope_status,
            "out_of_scope_reason": result.get("out_of_scope_reason", ""),
            "skill_id": result.get("skill_id") or "",
            "micro_skill_id": result.get("micro_skill_id") or "",
            "question_type": result.get("question_type") or "",
            "difficulty": "" if result.get("difficulty") is None else result.get("difficulty"),
            "confidence": result.get("confidence", ""),
            "review_status": review_status,
            "validation_errors": ",".join(errors),
            "human_verdict": "",
            "human_note": "",
        })

    _write_csv(
        output / "g8_scope_human_review_queue.csv",
        review_rows,
        [
            "fingerprint", "question_text", "source_unit", "source_knowledge_tag", "scope_status",
            "out_of_scope_reason", "skill_id", "micro_skill_id", "question_type", "difficulty",
            "confidence", "review_status", "validation_errors", "human_verdict", "human_note",
        ],
    )

    report = {
        "sample_size": len(sample),
        "mapped": len(results),
        "scope_counts": scope_counts,
        "review_counts": review_counts,
        "invalid": invalid,
        "production_reads": 0,
        "production_writes": 0,
        "ready_for_human_review": len(results) == 20 and invalid == 0,
    }
    _write_json(output / "scope_validation_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="MathAI G8 scope-aware smoke mapping")
    parser.add_argument("command", choices=("map", "validate", "all"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    try:
        if args.command in ("map", "all"):
            print("SCOPE_MAP:", json.dumps(run_mapping(args.output, args.model), ensure_ascii=False))
        if args.command in ("validate", "all"):
            print("SCOPE_VALIDATE:", json.dumps(validate(args.output), ensure_ascii=False))
    except Exception as exc:
        print(f"STAGE5 G8 SCOPE PILOT: BLOCKED ({type(exc).__name__}): {exc}")
        return 2
    print("STAGE5 G8 SCOPE PILOT: PASS (local artifacts only; production writes=0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
