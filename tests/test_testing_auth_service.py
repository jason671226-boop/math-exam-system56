from types import SimpleNamespace
import unittest

from services.auth_service import AuthFlowError
from services.testing_auth_service import (
    ALLOWLISTED_TESTING_EMAILS,
    TESTING_OTP_TTL_SECONDS,
    TestingAuthError,
    clear_testing_challenge,
    complete_testing_login,
    is_allowlisted_testing_email,
    issue_testing_code,
    prepare_testing_challenge,
    public_testing_auth_error_message,
    request_testing_otp,
    reveal_testing_otp,
    testing_challenge_email,
    testing_code_display,
)


ALLOWED = "jason671226@gmail.com"
OTHER = "someone-else@gmail.com"


class FakeAuth:
    def __init__(self, user_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"):
        self.user_id = user_id
        self.calls = []

    def sign_in_with_otp(self, payload):
        self.calls.append(("sign_in_with_otp", payload))
        return SimpleNamespace(user=SimpleNamespace(id=self.user_id))

    def verify_otp(self, payload):
        self.calls.append(("verify_otp", payload))
        return SimpleNamespace(user=SimpleNamespace(id=self.user_id), session=object())

    def get_user(self):
        return SimpleNamespace(user=SimpleNamespace(id=self.user_id))

    def sign_in_with_password(self, payload):
        self.calls.append(("sign_in_with_password", payload))
        raise AssertionError("temporary password flow must not be used")


class FakeRpc:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self):
        return SimpleNamespace(data=[dict(row) for row in self.rows])


class FakeClient:
    def __init__(self, *, reveal_otp="123456"):
        self.auth = FakeAuth()
        self.reveal_otp = reveal_otp
        self.rpc_calls = []
        self.prepare_hash = ""

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        if name == "mathai_testing_auth_prepare":
            self.prepare_hash = payload["p_challenge_hash"]
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=[{"ok": True}]))
        if name == "mathai_testing_auth_reveal":
            if payload["p_challenge_hash"] != self.prepare_hash:
                raise RuntimeError("testing challenge rejected")
            return SimpleNamespace(
                execute=lambda: SimpleNamespace(data=[{"otp": self.reveal_otp}])
            )
        if name in {"mathai_testing_auth_fail", "mathai_testing_auth_consume"}:
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=[{"ok": True}]))
        raise AssertionError(f"unexpected rpc {name}")


class TestingAuthServiceTests(unittest.TestCase):
    def test_allowlist_contains_exactly_three_internal_test_accounts(self):
        self.assertEqual(
            ALLOWLISTED_TESTING_EMAILS,
            {
                "jason601226@gmail.com",
                "jason621226@gmail.com",
                "jason671226@gmail.com",
            },
        )
        self.assertTrue(is_allowlisted_testing_email(" JASON671226@GMAIL.COM "))
        self.assertFalse(is_allowlisted_testing_email(OTHER))

    def test_issue_code_for_non_allowlisted_email_is_rejected(self):
        state = {}
        with self.assertRaises(TestingAuthError) as raised:
            issue_testing_code(FakeClient(), state, email=OTHER, now=1_000_000.0)
        self.assertEqual(raised.exception.code, "not_allowlisted")
        self.assertEqual(testing_code_display(state), "")

    def test_issue_code_requests_official_otp_for_allowlisted_email(self):
        state = {}
        client = FakeClient()
        code = issue_testing_code(client, state, email=ALLOWED, now=1_000_000.0)
        self.assertRegex(code, r"^\d{6}$")
        self.assertEqual(testing_code_display(state), code)
        self.assertEqual(testing_challenge_email(state), ALLOWED)
        self.assertTrue(
            [call for call in client.auth.calls if call[0] == "sign_in_with_otp"]
        )
        otp_payload = next(
            call for call in client.auth.calls if call[0] == "sign_in_with_otp"
        )[1]
        self.assertEqual(otp_payload["email"], ALLOWED)
        self.assertFalse(otp_payload["options"]["should_create_user"])

    def test_prepare_sends_challenge_hash_and_expiry(self):
        state = {}
        client = FakeClient()
        prepare_testing_challenge(client, state, email=ALLOWED, now=1_000_000.0)
        prepare_call = next(
            call for call in client.rpc_calls if call[0] == "mathai_testing_auth_prepare"
        )
        payload = prepare_call[1]
        self.assertEqual(payload["p_email"], ALLOWED)
        self.assertRegex(payload["p_challenge_hash"], r"^[0-9a-f]{64}$")
        # PostgREST timestamptz must be ISO-8601, not a Unix epoch float.
        from datetime import datetime, timezone

        expected_iso = datetime.fromtimestamp(
            1_000_000.0 + TESTING_OTP_TTL_SECONDS, tz=timezone.utc
        ).isoformat()
        self.assertEqual(payload["p_expires_at"], expected_iso)

    def test_reveal_requires_matching_nonce_and_expiry(self):
        state = {}
        client = FakeClient()
        prepare_testing_challenge(client, state, email=ALLOWED, now=1_000_000.0)
        # Wrong nonce is never available to reveal; simulate by tampering state.
        import secrets as _secrets

        state["testing_auth_nonce_v1"] = _secrets.token_hex(32)
        with self.assertRaises(TestingAuthError) as raised:
            reveal_testing_otp(client, state, email=ALLOWED, now=1_000_001.0)
        self.assertIn(
            raised.exception.code,
            {"invalid_challenge", "testing_auth_unavailable"},
        )

    def test_reveal_rejects_expired_challenge(self):
        state = {}
        client = FakeClient()
        prepare_testing_challenge(client, state, email=ALLOWED, now=1_000_000.0)
        with self.assertRaises(TestingAuthError) as raised:
            reveal_testing_otp(
                client,
                state,
                email=ALLOWED,
                now=1_000_000.0 + TESTING_OTP_TTL_SECONDS + 1,
            )
        self.assertEqual(raised.exception.code, "expired_code")

    def test_reveal_validates_otp_is_six_digits(self):
        state = {}
        client = FakeClient(reveal_otp="12345")
        prepare_testing_challenge(client, state, email=ALLOWED, now=1_000_000.0)
        with self.assertRaises(TestingAuthError) as raised:
            reveal_testing_otp(client, state, email=ALLOWED, now=1_000_001.0)
        self.assertEqual(raised.exception.code, "testing_auth_unavailable")

    def test_complete_login_uses_standard_verify_otp_and_never_password(self):
        state = {}
        client = FakeClient()
        code = issue_testing_code(client, state, email=ALLOWED, now=1_000_000.0)
        response, email = complete_testing_login(
            client,
            state,
            email=ALLOWED,
            token=code,
            now=1_000_001.0,
        )
        self.assertEqual(email, ALLOWED)
        self.assertEqual(response.user.id, client.auth.user_id)
        self.assertTrue([call for call in client.auth.calls if call[0] == "verify_otp"])
        self.assertFalse(
            [call for call in client.auth.calls if call[0] == "sign_in_with_password"]
        )
        consume_call = next(
            call for call in client.rpc_calls if call[0] == "mathai_testing_auth_consume"
        )
        self.assertEqual(consume_call[1]["p_email"], ALLOWED)

    def test_wrong_otp_marks_challenge_failed_and_raises_auth_error(self):
        state = {}
        client = FakeClient()
        issue_testing_code(client, state, email=ALLOWED, now=1_000_000.0)

        def fail_verify(payload):
            raise RuntimeError("otp_expired")

        client.auth.verify_otp = fail_verify
        with self.assertRaises(AuthFlowError):
            complete_testing_login(
                client,
                state,
                email=ALLOWED,
                token="000000",
                now=1_000_001.0,
            )
        self.assertTrue(
            [call for call in client.rpc_calls if call[0] == "mathai_testing_auth_fail"]
        )

    def test_expired_local_challenge_is_rejected_before_verify(self):
        state = {}
        client = FakeClient()
        issue_testing_code(client, state, email=ALLOWED, now=1_000_000.0)
        with self.assertRaises(TestingAuthError) as raised:
            complete_testing_login(
                client,
                state,
                email=ALLOWED,
                token="123456",
                now=1_000_000.0 + TESTING_OTP_TTL_SECONDS + 1,
            )
        self.assertEqual(raised.exception.code, "expired_code")

    def test_complete_login_then_resolve_authenticated_student_returns_stable_student_id(self):
        from services.learning_runtime import resolve_authenticated_student

        STUDENT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

        class FakeQuery:
            def __init__(self, rows):
                self.rows = rows
                self.filters = []

            def select(self, _fields):
                return self

            def eq(self, field, value):
                self.filters.append((field, value))
                return self

            def execute(self):
                return SimpleNamespace(
                    data=[
                        dict(row)
                        for row in self.rows
                        if all(row.get(field) == value for field, value in self.filters)
                    ]
                )

        class ClientWithAccess(FakeClient):
            def __init__(self):
                super().__init__()
                self.access_rows = [
                    {"user_id": self.auth.user_id, "student_id": STUDENT_A, "role": "owner"}
                ]

            def table(self, name):
                if name != "student_access":
                    raise AssertionError(f"unexpected table {name}")
                return FakeQuery(self.access_rows)

        state = {}
        client = ClientWithAccess()
        code = issue_testing_code(client, state, email=ALLOWED, now=1_000_000.0)
        complete_testing_login(
            client,
            state,
            email=ALLOWED,
            token=code,
            now=1_000_001.0,
        )
        identity = resolve_authenticated_student(client)
        self.assertEqual(identity.auth_user_id, client.auth.user_id)
        self.assertEqual(identity.student_id, STUDENT_A)

    def test_service_source_has_no_service_role_or_temp_password_flow(self):
        import inspect

        module = __import__(
            "services.testing_auth_service",
            fromlist=["testing_auth_service"],
        )
        source = inspect.getsource(module)
        code_only = source.split('"""', 2)[2] if source.startswith('"""') else source
        lowered = code_only.lower()
        self.assertNotIn("service_role", lowered)
        self.assertNotIn("sign_in_with_password", lowered)
        self.assertNotIn("password rotation", lowered)
        self.assertNotIn("client.functions.invoke", lowered)

    def test_public_error_messages_are_fixed_and_non_sensitive(self):
        cases = {
            "not_allowlisted": "此 Email 不開放測試期間直接顯示驗證碼，請改用 Email 寄送驗證碼登入。",
            "invalid_challenge": "驗證碼挑戰無效，請重新顯示驗證碼。",
            "expired_code": "驗證碼過期，請重新顯示驗證碼。",
            "testing_auth_unavailable": "測試期間登入服務尚未啟用，請改用 Email 寄送驗證碼登入。",
        }
        for code, message in cases.items():
            error = TestingAuthError("raw detail", code=code)
            self.assertEqual(public_testing_auth_error_message(error), message)
            self.assertNotIn("raw detail", public_testing_auth_error_message(error))

    def test_clear_testing_challenge_removes_all_state(self):
        state = {}
        client = FakeClient()
        issue_testing_code(client, state, email=ALLOWED, now=1_000_000.0)
        clear_testing_challenge(state)
        self.assertEqual(testing_code_display(state), "")
        self.assertEqual(testing_challenge_email(state), "")


if __name__ == "__main__":
    unittest.main()
