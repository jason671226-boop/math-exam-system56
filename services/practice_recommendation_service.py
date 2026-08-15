from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .mastery_service import MasterySnapshot, MasteryStatus, recommend_learning_priorities


@dataclass(frozen=True)
class PracticeRequest:
    target_knowledge_id: str
    recommendation_reason: str
    desired_difficulty: str
    requested_item_count: int
    prerequisite_context: Mapping[str, Any]


def build_practice_requests(knowledge_points: tuple[Any, ...], snapshots: Mapping[str, MasterySnapshot], item_count: int = 5) -> tuple[PracticeRequest, ...]:
    requests = []
    for priority in recommend_learning_priorities(knowledge_points, snapshots):
        status = priority.mastery_status
        requests.append(PracticeRequest(
            priority.knowledge_id,
            priority.reason,
            "basic" if status == MasteryStatus.NEEDS_WORK else "standard",
            item_count,
            {"prerequisite_for": priority.prerequisite_for, "current_status": status.value},
        ))
    return tuple(requests)
