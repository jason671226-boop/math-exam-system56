"""Temporary testing-period login bridge for MathAI v0.8.8.

This module is intentionally isolated so the testing login can be removed cleanly
when production Email OTP is re-enabled.  It never sends a login email.
"""

from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any


DEVICE_EMAIL_COOKIE = "mathai_recent_emails_v1"
MANUAL_EMAIL_OPTION = "➕ 手動輸入新 Email..."
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_INSTALLED = False
_COOKIE_CONTROLLER = None


def _clean_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _clean_recent(value: Any) -> list[str]:
    try:
        if isinstance(value, str):
            value = json.loads(value)
    except Exception:
        value = []
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        email = _clean_email(item)
        if (
            email
            and _EMAIL_RE.fullmatch(email)
            and email != "trial@example.com"
            and email not in result
        ):
            result.append(email)
    return result[:10]


def _get_cookie_controller():
    global _COOKIE_CONTROLLER
    if _COOKIE_CONTROLLER is not None:
        return _COOKIE_CONTROLLER
    try:
        from streamlit_cookies_controller import CookieController

        _COOKIE_CONTROLLER = CookieController(
            key="mathai_testing_login_cookie_controller"
        )
    except Exception:
        _COOKIE_CONTROLLER = False
    return _COOKIE_CONTROLLER or None


def _recent_emails(st) -> list[str]:
    combined = list(
        _clean_recent(st.session_state.get("_mathai_testing_recent_emails", []))
    )
    controller = _get_cookie_controller()
    if controller is not None:
        try:
            combined.extend(_clean_recent(controller.get(DEVICE_EMAIL_COOKIE)))
        except Exception:
            pass

    remembered = _clean_email(st.session_state.get("private_beta_auth_email", ""))
    if remembered and _EMAIL_RE.fullmatch(remembered):
        combined.insert(0, remembered)
    return _clean_recent(combined)


def _save_recent_email(st, email: str) -> None:
    email = _clean_email(email)
    if not _EMAIL_RE.fullmatch(email):
        return

    recent = _recent_emails(st)
    if email in recent:
        recent.remove(email)
    recent.insert(0, email)
    recent = recent[:10]
    st.session_state["_mathai_testing_recent_emails"] = recent

    controller = _get_cookie_controller()
    if controller is not None:
        try:
            controller.set(
                DEVICE_EMAIL_COOKIE,
                json.dumps(recent, ensure_ascii=False),
                expires=datetime.now() + timedelta(days=365),
                same_site="lax",
            )
        except Exception:
            pass


def _profile_row_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "found": True,
        "identity_locked": bool(payload.get("p_identity_locked", False)),
        "locked_last_name": str(payload.get("p_locked_last_name") or ""),
        "locked_first_name": str(payload.get("p_locked_first_name") or ""),
        "city": str(payload.get("p_city") or ""),
        "district": str(payload.get("p_district") or ""),
        "school": str(payload.get("p_school") or ""),
        "grade": str(payload.get("p_grade") or ""),
        "version": str(payload.get("p_version") or ""),
        "traits": payload.get("p_traits") or [],
        "interests": payload.get("p_interests") or [],
        "discovery_source": str(payload.get("p_discovery_source") or ""),
        "source_detail": str(payload.get("p_source_detail") or ""),
        "source_reward_status": str(
            payload.get("p_source_reward_status") or "none"
        ),
        "referral_eligible_override": bool(
            payload.get("p_referral_eligible_override", False)
        ),
        "change_year": payload.get("p_change_year"),
        "change_count": payload.get("p_change_count", 0),
    }


class _TestingExecutable:
    def __init__(self, data: Any):
        self._data = data

    def execute(self):
        data = self._data() if callable(self._data) else self._data
        return SimpleNamespace(data=data)


class _TestingAuth:
    def __init__(self, st, user_id: str, email: str):
        self._st = st
        self._user_id = user_id
        self._email = email

    def get_user(self):
        return SimpleNamespace(
            user=SimpleNamespace(id=self._user_id, email=self._email)
        )

    def sign_out(self):
        for key in (
            "_mathai_testing_direct_login",
            "_mathai_testing_otp",
            "_mathai_testing_otp_email",
            "private_beta_auth_user_id",
            "private_beta_student_id",
        ):
            self._st.session_state.pop(key, None)


class _TestingClient:
    """Small session-only stand-in for Auth-owned profile/wallet RPCs."""

    def __init__(self, st, email: str, auth_user_id: str, student_id: str):
        self._st = st
        self.email = email
        self.auth_user_id = auth_user_id
        self.student_id = student_id
        self.auth = _TestingAuth(st, auth_user_id, email)

    def rpc(self, name: str, params: dict[str, Any] | None = None):
        payload = dict(params or {})
        state = self._st.session_state

        if name == "mathai_private_profile_get":
            def profile_get():
                row = state.get("_mathai_testing_profile_row")
                return [dict(row)] if isinstance(row, dict) else []

            return _TestingExecutable(profile_get)

        if name == "mathai_private_profile_save":
            def profile_save():
                state["_mathai_testing_profile_row"] = _profile_row_from_payload(
                    payload
                )
                return True

            return _TestingExecutable(profile_save)

        if name == "mathai_private_wallet_lookup":
            def wallet_lookup():
                credits = int(
                    state.get("user_profile", {}).get("credits", 200) or 0
                )
                return [{"found": True, "credits": credits}]

            return _TestingExecutable(wallet_lookup)

        if name == "mathai_private_wallet_bootstrap":
            def wallet_bootstrap():
                profile = state.setdefault("user_profile", {})
                if profile.get("credits") is None:
                    profile["credits"] = 200
                return [{"credits": int(profile.get("credits", 200) or 0)}]

            return _TestingExecutable(wallet_bootstrap)

        if name == "mathai_private_wallet_debit":
            # During the public testing period we validate the whole exam flow
            # without consuming the persistent production wallet.
            def wallet_debit():
                credits = int(
                    state.get("user_profile", {}).get("credits", 200) or 0
                )
                amount = int(payload.get("p_amount") or 0)
                return [{
                    "success": credits >= amount,
                    "new_balance": credits,
                }]

            return _TestingExecutable(wallet_debit)

        if name == "mathai_private_ensure_student":
            return _TestingExecutable([
                {"student_id": self.student_id, "created": False}
            ])

        # Non-critical test-period RPCs fail closed/no-op rather than touching
        # production ownership data with a fabricated Auth session.
        return _TestingExecutable([])


def _stable_ids(email: str) -> tuple[str, str]:
    auth_user_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"mathai-testing-auth:{email}")
    )
    student_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"mathai-testing-student:{email}")
    )
    return auth_user_id, student_id


def install_testing_login_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import streamlit as st
    import services.auth_service as auth_service
    import services.learning_runtime as learning_runtime

    original_text_input = st.text_input
    original_button = st.button
    original_success = st.success
    original_caption = st.caption
    original_resolve = learning_runtime.resolve_authenticated_student
    original_build_runtime = learning_runtime.build_learning_runtime

    def testing_text_input(label, *args, **kwargs):
        if kwargs.get("key") != "private_beta_email_input":
            return original_text_input(label, *args, **kwargs)

        recent = _recent_emails(st)
        options = [*recent, MANUAL_EMAIL_OPTION]
        choice_key = "_mathai_testing_email_choice"
        if st.session_state.get(choice_key) not in options:
            st.session_state.pop(choice_key, None)

        selected = st.selectbox(
            "這台裝置曾使用的 Email",
            options,
            index=0 if recent else len(options) - 1,
            key=choice_key,
            help="最後一項可手動輸入新的 Email。",
        )
        if recent:
            original_caption(
                "✅ 已載入這台裝置曾使用的 Email；最後一項可手動輸入新 Email。"
            )

        if selected != MANUAL_EMAIL_OPTION:
            return str(selected)

        manual_kwargs = dict(kwargs)
        manual_kwargs["key"] = "private_beta_email_input"
        manual_kwargs["value"] = ""
        manual_kwargs.setdefault("autocomplete", "email")
        manual_kwargs.setdefault("placeholder", "example@gmail.com")
        return original_text_input("手動輸入新 Email", *args, **manual_kwargs)

    def testing_button(label, *args, **kwargs):
        if kwargs.get("key") == "private_beta_send_otp":
            label = "顯示驗證碼（測試期間）"
        return original_button(label, *args, **kwargs)

    def testing_caption(body, *args, **kwargs):
        if str(body) == "輸入 Email，我們會寄送一次性驗證碼給你。":
            body = (
                "測試期間先不寄 Email；按下方按鈕後，登入驗證碼會直接顯示在畫面上。"
            )
        return original_caption(body, *args, **kwargs)

    def testing_success(body, *args, **kwargs):
        if (
            str(body) == "驗證碼已寄出，請查看 Email。"
            and st.session_state.get("_mathai_testing_otp")
        ):
            code = st.session_state["_mathai_testing_otp"]
            return original_success(
                f"🔧 **[測試模式] 登入驗證碼：{code}**  \n"
                "目前不寄送 Email，請直接把上方驗證碼輸入下方欄位。"
            )
        return original_success(body, *args, **kwargs)

    def request_email_otp_testing(
        client: Any,
        email: str,
        *,
        allow_registration: bool = True,
    ) -> str:
        normalized = _clean_email(email)
        if not _EMAIL_RE.fullmatch(normalized):
            raise auth_service.AuthFlowError(
                "invalid email", code="invalid_email"
            )

        auth_user_id, student_id = _stable_ids(normalized)
        code = str(random.randint(100000, 999999))
        st.session_state["_mathai_testing_otp"] = code
        st.session_state["_mathai_testing_otp_email"] = normalized
        st.session_state["private_beta_auth_client"] = _TestingClient(
            st,
            normalized,
            auth_user_id,
            student_id,
        )
        _save_recent_email(st, normalized)
        return normalized

    def verify_email_otp_testing(client: Any, email: str, token: str):
        normalized = _clean_email(email)
        expected_email = _clean_email(
            st.session_state.get("_mathai_testing_otp_email", "")
        )
        expected_code = str(
            st.session_state.get("_mathai_testing_otp", "")
        ).strip()
        clean_token = str(token or "").strip()

        if not clean_token or clean_token != expected_code:
            raise auth_service.AuthFlowError(
                "invalid otp", code="invalid_code"
            )
        if normalized != expected_email:
            raise auth_service.AuthFlowError(
                "invalid otp email", code="invalid_code"
            )

        auth_user_id, student_id = _stable_ids(normalized)
        testing_client = _TestingClient(
            st,
            normalized,
            auth_user_id,
            student_id,
        )
        st.session_state["private_beta_auth_client"] = testing_client
        st.session_state["_mathai_testing_direct_login"] = True
        st.session_state["private_beta_auth_user_id"] = auth_user_id
        st.session_state["private_beta_student_id"] = student_id
        _save_recent_email(st, normalized)
        return SimpleNamespace(
            user=SimpleNamespace(id=auth_user_id, email=normalized),
            session=SimpleNamespace(access_token="testing-period-session"),
        )

    def resolve_authenticated_student_testing(
        client: Any,
        *,
        preferred_student_id: str | None = None,
    ):
        if isinstance(client, _TestingClient):
            return learning_runtime.AuthenticatedStudent(
                client.auth_user_id,
                client.student_id,
                "owner",
            )
        return original_resolve(
            client,
            preferred_student_id=preferred_student_id,
        )

    def build_learning_runtime_testing(
        state,
        authenticated_client,
        *,
        preferred_student_id: str | None = None,
    ):
        if (
            state.get("_mathai_testing_direct_login", False)
            or isinstance(authenticated_client, _TestingClient)
        ):
            # Keep diagnostic/mastery writes session-only while Auth is bypassed.
            return original_build_runtime(
                state,
                None,
                preferred_student_id=preferred_student_id,
            )
        return original_build_runtime(
            state,
            authenticated_client,
            preferred_student_id=preferred_student_id,
        )

    st.text_input = testing_text_input
    st.button = testing_button
    st.caption = testing_caption
    st.success = testing_success
    auth_service.request_email_otp = request_email_otp_testing
    auth_service.verify_email_otp = verify_email_otp_testing
    learning_runtime.resolve_authenticated_student = (
        resolve_authenticated_student_testing
    )
    learning_runtime.build_learning_runtime = build_learning_runtime_testing

    _INSTALLED = True
