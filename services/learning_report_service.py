from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .mastery_service import MasterySnapshot, MasteryStatus, recommend_learning_priorities


@dataclass(frozen=True)
class LearningReport:
    profile: str
    total_count: int
    assessed_count: int
    status_counts: Mapping[str, int]
    strengths: tuple[Mapping[str, Any], ...]
    weaknesses: tuple[Mapping[str, Any], ...]
    priorities: tuple[Any, ...]
    thinking_summary: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ReportView:
    audience: str
    title: str
    introduction: str
    strength_message: str
    weakness_message: str
    next_step_message: str


def build_learning_report(profile: str, knowledge_points: tuple[Any, ...], snapshots: Mapping[str, MasterySnapshot], thinking: Mapping[str, Any], thinking_names: Mapping[str, str] | None = None) -> LearningReport:
    points = {point.id: point for point in knowledge_points}
    assessed = [snapshot for snapshot in snapshots.values() if snapshot.evidence_count]
    strong = sorted(
        (s for s in assessed if s.mastery_status in {MasteryStatus.BASIC, MasteryStatus.PROFICIENT}),
        key=lambda s: (-s.mastery_score, s.knowledge_id),
    )[:3]
    weak = sorted(
        (s for s in assessed if s.mastery_status in {MasteryStatus.NEEDS_WORK, MasteryStatus.LEARNING}),
        key=lambda s: (s.mastery_score, s.knowledge_id),
    )[:3]
    row = lambda s: {"knowledge_id": s.knowledge_id, "name": points[s.knowledge_id].sub_unit, "status": s.mastery_status.value, "score": s.mastery_score}
    thinking_rows = tuple(
        {"thinking_id": key, "name": (thinking_names or {}).get(key, key), "status": value.status.value, "score": value.score_numeric, "evidence_count": value.evidence_count}
        for key, value in sorted(thinking.items())
    )
    counts = {status.value: 0 for status in MasteryStatus}
    for point in knowledge_points:
        counts[snapshots[point.id].mastery_status.value if point.id in snapshots else MasteryStatus.UNASSESSED.value] += 1
    return LearningReport(profile, len(knowledge_points), len(assessed), counts, tuple(map(row, strong)), tuple(map(row, weak)), recommend_learning_priorities(knowledge_points, snapshots), thinking_rows)


def build_report_view(report: LearningReport, *, audience: str) -> ReportView:
    """Present one aggregate model for students or parents without recalculation."""

    if audience not in {"student", "parent"}:
        raise ValueError("audience must be student or parent")
    strength = "、".join(item["name"] for item in report.strengths) or "目前資料仍不足"
    weakness = "、".join(item["name"] for item in report.weaknesses) or "目前尚無明確需補強項目"
    if audience == "student":
        return ReportView(audience, "我的診斷報告", "這是依目前作答證據整理的學習快照。", strength, weakness, "先從第一項建議開始練習，完成後再回來查看變化。")
    return ReportView(audience, "家長學習摘要", "本報告反映孩子目前的作答證據，不是永久能力標籤。", strength, weakness, "建議先補足先備知識，再銜接目前年級的目標內容。")
