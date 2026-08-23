"""G7 Gold Template builder — the enrichment layer over ``learning_map_g7.json``.

This module turns the existing G7 core knowledge tree + publisher mapping +
164-question-type catalog into the reusable **Gold Template** that future
G1-G9 rollouts will consume.  It is deliberately *non-destructive*: the
original ``learning_map_g7.json`` stays the source of truth for stable IDs
(``G7-C01``..``G7-C23`` and every ``type_id``), and this module only *derives*
the additional instructional fields.

Enrichment responsibilities (Phases 1-3 of the Gold Template plan):

* Phase 1 — for every question type, add ``solving_strategy``, ``key_steps``,
  ``common_error_diagnosis``, ``underlying_principle``,
  ``prerequisite_knowledge_ids``, ``follow_up_knowledge_ids``,
  ``variation_methods``, ``recommended_difficulty_range``.
* Phase 2 — G1-G9 thinking-skill taxonomy + QuestionType <-> ThinkingSkill
  many-to-many mapping (stable IDs, none G7-specific).
* Phase 3 — the unified five-level difficulty/variation framework (L1-L5) and
  per-question-type min/max/default level.

The existing curated fields are *reused*, not rewritten: ``skill`` feeds
``solving_strategy``, ``principle`` feeds ``underlying_principle``, and
``common_error`` + ``diagnostic_clue`` feed the structured
``common_error_diagnosis``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_G7_FILE = Path(__file__).resolve().parents[1] / "learning_map_g7.json"
_THINKING_SKILLS_FILE = _DATA_DIR / "thinking_skills_gold.json"

# ---------------------------------------------------------------------------
# Phase 3 — five-level difficulty / variation framework
# ---------------------------------------------------------------------------

DIFFICULTY_LEVELS: Mapping[int, Mapping[str, str]] = {
    1: {"id": "L1", "name": "Prototype", "label": "原型題", "description": "主要改數字"},
    2: {"id": "L2", "name": "Variant", "label": "變形題", "description": "同觀念改條件／問法"},
    3: {"id": "L3", "name": "Reasoning", "label": "推理題", "description": "逆向、缺步驟、多步驟"},
    4: {"id": "L4", "name": "Integration", "label": "整合題", "description": "多題型或跨知識點"},
    5: {"id": "L5", "name": "Challenge", "label": "挑戰題", "description": "陌生情境／素養／資優型"},
}

VARIATION_METHODS: Mapping[int, str] = {
    1: "更換數字／情境數值",
    2: "改條件／問法（同觀念）",
    3: "逆向／缺步驟／多步驟推理",
    4: "多題型／跨知識點整合",
    5: "陌生情境／素養／資優挑戰",
}

# Existing 3-level publisher difficulty -> (min_level, max_level, default_level)
_DIFFICULTY_RANGE: Mapping[str, tuple[int, int, int]] = {
    "基礎": (1, 2, 1),
    "標準": (2, 3, 2),
    "進階": (3, 4, 3),
}

# Categories whose content legitimately reaches L5 (cross-unit / literacy).
_CHALLENGE_HINT = ("素養", "綜合", "整合", "跨", "資優")

# ---------------------------------------------------------------------------
# Phase 1 — common-error diagnosis taxonomy (8 categories)
# ---------------------------------------------------------------------------

ERROR_TAXONOMY: tuple[tuple[str, str], ...] = (
    ("概念錯誤", "概念錯誤"),
    ("符號錯誤", "符號錯誤"),
    ("程序錯誤", "程序錯誤"),
    ("條件擷取錯誤", "條件擷取錯誤"),
    ("模型建立錯誤", "模型建立錯誤"),
    ("運算錯誤", "運算錯誤"),
    ("策略選擇錯誤", "策略選擇錯誤"),
    ("驗證不足", "驗證不足"),
)

_ERROR_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("概念錯誤", ("誤當成", "混淆", "誤解", "概念", "定義", "不理解", "認為", "不知道", "意義")),
    ("符號錯誤", ("符號", "正負", "負號", "括號", "方向", "大小於", "不等號", "移項", "正負號")),
    ("條件擷取錯誤", ("漏讀", "看漏", "沒看到", "條件", "已知", "未知", "題目", "情境", "遺漏條件")),
    ("模型建立錯誤", ("列式", "未知數", "方程", "模型", "關係式", "設", "對應", "表示", "轉譯")),
    ("策略選擇錯誤", ("策略", "方法", "試", "猜", "反查", "估算", "直接")),
    ("驗證不足", ("驗證", "驗算", "檢核", "代回", "檢查", "未驗")),
    ("程序錯誤", ("步驟", "順序", "漏", "跳", "遺漏", "程序", "先後", "缺少", "忽略", "過程")),
    ("運算錯誤", ("計算", "算錯", "運算", "進位", "退位", "約分", "通分", "乘除", "加減", "小數", "錯誤")),
)

# category -> default error category when no keyword matches
_CATEGORY_DEFAULT_ERROR = (
    (("計算", "運算", "數感", "代數運算"), "運算錯誤"),
    (("觀念", "定義", "表示"), "概念錯誤"),
    (("圖形", "幾何", "空間"), "程序錯誤"),
    (("素養", "情境", "應用", "綜合"), "模型建立錯誤"),
)

# ---------------------------------------------------------------------------
# Phase 1 — prerequisite / follow-up graph (curated from textbook progression)
# ---------------------------------------------------------------------------

_PREREQUISITE_CORE: Mapping[str, tuple[str, ...]] = {
    "G7-C01": (),
    "G7-C02": ("G7-C01",),
    "G7-C03": ("G7-C02",),
    "G7-C04": ("G7-C03",),
    "G7-C05": ("G7-C03",),
    "G7-C06": ("G7-C05",),
    "G7-C07": ("G7-C03", "G7-C06"),
    "G7-C08": ("G7-C04",),
    "G7-C09": ("G7-C03", "G7-C07"),
    "G7-C10": ("G7-C09",),
    "G7-C11": ("G7-C10",),
    "G7-C12": ("G7-C10",),
    "G7-C13": ("G7-C12",),
    "G7-C14": ("G7-C13",),
    "G7-C15": ("G7-C01",),
    "G7-C16": ("G7-C12", "G7-C15"),
    "G7-C17": ("G7-C07",),
    "G7-C18": ("G7-C17",),
    "G7-C19": ("G7-C09",),
    "G7-C20": ("G7-C19",),
    "G7-C21": ("G7-C03", "G7-C07"),
    "G7-C22": ("G7-C21",),
    "G7-C23": ("G7-C01", "G7-C15"),
}


def _follow_up_core() -> Mapping[str, tuple[str, ...]]:
    follow: dict[str, list[str]] = {cid: [] for cid in _PREREQUISITE_CORE}
    for cid, prereqs in _PREREQUISITE_CORE.items():
        for prereq in prereqs:
            follow[prereq].append(cid)
    return {cid: tuple(sorted(ids)) for cid, ids in follow.items()}


_FOLLOW_UP_CORE = _follow_up_core()

# ---------------------------------------------------------------------------
# Phase 2 — QuestionType -> ThinkingSkill mapping
# ---------------------------------------------------------------------------

# category keyword -> primary thinking skill(s)
_CATEGORY_SKILLS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("統計", "圖表", "資料", "折線", "長條"), ("TS-GRAPH", "TS-TABLE")),
    (("幾何", "空間", "圖形", "作圖", "立體"), ("TS-SPATIAL", "TS-DRAW")),
    (("坐標", "數線"), ("TS-DRAW",)),
    (("方程", "不等式", "聯立"), ("TS-MODEL", "TS-TRANSLATE")),
    (("代數", "式", "設"), ("TS-TRANSLATE", "TS-EQUIV", "TS-ASSUME")),
    (("計算", "運算"), ("TS-SIMPLIFY", "TS-EQUIV")),
    (("觀念", "定義", "表示"), ("TS-DEFINE", "TS-READ")),
    (("應用", "情境", "素養"), ("TS-TRANSLATE", "TS-MODEL")),
    (("推理"), ("TS-LOGIC", "TS-FORWARD")),
    (("策略"), ("TS-STRATEGY",)),
    (("規律"), ("TS-PATTERN",)),
    (("比例", "單位", "換算"), ("TS-RELATE", "TS-UNIT")),
    (("比較"), ("TS-DIFF",)),
    (("分類"), ("TS-CASE",)),
)

# feature/skill text keyword -> extra supporting thinking skill(s)
_TEXT_SKILLS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("逆向", ("TS-BACKWARD",)),
    ("反推", ("TS-BACKWARD",)),
    ("多步驟", ("TS-MULTI",)),
    ("缺步驟", ("TS-MULTI",)),
    ("跨單元", ("TS-INTEGRATE",)),
    ("整合", ("TS-INTEGRATE",)),
    ("規律", ("TS-PATTERN",)),
    ("列舉", ("TS-ENUM",)),
    ("分類討論", ("TS-CASE",)),
    ("估算", ("TS-ESTIMATE",)),
    ("驗算", ("TS-CHECK", "TS-ERROR")),
    ("檢查", ("TS-CHECK", "TS-ERROR")),
    ("假設", ("TS-ASSUME",)),
    ("單位量", ("TS-UNIT",)),
    ("差量", ("TS-DIFF",)),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_g7() -> Mapping[str, Any]:
    return json.loads(_G7_FILE.read_text(encoding="utf-8"))


def _load_thinking_skills() -> tuple[Mapping[str, Any], ...]:
    raw = json.loads(_THINKING_SKILLS_FILE.read_text(encoding="utf-8"))
    return tuple(raw.get("skills", ()))


def _split_clauses(text: str) -> list[str]:
    """Split a Chinese strategy sentence into stable step clauses."""
    parts = [p.strip() for p in re.split(r"[，。；、]|(?=最後|接著|然後|再)", text or "") if p.strip()]
    # drop over-short fragments unless they are the only fragment
    if len(parts) > 1:
        parts = [p for p in parts if len(p) >= 3]
    return parts or ([text.strip()] if text and text.strip() else [])


def _extract_steps(feature: str, skill: str, category: str) -> tuple[str, ...]:
    steps: list[str] = []
    if feature and feature.strip():
        steps.append(f"辨識題型：{feature.strip()}")
    skill_steps = _split_clauses(skill)
    if skill_steps:
        steps.extend(skill_steps)
    if len(steps) < 2:
        steps.append("依題型選定合適的計算或推理策略並逐步執行")
    if len(steps) < 3:
        steps.append("代回原題條件，檢查答案與單位是否合理")
    return tuple(dict.fromkeys(steps))


def _classify_error(common_error: str, category: str) -> str:
    text = common_error or ""
    for label, keywords in _ERROR_KEYWORDS:
        if any(kw in text for kw in keywords):
            return label
    for keys, default in _CATEGORY_DEFAULT_ERROR:
        if any(kw in category for kw in keys):
            return default
    return "程序錯誤"


def _thinking_skill_ids(category: str, name: str, feature: str, skill: str) -> tuple[str, ...]:
    ids: list[str] = []
    text = (category or "") + (name or "") + (feature or "") + (skill or "")
    for keys, skills in _CATEGORY_SKILLS:
        if any(kw in category for kw in keys):
            ids.extend(skills)
    for key, skills in _TEXT_SKILLS:
        if key in text:
            ids.extend(skills)
    if not ids:
        ids.append("TS-READ")
    ids.append("TS-CHECK")
    return tuple(dict.fromkeys(ids))


def _difficulty_range(difficulty: str, category: str) -> Mapping[str, int]:
    lo, hi, default = _DIFFICULTY_RANGE.get(difficulty, (2, 3, 2))
    if any(hint in category for hint in _CHALLENGE_HINT):
        hi = max(hi, 5)
    return {"min_level": lo, "max_level": hi, "default_level": default}


def _variation_methods(lo: int, hi: int) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        {
            "level": level,
            "level_id": DIFFICULTY_LEVELS[level]["id"],
            "label": DIFFICULTY_LEVELS[level]["label"],
            "method": VARIATION_METHODS[level],
        }
        for level in range(lo, hi + 1)
    )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _enrich_question_type(qtype: Mapping[str, Any], core_id: str) -> Mapping[str, Any]:
    category = str(qtype.get("category") or "")
    difficulty = str(qtype.get("difficulty") or "標準")
    feature = str(qtype.get("feature") or "")
    skill = str(qtype.get("skill") or "")
    principle = str(qtype.get("principle") or "")
    common_error = str(qtype.get("common_error") or "")
    diagnostic_clue = str(qtype.get("diagnostic_clue") or "")
    name = str(qtype.get("name") or "")

    rng = _difficulty_range(difficulty, category)
    enriched = dict(qtype)
    enriched["solving_strategy"] = skill
    enriched["key_steps"] = _extract_steps(feature, skill, category)
    enriched["common_error_diagnosis"] = {
        "category": _classify_error(common_error, category),
        "error": common_error,
        "diagnosis": diagnostic_clue,
    }
    enriched["underlying_principle"] = principle
    enriched["prerequisite_knowledge_ids"] = list(_PREREQUISITE_CORE.get(core_id, ()))
    enriched["follow_up_knowledge_ids"] = list(_FOLLOW_UP_CORE.get(core_id, ()))
    enriched["recommended_difficulty_range"] = rng
    enriched["variation_methods"] = _variation_methods(rng["min_level"], rng["max_level"])
    enriched["thinking_skill_ids"] = _thinking_skill_ids(category, name, feature, skill)
    return enriched


def _enrich_core(core_id: str, core: Mapping[str, Any]) -> Mapping[str, Any]:
    enriched = dict(core)
    enriched["prerequisite_knowledge_ids"] = list(_PREREQUISITE_CORE.get(core_id, ()))
    enriched["follow_up_knowledge_ids"] = list(_FOLLOW_UP_CORE.get(core_id, ()))
    enriched["question_type_catalog"] = [
        _enrich_question_type(q, core_id) for q in core.get("question_type_catalog", ())
    ]
    return enriched


def build_gold_template() -> Mapping[str, Any]:
    """Build the complete G7 Gold Template (enriched, non-destructive)."""
    g7 = _load_g7()
    skills = _load_thinking_skills()
    core = {
        cid: _enrich_core(cid, node)
        for cid, node in sorted(g7.get("core", {}).items())
    }
    type_map: dict[str, tuple[str, ...]] = {}
    for cid, node in core.items():
        for q in node["question_type_catalog"]:
            type_map[str(q["type_id"])] = tuple(q["thinking_skill_ids"])

    question_type_total = sum(
        len(node["question_type_catalog"]) for node in core.values()
    )
    return {
        "schema_version": "2.0",
        "grade": 7,
        "display_name": "MathAI G7 Learning Map Gold Template",
        "core_knowledge_total": len(core),
        "question_type_total": question_type_total,
        "thinking_skill_total": len(skills),
        "core": core,
        "publishers": g7.get("publishers", {}),
        "thinking_skills": skills,
        "difficulty_framework": {
            "levels": DIFFICULTY_LEVELS,
            "variation_methods": VARIATION_METHODS,
        },
        "error_taxonomy": [{"category": label, "label": label} for label, _ in ERROR_TAXONOMY],
        "prerequisite_graph": {cid: list(ids) for cid, ids in _PREREQUISITE_CORE.items()},
        "follow_up_graph": {cid: list(ids) for cid, ids in _FOLLOW_UP_CORE.items()},
        "question_type_skill_map": type_map,
    }


_GOLD_CACHE: Mapping[str, Any] | None = None


def get_gold_template() -> Mapping[str, Any]:
    global _GOLD_CACHE
    if _GOLD_CACHE is None:
        _GOLD_CACHE = build_gold_template()
    return _GOLD_CACHE


def get_question_type(type_id: str) -> Mapping[str, Any] | None:
    """Look up one enriched question type by stable ``type_id``."""
    for node in get_gold_template()["core"].values():
        for q in node["question_type_catalog"]:
            if q.get("type_id") == type_id:
                return q
    return None


def all_question_types() -> tuple[Mapping[str, Any], ...]:
    return tuple(
        q
        for node in get_gold_template()["core"].values()
        for q in node["question_type_catalog"]
    )


def thinking_skill_by_id() -> Mapping[str, Mapping[str, Any]]:
    return {str(s["id"]): s for s in _load_thinking_skills()}
