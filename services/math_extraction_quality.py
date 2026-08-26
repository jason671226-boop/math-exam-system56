"""Deterministic math-notation extraction checks; never a difficulty classifier."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionQuality:
    status: str
    risks: tuple[str, ...]


def assess_fraction_structure_loss(text: str, *, source_metadata: dict[str, object], pdf_text_discrepancy: bool = False) -> ExtractionQuality:
    """Require multiple independent signals before declaring fraction-line loss."""
    value=str(text or "");stem=re.split(r"\(A\)|（A）",value,maxsplit=1)[0];numbers=[int(x) for x in re.findall(r"\d+",stem)]
    has_fraction_marker=bool(re.search(r"\d\s*[/／⁄]\s*\d|\\frac|分之",value))
    option_pattern=sum(marker in value for marker in ("(A)","(B)","(C)","(D)","（A）","（B）","（C）","（D）"))>=3
    operators=sum(value.count(op) for op in ("+","＋","-","−"))
    small_ratio=(sum(number<=30 for number in numbers)/len(numbers)) if numbers else 0
    plausible_fraction_syntax=(small_ratio>=.70 and ((len(numbers)>=6 and option_pattern) or (len(numbers)>=5 and operators>=3)))
    source_supported=bool(source_metadata.get("official_pdf") and source_metadata.get("question_number"))
    topic_supported=bool(source_metadata.get("fraction_expected"))
    notation_evidence=pdf_text_discrepancy or topic_supported
    risks=("MATH_FRACTION_NOTATION_LOST",) if (not has_fraction_marker and source_supported and
        (option_pattern or operators>=3) and plausible_fraction_syntax and notation_evidence) else ()
    return ExtractionQuality("SOURCE_NEEDS_REEXTRACTION" if risks else "PASS",risks)


def assess_missing_required_image(text: str, *, extracted_record: dict[str, object]) -> ExtractionQuality:
    """Flag an explicit diagram dependency only when no usable visual survived extraction."""
    value=str(text or "")
    patterns=(r"(?:右圖|左圖|下圖|上圖)(?!書館)",r"如(?:右|左|下|上)?圖(?!書館)",
      r"附圖(?:中|所示|，|,|。|：|:|\s)",r"圖中",r"根據圖形",r"依圖回答",r"見圖")
    depends_on_image=any(re.search(pattern,value) for pattern in patterns)
    visual_fields=("image","diagram","figure_reference","page_crop","usable_visual_representation")
    usable_visual=any(bool(extracted_record.get(field)) for field in visual_fields)
    risks=("MISSING_REQUIRED_DIAGRAM",) if depends_on_image and not usable_visual else ()
    return ExtractionQuality("SOURCE_IMAGE_REQUIRED" if risks else "PASS",risks)


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
