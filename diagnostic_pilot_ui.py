from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import io
import json
import re
from uuid import uuid4
from typing import Any, Mapping, MutableMapping

try:
    from catalog.diagnostic_loader import (
        DiagnosticQuestion,
        ErrorType,
        load_diagnostic_questions,
        load_error_types,
    )
    from services.diagnostic_service import (
        DiagnosticResponseResult,
        ErrorCandidate,
        TargetedEvidence,
        build_mastery_evidence,
        evaluate_diagnostic_response,
    )
    from services.mastery_service import (
        aggregate_knowledge_evidence,
        aggregate_primary_thinking_evidence,
    )
    from services.mastery_repository import DiagnosticAttempt, SessionStateMasteryRepository
except ModuleNotFoundError as exc:
    if exc.name not in {"catalog", "services"}:
        raise
    from app.catalog.diagnostic_loader import (
        DiagnosticQuestion,
        ErrorType,
        load_diagnostic_questions,
        load_error_types,
    )
    from app.services.diagnostic_service import (
        DiagnosticResponseResult,
        ErrorCandidate,
        TargetedEvidence,
        build_mastery_evidence,
        evaluate_diagnostic_response,
    )
    from app.services.mastery_service import (
        aggregate_knowledge_evidence,
        aggregate_primary_thinking_evidence,
    )
    from app.services.mastery_repository import DiagnosticAttempt, SessionStateMasteryRepository

try:
    from ai_service import call_gemini_api
except ModuleNotFoundError:
    from app.ai_service import call_gemini_api


DIAG_PILOT_PREFIX = "diag_pilot_"
DIAGNOSTIC_PROFILE_LABELS = {
    "G5_PREREQUISITE_BASELINE": "Grade 5 先備能力診斷",
    "G6_PRIVATE_SCHOOL_PILOT": "Grade 6 私中入學診斷",
    "G5_COMPETITION_CORE": "Grade 5 競賽核心診斷",
    "G6_COMPETITION_CORE": "Grade 6 競賽核心診斷",
    "G7_GENERAL_BASELINE": "Grade 7 一般數學能力診斷",
    "G8_GENERAL_BASELINE": "Grade 8 一般數學能力診斷",
    "G9_GENERAL_BASELINE": "Grade 9 一般數學能力診斷",
}
COMPETITION_UNAVAILABLE = "competition_unavailable"
PROFILE_UNAVAILABLE = "profile_unavailable"


def _multipart_part_label(part: Mapping[str, Any]) -> str:
    labels = {"area": "面積", "perimeter": "周長", "angle": "頂角"}
    return str(part.get("label") or labels.get(part["part_id"], part["part_id"]))


def diagnostic_pilot_state_keys(state: Mapping[str, Any]) -> tuple[str, ...]:
    """Return only keys owned by the Phase 2B Pilot namespace."""

    return tuple(key for key in state if str(key).startswith(DIAG_PILOT_PREFIX))


def reset_diagnostic_pilot_state(state: MutableMapping[str, Any] | None = None) -> None:
    """Clear only diag_pilot_* keys; never clear the whole Streamlit session."""

    if state is None:
        import streamlit as st

        state = st.session_state
    for key in list(diagnostic_pilot_state_keys(state)):
        state.pop(key, None)


def resolve_diagnostic_route(grade: Any, learning_goal: Any) -> str:
    """Resolve existing diagnostic profiles from canonical student profile fields."""

    match = re.search(r"(\d+)", str(grade or ""))
    grade_number = int(match.group(1)) if match else 0
    if str(learning_goal or "").strip() == "參加數學競賽":
        return {
            5: "G5_COMPETITION_CORE",
            6: "G6_COMPETITION_CORE",
        }.get(grade_number, COMPETITION_UNAVAILABLE)
    profiles_by_grade = {
        5: "G5_PREREQUISITE_BASELINE",
        6: "G6_PRIVATE_SCHOOL_PILOT",
        7: "G7_GENERAL_BASELINE",
        8: "G8_GENERAL_BASELINE",
        9: "G9_GENERAL_BASELINE",
    }
    return profiles_by_grade.get(grade_number, PROFILE_UNAVAILABLE)


def set_active_diagnostic_route(
    state: MutableMapping[str, Any], route: str, student_id: str | None = None
) -> bool:
    """Switch routes without retaining answers/results from another track."""

    context = f"{student_id or 'session_student'}::{route}"
    if (
        state.get("diag_pilot_active_route") == route
        and state.get("diag_pilot_active_context", context) == context
    ):
        return False
    reset_diagnostic_pilot_state(state)
    state["diag_pilot_active_route"] = route
    state["diag_pilot_active_context"] = context
    return True


def update_session_mastery(
    state: MutableMapping[str, Any],
    profile: str,
    evidence_by_question: Mapping[str, tuple[TargetedEvidence, ...]],
    student_id: str = "session_student",
    repository: Any | None = None,
) -> None:
    """Persist one profile's application-layer mastery without cross-profile mixing."""

    all_evidence = tuple(
        item for question_evidence in evidence_by_question.values() for item in question_evidence
    )
    repository = repository or SessionStateMasteryRepository(state)
    mastery_by_profile = dict(state.get("knowledge_mastery_by_profile", {}))
    previous = repository.load_latest_knowledge_mastery(student_id, profile)
    mastery_by_profile[profile] = aggregate_knowledge_evidence(
        all_evidence,
        profile=profile,
        previous=previous,
    )
    state["knowledge_mastery_by_profile"] = mastery_by_profile
    thinking_by_profile = dict(state.get("thinking_mastery_by_profile", {}))
    thinking_by_profile[profile] = aggregate_primary_thinking_evidence(all_evidence)
    state["thinking_mastery_by_profile"] = thinking_by_profile
    repository.save_knowledge_mastery(student_id, profile, mastery_by_profile[profile])
    repository.save_thinking_skill_summary(student_id, profile, thinking_by_profile[profile])


def parse_ordered_answer_text(value: Any) -> list[str]:
    """Parse a student ordering expression without deciding whether it is correct."""

    text = str(value or "").strip()
    if not text:
        return []

    # Preserve mathematical tokens (37%, 3/8, decimals) and only split separators.
    for separator in ("＜", "，", ","):
        text = text.replace(separator, "<")
    return [part.strip() for part in text.split("<") if part.strip()]


def build_student_answer_payload(
    question: DiagnosticQuestion,
    raw_values: Mapping[str, Any],
) -> Any:
    """Convert UI fields into the payload expected by diagnostic_service.

    This function does format conversion only. It never checks correctness.
    """

    answer_type = question.answer_spec["type"]

    if answer_type in {"numeric", "ratio"}:
        return str(raw_values.get("answer", "")).strip()

    if answer_type == "ordered_list":
        return parse_ordered_answer_text(raw_values.get("answer", ""))

    if answer_type == "multipart":
        return {
            part["part_id"]: str(raw_values.get(part["part_id"], "")).strip()
            for part in question.answer_spec["parts"]
        }

    raise ValueError(f"unsupported answer type: {answer_type}")


def validate_student_answer_payload(
    question: DiagnosticQuestion,
    payload: Any,
) -> tuple[bool, str]:
    """Validate completeness/shape only; do not validate mathematical correctness."""

    answer_type = question.answer_spec["type"]

    if answer_type in {"numeric", "ratio"}:
        if not str(payload or "").strip():
            return False, "請填寫答案。"
        if answer_type == "ratio" and not any(sep in str(payload) for sep in (":", "：")):
            return False, "比例請用「4:5」這種格式輸入。"
        return True, ""

    if answer_type == "ordered_list":
        expected_count = len(question.answer_spec["accepted_answers"][0])
        if not isinstance(payload, (list, tuple)) or len(payload) != expected_count:
            return False, f"請用 < 依序排出 {expected_count} 個數值。"
        return True, ""

    if answer_type == "multipart":
        if not isinstance(payload, Mapping):
            return False, "請完成所有小題。"
        missing = [
            part["part_id"]
            for part in question.answer_spec["parts"]
            if not str(payload.get(part["part_id"], "")).strip()
        ]
        if missing:
            if {part["part_id"] for part in question.answer_spec["parts"]} == {
                "area",
                "perimeter",
            }:
                return False, "請完成面積與周長兩個答案。"
            return False, "請完成所有小題。"
        return True, ""

    return False, "目前不支援這種答案格式。"


def format_correct_answer(question: DiagnosticQuestion) -> str:
    spec = question.answer_spec
    answer_type = spec["type"]

    if answer_type in {"numeric", "ratio"}:
        return str(spec["accepted_answers"][0])
    if answer_type == "ordered_list":
        return " < ".join(str(item) for item in spec["accepted_answers"][0])
    if answer_type == "multipart":
        return "；".join(
            f"{_multipart_part_label(part)} {part['accepted_answers'][0]}"
            for part in spec["parts"]
        )
    return ""


def format_student_answer(question: DiagnosticQuestion, payload: Any) -> str:
    answer_type = question.answer_spec["type"]
    if answer_type == "ordered_list" and isinstance(payload, (list, tuple)):
        return " < ".join(str(item) for item in payload)
    if answer_type == "multipart" and isinstance(payload, Mapping):
        return "；".join(
            f"{_multipart_part_label(part)} {payload.get(part['part_id'], '')}"
            for part in question.answer_spec["parts"]
        )
    return str(payload)


def format_error_candidate(
    candidate: ErrorCandidate,
    error_types: Mapping[str, ErrorType],
) -> str:
    """Student-facing formatter: show the pedagogical label, not IDs/confidence."""

    error_type = error_types.get(candidate.error_type_id)
    return error_type.name if error_type is not None else "需要進一步確認的錯因"


def build_diagnostic_summary(
    results: Mapping[str, DiagnosticResponseResult],
) -> dict[str, Any]:
    full_correct = sum(1 for result in results.values() if result.is_correct)
    partial_ids = [
        qid
        for qid, result in results.items()
        if not result.is_correct and 0.0 < result.credit < 1.0
    ]
    return {
        "question_count": len(results),
        "full_correct": full_correct,
        "partial_question_ids": tuple(partial_ids),
        "has_partial": bool(partial_ids),
    }


def select_profile_questions(catalog: Any) -> tuple[DiagnosticQuestion, ...]:
    """Select active questions belonging to the catalog's declared profile."""

    return tuple(
        question
        for question in catalog.questions
        if question.active and catalog.target_profile in question.target_profiles
    )


def _canonical_autofill_value(spec: Mapping[str, Any]) -> Any:
    if spec["type"] == "ordered_list":
        return " < ".join(str(value) for value in spec["accepted_answers"][0])
    return str(spec["accepted_answers"][0])


def _incorrect_autofill_value(spec: Mapping[str, Any]) -> Any:
    """Return a validly shaped generic value that differs from the canonical answer."""

    canonical = _canonical_autofill_value(spec)
    if spec["type"] == "ordered_list":
        values = list(spec["accepted_answers"][0])
        shifted = values[1:] + values[:1]
        return " < ".join(str(value) for value in shifted)
    if spec["type"] == "ratio":
        text = str(canonical).replace("：", ":")
        left, separator, right = text.partition(":")
        if separator:
            try:
                return f"{Decimal(left) + 1}:{right}"
            except InvalidOperation:
                pass
    try:
        return str(Decimal(str(canonical)) + 1)
    except InvalidOperation:
        return "999999999"


def build_mixed_autofill_answers(
    questions: tuple[DiagnosticQuestion, ...],
) -> dict[str, dict[str, str]]:
    """Build deterministic UI-field values from catalog answer specs."""

    answers: dict[str, dict[str, str]] = {}
    partial_assigned = False
    for index, question in enumerate(questions):
        spec = question.answer_spec
        if spec["type"] == "multipart":
            make_partial = not partial_assigned
            values = {}
            for part_index, part in enumerate(spec["parts"]):
                part_spec = {"type": part["answer_type"], "accepted_answers": part["accepted_answers"]}
                values[part["part_id"]] = str(
                    _incorrect_autofill_value(part_spec)
                    if (make_partial and part_index == len(spec["parts"]) - 1)
                    or (not make_partial and index >= 10)
                    else _canonical_autofill_value(part_spec)
                )
            answers[question.question_id] = values
            partial_assigned = partial_assigned or make_partial
        else:
            value = (
                _canonical_autofill_value(spec)
                if index < 10
                else _incorrect_autofill_value(spec)
            )
            answers[question.question_id] = {"answer": str(value)}
    return answers


def apply_developer_autofill(
    state: MutableMapping[str, Any],
    questions: tuple[DiagnosticQuestion, ...],
    *,
    developer_mode: bool,
) -> bool:
    """Fill Streamlit widget state only when the authenticated developer mode allows it."""

    if not developer_mode:
        return False
    generated = build_mixed_autofill_answers(questions)
    for question in questions:
        values = generated[question.question_id]
        if question.answer_spec["type"] == "multipart":
            for part_id, value in values.items():
                state[f"diag_pilot_input_{question.question_id}_{part_id}"] = value
        else:
            state[f"diag_pilot_input_{question.question_id}"] = values["answer"]
    return True


def clear_developer_autofill(
    state: MutableMapping[str, Any], questions: tuple[DiagnosticQuestion, ...]
) -> None:
    """Clear only answer widgets belonging to the current diagnostic catalog."""

    for question in questions:
        prefix = f"diag_pilot_input_{question.question_id}"
        for key in tuple(state):
            if str(key) == prefix or str(key).startswith(prefix + "_"):
                state.pop(key, None)


def render_developer_autofill_controls(
    st: Any,
    questions: tuple[DiagnosticQuestion, ...],
    *,
    developer_mode: bool,
) -> bool:
    """Render the developer-only controls and report whether they are available."""

    if not developer_mode:
        return False
    if st.button("🧪 填入測試答案", key="diag_pilot_autofill_button"):
        apply_developer_autofill(st.session_state, questions, developer_mode=True)
        st.rerun()
    if st.button("🧹 清除診斷測試答案", key="diag_pilot_clear_autofill_button"):
        clear_developer_autofill(st.session_state, questions)
        st.rerun()
    return True


def _evidence_debug_row(item: TargetedEvidence) -> dict[str, Any]:
    return {
        "target_type": item.target_type,
        "target_id": item.target_id,
        "role": item.role,
        "part_id": item.part_id,
        **asdict(item.evidence),
    }


def _render_q5_cut_corner_svg(st: Any) -> None:
    """Render a lightweight SVG diagram for the Pilot cut-corner rectangle item."""

    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 300" width="100%" role="img"
         aria-label="長 12 公分、寬 8 公分的長方形，右上角剪去邊長 3 公分的正方形">
      <style>
        .shape { fill: #eef6ff; stroke: #2563eb; stroke-width: 3; }
        .cut { fill: #fff1f2; stroke: #dc2626; stroke-width: 2; stroke-dasharray: 7 5; }
        .dim { stroke: #374151; stroke-width: 1.8; }
        .cutdim { stroke: #dc2626; stroke-width: 1.8; }
        .label { font: 16px sans-serif; fill: #1f2937; }
        .cutlabel { font: 15px sans-serif; fill: #b91c1c; }
      </style>

      <!-- Remaining L-shaped figure: scale 12x8 to 300x200; cut corner 3x3 = 75x75 -->
      <path class="shape" d="M90 45 H315 V120 H390 V245 H90 Z"/>
      <rect class="cut" x="315" y="45" width="75" height="75"/>

      <!-- Overall width 12 cm -->
      <line class="dim" x1="90" y1="270" x2="390" y2="270"/>
      <line class="dim" x1="90" y1="263" x2="90" y2="277"/>
      <line class="dim" x1="390" y1="263" x2="390" y2="277"/>
      <text class="label" x="218" y="294">12 公分</text>

      <!-- Overall height 8 cm -->
      <line class="dim" x1="60" y1="45" x2="60" y2="245"/>
      <line class="dim" x1="53" y1="45" x2="67" y2="45"/>
      <line class="dim" x1="53" y1="245" x2="67" y2="245"/>
      <text class="label" x="22" y="157" transform="rotate(-90 22 157)">8 公分</text>

      <!-- Cut size 3 cm horizontally -->
      <line class="cutdim" x1="315" y1="25" x2="390" y2="25"/>
      <line class="cutdim" x1="315" y1="19" x2="315" y2="31"/>
      <line class="cutdim" x1="390" y1="19" x2="390" y2="31"/>
      <text class="cutlabel" x="331" y="17">3 公分</text>

      <!-- Cut size 3 cm vertically -->
      <line class="cutdim" x1="415" y1="45" x2="415" y2="120"/>
      <line class="cutdim" x1="409" y1="45" x2="421" y2="45"/>
      <line class="cutdim" x1="409" y1="120" x2="421" y2="120"/>
      <text class="cutlabel" x="428" y="88">3 公分</text>
    </svg>
    """
    st.image(svg.lstrip(), width="stretch")


def _render_rectangle_dimensions_svg(st: Any) -> None:
    """Render the G5 rectangle dimensions without exposing its answers."""

    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 300" width="100%" role="img"
         aria-label="長 12 公分、寬 7 公分的長方形">
      <style>
        .shape { fill: #eef6ff; stroke: #2563eb; stroke-width: 3; }
        .dim { stroke: #374151; stroke-width: 1.8; }
        .label { font: 17px sans-serif; fill: #1f2937; }
      </style>
      <rect class="shape" x="110" y="55" width="300" height="175"/>
      <line class="dim" x1="110" y1="260" x2="410" y2="260"/>
      <line class="dim" x1="110" y1="252" x2="110" y2="268"/>
      <line class="dim" x1="410" y1="252" x2="410" y2="268"/>
      <text class="label" x="230" y="288">12 公分</text>
      <line class="dim" x1="75" y1="55" x2="75" y2="230"/>
      <line class="dim" x1="67" y1="55" x2="83" y2="55"/>
      <line class="dim" x1="67" y1="230" x2="83" y2="230"/>
      <text class="label" x="38" y="175" transform="rotate(-90 38 175)">7 公分</text>
    </svg>
    """
    st.image(svg.lstrip(), width="stretch")


def _render_trapezoid_composite_svg(st: Any) -> None:
    """Render a trapezoid with the stated triangular cut highlighted."""

    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 370" width="100%" role="img"
         aria-label="上底 8 公分、下底 14 公分、高 6 公分的梯形，切去底 4 公分、高 6 公分的三角形">
      <style>
        .shape { fill: #eef6ff; stroke: #2563eb; stroke-width: 3; }
        .cut { fill: #fff1f2; stroke: #dc2626; stroke-width: 2.5; stroke-dasharray: 7 5; }
        .dim { stroke: #374151; stroke-width: 1.8; }
        .cutdim { stroke: #dc2626; stroke-width: 1.8; }
        .label { font: 16px sans-serif; fill: #1f2937; }
        .cutlabel { font: 15px sans-serif; fill: #b91c1c; }
      </style>
      <path class="shape" d="M150 65 H350 L425 245 H75 Z"/>
      <path class="cut" d="M325 65 L425 245 H325 Z"/>
      <line class="dim" x1="150" y1="38" x2="350" y2="38"/>
      <line class="dim" x1="150" y1="31" x2="150" y2="45"/>
      <line class="dim" x1="350" y1="31" x2="350" y2="45"/>
      <text class="label" x="220" y="29">上底 8 公分</text>
      <line class="dim" x1="75" y1="320" x2="425" y2="320"/>
      <line class="dim" x1="75" y1="313" x2="75" y2="327"/>
      <line class="dim" x1="425" y1="313" x2="425" y2="327"/>
      <text class="label" x="250" y="350" text-anchor="middle">下底 14 公分</text>
      <line class="dim" x1="110" y1="65" x2="110" y2="245"/>
      <line class="dim" x1="103" y1="65" x2="117" y2="65"/>
      <line class="dim" x1="103" y1="245" x2="117" y2="245"/>
      <text class="label" x="72" y="185" transform="rotate(-90 72 185)">高 6 公分</text>
      <line class="cutdim" x1="325" y1="270" x2="425" y2="270"/>
      <line class="cutdim" x1="325" y1="264" x2="325" y2="276"/>
      <line class="cutdim" x1="425" y1="264" x2="425" y2="276"/>
      <text class="cutlabel" x="375" y="296" text-anchor="middle">切去三角形的底 4 公分</text>
    </svg>
    """
    st.image(svg.lstrip(), width="stretch")


def _render_cube_train_svg(st: Any) -> None:
    """Render three face-joined cubes without exposing the face-count answer."""

    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 260" width="100%" role="img"
         aria-label="三個相同正方體排成一直線並以整個面相接">
      <style>
        .front { fill:#dbeafe; stroke:#2563eb; stroke-width:2.5; }
        .top { fill:#eff6ff; stroke:#2563eb; stroke-width:2.5; }
        .side { fill:#bfdbfe; stroke:#2563eb; stroke-width:2.5; }
        .label { font:17px sans-serif; fill:#1f2937; }
      </style>
      <g transform="translate(70 80)">
        <g transform="translate(0 0)"><path class="front" d="M0 30 L70 30 L70 100 L0 100 Z"/><path class="top" d="M0 30 L25 5 L95 5 L70 30 Z"/><path class="side" d="M70 30 L95 5 L95 75 L70 100 Z"/></g>
        <g transform="translate(95 0)"><path class="front" d="M0 30 L70 30 L70 100 L0 100 Z"/><path class="top" d="M0 30 L25 5 L95 5 L70 30 Z"/><path class="side" d="M70 30 L95 5 L95 75 L70 100 Z"/></g>
        <g transform="translate(190 0)"><path class="front" d="M0 30 L70 30 L70 100 L0 100 Z"/><path class="top" d="M0 30 L25 5 L95 5 L70 30 Z"/><path class="side" d="M70 30 L95 5 L95 75 L70 100 Z"/></g>
      </g>
      <text class="label" x="170" y="225">相鄰正方體以整個面相接</text>
    </svg>
    """
    st.image(svg.lstrip(), width="stretch")


VISUALIZATION_RENDERERS = {
    "cut_corner_rectangle": _render_q5_cut_corner_svg,
    "rectangle_dimensions": _render_rectangle_dimensions_svg,
    "trapezoid_composite": _render_trapezoid_composite_svg,
    "cube_train": _render_cube_train_svg,
}


def render_question_visualization(st: Any, visualization: str | None) -> bool:
    """Render a registered metadata-driven visualization when available."""

    renderer = VISUALIZATION_RENDERERS.get(visualization)
    if renderer is None:
        return False
    renderer(st)
    return True


def _normalize_math_markdown(value: Any) -> str:
    text = str(value or "")
    text = re.sub(
        r"\\\[(.*?)\\\]",
        lambda m: "$$\n" + m.group(1).strip() + "\n$$",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\\\((.*?)\\\)",
        lambda m: "$" + m.group(1).strip() + "$",
        text,
        flags=re.DOTALL,
    )
    return text


def _diagnostic_photo_prompt(questions: tuple[DiagnosticQuestion, ...]) -> str:
    question_rows = []
    for question in questions:
        if question.answer_spec["type"] == "multipart":
            fields = [part["part_id"] for part in question.answer_spec["parts"]]
        else:
            fields = ["answer"]
        question_rows.append(
            {
                "question_id": question.question_id,
                "sequence": question.sequence,
                "prompt": question.prompt,
                "fields": fields,
            }
        )

    return (
        "你是 MathAI 的『學生手寫答案抄錄員』，不是解題老師。\n"
        "請只根據照片上學生實際寫出的內容，把答案抄錄到對應題號。"
        "絕對不要自行計算、推理、猜答案或補上空白題。看不清楚或沒有作答就填空字串。\n"
        "請依下方 question_id 與 sequence 對照題目；只回傳 JSON 物件，不要 Markdown、不要說明。\n"
        "JSON 格式：{\"question_id\": {\"answer\": \"學生答案\"}}；multipart 題依 fields 回傳各欄位。\n"
        "保留學生原本的數學符號；比例可用 4:5，排序可用 <。\n\n"
        "題目清單：\n"
        + json.dumps(question_rows, ensure_ascii=False)
    )


def _parse_ai_json_object(raw_text: Any) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("AI answer transcription did not return an object")
    return parsed


def _transcribe_diagnostic_answer_images(
    image_files: list[Any],
    questions: tuple[DiagnosticQuestion, ...],
) -> dict[str, Any]:
    from PIL import Image

    contents: list[Any] = [_diagnostic_photo_prompt(questions)]
    for uploaded in image_files[:3]:
        image = Image.open(io.BytesIO(uploaded.getvalue())).convert("RGB")
        contents.append(image)
    response = call_gemini_api(contents)
    return _parse_ai_json_object(response)


def _apply_transcribed_answers_to_state(
    state: MutableMapping[str, Any],
    questions: tuple[DiagnosticQuestion, ...],
    transcribed: Mapping[str, Any],
) -> int:
    filled = 0
    for question in questions:
        row = transcribed.get(question.question_id, {})
        if not isinstance(row, Mapping):
            row = {"answer": row}
        if question.answer_spec["type"] == "multipart":
            for part in question.answer_spec["parts"]:
                value = str(row.get(part["part_id"], "") or "").strip()
                if value:
                    state[f"diag_pilot_input_{question.question_id}_{part['part_id']}"] = value
                    filled += 1
        else:
            value = str(row.get("answer", "") or "").strip()
            if value:
                state[f"diag_pilot_input_{question.question_id}"] = value
                filled += 1
    return filled


def _render_photo_answer_controls(st: Any, questions: tuple[DiagnosticQuestion, ...]) -> None:
    st.markdown("#### 📷 也可以拍照／上傳作答照片")
    st.caption(
        "AI 只負責把照片中的手寫答案抄進下方欄位；正誤與錯因仍由 MathAI 診斷規則判定。"
        "辨識後請先檢查文字，再提交診斷。"
    )
    mode = st.radio(
        "照片來源：",
        ["📷 直接拍照", "📂 上傳已拍好的照片"],
        horizontal=True,
        key="diag_pilot_photo_mode",
    )
    image_files: list[Any] = []
    if mode == "📷 直接拍照":
        captured = st.camera_input(
            "拍攝學生作答紙",
            key="diag_pilot_camera_answer",
        )
        if captured is not None:
            image_files.append(captured)
    else:
        uploaded = st.file_uploader(
            "上傳作答照片（最多 3 張）",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="diag_pilot_answer_upload",
        )
        image_files.extend((uploaded or [])[:3])
        if uploaded and len(uploaded) > 3:
            st.warning("最多先辨識 3 張，已自動取前 3 張。")

    if image_files and st.button(
        "🤖 AI 讀取照片並填入答案欄位",
        key="diag_pilot_transcribe_photo",
        use_container_width=True,
    ):
        try:
            with st.spinner("正在辨識學生手寫答案…"):
                transcribed = _transcribe_diagnostic_answer_images(image_files, questions)
                filled = _apply_transcribed_answers_to_state(
                    st.session_state,
                    questions,
                    transcribed,
                )
            if filled:
                st.success(f"已辨識並填入 {filled} 個答案欄位，請先檢查後再提交。")
                st.rerun()
            else:
                st.warning("照片中沒有辨識到可確定的作答內容，請換一張較清楚的照片或手動輸入。")
        except Exception:
            st.error("照片答案辨識暫時無法完成。請改用較清楚的照片，或直接在下方手動輸入答案。")


def _render_answer_input(st: Any, question: DiagnosticQuestion) -> dict[str, Any]:
    qid = question.question_id
    spec = question.answer_spec
    answer_type = spec["type"]

    if answer_type == "multipart":
        number_labels = ("①", "②", "③", "④", "⑤")
        return {
            part["part_id"]: st.text_input(
                f"{number_labels[index - 1] if index <= len(number_labels) else index} "
                f"{part.get('input_label') or _multipart_part_label(part)}",
                key=f"diag_pilot_input_{qid}_{part['part_id']}",
            )
            for index, part in enumerate(spec["parts"], start=1)
        }

    placeholder = "例如：0.365 < 37% < 3/8 < 0.38" if answer_type == "ordered_list" else None
    if answer_type == "ratio":
        placeholder = "例如：4:5"
    return {
        "answer": st.text_input(
            "答案",
            placeholder=placeholder,
            key=f"diag_pilot_input_{qid}",
        )
    }


def _render_result_block(
    st: Any,
    question: DiagnosticQuestion,
    payload: Any,
    result: DiagnosticResponseResult,
    error_types: Mapping[str, ErrorType],
) -> None:
    if result.is_correct:
        status = "✅ 答對"
    elif 0.0 < result.credit < 1.0:
        status = "🟡 部分答對"
    else:
        status = "🟠 需要再確認"

    st.markdown(f"#### 第 {question.sequence} 題｜{status}")
    st.markdown("你的答案：" + _normalize_math_markdown(format_student_answer(question, payload)))
    st.markdown("標準答案：" + _normalize_math_markdown(format_correct_answer(question)))

    if result.error_candidates:
        names = [
            format_error_candidate(candidate, error_types)
            for candidate in result.error_candidates
        ]
        st.warning("可能錯因：" + "、".join(names))

    if not result.is_correct:
        with st.expander("查看標準解法", expanded=False):
            st.markdown(_normalize_math_markdown(question.solution.summary))
            for step in question.solution.steps:
                st.markdown("• " + _normalize_math_markdown(step))


def render_diagnostic_pilot(
    *,
    developer_mode: bool = False,
    learning_runtime: Any | None = None,
    learning_map_tab_label: str | None = None,
) -> None:
    """Render the local Phase 2B diagnostic Pilot inside the existing diagnosis tab."""

    import streamlit as st

    student_profile = st.session_state.get("user_profile", {})
    selected_profile = resolve_diagnostic_route(
        student_profile.get("grade"),
        student_profile.get("version"),
    )
    if learning_runtime is not None:
        student_id = learning_runtime.student_id
        repository = learning_runtime.repository
    else:
        student_id = str(st.session_state.setdefault("local_learning_student_id", uuid4()))
        repository = SessionStateMasteryRepository(st.session_state)
    set_active_diagnostic_route(st.session_state, selected_profile, student_id)

    if selected_profile == COMPETITION_UNAVAILABLE:
        st.info("數學競賽診斷尚未建立，目前不提供競賽能力診斷題。")
        return
    if selected_profile == PROFILE_UNAVAILABLE:
        st.info("目前尚未建立此年級的學習診斷題。")
        return

    try:
        catalog = load_diagnostic_questions(profile=selected_profile)
        error_catalog = load_error_types()
    except (OSError, ValueError) as exc:
        st.error("診斷內容目前無法載入，請稍後再試或通知管理員。")
        if developer_mode:
            st.code(f"{type(exc).__name__}: {exc}")
        return
    question_map = catalog.by_id()
    questions = select_profile_questions(catalog)
    error_types = error_catalog.by_id()

    st.markdown(f"### 🧭 {DIAGNOSTIC_PROFILE_LABELS[selected_profile]}")
    st.caption(
        f"{len(questions)} 題基礎診斷｜目前僅供開發驗證，不代表正式能力報告。"
    )
    render_developer_autofill_controls(
        st,
        questions,
        developer_mode=developer_mode,
    )

    if not st.session_state.get("diag_pilot_started", False):
        st.info(
            "這個 Pilot 用來驗證：學生作答 → 系統判定 → 錯因候選 → "
            "Knowledge / Thinking Evidence。資料不會寫入正式 Supabase。"
        )
        if st.button(
            "開始診斷",
            type="primary",
            key="diag_pilot_start_button",
        ):
            st.session_state["diag_pilot_started"] = True
            st.session_state["diag_pilot_submitted"] = False
            st.session_state["diag_pilot_started_at"] = datetime.now(timezone.utc).isoformat()
            st.session_state["diag_pilot_attempt_key"] = str(uuid4())
            st.rerun()
        return

    if not st.session_state.get("diag_pilot_submitted", False):
        _render_photo_answer_controls(st, questions)
        raw_answers: dict[str, Mapping[str, Any]] = {}
        with st.form("diag_pilot_form"):
            for question in questions:
                st.markdown(f"#### 第 {question.sequence} 題")
                st.markdown(_normalize_math_markdown(question.prompt))
                render_question_visualization(st, question.visualization)
                raw_answers[question.question_id] = _render_answer_input(st, question)
                st.markdown("---")

            submitted = st.form_submit_button(
                "提交診斷",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            payloads: dict[str, Any] = {}
            validation_errors: list[str] = []
            for question in questions:
                payload = build_student_answer_payload(
                    question,
                    raw_answers[question.question_id],
                )
                is_valid, message = validate_student_answer_payload(question, payload)
                if not is_valid:
                    validation_errors.append(f"第 {question.sequence} 題：{message}")
                payloads[question.question_id] = payload

            if validation_errors:
                st.error("請先修正以下欄位：\n\n" + "\n\n".join(validation_errors))
                return

            results: dict[str, DiagnosticResponseResult] = {}
            evidence: dict[str, tuple[TargetedEvidence, ...]] = {}
            for question in questions:
                payload = payloads[question.question_id]
                result = evaluate_diagnostic_response(
                    question,
                    payload,
                    response_time_seconds=0,
                    hint_count=0,
                    attempts=1,
                )
                results[question.question_id] = result
                evidence[question.question_id] = build_mastery_evidence(question, result)

            st.session_state["diag_pilot_answers"] = payloads
            st.session_state["diag_pilot_results"] = results
            st.session_state["diag_pilot_evidence"] = evidence
            update_session_mastery(
                st.session_state,
                selected_profile,
                evidence,
                student_id=student_id,
                repository=repository,
            )
            repository.save_diagnostic_result(
                DiagnosticAttempt(
                    student_id=student_id,
                    profile=selected_profile,
                    answers=payloads,
                    results=results,
                    evidence=evidence,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    attempt_key=st.session_state.setdefault(
                        "diag_pilot_attempt_key", str(uuid4())
                    ),
                )
            )
            st.session_state["diag_pilot_submitted"] = True
            st.session_state["diag_pilot_completed_at"] = datetime.now(timezone.utc).isoformat()
            st.rerun()
        return

    results = st.session_state.get("diag_pilot_results", {})
    payloads = st.session_state.get("diag_pilot_answers", {})
    evidence = st.session_state.get("diag_pilot_evidence", {})
    summary = build_diagnostic_summary(results)

    st.success(
        f"完成 {summary['question_count']} 題診斷｜完全答對："
        f"{summary['full_correct']} / {summary['question_count']}"
    )
    if st.session_state.get("learning_persistence_warning"):
        st.warning(st.session_state["learning_persistence_warning"])
    elif learning_runtime is not None and learning_runtime.persistence_enabled:
        st.caption("診斷、Knowledge Mastery 與 Thinking evidence 已同步至持久化學習紀錄。")
    else:
        st.caption("本次診斷結果僅保留於目前 session；使用 Supabase Auth 登入可啟用跨 session 紀錄。")
    if learning_map_tab_label and st.button(
        "查看個人學習地圖與下一步建議",
        key="diag_open_learning_map",
        use_container_width=True,
    ):
        st.session_state["main_tabs_control"] = learning_map_tab_label
        st.rerun()
    if summary["has_partial"]:
        partial_sequences = [
            str(question_map[qid].sequence)
            for qid in summary["partial_question_ids"]
            if qid in question_map
        ]
        st.info("部分答對題目：第 " + "、".join(partial_sequences) + " 題")

    for question in questions:
        qid = question.question_id
        if qid not in results:
            continue
        _render_result_block(
            st,
            question,
            payloads.get(qid),
            results[qid],
            error_types,
        )

    with st.expander("開發者：診斷 Evidence", expanded=False):
        debug_payload: dict[str, Any] = {}
        for question in questions:
            qid = question.question_id
            result = results.get(qid)
            if result is None:
                continue
            debug_payload[qid] = {
                "result": asdict(result),
                "evidence": [
                    _evidence_debug_row(item)
                    for item in evidence.get(qid, ())
                ],
            }
        st.json(debug_payload)

    st.button(
        "重新開始診斷",
        key="diag_pilot_restart_button",
        use_container_width=True,
        on_click=reset_diagnostic_pilot_state,
    )
