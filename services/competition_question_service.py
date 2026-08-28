"""Local-only adapter for verified ELMC competition questions.

The adapter reads the Stage 7 source-grounded artifact when present.  It never
falls back to quarantined OCR, excluded records, or external services.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_VERIFIED_PATH = Path(
    r"C:\MathAI_Stage7_Pilot\.local\stage7_elementary_competition"
) / "elmc_competition_final_verified.jsonl"


@lru_cache(maxsize=1)
def load_verified_competition_questions() -> tuple[dict[str, Any], ...]:
    path = Path(os.getenv("MATHAI_ELMC_VERIFIED_PATH", str(DEFAULT_VERIFIED_PATH)))
    if not path.is_file():
        return ()
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (
            row.get("final_corpus_status") != "VERIFIED"
            or row.get("source_verification") != "KEEP"
            or row.get("competition_type") not in {"INDIVIDUAL", "TEAM"}
            or row.get("primary_skill_id") in {None, "", "NEW_SKILL_CANDIDATE"}
            or row.get("primary_micro_skill_id") in {None, "", "NEW_MICRO_CANDIDATE"}
        ):
            continue
        rows.append({
            "id": row["question_id"],
            "question_id": row["question_id"],
            "grade": int(str(row.get("approximate_grade", "G6")).lstrip("G")) if str(row.get("approximate_grade", "G6")).lstrip("G").isdigit() else 6,
            "publisher": "參加數學競賽",
            "semester": "上學期",
            "official_subunit": row.get("topic") or "ELMC 競賽題",
            "skill_id": row["primary_skill_id"],
            "micro_skill_id": row["primary_micro_skill_id"],
            "question_type": row.get("question_type") or "競賽題",
            "difficulty": row.get("difficulty") or "挑戰",
            "variation_level": 4,
            "question": row.get("question_summary") or "（請參閱原始競賽題目圖像）",
            "answer": row.get("answer") or "",
            "solution": row.get("solution") or "",
            "source": "ELMC_SOURCE_VERIFIED",
            "source_reference": row.get("source_verification_note", ""),
            "visual_required": bool(row.get("visual_required", True)),
            "edition": row.get("edition"),
            "competition_type": row.get("competition_type"),
            "question_number": row.get("question_number"),
        })
    return tuple(rows)


def competition_question_bank(*, grade: int, publisher: str, semester: str) -> tuple[dict[str, Any], ...]:
    if grade != 6 or publisher != "參加數學競賽":
        return ()
    return load_verified_competition_questions()


def competition_bank_counts(*, grade: int, publisher: str, semester: str) -> tuple[int, int]:
    rows = competition_question_bank(grade=grade, publisher=publisher, semester=semester)
    return len(rows), len(rows)
