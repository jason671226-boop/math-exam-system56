"""Deterministic rules for the Stage 7C public competition corpus pipeline."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from typing import Any, Iterable
from urllib.parse import urlparse

OFFICIAL_DOMAINS = frozenset({"imcct.net", "www.imcct.net", "mathkangaroo.org", "www.mathkangaroo.org"})
ELEMENTARY_GRADES = frozenset({"G3", "G4", "G5", "G6"})
QUALITY_RISKS = frozenset({
    "MISSING_REQUIRED_DIAGRAM", "MISSING_REQUIRED_CHART", "MATH_FRACTION_NOTATION_LOST",
    "MATH_EXPRESSION_INCOMPLETE", "MULTI_DOCUMENT_CONTAMINATION", "GEOMETRY_FIGURE_REQUIRED",
    "TABLE_LAYOUT_LOST", "SEQUENCE_LAYOUT_LOST", "SPECIAL_SYMBOL_LOST",
})

TOPIC_PATTERNS = (
    ("WORK", r"\u5de5\u4f5c|\u5de5\u8cc7|\u5de5\u8d44|\u6bcf\u4eba\u6bcf\u5929|\u5b8c\u6210.{0,8}\u5929"),
    ("AGES", r"\u5e74\u9f61|\u5e74\u9f84|\u6b72|\u5c81|age"),
    ("CHICKEN_RABBIT", r"\u96de\u5154|\u9e21\u5154|\u8173|\u811a"),
    ("AREA_CUTTING", r"\u5207\u5272|\u62fc|\u5857\u8272.{0,8}\u9762\u7a4d|\u7b49\u7a4d"),
    ("SOLID_GEOMETRY", r"\u9ad4\u7a4d|\u4f53\u79ef|\u7acb\u65b9|\u9577\u65b9\u9ad4|\u957f\u65b9\u4f53|\u6b63\u65b9\u9ad4|\u6b63\u65b9\u4f53|\u5c55\u958b\u5716|\u5c55\u5f00\u56fe"),
    ("COUNTING_GEOMETRY", r"\u591a\u5c11(?:\u500b|\u4e2a).{0,8}(?:\u4e09\u89d2|\u6b63\u65b9|\u9577\u65b9|\u957f\u65b9|\u5716\u5f62|\u56fe\u5f62)"),
    ("GRAPH_PATH", r"\u8def\u5f91|\u65b9\u683c|\u7db2\u683c|\u7f51\u683c|\u8d70\u6cd5|path|grid"),
    ("PARITY", r"\u5947\u6578|\u5947\u6570|\u5076\u6578|\u5076\u6570|\u5947\u5076|odd|even"),
    ("LOGIC", r"\u6b63\u78ba|\u6b63\u786e|\u932f\u8aa4|\u9519\u8bef|\u53ef\u80fd|\u4e0d\u53ef\u80fd|\u81f3\u5c11|\u81f3\u591a"),
    ("NUMBER_THEORY", r"\u9918\u6578|\u4f59\u6570|\u4e92\u8cea|\u4e92\u8d28|\u5e73\u65b9\u6578|\u5e73\u65b9\u6570|\u6578\u5b57\u548c|\u6570\u5b57\u548c"),
    ("GEOMETRY", r"\u5716|\u56fe|\u89d2|\u9762\u7a4d|\u5468\u9577|\u5468\u957f|\u6b63\u65b9|\u9577\u65b9|\u957f\u65b9|\u4e09\u89d2|\u5713|\u5706|rectangle|triangle|square"),
    ("DIVISIBILITY", r"\u56e0\u6578|\u56e0\u6570|\u500d\u6578|\u500d\u6570|\u6574\u9664|\u8cea\u6578|\u8d28\u6570|\u5408\u6578|\u5408\u6570|\u516c\u56e0|\u516c\u500d"),
    ("NUMBER_PATTERN", r"\u6578\u5217|\u6570\u5217|\u898f\u5f8b|\u89c4\u5f8b|\u7b2c\s*\d+\s*(?:\u9805|\u9879)|sequence|pattern"),
    ("COUNTING", r"\u591a\u5c11\u7a2e|\u6392\u5217|\u7d44\u5408|\u7ec4\u5408|\u53d6\u51fa|\u9078\u51fa|\u9009\u51fa|how many ways"),
    ("RATE", r"\u901f\u5ea6|\u901f\u7387|\u516c\u91cc.{0,8}(?:\u5c0f\u6642|\u5c0f\u65f6|\u5206\u9418|\u5206\u949f)|speed"),
    ("ARITHMETIC_TRICKS", r"\u8a08\u7b97|\u8ba1\u7b97|\u7b97\u5f0f|\u4e58\u7a4d|\u4e58\u79ef|\u548c\u70ba|\u548c\u4e3a|\u5dee\u70ba|\u5dee\u4e3a|product|calculate this value"),
)


def official_source(url: str) -> bool:
    """Accept only the explicitly approved official domains and HTTPS."""
    parsed = urlparse(str(url))
    return parsed.scheme == "https" and parsed.hostname in OFFICIAL_DOMAINS


def normalized_fingerprint(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).lower()
    value = re.sub(r"[\s\u3000]+", "", value)
    value = re.sub(r"[，。！？；：、,.!?;:'\"()（）\[\]【】]", "", value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def infer_topic(text: str) -> str:
    for topic, pattern in TOPIC_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return topic
    operators = sum(symbol in text for symbol in ("+", "-", "×", "x", "÷", "/"))
    numbers = len(re.findall(r"\d+(?:\.\d+)?", text))
    if operators >= 2 and numbers >= 5:
        return "COMBINED"
    if len(re.findall(r"\d+[\s,\u3001]+", text)) >= 4:
        return "NUMBER_PATTERN"
    return "WORD_PROBLEM"


def extraction_risks(record: dict[str, Any]) -> list[str]:
    risks = set(record.get("quality_risks") or []) & QUALITY_RISKS
    text = str(record.get("question_text") or "")
    if not text.strip() or len(text.strip()) < 8:
        risks.add("MATH_EXPRESSION_INCOMPLETE")
    if "�" in text:
        risks.add("SPECIAL_SYMBOL_LOST")
    if record.get("ocr_confidence", 0) < 0.60:
        risks.add("SPECIAL_SYMBOL_LOST")
    visual_ref = bool(re.search(r"\u4e0b\u5716|\u53f3\u5716|\u5de6\u5716|\u5982\u5716|\u9644\u5716|\u5716\u4e2d|figure|shown", text, re.IGNORECASE))
    if visual_ref and not record.get("page_crop"):
        risks.add("MISSING_REQUIRED_DIAGRAM")
    return sorted(risks)


def eligible(record: dict[str, Any]) -> bool:
    return bool(
        record.get("official_source")
        and official_source(str(record.get("source_page") or ""))
        and record.get("grade") in ELEMENTARY_GRADES
        and record.get("extraction_status") == "COMPLETE"
        and not extraction_risks(record)
        and record.get("page_crop")
    )


def select_pilot(records: Iterable[dict[str, Any]], target: int = 100) -> list[dict[str, Any]]:
    """Deterministic diversity-first selection with a 25 percent topic ceiling."""
    unique = {r["fingerprint"]: r for r in records if eligible(r)}
    if len(unique) < target:
        raise RuntimeError(f"CORPUS_INSUFFICIENT:{len(unique)}/{target}")
    remaining = list(unique.values())
    chosen: list[dict[str, Any]] = []
    topic_counts: Counter[str] = Counter()
    paper_counts: Counter[str] = Counter()
    grade_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    cap = max(1, target // 4)
    while len(chosen) < target:
        candidates = [r for r in remaining if topic_counts[r["competition_topic"]] < cap]
        if not candidates:
            raise RuntimeError("PILOT_DIVERSITY_UNSATISFIABLE")
        row = min(candidates, key=lambda r: (
            topic_counts[r["competition_topic"]], paper_counts[r["source_file"]],
            grade_counts[r["grade"]], year_counts[str(r["year"])], r["fingerprint"],
        ))
        chosen.append(row)
        remaining.remove(row)
        topic_counts[row["competition_topic"]] += 1
        paper_counts[row["source_file"]] += 1
        grade_counts[row["grade"]] += 1
        year_counts[str(row["year"])] += 1
    return chosen
