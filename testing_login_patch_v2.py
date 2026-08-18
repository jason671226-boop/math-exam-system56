"""MathAI testing-login v2.

Fixes StreamlitDuplicateElementKey by keeping the app's public Email widget key
separate from the manual-entry widget rendered by the testing bridge.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import testing_login_patch as base


def install_testing_login_patch_v2() -> None:
    import streamlit as st
    import services.auth_service as auth_service
    import services.learning_runtime as learning_runtime

    # Keep the sentinel on the Streamlit module so reruns/module reloads cannot
    # accidentally install nested wrappers around the same widget functions.
    if getattr(st, "_mathai_testing_login_v2_installed", False):
        return

    original_text_input = st.text_input
    original_button = st.button
    original_success = st.success
    original_caption = st.caption
    original_resolve = learning_runtime.resolve_authenticated_student
    original_build_runtime = learning_runtime.build_learning_runtime

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

        # IMPORTANT: do not reuse private_beta_email_input here.  The caller is
        # already the public Email widget with that key, and reusing it creates
        # StreamlitDuplicateElementKey on Streamlit Cloud.
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
                "目前不寄送 Email，請直接把上方驗證碼輸入下方欄位。"
            )
        return original_success(body, *args, **kwargs)

    def request_email_otp_testing(
        client: Any,
        email: str,
        *,
        allow_registration: bool = True,
    ) -> str:
        normalized = base._clean_email(email)
        if not base._EMAIL_RE.fullmatch(normalized):
            raise auth_service.AuthFlowError(
                "invalid email", code="invalid_email"
            )

        auth_user_id, student_id = base._stable_ids(normalized)
        import random

        code = str(random.randint(100000, 999999))
        st.session_state["_mathai_testing_otp"] = code
        st.session_state["_mathai_testing_otp_email"] = normalized
        st.session_state["private_beta_auth_client"] = base._TestingClient(
            st,
            normalized,
            auth_user_id,
            student_id,
        )
        base._save_recent_email(st, normalized)
        return normalized

    def verify_email_otp_testing(client: Any, email: str, token: str):
        normalized = base._clean_email(email)
        expected_email = base._clean_email(
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

        auth_user_id, student_id = base._stable_ids(normalized)
        testing_client = base._TestingClient(
            st,
            normalized,
            auth_user_id,
            student_id,
        )
        st.session_state["private_beta_auth_client"] = testing_client
        st.session_state["_mathai_testing_direct_login"] = True
        st.session_state["private_beta_auth_user_id"] = auth_user_id
        st.session_state["private_beta_student_id"] = student_id
        base._save_recent_email(st, normalized)
        return SimpleNamespace(
            user=SimpleNamespace(id=auth_user_id, email=normalized),
            session=SimpleNamespace(access_token="testing-period-session"),
        )

    def resolve_authenticated_student_testing(
        client: Any,
        *,
        preferred_student_id: str | None = None,
    ):
        if isinstance(client, base._TestingClient):
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
            or isinstance(authenticated_client, base._TestingClient)
        ):
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

    st._mathai_testing_login_v2_installed = True
