"""Fail-closed elementary competition corpus metadata and quality rules."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from typing import Any

SOURCE_CLASSES = frozenset({"EXPLICIT_COMPETITION", "COMPETITION_CANDIDATE",
    "GENERAL_ADVANCED", "PRIVATE_JH", "GENERAL_CURRICULUM", "UNKNOWN"})
PILOT_ALLOWED_SOURCE_CLASSES = frozenset({"EXPLICIT_COMPETITION"})
ELEMENTARY_GRADES = frozenset({"G1", "G2", "G3", "G4", "G5", "G6"})
PILOT_PRIORITY_GRADES = frozenset({"G4", "G5", "G6"})

COMPETITION_TOPICS = {
    "NUMBER_PATTERN": "數列與數字規律", "ARITHMETIC_TRICKS": "巧算／運算規律",
    "DIVISIBILITY": "整除／因數／倍數", "COUNTING": "排列組合／系統列舉",
    "LOGIC": "邏輯推理", "PIGEONHOLE": "抽屜原理", "INVARIANT": "不變量",
    "PARITY": "奇偶性", "NUMBER_THEORY": "初等數論", "WORD_PROBLEM": "高階文字題",
    "RATE": "速率", "WORK": "工程／工作量", "AGES": "年齡",
    "CHICKEN_RABBIT": "雞兔／雙條件推理", "GEOMETRY": "平面幾何",
    "AREA_CUTTING": "面積切割重組", "SOLID_GEOMETRY": "立體幾何",
    "COUNTING_GEOMETRY": "數圖形", "GRAPH_PATH": "路徑／網格", "COMBINED": "跨單元綜合",
}
COMPETITION_THINKING_SKILLS = frozenset({"DIRECT_APPLICATION", "REVERSE_REASONING",
    "SYSTEMATIC_ENUMERATION", "CASE_SPLIT", "PATTERN_DISCOVERY", "INVARIANT_REASONING",
    "EXTREME_PRINCIPLE", "PARITY_REASONING", "CONSTRUCTION", "DECOMPOSITION",
    "TRANSFORMATION", "BACKWARD_REASONING", "MULTI_STEP_INFERENCE"})


def normalized_fingerprint(text: str) -> str:
    """Normalize presentation noise while preserving every digit and letter."""
    value = unicodedata.normalize("NFKC", str(text or "")).lower()
    value = re.sub(r"[\s\u3000]+", "", value)
    value = re.sub(r"[，。；：、,.!?！？;:'\"()（）\[\]【】]", "", value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def classify_source(metadata: dict[str, Any]) -> str:
    explicit = bool(metadata.get("official_competition_source") and metadata.get("source_url")
                    and metadata.get("competition_name"))
    if explicit:
        return "EXPLICIT_COMPETITION"
    profile = str(metadata.get("target_profile") or "").upper()
    if "PRIVATE" in profile or metadata.get("private_jh"):
        return "PRIVATE_JH"
    if "COMPETITION" in profile or metadata.get("competition_evidence"):
        return "COMPETITION_CANDIDATE"
    if metadata.get("general_curriculum"):
        return "GENERAL_CURRICULUM"
    if metadata.get("advanced") or metadata.get("gifted"):
        return "GENERAL_ADVANCED"
    return "UNKNOWN"


def source_quality_risks(question: dict[str, Any]) -> list[str]:
    text = str(question.get("question_text") or question.get("prompt") or "")
    visual = bool(question.get("visualization") or question.get("image") or question.get("page_crop"))
    risks: list[str] = []
    inherited = {"missing_required_diagram": "MISSING_REQUIRED_DIAGRAM",
        "missing_required_chart": "MISSING_REQUIRED_CHART",
        "fraction_notation_lost": "MATH_FRACTION_NOTATION_LOST",
        "expression_incomplete": "MATH_EXPRESSION_INCOMPLETE",
        "multi_document_contamination": "MULTI_DOCUMENT_CONTAMINATION"}
    risks.extend(risk for flag, risk in inherited.items() if question.get(flag))
    layout_rules = {"GEOMETRY_FIGURE_REQUIRED": r"(?:方格圖|圖形切割|點陣圖|天平圖)",
        "TABLE_LAYOUT_LOST": r"(?:數陣|數表|表格圖像)",
        "SEQUENCE_LAYOUT_LOST": r"(?:火柴棒圖|特殊符號排列)",
        "SPECIAL_SYMBOL_LOST": r"(?:特殊符號|自訂運算符)"}
    for risk, pattern in layout_rules.items():
        if re.search(pattern, text) and not visual:
            risks.append(risk)
    if question.get("scope_status") == "OUT_OF_SCOPE_ELEMENTARY":
        risks.append("OUT_OF_SCOPE_ELEMENTARY")
    return sorted(set(risks))


def pilot_eligible(source_class: str, grade: str, risks: list[str], metadata: dict[str, Any]) -> bool:
    return (source_class in PILOT_ALLOWED_SOURCE_CLASSES and grade in ELEMENTARY_GRADES and not risks
            and bool(metadata.get("source_complete")) and bool(metadata.get("source_url")))


def select_pilot(candidates: list[dict[str, Any]], target: int = 100) -> list[dict[str, Any]]:
    """Deterministic diversity-first selection with a 25% topic ceiling."""
    eligible = [row for row in candidates if pilot_eligible(row.get("source_class", ""),
        row.get("grade", ""), row.get("risks", []), row)]
    unique = {row["fingerprint"]: row for row in eligible}
    if len(unique) < target:
        raise RuntimeError(f"CORPUS_INSUFFICIENT:{len(unique)}/{target}")
    pool = list(unique.values()); selected: list[dict[str, Any]] = []
    topics: Counter[str] = Counter(); sources: Counter[str] = Counter(); years: Counter[str] = Counter()
    topic_cap = max(1, target // 4)
    while len(selected) < target:
        choices = [row for row in pool if topics[row["competition_topic"]] < topic_cap]
        if not choices:
            raise RuntimeError("PILOT_DIVERSITY_UNSATISFIABLE")
        choice = min(choices, key=lambda row: (topics[row["competition_topic"]],
            sources[str(row.get("source"))], years[str(row.get("year"))],
            row.get("grade") not in PILOT_PRIORITY_GRADES, row["fingerprint"]))
        selected.append(choice); pool.remove(choice)
        topics[choice["competition_topic"]] += 1
        sources[str(choice.get("source"))] += 1; years[str(choice.get("year"))] += 1
    return selected
