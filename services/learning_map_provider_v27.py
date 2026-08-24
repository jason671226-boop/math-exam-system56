from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .curriculum_master_bridge import route_from_user_profile
from .curriculum_master_runtime import CurriculumMasterRuntime, CurriculumRouteError, RouteContext
from .learning_map_v27 import build_learning_map_model_v27


@dataclass(frozen=True)
class LearningMapProviderResultV27:
    route: RouteContext
    profile_id: str
    student_id: str
    snapshots: Mapping[str, Any]
    model: Mapping[str, Any]


def resolve_learning_map_v27(
    runtime: CurriculumMasterRuntime,
    *,
    user_profile: Mapping[str, Any],
    repository: Any,
    student_id: str,
) -> LearningMapProviderResultV27:
    """Resolve route, load canonical mastery snapshots and build the v2.7 model.

    This provider intentionally does not guess ambiguous high-school tracks.
    `route_from_user_profile` delegates to the deterministic runtime router, so
    G11 requires A/B, G12 requires 甲/乙, and technical G10 requires A/B/C.

    The existing mastery repository API is reused unchanged. Canonical v2.7
    skill IDs are stored in the existing `knowledge_id` dimension, while the
    route-specific profile_id keeps mastery from different tracks isolated.
    """

    route = route_from_user_profile(runtime, user_profile)
    profile_id = route.profile_id
    snapshots = repository.load_latest_knowledge_mastery(student_id, profile_id)
    model = build_learning_map_model_v27(runtime, route, snapshots)
    return LearningMapProviderResultV27(
        route=route,
        profile_id=profile_id,
        student_id=student_id,
        snapshots=snapshots,
        model=model,
    )


def try_resolve_learning_map_v27(
    runtime: CurriculumMasterRuntime,
    *,
    user_profile: Mapping[str, Any],
    repository: Any,
    student_id: str,
) -> LearningMapProviderResultV27 | None:
    """Fail closed for unresolved routes/data so legacy UI can remain active."""

    try:
        return resolve_learning_map_v27(
            runtime,
            user_profile=user_profile,
            repository=repository,
            student_id=student_id,
        )
    except (CurriculumRouteError, OSError, ValueError, KeyError):
        return None
