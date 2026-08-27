"""Build a local-only, fail-closed elementary competition corpus inventory."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.elementary_competition import (classify_source, normalized_fingerprint,
    pilot_eligible, select_pilot, source_quality_risks)

LOCAL = ROOT / ".local" / "stage7_elementary_competition" / "foundation_inventory"
INVENTORY_JSON = LOCAL / "competition_corpus_inventory.json"
INVENTORY_CSV = LOCAL / "competition_corpus_inventory.csv"
SOURCE_AUDIT = LOCAL / "competition_source_audit.json"
QUALITY_QUEUE = LOCAL / "competition_source_quality_queue.json"
UNIQUE_JSONL = LOCAL / "competition_unique_questions.jsonl"
PILOT_JSONL = LOCAL / "competition_pilot100.jsonl"
PILOT_MANIFEST = LOCAL / "competition_pilot100_manifest.json"
COMPETITION_FILES = (ROOT / "data/diagnostic_questions_g5_competition_core_v1.json",
                     ROOT / "data/diagnostic_questions_g6_competition_core_v1.json")
BASELINE_FILES = (ROOT / "data/diagnostic_questions_g5_baseline_v1.json",
                  ROOT / "data/diagnostic_questions_g6_pilot_v1.json")
PRIVATE_REGISTRY = ROOT / ".local/stage7_private_jh/public_source_registry.json"

SECTION_TOPIC = {"A_NUMBER": "ARITHMETIC_TRICKS", "B_NUMBER_THEORY": "NUMBER_THEORY",
    "C_RELATION": "WORD_PROBLEM", "D_PATTERN_LOGIC": "NUMBER_PATTERN", "E_COUNTING": "COUNTING",
    "F_GEOMETRY": "GEOMETRY", "G_NOVEL": "COMBINED"}


def _questions(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = next((value for value in data.values() if isinstance(value, list) and value
                 and isinstance(value[0], dict) and "question_id" in value[0]), [])
    return data, rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def build() -> dict[str, Any]:
    if not all(path.is_file() for path in COMPETITION_FILES + BASELINE_FILES) or not PRIVATE_REGISTRY.is_file():
        raise RuntimeError("COMPETITION_INVENTORY_INPUT_MISSING")
    LOCAL.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    for path, grade in zip(COMPETITION_FILES, ("G5", "G6")):
        data, questions = _questions(path)
        metadata = {"target_profile": data.get("target_profile"), "source_url": None,
            "competition_name": None, "official_competition_source": False}
        source_class = classify_source(metadata)
        sources.append({"source": path.name, "source_class": source_class, "rows": len(questions),
            "grade": grade, "reason": "COMPETITION_PROFILE_WITHOUT_VERIFIABLE_PROVENANCE"})
        for question in questions:
            text = str(question.get("prompt") or "")
            raw.append({"fingerprint": normalized_fingerprint(text), "question_text": text,
                "question_id": question.get("question_id"), "source": path.name, "source_class": source_class,
                "source_url": None, "grade": grade, "competition_topic": SECTION_TOPIC.get(
                    str(question.get("section")), "COMBINED"), "visualization": question.get("visualization"),
                "source_complete": False, "official_competition_source": False})
    private = json.loads(PRIVATE_REGISTRY.read_text(encoding="utf-8-sig"))
    for item in private.get("sources", []):
        sources.append({"source": item.get("school") or "PRIVATE_JH_SOURCE", "source_class": "PRIVATE_JH",
            "rows": item.get("math_question_estimate") or 0, "grade": item.get("grade_scope"),
            "reason": "PRIVATE_JH_EXCLUDED"})
    for path in BASELINE_FILES:
        _, questions = _questions(path)
        sources.append({"source": path.name, "source_class": "GENERAL_CURRICULUM", "rows": len(questions),
            "grade": "G5" if "g5" in path.name else "G6", "reason": "GENERAL_CURRICULUM_EXCLUDED"})

    unique_by_fp: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for question in raw:
        if question["fingerprint"] in unique_by_fp:
            duplicates += 1
        else:
            unique_by_fp[question["fingerprint"]] = question
    unique = list(unique_by_fp.values())
    quality: list[dict[str, Any]] = []
    usable: list[dict[str, Any]] = []
    for question in unique:
        risks = source_quality_risks(question)
        if risks:
            quality.append({"fingerprint": question["fingerprint"], "risks": risks,
                "status": "SOURCE_NEEDS_REEXTRACTION", "source": question["source"]})
        if pilot_eligible(question["source_class"], question["grade"], risks, question):
            usable.append(question)
    source_counts = Counter(row["source_class"] for row in sources)
    grades = Counter(row["grade"] for row in unique)
    topic_counts = Counter(row["competition_topic"] for row in usable)
    status = "CORPUS_READY" if len(usable) >= 100 else "CORPUS_INSUFFICIENT"
    audit = {"sources_scanned": len(sources), "source_counts": dict(source_counts),
        "raw_questions": len(raw), "unique_questions": len(unique), "duplicates_removed": duplicates,
        "source_quality_rejected": len(quality), "usable_competition_questions": len(usable),
        "grade_counts": {grade: grades[grade] for grade in ("G1", "G2", "G3", "G4", "G5", "G6")},
        "out_of_scope_elementary": sum("OUT_OF_SCOPE_ELEMENTARY" in row["risks"] for row in quality),
        "quality_counts": dict(Counter(risk for row in quality for risk in row["risks"])),
        "topic_groups": len(topic_counts), "competitions_sources_represented": len({r["source"] for r in usable}),
        "years_represented": 0, "largest_topic_share": round(max(topic_counts.values()) / len(usable), 4) if usable else 0,
        "pilot_target": 100, "pilot_selected": min(100, len(usable)),
        "additional_questions_needed": max(0, 100 - len(usable)), "status": status,
        "api_calls": 0, "gemini_calls": 0, "deepseek_calls": 0,
        "production_reads": 0, "production_writes": 0, "supabase_used": False}
    INVENTORY_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(INVENTORY_CSV, sources, ["source", "source_class", "rows", "grade", "reason"])
    SOURCE_AUDIT.write_text(json.dumps({"sources": sources}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    QUALITY_QUEUE.write_text(json.dumps({"items": quality}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    UNIQUE_JSONL.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in unique), encoding="utf-8")
    if len(usable) >= 100:
        selected = select_pilot(usable, 100)
        PILOT_JSONL.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected), encoding="utf-8")
        PILOT_MANIFEST.write_text(json.dumps({"questions": selected}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
