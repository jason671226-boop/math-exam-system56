"""Deterministic math-notation extraction checks; never a difficulty classifier."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionQuality:
    status: str
    risks: tuple[str, ...]


def assess_math_extraction(text: str, *, expected_notation: tuple[str, ...] = ()) -> ExtractionQuality:
    value=str(text or "");risks:set[str]=set()
    if not value.strip():risks.add("EMPTY_TEXT")
    if "�" in value or "□" in value or "[MISSING" in value.upper():risks.add("SYMBOL_LOSS")
    if re.search(r"(?:^|\s)/(?:\s|$)|\d\s*/\s*(?:[),，。]|$)|(?:^|[(（])\s*/\s*\d",value):risks.add("BROKEN_FRACTION")
    if "\\frac" in value and not re.search(r"\\frac\s*\{[^{}]+\}\s*\{[^{}]+\}",value):risks.add("BROKEN_FRACTION")
    if re.search(r"√\s*(?:$|的值|[，。；;,)）])|\\sqrt\s*(?:$|[^\{])",value):risks.add("MISSING_RADICAL")
    if re.search(r"\^\s*(?:$|[+\-×÷=，。；;,)）])",value):risks.add("BROKEN_EXPONENT")
    if re.search(r"(?:∠|△|⊥|∥)\s*(?:$|[，。；;])",value):risks.add("BROKEN_GEOMETRY_SYMBOL")
    expected=set(expected_notation)
    if "fraction" in expected and not (re.search(r"\d\s*/\s*\d",value) or "分之" in value or "\\frac" in value):risks.add("MISSING_FRACTION_NOTATION")
    if "radical" in expected and "√" not in value and "\\sqrt" not in value:risks.add("MISSING_RADICAL")
    if "exponent" in expected and not ("^" in value or re.search(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]",value)):risks.add("BROKEN_EXPONENT")
    if "geometry" in expected and not any(symbol in value for symbol in ("∠","△","⊥","∥","度")):risks.add("GEOMETRY_SYMBOL_LOSS")
    return ExtractionQuality("SOURCE_NEEDS_REEXTRACTION" if risks else "PASS",tuple(sorted(risks)))
