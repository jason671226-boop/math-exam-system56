from __future__ import annotations

import re
from typing import Any, MutableMapping


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthFlowError(ValueError):
    """Safe authentication error without credential or token details."""


def normalize_login_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise AuthFlowError("請輸入有效的 Email。")
    return email


def request_email_otp(client: Any, email: str) -> str:
    """Request an OTP/magic-link email without creating unprovisioned users."""
    normalized = normalize_login_email(email)
    if client is None or not hasattr(client, "auth"):
        raise AuthFlowError("Supabase Auth 目前無法使用。")
    try:
        client.auth.sign_in_with_otp(
            {
                "email": normalized,
                "options": {"should_create_user": False},
            }
        )
    except Exception as exc:
        raise AuthFlowError("無法寄送登入驗證信，請確認帳號已加入 Private Beta。") from exc
    return normalized


def verify_email_otp(client: Any, email: str, token: str) -> Any:
    normalized = normalize_login_email(email)
    clean_token = str(token or "").strip()
    if not clean_token:
        raise AuthFlowError("請輸入驗證碼。")
    if client is None or not hasattr(client, "auth"):
        raise AuthFlowError("Supabase Auth 目前無法使用。")
    try:
        response = client.auth.verify_otp(
            {"email": normalized, "token": clean_token, "type": "email"}
        )
    except Exception as exc:
        raise AuthFlowError("驗證失敗或驗證碼已過期，請重新取得驗證信。") from exc
    user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if not getattr(user, "id", None) or session is None:
        raise AuthFlowError("Supabase Auth session 未建立，請重新登入。")
    return response


def sign_out_safely(client: Any) -> None:
    if client is None or not hasattr(client, "auth"):
        return
    try:
        client.auth.sign_out()
    except Exception:
        pass


def clear_authenticated_session(
    state: MutableMapping[str, Any],
    client: Any,
) -> None:
    """Sign out and remove only the application keys tied to Supabase Auth."""
    sign_out_safely(client)
    for key in (
        "private_beta_auth_client",
        "private_beta_auth_email",
        "private_beta_otp_sent",
        "learning_persistence_warning",
    ):
        state.pop(key, None)
