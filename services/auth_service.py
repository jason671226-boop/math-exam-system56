from __future__ import annotations

import re
from typing import Any, MutableMapping


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthFlowError(ValueError):
    """Safe authentication error without credential or token details."""

    def __init__(self, message: str, *, code: str = "login_unavailable") -> None:
        super().__init__(message)
        self.code = code


PUBLIC_AUTH_ERROR_MESSAGES = {
    "invalid_email": "Email 格式錯誤",
    "invalid_code": "驗證碼錯誤",
    "expired_code": "驗證碼過期",
    "login_unavailable": "登入暫時失敗，請稍後再試",
    "otp_rate_limit": "驗證碼剛剛已寄出，請稍候再試。",
    "email_provider_error": "目前無法寄送驗證碼，請稍後再試。",
    "network_error": "目前無法連線，請稍後再試。",
    "auth_disabled": "目前無法寄送驗證碼，請稍後再試。",
    "supabase_config_error": "登入服務暫時無法使用，請稍後再試。",
}


def public_auth_error_message(error: AuthFlowError) -> str:
    """Map an internal Auth failure to a fixed, non-sensitive UI message."""
    return PUBLIC_AUTH_ERROR_MESSAGES.get(
        getattr(error, "code", "login_unavailable"),
        PUBLIC_AUTH_ERROR_MESSAGES["login_unavailable"],
    )


def normalize_login_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise AuthFlowError("invalid email", code="invalid_email")
    return email


def _request_error_code(error: Exception) -> str:
    detail = str(error).lower()
    error_type = type(error).__name__.lower()
    if any(token in detail for token in ("rate limit", "over_email_send_rate_limit", "429")):
        return "otp_rate_limit"
    if any(token in detail for token in ("smtp", "email provider", "mail provider")):
        return "email_provider_error"
    if "connect" in error_type or any(token in detail for token in ("network", "connection", "timeout", "dns", "winerror 10013")):
        return "network_error"
    if any(token in detail for token in ("otp_disabled", "signups not allowed", "auth disabled")):
        return "auth_disabled"
    if any(token in detail for token in ("invalid api key", "project not found", "configuration")):
        return "supabase_config_error"
    return "login_unavailable"


def request_email_otp(
    client: Any,
    email: str,
    *,
    allow_registration: bool = True,
) -> str:
    """Request Email OTP; student provisioning still requires verified Auth."""
    normalized = normalize_login_email(email)
    if client is None or not hasattr(client, "auth"):
        raise AuthFlowError("auth unavailable", code="login_unavailable")
    try:
        client.auth.sign_in_with_otp(
            {
                "email": normalized,
                "options": {"should_create_user": bool(allow_registration)},
            }
        )
    except Exception as exc:
        raise AuthFlowError("otp request failed", code=_request_error_code(exc)) from exc
    return normalized


def verify_email_otp(client: Any, email: str, token: str) -> Any:
    normalized = normalize_login_email(email)
    clean_token = str(token or "").strip()
    if not clean_token:
        raise AuthFlowError("missing otp", code="invalid_code")
    if client is None or not hasattr(client, "auth"):
        raise AuthFlowError("auth unavailable", code="login_unavailable")
    try:
        response = client.auth.verify_otp(
            {"email": normalized, "token": clean_token, "type": "email"}
        )
    except Exception as exc:
        detail = str(exc).lower()
        code = "expired_code" if "expired" in detail or "otp_expired" in detail else "invalid_code"
        raise AuthFlowError("otp verification failed", code=code) from exc
    user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if not getattr(user, "id", None) or session is None:
        raise AuthFlowError("auth session unavailable", code="login_unavailable")
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
        "authenticated",
        "private_beta_auth_client",
        "private_beta_auth_email",
        "private_beta_auth_user_id",
        "private_beta_student_id",
        "private_beta_otp_sent",
        "learning_persistence_warning",
    ):
        state.pop(key, None)
