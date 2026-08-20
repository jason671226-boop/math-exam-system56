from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .curriculum_master_runtime import CurriculumMasterRuntime, RouteContext


@dataclass(frozen=True)
class LearningMapPriorityV27:
    skill_id: str
    reason: str
    mastery_score: float
    confidence: float
    blocking_prerequisites: tuple[str, ...]


def build_learning_map_model_v27(
    runtime: CurriculumMasterRuntime,
    route: RouteContext,
    snapshots: Mapping[str, Any],
) -> dict[str, Any]:
    rows = []
    for skill in runtime.load_standard_skills(route):
        snap = snapshots.get(skill.skill_id)
        rows.append({
            "knowledge_id": skill.skill_id,
            "skill_id": skill.skill_id,
            "main_unit": skill.main_unit,
            "sub_unit": skill.subunit,
            "learning_focus": skill.focus,
            "difficulty": skill.difficulty,
            "mastery_status": getattr(getattr(snap, "mastery_status", None), "value", "unassessed"),
            "mastery_score": float(getattr(snap, "mastery_score", 0.0) or 0.0),
            "confidence": float(getattr(snap, "confidence", 0.0) or 0.0),
            "evidence_count": int(getattr(snap, "evidence_count", 0) or 0),
        })
    return {
        "route": route,
        "profile_id": route.profile_id,
        "rows": rows,
        "priorities": recommend_learning_priorities_v27(runtime, route, snapshots),
    }


def _score(snapshot: Any) -> float:
    return float(getattr(snapshot, "mastery_score", 0.0) or 0.0)


def _confidence(snapshot: Any) -> float:
    return float(getattr(snapshot, "confidence", 0.0) or 0.0)


def recommend_learning_priorities_v27(
    runtime: CurriculumMasterRuntime,
    route: RouteContext,
    snapshots: Mapping[str, Any],
    *,
    limit: int = 3,
    mastery_threshold: float = 60.0,
) -> tuple[LearningMapPriorityV27, ...]:
    candidates = []
    for skill in runtime.load_standard_skills(route):
        snap = snapshots.get(skill.skill_id)
        score = _score(snap)
        confidence = _confidence(snap)
        ctx = runtime.get_skill_context(route, skill.skill_id)
        blockers = []
        for prereq in ctx.prerequisite_ids:
            ps = snapshots.get(prereq)
            if ps is None or _score(ps) < mastery_threshold:
                blockers.append(prereq)
        if blockers:
            reason = "先補強阻塞此技能的先備知識"
            rank = (0, len(blockers) * -1, score, confidence)
        elif snap is None:
            reason = "尚未評估，建議先建立基準證據"
            rank = (2, 0, 0.0, 0.0)
        elif score < mastery_threshold:
            reason = "目前掌握度不足，需優先補強"
            rank = (1, 0, score, confidence)
        else:
            continue
        candidates.append((rank, LearningMapPriorityV27(skill.skill_id, reason, score, confidence, tuple(blockers))))
    candidates.sort(key=lambda item: item[0])
    return tuple(item[1] for item in candidates[:limit])
