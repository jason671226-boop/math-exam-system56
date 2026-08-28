"""Testing-mode direct-code login for allowlisted internal test accounts.

Final architecture (v2): Supabase Native Email OTP + Postgres Send Email Hook.

* The browser asks Supabase for a REAL Email OTP via ``sign_in_with_otp``.
* A Postgres Send Email Hook intercepts Email delivery for the allowlisted
  test accounts only, stores the OTP in a test-only challenge table, and
  returns a valid empty response so no SMTP Email is sent.
* A narrow SECURITY DEFINER RPC reveals that single OTP only when the caller
  presents the matching high-entropy challenge hash (nonce) for an
  allowlisted, unexpired, unused, non-locked challenge.
* Verification always uses the official ``supabase.auth.verify_otp`` endpoint
  and ``resolve_authenticated_student`` for ``auth.uid() -> student_access``.

No service_role, no temporary password, no password rotation, no synthetic
JWT, and no deterministic UUID are used anywhere in this flow.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets as _secrets
import time
from datetime import datetime, timezone
from typing import Any, MutableMapping

from .auth_service import AuthFlowError, request_email_otp, verify_email_otp

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

ALLOWLISTED_TESTING_EMAILS = frozenset(
    {
        "jason601226@gmail.com",
        "jason621226@gmail.com",
        "jason671226@gmail.com",
    }
)

TESTING_OTP_TTL_SECONDS = 600
CHALLENGE_NONCE_BYTES = 32
MAX_REVEAL_ATTEMPTS = 5
REVEAL_POLL_ATTEMPTS = 8
REVEAL_POLL_INTERVAL_SECONDS = 0.5

TESTING_EMAIL_KEY = "testing_auth_email_v1"
TESTING_NONCE_KEY = "testing_auth_nonce_v1"
TESTING_OTP_DISPLAY_KEY = "testing_auth_otp_display_v1"
TESTING_EXPIRES_AT_KEY = "testing_auth_expires_at_v1"

PREPARE_RPC = "mathai_testing_auth_prepare"
REVEAL_RPC = "mathai_testing_auth_reveal"
FAIL_RPC = "mathai_testing_auth_fail"
CONSUME_RPC = "mathai_testing_auth_consume"


class TestingAuthError(ValueError):
    """Safe testing-auth failure without credential or token details."""

    def __init__(self, message: str, *, code: str = "testing_auth_unavailable") -> None:
        super().__init__(message)
        self.code = code


PUBLIC_TESTING_AUTH_ERROR_MESSAGES = {
    "invalid_email": "Email 格式錯誤",
    "not_allowlisted": "此 Email 不開放測試期間直接顯示驗證碼，請改用 Email 寄送驗證碼登入。",
    "invalid_challenge": "驗證碼挑戰無效，請重新顯示驗證碼。",
    "expired_code": "驗證碼過期，請重新顯示驗證碼。",
    "too_many_attempts": "驗證碼錯誤次數過多，請重新顯示驗證碼。",
    "testing_auth_unavailable": "測試期間登入服務尚未啟用，請改用 Email 寄送驗證碼登入。",
}


def public_testing_auth_error_message(error: TestingAuthError) -> str:
    """Map an internal testing-auth failure to a fixed, non-sensitive message."""
    return PUBLIC_TESTING_AUTH_ERROR_MESSAGES.get(
        getattr(error, "code", "testing_auth_unavailable"),
        PUBLIC_TESTING_AUTH_ERROR_MESSAGES["testing_auth_unavailable"],
    )


def normalize_testing_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise TestingAuthError("invalid email", code="invalid_email")
    return email


def is_allowlisted_testing_email(email: Any) -> bool:
    try:
        return normalize_testing_email(email) in ALLOWLISTED_TESTING_EMAILS
    except TestingAuthError:
        return False


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_challenge_nonce() -> str:
    """Return a high-entropy 256-bit challenge nonce; never log it."""
    return _secrets.token_hex(CHALLENGE_NONCE_BYTES)


def _timestamp(now: float | None) -> float:
    return now if now is not None else time.time()


def testing_challenge_email(state: MutableMapping[str, Any]) -> str:
    return str(state.get(TESTING_EMAIL_KEY, "")).strip().lower()


def testing_code_display(state: MutableMapping[str, Any]) -> str:
    return str(state.get(TESTING_OTP_DISPLAY_KEY, "")).strip()


# These helpers are imported into the unittest module.  Prevent pytest from
# mistaking the ``testing_*`` names for test functions while preserving their
# public API and runtime behavior.
testing_challenge_email.__test__ = False
testing_code_display.__test__ = False


def clear_testing_challenge(state: MutableMapping[str, Any]) -> None:
    for key in (
        TESTING_EMAIL_KEY,
        TESTING_NONCE_KEY,
        TESTING_OTP_DISPLAY_KEY,
        TESTING_EXPIRES_AT_KEY,
    ):
        state.pop(key, None)


def _rpc(client: Any, name: str, payload: dict[str, Any]) -> Any:
    if client is None or not hasattr(client, "rpc"):
        raise TestingAuthError(
            "testing bridge unavailable",
            code="testing_auth_unavailable",
        )
    try:
        return client.rpc(name, payload).execute()
    except Exception as exc:
        raise TestingAuthError(
            "testing bridge unavailable",
            code="testing_auth_unavailable",
        ) from exc


def _single_row(response: Any) -> dict[str, Any] | None:
    rows = getattr(response, "data", None) or []
    if isinstance(rows, list):
        return rows[0] if rows else None
    return rows if isinstance(rows, dict) else None


def prepare_testing_challenge(
    client: Any,
    state: MutableMapping[str, Any],
    *,
    email: str,
    now: float | None = None,
) -> None:
    """Create the server-side pre-claim row for one allowlisted Email."""
    normalized = normalize_testing_email(email)
    if not is_allowlisted_testing_email(normalized):
        raise TestingAuthError("not allowlisted", code="not_allowlisted")
    nonce = generate_challenge_nonce()
    issued_at = _timestamp(now)
    expires_at = issued_at + TESTING_OTP_TTL_SECONDS
    # PostgREST expects an ISO-8601 timestamptz string, not a Unix epoch float.
    expires_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
    _rpc(
        client,
        PREPARE_RPC,
        {
            "p_email": normalized,
            "p_challenge_hash": _sha256(nonce),
            "p_expires_at": expires_iso,
        },
    )
    state[TESTING_EMAIL_KEY] = normalized
    state[TESTING_NONCE_KEY] = nonce
    state[TESTING_EXPIRES_AT_KEY] = expires_at
    state.pop(TESTING_OTP_DISPLAY_KEY, None)


def request_testing_otp(client: Any, *, email: str) -> str:
    """Request the official Supabase Email OTP (hook intercepts delivery)."""
    normalized = normalize_testing_email(email)
    if not is_allowlisted_testing_email(normalized):
        raise TestingAuthError("not allowlisted", code="not_allowlisted")
    # Official GoTrue endpoint; the Send Email Hook suppresses SMTP delivery.
    return request_email_otp(client, normalized, allow_registration=False)


def reveal_testing_otp(
    client: Any,
    state: MutableMapping[str, Any],
    *,
    email: str,
    now: float | None = None,
) -> str:
    """Reveal the single OTP for the matching challenge; never list rows."""
    normalized = normalize_testing_email(email)
    if not is_allowlisted_testing_email(normalized):
        raise TestingAuthError("not allowlisted", code="not_allowlisted")
    nonce = str(state.get(TESTING_NONCE_KEY, ""))
    if not nonce:
        raise TestingAuthError("challenge missing", code="invalid_challenge")
    if _timestamp(now) > float(state.get(TESTING_EXPIRES_AT_KEY, 0)):
        clear_testing_challenge(state)
        raise TestingAuthError("expired code", code="expired_code")
    response = _rpc(
        client,
        REVEAL_RPC,
        {"p_email": normalized, "p_challenge_hash": _sha256(nonce)},
    )
    row = _single_row(response)
    otp = row.get("otp") if isinstance(row, dict) else None
    if not isinstance(otp, str) or not otp.isdigit() or len(otp) != 6:
        raise TestingAuthError(
            "testing code unavailable",
            code="testing_auth_unavailable",
        )
    state[TESTING_OTP_DISPLAY_KEY] = otp
    return otp


def issue_testing_code(
    client: Any,
    state: MutableMapping[str, Any],
    *,
    email: str,
    now: float | None = None,
) -> str:
    """Prepare + request official OTP + reveal it for one allowlisted account."""
    normalized = normalize_testing_email(email)
    if not is_allowlisted_testing_email(normalized):
        raise TestingAuthError("not allowlisted", code="not_allowlisted")
    prepare_testing_challenge(client, state, email=normalized, now=now)
    request_testing_otp(client, email=normalized)
    last_error: TestingAuthError | None = None
    for _ in range(REVEAL_POLL_ATTEMPTS):
        try:
            return reveal_testing_otp(client, state, email=normalized, now=now)
        except TestingAuthError as exc:
            last_error = exc
            if exc.code != "testing_auth_unavailable":
                raise
            time.sleep(REVEAL_POLL_INTERVAL_SECONDS)
    if last_error is not None:
        raise last_error
    raise TestingAuthError(
        "testing code unavailable",
        code="testing_auth_unavailable",
    )


def _mark_challenge(client: Any, state: MutableMapping[str, Any], name: str) -> None:
    email = testing_challenge_email(state)
    nonce = str(state.get(TESTING_NONCE_KEY, ""))
    if not email or not nonce:
        return
    try:
        _rpc(client, name, {"p_email": email, "p_challenge_hash": _sha256(nonce)})
    except TestingAuthError:
        pass


def complete_testing_login(
    client: Any,
    state: MutableMapping[str, Any],
    *,
    email: str,
    token: str,
    now: float | None = None,
) -> tuple[Any, str]:
    """Verify the official OTP and return the REAL Supabase Auth response."""
    normalized = normalize_testing_email(email)
    clean_token = str(token or "").strip()
    if not clean_token.isdigit() or len(clean_token) != 6:
        raise TestingAuthError("invalid code", code="invalid_challenge")
    if _timestamp(now) > float(state.get(TESTING_EXPIRES_AT_KEY, 0)):
        clear_testing_challenge(state)
        raise TestingAuthError("expired code", code="expired_code")
    try:
        response = verify_email_otp(client, normalized, clean_token)
    except AuthFlowError as exc:
        if exc.code in {"invalid_code", "expired_code"}:
            _mark_challenge(client, state, FAIL_RPC)
        raise
    _mark_challenge(client, state, CONSUME_RPC)
    clear_testing_challenge(state)
    return response, normalized
