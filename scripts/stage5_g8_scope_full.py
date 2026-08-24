"""Stage 5B-2B: resumable scope-aware mapping for the full local G8 200-row pilot.

Safety:
- Reads local pilot artifacts only.
- Calls Gemini only for scope/mapping classification.
- No Supabase/database reads or writes.
- Checkpoints every completed result so interrupted runs can resume.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from stage5_g8_scope_mapping import (
    _gemini_client,
    _prompt,
    _read_json,
    _read_jsonl,
    _response_json,
    _scope_catalog,
    _scope_review_status,
    _validate_scope_result,
    _write_csv,
    _write_json,
)

DEFAULT_MODEL = os.getenv("G8_MAPPING_MODEL", "gemini-3.6-flash")
EXPECTED_SAMPLE_SIZE = 200


def _existing_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return _read_jsonl(path)


def run_mapping(output: Path, model: str) -> dict[str, Any]:
    packets = _read_jsonl(output / "g8_mapping_input.jsonl")
    skills = _read_json(output / "g8_curriculum_skills.json")
    sample = _read_json(output / "g8_pilot_sample.json")

    if len(packets) != EXPECTED_SAMPLE_SIZE or len(sample) != EXPECTED_SAMPLE_SIZE:
        raise RuntimeError(
            f"Stage 5B-2B requires exactly {EXPECTED_SAMPLE_SIZE} local rows; "
            f"packets={len(packets)} sample={len(sample)}"
        )

    packet_fps = [str(row.get("fingerprint") or "") for row in packets]
    if not all(packet_fps) or len(packet_fps) != len(set(packet_fps)):
        raise RuntimeError("Input packets contain blank or duplicate fingerprints")

    results_path = output / "g8_scope_mapping_results.jsonl"
    existing_rows = _existing_results(results_path)
    existing: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        fp = str(row.get("fingerprint") or "")
        if not fp or fp not in set(packet_fps):
            raise RuntimeError("Existing checkpoint contains an unknown/blank fingerprint")
        if fp in existing:
            raise RuntimeError("Existing checkpoint contains duplicate fingerprints")
        existing[fp] = row

    scope_catalog = _scope_catalog(skills)
    client = _gemini_client()
    newly_mapped = 0

    with results_path.open("a", encoding="utf-8") as handle:
        for index, packet in enumerate(packets, 1):
            fp = str(packet["fingerprint"])
            if fp in existing:
                print(f"Scoped {index}/{EXPECTED_SAMPLE_SIZE} {fp[:10]} CHECKPOINT_SKIP")
                continue

            response = client.models.generate_content(model=model, contents=_prompt(packet, scope_catalog))
            parsed = _response_json(getattr(response, "text", ""))
            parsed["fingerprint"] = fp
            parsed["model"] = model
            parsed["review_status"] = _scope_review_status(parsed)

            handle.write(json.dumps(parsed, ensure_ascii=False) + "\n")
            handle.flush()
            existing[fp] = parsed
            newly_mapped += 1
            print(
                f"Scoped {index}/{EXPECTED_SAMPLE_SIZE} {fp[:10]} "
                f"{parsed.get('scope_status')} {parsed.get('review_status')}"
            )

    return {
        "requested": EXPECTED_SAMPLE_SIZE,
        "newly_mapped": newly_mapped,
        "total_results": len(existing),
        "model": model,
        "production_reads": 0,
        "production_writes": 0,
        "resumable": True,
    }


def validate(output: Path) -> dict[str, Any]:
    skills = _read_json(output / "g8_curriculum_skills.json")
    micros = _read_json(output / "g8_curriculum_micro_skills.json")
    sample = _read_json(output / "g8_pilot_sample.json")
    results = _existing_results(output / "g8_scope_mapping_results.jsonl")

    if len(sample) != EXPECTED_SAMPLE_SIZE:
        raise RuntimeError(f"Expected {EXPECTED_SAMPLE_SIZE} sample rows; got {len(sample)}")
    if len(results) != EXPECTED_SAMPLE_SIZE:
        raise RuntimeError(
            f"Mapping is incomplete: expected {EXPECTED_SAMPLE_SIZE} results; got {len(results)}. "
            "Rerun the same batch to resume."
        )

    skills_by_id = {str(row["skill_id"]): row for row in skills}
    micros_by_id = {str(row["micro_skill_id"]): row for row in micros}
    sample_by_fp = {str(row["fingerprint"]): row for row in sample}

    seen: set[str] = set()
    invalid = 0
    scope_counts = {"IN_SCOPE_G8": 0, "OUT_OF_SCOPE_G8": 0}
    review_counts: dict[str, int] = {}
    review_rows: list[dict[str, Any]] = []

    for result in results:
        fp = str(result.get("fingerprint") or "")
        if not fp or fp in seen or fp not in sample_by_fp:
            invalid += 1
        seen.add(fp)

        errors = _validate_scope_result(result, skills_by_id, micros_by_id)
        if errors:
            invalid += 1

        scope_status = str(result.get("scope_status") or "")
        if scope_status in scope_counts:
            scope_counts[scope_status] += 1
        review_status = _scope_review_status(result)
        review_counts[review_status] = review_counts.get(review_status, 0) + 1
        question = sample_by_fp.get(fp, {})
        review_rows.append({
            "fingerprint": fp,
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
        "stage": "5B-2B",
        "sample_size": len(sample),
        "mapped": len(results),
        "scope_counts": scope_counts,
        "review_counts": review_counts,
        "invalid": invalid,
        "production_reads": 0,
        "production_writes": 0,
        "ready_for_human_review": len(results) == EXPECTED_SAMPLE_SIZE and invalid == 0,
    }
    _write_json(output / "scope_validation_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="MathAI Stage 5B-2B full G8 scope-aware local mapping")
    parser.add_argument("command", choices=("map", "validate", "all"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    try:
        if args.command in ("map", "all"):
            print("SCOPE200_MAP:", json.dumps(run_mapping(args.output, args.model), ensure_ascii=False))
        if args.command in ("validate", "all"):
            print("SCOPE200_VALIDATE:", json.dumps(validate(args.output), ensure_ascii=False))
    except Exception as exc:
        print(f"STAGE5 G8 200 SCOPE PILOT: BLOCKED ({type(exc).__name__}): {exc}")
        return 2

    print("STAGE5 G8 200 SCOPE PILOT: PASS (local artifacts only; production writes=0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
