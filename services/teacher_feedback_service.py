from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol
from uuid import UUID


SCOPES = {"overall", "knowledge", "thinking_skill"}


class TeacherFeedbackError(ValueError):
    """Safe validation or persistence error for the teacher evidence layer."""


@dataclass(frozen=True)
class TeacherFeedback:
    id: str
    student_id: str
    recorded_by: str
    profile_id: str
    scope_type: str
    feedback_text: str
    recommendation: str = ""
    knowledge_point_id: str | None = None
    thinking_skill_id: str | None = None
    created_at: str = ""


class TeacherFeedbackRepository(Protocol):
    def create(self, feedback: TeacherFeedback) -> TeacherFeedback: ...
    def list_for_student(
        self,
        student_id: str,
        limit: int = 20,
        profile_id: str | None = None,
    ) -> tuple[TeacherFeedback, ...]: ...


def _uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise TeacherFeedbackError(f"{field} must be a UUID") from exc


def validate_feedback(
    feedback: TeacherFeedback,
    *,
    knowledge_ids: set[str] | None = None,
    thinking_ids: set[str] | None = None,
) -> TeacherFeedback:
    _uuid(feedback.student_id, "student_id")
    _uuid(feedback.recorded_by, "recorded_by")
    if not feedback.profile_id.strip():
        raise TeacherFeedbackError("profile_id is required")
    if feedback.scope_type not in SCOPES:
        raise TeacherFeedbackError("unsupported feedback scope")
    if not feedback.feedback_text.strip():
        raise TeacherFeedbackError("feedback text is required")
    if len(feedback.feedback_text.strip()) > 2000 or len(feedback.recommendation.strip()) > 1000:
        raise TeacherFeedbackError("feedback text is too long")

    knowledge_id = (feedback.knowledge_point_id or "").strip() or None
    thinking_id = (feedback.thinking_skill_id or "").strip() or None
    if feedback.scope_type == "overall" and (knowledge_id or thinking_id):
        raise TeacherFeedbackError("overall feedback cannot have a target mapping")
    if feedback.scope_type == "knowledge" and (not knowledge_id or thinking_id):
        raise TeacherFeedbackError("knowledge feedback requires one knowledge mapping")
    if feedback.scope_type == "thinking_skill" and (not thinking_id or knowledge_id):
        raise TeacherFeedbackError("thinking feedback requires one thinking mapping")
    if knowledge_id and knowledge_ids is not None and knowledge_id not in knowledge_ids:
        raise TeacherFeedbackError("unknown knowledge mapping")
    if thinking_id and thinking_ids is not None and thinking_id not in thinking_ids:
        raise TeacherFeedbackError("unknown thinking mapping")
    return feedback


def create_teacher_feedback(
    repository: TeacherFeedbackRepository,
    *,
    student_id: str,
    recorded_by: str,
    profile_id: str,
    scope_type: str,
    feedback_text: str,
    recommendation: str = "",
    knowledge_point_id: str | None = None,
    thinking_skill_id: str | None = None,
    knowledge_ids: set[str] | None = None,
    thinking_ids: set[str] | None = None,
) -> TeacherFeedback:
    feedback = TeacherFeedback(
        id="",
        student_id=student_id,
        recorded_by=recorded_by,
        profile_id=profile_id.strip(),
        scope_type=scope_type,
        feedback_text=feedback_text.strip(),
        recommendation=recommendation.strip(),
        knowledge_point_id=knowledge_point_id,
        thinking_skill_id=thinking_skill_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    validate_feedback(
        feedback,
        knowledge_ids=knowledge_ids,
        thinking_ids=thinking_ids,
    )
    try:
        return repository.create(feedback)
    except TeacherFeedbackError:
        raise
    except Exception as exc:
        raise TeacherFeedbackError("teacher feedback could not be saved") from exc


def create_teacher_feedback_once(
    repository: TeacherFeedbackRepository,
    *,
    duplicate_window_seconds: int = 30,
    **values: Any,
) -> tuple[TeacherFeedback, bool]:
    """Avoid a repeated UI submit without changing or bypassing persistence rules."""
    candidate = TeacherFeedback(
        id="",
        student_id=str(values.get("student_id") or ""),
        recorded_by=str(values.get("recorded_by") or ""),
        profile_id=str(values.get("profile_id") or "").strip(),
        scope_type=str(values.get("scope_type") or ""),
        feedback_text=str(values.get("feedback_text") or "").strip(),
        recommendation=str(values.get("recommendation") or "").strip(),
        knowledge_point_id=values.get("knowledge_point_id"),
        thinking_skill_id=values.get("thinking_skill_id"),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    validate_feedback(
        candidate,
        knowledge_ids=values.get("knowledge_ids"),
        thinking_ids=values.get("thinking_ids"),
    )
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(0, duplicate_window_seconds))
    try:
        recent = repository.list_for_student(
            candidate.student_id,
            limit=10,
            profile_id=candidate.profile_id,
        )
    except Exception as exc:
        raise TeacherFeedbackError("teacher feedback could not be checked") from exc
    for row in recent:
        try:
            created_at = datetime.fromisoformat(row.created_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        comparable = (
            row.recorded_by == candidate.recorded_by
            and row.scope_type == candidate.scope_type
            and row.feedback_text.strip() == candidate.feedback_text
            and row.recommendation.strip() == candidate.recommendation
            and row.knowledge_point_id == candidate.knowledge_point_id
            and row.thinking_skill_id == candidate.thinking_skill_id
        )
        if comparable and created_at >= cutoff:
            return row, False
    return create_teacher_feedback(repository, **values), True


class SessionTeacherFeedbackRepository:
    ROOT_KEY = "teacher_feedback_v1"

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    def create(self, feedback: TeacherFeedback) -> TeacherFeedback:
        validate_feedback(feedback)
        rows = self.state.setdefault(self.ROOT_KEY, [])
        stored = TeacherFeedback(**{**feedback.__dict__, "id": feedback.id or f"local-{len(rows) + 1}"})
        rows.append(stored)
        return stored

    def list_for_student(
        self,
        student_id: str,
        limit: int = 20,
        profile_id: str | None = None,
    ) -> tuple[TeacherFeedback, ...]:
        rows = [
            row
            for row in self.state.setdefault(self.ROOT_KEY, [])
            if row.student_id == student_id
            and (profile_id is None or row.profile_id == profile_id)
        ]
        return tuple(sorted(rows, key=lambda row: row.created_at, reverse=True)[:limit])


class SupabaseTeacherFeedbackRepository:
    """Authenticated client adapter; authorization remains enforced by RLS."""

    def __init__(self, client: Any) -> None:
        if client is None or not callable(getattr(client, "table", None)):
            raise TeacherFeedbackError("authenticated feedback client is unavailable")
        self.client = client

    @staticmethod
    def _from_row(row: Mapping[str, Any]) -> TeacherFeedback:
        return TeacherFeedback(
            id=str(row.get("id") or ""),
            student_id=str(row.get("student_id") or ""),
            recorded_by=str(row.get("recorded_by") or ""),
            profile_id=str(row.get("profile_id") or ""),
            scope_type=str(row.get("scope_type") or ""),
            feedback_text=str(row.get("feedback_text") or ""),
            recommendation=str(row.get("recommendation") or ""),
            knowledge_point_id=row.get("knowledge_point_id"),
            thinking_skill_id=row.get("thinking_skill_id"),
            created_at=str(row.get("created_at") or ""),
        )

    def create(self, feedback: TeacherFeedback) -> TeacherFeedback:
        validate_feedback(feedback)
        payload = {
            "student_id": feedback.student_id,
            "recorded_by": feedback.recorded_by,
            "profile_id": feedback.profile_id,
            "scope_type": feedback.scope_type,
            "feedback_text": feedback.feedback_text,
            "recommendation": feedback.recommendation or None,
            "knowledge_point_id": feedback.knowledge_point_id,
            "thinking_skill_id": feedback.thinking_skill_id,
        }
        response = self.client.table("teacher_feedback").insert(payload).execute()
        rows = getattr(response, "data", None) or []
        if len(rows) != 1:
            raise TeacherFeedbackError("teacher feedback write was not confirmed")
        return self._from_row(rows[0])

    def list_for_student(
        self,
        student_id: str,
        limit: int = 20,
        profile_id: str | None = None,
    ) -> tuple[TeacherFeedback, ...]:
        _uuid(student_id, "student_id")
        query = self.client.table("teacher_feedback").select("*").eq("student_id", student_id)
        if profile_id is not None:
            if not profile_id.strip():
                raise TeacherFeedbackError("profile_id is required")
            query = query.eq("profile_id", profile_id)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return tuple(self._from_row(row) for row in (getattr(response, "data", None) or []))
