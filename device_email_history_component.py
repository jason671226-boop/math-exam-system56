"""Minimal Streamlit component bridge for browser-local Email history."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import streamlit.components.v1 as components

try:
    from services.device_email_history import clean_email_history, normalize_history_email
except ModuleNotFoundError:
    from app.services.device_email_history import clean_email_history, normalize_history_email


STORAGE_KEY = "mathai_recent_emails_v2"
BRIDGE_COOKIE_KEY = "mathai_recent_emails_v1"
COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "device_email_history"
_component = components.declare_component(
    "mathai_device_email_history",
    path=str(COMPONENT_DIR),
)


def sync_device_email_history(
    *,
    remember: Any = "",
    clear: bool = False,
    seed: Iterable[str] = (),
    key: str = "mathai_device_email_history_sync",
) -> list[str] | None:
    """Synchronize history with localStorage; return None until browser responds."""
    email = normalize_history_email(remember)
    value = _component(
        storage_key=STORAGE_KEY,
        cookie_key=BRIDGE_COOKIE_KEY,
        command="clear" if clear else ("remember" if email else "read"),
        email=email,
        seed=clean_email_history(list(seed)),
        default=None,
        key=key,
    )
    if value is None:
        return None
    return clean_email_history(value)
