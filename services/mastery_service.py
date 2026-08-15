from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol


class MasteryStatus(str, Enum):
    UNASSESSED = "unassessed"
    NEEDS_WORK = "needs_work"
    LEARNING = "learning"
    BASIC = "basic"
    PROFICIENT = "proficient"


DIFFICULTY_WEIGHTS = {
    "basic": 0.80,
    "standard": 1.00,
    "advanced": 1.25,
}

REVIEW_INTERVAL_DAYS = {
    MasteryStatus.NEEDS_WORK: 3,
    MasteryStatus.LEARNING: 7,
    MasteryStatus.BASIC: 14,
    MasteryStatus.PROFICIENT: 30,
}


@dataclass(frozen=True)
class MasteryEvidence:
    is_correct: bool
    difficulty: str = "standard"
    hints_used: int = 0
    attempts: int = 1
    weight: float = 1.0
    occurred_at: datetime | None = None
    source_type: str = "practice"

    def validate(self) -> None:
        if not isinstance(self.is_correct, bool):
            raise ValueError("is_correct must be boolean")
        if self.difficulty not in DIFFICULTY_WEIGHTS:
            raise ValueError(
                f"difficulty must be one of {sorted(DIFFICULTY_WEIGHTS)}, got {self.difficulty!r}"
            )
        if not isinstance(self.hints_used, int) or self.hints_used < 0:
            raise ValueError("hints_used must be a non-negative integer")
        if not isinstance(self.attempts, int) or self.attempts < 1:
            raise ValueError("attempts must be an integer >= 1")
        if not isinstance(self.weight, (int, float)) or self.weight <= 0:
            raise ValueError("weight must be > 0")


@dataclass(frozen=True)
class MasteryState:
    status: MasteryStatus = MasteryStatus.UNASSESSED
    score_numeric: float = 0.0
    confidence: float = 0.0
    evidence_count: int = 0
    last_assessed_at: datetime | None = None
    next_review_at: datetime | None = None
    weighted_points: float = 0.0
    total_weight: float = 0.0
    standard_successes: int = 0
    advanced_successes: int = 0
    correct_count: int = 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _quality_factor(evidence: MasteryEvidence) -> float:
    hint_penalty = min(0.36, evidence.hints_used * 0.12)
    attempt_penalty = min(0.32, max(0, evidence.attempts - 1) * 0.08)
    return max(0.40, 1.0 - hint_penalty - attempt_penalty)


def _derive_status(
    *,
    score: float,
    evidence_count: int,
    confidence: float,
    standard_successes: int,
    advanced_successes: int,
) -> MasteryStatus:
    if evidence_count == 0:
        return MasteryStatus.UNASSESSED
    if score < 45:
        return MasteryStatus.NEEDS_WORK
    if score < 70:
        return MasteryStatus.LEARNING
    if score < 85:
        return MasteryStatus.BASIC if evidence_count >= 2 else MasteryStatus.LEARNING

    # High accuracy on only easy items is intentionally kept at BASIC.
    # PROFICIENT requires repeated evidence plus success on standard/advanced work.
    enough_depth = advanced_successes >= 1 or standard_successes >= 3
    if evidence_count >= 3 and confidence >= 0.60 and enough_depth:
        return MasteryStatus.PROFICIENT
    return MasteryStatus.BASIC if evidence_count >= 2 else MasteryStatus.LEARNING


def _next_review(status: MasteryStatus, assessed_at: datetime) -> datetime | None:
    days = REVIEW_INTERVAL_DAYS.get(status)
    if days is None:
        return None
    return assessed_at + timedelta(days=days)


def apply_evidence(
    previous: MasteryState | None,
    evidence: MasteryEvidence,
    *,
    assessed_at: datetime | None = None,
) -> MasteryState:
    """Apply one evidence item to a mastery state without UI or database dependencies."""

    evidence.validate()
    state = previous or MasteryState()
    effective_weight = DIFFICULTY_WEIGHTS[evidence.difficulty] * float(evidence.weight)
    quality = _quality_factor(evidence)
    earned = effective_weight * (quality if evidence.is_correct else 0.0)

    total_weight = state.total_weight + effective_weight
    weighted_points = state.weighted_points + earned
    evidence_count = state.evidence_count + 1
    score = round((weighted_points / total_weight) * 100, 2) if total_weight else 0.0
    confidence = round(min(1.0, total_weight / 4.0), 3)

    standard_successes = state.standard_successes + int(
        evidence.is_correct and evidence.difficulty == "standard"
    )
    advanced_successes = state.advanced_successes + int(
        evidence.is_correct and evidence.difficulty == "advanced"
    )
    correct_count = state.correct_count + int(evidence.is_correct)

    status = _derive_status(
        score=score,
        evidence_count=evidence_count,
        confidence=confidence,
        standard_successes=standard_successes,
        advanced_successes=advanced_successes,
    )
    timestamp = assessed_at or evidence.occurred_at or _utc_now()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return MasteryState(
        status=status,
        score_numeric=score,
        confidence=confidence,
        evidence_count=evidence_count,
        last_assessed_at=timestamp,
        next_review_at=_next_review(status, timestamp),
        weighted_points=weighted_points,
        total_weight=total_weight,
        standard_successes=standard_successes,
        advanced_successes=advanced_successes,
        correct_count=correct_count,
    )


def calculate_mastery(
    evidences: Iterable[MasteryEvidence],
    *,
    assessed_at: datetime | None = None,
) -> MasteryState:
    """Calculate a mastery state from a sequence of evidence items."""

    state = MasteryState()
    for evidence in evidences:
        state = apply_evidence(state, evidence, assessed_at=assessed_at)
    return state


@dataclass(frozen=True)
class MasterySnapshot:
    knowledge_id: str
    mastery_status: MasteryStatus
    mastery_score: float
    confidence: float
    evidence_count: int
    correct_count: int
    weighted_credit: float
    last_evidence_at: datetime | None
    source_profiles: tuple[str, ...]
    state: MasteryState


@dataclass(frozen=True)
class LearningPriority:
    knowledge_id: str
    reason: str
    prerequisite_for: str | None
    mastery_status: MasteryStatus


class MasterySnapshotRepository(Protocol):
    """Storage boundary for a future Supabase-backed snapshot repository."""

    def load(self, profile: str) -> Mapping[str, MasterySnapshot]: ...
    def save(self, profile: str, snapshots: Mapping[str, MasterySnapshot]) -> None: ...


def aggregate_knowledge_evidence(
    targeted_evidence: Iterable[Any],
    *,
    profile: str,
    previous: Mapping[str, MasterySnapshot] | None = None,
    assessed_at: datetime | None = None,
) -> dict[str, MasterySnapshot]:
    """Aggregate only Knowledge evidence; Thinking evidence stays separate."""

    snapshots = dict(previous or {})
    grouped: dict[str, list[MasteryEvidence]] = {}
    for item in targeted_evidence:
        if getattr(item, "target_type", None) != "knowledge":
            continue
        grouped.setdefault(str(item.target_id), []).append(item.evidence)

    for knowledge_id, evidences in grouped.items():
        old = snapshots.get(knowledge_id)
        state = old.state if old is not None else MasteryState()
        for evidence in evidences:
            state = apply_evidence(state, evidence, assessed_at=assessed_at)
        profiles = tuple(sorted(set((old.source_profiles if old else ()) + (profile,))))
        snapshots[knowledge_id] = MasterySnapshot(
            knowledge_id=knowledge_id,
            mastery_status=state.status,
            mastery_score=state.score_numeric,
            confidence=state.confidence,
            evidence_count=state.evidence_count,
            correct_count=state.correct_count,
            weighted_credit=round(state.weighted_points, 4),
            last_evidence_at=state.last_assessed_at,
            source_profiles=profiles,
            state=state,
        )
    return snapshots


def aggregate_primary_thinking_evidence(
    targeted_evidence: Iterable[Any],
) -> dict[str, MasteryState]:
    """Aggregate primary Thinking evidence without mixing it into Knowledge mastery."""

    states: dict[str, MasteryState] = {}
    for item in targeted_evidence:
        if getattr(item, "target_type", None) != "thinking" or getattr(item, "role", None) != "primary":
            continue
        states[str(item.target_id)] = apply_evidence(
            states.get(str(item.target_id)), item.evidence
        )
    return states


def mastery_for(
    knowledge_id: str,
    snapshots: Mapping[str, MasterySnapshot],
) -> MasterySnapshot:
    snapshot = snapshots.get(knowledge_id)
    if snapshot is not None:
        return snapshot
    state = MasteryState()
    return MasterySnapshot(
        knowledge_id=knowledge_id,
        mastery_status=MasteryStatus.UNASSESSED,
        mastery_score=0.0,
        confidence=0.0,
        evidence_count=0,
        correct_count=0,
        weighted_credit=0.0,
        last_evidence_at=None,
        source_profiles=(),
        state=state,
    )


def recommend_learning_priorities(
    knowledge_points: Iterable[Any],
    snapshots: Mapping[str, MasterySnapshot],
    *,
    limit: int = 3,
    target_weights: Mapping[str, float] | None = None,
) -> tuple[LearningPriority, ...]:
    """Recommend prerequisites first, then deterministic evidence-based priorities."""

    points = {point.id: point for point in knowledge_points}
    weights = dict(target_weights or {})
    weak = {MasteryStatus.NEEDS_WORK, MasteryStatus.LEARNING}
    rank = {MasteryStatus.NEEDS_WORK: 0, MasteryStatus.LEARNING: 1}
    candidates: dict[str, LearningPriority] = {}

    def first_weak_prerequisites(point_id: str, seen: set[str]) -> list[str]:
        if point_id in seen or point_id not in points:
            return []
        seen = seen | {point_id}
        result: list[str] = []
        for prerequisite_id in points[point_id].prerequisite_ids:
            status = mastery_for(prerequisite_id, snapshots).mastery_status
            if status in weak:
                deeper = first_weak_prerequisites(prerequisite_id, seen)
                result.extend(deeper or [prerequisite_id])
        return result

    ordered_weak = sorted(
        (point_id for point_id in points if mastery_for(point_id, snapshots).mastery_status in weak),
        key=lambda point_id: (
            rank[mastery_for(point_id, snapshots).mastery_status],
            mastery_for(point_id, snapshots).mastery_score,
            mastery_for(point_id, snapshots).confidence,
            mastery_for(point_id, snapshots).evidence_count,
            -float(weights.get(point_id, 0.0)),
            point_id,
        ),
    )
    for point_id in ordered_weak:
        prerequisites = first_weak_prerequisites(point_id, set())
        if prerequisites:
            for prerequisite_id in prerequisites:
                candidates[prerequisite_id] = LearningPriority(
                    knowledge_id=prerequisite_id,
                    reason=f"先補強此先備知識，再學習 {point_id}",
                    prerequisite_for=point_id,
                    mastery_status=mastery_for(prerequisite_id, snapshots).mastery_status,
                )
        else:
            candidates.setdefault(
                point_id,
                LearningPriority(
                    knowledge_id=point_id,
                    reason="目前診斷證據顯示此知識需要優先補強",
                    prerequisite_for=None,
                    mastery_status=mastery_for(point_id, snapshots).mastery_status,
                ),
            )
        if len(candidates) >= limit:
            break
    return tuple(list(candidates.values())[:limit])
