"""Rerun-safe state transitions for the main Streamlit navigation widget."""

from __future__ import annotations

from typing import Any, MutableMapping, Sequence

# Private-beta testing period only: install the direct on-screen OTP bridge before
# app.py imports the Auth helpers.  The bridge is isolated in its own module so
# production Email OTP can be restored later by removing these lines.
try:
    from testing_login_patch import install_testing_login_patch

    install_testing_login_patch()
except Exception:
    # Navigation must never fail just because the temporary testing bridge cannot
    # load.  In that case app.py falls back to the normal Supabase Auth path.
    pass


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
