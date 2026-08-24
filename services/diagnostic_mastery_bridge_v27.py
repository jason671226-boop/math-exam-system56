from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .curriculum_master_contracts import DiagnosisV27
from .curriculum_master_runtime import CurriculumMasterRuntime, RouteContext
from .mastery_service import MasteryEvidence, MasterySnapshot, aggregate_knowledge_evidence


@dataclass(frozen=True)
class _CanonicalTargetedEvidence:
    target_type: str
    target_id: str
    evidence: MasteryEvidence
    role: str = "primary"


def diagnosis_to_mastery_evidence(
    diagnosis: DiagnosisV27,
    *,
    is_correct: bool,
    difficulty: str = "standard",
    hints_used: int = 0,
    attempts: int = 1,
    source_type: str = "diagnosis_v27",
) -> _CanonicalTargetedEvidence:
    """Convert a canonical diagnosis into the existing mastery-service evidence shape."""

    if diagnosis.confidence <= 0:
        raise ValueError("diagnosis confidence must be positive before persistence")
    # Confidence scales the evidence weight rather than inventing a new mastery model.
    weight = max(0.25, min(1.0, float(diagnosis.confidence)))
    return _CanonicalTargetedEvidence(
        target_type="knowledge",
        target_id=diagnosis.skill_id,
        evidence=MasteryEvidence(
            is_correct=is_correct,
            difficulty=difficulty,
            hints_used=hints_used,
            attempts=attempts,
            weight=weight,
            source_type=source_type,
        ),
    )


def persist_diagnosis_mastery_v27(
    runtime: CurriculumMasterRuntime,
    route: RouteContext,
    *,
    repository: Any,
    student_id: str,
    diagnosis: DiagnosisV27,
    is_correct: bool,
    difficulty: str = "standard",
    hints_used: int = 0,
    attempts: int = 1,
) -> Mapping[str, MasterySnapshot]:
    """Persist one canonical diagnostic evidence item using current repository APIs.

    No new Supabase schema is required. The canonical skill_id is written to the
    existing `knowledge_id` column, isolated by route.profile_id.
    """

    # Fail closed if the diagnosis points outside the selected curriculum pack.
    runtime.get_skill_context(route, diagnosis.skill_id)
    profile_id = route.profile_id
    previous = repository.load_latest_knowledge_mastery(student_id, profile_id)
    targeted = diagnosis_to_mastery_evidence(
        diagnosis,
        is_correct=is_correct,
        difficulty=difficulty,
        hints_used=hints_used,
        attempts=attempts,
    )
    updated = aggregate_knowledge_evidence(
        [targeted],
        profile=profile_id,
        previous=previous,
    )
    repository.save_knowledge_mastery(student_id, profile_id, updated)
    return updated
