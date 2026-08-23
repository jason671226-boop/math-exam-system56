from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.local_test_session import (
    ALLOWLISTED_LOCAL_TEST_EMAILS,
    LocalTestSessionError,
    create_local_test_user_session,
    generate_visible_test_code,
    local_test_login_enabled,
)


EMAIL = "jason671226@gmail.com"
USER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class FakeAdmin:
    def __init__(self, users):
        self.users = users
        self.generated = []

    def list_users(self, page=None, per_page=None):
        return self.users

    def generate_link(self, payload):
        self.generated.append(payload)
        return SimpleNamespace(
            user=self.users[0],
            properties=SimpleNamespace(email_otp="654321"),
        )


class FakeUserAuth:
    def __init__(self):
        self.payloads = []

    def verify_otp(self, payload):
        self.payloads.append(payload)
        return SimpleNamespace(
            user=SimpleNamespace(id=USER_ID), session=SimpleNamespace()
        )


class LocalTestSessionTests(unittest.TestCase):
    def test_gate_requires_localhost_flag_and_dev_environment(self):
        self.assertTrue(
            local_test_login_enabled(
                is_localhost=True, explicit_flag="true", app_env="development"
            )
        )
        for localhost, flag, env in (
            (False, "true", "development"),
            (True, "false", "development"),
            (True, "true", "production"),
        ):
            self.assertFalse(
                local_test_login_enabled(
                    is_localhost=localhost, explicit_flag=flag, app_env=env
                )
            )

    def test_visible_code_is_six_digits_and_regenerates(self):
        with patch("services.local_test_session.secrets.randbelow", side_effect=[1, 2]):
            self.assertEqual(generate_visible_test_code(), "000001")
            self.assertEqual(generate_visible_test_code(), "000002")

    def test_allowlist_is_exact(self):
        self.assertEqual(
            ALLOWLISTED_LOCAL_TEST_EMAILS,
            {
                "jason601226@gmail.com",
                "jason621226@gmail.com",
                "jason671226@gmail.com",
            },
        )

    def test_existing_user_gets_real_user_session_exchange(self):
        admin = FakeAdmin([SimpleNamespace(id=USER_ID, email=EMAIL)])
        admin_client = SimpleNamespace(auth=SimpleNamespace(admin=admin))
        user_auth = FakeUserAuth()
        user_client = SimpleNamespace(auth=user_auth)
        response = create_local_test_user_session(
            supabase_url="https://project.supabase.co",
            service_role_key="server-secret",
            email=EMAIL,
            user_client=user_client,
            is_localhost=True,
            explicit_flag=True,
            app_env="test",
            client_factory=lambda *_: admin_client,
        )
        self.assertIsNotNone(response.session)
        self.assertEqual(admin.generated, [{"type": "magiclink", "email": EMAIL}])
        self.assertEqual(user_auth.payloads[0]["type"], "email")
        self.assertEqual(user_auth.payloads[0]["token"], "654321")

    def test_missing_or_non_allowlisted_user_never_generates_link(self):
        for email, users in (("other@example.com", []), (EMAIL, [])):
            admin = FakeAdmin(users)
            admin_client = SimpleNamespace(auth=SimpleNamespace(admin=admin))
            with self.assertRaises(LocalTestSessionError):
                create_local_test_user_session(
                    supabase_url="https://project.supabase.co",
                    service_role_key="server-secret",
                    email=email,
                    user_client=SimpleNamespace(auth=FakeUserAuth()),
                    is_localhost=True,
                    explicit_flag=True,
                    app_env="test",
                    client_factory=lambda *_: admin_client,
                )
            self.assertEqual(admin.generated, [])


if __name__ == "__main__":
    unittest.main()
