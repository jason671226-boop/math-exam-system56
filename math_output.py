"""Shared, pure helpers for preserving MathAI mathematical output."""

from __future__ import annotations

import re
from typing import Any


MATH_OUTPUT_RULES = (
    "所有數學式必須完整保留，不可省略分數、指數、根號、方程式或不等式符號。"
    "一般運算優先使用清楚可讀的 ×、÷、±、√、≤、≥、≠、°。"
    "需要 LaTeX 時，行內公式使用 $...$，獨立公式使用 $$...$$；"
    "不可輸出未被數學分隔符包住的 \\frac、\\sqrt 等指令。"
)


_NAKED_LATEX = re.compile(
    r"(?<![$\\])"
    r"(\\(?:d?frac)\{[^{}]+\}\{[^{}]+\}"
    r"|\\sqrt(?:\[[^\]]+\])?\{[^{}]+\})"
)

_READABLE_SYMBOLS = {
    r"\times": "×",
    r"\div": "÷",
    r"\pm": "±",
    r"\leq": "≤",
    r"\le": "≤",
    r"\geq": "≥",
    r"\ge": "≥",
    r"\neq": "≠",
    r"\ne": "≠",
    r"\percent": "%",
}


def _normalize_plain_segment(text: str) -> str:
    """Make bare symbol commands readable while preserving real formulas."""
    for command, symbol in _READABLE_SYMBOLS.items():
        text = re.sub(re.escape(command) + r"(?![A-Za-z])", symbol, text)
    return _NAKED_LATEX.sub(lambda match: "$" + match.group(1) + "$", text)


def normalize_math_markdown(value: Any) -> str:
    """Normalize common delimiters without altering mathematical content."""
    text = str(value or "")
    text = re.sub(
        r"\\\[(.*?)\\\]",
        lambda match: "$$\n" + match.group(1).strip() + "\n$$",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\\\((.*?)\\\)",
        lambda match: "$" + match.group(1).strip() + "$",
        text,
        flags=re.DOTALL,
    )
    # Only normalize text outside existing math blocks. Content already enclosed
    # by $...$ / $$...$$ must remain byte-for-byte intact for Streamlit/KaTeX.
    parts = re.split(
        r"(\$\$.*?\$\$|(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$))",
        text,
        flags=re.DOTALL,
    )
    return "".join(
        part if part.startswith("$") else _normalize_plain_segment(part)
        for part in parts
    )
