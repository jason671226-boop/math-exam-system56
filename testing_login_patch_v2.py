"""MathAI testing-login v2.

Testing-period login UX:
- show a short verification code directly on screen (no Email delivery),
- remember device-local Email history,
- exchange the short code for a one-time temporary password through tightly scoped
  Supabase RPCs,
- establish a REAL Supabase Auth session before loading profile/mastery data.

The database-side testing RPCs are temporary, allowlisted, expiring, and preserve
RLS ownership.  No service_role key is used by the Streamlit app.
"""

from __future__ import annotations

from typing import Any

import testing_login_patch as base


def _first_row(data: Any) -> dict[str, Any]:
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return dict(data[0])
    if isinstance(data, dict):
        return dict(data)
    return {}


def install_testing_login_patch_v2() -> None:
    import streamlit as st
    import services.auth_service as auth_service

    # Keep the sentinel on the Streamlit module so reruns/module reloads cannot
    # accidentally install nested wrappers around the same widget functions.
    if getattr(st, "_mathai_testing_login_v2_installed", False):
        return

    original_text_input = st.text_input
    original_button = st.button
    original_success = st.success
    original_caption = st.caption

    def testing_text_input(label, *args, **kwargs):
        if kwargs.get("key") != "private_beta_email_input":
            return original_text_input(label, *args, **kwargs)

        recent = base._recent_emails(st)
        options = [*recent, base.MANUAL_EMAIL_OPTION]
        choice_key = "_mathai_testing_email_choice_v2"
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

        if selected != base.MANUAL_EMAIL_OPTION:
            return str(selected)

        # Do not reuse private_beta_email_input here. The caller is already the
        # public Email widget with that key; reusing it causes DuplicateElementKey.
        manual_kwargs = dict(kwargs)
        manual_kwargs["key"] = "_mathai_testing_manual_email_input_v2"
        manual_kwargs["value"] = st.session_state.get(
            "_mathai_testing_manual_email_value_v2", ""
        )
        manual_kwargs.setdefault("autocomplete", "email")
        manual_kwargs.setdefault("placeholder", "example@gmail.com")
        value = original_text_input("手動輸入新 Email", *args, **manual_kwargs)
        st.session_state["_mathai_testing_manual_email_value_v2"] = value
        return value

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
                "目前不寄送 Email；請直接把上方驗證碼輸入下方欄位。"
            )
        return original_success(body, *args, **kwargs)

    def request_email_otp_testing(
        client: Any,
        email: str,
        *,
        allow_registration: bool = True,
    ) -> str:
        del allow_registration  # testing allowlist is controlled in Supabase.
        normalized = base._clean_email(email)
        if not base._EMAIL_RE.fullmatch(normalized):
            raise auth_service.AuthFlowError(
                "invalid email", code="invalid_email"
            )
        if client is None:
            raise auth_service.AuthFlowError(
                "testing login unavailable", code="auth_unavailable"
            )

        try:
            response = client.rpc(
                "mathai_testing_issue_login_code",
                {"p_email": normalized},
            ).execute()
            row = _first_row(getattr(response, "data", None))
            code = str(row.get("code") or "").strip()
            if not code:
                raise ValueError("missing testing code")
        except Exception as exc:
            raise auth_service.AuthFlowError(
                "testing login unavailable", code="auth_unavailable"
            ) from exc

        st.session_state["_mathai_testing_otp"] = code
        st.session_state["_mathai_testing_otp_email"] = normalized
        st.session_state["_mathai_testing_otp_expires_at"] = str(
            row.get("expires_at") or ""
        )
        st.session_state["private_beta_auth_email"] = normalized
        return normalized

    def verify_email_otp_testing(client: Any, email: str, token: str):
        normalized = base._clean_email(email)
        expected_email = base._clean_email(
            st.session_state.get("_mathai_testing_otp_email", "")
        )
        clean_token = str(token or "").strip()

        if not clean_token:
            raise auth_service.AuthFlowError(
                "invalid otp", code="invalid_code"
            )
        if normalized != expected_email:
            raise auth_service.AuthFlowError(
                "invalid otp email", code="invalid_code"
            )
        if client is None:
            raise auth_service.AuthFlowError(
                "testing login unavailable", code="auth_unavailable"
            )

        try:
            verify_response = client.rpc(
                "mathai_testing_verify_login_code",
                {"p_email": normalized, "p_code": clean_token},
            ).execute()
            row = _first_row(getattr(verify_response, "data", None))
            temp_password = str(row.get("temp_password") or "").strip()
            if not temp_password:
                raise ValueError("missing temporary password")

            auth_response = client.auth.sign_in_with_password(
                {"email": normalized, "password": temp_password}
            )
            user = getattr(auth_response, "user", None)
            session = getattr(auth_response, "session", None)
            if user is None or session is None:
                raise ValueError("Supabase session was not established")

            # Immediately rotate the temporary password away after the real
            # authenticated session exists. The current JWT/session remains valid.
            try:
                client.rpc("mathai_testing_consume_login_password", {}).execute()
            except Exception:
                # The session is already valid. Do not discard a successful login
                # because cleanup failed; the DB allowlist still expires.
                pass
        except auth_service.AuthFlowError:
            raise
        except Exception as exc:
            raise auth_service.AuthFlowError(
                "invalid or expired testing code", code="invalid_code"
            ) from exc

        base._save_recent_email(st, normalized)
        for key in (
            "_mathai_testing_otp",
            "_mathai_testing_otp_email",
            "_mathai_testing_otp_expires_at",
        ):
            st.session_state.pop(key, None)
        return auth_response

    st.text_input = testing_text_input
    st.button = testing_button
    st.caption = testing_caption
    st.success = testing_success
    auth_service.request_email_otp = request_email_otp_testing
    auth_service.verify_email_otp = verify_email_otp_testing

    st._mathai_testing_login_v2_installed = True
