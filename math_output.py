"""Shared, deployable helpers for preserving MathAI mathematical output."""

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


# The legacy normalizer above intentionally preserves plain text for older
# callers.  The UI renderer opts into this stricter pass so canonical strings
# such as ``16x^2-1`` become Streamlit math instead of being shown verbatim.
_RENDER_SYMBOLS = {
    r"\times": "\\times",
    r"\div": "\\div",
    r"\pm": "\\pm",
    r"\leq": "\\leq",
    r"\le": "\\le",
    r"\geq": "\\geq",
    r"\ge": "\\ge",
    r"\neq": "\\ne",
}
_PAREN_FORMULA = re.compile(
    r"(?<![A-Za-z0-9])\([^\n()]+\)\([^\n()]+\)"
    r"(?:\s*=\s*[A-Za-z0-9^{}+\-*/()\s]+)?"
)
_SQUARED_DIFFERENCE = re.compile(r"(?<![A-Za-z0-9])\([^\n()]+\)\^2\s*-\s*\([^\n()]+\)\^2")
_POWER_FORMULA = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z])\^\{?[A-Za-z0-9]+\}?")
_SUBSCRIPT_FORMULA = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z])_[{]?[A-Za-z0-9]+[}]?")
_COMMAND_FORMULA = re.compile(r"(?<![A-Za-z0-9])\\(?:pi|theta|alpha|beta|gamma|infty|angle)(?![A-Za-z])")
_COMMAND_EXPRESSION = re.compile(
    r"(?<![A-Za-z0-9])\\(?:pi|theta|alpha|beta|gamma|infty|angle)\s+"
    r"[A-Za-z](?:\^\{?[A-Za-z0-9]+\}?)?"
)
_ABS_FORMULA = re.compile(r"(?<![A-Za-z0-9])\|[A-Za-z0-9]+\|")
_SYMBOL_EXPRESSION = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z0-9]+\s*\\(?:times|div|leq|geq|ne|pm)\s*[A-Za-z0-9]+"
)
_POLYNOMIAL_FORMULA = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z0-9]+(?:\^\{?[A-Za-z0-9]+\}?)?)(?:\s*(?:[+\-=*/]|\\times|\\div)\s*(?:[A-Za-z0-9]+(?:\^\{?[A-Za-z0-9]+\}?)?))+"
)


def render_math_markdown(value: Any) -> str:
    """Return Streamlit Markdown with inline/block math for mixed text.

    Formula data remains canonical plain text in the question bank.  This
    presentation-only helper converts delimiters, commands, powers, and
    common polynomial expressions into KaTeX-compatible inline math.
    """
    text = str(value or "")
    def render_bracket_math(match: re.Match[str]) -> str:
        formula = match.group(1).strip()
        if "\n" not in formula and len(formula) <= 80 and "\\begin{" not in formula:
            return "$" + formula + "$"
        return "$$\n" + formula + "\n$$"

    text = re.sub(r"\\\[(.*?)\\\]", render_bracket_math, text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", lambda m: "$" + m.group(1).strip() + "$", text, flags=re.DOTALL)
    parts = re.split(r"(\$\$.*?\$\$|(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$))", text, flags=re.DOTALL)
    rendered: list[str] = []
    for part in parts:
        if part.startswith("$"):
            rendered.append(part)
            continue
        for command, replacement in _RENDER_SYMBOLS.items():
            part = part.replace(command, replacement)
        protected: list[str] = []

        def protect(match: re.Match[str]) -> str:
            protected.append("$" + match.group(0) + "$")
            return f"\x00MATH{len(protected) - 1}\x00"

        # Protect complete expressions before their smaller power components.
        part = _SQUARED_DIFFERENCE.sub(protect, part)
        part = _PAREN_FORMULA.sub(protect, part)
        part = _SYMBOL_EXPRESSION.sub(protect, part)
        part = _COMMAND_EXPRESSION.sub(protect, part)
        part = _ABS_FORMULA.sub(protect, part)
        part = _POLYNOMIAL_FORMULA.sub(protect, part)
        part = _POWER_FORMULA.sub(protect, part)
        part = _SUBSCRIPT_FORMULA.sub(protect, part)
        part = _COMMAND_FORMULA.sub(protect, part)
        part = _NAKED_LATEX.sub(lambda m: "$" + m.group(1) + "$", part)
        for index, formula in enumerate(protected):
            part = part.replace(f"\x00MATH{index}\x00", formula)
        rendered.append(part)
    return "".join(rendered)


def split_math_segments(value: Any) -> list[tuple[bool, str]]:
    """Split normalized mixed text into plain-text and formula segments."""
    normalized = render_math_markdown(value)
    return [
        (segment.startswith("$"), segment.strip("$") if segment.startswith("$") else segment)
        for segment in re.split(r"(\$\$.*?\$\$|(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$))", normalized, flags=re.DOTALL)
        if segment
    ]
