from pathlib import Path
import unittest

from services.device_email_history import (
    MAX_HISTORY_SIZE,
    clean_email_history,
    remember_email,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app_release_v0_8_8_3.py").read_text(encoding="utf-8")


class ReferralRewardFixture:
    """Local model of the existing idempotent v070 RPC result contract."""

    def __init__(self):
        self.relations = {}
        self.processed_events = set()
        self.wallets = {}

    def establish(self, referred, referrer, *, eligible):
        if not eligible or referred == referrer or referred in self.relations:
            return False
        self.relations[referred] = {"referrer": referrer, "status": "pending"}
        return True

    def valid_use(self, referred, event_id):
        if event_id in self.processed_events:
            return False
        self.processed_events.add(event_id)
        relation = self.relations.get(referred)
        if not relation or relation["status"] != "pending":
            return False
        relation["status"] = "awarded"
        self.wallets[referred] = self.wallets.get(referred, 0) + 50
        referrer = relation["referrer"]
        self.wallets[referrer] = self.wallets.get(referrer, 0) + 50
        return True


class LoginReferralProductionHotfixTests(unittest.TestCase):
    def test_email_history_contract_and_browser_bridge(self):
        self.assertIn("sync_recent_email_history_bridge()", SOURCE)
        self.assertIn("sync_device_email_history(", SOURCE)
        self.assertIn('manual_email_option = "手動輸入其他 Email"', SOURCE)
        self.assertIn("email = normalize_email(selected_email)", SOURCE)
        self.assertIn("request_email_otp(get_private_beta_auth_client(), email)", SOURCE)

    def test_history_is_deduplicated_newest_first_and_bounded(self):
        history = clean_email_history(
            ["repeat@fixture.test", "first@fixture.test", "repeat@fixture.test", ""]
        )
        self.assertEqual(history, ["repeat@fixture.test", "first@fixture.test"])
        for index in range(MAX_HISTORY_SIZE + 3):
            history = remember_email(history, f"student{index}@fixture.test")
        self.assertEqual(len(history), MAX_HISTORY_SIZE)
        self.assertEqual(history[0], "student12@fixture.test")

    def test_history_updates_only_after_successful_identity(self):
        identity = SOURCE.split("def apply_private_beta_identity", 1)[1].split(
            "def render_auth_diagnostics", 1
        )[0]
        self.assertIn("save_recent_email(verified_email)", identity)
        native = SOURCE.split("def render_native_email_otp_login", 1)[1].split(
            "def render_private_beta_auth_login", 1
        )[0]
        for error_block in native.split("except ")[1:]:
            self.assertNotIn("save_recent_email", error_block)

    def test_referral_ui_is_registration_or_db_retry_only(self):
        edit_block = SOURCE.split("can_edit_source = bool(", 1)[1].split(
            ")\n    )", 1
        )[0]
        self.assertIn('st.session_state.get("is_new_account_registration", False)', edit_block)
        self.assertIn("retry_source_allowed", edit_block)
        self.assertNotIn("source_edit_mode", edit_block)
        self.assertNotIn("新增／修改推薦人 Email", SOURCE)
        self.assertIn('"你從哪裡知道 MathAI？"', SOURCE)
        conditional = SOURCE.split(
            'if source_type_selection == "親友／老師介紹":', 1
        )[1]
        self.assertIn('"介紹人 Email"', conditional)
        self.assertIn('"🔎 驗證介紹人資格"', conditional)

    def test_referrer_eligibility_and_relation_rpc_wiring(self):
        status = SOURCE.split("def validate_referrer", 1)[1].split(
            "def get_user_referral_status", 1
        )[0]
        self.assertIn("override_eligible", status)
        self.assertIn("has_topup", status)
        self.assertIn("effective_usage_count", status)
        self.assertIn(">= 3", status)
        self.assertIn('"mathai_referrer_status_v070"', SOURCE)
        self.assertIn('"mathai_create_referral_v070"', SOURCE)

    def test_first_valid_use_awards_both_once(self):
        fixture = ReferralRewardFixture()
        self.assertTrue(
            fixture.establish("new@fixture.test", "teacher@fixture.test", eligible=True)
        )
        self.assertTrue(fixture.valid_use("new@fixture.test", "event-1"))
        self.assertEqual(fixture.wallets["new@fixture.test"], 50)
        self.assertEqual(fixture.wallets["teacher@fixture.test"], 50)
        self.assertFalse(fixture.valid_use("new@fixture.test", "event-1"))
        self.assertEqual(fixture.wallets["new@fixture.test"], 50)
        self.assertIn('"mathai_record_use_and_award_referral_v070"', SOURCE)
        self.assertIn('row.get("event_recorded", False)', SOURCE)
        self.assertIn('row.get("referral_awarded", False)', SOURCE)
        self.assertIn("不是領這次 50 點的條件", SOURCE)


if __name__ == "__main__":
    unittest.main()
