"""G1-G9 Rollout Engine — grade-agnostic adaptive recommendation.

A generalized version of the G7 ``recommend_next`` that consumes any
:class:`GradeRecord` (not the G7-specific gold template), so the adaptive
recommendation capability is shared across grades.  Ordering follows the same
explainable six-tier priority:

1. missing prerequisite
2. unstable core knowledge
3. same-knowledge variation
4. thinking-skill reinforcement
5. cross-unit integration
6. advanced / challenge
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from services.evidence_mastery_gold import (
    STRONG_STATUSES,
    WEAK_STATUSES,
    MasteryResult,
)

from .schema import GradeRecord


@dataclass(frozen=True)
class RecommendationStep:
    order: int
    category: str
    knowledge_id: str
    question_type_id: str
    reason: str
    thinking_skill_ids: tuple[str, ...]


def _status(mastery: Mapping[str, MasteryResult], knowledge_id: str) -> str:
    result = mastery.get(knowledge_id)
    return result.status if result is not None else "unassessed"


def _weak_prerequisites(record: GradeRecord, knowledge_id: str, mastery: Mapping[str, MasteryResult]) -> list[str]:
    prereqs = record.prerequisite_graph.get(knowledge_id, ())
    return [p for p in prereqs if _status(mastery, p) in WEAK_STATUSES or p not in mastery]


def _question_type_for(record: GradeRecord, knowledge_id: str, prefer_level: int | None = None):
    node_qts = [q for q in record.question_types if q.knowledge_id == knowledge_id]
    if prefer_level is not None:
        for q in node_qts:
            if q.recommended_difficulty_range.get("default_level") == prefer_level:
                return q
    return node_qts[0] if node_qts else None


def recommend_for_record(
    record: GradeRecord,
    knowledge_mastery: Mapping[str, MasteryResult],
    thinking_mastery: Mapping[str, MasteryResult],
    *,
    pack_size: int = 5,
) -> tuple[RecommendationStep, ...]:
    """Produce an explainable, deterministic next-action plan for one grade."""
    knowledge_ids = tuple(record.knowledge_ids)
    steps: list[RecommendationStep] = []
    order = 0
    seen_types: set[str] = set()

    def emit(category: str, knowledge_id: str, qtype, reason: str) -> None:
        nonlocal order
        if qtype is None:
            return
        if qtype.type_id in seen_types:
            return
        seen_types.add(qtype.type_id)
        order += 1
        steps.append(RecommendationStep(
            order=order,
            category=category,
            knowledge_id=knowledge_id,
            question_type_id=qtype.type_id,
            reason=reason,
            thinking_skill_ids=qtype.thinking_skill_ids,
        ))

    for knowledge_id in knowledge_ids:
        if _status(knowledge_mastery, knowledge_id) not in WEAK_STATUSES:
            continue
        for prereq in _weak_prerequisites(record, knowledge_id, knowledge_mastery):
            emit("missing_prerequisite", prereq, _question_type_for(record, prereq, prefer_level=1),
                 f"先補強先備知識 {prereq}，才能銜接 {knowledge_id}")

    for knowledge_id in knowledge_ids:
        if _status(knowledge_mastery, knowledge_id) in WEAK_STATUSES and not _weak_prerequisites(record, knowledge_id, knowledge_mastery):
            emit("unstable_core", knowledge_id, _question_type_for(record, knowledge_id, prefer_level=2),
                 f"核心知識 {knowledge_id} 尚未穩定，先以原型題鞏固")

    for knowledge_id in knowledge_ids:
        if _status(knowledge_mastery, knowledge_id) in STRONG_STATUSES:
            for q in [q for q in record.question_types if q.knowledge_id == knowledge_id]:
                if q.recommended_difficulty_range.get("min_level", 1) >= 3:
                    emit("variation", knowledge_id, q, f"{knowledge_id} 已掌握，進入變形／推理層級加深")
                    break

    for skill_id, result in thinking_mastery.items():
        if result.status in WEAK_STATUSES:
            for knowledge_id in knowledge_ids:
                for q in [q for q in record.question_types if q.knowledge_id == knowledge_id]:
                    if skill_id in q.thinking_skill_ids:
                        emit("thinking_skill", knowledge_id, q, f"補強思考技能 {skill_id}，透過 {q.name} 練習")
                        break

    for knowledge_id in knowledge_ids:
        for q in [q for q in record.question_types if q.knowledge_id == knowledge_id]:
            if "TS-INTEGRATE" in q.thinking_skill_ids:
                emit("cross_unit_integration", knowledge_id, q, f"以 {q.name} 練習跨單元整合")
                break

    for knowledge_id in knowledge_ids:
        for q in [q for q in record.question_types if q.knowledge_id == knowledge_id]:
            if q.recommended_difficulty_range.get("max_level", 1) >= 5:
                emit("advanced_challenge", knowledge_id, q, f"以 {q.name} 進入挑戰層級（L5）")
                break

    return tuple(steps[:pack_size])
