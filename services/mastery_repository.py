from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import UUID
from typing import Any, Mapping, MutableMapping, Protocol

from .mastery_service import MasterySnapshot, MasteryState, MasteryStatus


@dataclass(frozen=True)
class DiagnosticAttempt:
    student_id: str
    profile: str
    answers: Mapping[str, Any]
    results: Mapping[str, Any]
    evidence: Mapping[str, Any]
    completed_at: str
    attempt_key: str = ""
    source_type: str = "diagnostic"


class MasteryRepository(Protocol):
    def save_diagnostic_result(self, attempt: DiagnosticAttempt) -> None: ...
    def load_diagnostic_history(self, student_id: str, profile: str | None = None) -> tuple[DiagnosticAttempt, ...]: ...
    def save_knowledge_mastery(self, student_id: str, profile: str, snapshots: Mapping[str, MasterySnapshot]) -> None: ...
    def load_latest_knowledge_mastery(self, student_id: str, profile: str) -> Mapping[str, MasterySnapshot]: ...
    def save_thinking_skill_summary(self, student_id: str, profile: str, summary: Mapping[str, MasteryState]) -> None: ...
    def load_latest_thinking_skill_summary(self, student_id: str, profile: str) -> Mapping[str, MasteryState]: ...


class SessionStateMasteryRepository:
    """Session-backed adapter; no database or network side effects."""

    ROOT_KEY = "mastery_repository_v1"

    def __init__(self, state: MutableMapping[str, Any]) -> None:
        self.state = state

    def _root(self) -> dict[str, Any]:
        return self.state.setdefault(self.ROOT_KEY, {"attempts": [], "knowledge": {}, "thinking": {}})

    @staticmethod
    def _key(student_id: str, profile: str) -> str:
        if not student_id or not profile:
            raise ValueError("student_id and profile are required")
        return f"{student_id}::{profile}"

    def save_diagnostic_result(self, attempt: DiagnosticAttempt) -> None:
        attempts = self._root()["attempts"]
        if attempt.attempt_key:
            for index, stored in enumerate(attempts):
                if stored.student_id == attempt.student_id and stored.attempt_key == attempt.attempt_key:
                    attempts[index] = deepcopy(attempt)
                    return
        attempts.append(deepcopy(attempt))

    def load_diagnostic_history(self, student_id: str, profile: str | None = None) -> tuple[DiagnosticAttempt, ...]:
        return tuple(
            deepcopy(item) for item in self._root()["attempts"]
            if item.student_id == student_id and (profile is None or item.profile == profile)
        )

    def save_knowledge_mastery(self, student_id: str, profile: str, snapshots: Mapping[str, MasterySnapshot]) -> None:
        key = self._key(student_id, profile)
        stored = self._root()["knowledge"].setdefault(key, {})
        stored.update(deepcopy(dict(snapshots)))

    def load_latest_knowledge_mastery(self, student_id: str, profile: str) -> Mapping[str, MasterySnapshot]:
        return deepcopy(self._root()["knowledge"].get(self._key(student_id, profile), {}))

    def save_thinking_skill_summary(self, student_id: str, profile: str, summary: Mapping[str, MasteryState]) -> None:
        key = self._key(student_id, profile)
        stored = self._root()["thinking"].setdefault(key, {})
        stored.update(deepcopy(dict(summary)))

    def load_latest_thinking_skill_summary(self, student_id: str, profile: str) -> Mapping[str, MasteryState]:
        return deepcopy(self._root()["thinking"].get(self._key(student_id, profile), {}))

    def load_latest_student_mastery(self, student_id: str) -> Mapping[str, Mapping[str, MasterySnapshot]]:
        prefix = f"{student_id}::"
        return {
            key[len(prefix):]: deepcopy(value)
            for key, value in self._root()["knowledge"].items() if key.startswith(prefix)
        }

    def clear_student(self, student_id: str) -> None:
        root = self._root()
        root["attempts"] = [item for item in root["attempts"] if item.student_id != student_id]
        prefix = f"{student_id}::"
        for bucket in ("knowledge", "thinking"):
            for key in tuple(root[bucket]):
                if key.startswith(prefix):
                    root[bucket].pop(key, None)


class SupabaseMasteryRepository:
    """Injected-client adapter. It never creates a client or reads configuration."""

    def __init__(self, client: Any) -> None:
        if client is None or not callable(getattr(client, "table", None)):
            raise ValueError("a table-capable client is required")
        self.client = client

    @staticmethod
    def _require(student_id: str, profile: str) -> None:
        if not student_id or not profile:
            raise ValueError("student_id and profile are required")
        try:
            UUID(student_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("student_id must be a UUID") from exc

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @classmethod
    def _state_payload(cls, state: MasteryState) -> dict[str, Any]:
        payload = asdict(state)
        payload["status"] = state.status.value
        payload["last_assessed_at"] = cls._timestamp(state.last_assessed_at)
        payload["next_review_at"] = cls._timestamp(state.next_review_at)
        return payload

    def save_diagnostic_result(self, attempt: DiagnosticAttempt) -> None:
        self._require(attempt.student_id, attempt.profile)
        try:
            UUID(attempt.attempt_key)
        except (ValueError, AttributeError) as exc:
            raise ValueError("attempt_key must be a UUID") from exc
        result = self.client.table("diagnostic_attempts").upsert({
            "student_id": attempt.student_id, "profile_id": attempt.profile,
            "attempt_key": attempt.attempt_key, "source_type": attempt.source_type,
            "completed_at": attempt.completed_at, "metadata": {"answers": dict(attempt.answers)},
        }, on_conflict="student_id,attempt_key").execute()
        attempt_id = result.data[0]["id"]
        rows = []
        for question_id, item_result in attempt.results.items():
            rows.append({
                "attempt_id": attempt_id, "question_id": question_id,
                "credit": float(getattr(item_result, "credit", 0.0)), "source_type": attempt.source_type,
                "answer_payload": attempt.answers.get(question_id),
                "evidence_payload": [str(item) for item in attempt.evidence.get(question_id, ())],
            })
        if rows:
            self.client.table("diagnostic_item_results").upsert(rows, on_conflict="attempt_id,question_id").execute()

    def load_diagnostic_history(self, student_id: str, profile: str | None = None) -> tuple[DiagnosticAttempt, ...]:
        if not student_id:
            raise ValueError("student_id is required")
        query = self.client.table("diagnostic_attempts").select("*").eq("student_id", student_id)
        if profile:
            query = query.eq("profile_id", profile)
        rows = query.order("completed_at").execute().data
        history = []
        for row in rows:
            item_rows = self.client.table("diagnostic_item_results").select("*").eq("attempt_id", row["id"]).execute().data
            answers = dict(row.get("metadata", {}).get("answers", {}))
            answers.update({item["question_id"]: item.get("answer_payload") for item in item_rows})
            results = {item["question_id"]: item for item in item_rows}
            evidence = {item["question_id"]: item.get("evidence_payload", []) for item in item_rows}
            history.append(DiagnosticAttempt(row["student_id"], row["profile_id"], answers, results, evidence, row["completed_at"], row.get("attempt_key", ""), row.get("source_type", "diagnostic")))
        return tuple(history)

    def save_knowledge_mastery(self, student_id: str, profile: str, snapshots: Mapping[str, MasterySnapshot]) -> None:
        self._require(student_id, profile)
        updated_at = datetime.now(timezone.utc).isoformat()
        rows = [{
            "student_id": student_id, "profile_id": profile, "knowledge_id": item.knowledge_id,
            "mastery_status": item.mastery_status.value, "mastery_score": item.mastery_score,
            "confidence": item.confidence, "evidence_count": item.evidence_count,
            "weighted_credit": item.weighted_credit, "last_evidence_at": self._timestamp(item.last_evidence_at),
            "updated_at": updated_at,
            "metadata": {"correct_count": item.correct_count, "source_profiles": list(item.source_profiles), "state": self._state_payload(item.state)},
        } for item in snapshots.values()]
        if rows:
            self.client.table("knowledge_mastery").upsert(rows, on_conflict="student_id,profile_id,knowledge_id").execute()

    def load_latest_knowledge_mastery(self, student_id: str, profile: str) -> Mapping[str, MasterySnapshot]:
        self._require(student_id, profile)
        rows = self.client.table("knowledge_mastery").select("*").eq("student_id", student_id).eq("profile_id", profile).execute().data
        result = {}
        for row in rows:
            metadata = row.get("metadata", {})
            raw_state = dict(metadata.get("state", {}))
            raw_state["status"] = MasteryStatus(row["mastery_status"])
            for field in ("last_assessed_at", "next_review_at"):
                if isinstance(raw_state.get(field), str): raw_state[field] = datetime.fromisoformat(raw_state[field])
            state = MasteryState(**raw_state)
            result[row["knowledge_id"]] = MasterySnapshot(row["knowledge_id"], state.status, float(row["mastery_score"]), float(row["confidence"]), int(row["evidence_count"]), int(metadata.get("correct_count", 0)), float(row["weighted_credit"]), state.last_assessed_at, tuple(metadata.get("source_profiles", ())), state)
        return result

    def save_thinking_skill_summary(self, student_id: str, profile: str, summary: Mapping[str, MasteryState]) -> None:
        self._require(student_id, profile)
        updated_at = datetime.now(timezone.utc).isoformat()
        rows = [{"student_id": student_id, "profile_id": profile, "thinking_skill_id": key, "score": value.score_numeric, "confidence": value.confidence, "evidence_count": value.evidence_count, "last_evidence_at": self._timestamp(value.last_assessed_at), "updated_at": updated_at, "metadata": {"state": self._state_payload(value)}} for key, value in summary.items()]
        if rows: self.client.table("thinking_skill_evidence").upsert(rows, on_conflict="student_id,profile_id,thinking_skill_id").execute()

    def load_latest_thinking_skill_summary(self, student_id: str, profile: str) -> Mapping[str, MasteryState]:
        self._require(student_id, profile)
        rows = self.client.table("thinking_skill_evidence").select("*").eq("student_id", student_id).eq("profile_id", profile).execute().data
        result = {}
        for row in rows:
            raw = dict(row.get("metadata", {}).get("state", {})); raw["status"] = MasteryStatus(raw["status"])
            for field in ("last_assessed_at", "next_review_at"):
                if isinstance(raw.get(field), str): raw[field] = datetime.fromisoformat(raw[field])
            result[row["thinking_skill_id"]] = MasteryState(**raw)
        return result
