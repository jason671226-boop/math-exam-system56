from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .mastery_repository import DiagnosticAttempt
from .mastery_service import MasterySnapshot, MasteryState, MasteryStatus
from .teacher_feedback_service import TeacherFeedback


@dataclass(frozen=True)
class ReportRecommendation:
    title: str
    target: str
    priority: int
    reason: str
    evidence_summary: str
    next_action: str


@dataclass(frozen=True)
class ParentReport:
    student_id: str
    profile: str
    diagnostic_summary: Mapping[str, Any]
    strengths: tuple[Mapping[str, Any], ...]
    knowledge_priorities: tuple[Mapping[str, Any], ...]
    thinking_priorities: tuple[Mapping[str, Any], ...]
    teacher_observations: Mapping[str, tuple[TeacherFeedback, ...]]
    recommendations: tuple[ReportRecommendation, ...]
    parent_actions: tuple[str, ...]
    messages: tuple[str, ...]


def _credit(result: Any) -> float:
    raw = result.get("credit", 0.0) if isinstance(result, Mapping) else getattr(result, "credit", 0.0)
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 0.0


def _diagnostic_summary(attempts: Sequence[DiagnosticAttempt]) -> dict[str, Any]:
    if not attempts:
        return {
            "available": False,
            "question_count": 0,
            "full_credit": 0,
            "partial_credit": 0,
            "evidence_count": 0,
            "average_credit": None,
            "completed_at": None,
        }
    latest = max(attempts, key=lambda item: item.completed_at)
    credits = [_credit(item) for item in latest.results.values()]
    return {
        "available": True,
        "question_count": len(credits),
        "full_credit": sum(value >= 1.0 for value in credits),
        "partial_credit": sum(0.0 < value < 1.0 for value in credits),
        "evidence_count": sum(len(items or ()) for items in latest.evidence.values()),
        "average_credit": round(sum(credits) / len(credits) * 100, 1) if credits else None,
        "completed_at": latest.completed_at,
    }


def _knowledge_reason(snapshot: MasterySnapshot) -> str:
    return f"目前累積 {snapshot.evidence_count} 次學習證據，答題穩定度仍在建立。"

def _knowledge_priorities(
    snapshots: Mapping[str, MasterySnapshot],
    names: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    status_rank = {
        MasteryStatus.NEEDS_WORK: 0,
        MasteryStatus.LEARNING: 1,
        MasteryStatus.BASIC: 2,
        MasteryStatus.PROFICIENT: 3,
        MasteryStatus.UNASSESSED: 4,
    }
    eligible = [item for item in snapshots.values() if item.evidence_count > 0]
    ranked = sorted(
        eligible,
        key=lambda item: (
            status_rank[item.mastery_status],
            item.mastery_score,
            item.confidence,
            item.evidence_count,
            -item.weighted_credit,
            item.knowledge_id,
        ),
    )[:3]
    return tuple(
        {
            "target_id": item.knowledge_id,
            "name": names.get(item.knowledge_id, item.knowledge_id),
            "status": item.mastery_status.value,
            "score": item.mastery_score,
            "confidence": item.confidence,
            "evidence_count": item.evidence_count,
            "weighted_credit": item.weighted_credit,
            "reason": _knowledge_reason(item),
        }
        for item in ranked
    )


def _strengths(
    snapshots: Mapping[str, MasterySnapshot],
    names: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    eligible = [
        item for item in snapshots.values()
        if item.evidence_count >= 2
        and item.mastery_status in {MasteryStatus.BASIC, MasteryStatus.PROFICIENT}
    ]
    ranked = sorted(
        eligible,
        key=lambda item: (-item.mastery_score, -item.confidence, -item.evidence_count, item.knowledge_id),
    )[:3]
    return tuple(
        {
            "target_id": item.knowledge_id,
            "name": names.get(item.knowledge_id, item.knowledge_id),
            "reason": (
                f"已有 {item.evidence_count} 次累積證據，近期表現較穩定。"
            ),
        }
        for item in ranked
    )


def _thinking_priorities(
    thinking: Mapping[str, MasteryState],
    names: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    eligible = [(key, value) for key, value in thinking.items() if value.evidence_count >= 2]
    ranked = sorted(
        eligible,
        key=lambda pair: (
            pair[1].score_numeric,
            pair[1].confidence,
            pair[1].evidence_count,
            pair[0],
        ),
    )[:3]
    return tuple(
        {
            "target_id": key,
            "name": names.get(key, key),
            "status": state.status.value,
            "score": state.score_numeric,
            "confidence": state.confidence,
            "evidence_count": state.evidence_count,
            "reason": (
                f"目前累積 {state.evidence_count} 次解題策略證據，適合繼續建立穩定策略。"
            ),
        }
        for key, state in ranked
    )


def build_parent_report(
    *,
    student_id: str,
    profile: str,
    diagnostic_attempts: Sequence[DiagnosticAttempt],
    knowledge: Mapping[str, MasterySnapshot],
    thinking: Mapping[str, MasteryState],
    teacher_feedback: Sequence[TeacherFeedback],
    knowledge_names: Mapping[str, str] | None = None,
    thinking_names: Mapping[str, str] | None = None,
) -> ParentReport:
    if any(item.student_id != student_id for item in diagnostic_attempts):
        raise ValueError("diagnostic evidence belongs to another student")
    if any(item.student_id != student_id for item in teacher_feedback):
        raise ValueError("teacher feedback belongs to another student")
    if any(item.profile != profile for item in diagnostic_attempts):
        raise ValueError("diagnostic evidence belongs to another profile")
    if any(item.profile_id != profile for item in teacher_feedback):
        raise ValueError("teacher feedback belongs to another profile")

    knowledge_names = knowledge_names or {}
    thinking_names = thinking_names or {}
    summary = _diagnostic_summary(diagnostic_attempts)
    strengths = _strengths(knowledge, knowledge_names)
    knowledge_top = _knowledge_priorities(knowledge, knowledge_names)
    thinking_top = _thinking_priorities(thinking, thinking_names)
    observations = {
        scope: tuple(item for item in teacher_feedback if item.scope_type == scope)[:5]
        for scope in ("overall", "knowledge", "thinking_skill")
    }

    recommendations: list[ReportRecommendation] = []
    for item in knowledge_top:
        recommendations.append(
            ReportRecommendation(
                title=f"優先補強：{item['name']}",
                target=item["target_id"],
                priority=len(recommendations) + 1,
                reason=item["reason"],
                evidence_summary=(
                    f"依據 {item['evidence_count']} 次學習紀錄與近期作答結果排序。"
                ),
                next_action="先完成一組基礎題，再用一組變形題確認能否獨立轉換策略。",
            )
        )
    if thinking_top and len(recommendations) < 3:
        item = thinking_top[0]
        recommendations.append(
            ReportRecommendation(
                title=f"建立策略：{item['name']}",
                target=item["target_id"],
                priority=len(recommendations) + 1,
                reason=item["reason"],
                evidence_summary=f"依據 {item['evidence_count']} 次解題策略紀錄排序。",
                next_action="解題時先口述條件與步驟，完成後再檢查策略是否可套用到變形題。",
            )
        )

    actions: list[str] = []
    if knowledge_top:
        actions.append(f"本週陪孩子用 10 分鐘說明「{knowledge_top[0]['name']}」的解題步驟，不直接提示答案。")
    if thinking_top:
        actions.append(f"做題前請孩子先圈出條件，並說明準備使用的「{thinking_top[0]['name']}」策略。")
    if strengths:
        actions.append(f"請孩子示範一題「{strengths[0]['name']}」，用教別人的方式鞏固已累積的證據。")
    if not actions:
        actions.append("先完成一份短診斷或練習，累積足夠證據後再決定補強方向。")

    messages: list[str] = []
    if not summary["available"]:
        messages.append("目前沒有最近診斷資料；報告僅呈現已累積的學習證據。")
    if not strengths:
        messages.append("目前尚未累積足夠證據辨識穩定優勢，並不代表學生沒有優勢。")
    if not thinking_top:
        messages.append("目前累積的解題策略證據還不足，完成更多練習後再更新判斷。")
    if not teacher_feedback:
        messages.append("目前尚無老師觀察紀錄。")

    return ParentReport(
        student_id=student_id,
        profile=profile,
        diagnostic_summary=summary,
        strengths=strengths,
        knowledge_priorities=knowledge_top,
        thinking_priorities=thinking_top,
        teacher_observations=observations,
        recommendations=tuple(recommendations),
        parent_actions=tuple(actions),
        messages=tuple(messages),
    )
