import ast
from pathlib import Path
import unittest

from services.auth_service import (
    AuthFlowError,
    normalize_login_email,
    public_auth_error_message,
    verify_email_otp,
)


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "app.py"


class _FailingAuth:
    def __init__(self, message: str) -> None:
        self.message = message

    def verify_otp(self, _payload):
        raise RuntimeError(self.message)


class _Client:
    def __init__(self, message: str) -> None:
        self.auth = _FailingAuth(message)


def _function_ui_literals(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    visible_calls = {
        "button",
        "caption",
        "code",
        "error",
        "form_submit_button",
        "info",
        "markdown",
        "selectbox",
        "success",
        "subheader",
        "text_input",
        "title",
        "warning",
    }
    values = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        attribute = node.func if isinstance(node.func, ast.Attribute) else None
        if attribute is None or attribute.attr not in visible_calls:
            continue
        value = node.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            values.append(value.value)
    return "\n".join(values)


def _function_widget_keys(source: str, function_name: str) -> list[str]:
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    keys = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "key" and isinstance(keyword.value, ast.Constant):
                keys.append(str(keyword.value.value))
    return keys


class AuthRegistrationUxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_SOURCE.read_text(encoding="utf-8")

    def test_public_auth_copy_is_simple_and_has_no_internal_terms(self):
        visible = _function_ui_literals(self.source, "render_private_beta_auth_login")
        for required in (
            "Email",
            "顯示驗證碼（測試期間）",
            "這台裝置曾使用的 Email",
            "驗證碼",
            "驗證並登入",
        ):
            self.assertIn(required, visible)
        for forbidden in (
            "Private Beta",
            "Supabase",
            "student_access",
            "student_id",
            "ownership",
            "RLS",
            "RPC",
            "JWT",
            "UUID",
        ):
            self.assertNotIn(forbidden, visible)

    def test_testing_login_never_displays_email_sent_copy(self):
        visible = _function_ui_literals(self.source, "render_private_beta_auth_login")
        for forbidden in (
            "已寄出 Email",
            "驗證碼已寄出，請查看 Email。",
            "寄送驗證碼",
        ):
            self.assertNotIn(forbidden, visible)

    def test_real_email_otp_fallback_is_an_explicit_secondary_surface(self):
        visible = _function_ui_literals(self.source, "render_email_otp_fallback_login")
        for required in ("Email（正式 OTP 流程）", "寄送驗證碼", "登入／繼續"):
            self.assertIn(required, visible)
        self.assertNotIn("顯示驗證碼（測試期間）", visible)

    def test_internal_auth_diagnostics_are_privileged(self):
        diagnostics = _function_ui_literals(self.source, "render_auth_diagnostics")
        self.assertIn("student_access", diagnostics)
        self.assertIn('st.session_state.get("developer_mode", False)', self.source)
        self.assertIn('st.session_state.get("admin_unlocked", False)', self.source)

    def test_registration_title_privacy_copy_and_version(self):
        self.assertIn('APP_VERSION = "v0.8.8.2"', self.source)
        self.assertIn('st.subheader("學生登入／註冊")', self.source)
        self.assertIn(
            "為保護個人隱私，可以使用英文名字或暱稱，不一定要填寫真實中文姓名。",
            self.source,
        )

    def test_login_widget_keys_are_unique_within_each_login_surface(self):
        testing_keys = _function_widget_keys(
            self.source, "render_private_beta_auth_login"
        )
        fallback_keys = _function_widget_keys(
            self.source, "render_email_otp_fallback_login"
        )
        self.assertEqual(len(testing_keys), len(set(testing_keys)))
        self.assertEqual(len(fallback_keys), len(set(fallback_keys)))
        self.assertEqual(set(testing_keys) & set(fallback_keys), set())
        for key in testing_keys:
            self.assertIn("testing_login_", key)
        for key in fallback_keys:
            self.assertIn("private_beta_", key)

    def test_public_auth_errors_are_fixed_and_non_sensitive(self):
        cases = {
            "invalid_email": "Email 格式錯誤",
            "invalid_code": "驗證碼錯誤",
            "expired_code": "驗證碼過期",
            "login_unavailable": "登入暫時失敗，請稍後再試",
        }
        for code, message in cases.items():
            error = AuthFlowError("raw Supabase JWT SQL detail", code=code)
            self.assertEqual(public_auth_error_message(error), message)
            self.assertNotIn("Supabase", public_auth_error_message(error))

    def test_legacy_profile_loads_as_existing_and_new_user_gets_200_credits(self):
        identity_block = self.source.split("def apply_private_beta_identity", 1)[1].split(
            "def render_auth_diagnostics", 1
        )[0]
        self.assertIn("db_profile = build_complete_user_profile(verified_email)", identity_block)
        self.assertIn('st.session_state["profile_load_notice"] = "existing"', identity_block)
        self.assertIn("reset_user_profile_for_new_account(verified_email, credits=200)", identity_block)
        self.assertIn('st.session_state["is_new_account_registration"] = False', identity_block)
        self.assertIn('st.session_state["is_new_account_registration"] = True', identity_block)

    def test_invalid_email_and_otp_failures_are_classified(self):
        with self.assertRaises(AuthFlowError) as invalid_email:
            normalize_login_email("not-an-email")
        self.assertEqual(invalid_email.exception.code, "invalid_email")

        with self.assertRaises(AuthFlowError) as expired:
            verify_email_otp(_Client("otp_expired"), "student@example.com", "123456")
        self.assertEqual(expired.exception.code, "expired_code")

        with self.assertRaises(AuthFlowError) as invalid:
            verify_email_otp(_Client("bad token"), "student@example.com", "123456")
        self.assertEqual(invalid.exception.code, "invalid_code")

    def test_native_existing_login_is_read_only_and_fail_closed(self):
        native = self.source.split("def render_native_email_otp_login", 1)[1].split(
            "def render_private_beta_auth_login", 1
        )[0]
        self.assertIn("identity = resolve_authenticated_student(client)", native)
        self.assertIn("require_existing=True", native)
        self.assertIn("is_new_account=False", native)
        self.assertNotIn("resolve_or_provision_authenticated_student", native)
        self.assertNotIn("mathai_private_ensure_student", native)
        wallet_sync = self.source.split("def sync_wallet_balance_to_session", 1)[1].split(
            "def add_user_credits", 1
        )[0]
        self.assertIn("if not is_new_account:", wallet_sync)
        self.assertIn("bootstrap was blocked", wallet_sync)


if __name__ == "__main__":
    unittest.main()
