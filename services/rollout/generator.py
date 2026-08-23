"""G1-G9 Rollout Engine — Grade Template Generator / scaffold (Phase 6).

Given a ``grade_id``, produce the standard data skeleton for that grade:
core-knowledge template, question-type template, publisher-mapping template,
checkpoint template, and a validation stub.  The generator never overwrites an
existing artifact — G7 (and any already-authored grade) is protected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .registry import _load_registry, empty_publisher_mapping
from .schema import SEMESTERS

_SAMPLE_KNOWLEDGE_POINT = {
    "id": "",
    "grade": None,
    "semester": "",
    "domain": "",
    "core_topic": "",
    "subunit": "",
    "curriculum_codes": [],
    "concepts": [],
    "prerequisite_knowledge_ids": [],
    "follow_up_knowledge_ids": [],
}

_SAMPLE_QUESTION_TYPE = {
    "type_id": "",
    "name": "",
    "category": "",
    "difficulty": "",
    "solving_strategy": "",
    "key_steps": [],
    "common_error_diagnosis": {"category": "", "error": "", "diagnosis": ""},
    "underlying_principle": "",
    "prerequisite_knowledge_ids": [],
    "follow_up_knowledge_ids": [],
    "variation_methods": [],
    "recommended_difficulty_range": {"min_level": 1, "max_level": 2, "default_level": 1},
    "thinking_skill_ids": [],
}

_SAMPLE_CHECKPOINT = {
    "id": "",
    "semester": "",
    "name": "",
    "core_ids": [],
    "threshold": 0.80,
    "composition": {"基礎核心題": 3, "數字變形題": 2, "中等應用題": 2, "陌生題": 1, "跨單元題": 1},
}


def generate_grade_template(grade: int) -> Mapping[str, Any]:
    """Return the standard, schema-compatible skeleton template for a grade."""
    if grade not in range(1, 10):
        raise ValueError("grade must be 1-9")
    raw = _load_registry()
    entry = raw["grades"].get(str(grade))
    if entry is None:
        raise ValueError(f"unknown grade {grade}")
    return {
        "schema_version": "2.0",
        "grade": grade,
        "status": entry["status"],
        "display_name": f"MathAI G{grade} Learning Map (Skeleton)",
        "semesters": list(entry["semesters"]),
        "domains": list(entry["domains"]),
        "knowledge_points": [],
        "question_type_catalog": [],
        "publisher_mapping": empty_publisher_mapping(grade),
        "checkpoints": [],
        "templates": {
            "knowledge_point": _SAMPLE_KNOWLEDGE_POINT,
            "question_type": _SAMPLE_QUESTION_TYPE,
            "checkpoint": _SAMPLE_CHECKPOINT,
        },
    }


def scaffold_grade(grade: int, out_path: str | Path, *, overwrite: bool = False) -> Path:
    """Write a grade skeleton to ``out_path``.

    Refuses to overwrite an existing file unless ``overwrite=True`` — this is
    the guard that prevents clobbering authored (formal) grade data.
    """
    target = Path(out_path)
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"refusing to overwrite existing artifact {target}; set overwrite=True to force"
        )
    import json

    payload = generate_grade_template(grade)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target
