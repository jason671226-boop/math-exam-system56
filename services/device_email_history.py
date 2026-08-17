"""Pure helpers for device-local login Email history.

Only normalized Email addresses are accepted.  Authentication credentials,
tokens and identity identifiers are never part of this storage contract.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable


MAX_HISTORY_SIZE = 10
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
FORBIDDEN_STORAGE_FIELDS = frozenset(
    {"otp", "password", "jwt", "access_token", "refresh_token", "student_id", "auth.uid"}
)


def normalize_history_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if email == "trial@example.com" or not EMAIL_PATTERN.fullmatch(email):
        return ""
    return email


def clean_email_history(value: Any, *, limit: int = MAX_HISTORY_SIZE) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = []
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        email = normalize_history_email(item)
        if email and email not in result:
            result.append(email)
    return result[: max(0, limit)]


def remember_email(history: Iterable[str], email: Any) -> list[str]:
    normalized = normalize_history_email(email)
    current = clean_email_history(list(history))
    if not normalized:
        return current
    return [normalized, *(item for item in current if item != normalized)][:MAX_HISTORY_SIZE]


class DeviceEmailHistory:
    """Fail-open adapter around browser-local get/set/remove callbacks."""

    def __init__(
        self,
        reader: Callable[[], Any],
        writer: Callable[[str], None],
        remover: Callable[[], None],
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._remover = remover

    def load(self) -> list[str]:
        try:
            return clean_email_history(self._reader())
        except Exception:
            return []

    def remember(self, email: Any) -> list[str]:
        history = remember_email(self.load(), email)
        if not normalize_history_email(email):
            return history
        try:
            self._writer(json.dumps(history, ensure_ascii=False))
        except Exception:
            pass
        return history

    def clear(self) -> None:
        try:
            self._remover()
        except Exception:
            pass
