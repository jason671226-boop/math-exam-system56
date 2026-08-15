from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping
from uuid import UUID, uuid4

from .mastery_repository import (
    DiagnosticAttempt,
    MasteryRepository,
    SessionStateMasteryRepository,
    SupabaseMasteryRepository,
)
from .mastery_service import MasterySnapshot, MasteryState


LOCAL_STUDENT_KEY = "local_learning_student_id"
PERSISTENCE_WARNING_KEY = "learning_persistence_warning"


class LearningIdentityError(ValueError):
    """Raised when an authenticated identity cannot resolve to one student."""


@dataclass(frozen=True)
class AuthenticatedStudent:
    auth_user_id: str
    student_id: str
    role: str


@dataclass(frozen=True)
class LearningRuntime:
    student_id: str
    repository: MasteryRepository
    persistence_enabled: bool
    identity_source: str
    message: str = ""


def _uuid(value: Any, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise LearningIdentityError(f"{field} must be a UUID") from exc


def current_auth_user_id(client: Any) -> str:
    """Return the signed-in Supabase Auth UUID; never infer it from email."""
    if client is None or not hasattr(client, "auth"):
        raise LearningIdentityError("Supabase Auth session is unavailable")
    response = client.auth.get_user()
    user = getattr(response, "user", None)
    user_id = getattr(user, "id", None)
    if not user_id:
        raise LearningIdentityError("Supabase Auth session is unavailable")
    return _uuid(user_id, field="auth user id")


def resolve_authenticated_student(
    client: Any,
    *,
    preferred_student_id: str | None = None,
) -> AuthenticatedStudent:
    """Resolve auth.uid() ownership through student_access without using email."""
    user_id = current_auth_user_id(client)
    rows = (
        client.table("student_access")
        .select("student_id,role")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    owned = [row for row in (rows or []) if row.get("role") in {"owner", "student", "guardian"}]
    if preferred_student_id:
        preferred = _uuid(preferred_student_id, field="preferred student id")
        owned = [row for row in owned if str(row.get("student_id")) == preferred]
    if not owned:
        raise LearningIdentityError("No authorized student_access mapping is available")
    if len(owned) != 1:
        raise LearningIdentityError("Multiple students require an explicit student selection")
    student_id = _uuid(owned[0].get("student_id"), field="student id")
    return AuthenticatedStudent(user_id, student_id, str(owned[0]["role"]))


def ensure_local_student_id(state: MutableMapping[str, Any]) -> str:
    """Create a session-only UUID; email is never used as relational identity."""
    current = state.get(LOCAL_STUDENT_KEY)
    try:
        return _uuid(current, field="local student id")
    except LearningIdentityError:
        generated = str(uuid4())
        state[LOCAL_STUDENT_KEY] = generated
        return generated


class ReconciledMasteryRepository:
    """DB-backed repository with a session mirror and safe transient fallback."""

    def __init__(
        self,
        primary: MasteryRepository,
        session: SessionStateMasteryRepository,
        state: MutableMapping[str, Any],
    ) -> None:
        self.primary = primary
        self.session = session
        self.state = state

    def _warning(self) -> None:
        self.state[PERSISTENCE_WARNING_KEY] = (
            "雲端學習紀錄暫時無法同步；本次結果仍保留在目前瀏覽器 session。"
        )

    def _clear_warning(self) -> None:
        self.state.pop(PERSISTENCE_WARNING_KEY, None)

    def save_diagnostic_result(self, attempt: DiagnosticAttempt) -> None:
        self.session.save_diagnostic_result(attempt)
        try:
            self.primary.save_diagnostic_result(attempt)
            self._clear_warning()
        except Exception:
            self._warning()

    def load_diagnostic_history(
        self, student_id: str, profile: str | None = None
    ) -> tuple[DiagnosticAttempt, ...]:
        session_rows = self.session.load_diagnostic_history(student_id, profile)
        try:
            persisted = self.primary.load_diagnostic_history(student_id, profile)
            self._clear_warning()
        except Exception:
            self._warning()
            return session_rows
        keyed: dict[str, DiagnosticAttempt] = {}
        for item in (*persisted, *session_rows):
            key = item.attempt_key or f"{item.profile}:{item.completed_at}"
            keyed[key] = item
        return tuple(sorted(keyed.values(), key=lambda item: item.completed_at))

    def save_knowledge_mastery(
        self,
        student_id: str,
        profile: str,
        snapshots: Mapping[str, MasterySnapshot],
    ) -> None:
        self.session.save_knowledge_mastery(student_id, profile, snapshots)
        try:
            self.primary.save_knowledge_mastery(student_id, profile, snapshots)
            self._clear_warning()
        except Exception:
            self._warning()

    def load_latest_knowledge_mastery(
        self, student_id: str, profile: str
    ) -> Mapping[str, MasterySnapshot]:
        current = dict(self.session.load_latest_knowledge_mastery(student_id, profile))
        try:
            persisted = dict(self.primary.load_latest_knowledge_mastery(student_id, profile))
            self._clear_warning()
        except Exception:
            self._warning()
            return current
        persisted.update(current)
        return persisted

    def save_thinking_skill_summary(
        self,
        student_id: str,
        profile: str,
        summary: Mapping[str, MasteryState],
    ) -> None:
        self.session.save_thinking_skill_summary(student_id, profile, summary)
        try:
            self.primary.save_thinking_skill_summary(student_id, profile, summary)
            self._clear_warning()
        except Exception:
            self._warning()

    def load_latest_thinking_skill_summary(
        self, student_id: str, profile: str
    ) -> Mapping[str, MasteryState]:
        current = dict(self.session.load_latest_thinking_skill_summary(student_id, profile))
        try:
            persisted = dict(self.primary.load_latest_thinking_skill_summary(student_id, profile))
            self._clear_warning()
        except Exception:
            self._warning()
            return current
        persisted.update(current)
        return persisted


def build_learning_runtime(
    state: MutableMapping[str, Any],
    authenticated_client: Any | None,
    *,
    preferred_student_id: str | None = None,
) -> LearningRuntime:
    session = SessionStateMasteryRepository(state)
    if authenticated_client is None:
        return LearningRuntime(
            ensure_local_student_id(state),
            session,
            False,
            "legacy_session",
            "目前登入未建立 Supabase Auth session；學習紀錄僅保留於本次 session。",
        )
    try:
        identity = resolve_authenticated_student(
            authenticated_client,
            preferred_student_id=preferred_student_id,
        )
    except LearningIdentityError as exc:
        return LearningRuntime(
            ensure_local_student_id(state),
            session,
            False,
            "auth_unavailable",
            str(exc),
        )
    primary = SupabaseMasteryRepository(authenticated_client)
    return LearningRuntime(
        identity.student_id,
        ReconciledMasteryRepository(primary, session, state),
        True,
        "supabase_auth",
    )
