from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .mastery_service import MasteryEvidence, MasterySnapshot, aggregate_knowledge_evidence
from .practice_recommendation_service import PracticeRequest


@dataclass(frozen=True)
class DemoPracticeItem:
    item_id: str
    knowledge_id: str
    prompt: str
    accepted_answer: str
    difficulty: str
    source_status: str = "developer_demo_not_production_item_bank"


@dataclass(frozen=True)
class PracticeResult:
    item_id: str
    is_correct: bool
    source_type: str = "practice"


def score_practice_response(item: DemoPracticeItem, answer: str) -> PracticeResult:
    """Formal deterministic scoring boundary used by UI and smoke tests."""
    return PracticeResult(item.item_id, str(answer).strip() == item.accepted_answer)


def select_demo_practice_items(request: PracticeRequest) -> tuple[DemoPracticeItem, ...]:
    """Small deterministic fixture proving the loop; not a production item bank."""

    return tuple(
        DemoPracticeItem(
            f"DEMO-{request.target_knowledge_id}-{index}", request.target_knowledge_id,
            f"補強練習 {index}：完成此知識點的教師檢核題。", "完成", request.desired_difficulty,
        ) for index in range(1, min(request.requested_item_count, 3) + 1)
    )


def apply_practice_results(profile: str, snapshots: Mapping[str, MasterySnapshot], items: tuple[DemoPracticeItem, ...], answers: Mapping[str, str]) -> dict[str, MasterySnapshot]:
    targeted = []
    for item in items:
        result = score_practice_response(item, answers.get(item.item_id, ""))
        targeted.append(type("PracticeTarget", (), {
            "target_type": "knowledge", "target_id": item.knowledge_id,
            "evidence": MasteryEvidence(result.is_correct, item.difficulty, source_type=result.source_type),
        })())
    return aggregate_knowledge_evidence(targeted, profile=profile, previous=snapshots)
