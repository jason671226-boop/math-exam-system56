"""Rerun-safe state transitions for the main Streamlit navigation widget."""

from __future__ import annotations

from typing import Any, MutableMapping, Sequence


MAIN_TAB_KEY = "main_tabs_control"
MOBILE_TAB_KEY = "mobile_main_nav_selector"
PENDING_MAIN_TAB_KEY = "pending_main_tab"


def queue_main_tab(
    state: MutableMapping[str, Any],
    label: str,
    valid_labels: Sequence[str],
) -> bool:
    """Queue a valid tab without mutating the instantiated widget key."""
    if label not in valid_labels:
        return False
    state[PENDING_MAIN_TAB_KEY] = label
    return True


def apply_pending_main_tab(
    state: MutableMapping[str, Any],
    valid_labels: Sequence[str],
) -> str:
    """Apply one queued transition before widget creation, then consume it."""
    labels = tuple(valid_labels)
    if not labels:
        raise ValueError("valid_labels must not be empty")

    pending = state.pop(PENDING_MAIN_TAB_KEY, None)
    current = state.get(MAIN_TAB_KEY)
    if pending in labels:
        current = pending
    elif current not in labels:
        current = labels[0]

    state[MAIN_TAB_KEY] = current
    if state.get(MOBILE_TAB_KEY) != current:
        state[MOBILE_TAB_KEY] = current
    return current
