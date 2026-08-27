"""Deterministic, fail-closed import helpers for user-provided ELMC text PDFs."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

EDITIONS = ("第1屆", "第2屆", "第3屆", "第4屆")
SECTIONS = ("個人賽", "團體賽", "思考賽", "接力賽")
QUALITY_RISKS = frozenset({
    "MATH_FRACTION_NOTATION_LOST", "MATH_EXPRESSION_INCOMPLETE", "SPECIAL_SYMBOL_LOST",
    "TABLE_LAYOUT_LOST", "SEQUENCE_LAYOUT_LOST", "GEOMETRY_FIGURE_REQUIRED",
    "MISSING_REQUIRED_DIAGRAM", "MISSING_REQUIRED_CHART", "MULTI_DOCUMENT_CONTAMINATION",
})


def fingerprint(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").lower()
    value = re.sub(r"[\s\u3000]+", "", value)
    value = re.sub(r"[，。！？、；：,.!?;:'\"()（）\[\]【】]", "", value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _section(line: str) -> str | None:
    return next((name for name in SECTIONS if name in line), None)


def _mode(line: str) -> str | None:
    if "答案與詳解" in line or "詳解" in line or "解答" in line:
        return "solution"
    if "試題" in line:
        return "question"
    return None


TOP_MARKER = re.compile(r"^\s*(?:第\s*)?(\d{1,2})\s*(?:題|[.、．])\s*(.*)$")
SOLUTION_MARKER = re.compile(r"^\s*[（(]?(\d{1,2})[）)]\s*(.*)$")


def _segments(page_texts: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    questions: list[dict[str, Any]] = []
    solutions: list[dict[str, Any]] = []
    sections: set[str] = set()
    section: str | None = None
    mode: str | None = None
    current: dict[str, Any] | None = None

    def finish() -> None:
        nonlocal current
        if current and current["lines"]:
            current["text"] = "\n".join(current.pop("lines")).strip()
            (questions if current["mode"] == "question" else solutions).append(current)
        current = None

    for page_no, page_text in enumerate(page_texts, 1):
        for raw in page_text.splitlines():
            line = raw.strip()
            if not line:
                continue
            found_section, found_mode = _section(line), _mode(line)
            if found_section and found_mode:
                finish(); section, mode = found_section, found_mode; sections.add(section); continue
            if "僅有詳解頁" in line and found_section:
                finish(); section, mode = found_section, "solution"; sections.add(section); continue
            if not section or not mode:
                continue
            match = TOP_MARKER.match(line) or (SOLUTION_MARKER.match(line) if mode == "solution" else None)
            if match:
                number = int(match.group(1))
                finish()
                current = {"section": section, "mode": mode, "question_number": number,
                           "page": page_no, "lines": [match.group(2)] if match.group(2) else []}
                continue
            if current:
                current["lines"].append(line)
        if current:
            current.setdefault("pages", []).append(page_no)
    finish()
    return questions, solutions, sections


def quality_risks(text: str, *, has_visual: bool = False) -> list[str]:
    risks: set[str] = set()
    figure = re.search(r"(?:來源圖|如下圖|下圖|右圖|左圖|圖中|附圖|陰影部分|塗色部分|展開圖)", text)
    chart = re.search(r"(?:折線圖|長條圖|圓形圖|統計圖|座標圖)", text)
    table = re.search(r"(?:數表|表格|方格表|下表)", text)
    sequence = re.search(r"(?:數陣|特殊排列|依下列排列|方格圖|點陣圖)", text)
    if figure and not has_visual: risks.add("MISSING_REQUIRED_DIAGRAM")
    if chart and not has_visual: risks.add("MISSING_REQUIRED_CHART")
    if table and not has_visual: risks.add("TABLE_LAYOUT_LOST")
    if sequence and not has_visual: risks.add("SEQUENCE_LAYOUT_LOST")
    if re.search(r"(?:幾分之|分率|分數|占全體).{0,30}\b(?:13|23|35|45|53)\b", text):
        risks.add("MATH_FRACTION_NOTATION_LOST")
    if re.search(r"(?:[+\-×÷=]\s*[?？]|[=+\-×÷]\s*$|\(\s*[^)]*$|（\s*[^）]*$)", text):
        risks.add("MATH_EXPRESSION_INCOMPLETE")
    if len(re.findall(r"(?:試題|詳解|答案表|第\s*\d+\s*頁)", text)) >= 3:
        risks.add("MULTI_DOCUMENT_CONTAMINATION")
    latin_runs = re.findall(r"[A-Za-z]{12,}", text)
    if len(latin_runs) >= 2 or "�" in text:
        risks.add("SPECIAL_SYMBOL_LOST")
    return sorted(risks)


def parse_pdf(path: Path, edition: str) -> dict[str, Any]:
    reader = PdfReader(str(path))
    page_texts = [(page.extract_text() or "") for page in reader.pages]
    questions, solutions, sections = _segments(page_texts)
    solution_lists: dict[str, list[dict[str, Any]]] = {}
    for item in solutions: solution_lists.setdefault(item["section"], []).append(item)
    question_offsets: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    for q in questions:
        offset = question_offsets.get(q["section"], 0)
        candidates = solution_lists.get(q["section"], [])
        solution = candidates[offset] if offset < len(candidates) else None
        question_offsets[q["section"]] = offset + 1
        text = q["text"].strip()
        risks = quality_risks(text, has_visual=False)
        records.append({
            "fingerprint": fingerprint(text), "competition_profile": "ELEMENTARY_COMPETITION",
            "competition_family": "ELMC", "edition": edition, "section": q["section"],
            "question_number": q["question_number"], "question_text": text,
            "answer": None, "solution_text": solution["text"] if solution else None,
            "source_pdf": path.name, "source_page": q["page"],
            "solution_source_page": solution["page"] if solution else None,
            "has_solution": bool(solution and solution["text"]),
            "has_diagram_reference": bool(re.search(r"(?:圖|表|來源圖)", text)),
            "source_quality": "OCR_DERIVED_TEXT", "source_quality_risks": risks,
            "source_quality_status": "USABLE" if not risks else "OCR_DERIVED_REVIEW_REQUIRED",
            "profile": "ELEMENTARY_COMPETITION", "source_type": "USER_PROVIDED_DERIVED_TEXT_PDF",
            "foundation_grade": "UNKNOWN", "foundation_skill_id": None,
            "foundation_micro_skill_id": None, "secondary_skill_ids": [], "competition_topic": None,
            "thinking_skills": [], "assessment_style": None, "difficulty": None,
            "requires_diagram": "MISSING_REQUIRED_DIAGRAM" in risks, "answer_available": False,
            "solution_available": bool(solution), "mapping_confidence": None, "review_status": "UNMAPPED",
        })
    return {"edition": edition, "source_pdf": path.name, "pages": len(reader.pages),
            "sections": sorted(sections), "questions": records, "solutions_found": len(solutions)}


def load_catalog(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    skills: dict[str, dict] = {}; micros: dict[str, dict] = {}
    for grade in range(1, 7):
        base = root / "data/master_curriculum_v2_7/grade_packs" / f"G{grade}"
        with (base / "standard_skills.csv").open(encoding="utf-8-sig", newline="") as h:
            for row in csv.DictReader(h): skills[row["skill_id"]] = row
        with (base / "layer2_micro_skills.csv").open(encoding="utf-8-sig", newline="") as h:
            for row in csv.DictReader(h): micros[row["micro_skill_id"]] = row
    return skills, micros


def validate_mapping(row: dict[str, Any], skills: dict[str, dict], micros: dict[str, dict], topics: set[str], thinking: set[str]) -> list[str]:
    errors: list[str] = []
    sid, mid = row.get("foundation_skill_id"), row.get("foundation_micro_skill_id")
    if row.get("scope") == "ELEMENTARY_COMPETITION":
        if row.get("foundation_grade") not in {"G1", "G2", "G3", "G4", "G5", "G6", "UNKNOWN"}:
            errors.append("OUT_OF_SCOPE_GRADE")
        if sid not in skills: errors.append("INVALID_SKILL")
        if mid not in micros: errors.append("INVALID_MICRO")
        elif micros[mid]["parent_skill_id"] != sid: errors.append("MICRO_PARENT_MISMATCH")
        if any(x not in skills for x in row.get("secondary_skill_ids", [])): errors.append("INVALID_SECONDARY_SKILL")
        if row.get("competition_topic") not in topics: errors.append("INVALID_COMPETITION_TOPIC")
        if any(x not in thinking for x in row.get("thinking_skills", [])): errors.append("INVALID_THINKING_SKILL")
    return errors


def counter(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key)) for row in rows))
