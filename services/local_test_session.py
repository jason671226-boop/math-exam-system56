"""Local-development-only Supabase session bridge for fixed test accounts.

The service credential is accepted only as a server-side argument and is
never returned, stored in UI state, or used to read application data.  The
resulting ordinary user session remains subject to the existing RLS rules.
"""

from __future__ import annotations

import secrets
from typing import Any, Callable


ALLOWLISTED_LOCAL_TEST_EMAILS = frozenset(
    {
        "jason601226@gmail.com",
        "jason621226@gmail.com",
        "jason671226@gmail.com",
    }
)
LOCAL_TEST_ENVIRONMENTS = frozenset({"dev", "development", "local", "test"})


class LocalTestSessionError(ValueError):
    """Non-sensitive local test-login failure."""


def normalize_local_test_email(value: Any) -> str:
    return str(value or "").strip().lower()


def local_test_login_enabled(
    *, is_localhost: bool, explicit_flag: Any, app_env: Any
) -> bool:
    flag = str(explicit_flag or "").strip().lower() in {"1", "true", "yes", "on"}
    environment = str(app_env or "").strip().lower()
    return bool(is_localhost and flag and environment in LOCAL_TEST_ENVIRONMENTS)


def generate_visible_test_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _find_existing_auth_user(admin: Any, email: str) -> Any:
    for page in range(1, 11):
        users = admin.list_users(page=page, per_page=1000) or []
        for user in users:
            if normalize_local_test_email(getattr(user, "email", "")) == email:
                return user
        if len(users) < 1000:
            break
    raise LocalTestSessionError("allowlisted Auth user does not exist")


def create_local_test_user_session(
    *,
    supabase_url: str,
    service_role_key: str,
    email: str,
    user_client: Any,
    is_localhost: bool,
    explicit_flag: Any,
    app_env: Any,
    client_factory: Callable[..., Any] | None = None,
) -> Any:
    """Mint and exchange a link token for one existing allowlisted Auth user."""
    if not local_test_login_enabled(
        is_localhost=is_localhost,
        explicit_flag=explicit_flag,
        app_env=app_env,
    ):
        raise LocalTestSessionError("local test login is disabled")

    normalized = normalize_local_test_email(email)
    if normalized not in ALLOWLISTED_LOCAL_TEST_EMAILS:
        raise LocalTestSessionError("email is not allowlisted")
    if not str(supabase_url or "").startswith("https://"):
        raise LocalTestSessionError("Supabase URL is unavailable")
    if not service_role_key or user_client is None:
        raise LocalTestSessionError("server-side test session capability is unavailable")

    if client_factory is None:
        from supabase import create_client as client_factory
        from supabase.lib.client_options import SyncClientOptions

        admin_client = client_factory(
            supabase_url,
            service_role_key,
            options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
        )
    else:
        admin_client = client_factory(supabase_url, service_role_key)

    existing_user = _find_existing_auth_user(admin_client.auth.admin, normalized)
    link = admin_client.auth.admin.generate_link(
        {"type": "magiclink", "email": normalized}
    )
    link_user = getattr(link, "user", None)
    if str(getattr(link_user, "id", "")) != str(getattr(existing_user, "id", "")):
        raise LocalTestSessionError("Auth identity mismatch")
    server_otp = str(getattr(getattr(link, "properties", None), "email_otp", ""))
    if not server_otp:
        raise LocalTestSessionError("session exchange token is unavailable")

    response = user_client.auth.verify_otp(
        {"email": normalized, "token": server_otp, "type": "email"}
    )
    response_user = getattr(response, "user", None)
    if (
        getattr(response, "session", None) is None
        or str(getattr(response_user, "id", "")) != str(getattr(existing_user, "id", ""))
    ):
        raise LocalTestSessionError("real Auth session is unavailable")
    return response
