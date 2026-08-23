import json
from pathlib import Path
import unittest

from services.device_email_history import (
    DeviceEmailHistory,
    FORBIDDEN_STORAGE_FIELDS,
    MAX_HISTORY_SIZE,
    clean_email_history,
    normalize_history_email,
    remember_email,
)


ROOT = Path(__file__).resolve().parents[1]


class MemoryStorage:
    def __init__(self, payload=None, *, unavailable=False):
        self.payload = payload
        self.unavailable = unavailable
        self.removed = False

    def read(self):
        if self.unavailable:
            raise RuntimeError("storage unavailable")
        return self.payload

    def write(self, payload):
        if self.unavailable:
            raise RuntimeError("storage unavailable")
        self.payload = payload

    def remove(self):
        if self.unavailable:
            raise RuntimeError("storage unavailable")
        self.payload = None
        self.removed = True


class DeviceEmailHistoryTests(unittest.TestCase):
    def test_release_gate_uses_real_browser_and_local_storage(self):
        component = (ROOT / "components" / "device_email_history" / "index.html").read_text(encoding="utf-8")
        gate = (ROOT / "scripts" / "auth_browser_e2e.py").read_text(encoding="utf-8")
        self.assertIn("window.localStorage", component)
        self.assertIn("streamlit:setComponentValue", component)
        self.assertIn("sync_playwright", gate)
        self.assertIn("page.reload", gate)
        self.assertIn("390", gate)
        self.assertNotIn("supabase", component.lower())

    def test_empty_history_keeps_manual_path_available(self):
        storage = MemoryStorage()
        history = DeviceEmailHistory(storage.read, storage.write, storage.remove)
        self.assertEqual(history.load(), [])
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('manual_email_option = "➕ 手動輸入新 Email"', source)
        self.assertIn("else:\n        email = st.text_input(", source)

    def test_one_and_multiple_remembered_emails_are_newest_first(self):
        self.assertEqual(clean_email_history('["one@example.com"]'), ["one@example.com"])
        history = remember_email(["older@example.com", "oldest@example.com"], "new@example.com")
        self.assertEqual(
            history,
            ["new@example.com", "older@example.com", "oldest@example.com"],
        )

    def test_duplicate_is_deduplicated_and_moved_to_front(self):
        history = remember_email(
            ["first@example.com", "repeat@example.com", "repeat@example.com"],
            "repeat@example.com",
        )
        self.assertEqual(history, ["repeat@example.com", "first@example.com"])

    def test_normalize_lowercases_and_trims(self):
        self.assertEqual(normalize_history_email(" Test@Email.com "), "test@email.com")
        self.assertEqual(normalize_history_email("not-email"), "")

    def test_maximum_history_size(self):
        history = []
        for index in range(MAX_HISTORY_SIZE + 5):
            history = remember_email(history, f"student{index}@example.com")
        self.assertEqual(len(history), MAX_HISTORY_SIZE)
        self.assertEqual(history[0], "student14@example.com")

    def test_selected_email_and_manual_input_are_wired_to_auth_email(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"這台裝置曾使用的 Email"', source)
        self.assertIn("if selected_email_option == manual_email_option", source)
        self.assertIn(
            "issue_testing_code(\n                get_private_beta_auth_client(),\n                st.session_state,\n                email=email,\n            )",
            source,
        )
        self.assertNotIn(
            "issue_testing_code(..., email=selected_email_option)", source
        )
        fallback = source.split("def render_email_otp_fallback_login", 1)[1].split(
            "def render_private_beta_auth_login", 1
        )[0]
        self.assertIn("request_email_otp(client, email)", fallback)
        self.assertNotIn("request_email_otp(client, selected_email_option)", fallback)

    def test_successful_identity_application_remembers_email_but_failed_login_does_not(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        identity_block = source.split("def apply_private_beta_identity", 1)[1].split(
            "def render_auth_diagnostics", 1
        )[0]
        self.assertIn("save_recent_email(verified_email)", identity_block)
        login_block = source.split("def render_private_beta_auth_login", 1)[1].split(
            "# ==========================================", 1
        )[0]
        testing_error_block = login_block.split("except TestingAuthError as exc:")[-1]
        self.assertNotIn("save_recent_email", testing_error_block)
        fallback_block = source.split("def render_email_otp_fallback_login", 1)[1].split(
            "def render_private_beta_auth_login", 1
        )[0]
        fallback_error_block = fallback_block.split("except AuthFlowError as exc:")[-1]
        self.assertNotIn("save_recent_email", fallback_error_block)

    def test_storage_unavailable_fails_open_to_manual_login(self):
        storage = MemoryStorage(unavailable=True)
        history = DeviceEmailHistory(storage.read, storage.write, storage.remove)
        self.assertEqual(history.load(), [])
        self.assertEqual(history.remember("student@example.com"), ["student@example.com"])
        history.clear()  # no exception

    def test_clear_removes_only_device_payload(self):
        storage = MemoryStorage('["student@example.com"]')
        history = DeviceEmailHistory(storage.read, storage.write, storage.remove)
        history.clear()
        self.assertTrue(storage.removed)
        self.assertIsNone(storage.payload)

    def test_payload_contains_only_email_addresses(self):
        storage = MemoryStorage()
        history = DeviceEmailHistory(storage.read, storage.write, storage.remove)
        history.remember("student@example.com")
        self.assertEqual(json.loads(storage.payload), ["student@example.com"])
        lowered = storage.payload.lower()
        for field in FORBIDDEN_STORAGE_FIELDS:
            self.assertNotIn(field, lowered)

    def test_trial_and_invalid_values_are_never_saved(self):
        self.assertEqual(remember_email([], "trial@example.com"), [])
        self.assertEqual(remember_email([], "wrong address"), [])


if __name__ == "__main__":
    unittest.main()
