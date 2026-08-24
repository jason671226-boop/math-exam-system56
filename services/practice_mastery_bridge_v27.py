from __future__ import annotations

from typing import Any, Mapping

from .curriculum_master_contracts import GeneratedItemV27
from .curriculum_master_runtime import CurriculumMasterRuntime, RouteContext
from .mastery_service import MasteryEvidence, MasterySnapshot, aggregate_knowledge_evidence


_DIFFICULTY = {
    1: "basic",
    2: "basic",
    3: "standard",
    4: "advanced",
    5: "advanced",
}


def apply_generated_item_result_v27(
    runtime: CurriculumMasterRuntime,
    *,
    route: RouteContext,
    repository: Any,
    student_id: str,
    item: GeneratedItemV27,
    is_correct: bool,
    hints_used: int = 0,
    attempts: int = 1,
    previous: Mapping[str, MasterySnapshot] | None = None,
) -> Mapping[str, MasterySnapshot]:
    """Feed a generated/variant item result back into canonical mastery.

    No new mastery model is introduced. ``skill_id`` is deliberately stored in
    the existing ``knowledge_id`` dimension and the route-specific profile ID
    isolates high-school tracks.
    """

    # Fail closed if the item claims a skill outside the selected route.
    runtime.get_skill_context(route, item.skill_id)

    snapshots = dict(
        previous
        if previous is not None
        else repository.load_latest_knowledge_mastery(student_id, route.profile_id)
    )
    evidence = MasteryEvidence(
        bool(is_correct),
        difficulty=_DIFFICULTY.get(int(item.difficulty), "standard"),
        hints_used=int(hints_used),
        attempts=max(1, int(attempts)),
        source_type="variant_practice",
    )
    targeted = type(
        "GeneratedItemTarget",
        (),
        {
            "target_type": "knowledge",
            "target_id": item.skill_id,
            "evidence": evidence,
        },
    )()
    updated = aggregate_knowledge_evidence(
        [targeted],
        profile=route.profile_id,
        previous=snapshots,
    )
    repository.save_knowledge_mastery(student_id, route.profile_id, updated)
    return updated
