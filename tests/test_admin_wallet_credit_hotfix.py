from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "app_release_v0_8_8_3.py").read_text(
    encoding="utf-8-sig"
)


def test_admin_credit_uses_service_role_rpc_and_admin_guard():
    assert "def admin_wallet_credit(" in SOURCE
    assert 'st.session_state.get("admin_unlocked", False)' in SOURCE
    assert 'get_streamlit_secret("SUPABASE_SERVICE_ROLE_KEY", "")' in SOURCE
    assert 'admin_client.rpc(' in SOURCE
    assert '"mathai_admin_wallet_credit"' in SOURCE
    assert '"p_reference_id"' in SOURCE


def test_student_debit_path_still_rejects_positive_delta():
    debit = SOURCE.split("def wallet_adjust(", 1)[1].split(
        "def sync_wallet_balance_to_session", 1
    )[0]
    assert "delta >= 0" in debit
    assert "mathai_private_wallet_debit" in debit


def test_manual_credit_does_not_report_success_on_rpc_failure():
    manual = SOURCE.split("manual_email =", 1)[1].split(
        "st.markdown", 1
    )[0]
    assert "admin_wallet_credit(" in manual
    assert 'if credit_result.get("success")' in manual
    assert "手動儲值失敗" in manual


def test_topup_approval_is_gated_by_credit_success_and_stable_reference():
    topup = SOURCE.split("selected_req_ids =", 1)[1].split(
        "manual_email =", 1
    )[0]
    assert "admin_wallet_credit(" in topup
    assert 'reference_id=f"topup-{req_id}"' in topup
    assert 'if credit_result.get("success")' in topup
    assert "approve_topup_request(req_id)" in topup
