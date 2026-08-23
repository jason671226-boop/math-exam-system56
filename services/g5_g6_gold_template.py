"""G5 / G6 Gold Template builder.

Upgrades the existing publisher-neutral baselines (``learning_map_g5_baseline.json``
and ``learning_map_g6_pilot.json``) into the full Gold Template standard, reusing
the G1-G9 shared machinery built for G7 (thinking-skill taxonomy, L1-L5 difficulty,
eight-category error diagnosis, evidence/mastery/recommendation).

Principles honoured here:
  * Preserve, don't regenerate: the baseline knowledge points are the source of
    truth for the core knowledge tree; they are standardised into stable IDs
    (``G5-C##`` / ``G6-C##``) but never rewritten or duplicated.
  * Publisher-neutral core + publisher path mapping: publisher chapter tables are
    emitted as an explicit ``NEEDS_VERIFICATION`` skeleton — we do not fabricate
    康軒 / 翰林 / 南一 chapter names for G5/G6 without a reliable source.
  * Curriculum codes remain empty (``NEEDS_VERIFICATION``) until an authoritative
    108-curriculum mapping is confirmed.
  * Question-type enrichment (strategy, principle, error diagnosis) is *derived*
    from the baseline ``learning_focus`` / ``description`` and labelled
    ``derived_pending_verification``, not presented as verified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from services.g7_gold_template import (
    DIFFICULTY_LEVELS,
    ERROR_TAXONOMY,
    VARIATION_METHODS,
    _classify_error,
    _difficulty_range,
    _extract_steps,
    _thinking_skill_ids,
    _variation_methods,
    thinking_skill_by_id,
)

from .rollout.schema import (
    PUBLISHERS,
    SEMESTERS,
    GradeRecord,
    KnowledgePoint,
    QuestionTypeRecord,
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_SOURCE_FILE = {
    5: _DATA_DIR / "learning_map_g5_baseline.json",
    6: _DATA_DIR / "learning_map_g6_pilot.json",
}

_DATA_STATUS = "derived_pending_verification"

# Per-category common-error / diagnosis templates (honest, category-level).
_ERROR_TEMPLATES: Mapping[str, tuple[str, str]] = {
    "概念錯誤": ("對{unit}的核心概念理解不完整", "先確認定義與基本原則，而非只記表面步驟"),
    "符號錯誤": ("符號、比較方向或括號使用出錯", "檢查符號約定與方向是否一致"),
    "程序錯誤": ("解題步驟的順序或完整性不足", "把流程拆成明確步驟逐一核對"),
    "條件擷取錯誤": ("遺漏或誤讀題目中的條件", "回讀題目，圈出已知、未知與限制"),
    "模型建立錯誤": ("未能把情境轉成正確的數量關係或算式", "先建立數量關係，再轉成算式"),
    "運算錯誤": ("進退位、小數點或運算順序出錯", "放慢計算並以逆算或估算驗證"),
    "策略選擇錯誤": ("選用了較繁瑣或不適用的解法", "比較多種可行方法再選擇較佳策略"),
    "驗證不足": ("未回代或檢查答案的合理性", "把答案代回原題並檢查單位與範圍"),
}


def _load_baseline(grade: int) -> list[Mapping[str, Any]]:
    raw = json.loads(_SOURCE_FILE[grade].read_text(encoding="utf-8"))
    points = list(raw.get("knowledge_points", ()))
    return sorted(points, key=lambda p: p.get("sort_order", 0))


def _derive_category(main_unit: str, sub_unit: str, label: str) -> str:
    """Derive a coarse question-type category from the domain/subunit/label."""
    text = f"{main_unit}{sub_unit}{label}"
    if any(k in text for k in ("圖形", "幾何", "面積", "周長", "角度", "立體", "對稱")):
        return "幾何／圖形"
    if any(k in text for k in ("應用", "情境", "文字", "問題", "行程")):
        return "應用／情境"
    if any(k in text for k in ("規律", "週期", "數列")):
        return "規律"
    if any(k in text for k in ("推理", "邏輯", "假設", "反推")):
        return "推理"
    if any(k in text for k in ("圖表", "統計", "資料", "可能性", "機率")):
        return "資料／機率"
    if any(k in text for k in ("因數", "倍數", "質數", "整除", "餘數")):
        return "數論"
    if any(k in text for k in ("分數", "小數", "比", "比值", "換算", "單位")):
        return "數感／數量關係"
    return "計算"


def _common_error_diagnosis(category: str, sub_unit: str, label: str) -> Mapping[str, str]:
    """Derive a category-level, honest common-error diagnosis."""
    # classify a concrete error category from the label/subunit text
    error_category = _classify_error(f"{label}{sub_unit}", category)
    error_template, diagnosis = _ERROR_TEMPLATES.get(error_category, _ERROR_TEMPLATES["程序錯誤"])
    return {
        "category": error_category,
        "error": error_template.format(unit=sub_unit),
        "diagnosis": diagnosis,
        "evidence_status": _DATA_STATUS,
    }


def _build_question_type(
    label: str,
    *,
    knowledge_id: str,
    main_unit: str,
    sub_unit: str,
    learning_focus: str,
    description: str,
    index: int,
) -> Mapping[str, Any]:
    category = _derive_category(main_unit, sub_unit, label)
    difficulty = "標準"
    rng = _difficulty_range(difficulty, category)
    strategy = learning_focus or f"依題意逐步完成「{label}」的計算或推理"
    steps = _extract_steps(f"{label}：{description}" if description else label, strategy, category)
    return {
        "type_id": f"{knowledge_id}-Q{index:02d}",
        "name": label,
        "category": category,
        "difficulty": difficulty,
        "feature": f"{sub_unit}（{label}）",
        "solving_strategy": strategy,
        "key_steps": steps,
        "common_error_diagnosis": _common_error_diagnosis(category, sub_unit, label),
        "underlying_principle": description or learning_focus,
        "prerequisite_knowledge_ids": [],
        "follow_up_knowledge_ids": [],
        "variation_methods": _variation_methods(rng["min_level"], rng["max_level"]),
        "recommended_difficulty_range": rng,
        "thinking_skill_ids": _thinking_skill_ids(category, label, strategy, description),
        "data_status": _DATA_STATUS,
    }


def _semester_for(index: int, total: int) -> str:
    return SEMESTERS[0] if index < (total + 1) // 2 else SEMESTERS[1]


def _normalize_domain(main_unit: str) -> str:
    if any(k in main_unit for k in ("幾何", "圖形", "空間", "立體")):
        return "空間與形狀"
    if any(k in main_unit for k in ("可能性", "計數", "統計", "資料")):
        return "資料與不確定性"
    if any(k in main_unit for k in ("等量", "方程", "代數")):
        return "代數"
    return "數與量"


def build_grade_template(grade: int) -> Mapping[str, Any]:
    if grade not in (5, 6):
        raise ValueError("only G5 and G6 are supported here")
    points = _load_baseline(grade)
    total = len(points)

    # stable-ID remap: baseline id (G5-K###) -> core id (G5-C##) by sort order
    id_map: dict[str, str] = {}
    for i, point in enumerate(points, start=1):
        id_map[str(point["id"])] = f"G{grade}-C{i:02d}"

    core: list[Mapping[str, Any]] = []
    question_types: list[QuestionTypeRecord] = []
    knowledge_points: list[KnowledgePoint] = []

    for i, point in enumerate(points):
        cid = id_map[str(point["id"])]
        main_unit = str(point.get("main_unit") or "")
        sub_unit = str(point.get("sub_unit") or "")
        domain = _normalize_domain(main_unit)
        semester = _semester_for(i, total)
        learning_focus = str(point.get("learning_focus") or "")
        description = str(point.get("description") or "")
        prereq = tuple(id_map[p] for p in point.get("prerequisite_ids", []) if p in id_map)

        qt_records: list[QuestionTypeRecord] = []
        for qi, label in enumerate(point.get("question_types", ()), start=1):
            qt = _build_question_type(
                str(label),
                knowledge_id=cid,
                main_unit=main_unit,
                sub_unit=sub_unit,
                learning_focus=learning_focus,
                description=description,
                index=qi,
            )
            qt_records.append(QuestionTypeRecord(
                type_id=str(qt["type_id"]),
                knowledge_id=cid,
                name=str(qt["name"]),
                category=str(qt["category"]),
                difficulty=str(qt["difficulty"]),
                solving_strategy=str(qt["solving_strategy"]),
                key_steps=tuple(qt["key_steps"]),
                common_error_diagnosis=dict(qt["common_error_diagnosis"]),
                underlying_principle=str(qt["underlying_principle"]),
                prerequisite_knowledge_ids=tuple(qt["prerequisite_knowledge_ids"]),
                follow_up_knowledge_ids=tuple(qt["follow_up_knowledge_ids"]),
                variation_methods=tuple(qt["variation_methods"]),
                recommended_difficulty_range=dict(qt["recommended_difficulty_range"]),
                thinking_skill_ids=tuple(qt["thinking_skill_ids"]),
            ))
        question_types.extend(qt_records)

        knowledge_points.append(KnowledgePoint(
            id=cid,
            grade=grade,
            semester=semester,
            domain=domain,
            core_topic=main_unit,
            subunit=sub_unit,
            curriculum_codes=(),  # NEEDS_VERIFICATION
            prerequisite_ids=prereq,
            follow_up_ids=(),
        ))

    # follow-up = inverse of prerequisite
    follow_up: dict[str, list[str]] = {p.id: [] for p in knowledge_points}
    for p in knowledge_points:
        for prereq in p.prerequisite_ids:
            follow_up.setdefault(prereq, []).append(p.id)
    knowledge_points = [
        KnowledgePoint(
            id=p.id, grade=p.grade, semester=p.semester, domain=p.domain,
            core_topic=p.core_topic, subunit=p.subunit, curriculum_codes=p.curriculum_codes,
            prerequisite_ids=p.prerequisite_ids,
            follow_up_ids=tuple(dict.fromkeys(follow_up.get(p.id, ()))),
        )
        for p in knowledge_points
    ]

    prereq_graph = {p.id: p.prerequisite_ids for p in knowledge_points}
    follow_graph = {p.id: p.follow_up_ids for p in knowledge_points}

    return {
        "schema_version": "2.0",
        "grade": grade,
        "display_name": f"MathAI G{grade} Learning Map (Gold Template)",
        "status": "formal",
        "source": f"learning_map_g{grade}_{'baseline' if grade == 5 else 'pilot'}.json",
        "data_status": _DATA_STATUS,
        "verification_note": (
            "Core knowledge standardised from the existing neutral baseline; "
            "publisher mapping and curriculum codes remain NEEDS_VERIFICATION."
        ),
        "semesters": list(SEMESTERS),
        "domains": sorted({p.domain for p in knowledge_points}),
        "knowledge_points": [p.__dict__ for p in knowledge_points],
        "question_types": [q.__dict__ for q in question_types],
        "prerequisite_graph": prereq_graph,
        "follow_up_graph": follow_graph,
        "publisher_mapping": {
            pub: {sem: {"units": [], "verification_status": "NEEDS_VERIFICATION"} for sem in SEMESTERS}
            for pub in PUBLISHERS
        },
        "thinking_skill_ids_used": sorted({sid for q in question_types for sid in q.thinking_skill_ids}),
    }


def _to_grade_record(grade: int, template: Mapping[str, Any]) -> GradeRecord:
    kps = [KnowledgePoint(**p) for p in template["knowledge_points"]]
    qts = [QuestionTypeRecord(**q) for q in template["question_types"]]
    return GradeRecord(
        grade_id=grade,
        semesters=tuple(template["semesters"]),
        domains=tuple(template["domains"]),
        status="formal",
        knowledge_points=tuple(kps),
        question_types=tuple(qts),
        publisher_mapping=template["publisher_mapping"],
        prerequisite_graph=dict(template["prerequisite_graph"]),
        follow_up_graph=dict(template["follow_up_graph"]),
    )


_CACHE: dict[int, GradeRecord] = {}


def get_grade_record(grade: int) -> GradeRecord:
    if grade not in (5, 6):
        raise ValueError("only G5 and G6 are supported here")
    if grade not in _CACHE:
        _CACHE[grade] = _to_grade_record(grade, build_grade_template(grade))
    return _CACHE[grade]
