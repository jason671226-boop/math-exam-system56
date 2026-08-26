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


def assess_multi_document_contamination(
    text: str, *, source_metadata: dict[str, object]
) -> ExtractionQuality:
    """Detect strong cross-document/cross-question evidence, not mere length.

    A single school name, option list, table, or multi-part question is deliberately
    insufficient.  The caller must provide extraction provenance and the text must
    contain at least two independent boundary signals.
    """
    value = str(text or "")
    provenance = bool(source_metadata.get("source_document") and source_metadata.get("question_number"))
    exam_headers = len(re.findall(r"(?:學年度|入學|學藝|獎學金).{0,30}(?:試題|測驗|考試)", value))
    answer_table = bool(re.search(r"(?:答案表|參考答案|解答)\s*(?:[:：]|\n).{0,120}(?:[ABCDＡＢＣＤ][,，\s]*){5,}", value, re.S))
    page_residue = len(re.findall(r"第\s*[一二三四五六七八九十0-9]+\s*頁", value))
    question_runs = len(re.findall(r"(?:^|\n)\s*(?:\(?\d{1,2}\)?[.、]|第\s*\d+\s*題)", value))
    inserted_instructions = bool(re.search(r"(?:作答說明|注意事項|本試卷|試卷說明)", value))
    different_exam_metadata = bool(source_metadata.get("multiple_exam_headers"))
    explicit_second_document = bool(source_metadata.get("pdf_text_discrepancy") and exam_headers >= 2)
    signals = sum((exam_headers >= 2, answer_table, page_residue >= 2,
                   question_runs >= 4, inserted_instructions, different_exam_metadata,
                   explicit_second_document))
    risks = ("MULTI_DOCUMENT_CONTAMINATION",) if provenance and signals >= 2 and (
        exam_headers >= 2 or different_exam_metadata or explicit_second_document
    ) else ()
    return ExtractionQuality("SOURCE_NEEDS_REEXTRACTION" if risks else "PASS", risks)


def assess_expression_completeness(
    text: str, *, source_metadata: dict[str, object], pdf_text_discrepancy: bool = False
) -> ExtractionQuality:
    """Flag incomplete core expressions only when source evidence supports loss."""
    value = str(text or "")
    source_supported = bool(source_metadata.get("source_document") and source_metadata.get("question_number"))
    explicit_loss = bool(source_metadata.get("expression_expected") or pdf_text_discrepancy)
    suspicious = any((
        bool(source_metadata.get("expression_incomplete_verified")),
        bool(re.search(r"(?:[A-Za-z0-9一-龥])\s*[+\-×÷*/]\s*[?？_]\s*(?:$|[。；;])", value)),
        bool(re.search(r"(?:^|[\s，,；;])(?:[A-Za-z]\w*)\s*=\s*(?:$|[。；;，,])", value)),
        value.count("(") != value.count(")"),
        value.count("（") != value.count("）"),
        bool(re.search(r"(?:求|計算)\s*(?:[_＿]{2,}|[?？])\s*(?:$|[。；;])", value)),
        bool(re.search(r"\\frac\s*\{[^{}]*\}\s*(?:$|[^\{])", value)),
    ))
    risks = ("MATH_EXPRESSION_INCOMPLETE",) if source_supported and explicit_loss and suspicious else ()
    return ExtractionQuality("SOURCE_NEEDS_REEXTRACTION" if risks else "PASS", risks)


def assess_missing_required_chart(text: str, *, extracted_record: dict[str, object]) -> ExtractionQuality:
    """Require a usable chart representation when the answer depends on chart positions."""
    value = str(text or "")
    chart_named = bool(extracted_record.get("chart_expected")) or bool(re.search(r"(?:折線圖|長條圖|圓形圖|統計圖|座標圖|圖表)", value))
    dependency = bool(extracted_record.get("chart_dependency_verified")) or bool(re.search(r"(?:下列|根據|依|由|如下|右|左|上|下).{0,18}(?:折線圖|長條圖|圓形圖|統計圖|座標圖|圖表)", value))
    visual_fields = ("image", "diagram", "figure_reference", "page_crop",
                     "usable_visual_representation", "chart_data", "table_data")
    usable_visual = any(bool(extracted_record.get(field)) for field in visual_fields)
    risks = ("MISSING_REQUIRED_CHART",) if chart_named and dependency and not usable_visual else ()
    return ExtractionQuality("SOURCE_IMAGE_REQUIRED" if risks else "PASS", risks)


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
