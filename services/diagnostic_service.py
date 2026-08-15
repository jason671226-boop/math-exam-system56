from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import gcd
from typing import Any, Callable, Iterable, Mapping

try:
    from catalog.diagnostic_loader import DiagnosticQuestion, SCHEMA_VERSION
    from services.mastery_service import MasteryEvidence
except ModuleNotFoundError as exc:
    if exc.name not in {"catalog", "services"}:
        raise
    from app.catalog.diagnostic_loader import DiagnosticQuestion, SCHEMA_VERSION
    from app.services.mastery_service import MasteryEvidence


@dataclass(frozen=True)
class PartResult:
    part_id: str
    is_correct: bool
    student_answer: Any = None


@dataclass(frozen=True)
class ErrorCandidate:
    error_type_id: str
    confidence: float
    source: str = "rule"


@dataclass(frozen=True)
class AnswerEvaluation:
    is_correct: bool
    credit: float
    part_results: tuple[PartResult, ...] = ()


@dataclass(frozen=True)
class DiagnosticResponseResult:
    question_id: str
    is_correct: bool
    credit: float
    part_results: tuple[PartResult, ...]
    response_time_seconds: int
    hint_count: int
    attempts: int
    error_candidates: tuple[ErrorCandidate, ...]


@dataclass(frozen=True)
class TargetedEvidence:
    target_type: str
    target_id: str
    role: str
    evidence: MasteryEvidence
    part_id: str | None = None


@dataclass(frozen=True)
class DiagnosticSession:
    session_id: str
    student_id: str
    target_profile: str
    schema_version: str
    question_ids: tuple[str, ...]
    status: str
    started_at: datetime
    completed_at: datetime | None = None


def _clean_text(value: Any) -> str:
    return str(value).strip().replace(" ", "")


def _numeric_equal(left: Any, right: Any) -> bool:
    try:
        return Decimal(_clean_text(left)) == Decimal(_clean_text(right))
    except (InvalidOperation, ValueError):
        try:
            return Fraction(_clean_text(left)) == Fraction(_clean_text(right))
        except (ValueError, ZeroDivisionError):
            return _clean_text(left) == _clean_text(right)


def normalize_ratio(value: Any) -> str:
    """Normalize an integer ratio, e.g. 32:40 -> 4:5."""

    text = _clean_text(value).replace("：", ":")
    match = re.fullmatch(r"([+-]?\d+):([+-]?\d+)", text)
    if not match:
        raise ValueError(f"invalid ratio: {value!r}")

    first = int(match.group(1))
    second = int(match.group(2))
    if second == 0:
        raise ValueError("ratio second term cannot be zero")
    if first == 0:
        return "0:1"

    divisor = gcd(abs(first), abs(second))
    first //= divisor
    second //= divisor
    if second < 0:
        first *= -1
        second *= -1
    return f"{first}:{second}"


def _ordered_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(_clean_text(item) for item in value)

    if isinstance(value, str):
        text = value.strip()
        parts = re.split(r"\s*(?:<|＜|,|，)\s*", text)
        return tuple(_clean_text(part) for part in parts if part.strip())

    return (_clean_text(value),)


def _evaluate_scalar(answer_type: str, accepted_answers: Iterable[Any], student_answer: Any) -> bool:
    if answer_type == "numeric":
        return any(_numeric_equal(student_answer, accepted) for accepted in accepted_answers)

    if answer_type == "ratio":
        try:
            normalized = normalize_ratio(student_answer)
        except ValueError:
            return False
        for accepted in accepted_answers:
            try:
                if normalized == normalize_ratio(accepted):
                    return True
            except ValueError:
                continue
        return False

    raise ValueError(f"unsupported scalar answer type: {answer_type}")


def evaluate_answer(question: DiagnosticQuestion, student_answer: Any) -> AnswerEvaluation:
    spec = question.answer_spec
    answer_type = spec["type"]

    if answer_type in {"numeric", "ratio"}:
        is_correct = _evaluate_scalar(answer_type, spec["accepted_answers"], student_answer)
        return AnswerEvaluation(is_correct=is_correct, credit=1.0 if is_correct else 0.0)

    if answer_type == "ordered_list":
        submitted = _ordered_list(student_answer)
        accepted = [tuple(_clean_text(v) for v in order) for order in spec["accepted_answers"]]
        is_correct = submitted in accepted
        return AnswerEvaluation(is_correct=is_correct, credit=1.0 if is_correct else 0.0)

    if answer_type == "multipart":
        if not isinstance(student_answer, dict):
            part_results = tuple(
                PartResult(part_id=part["part_id"], is_correct=False, student_answer=None)
                for part in spec["parts"]
            )
            return AnswerEvaluation(
                is_correct=False,
                credit=0.0,
                part_results=part_results,
            )

        results: list[PartResult] = []
        for part in spec["parts"]:
            part_id = part["part_id"]
            submitted = student_answer.get(part_id)
            is_correct = _evaluate_scalar(
                part["answer_type"], part["accepted_answers"], submitted
            )
            results.append(
                PartResult(
                    part_id=part_id,
                    is_correct=is_correct,
                    student_answer=submitted,
                )
            )

        credit = sum(1 for result in results if result.is_correct) / len(results)
        return AnswerEvaluation(
            is_correct=all(result.is_correct for result in results),
            credit=round(credit, 4),
            part_results=tuple(results),
        )

    raise ValueError(f"unsupported answer type: {answer_type}")


def detect_error_candidates(
    question: DiagnosticQuestion,
    student_answer: Any,
) -> tuple[ErrorCandidate, ...]:
    """Evaluate registered deterministic rules; unknown cases return empty."""

    candidates: list[ErrorCandidate] = []
    for rule in question.error_rules:
        handler = ERROR_RULE_HANDLERS.get(str(rule.get("type", "")))
        if handler is not None and handler(question, student_answer, rule):
            candidates.append(
                ErrorCandidate(
                    error_type_id=str(rule["error_type_id"]),
                    confidence=float(rule["confidence"]),
                )
            )
    return tuple(candidates)


ErrorRuleHandler = Callable[[DiagnosticQuestion, Any, Mapping[str, Any]], bool]
ERROR_RULE_HANDLERS: dict[str, ErrorRuleHandler] = {}


def register_error_rule_handler(rule_type: str, handler: ErrorRuleHandler) -> None:
    """Register a deterministic error-rule matcher by schema rule type."""

    if not isinstance(rule_type, str) or not rule_type.strip():
        raise ValueError("rule_type must be a non-empty string")
    if not callable(handler):
        raise TypeError("handler must be callable")
    ERROR_RULE_HANDLERS[rule_type.strip()] = handler


def _answer_equals_rule(
    question: DiagnosticQuestion,
    student_answer: Any,
    rule: Mapping[str, Any],
) -> bool:
    expected = rule.get("answer")
    if isinstance(expected, dict):
        if not isinstance(student_answer, dict):
            return False
        return all(_numeric_equal(student_answer.get(key), value) for key, value in expected.items())
    if question.answer_spec["type"] == "ratio":
        try:
            return normalize_ratio(student_answer) == normalize_ratio(expected)
        except ValueError:
            return False
    return _numeric_equal(student_answer, expected)


register_error_rule_handler("answer_equals", _answer_equals_rule)


def evaluate_diagnostic_response(
    question: DiagnosticQuestion,
    student_answer: Any,
    *,
    response_time_seconds: int = 0,
    hint_count: int = 0,
    attempts: int = 1,
) -> DiagnosticResponseResult:
    if (
        not isinstance(response_time_seconds, int)
        or isinstance(response_time_seconds, bool)
        or response_time_seconds < 0
    ):
        raise ValueError("response_time_seconds must be a non-negative integer")
    if not isinstance(hint_count, int) or isinstance(hint_count, bool) or hint_count < 0:
        raise ValueError("hint_count must be a non-negative integer")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        raise ValueError("attempts must be an integer >= 1")

    evaluation = evaluate_answer(question, student_answer)
    candidates = () if evaluation.is_correct else detect_error_candidates(
        question, student_answer
    )
    return DiagnosticResponseResult(
        question_id=question.question_id,
        is_correct=evaluation.is_correct,
        credit=evaluation.credit,
        part_results=evaluation.part_results,
        response_time_seconds=response_time_seconds,
        hint_count=hint_count,
        attempts=attempts,
        error_candidates=candidates,
    )


def _make_evidence(
    *,
    is_correct: bool,
    difficulty: str,
    hints_used: int,
    attempts: int,
    weight: float,
) -> MasteryEvidence:
    return MasteryEvidence(
        is_correct=is_correct,
        difficulty=difficulty,
        hints_used=hints_used,
        attempts=attempts,
        weight=weight,
        source_type="diagnostic",
    )


def build_mastery_evidence(
    question: DiagnosticQuestion,
    result: DiagnosticResponseResult,
) -> tuple[TargetedEvidence, ...]:
    """Adapt a diagnostic response into conservative mastery evidence.

    Supporting skills receive low-weight positive evidence when correct, but no
    negative evidence when an item/part is wrong.
    """

    if result.question_id != question.question_id:
        raise ValueError("result.question_id does not match question.question_id")

    units: tuple[tuple[str | None, bool], ...]
    if result.part_results:
        units = tuple((part.part_id, part.is_correct) for part in result.part_results)
    else:
        units = ((None, result.is_correct),)

    share = 1.0 / len(units)
    outputs: list[TargetedEvidence] = []

    for part_id, is_correct in units:
        part_spec = next(
            (
                part
                for part in question.answer_spec.get("parts", ())
                if part.get("part_id") == part_id
            ),
            {},
        )
        knowledge_points = tuple(part_spec.get("knowledge_points", question.knowledge_points))
        primary_skills = tuple(
            part_spec.get("primary_thinking_skills", question.primary_thinking_skills)
        )
        supporting_skills = tuple(
            part_spec.get("supporting_thinking_skills", question.supporting_thinking_skills)
        )

        for knowledge_id in knowledge_points:
            outputs.append(
                TargetedEvidence(
                    target_type="knowledge",
                    target_id=knowledge_id,
                    role="knowledge",
                    part_id=part_id,
                    evidence=_make_evidence(
                        is_correct=is_correct,
                        difficulty=question.difficulty.mastery_band,
                        hints_used=result.hint_count,
                        attempts=result.attempts,
                        weight=1.00 * share,
                    ),
                )
            )

        for skill_id in primary_skills:
            outputs.append(
                TargetedEvidence(
                    target_type="thinking",
                    target_id=skill_id,
                    role="primary",
                    part_id=part_id,
                    evidence=_make_evidence(
                        is_correct=is_correct,
                        difficulty=question.difficulty.mastery_band,
                        hints_used=result.hint_count,
                        attempts=result.attempts,
                        weight=0.60 * share,
                    ),
                )
            )

        if is_correct:
            for skill_id in supporting_skills:
                outputs.append(
                    TargetedEvidence(
                        target_type="thinking",
                        target_id=skill_id,
                        role="supporting",
                        part_id=part_id,
                        evidence=_make_evidence(
                            is_correct=True,
                            difficulty=question.difficulty.mastery_band,
                            hints_used=result.hint_count,
                            attempts=result.attempts,
                            weight=0.25 * share,
                        ),
                    )
                )

    return tuple(outputs)


def create_diagnostic_session(
    student_id: str,
    question_ids: Iterable[str],
    *,
    target_profile: str = "G6_PRIVATE_SCHOOL_PILOT",
    started_at: datetime | None = None,
) -> DiagnosticSession:
    if not isinstance(student_id, str) or not student_id.strip():
        raise ValueError("student_id must be a non-empty string")
    ids = tuple(question_ids)
    if not ids or any(not isinstance(qid, str) or not qid.strip() for qid in ids):
        raise ValueError("question_ids must contain at least one non-empty question id")
    timestamp = started_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return DiagnosticSession(
        session_id=str(uuid.uuid4()),
        student_id=student_id.strip(),
        target_profile=target_profile,
        schema_version=SCHEMA_VERSION,
        question_ids=ids,
        status="in_progress",
        started_at=timestamp,
    )
