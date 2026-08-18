"""Force the testing-period Auth functions onto services.auth_service.

Streamlit Cloud hot reloads can preserve wrapped UI functions while reloading
services.auth_service, leaving the button labelled as testing mode but the Auth
call pointing back to the real /otp Email endpoint.  This module deliberately
rebinds only the Auth functions on every app rerun so testing mode never sends
Email and the on-screen code is always the source of verification.
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


def _bool_result(data: Any) -> bool:
    if isinstance(data, bool):
        return data
    if isinstance(data, list) and data:
        if isinstance(data[0], bool):
            return bool(data[0])
        if isinstance(data[0], dict):
            return bool(next(iter(data[0].values()), False))
    if isinstance(data, dict):
        return bool(next(iter(data.values()), False))
    return False


def install_testing_auth_rebind_v3() -> None:
    import streamlit as st
    import services.auth_service as auth_service

    def request_email_otp_testing(
        client: Any,
        email: str,
        *,
        allow_registration: bool = True,
    ) -> str:
        del allow_registration
        normalized = base._clean_email(email)
        if not base._EMAIL_RE.fullmatch(normalized):
            raise auth_service.AuthFlowError("invalid email", code="invalid_email")
        if client is None:
            raise auth_service.AuthFlowError(
                "testing login unavailable", code="login_unavailable"
            )

        # Reuse an already displayed challenge for the same Email on the current
        # Streamlit session instead of generating another one on accidental reruns.
        if (
            base._clean_email(st.session_state.get("_mathai_testing_otp_email", ""))
            == normalized
            and str(st.session_state.get("_mathai_testing_otp", "")).strip()
        ):
            st.session_state["private_beta_auth_email"] = normalized
            return normalized

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
                "testing login unavailable", code="login_unavailable"
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

        if not clean_token or normalized != expected_email:
            raise auth_service.AuthFlowError(
                "invalid testing code", code="invalid_code"
            )
        if client is None:
            raise auth_service.AuthFlowError(
                "testing login unavailable", code="login_unavailable"
            )

        temp_password = ""
        auth_response = None
        cleanup_ok = False
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
        except auth_service.AuthFlowError:
            raise
        except Exception as exc:
            raise auth_service.AuthFlowError(
                "invalid or expired testing code", code="invalid_code"
            ) from exc
        finally:
            if temp_password:
                try:
                    revoke_response = client.rpc(
                        "mathai_testing_revoke_temp_password",
                        {"p_email": normalized, "p_temp_password": temp_password},
                    ).execute()
                    cleanup_ok = _bool_result(
                        getattr(revoke_response, "data", None)
                    )
                except Exception:
                    cleanup_ok = False

        if auth_response is None:
            raise auth_service.AuthFlowError(
                "testing login unavailable", code="login_unavailable"
            )
        if not cleanup_ok:
            try:
                consume_response = client.rpc(
                    "mathai_testing_consume_login_password", {}
                ).execute()
                cleanup_ok = _bool_result(
                    getattr(consume_response, "data", None)
                )
            except Exception:
                cleanup_ok = False
        if not cleanup_ok:
            try:
                client.auth.sign_out()
            except Exception:
                pass
            raise auth_service.AuthFlowError(
                "testing login cleanup failed", code="login_unavailable"
            )

        base._save_recent_email(st, normalized)
        for key in (
            "_mathai_testing_otp",
            "_mathai_testing_otp_email",
            "_mathai_testing_otp_expires_at",
        ):
            st.session_state.pop(key, None)
        return auth_response

    # IMPORTANT: intentionally no sentinel. Rebind every rerun so a hot-reloaded
    # auth_service module can never fall back to sign_in_with_otp()/Email delivery.
    auth_service.request_email_otp = request_email_otp_testing
    auth_service.verify_email_otp = verify_email_otp_testing
