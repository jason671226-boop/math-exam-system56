"""G7 Gold Template — Evidence model, mastery calculation, adaptive recommendation.

Phases 4-5 of the Gold Template plan.  This module is **independent** of any
Streamlit UI and database: every function is a pure, testable transformation of
explicit inputs.  Mastery is *never* reduced to a single correct answer.

Phase 4 — Evidence / Mastery
  * four evidence source types (``diagnostic``, ``autonomous_test``,
    ``wrong_answer``, ``variation_practice``)
  * the full evidence field set (knowledge, thinking skills, difficulty,
    variation level, correctness, hints, attempts, timestamp, delayed review,
    cross-unit, source)
  * a mastery score that weighs accuracy by difficulty and variation, penalises
    hint/attempt over-reliance, rewards delayed-review retention and cross-unit
    transfer, and decays old evidence in favour of recent performance.

Phase 5 — Adaptive recommendation
  * Evidence -> Knowledge mastery -> Thinking-skill weakness -> Prerequisite
    check -> Next question type -> five-question pack
  * a deterministic, explainable ordering: missing prerequisite -> unstable
    core -> same-knowledge variation -> thinking-skill reinforcement ->
    cross-unit integration -> advanced/challenge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from .g7_gold_template import (
    get_gold_template,
    get_question_type,
)

# ---------------------------------------------------------------------------
# Phase 4 — evidence model
# ---------------------------------------------------------------------------

SOURCE_TYPES = ("diagnostic", "autonomous_test", "wrong_answer", "variation_practice")

DIFFICULTY_LEVELS = (1, 2, 3, 4, 5)

DIFFICULTY_WEIGHTS: Mapping[int, float] = {
    1: 0.80,
    2: 1.00,
    3: 1.25,
    4: 1.50,
    5: 1.80,
}

# recency half-life in days: evidence twice as old as this counts half as much.
RECENCY_HALF_LIFE_DAYS = 14.0

DELAYED_REVIEW_BONUS = 0.10   # correct answer recalled after a gap -> retention
CROSS_UNIT_BONUS = 0.15       # correct answer that transfers across units
HINT_PENALTY_PER_HINT = 0.12
ATTEMPT_PENALTY_PER_EXTRA = 0.08

MASTERY_STATUSES = ("unassessed", "needs_work", "learning", "basic", "proficient")


@dataclass(frozen=True)
class Evidence:
    knowledge_id: str
    thinking_skill_ids: tuple[str, ...]
    difficulty_level: int
    variation_level: int
    correct: bool
    hints: int
    attempts: int
    timestamp: datetime
    delayed_review: bool
    cross_unit: bool
    source_type: str

    def validate(self) -> None:
        if not self.knowledge_id:
            raise ValueError("knowledge_id must be non-empty")
        if not isinstance(self.correct, bool):
            raise ValueError("correct must be boolean")
        if self.difficulty_level not in DIFFICULTY_LEVELS:
            raise ValueError(f"difficulty_level must be in {DIFFICULTY_LEVELS}")
        if self.variation_level not in DIFFICULTY_LEVELS:
            raise ValueError(f"variation_level must be in {DIFFICULTY_LEVELS}")
        if not isinstance(self.hints, int) or self.hints < 0:
            raise ValueError("hints must be a non-negative integer")
        if not isinstance(self.attempts, int) or self.attempts < 1:
            raise ValueError("attempts must be an integer >= 1")
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"source_type must be in {SOURCE_TYPES}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp


@dataclass(frozen=True)
class MasteryResult:
    target_id: str
    status: str
    score: float
    confidence: float
    evidence_count: int
    correct_count: int
    weighted_credit: float
    total_weight: float
    hint_penalty: float
    attempt_penalty: float
    retention_bonus: float
    transfer_bonus: float
    last_evidence_at: datetime | None


def _quality_factor(evidence: Evidence) -> float:
    hint_penalty = min(0.36, evidence.hints * HINT_PENALTY_PER_HINT)
    attempt_penalty = min(0.32, max(0, evidence.attempts - 1) * ATTEMPT_PENALTY_PER_EXTRA)
    return max(0.40, 1.0 - hint_penalty - attempt_penalty)


def _recency_weight(timestamp: datetime, now: datetime) -> float:
    age_days = max(0.0, (now - _as_utc(timestamp)).total_seconds() / 86400.0)
    return math.exp(-age_days / RECENCY_HALF_LIFE_DAYS)


def _derive_status(score: float, evidence_count: int, confidence: float) -> str:
    if evidence_count == 0:
        return "unassessed"
    if score < 45:
        return "needs_work"
    if score < 70:
        return "learning"
    if score < 85:
        return "basic" if evidence_count >= 2 else "learning"
    if evidence_count >= 3 and confidence >= 0.60:
        return "proficient"
    return "basic" if evidence_count >= 2 else "learning"


def calculate_mastery(
    evidences: Iterable[Evidence],
    *,
    now: datetime | None = None,
) -> MasteryResult:
    """Compute mastery for one target from a sequence of evidence items.

    The target may be a knowledge point (``knowledge_id``) or a thinking skill
    (``thinking_skill_ids`` aggregated separately by the caller).
    """
    ref = now or _utc_now()
    total_weight = 0.0
    weighted_credit = 0.0
    evidence_count = 0
    correct_count = 0
    hint_penalty = 0.0
    attempt_penalty = 0.0
    retention_bonus = 0.0
    transfer_bonus = 0.0
    last_evidence_at: datetime | None = None

    for evidence in evidences:
        evidence.validate()
        difficulty_weight = DIFFICULTY_WEIGHTS[evidence.difficulty_level]
        recency = _recency_weight(evidence.timestamp, ref)
        base_weight = difficulty_weight * recency
        quality = _quality_factor(evidence)

        earned = 0.0
        if evidence.correct:
            earned = base_weight * quality
            if evidence.delayed_review:
                earned += base_weight * DELAYED_REVIEW_BONUS
                retention_bonus += base_weight * DELAYED_REVIEW_BONUS
            if evidence.cross_unit:
                earned += base_weight * CROSS_UNIT_BONUS
                transfer_bonus += base_weight * CROSS_UNIT_BONUS

        total_weight += base_weight
        weighted_credit += earned
        evidence_count += 1
        correct_count += int(evidence.correct)
        hint_penalty += min(0.36, evidence.hints * HINT_PENALTY_PER_HINT)
        attempt_penalty += min(0.32, max(0, evidence.attempts - 1) * ATTEMPT_PENALTY_PER_EXTRA)

        ts = _as_utc(evidence.timestamp)
        if last_evidence_at is None or ts > last_evidence_at:
            last_evidence_at = ts

    score = round((weighted_credit / total_weight) * 100, 2) if total_weight else 0.0
    confidence = round(min(1.0, total_weight / 4.0), 3)
    status = _derive_status(score, evidence_count, confidence)

    return MasteryResult(
        target_id="",
        status=status,
        score=score,
        confidence=confidence,
        evidence_count=evidence_count,
        correct_count=correct_count,
        weighted_credit=round(weighted_credit, 4),
        total_weight=round(total_weight, 4),
        hint_penalty=round(hint_penalty, 4),
        attempt_penalty=round(attempt_penalty, 4),
        retention_bonus=round(retention_bonus, 4),
        transfer_bonus=round(transfer_bonus, 4),
        last_evidence_at=last_evidence_at,
    )


def aggregate_knowledge_mastery(
    evidences: Iterable[Evidence],
    *,
    now: datetime | None = None,
) -> Mapping[str, MasteryResult]:
    grouped: dict[str, list[Evidence]] = {}
    for evidence in evidences:
        grouped.setdefault(evidence.knowledge_id, []).append(evidence)
    return {
        knowledge_id: _with_target(calculate_mastery(items, now=now), knowledge_id)
        for knowledge_id, items in grouped.items()
    }


def aggregate_thinking_mastery(
    evidences: Iterable[Evidence],
    *,
    now: datetime | None = None,
) -> Mapping[str, MasteryResult]:
    """Aggregate evidence by thinking skill (one evidence may feed many skills)."""
    grouped: dict[str, list[Evidence]] = {}
    for evidence in evidences:
        for skill_id in evidence.thinking_skill_ids:
            grouped.setdefault(skill_id, []).append(evidence)
    return {
        skill_id: _with_target(calculate_mastery(items, now=now), skill_id)
        for skill_id, items in grouped.items()
    }


def _with_target(result: MasteryResult, target_id: str) -> MasteryResult:
    return MasteryResult(
        target_id=target_id,
        status=result.status,
        score=result.score,
        confidence=result.confidence,
        evidence_count=result.evidence_count,
        correct_count=result.correct_count,
        weighted_credit=result.weighted_credit,
        total_weight=result.total_weight,
        hint_penalty=result.hint_penalty,
        attempt_penalty=result.attempt_penalty,
        retention_bonus=result.retention_bonus,
        transfer_bonus=result.transfer_bonus,
        last_evidence_at=result.last_evidence_at,
    )


# ---------------------------------------------------------------------------
# Phase 5 — adaptive recommendation
# ---------------------------------------------------------------------------

WEAK_STATUSES = {"needs_work", "learning"}
STRONG_STATUSES = {"basic", "proficient"}


@dataclass(frozen=True)
class RecommendationStep:
    order: int
    category: str
    knowledge_id: str
    question_type_id: str
    reason: str
    thinking_skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationPlan:
    steps: tuple[RecommendationStep, ...]

    @property
    def pack(self) -> tuple[RecommendationStep, ...]:
        return self.steps[:5]


def _question_type_for_knowledge(
    knowledge_id: str,
    *,
    prefer_level: int | None = None,
) -> Mapping[str, Any] | None:
    template = get_gold_template()
    node = template["core"].get(knowledge_id)
    if not node:
        return None
    catalog = node["question_type_catalog"]
    if prefer_level is not None:
        for q in catalog:
            rng = q["recommended_difficulty_range"]
            if rng["default_level"] == prefer_level:
                return q
    return catalog[0] if catalog else None


def _weak_prerequisites(
    knowledge_id: str,
    knowledge_mastery: Mapping[str, MasteryResult],
) -> list[str]:
    template = get_gold_template()
    prereqs = template["prerequisite_graph"].get(knowledge_id, ())
    return [
        prereq
        for prereq in prereqs
        if knowledge_mastery.get(prereq, MasteryResult("", "unassessed", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None)).status in WEAK_STATUSES
        or prereq not in knowledge_mastery
    ]


def recommend_next(
    knowledge_mastery: Mapping[str, MasteryResult],
    thinking_mastery: Mapping[str, MasteryResult],
    *,
    pack_size: int = 5,
) -> RecommendationPlan:
    """Produce an explainable, deterministic next-action plan.

    Ordering (Phase 5 spec):
      1. missing prerequisite
      2. unstable core knowledge
      3. same-knowledge variation
      4. thinking-skill reinforcement
      5. cross-unit integration
      6. advanced / challenge
    """
    template = get_gold_template()
    core_ids = tuple(template["core"].keys())
    steps: list[RecommendationStep] = []
    order = 0
    seen_types: set[str] = set()

    def emit(category: str, knowledge_id: str, qtype: Mapping[str, Any] | None, reason: str) -> None:
        nonlocal order
        if qtype is None:
            return
        type_id = str(qtype["type_id"])
        if type_id in seen_types:
            return
        seen_types.add(type_id)
        order += 1
        steps.append(
            RecommendationStep(
                order=order,
                category=category,
                knowledge_id=knowledge_id,
                question_type_id=type_id,
                reason=reason,
                thinking_skill_ids=tuple(qtype.get("thinking_skill_ids", ())),
            )
        )

    # 1. missing prerequisite — walk weak points, surface their weak prerequisites
    for knowledge_id in core_ids:
        status = knowledge_mastery.get(knowledge_id).status if knowledge_id in knowledge_mastery else "unassessed"
        if status not in WEAK_STATUSES:
            continue
        for prereq in _weak_prerequisites(knowledge_id, knowledge_mastery):
            qtype = _question_type_for_knowledge(prereq, prefer_level=1)
            emit(
                "missing_prerequisite",
                prereq,
                qtype,
                f"先補強先備知識 {prereq}，才能銜接 {knowledge_id}",
            )

    # 2. unstable core knowledge
    for knowledge_id in core_ids:
        status = knowledge_mastery.get(knowledge_id).status if knowledge_id in knowledge_mastery else "unassessed"
        if status in WEAK_STATUSES and not _weak_prerequisites(knowledge_id, knowledge_mastery):
            qtype = _question_type_for_knowledge(knowledge_id, prefer_level=2)
            emit(
                "unstable_core",
                knowledge_id,
                qtype,
                f"核心知識 {knowledge_id} 尚未穩定，先以原型題鞏固",
            )

    # 3. same-knowledge variation — deepen stable knowledge with higher variation
    for knowledge_id in core_ids:
        status = knowledge_mastery.get(knowledge_id).status if knowledge_id in knowledge_mastery else "unassessed"
        if status in STRONG_STATUSES:
            node = template["core"][knowledge_id]
            for q in node["question_type_catalog"]:
                if q["recommended_difficulty_range"]["min_level"] >= 3:
                    emit(
                        "variation",
                        knowledge_id,
                        q,
                        f"{knowledge_id} 已掌握，進入變形／推理層級加深",
                    )
                    break

    # 4. thinking-skill reinforcement
    weak_skills = [
        skill_id
        for skill_id, result in thinking_mastery.items()
        if result.status in WEAK_STATUSES
    ]
    for skill_id in weak_skills:
        for knowledge_id in core_ids:
            node = template["core"][knowledge_id]
            for q in node["question_type_catalog"]:
                if skill_id in q.get("thinking_skill_ids", ()):
                    emit(
                        "thinking_skill",
                        knowledge_id,
                        q,
                        f"補強思考技能 {skill_id}，透過 {q['name']} 練習",
                    )
                    break

    # 5. cross-unit integration
    for knowledge_id in core_ids:
        node = template["core"][knowledge_id]
        for q in node["question_type_catalog"]:
            if "TS-INTEGRATE" in q.get("thinking_skill_ids", ()):
                emit(
                    "cross_unit_integration",
                    knowledge_id,
                    q,
                    f"以 {q['name']} 練習跨單元整合",
                )
                break

    # 6. advanced / challenge
    for knowledge_id in core_ids:
        node = template["core"][knowledge_id]
        for q in node["question_type_catalog"]:
            if q["recommended_difficulty_range"]["max_level"] >= 5:
                emit(
                    "advanced_challenge",
                    knowledge_id,
                    q,
                    f"以 {q['name']} 進入挑戰層級（L5）",
                )
                break

    return RecommendationPlan(tuple(steps[:pack_size]))
