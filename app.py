import io
import json
import streamlit as st
import streamlit.components.v1 as components
import re
import urllib.parse
import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta
import uuid
import base64
import hashlib
import hmac
from pathlib import Path

from math_output import MATH_OUTPUT_RULES, normalize_math_markdown
from image_input import collect_image_inputs, image_bytes, load_rgb_image
from navigation_state import apply_pending_main_tab, queue_main_tab

# 學習地圖模組（MVP）
try:
    from learning_map import (
        get_classic_question_type_names_for_units,
        get_subunit_names_for_units,
        get_topic_names_for_subunits,
        get_unit_names_for_profile,
        render_learning_map,
    )
    LEARNING_MAP_AVAILABLE = True
except ImportError:
    get_classic_question_type_names_for_units = None
    get_subunit_names_for_units = None
    get_topic_names_for_subunits = None
    get_unit_names_for_profile = None
    render_learning_map = None
    LEARNING_MAP_AVAILABLE = False

# Phase 2B：初始診斷 Pilot。主程式只做薄接線，診斷 UI 與狀態集中在獨立模組。
try:
    from diagnostic_pilot_ui import render_diagnostic_pilot
    DIAGNOSTIC_PILOT_AVAILABLE = True
except ImportError:
    render_diagnostic_pilot = None
    DIAGNOSTIC_PILOT_AVAILABLE = False

try:
    from services.auth_service import (
        AuthFlowError,
        clear_authenticated_session,
        request_email_otp,
        verify_email_otp,
    )
    from services.learning_runtime import (
        LearningIdentityError,
        build_learning_runtime,
        resolve_authenticated_student,
    )
except ModuleNotFoundError:
    from app.services.auth_service import (
        AuthFlowError,
        clear_authenticated_session,
        request_email_otp,
        verify_email_otp,
    )
    from app.services.learning_runtime import (
        LearningIdentityError,
        build_learning_runtime,
        resolve_authenticated_student,
    )

try:
    from beta_feedback_ui import render_beta_feedback
except ModuleNotFoundError:
    from app.beta_feedback_ui import render_beta_feedback

# 嘗試載入 Pandas (處理 CSV)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# 集中管理 AI 呼叫與錯誤分類
from ai_service import (
    AIServiceError,
    call_gemini_api,
    get_ai_debug_message,
    get_ai_error_code,
    get_ai_error_message,
)

# 嘗試載入 Supabase 套件
try:
    from supabase import Client, create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    from PIL import Image, ImageEnhance, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageEnhance = None
    ImageDraw = None
    PIL_AVAILABLE = False

# 雲端穩定版圖片點選元件：
# 使用兩次點擊建立矩形框，或單次點擊建立圓形標記。
# 不再依賴 streamlit-drawable-canvas，避免 Streamlit Cloud 背景圖片空白。
try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    IMAGE_COORDINATES_AVAILABLE = True
except ImportError:
    streamlit_image_coordinates = None
    IMAGE_COORDINATES_AVAILABLE = False

# 瀏覽器裝置記憶：只保存曾登入的 Email，不保存密碼或 OTP。
try:
    from streamlit_cookies_controller import CookieController
    COOKIE_CONTROLLER_AVAILABLE = True
except ImportError:
    CookieController = None
    COOKIE_CONTROLLER_AVAILABLE = False

st.set_page_config(
    page_title="AI 數學錯題迭代系統", 
    page_icon="🤖", 
    initial_sidebar_state="expanded", 
    layout="wide"
)

# 介面微調：側欄 QR Code 自適應，主功能導覽列固定在上方。
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] [data-testid="stImage"] img {
        width: 100% !important;
        max-width: 260px !important;
        height: auto !important;
        object-fit: contain !important;
        display: block !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    /*
      v0.5.9 不再固定 st.tabs 內部頁籤。
      改用獨立的 Streamlit 原生按鈕導覽列。
    */
    /* 桌面版：固定顯示五個功能按鈕。 */
    .st-key-main_nav_desktop {
        position: fixed !important;
        top: 2.90rem !important;
        left: 20rem !important;
        right: 0.55rem !important;
        width: auto !important;
        max-width: calc(100vw - 20.55rem) !important;
        box-sizing: border-box !important;
        z-index: 999999 !important;
        background: rgba(255, 255, 255, 0.98) !important;
        border: 1px solid rgba(49, 51, 63, 0.18) !important;
        border-radius: 0.65rem !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.14) !important;
        padding: 0.20rem 0.25rem !important;
        overflow: hidden !important;
    }

    .st-key-main_nav_desktop [data-testid="stHorizontalBlock"] {
        gap: 0.12rem !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        min-width: 0 !important;
    }

    .st-key-main_nav_desktop [data-testid="column"] {
        min-width: 0 !important;
        flex: 1 1 0 !important;
    }

    .st-key-main_nav_desktop button {
        width: 100% !important;
        min-width: 0 !important;
        min-height: 1.82rem !important;
        padding: 0.06rem 0.10rem !important;
    }

    .st-key-main_nav_desktop button p {
        white-space: nowrap !important;
        font-size: 0.78rem !important;
        line-height: 1.05 !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    body:has(section[data-testid="stSidebar"][aria-expanded="false"])
    .st-key-main_nav_desktop {
        left: 4.2rem !important;
        max-width: calc(100vw - 4.8rem) !important;
    }

    /* 手機版：不用橫滑，改用可點選的下拉式選單。 */
    .st-key-main_nav_mobile {
        display: none !important;
    }

    .main-nav-content-spacer {
        height: 3.05rem;
    }

    .mathai-mobile-guide {
        display: none;
    }

    @media (max-width: 900px) {
        .st-key-main_nav_desktop {
            display: none !important;
        }

        .st-key-main_nav_mobile {
            display: block !important;
            position: relative !important;
            top: auto !important;
            z-index: 20 !important;
            width: 100% !important;
            box-sizing: border-box !important;
            margin-top: 3.05rem !important;
            margin-bottom: 0.65rem !important;
            padding: 0.46rem 0.52rem 0.50rem 0.52rem !important;
            background: rgba(255, 255, 255, 0.98) !important;
            border: 1px solid rgba(49, 51, 63, 0.18) !important;
            border-radius: 0.58rem !important;
            box-shadow: 0 3px 12px rgba(0, 0, 0, 0.12) !important;
            overflow: visible !important;
            clear: both !important;
        }

        .st-key-main_nav_mobile [data-testid="stSelectbox"] {
            margin-bottom: 0 !important;
        }

        .st-key-main_nav_mobile [data-baseweb="select"] > div {
            min-height: 2.65rem !important;
            font-size: 0.96rem !important;
            font-weight: 700 !important;
            border-width: 2px !important;
        }

        .st-key-main_nav_mobile p {
            margin-bottom: 0.18rem !important;
        }

        .main-nav-content-spacer {
            height: 0.10rem;
        }

        .mathai-mobile-guide {
            display: block;
            margin: 0.45rem 0 0.55rem 0;
            padding: 0.58rem 0.65rem;
            border-left: 4px solid #1c83e1;
            border-radius: 0.45rem;
            background: #eef6ff;
            font-size: 0.80rem;
            line-height: 1.45;
        }
    }

    @media (prefers-color-scheme: dark) {
        .st-key-main_nav_desktop,
        .st-key-main_nav_mobile {
            background: rgba(14, 17, 23, 0.98) !important;
        }

        .mathai-mobile-guide {
            background: rgba(28, 131, 225, 0.14);
        }
    }

    .mathai-tipbar {
        position: fixed; top: 0.2rem; left: 20rem; right: 0.55rem;
        z-index: 1000000; display: flex; align-items: center; gap: 0.65rem;
        min-height: 2.20rem; padding: 0.30rem 0.65rem;
        border: 1px solid rgba(49,51,63,.14); border-radius: .55rem;
        background: rgba(255,255,255,.97); box-shadow: 0 2px 10px rgba(0,0,0,.10);
        overflow: hidden; box-sizing: border-box;
    }
    .mathai-tipbar__label {
        flex: 0 0 auto; font-weight: 700; white-space: nowrap;
        padding-left: .5rem; border-left: 1px solid rgba(49,51,63,.20);
    }
    .mathai-tipbar__viewport {
        position: relative; flex: 1 1 auto; min-width: 0;
        height: 1.30rem; overflow: hidden;
    }
    .mathai-tipbar__tip {
        position: absolute; inset: 0; display: flex; align-items: center;
        opacity: 0; transform: translateY(5px); white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis;
        animation-name: mathaiTipSentence;
        animation-timing-function: ease-in-out;
        animation-iteration-count: infinite;
    }
    @keyframes mathaiTipSentence {
        0% { opacity: 0; transform: translateY(5px); }
        1% { opacity: 1; transform: translateY(0); }
        3.2% { opacity: 1; transform: translateY(0); }
        4% { opacity: 0; transform: translateY(-4px); }
        100% { opacity: 0; transform: translateY(-4px); }
    }
    body:has(section[data-testid="stSidebar"][aria-expanded="false"]) .mathai-tipbar {
        left: 4.2rem;
    }
    @media (max-width: 900px) {
        .mathai-tipbar {
            left: .25rem; right: .25rem; font-size: .73rem;
            gap: .35rem; padding: .24rem .38rem;
        }
        .mathai-tipbar__label { padding-left: .32rem; }
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        padding-top: .45rem !important;
        padding-left: .75rem !important;
        padding-right: .75rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: .32rem !important;
    }

    /* 隱藏主功能原生頁籤列，只保留內容；付款方式等其他 tabs 不受影響。 */
    .st-key-main_tabs_control [data-baseweb="tab-list"],
    .st-key-main_tabs_control [role="tablist"],
    .st-key-main_tabs_control > div:first-child > div:first-child {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }

    .st-key-main_tabs_control {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

APP_VERSION = "v0.8.7.3"
APP_DIR = Path(__file__).resolve().parent
LOCAL_EMAILS_FILE = APP_DIR / "recent_emails.json"
LINE_PAY_QR_FILE = APP_DIR / "line_pay_qr.jpg"
PROFILE_CONTROL_FILE = APP_DIR / "profile_controls.json"

# --- 裝置 Email 記憶與儲值紀錄備援 ---
# Email 清單保存在目前瀏覽器 Cookie；不再使用雲端伺服器共用的 recent_emails.json。
DEVICE_EMAIL_COOKIE = "mathai_recent_emails_v1"
TOPUP_FILE = "topup_requests.json"

cookie_controller = (
    CookieController(key="mathai_device_cookie_controller")
    if COOKIE_CONTROLLER_AVAILABLE
    else None
)

today_str = date.today().isoformat()

# 全域初始化 Session State，確保側邊欄隨時都能抓到資料不崩潰
if "setup_complete" not in st.session_state:
    st.session_state["setup_complete"] = False
if "is_trial" not in st.session_state:
    st.session_state["is_trial"] = False
if "user_profile" not in st.session_state:
    st.session_state["user_profile"] = {
        "last_name": "", "first_name": "", 
        "email": "trial@example.com", "city": "新北市", "district": "土城區", "school": "",
        "grade": "8年級(國二)", "version": "康軒版", 
        "traits": [], "interests": [], "credits": 30, "last_login_date": today_str
    }

if "is_verified" not in st.session_state:
    current_email = st.session_state["user_profile"].get("email", "")
    if current_email and current_email != "trial@example.com":
        st.session_state["is_verified"] = True
    else:
        st.session_state["is_verified"] = False

if "scanned_text" not in st.session_state: st.session_state["scanned_text"] = ""
if "generated_content" not in st.session_state: st.session_state["generated_content"] = ""
if "variation_content" not in st.session_state: st.session_state["variation_content"] = ""
if "history_mistakes" not in st.session_state: st.session_state["history_mistakes"] = ""
if "admin_unlocked" not in st.session_state: st.session_state["admin_unlocked"] = False
if "custom_interest" not in st.session_state: st.session_state["custom_interest"] = ""
if "ip_trial_history" not in st.session_state: st.session_state["ip_trial_history"] = {}
if "otp_sent" not in st.session_state: st.session_state["otp_sent"] = False
if "generated_otp" not in st.session_state: st.session_state["generated_otp"] = ""
if "pending_email" not in st.session_state: st.session_state["pending_email"] = ""
if "scan_manual_mode" not in st.session_state: st.session_state["scan_manual_mode"] = False
if "scan_error_message" not in st.session_state: st.session_state["scan_error_message"] = ""
if "scan_error_code" not in st.session_state: st.session_state["scan_error_code"] = ""
if "manual_scan_text" not in st.session_state: st.session_state["manual_scan_text"] = ""
if "custom_exam_content" not in st.session_state: st.session_state["custom_exam_content"] = ""
if "custom_exam_last_summary" not in st.session_state: st.session_state["custom_exam_last_summary"] = {}
if "developer_mode" not in st.session_state: st.session_state["developer_mode"] = False
if "iterative_exam_analysis" not in st.session_state: st.session_state["iterative_exam_analysis"] = ""
if "scan_scope_warning" not in st.session_state: st.session_state["scan_scope_warning"] = ""
if "scan_scope_estimate" not in st.session_state: st.session_state["scan_scope_estimate"] = {}
if "loaded_profile_email" not in st.session_state: st.session_state["loaded_profile_email"] = ""
if "is_new_account_registration" not in st.session_state: st.session_state["is_new_account_registration"] = False
if "registration_source_result" not in st.session_state: st.session_state["registration_source_result"] = ""
if "last_exam_email_sent_at" not in st.session_state: st.session_state["last_exam_email_sent_at"] = None
if "request_scroll_to_top" not in st.session_state: st.session_state["request_scroll_to_top"] = False
if "source_edit_mode" not in st.session_state: st.session_state["source_edit_mode"] = False
if "wallet_synced_email" not in st.session_state: st.session_state["wallet_synced_email"] = ""
if "wallet_last_message" not in st.session_state: st.session_state["wallet_last_message"] = ""


def _profile_list_value(value):
    """兼容 Supabase jsonb、文字 JSON 與一般文字格式。"""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                ]
        except Exception:
            pass
        return [
            item.strip()
            for item in re.split(r"[、,，;；\n]+", text)
            if item.strip()
        ]
    return []


def _profile_control_default(email):
    """v0.7.0：會員資料唯一正式來源為 student_profile_controls。"""
    return {
        "_found": False,
        "email": str(email or "").strip().lower(),
        "identity_locked": False,
        "locked_last_name": "",
        "locked_first_name": "",
        "city": "",
        "district": "",
        "school": "",
        "grade": "",
        "version": "",
        "traits": [],
        "interests": [],
        "discovery_source": "",
        "source_detail": "",
        "source_reward_status": "none",
        "referral_eligible_override": False,
        "change_year": date.today().year,
        "change_count": 0,
    }


def _read_profile_controls_local():
    """僅供 Supabase 完全未設定時的離線本機開發備援。"""
    try:
        if PROFILE_CONTROL_FILE.exists():
            data = json.loads(
                PROFILE_CONTROL_FILE.read_text(encoding="utf-8")
            )
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _write_profile_controls_local(data):
    try:
        PROFILE_CONTROL_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_profile_control(email):
    """讀取會員主檔。

    有 Supabase 時只讀安全 RPC；本機 JSON 不再覆蓋雲端資料。
    """
    email = str(email or "").strip().lower()
    control = _profile_control_default(email)
    if not email or email == "trial@example.com":
        return control

    account_client = _authenticated_account_client()
    if account_client:
        try:
            result = account_client.rpc("mathai_private_profile_get").execute()
            rows = result.data or []
            row = rows[0] if isinstance(rows, list) and rows else rows
            if isinstance(row, dict) and row and bool(row.get("found", True)):
                control.update({
                    "_found": True,
                    "email": email,
                    "identity_locked": bool(
                        row.get("identity_locked", False)
                    ),
                    "locked_last_name": str(
                        row.get("locked_last_name") or ""
                    ).strip(),
                    "locked_first_name": str(
                        row.get("locked_first_name") or ""
                    ).strip(),
                    "city": str(row.get("city") or "").strip(),
                    "district": str(row.get("district") or "").strip(),
                    "school": str(row.get("school") or "").strip(),
                    "grade": str(row.get("grade") or "").strip(),
                    "version": str(row.get("version") or "").strip(),
                    "traits": _profile_list_value(
                        row.get("traits", [])
                    ),
                    "interests": _profile_list_value(
                        row.get("interests", [])
                    ),
                    "discovery_source": str(
                        row.get("discovery_source") or ""
                    ).strip(),
                    "source_detail": str(
                        row.get("source_detail") or ""
                    ).strip(),
                    "source_reward_status": str(
                        row.get("source_reward_status") or "none"
                    ).strip(),
                    "referral_eligible_override": bool(
                        row.get("referral_eligible_override", False)
                    ),
                    "change_year": int(
                        row.get("change_year") or date.today().year
                    ),
                    "change_count": int(
                        row.get("change_count") or 0
                    ),
                })
            return control
        except Exception as exc:
            st.session_state["profile_cloud_read_warning"] = str(exc)
            return control

    local_data = _read_profile_controls_local()
    if email in local_data and isinstance(local_data[email], dict):
        local_row = local_data[email]
        control.update(local_row)
        control["_found"] = True
        control["traits"] = _profile_list_value(
            local_row.get("traits", [])
        )
        control["interests"] = _profile_list_value(
            local_row.get("interests", [])
        )
    return control


def save_profile_control(control):
    """儲存會員主檔；正式環境只寫 Supabase RPC。"""
    email = str(control.get("email", "")).strip().lower()
    if not email or email == "trial@example.com":
        return False

    payload = {
        "p_email": email,
        "p_identity_locked": bool(
            control.get("identity_locked", False)
        ),
        "p_locked_last_name": str(
            control.get("locked_last_name", "")
        ).strip(),
        "p_locked_first_name": str(
            control.get("locked_first_name", "")
        ).strip(),
        "p_city": str(control.get("city", "")).strip(),
        "p_district": str(control.get("district", "")).strip(),
        "p_school": str(control.get("school", "")).strip(),
        "p_grade": str(control.get("grade", "")).strip(),
        "p_version": str(control.get("version", "")).strip(),
        "p_traits": _profile_list_value(
            control.get("traits", [])
        ),
        "p_interests": _profile_list_value(
            control.get("interests", [])
        ),
        "p_discovery_source": str(
            control.get("discovery_source", "")
        ).strip(),
        "p_source_detail": str(
            control.get("source_detail", "")
        ).strip(),
        "p_source_reward_status": str(
            control.get("source_reward_status", "none")
        ).strip() or "none",
        "p_referral_eligible_override": bool(
            control.get("referral_eligible_override", False)
        ),
        "p_change_year": int(
            control.get("change_year") or date.today().year
        ),
        "p_change_count": int(
            control.get("change_count") or 0
        ),
    }

    account_client = _authenticated_account_client()
    if account_client:
        try:
            payload.pop("p_email", None)
            result = account_client.rpc(
                "mathai_private_profile_save", payload
            ).execute()
            saved = bool(result.data)
            if saved:
                return True
            st.session_state["profile_cloud_save_warning"] = (
                "mathai_profile_save_v070 未回傳成功。"
            )
            return False
        except Exception as exc:
            st.session_state["profile_cloud_save_warning"] = str(exc)
            return False

    local_data = _read_profile_controls_local()
    local_copy = dict(control)
    local_copy["_found"] = True
    local_data[email] = local_copy
    _write_profile_controls_local(local_data)
    return True


def remaining_grade_version_changes(control):
    current_year = date.today().year
    change_year = int(
        control.get("change_year") or current_year
    )
    change_count = int(control.get("change_count") or 0)
    if change_year != current_year:
        return 2
    return max(0, 2 - change_count)



def _clean_recent_email_list(value):
    """將 Cookie 內容整理成安全、去重複的 Email 清單。"""
    try:
        if isinstance(value, str):
            value = json.loads(value)
    except Exception:
        value = []

    if not isinstance(value, list):
        return []

    cleaned = []
    for item in value:
        email = str(item).strip().lower()
        if (
            email
            and "@" in email
            and email != "trial@example.com"
            and email not in cleaned
        ):
            cleaned.append(email)
    return cleaned[:10]


def is_localhost_request():
    """只在本機 localhost 開啟開發者快速測試功能。"""
    try:
        host = str(st.context.headers.get("Host", "")).lower()
        return host.startswith("localhost") or host.startswith("127.0.0.1")
    except Exception:
        return False


def _read_local_recent_emails():
    """本機開發模式：將曾登入 Email 保存於 C:\\MathAI\\app\\recent_emails.json。"""
    try:
        if LOCAL_EMAILS_FILE.exists():
            return _clean_recent_email_list(
                json.loads(LOCAL_EMAILS_FILE.read_text(encoding="utf-8"))
            )
    except Exception:
        pass
    return []


def _write_local_recent_emails(emails):
    try:
        LOCAL_EMAILS_FILE.write_text(
            json.dumps(emails[:10], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_recent_emails():
    """
    本機：優先讀取 recent_emails.json，重新啟動程式後仍保留。
    雲端：讀取目前瀏覽器 Cookie。
    """
    combined = []

    if is_localhost_request():
        combined.extend(_read_local_recent_emails())

    if cookie_controller is not None:
        try:
            combined.extend(
                _clean_recent_email_list(
                    cookie_controller.get(DEVICE_EMAIL_COOKIE)
                )
            )
        except Exception:
            pass

    return _clean_recent_email_list(combined)


def save_recent_email(email):
    """記住 Email；本機寫入檔案，瀏覽器同時寫入 Cookie。"""
    email = str(email or "").strip().lower()
    if not email or "@" not in email or email == "trial@example.com":
        return

    emails = get_recent_emails()
    if email in emails:
        emails.remove(email)
    emails.insert(0, email)
    emails = emails[:10]

    if is_localhost_request():
        _write_local_recent_emails(emails)

    if cookie_controller is not None:
        try:
            cookie_controller.set(
                DEVICE_EMAIL_COOKIE,
                json.dumps(emails, ensure_ascii=False),
                expires=datetime.now() + timedelta(days=365),
                same_site="lax",
            )
        except Exception:
            pass


def clear_recent_emails():
    """清除本機檔案與目前瀏覽器 Cookie 中的 Email 清單。"""
    if is_localhost_request():
        try:
            if LOCAL_EMAILS_FILE.exists():
                LOCAL_EMAILS_FILE.unlink()
        except Exception:
            pass

    if cookie_controller is not None:
        try:
            cookie_controller.remove(
                DEVICE_EMAIL_COOKIE,
                same_site="lax",
            )
        except Exception:
            pass



def sanitize_multiselect_state(key, valid_options):
    """移除因上層選項變動而失效的多選值，避免越權或跨單元殘留。"""
    current = st.session_state.get(key, [])
    if not isinstance(current, list):
        current = []
    valid_set = set(valid_options)
    cleaned = [item for item in current if item in valid_set]
    if cleaned != current:
        st.session_state[key] = cleaned



def get_client_ip():
    try:
        headers = st.context.headers
        if "Cf-Connecting-Ip" in headers:
            return headers["Cf-Connecting-Ip"]
        elif "X-Forwarded-For" in headers:
            return headers["X-Forwarded-For"].split(",")[0].strip()
        return "127.0.0.1"
    except Exception:
        return "127.0.0.1"

# 全國縣市與鄉鎮市區二級字典
taiwan_districts = {
    "台北市": ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"],
    "新北市": ["板橋區", "新莊區", "中和區", "永和區", "土城區", "樹林區", "三峽區", "鶯歌區", "三重區", "蘆洲區", "五股區", "泰山區", "林口區", "八里區", "淡水區", "三芝區", "石門區", "金山區", "萬里區", "汐止區", "瑞芳區", "貢寮區", "雙溪區", "平溪區", "新店區", "深坑區", "石碇區", "坪林區", "烏來區"],
    "基隆市": ["仁愛區", "信義區", "中正區", "中山區", "安樂區", "暖暖區", "七堵區"],
    "桃園市": ["桃園區", "中壢區", "平鎮區", "八德區", "楊梅區", "蘆竹區", "大溪區", "龍潭區", "龜山區", "大園區", "觀音區", "新屋區", "複興區"],
    "新竹市": ["東區", "北區", "香山區"],
    "新竹縣": ["竹北市", "竹東鎮", "新埔鎮", "關西鎮", "湖口鄉", "新豐鄉", "芎林鄉", "橫山鄉", "北埔鄉", "寶山鄉", "峨眉鄉", "尖石鄉", "五峰鄉"],
    "苗栗縣": ["苗栗市", "頭份市", "竹南鎮", "後龍鎮", "通霄鎮", "苑裡鎮", "卓欄鎮", "造橋鄉", "西湖鄉", "頭屋鄉", "公館鄉", "銅鑼鄉", "三義鄉", "大湖鄉", "獅潭鄉", "三灣鄉", "南庄鄉", "泰安鄉"],
    "台中市": ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區", "太平區", "大里區", "霧峰區", "烏日區", "豐原區", "后里區", "石岡區", "東勢區", "和平區", "新社區", "潭子區", "大雅區", "神岡區", "大肚區", "沙鹿區", "龍井區", "梧棲區", "清水區", "大甲區", "外埔區", "大安區"],
    "彰化縣": ["彰化市", "員林市", "和美鎮", "鹿港鎮", "溪湖鎮", "二林鎮", "田中鎮", "北斗鎮", "花壇鄉", "芬園鄉", "大村鄉", "永靖鄉", "伸港鄉", "線西鄉", "福興鄉", "秀水鄉", "埔心鄉", "埔鹽鄉", "大城鄉", "芳苑鄉", "竹塘鄉", "社頭鄉", "二水鄉", "田尾鄉", "埤頭鄉", "溪州鄉"],
    "南投縣": ["南投市", "埔里鎮", "草屯鎮", "竹山鎮", "集集鎮", "名間鄉", "鹿谷鄉", "中寮鄉", "魚池鄉", "國姓鄉", "水里鄉", "信義鄉", "仁愛鄉"],
    "雲林縣": ["斗六市", "斗南鎮", "虎尾鎮", "西螺鎮", "土庫鎮", "北港鎮", "古坑鄉", "大埤鄉", "莿桐鄉", "林內鄉", "二崙鄉", "崙背鄉", "麥寮鄉", "東勢鄉", "褒忠鄉", "臺西鄉", "元長鄉", "四湖鄉", "口湖鄉", "水林鄉"],
    "嘉義市": ["東區", "西區"],
    "嘉義縣": ["太保市", "朴子市", "布袋鎮", "大林鎮", "民雄鄉", "溪口鄉", "新港鄉", "六腳鄉", "東石鄉", "義竹鄉", "鹿草鄉", "水上鄉", "中埔鄉", "竹崎鄉", "梅山鄉", "番路鄉", "大埔鄉", "阿里山鄉"],
    "台南市": ["中西區", "東區", "南區", "北區", "安平區", "安南區", "永康區", "歸仁區", "新化區", "左鎮區", "玉井區", "楠西區", "南化區", "仁德區", "關廟區", "龍崎區", "官田區", "麻豆區", "佳里區", "西港區", "七股區", "將軍區", "學甲區", "北門區", "新營區", "後壁區", "白河區", "東山區", "六甲區", "下營區", "柳營區", "鹽水區", "善化區", "大內區", "山上區", "新市區", "安定區"],
    "高雄市": ["楠梓區", "左營區", "鼓山區", "三民區", "鹽埕區", "前金區", "新興區", "苓雅區", "前鎮區", "旗津區", "小港區", "鳳山區", "林園區", "大寮區", "大樹區", "大社區", "仁武區", "鳥松區", "岡山區", "橋頭區", "燕巢區", "田寮區", "阿蓮區", "路竹區", "湖內區", "茄萣區", "永安區", "彌陀區", "梓官區", "旗山區", "美濃區", "六龜區", "杉林區", "甲仙區", "桃源區", "朱溪區", "茂林區", "內門區"],
    "屏東縣": ["屏東市", "潮州鎮", "東港鎮", "恆春鎮", "萬丹鄉", "長治鄉", "麟洛鄉", "九如鄉", "里港鄉", "鹽埔鄉", "高樹鄉", "萬欄鄉", "內埔鄉", "竹田鄉", "新埤鄉", "枋寮鄉", "新園鄉", "崁頂鄉", "林邊鄉", "南州鄉", "佳冬鄉", "琉球鄉", "車城鄉", "滿州鄉", "枋山鄉", "三地門鄉", "霧臺鄉", "瑪家鄉", "泰武鄉", "來義鄉", "春日鄉", "獅子鄉", "牡丹鄉"],
    "宜蘭縣": ["宜蘭市", "羅東鎮", "蘇澳鎮", "頭城鎮", "礁溪鄉", "壯圍鄉", "員山鄉", "冬山鄉", "五結鄉", "三星鄉", "大同鄉", "南澳鄉"],
    "花蓮縣": ["花蓮市", "鳳林鎮", "玉里鎮", "新城鄉", "吉安鄉", "壽豐鄉", "光複鄉", "豐濱鄉", "瑞穗鄉", "富里鄉", "秀林鄉", "萬榮鄉", "卓溪鄉"],
    "台東縣": ["台東市", "成功鎮", "關山鎮", "長濱鄉", "海端鄉", "池上鄉", "東河鄉", "鹿野鄉", "延平鄉", "卑南鄉", "太麻里鄉", "大武鄉", "綠島鄉", "蘭嶼鄉", "金峰鄉", "達仁鄉"],
    "澎湖縣": ["馬公市", "湖西鄉", "白沙鄉", "西嶼鄉", "望安鄉", "七美鄉"],
    "金門縣": ["金城鎮", "金沙鎮", "金湖鎮", "金寧鄉", "烈嶼鄉", "烏坵鄉"],
    "連江縣(馬祖)": ["南竿鄉", "北竿鄉", "莒光鄉", "東引鄉"]
}

taiwan_counties = list(taiwan_districts.keys())

grade_options = [
    "1年級(小一)", "2年級(小二)", "3年級(小三)", "4年級(小四)", "5年級(小五)", "6年級(小六)",
    "7年級(國一)", "8年級(國二)", "9年級(國三)", "10年級(高一)", "11年級(高二)", "12年級(高三)"
]

interests_catalog = {
    "流行 IP": ["寶可夢 (Pokémon)", "角落小夥伴", "卡比", "汪汪隊立大功", "迪士尼系列"],
    "動漫": ["鬼滅之刃", "咒術迴戰", "葬送的芙莉蓮", "航海王", "名偵探柯南"],
    "手遊": ["傳說對決", "荒野亂鬥", "Roblox", "崩壞：星穹鐵道", "原神"],
    "益智遊戲": ["魔術方塊", "數獨", "密室逃脫", "樂高積木", "大富翁"],
    "體育運動": ["籃球", "羽球", "桌球", "排球", "躲避球"]
}

if "interest_selections" not in st.session_state:
    st.session_state["interest_selections"] = {k: [] for k in interests_catalog.keys()}

# --- 讀取金鑰 ---
try:
    raw_supa_url = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_URL = raw_supa_url.replace("/rest/v1/", "").replace("/rest/v1", "")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
    GEMINI_KEY = (
        st.secrets.get("GEMINI_API_KEY", "")
        or st.secrets.get("GOOGLE_API_KEY", "")
        or st.secrets.get("GEMINI_KEY", "")
    )
    SMTP_USER = st.secrets.get("SMTP_USER", "")
    SMTP_PASSWORD = (
        st.secrets.get("SMTP_PASSWORD", "")
        or st.secrets.get("SMTP_APP_PASSWORD", "")
    )
    SMTP_HOST = st.secrets.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(st.secrets.get("SMTP_PORT", 465))
    ADMIN_PASSWORD = str(st.secrets.get("MATHAI_ADMIN_PASSWORD", ""))
except Exception:
    SUPABASE_URL = ""
    SUPABASE_KEY = ""
    GEMINI_KEY = ""
    SMTP_USER = ""
    SMTP_PASSWORD = ""
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465
    ADMIN_PASSWORD = ""

# 安全原則：金鑰只從 .streamlit/secrets.toml 讀取。
# 若缺少設定，不使用任何寫死的備援金鑰。

@st.cache_resource
def init_supabase(url, key):
    if not SUPABASE_AVAILABLE or not url or not key: return None
    try:
        return create_client(url, key)
    except Exception:
        return None

supabase_client = init_supabase(SUPABASE_URL, SUPABASE_KEY)


def get_private_beta_auth_client(create_if_missing=True):
    """Return a per-Streamlit-session Auth client; never use the cached anon client."""
    client = st.session_state.get("private_beta_auth_client")
    if client is not None or not create_if_missing:
        return client
    if not SUPABASE_AVAILABLE or not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None
    st.session_state["private_beta_auth_client"] = client
    return client


def _authenticated_account_client():
    """Use only the signed-in per-session client for profile and wallet RPCs."""
    if not st.session_state.get("private_beta_auth_user_id"):
        return None
    if not st.session_state.get("private_beta_student_id"):
        return None
    return get_private_beta_auth_client(create_if_missing=False)


def current_learning_runtime():
    """Compose persistence once from the current authenticated client and ownership."""
    client = get_private_beta_auth_client(create_if_missing=False)
    return build_learning_runtime(st.session_state, client)


def clear_private_beta_auth_session():
    client = st.session_state.get("private_beta_auth_client")
    clear_authenticated_session(st.session_state, client)


def apply_private_beta_identity(email, student_id, auth_user_id):
    """Load legacy profile metadata while keeping UUID ownership authoritative."""
    verified_email = normalize_email(email)
    st.session_state["private_beta_auth_user_id"] = auth_user_id
    st.session_state["private_beta_student_id"] = student_id
    clear_profile_widget_state(verified_email)
    db_profile = build_complete_user_profile(verified_email)
    if db_profile:
        apply_user_profile_to_session(db_profile, verified_email)
        st.session_state["profile_load_notice"] = "existing"
        st.session_state["is_new_account_registration"] = False
    else:
        reset_user_profile_for_new_account(verified_email, credits=200)
        st.session_state["profile_load_notice"] = "new"
        st.session_state["is_new_account_registration"] = True
    st.session_state["user_profile"]["id"] = student_id
    st.session_state["developer_mode"] = False
    st.session_state["is_trial"] = False
    st.session_state["wallet_synced_email"] = ""
    st.session_state["is_verified"] = True
    st.session_state["private_beta_otp_sent"] = False
    save_recent_email(verified_email)


def render_private_beta_auth_login():
    """Render the Private Beta Supabase Auth OTP flow without exposing tokens."""
    with st.expander("Private Beta 安全登入（Supabase Auth OTP）", expanded=True):
        st.caption(
            "此登入會建立 Supabase Auth session，並透過 student_access 取得正式 student_id。"
        )
        email = st.text_input(
            "Private Beta Email",
            value=st.session_state.get("private_beta_auth_email", ""),
            key="private_beta_email_input",
        ).strip()
        if st.button(
            "寄送 Supabase 登入驗證信",
            key="private_beta_send_otp",
            use_container_width=True,
        ):
            client = get_private_beta_auth_client()
            try:
                normalized = request_email_otp(client, email)
                st.session_state["private_beta_auth_email"] = normalized
                st.session_state["private_beta_otp_sent"] = True
                st.success("驗證信已寄出；請輸入信中的一次性驗證碼。")
            except AuthFlowError:
                st.error("驗證信目前無法寄出；請確認 Email 格式與 Private Beta 資格後再試。")

        if st.session_state.get("private_beta_otp_sent"):
            with st.form("private_beta_verify_otp_form"):
                otp = st.text_input(
                    "Supabase 一次性驗證碼",
                    type="password",
                    autocomplete="one-time-code",
                )
                verify = st.form_submit_button(
                    "驗證並登入 Private Beta",
                    type="primary",
                    use_container_width=True,
                )
            if verify:
                client = get_private_beta_auth_client()
                try:
                    response = verify_email_otp(
                        client,
                        st.session_state.get("private_beta_auth_email", email),
                        otp,
                    )
                    identity = resolve_authenticated_student(client)
                    apply_private_beta_identity(
                        st.session_state.get("private_beta_auth_email", email),
                        identity.student_id,
                        identity.auth_user_id,
                    )
                    sync_wallet_balance_to_session(
                        st.session_state["user_profile"].get("email", ""),
                        force=True,
                        is_new_account=st.session_state.get(
                            "is_new_account_registration", False
                        ),
                    )
                    st.rerun()
                except (AuthFlowError, LearningIdentityError):
                    st.error("登入驗證失敗；請確認驗證碼與 Private Beta 學生授權後再試。")

# ==========================================
# v0.7.0 資料架構規則
# 1. student_profile_controls = 唯一會員主檔
# 2. member_wallets = 唯一正式點數來源
# 3. referrals / user_activity_events = 推薦與有效使用紀錄
# 4. Session State 只做畫面鏡像，不能反向覆蓋雲端資料
# 5. user_profiles 與本機 profile JSON 僅視為舊資料／離線開發備援
# ==========================================

def normalize_email(email):
    return str(email or "").strip().lower()


def is_local_developer_session(email=None):
    """只有 developer@local.test 才能視為開發者模式。

    避免曾經按過本機快速登入後，developer_mode=True 殘留到一般會員，
    導致正式會員跳過 Supabase wallet。
    """
    current_email = normalize_email(
        email
        if email is not None
        else st.session_state.get("user_profile", {}).get("email", "")
    )
    return (
        st.session_state.get("developer_mode", False)
        and current_email == "developer@local.test"
    )


def normalize_profile_list(value):
    return _profile_list_value(value)


def normalize_city_name(value):
    city = str(value or "").strip()
    city_aliases = {
        "臺北市": "台北市",
        "臺中市": "台中市",
        "臺南市": "台南市",
        "臺東縣": "台東縣",
    }
    return city_aliases.get(city, city)


def normalize_grade_name(value):
    text = str(value or "").strip()
    if text in grade_options:
        return text
    match = re.search(r"(\d+)", text)
    if match:
        grade_number = int(match.group(1))
        for option in grade_options:
            if option.startswith(f"{grade_number}年級"):
                return option
    return "8年級(國二)"


def normalize_version_name(value, grade_value=""):
    text = str(value or "").strip()
    aliases = {
        "康軒": "康軒版",
        "翰林": "翰林版",
        "南一": "南一版",
        "數學A": "A級 (數學A)",
        "A級": "A級 (數學A)",
        "數學B": "B級 (數學B)",
        "B級": "B級 (數學B)",
        "數學C": "C級 (數學C)",
        "C級": "C級 (數學C)",
        "奧數": "參加數學競賽",
        "數學競賽": "參加數學競賽",
        "奧林匹克數學": "參加數學競賽",
    }
    text = aliases.get(text, text)
    is_high_school = any(
        grade_marker in str(grade_value)
        for grade_marker in ["10年級", "11年級", "12年級"]
    )
    valid_versions = (
        [
            "A級 (數學A)",
            "B級 (數學B)",
            "C級 (數學C)",
            "報考私中",
            "參加數學競賽",
        ]
        if is_high_school
        else [
            "康軒版",
            "翰林版",
            "南一版",
            "報考私中",
            "參加數學競賽",
        ]
    )
    return text if text in valid_versions else valid_versions[0]


def fetch_user_profile_from_db(email):
    """相容舊呼叫名稱；v0.7.0 實際讀取 canonical profile RPC。"""
    control = get_profile_control(email)
    if not control.get("_found", False):
        return None
    return control


def build_complete_user_profile(email):
    """會員資料只由 student_profile_controls 組成；點數不在此處理。"""
    normalized_email = normalize_email(email)
    control = get_profile_control(normalized_email)

    has_existing_data = bool(
        control.get("_found")
        or control.get("identity_locked")
        or control.get("locked_last_name")
        or control.get("locked_first_name")
        or control.get("school")
        or control.get("grade")
        or control.get("traits")
        or control.get("interests")
    )
    if not has_existing_data:
        return None

    raw_grade = str(
        control.get("grade") or "8年級(國二)"
    ).strip()
    normalized_grade = normalize_grade_name(raw_grade)

    return {
        "email": normalized_email,
        "last_name": str(
            control.get("locked_last_name") or ""
        ).strip(),
        "first_name": str(
            control.get("locked_first_name") or ""
        ).strip(),
        "city": normalize_city_name(
            control.get("city") or "新北市"
        ),
        "district": str(
            control.get("district") or "土城區"
        ).strip(),
        "school": str(
            control.get("school") or ""
        ).strip(),
        "grade": normalized_grade,
        "version": normalize_version_name(
            control.get("version"),
            normalized_grade,
        ),
        "traits": normalize_profile_list(
            control.get("traits", [])
        ),
        "interests": normalize_profile_list(
            control.get("interests", [])
        ),
        "discovery_source": str(
            control.get("discovery_source") or ""
        ).strip(),
        "source_detail": str(
            control.get("source_detail") or ""
        ).strip(),
        "source_reward_status": str(
            control.get("source_reward_status") or "none"
        ).strip(),
        "last_login_date": today_str,
    }


def apply_user_profile_to_session(profile_data, email=None):
    """Session 只鏡像會員資料；絕不從會員主檔覆蓋點數。"""
    if not isinstance(profile_data, dict):
        return False

    normalized_email = normalize_email(
        email or profile_data.get("email", "")
    )
    city = normalize_city_name(
        profile_data.get("city", "新北市")
    )
    if city not in taiwan_counties:
        city = "新北市"

    district_options = taiwan_districts.get(city, ["全區"])
    district = str(profile_data.get("district") or "").strip()
    if district not in district_options:
        district = district_options[0]

    grade = normalize_grade_name(profile_data.get("grade"))
    version = normalize_version_name(
        profile_data.get("version"),
        grade,
    )

    st.session_state["user_profile"].update({
        "email": normalized_email or "trial@example.com",
        "last_name": str(
            profile_data.get("last_name") or ""
        ).strip(),
        "first_name": str(
            profile_data.get("first_name") or ""
        ).strip(),
        "city": city,
        "district": district,
        "school": str(
            profile_data.get("school") or ""
        ).strip(),
        "grade": grade,
        "version": version,
        "traits": normalize_profile_list(
            profile_data.get("traits", [])
        ),
        "interests": normalize_profile_list(
            profile_data.get("interests", [])
        ),
        "discovery_source": str(
            profile_data.get("discovery_source") or ""
        ).strip(),
        "source_detail": str(
            profile_data.get("source_detail") or ""
        ).strip(),
        "source_reward_status": str(
            profile_data.get("source_reward_status") or "none"
        ).strip(),
        "last_login_date": today_str,
    })
    st.session_state["loaded_profile_email"] = normalized_email
    return True


def clear_profile_widget_state(email):
    normalized_email = normalize_email(email)
    account_key = hashlib.sha256(
        (normalized_email or "new_user").encode("utf-8")
    ).hexdigest()[:10]

    exact_keys = {
        f"profile_last_name_{account_key}",
        f"profile_first_name_{account_key}",
        f"profile_city_{account_key}",
        f"profile_district_{account_key}",
        f"profile_school_{account_key}",
        f"profile_grade_{account_key}",
        f"profile_version_{account_key}",
        f"profile_custom_trait_{account_key}",
        f"profile_custom_interest_{account_key}",
    }
    prefixes = (
        f"profile_trait_{account_key}_",
        f"profile_interest_{account_key}_",
    )

    for state_key in list(st.session_state.keys()):
        if (
            state_key in exact_keys
            or state_key.startswith(prefixes)
        ):
            st.session_state.pop(state_key, None)


def reset_user_profile_for_new_account(
    email="",
    credits=200,
):
    st.session_state["user_profile"] = {
        "last_name": "",
        "first_name": "",
        "email": normalize_email(email)
        or "trial@example.com",
        "city": "新北市",
        "district": "土城區",
        "school": "",
        "grade": "8年級(國二)",
        "version": "康軒版",
        "traits": [],
        "interests": [],
        "credits": credits,
        "discovery_source": "",
        "source_detail": "",
        "source_reward_status": "none",
        "last_login_date": today_str,
    }


def save_user_profile_to_db(profile_data):
    """會員主檔單寫 student_profile_controls；credits 永不從此函式寫入。"""
    if not isinstance(profile_data, dict):
        return False

    email = normalize_email(profile_data.get("email", ""))
    if not email or email == "trial@example.com":
        return False

    grade = normalize_grade_name(profile_data.get("grade"))
    version = normalize_version_name(
        profile_data.get("version"),
        grade,
    )

    control = get_profile_control(email)
    control.update({
        "_found": True,
        "email": email,
        "locked_last_name": str(
            profile_data.get("last_name") or ""
        ).strip(),
        "locked_first_name": str(
            profile_data.get("first_name") or ""
        ).strip(),
        "city": normalize_city_name(
            profile_data.get("city")
        ),
        "district": str(
            profile_data.get("district") or ""
        ).strip(),
        "school": str(
            profile_data.get("school") or ""
        ).strip(),
        "grade": grade,
        "version": version,
        "traits": normalize_profile_list(
            profile_data.get("traits", [])
        ),
        "interests": normalize_profile_list(
            profile_data.get("interests", [])
        ),
        "discovery_source": str(
            profile_data.get("discovery_source") or ""
        ).strip(),
        "source_detail": str(
            profile_data.get("source_detail") or ""
        ).strip(),
        "source_reward_status": str(
            profile_data.get("source_reward_status") or "none"
        ).strip(),
    })
    return save_profile_control(control)



def fetch_relevant_questions_from_db(keywords, limit=20):
    if not supabase_client or not keywords: return ""
    extracted_data = []
    try:
        search_terms = []
        for kw in keywords:
            core_kw = kw.split("：")[-1] if "：" in kw else kw
            search_terms.append(core_kw[:10].strip()) 
            
        for term in search_terms:
            if not term: continue
            res_unit = supabase_client.table("item_bank").select("original_question, new_question, correct_answer").ilike("unit", f"%{term}%").limit(limit).execute()
            if res_unit.data: extracted_data.extend(res_unit.data)
            res_q = supabase_client.table("item_bank").select("original_question, new_question, correct_answer").ilike("new_question", f"%{term}%").limit(limit).execute()
            if res_q.data: extracted_data.extend(res_q.data)

        if not extracted_data: return ""

        unique_questions = []
        seen = set()
        for q in extracted_data:
            q_text = q.get('new_question') or q.get('original_question', '')
            if q_text and q_text not in seen:
                seen.add(q_text)
                unique_questions.append(q)
                
        random.shuffle(unique_questions)
        unique_questions = unique_questions[:limit]

        db_text = ""
        for i, q in enumerate(unique_questions):
            qt = q.get('new_question') or q.get('original_question', '')
            ans = q.get('correct_answer', '')
            db_text += f"[系統現有題庫 {i+1}] 題目: {qt} | 解答: {ans}\n"
        return db_text
    except Exception:
        return ""

def send_otp_email(target_email, otp_code):
    if SMTP_USER and SMTP_PASSWORD:
        try:
            msg = MIMEText(f"您好，\n\n您的驗證碼為：【 {otp_code} 】\n請在 10 分鐘內回到系統輸入此驗證碼以完成綁定。")
            msg["Subject"] = "AI 數學錯題迭代系統 - 帳號登入驗證碼"
            msg["From"] = SMTP_USER
            msg["To"] = target_email
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            return True
        except Exception:
            return True
    else:
        return True

def send_exam_email(target_email, exam_content):
    if not target_email or "@" not in target_email or target_email == "trial@example.com":
        st.warning("⚠️ 請輸入有效的 Email 帳號以使用寄送功能！")
        return False
        
    formatted_html_body = exam_content.replace('\n', '<br>')
    clean_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: "Microsoft JhengHei", sans-serif; line-height: 1.8; color: #333; font-size: 15px; }}
            h2 {{ color: #1c83e1; border-bottom: 2px solid #1c83e1; padding-bottom: 5px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h2>📝 AI 數學專屬試卷與解答</h2>
        <div>{formatted_html_body}</div>
    </body>
    </html>
    """
    
    if SMTP_USER and SMTP_PASSWORD:
        try:
            msg = MIMEText(clean_html, "html", "utf-8")
            msg["Subject"] = "【AI 數學錯題迭代系統】您的專屬考卷與解答"
            msg["From"] = SMTP_USER
            msg["To"] = target_email
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            return True
        except Exception:
            st.error("❌ 郵件寄送失敗，請稍後再試。")
            return False
    else:
        st.warning("⚠️ 系統後台尚未設定 SMTP 郵件發送金鑰！")
        return False

# --- 儲值紀錄輔助函式 ---
def save_topup_request(email, amount, points):
    requests = []
    if os.path.exists(TOPUP_FILE):
        try:
            with open(TOPUP_FILE, "r", encoding="utf-8") as f:
                requests = json.load(f)
        except Exception:
            pass
            
    req_id = str(random.randint(100000, 999999))
    
    if supabase_client:
        try:
            supabase_client.table("topup_requests").insert({
                "id": req_id,
                "user_email": email,
                "amount": amount,
                "points": points,
                "status": "pending",
                "created_at": str(date.today())
            }).execute()
        except Exception:
            pass
            
    requests.append({
        "id": req_id,
        "user_email": email,
        "amount": amount,
        "points": points,
        "status": "pending"
    })
    try:
        with open(TOPUP_FILE, "w", encoding="utf-8") as f:
            json.dump(requests, f, ensure_ascii=False)
    except Exception:
        pass

def get_pending_topups():
    if supabase_client:
        try:
            res = supabase_client.table("topup_requests").select("*").eq("status", "pending").execute()
            if res.data is not None:
                return res.data
        except Exception:
            pass
            
    if os.path.exists(TOPUP_FILE):
        try:
            with open(TOPUP_FILE, "r", encoding="utf-8") as f:
                requests = json.load(f)
                return [r for r in requests if r.get("status") == "pending"]
        except Exception:
            pass
    return []

def approve_topup_request(req_id):
    if supabase_client:
        try:
            supabase_client.table("topup_requests").update({"status": "approved"}).eq("id", req_id).execute()
        except Exception:
            pass
            
    if os.path.exists(TOPUP_FILE):
        try:
            with open(TOPUP_FILE, "r", encoding="utf-8") as f:
                requests = json.load(f)
            for r in requests:
                if str(r.get("id")) == str(req_id):
                    r["status"] = "approved"
            with open(TOPUP_FILE, "w", encoding="utf-8") as f:
                json.dump(requests, f, ensure_ascii=False)
        except Exception:
            pass

def wallet_lookup(email):
    """只讀 Supabase 正式錢包，不使用 Session 猜測餘額。"""
    email = normalize_email(email)
    if (
        not _authenticated_account_client()
        or not email
        or email == "trial@example.com"
        or is_local_developer_session(email)
    ):
        return None

    try:
        result = _authenticated_account_client().rpc(
            "mathai_private_wallet_lookup"
        ).execute()
        rows = result.data or []
        row = rows[0] if isinstance(rows, list) and rows else rows
        if isinstance(row, dict):
            return {
                "found": bool(row.get("found", False)),
                "credits": (
                    int(row["credits"])
                    if row.get("credits") is not None
                    else None
                ),
            }
    except Exception as exc:
        st.session_state["wallet_rpc_debug"] = str(exc)
    return None


def wallet_bootstrap(email, is_new_account=False):
    """由 Supabase 決定首次錢包餘額；Session 不參與初始化。"""
    email = normalize_email(email)
    if (
        not _authenticated_account_client()
        or not email
        or email == "trial@example.com"
        or is_local_developer_session(email)
    ):
        return None

    try:
        result = _authenticated_account_client().rpc(
            "mathai_private_wallet_bootstrap"
        ).execute()
        rows = result.data or []
        row = rows[0] if isinstance(rows, list) and rows else rows
        if not isinstance(row, dict):
            return None

        credits = row.get("credits")
        if credits is None:
            return None

        credits = int(credits)
        st.session_state["user_profile"]["credits"] = credits
        st.session_state["wallet_synced_email"] = email

        return credits
    except Exception as exc:
        st.session_state["wallet_rpc_debug"] = str(exc)
        return None


def wallet_adjust(
    email,
    delta,
    reason="manual_adjustment",
    reference_type="",
    reference_id="",
):
    """正式點數異動只走 member_wallets RPC。"""
    email = normalize_email(email)
    delta = int(delta or 0)
    if (
        not _authenticated_account_client()
        or not email
        or email == "trial@example.com"
        or delta >= 0
        or is_local_developer_session(email)
    ):
        return False, None, "無法處理點數異動。"

    try:
        result = _authenticated_account_client().rpc(
            "mathai_private_wallet_debit",
            {
                "p_amount": -delta,
                "p_reason": str(reason or "ai_usage_charge"),
                "p_reference_id": str(reference_id or ""),
            },
        ).execute()
        rows = result.data or []
        row = rows[0] if isinstance(rows, list) and rows else rows
        if isinstance(row, dict):
            success = bool(row.get("success", False))
            balance = row.get("new_balance")
            message = "" if success else "點數不足或請求已拒絕。"
            if balance is not None:
                balance = int(balance)
                if (
                    normalize_email(
                        st.session_state["user_profile"].get("email", "")
                    ) == email
                ):
                    st.session_state["user_profile"]["credits"] = balance
            return success, balance, message
    except Exception as exc:
        st.session_state["wallet_rpc_debug"] = str(exc)

    return False, None, "點數服務暫時無法使用。"


def sync_wallet_balance_to_session(
    email=None,
    force=False,
    is_new_account=None,
):
    """把 Supabase wallet 鏡像到 Session；雲端永遠優先。"""
    email = normalize_email(
        email or st.session_state["user_profile"].get("email", "")
    )
    if (
        not email
        or email == "trial@example.com"
        or is_local_developer_session(email)
    ):
        return st.session_state["user_profile"].get("credits")

    if (
        not force
        and st.session_state.get("wallet_synced_email") == email
    ):
        return st.session_state["user_profile"].get("credits")

    lookup = wallet_lookup(email)
    if lookup and lookup.get("found"):
        cloud_credits = int(lookup.get("credits") or 0)
        st.session_state["user_profile"]["credits"] = cloud_credits
        st.session_state["wallet_synced_email"] = email
        return cloud_credits

    if is_new_account is None:
        is_new_account = bool(
            st.session_state.get("is_new_account_registration", False)
        )

    return wallet_bootstrap(
        email,
        is_new_account=is_new_account,
    )


def add_user_credits(
    email,
    points,
    reason="manual_adjustment",
    reference_type="",
    reference_id="",
):
    success, _, _ = wallet_adjust(
        email,
        int(points or 0),
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id or str(uuid.uuid4()),
    )
    return success



def _table_first(table_name, filters=None, columns="*"):
    if not supabase_client:
        return None
    try:
        query = supabase_client.table(table_name).select(columns)
        for operator, field, value in filters or []:
            if operator == "eq":
                query = query.eq(field, value)
            elif operator == "ilike":
                query = query.ilike(field, value)
        result = query.limit(1).execute()
        if result.data:
            return result.data[0]
    except Exception:
        pass
    return None


def _effective_usage_count(email, limit=3):
    email = normalize_email(email)
    if not supabase_client or not email:
        return 0

    try:
        result = (
            supabase_client.table("user_activity_events")
            .select("id")
            .ilike("user_email", email)
            .limit(limit)
            .execute()
        )
        count = len(result.data or [])
        if count:
            return count
    except Exception:
        pass

    # 舊會員尚未建立事件紀錄時，以已存入的題目作為使用證明。
    try:
        result = (
            supabase_client.table("item_bank")
            .select("id")
            .ilike("user_id", email)
            .limit(limit)
            .execute()
        )
        return len(result.data or [])
    except Exception:
        return 0


def _has_approved_topup(email):
    email = normalize_email(email)
    if not supabase_client or not email:
        return False
    return bool(
        _table_first(
            "topup_requests",
            [
                ("ilike", "user_email", email),
                ("eq", "status", "approved"),
            ],
            "id",
        )
    )


def get_referrer_status_rpc(email):
    """只取推薦資格狀態，不暴露 student_profile_controls 的個資欄位。"""
    email = normalize_email(email)
    if not supabase_client or not email:
        return None
    try:
        result = supabase_client.rpc(
            "mathai_referrer_status_v070",
            {"p_email": email},
        ).execute()
        rows = result.data or []
        if isinstance(rows, list) and rows:
            return rows[0]
        if isinstance(rows, dict):
            return rows
    except Exception as exc:
        st.session_state["referrer_rpc_debug"] = str(exc)
    return None


def validate_referrer(referrer_email, referred_email):
    referrer_email = normalize_email(referrer_email)
    referred_email = normalize_email(referred_email)

    if not referrer_email or "@" not in referrer_email:
        return False, "請輸入正確的介紹人 Email。"
    if referrer_email == referred_email:
        return False, "不能填寫自己的 Email 作為介紹人。"

    # 優先使用 SECURITY DEFINER RPC。
    # student_profile_controls 開啟 RLS 時，匿名 App 不能直接 select；
    # RPC 只回傳資格狀態，既能正確判斷又不暴露會員個資。
    rpc_status = get_referrer_status_rpc(referrer_email)
    if rpc_status is not None:
        found = bool(rpc_status.get("found", False))
        override_eligible = bool(
            rpc_status.get("override_eligible", False)
        )
        profile_complete = bool(
            rpc_status.get("profile_complete", False)
        )
        effective_use_count = int(
            rpc_status.get("effective_use_count") or 0
        )
        has_approved_topup = bool(
            rpc_status.get("has_approved_topup", False)
        )
        eligible = bool(rpc_status.get("eligible", False))

        if override_eligible:
            return True, "介紹人資格確認成功（管理員指定合格推薦人）。"
        if not found:
            return False, "資料庫中找不到這位介紹人的會員帳號。"
        if not profile_complete:
            return False, "已找到此會員，但介紹人尚未完成學生基本資料。"
        if eligible:
            if has_approved_topup:
                return True, "介紹人資格確認成功（已有儲值紀錄）。"
            return (
                True,
                f"介紹人資格確認成功（已有 {effective_use_count} 次有效使用）。",
            )
        return (
            False,
            "已找到此會員，但目前只有 "
            f"{effective_use_count}/3 次有效使用，且尚無已核准儲值紀錄。",
        )

    # RPC 尚未建立時保留舊版 fallback，方便 localhost 測試。
    raw_profile = fetch_user_profile_from_db(referrer_email) or {}
    control = get_profile_control(referrer_email)
    complete_profile = build_complete_user_profile(referrer_email)

    control_has_account = bool(
        control.get("identity_locked")
        or str(control.get("locked_last_name") or "").strip()
        or str(control.get("locked_first_name") or "").strip()
        or str(control.get("grade") or "").strip()
        or str(control.get("version") or "").strip()
        or control.get("referral_eligible_override")
    )

    if not raw_profile and not control_has_account and not complete_profile:
        return False, "資料庫中找不到這位介紹人的會員帳號。"

    if bool(control.get("referral_eligible_override", False)):
        return True, "介紹人資格確認成功（管理員指定合格推薦人）。"

    merged = complete_profile or {}
    has_basic_profile = bool(
        str(merged.get("last_name") or "").strip()
        and str(merged.get("first_name") or "").strip()
        and str(merged.get("school") or "").strip()
    )
    if not has_basic_profile:
        return False, "已找到此會員，但介紹人尚未完成學生基本資料。"

    usage_count = _effective_usage_count(referrer_email, limit=3)
    has_topup = _has_approved_topup(referrer_email)
    if has_topup or usage_count >= 3:
        return True, "介紹人資格確認成功。"

    return (
        False,
        f"已找到此會員，但目前只有 {usage_count}/3 次有效使用，"
        "且尚無已核准儲值紀錄。",
    )



def get_registration_source_claim_status(user_email):
    """安全查詢此會員是否已經成功占用來源獎勵資格。"""
    user_email = normalize_email(user_email)
    if not supabase_client or not user_email:
        return {
            "has_claim": False,
            "claim_type": "",
            "claim_status": "",
        }

    try:
        result = supabase_client.rpc(
            "mathai_source_claim_status",
            {"p_email": user_email},
        ).execute()
        rows = result.data or []
        if isinstance(rows, list) and rows:
            return rows[0]
        if isinstance(rows, dict):
            return rows
    except Exception as exc:
        st.session_state["source_claim_rpc_debug"] = str(exc)

    # RPC 尚未建立時使用舊版 fallback。
    # RLS 可能讓 fallback 看不到資料，所以只作相容用途。
    for referral_status in (
        "pending",
        "processing",
        "awarded",
        "monthly_limit",
    ):
        if _table_first(
            "referrals",
            [
                ("ilike", "referred_email", user_email),
                ("eq", "status", referral_status),
            ],
            "id",
        ):
            return {
                "has_claim": True,
                "claim_type": "referral",
                "claim_status": referral_status,
            }

    if _table_first(
        "promo_redemptions",
        [("ilike", "user_email", user_email)],
        "id",
    ):
        return {
            "has_claim": True,
            "claim_type": "promo",
            "claim_status": "awarded",
        }

    for acquisition_status in ("pending", "approved", "awarded"):
        if _table_first(
            "acquisition_claims",
            [
                ("ilike", "user_email", user_email),
                ("eq", "status", acquisition_status),
            ],
            "id",
        ):
            return {
                "has_claim": True,
                "claim_type": "acquisition",
                "claim_status": acquisition_status,
            }

    return {
        "has_claim": False,
        "claim_type": "",
        "claim_status": "",
    }


def has_registration_source_claim(user_email):
    status = get_registration_source_claim_status(user_email)
    return bool(status.get("has_claim", False))



def save_source_retry_state(
    user_email,
    source_type,
    source_detail,
    status="retry_allowed",
):
    """透過 RPC 保存失敗推薦／優惠資料，跨登入與跨裝置仍可重填。"""
    user_email = normalize_email(user_email)
    if not supabase_client or not user_email:
        return False
    try:
        result = supabase_client.rpc(
            "mathai_save_source_retry",
            {
                "p_email": user_email,
                "p_source_type": str(source_type or "").strip(),
                "p_source_detail": str(source_detail or "").strip(),
                "p_status": str(status or "retry_allowed").strip(),
            },
        ).execute()
        return bool(result.data)
    except Exception as exc:
        st.session_state["source_retry_rpc_debug"] = str(exc)
        return False


def load_source_retry_state(user_email):
    """讀取跨登入保存的失敗推薦／優惠資料。"""
    user_email = normalize_email(user_email)
    if not supabase_client or not user_email:
        return None
    try:
        result = supabase_client.rpc(
            "mathai_get_source_retry",
            {"p_email": user_email},
        ).execute()
        rows = result.data or []
        if isinstance(rows, list) and rows:
            return rows[0]
        if isinstance(rows, dict):
            return rows
    except Exception as exc:
        st.session_state["source_retry_rpc_debug"] = str(exc)
    return None


def clear_source_retry_state(user_email):
    """推薦／優惠成功或主動放棄後，清除重填旗標。"""
    user_email = normalize_email(user_email)
    if not supabase_client or not user_email:
        return False
    try:
        result = supabase_client.rpc(
            "mathai_clear_source_retry",
            {"p_email": user_email},
        ).execute()
        return bool(result.data)
    except Exception as exc:
        st.session_state["source_retry_rpc_debug"] = str(exc)
        return False


def restore_retry_state_to_session():
    """登入後自動恢復尚未完成的推薦／優惠重填狀態。"""
    user_email = normalize_email(
        st.session_state["user_profile"].get("email", "")
    )
    if not user_email or user_email == "trial@example.com":
        return False

    retry_state = load_source_retry_state(user_email)
    if not retry_state:
        return False

    status = str(retry_state.get("status") or "").strip()
    if status != "retry_allowed":
        return False

    st.session_state["user_profile"]["source_reward_status"] = "retry_allowed"
    st.session_state["user_profile"]["discovery_source"] = str(
        retry_state.get("source_type") or "親友／老師介紹"
    ).strip()
    st.session_state["user_profile"]["source_detail"] = str(
        retry_state.get("source_detail") or ""
    ).strip()
    return True



def validate_promo_code(code):
    normalized_code = str(code or "").strip().upper()
    if not normalized_code:
        return False, None, "請輸入優惠碼。"

    promo = _table_first(
        "promo_codes",
        [
            ("eq", "code", normalized_code),
            ("eq", "active", True),
        ],
        "*",
    )
    if not promo:
        return False, None, "找不到有效的優惠碼。"

    expires_at = promo.get("expires_at")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(
                str(expires_at).replace("Z", "+00:00")
            )
            now = datetime.now(expiry.tzinfo) if expiry.tzinfo else datetime.now()
            if expiry < now:
                return False, promo, "這組優惠碼已經過期。"
        except Exception:
            pass

    max_uses = int(promo.get("max_uses") or 0)
    usage_count = int(promo.get("usage_count") or 0)
    if max_uses > 0 and usage_count >= max_uses:
        return False, promo, "這組優惠碼已達使用次數上限。"

    return True, promo, "優惠碼驗證成功。"


def create_pending_referral_rpc(
    referrer_email,
    referred_email,
):
    """建立推薦後再次查 DB 驗證，避免出現「假成功」訊息。"""
    referrer_email = normalize_email(referrer_email)
    referred_email = normalize_email(referred_email)

    if not supabase_client:
        return False, "目前未連接會員資料庫。"

    try:
        result = supabase_client.rpc(
            "mathai_create_referral_v070",
            {
                "p_referrer_email": referrer_email,
                "p_referred_email": referred_email,
            },
        ).execute()
        rows = result.data or []
        row = rows[0] if isinstance(rows, list) and rows else rows

        rpc_success = (
            isinstance(row, dict)
            and row.get("success") is True
        )
        rpc_message = (
            str(row.get("message") or "")
            if isinstance(row, dict)
            else ""
        )

        if not rpc_success:
            return False, rpc_message or "推薦紀錄建立失敗。"

        verify_result = supabase_client.rpc(
            "mathai_referral_status_v070",
            {"p_email": referred_email},
        ).execute()
        verify_rows = verify_result.data or []
        verify_row = (
            verify_rows[0]
            if isinstance(verify_rows, list) and verify_rows
            else verify_rows
        )
        if (
            isinstance(verify_row, dict)
            and verify_row.get("found") is True
            and str(verify_row.get("status") or "") == "pending"
            and normalize_email(
                verify_row.get("referrer_email", "")
            ) == referrer_email
        ):
            return True, "推薦關係已登記成功。完成第一次有效出題或錯題解析後，雙方各得 50 點。"

        st.session_state["referral_save_debug"] = (
            "RPC 回報成功，但重新查詢後沒有找到 pending 推薦紀錄。"
        )
        return False, "推薦資料未真正寫入雲端，請聯絡管理員。"

    except Exception as exc:
        st.session_state["referral_save_debug"] = str(exc)

    return False, "推薦紀錄暫時無法儲存，請聯絡管理員。"



def record_effective_usage_and_referral_rpc(
    user_email,
    event_type,
):
    """記錄有效使用，並由資料庫完成推薦雙方 +50 點。"""
    user_email = normalize_email(user_email)
    if (
        not supabase_client
        or not user_email
        or user_email == "trial@example.com"
        or is_local_developer_session(user_email)
    ):
        return False

    sync_wallet_balance_to_session(user_email)

    try:
        result = supabase_client.rpc(
            "mathai_record_use_and_award_referral_v070",
            {
                "p_email": user_email,
                "p_event_type": str(event_type or "ai_use"),
            },
        ).execute()
        rows = result.data or []
        row = rows[0] if isinstance(rows, list) and rows else rows
        if not isinstance(row, dict):
            return False

        new_credits = row.get("user_credits")
        if new_credits is not None:
            st.session_state["user_profile"]["credits"] = int(new_credits)

        if bool(row.get("referral_awarded", False)):
            referrer_now = bool(
                row.get("referrer_reward_applied", False)
            )
            if referrer_now:
                reward_text = "🎁 推薦成功：您與介紹人已各獲得 50 點。"
            else:
                reward_text = (
                    "🎁 推薦成功：您已獲得 50 點；介紹人的 50 點已保留，"
                    "會在介紹人下次登入時自動補入。"
                )
            st.session_state["registration_source_result"] = (
                "success|" + reward_text
            )
            st.session_state["user_profile"][
                "source_reward_status"
            ] = "awarded"
            st.session_state["wallet_last_message"] = (
                "🎁 推薦成功，雙方各增加 50 點。"
            )
            request_page_top()

        return bool(row.get("event_recorded", False))
    except Exception as exc:
        st.session_state["referral_award_debug"] = str(exc)
        st.session_state["wallet_last_message"] = (
            "試卷已完成，但推薦點數同步失敗，請聯絡管理員。"
        )
        return False



def process_registration_source(
    user_email,
    source_type,
    source_value="",
    source_detail="",
):
    user_email = normalize_email(user_email)
    source_type = str(source_type or "").strip()
    source_value = str(source_value or "").strip()
    source_detail = str(source_detail or "").strip()

    if not user_email or user_email == "trial@example.com":
        return "error", "請先完成 Email 驗證。"
    if not supabase_client:
        return "error", "目前未連接會員資料庫，暫時無法申請來源獎勵。"
    if has_registration_source_claim(user_email):
        return "info", "這個帳號已登記過來源獎勵，不能重複申請。"

    now_text = datetime.now().isoformat()

    if source_type == "親友／老師介紹":
        referrer_email = normalize_email(source_value)
        valid, message = validate_referrer(
            referrer_email,
            user_email,
        )

        # 無效／不存在的介紹人不建立 referrals 紀錄。
        # 使用者仍可完成註冊，只是不發放推薦點數。
        if not valid:
            return (
                "warning",
                f"{message} 本次不會發放推薦點數，但仍可正常完成註冊。",
            )

        referral_saved, referral_message = create_pending_referral_rpc(
            referrer_email,
            user_email,
        )
        if not referral_saved:
            return (
                "error",
                referral_message
                or (
                    "介紹人資格已確認，但推薦紀錄暫時無法儲存。"
                    "本次不會發放推薦點數，請聯絡管理員。"
                ),
            )

        return (
            "success",
            "✅ 推薦關係已登記成功。完成第一次有效出題或錯題解析後，"
            "您與介紹人將各獲得 50 點。",
        )

    if source_type == "MathAI 活動／優惠碼":
        valid, promo, message = validate_promo_code(source_value)
        if not valid:
            return "warning", f"{message} 本次不會發放優惠點數，但仍可註冊。"

        code = str(promo.get("code") or "").upper()
        points = int(promo.get("points") or 50)
        try:
            supabase_client.table("promo_redemptions").insert({
                "code": code,
                "user_email": user_email,
                "points": points,
                "status": "awarded",
                "created_at": now_text,
            }).execute()
            supabase_client.table("promo_codes").update({
                "usage_count": int(promo.get("usage_count") or 0) + 1,
                "updated_at": now_text,
            }).eq("code", code).execute()
        except Exception:
            return "warning", "此帳號可能已使用過優惠碼，無法重複領取。"

        if add_user_credits(
            user_email,
            points,
            reason="promo_code_reward",
            reference_type="promo_code",
            reference_id=code,
        ):
            return "success", f"優惠碼審核成功，已贈送 {points} 點。"
        return "error", "優惠碼已登記，但點數發放失敗，請聯絡管理員。"

    if source_type == "其他通路（審核後贈送 50 點）":
        if not source_detail:
            return "warning", "請填寫您從哪個通路知道 MathAI。"
        try:
            supabase_client.table("acquisition_claims").insert({
                "user_email": user_email,
                "source_type": source_type,
                "source_detail": source_detail,
                "status": "pending",
                "reward_points": 50,
                "created_at": now_text,
            }).execute()
            return (
                "success",
                "其他通路資料已送出。管理員審核成功後，將贈送 50 點。",
            )
        except Exception:
            return "error", "通路資料無法送出，請確認 SQL 已執行。"

    return "info", "已記錄您得知 MathAI 的方式；本選項不申請額外點數。"


def record_effective_usage(user_email, event_type):
    """有效使用與推薦紀錄屬於後處理；失敗時不可讓主功能崩潰。"""
    try:
        return record_effective_usage_and_referral_rpc(
            user_email,
            event_type,
        )
    except Exception as exc:
        st.session_state["referral_award_debug"] = str(exc)
        return False



def get_pending_acquisition_claims():
    if not supabase_client:
        return []
    try:
        result = (
            supabase_client.table("acquisition_claims")
            .select("*")
            .eq("status", "pending")
            .order("created_at")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def approve_acquisition_claim(claim):
    if not supabase_client or not claim:
        return False
    claim_id = claim.get("id")
    user_email = normalize_email(claim.get("user_email"))
    points = int(claim.get("reward_points") or 50)

    if not add_user_credits(
        user_email,
        points,
        reason="acquisition_channel_reward",
        reference_type="acquisition_claim",
        reference_id=str(claim_id or ""),
    ):
        return False
    try:
        supabase_client.table("acquisition_claims").update({
            "status": "awarded",
            "reviewed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }).eq("id", claim_id).execute()
        return True
    except Exception:
        return False


def create_or_update_promo_code(
    code,
    points=50,
    max_uses=0,
    expires_at=None,
):
    code = str(code or "").strip().upper()
    if not supabase_client or not code:
        return False
    try:
        supabase_client.table("promo_codes").upsert({
            "code": code,
            "points": int(points or 50),
            "active": True,
            "max_uses": int(max_uses or 0),
            "expires_at": (
                datetime.combine(
                    expires_at,
                    datetime.max.time().replace(microsecond=0),
                ).isoformat()
                if isinstance(expires_at, date)
                and not isinstance(expires_at, datetime)
                else (
                    expires_at.isoformat()
                    if hasattr(expires_at, "isoformat")
                    else expires_at
                )
            ),
            "updated_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception:
        return False


def get_required_credits(q_count):
    if q_count <= 5: return 15
    elif q_count <= 10: return 28
    elif q_count <= 15: return 40
    else: return 50

def deduct_credit(q_count=5):
    req_credits = get_required_credits(q_count)
    email = normalize_email(
        st.session_state["user_profile"].get("email", "")
    )

    if email == "trial@example.com" or is_local_developer_session(email):
        if st.session_state["user_profile"].get("credits", 0) >= req_credits:
            st.session_state["user_profile"]["credits"] -= req_credits
            return True
        return False

    sync_wallet_balance_to_session(email)
    current_credits = int(
        st.session_state["user_profile"].get("credits", 0) or 0
    )
    if current_credits < req_credits:
        return False

    success, balance, message = wallet_adjust(
        email,
        -req_credits,
        reason="ai_usage_charge",
        reference_type="exam_charge",
        reference_id=str(uuid.uuid4()),
    )
    if not success:
        st.session_state["wallet_last_message"] = (
            message or "點數扣除失敗。"
        )
        return False

    if balance is not None:
        st.session_state["user_profile"]["credits"] = balance
    return True



def handle_api_error(exc: Exception) -> None:
    """顯示一般使用者可理解的 AI 錯誤；完整技術資訊僅供管理員查看。"""
    error_code = get_ai_error_code(exc)
    st.error(f"⚠️ {get_ai_error_message(exc)}")

    if error_code in {
        "MISSING_API_KEY",
        "AUTHENTICATION_FAILED",
        "PERMISSION_DENIED",
    }:
        st.info(
            "管理員請到 Streamlit Cloud → App settings → Secrets，"
            "確認已設定有效的 GEMINI_API_KEY 或 GOOGLE_API_KEY。"
            "本次產生失敗不會扣點。"
        )

    if st.session_state.get("admin_unlocked", False):
        with st.expander("管理員技術資訊"):
            st.code(get_ai_debug_message(exc))

# ==========================================
# 🌟 全域左側欄 (Sidebar) 核心邏輯 - 直接展開、保證不消失
# ==========================================
# v0.7.0：側欄只顯示 Supabase member_wallets 的鏡像點數。
_sidebar_email_for_wallet = normalize_email(
    st.session_state.get("user_profile", {}).get("email", "")
)
if (
    st.session_state.get("is_verified", False)
    and _sidebar_email_for_wallet
    and _sidebar_email_for_wallet != "trial@example.com"
):
    sync_wallet_balance_to_session(
        _sidebar_email_for_wallet,
        force=True,
    )

with st.sidebar:
    st.caption("📱 儲值點數與問題回饋")
    sidebar_credits = st.session_state["user_profile"].get("credits", 30)
    sidebar_email = st.session_state["user_profile"].get("email", "")
    sidebar_logged_in = bool(sidebar_email and sidebar_email != "trial@example.com")
    login_label = "已登入" if sidebar_logged_in else "未登入"
    display_sidebar_email = sidebar_email if sidebar_logged_in else "尚未登入"

    st.markdown(
        f"""
        <div style="font-size:.74rem;line-height:1.20;margin:0 0 .42rem 0;">
            <div><b>{sidebar_credits} 點｜{login_label}</b>　<span style="opacity:.65;">{APP_VERSION}</span></div>
            <div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
                 title="{display_sidebar_email}">👤 {display_sidebar_email}</div>
            <div style="margin-top:.12rem;margin-bottom:.22rem;">💬 <a href="https://line.me/ti/p/a6B_R1wmyL" target="_blank"
                 style="font-weight:700;text-decoration:none;">加入 LINE</a></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("💳 儲值點數", expanded=False):
        st.caption("儲值 1 點為新臺幣 1 元")
        st.markdown("💰 **選擇儲值方案：**")
        topup_plan = st.selectbox("請選擇方案", [
            "儲值 100 元 (給 100 點)", 
            "儲值 299 元 (給 350 點)", 
            "儲值 599 元 (給 800 點)"
        ], label_visibility="collapsed")
    
        st.markdown("**支援轉帳方式 (可 QR Code 掃描)：**")
        pay_tabs = st.tabs(["🏦 銀行", "🟢 LINE Pay", "🔴 街口", "🔵 臺灣 Pay"])
    
        for pt in pay_tabs:
            with pt:
                st.markdown("🔹 **收款帳戶資訊**\n- 戶名：**陳冠麟**\n- 帳號：**郵局代碼 700，郵局帳號 00210570283172**")
        with pay_tabs[1]:
            st.markdown("#### 🟢 LINE Pay 收款碼")
            if LINE_PAY_QR_FILE.exists():
                st.image(
                    str(LINE_PAY_QR_FILE),
                    caption="請使用 LINE Pay 掃描付款，付款後再按下方按鈕通知管理員。",
                    use_container_width=True,
                )
            else:
                st.warning("找不到 LINE Pay 收款碼圖片，請確認 line_pay_qr.jpg 已放在 app 資料夾。")
        with pay_tabs[2]:
            st.info("💡 提示：若有街口條碼，可於此替換圖片。")
        with pay_tabs[3]:
            st.info("💡 提示：若有臺灣 Pay 條碼，可於此替換圖片。")
        
        if st.button("🔔 轉帳完畢，通知管理員開通點數", use_container_width=True):
            amt_match = re.search(r'儲值 (\d+) 元', topup_plan)
            pts_match = re.search(r'給 (\d+) 點', topup_plan)
            amount = int(amt_match.group(1)) if amt_match else 0
            points = int(pts_match.group(1)) if pts_match else 0
        
            save_topup_request(st.session_state['user_profile'].get('email'), amount, points)
        
            if SMTP_USER and SMTP_PASSWORD:
                try:
                    admin_msg = MIMEText(f"用戶 Email: {st.session_state['user_profile'].get('email')}\n已完成付款動作，請求系統手動核對帳戶並開通點數。\n申請方案: {topup_plan}")
                    admin_msg["Subject"] = "【系統通知】用戶已匯款，請求開通點數"
                    admin_msg["From"] = SMTP_USER
                    admin_msg["To"] = SMTP_USER
                    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                        server.login(SMTP_USER, SMTP_PASSWORD)
                        server.send_message(admin_msg)
                except Exception:
                    pass
            st.success("✅ 已成功發送通知！將根據您儲值的金額為您手動派發點數，請稍候。")

        st.markdown(
            "<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 10px; border-left: 5px solid #ffc107; font-size: 14px;'>"
            "<b>如果一小時內沒有帳號正確存入，請發 email 或是直接 LINE 下面的連結。</b><br><br>"
            "✉️ Email: jason671226@gmail.com<br>"
            "💬 LINE: <a href='https://line.me/ti/p/a6B_R1wmyL' target='_blank'>點擊此處加入 LINE</a>"
            "</div>", unsafe_allow_html=True
        )


    st.markdown("---")
    st.markdown("#### 💬 使用回饋")
    st.markdown(
        """
        <div style="background:#fff3cd;border-left:4px solid #f0ad4e;
        border-radius:5px;padding:4px 5px;margin:1px 0 4px 0;
        font-size:.72rem;font-weight:700;white-space:nowrap;">
        🎁 回饋一次送 20 點，最高 100 點
        </div>
        """,
        unsafe_allow_html=True,
    )
    feedback_text = ""
    render_beta_feedback(
        st,
        auth_client=_authenticated_account_client(),
        context=str(st.session_state.get("main_tab", "app") or "app"),
    )
    
    if False and st.button("送出回饋", use_container_width=True):
        current_email = st.session_state["user_profile"].get("email", "試用者/未綁定")
        if current_email == "trial@example.com":
            st.warning("請先完成登入綁定，才能領取回饋點數喔！")
        elif not feedback_text.strip():
            st.warning("請先輸入您的建議內容再點擊送出喔！")
        else:
            if st.session_state.get("feedback_today_done", False):
                st.warning("您今天已經填寫過回饋了，請明天再來領取點數！")
            else:
                if supabase_client:
                    try:
                        res = supabase_client.table("user_feedback").select("id").eq("user_email", current_email).execute()
                        past_count = len(res.data) if res.data else 0
                        
                        if past_count >= 5:
                            st.warning("您已達到帳號回饋次數上限 (5次)，非常感謝您的支持！")
                        else:
                            supabase_client.table("user_feedback").insert({"user_email": current_email, "content": feedback_text}).execute()
                            add_user_credits(
                                current_email,
                                20,
                                reason="feedback_reward",
                                reference_type="feedback",
                                reference_id=str(uuid.uuid4()),
                            )
                            st.session_state["feedback_today_done"] = True
                            st.session_state["wallet_last_message"] = (
                                "✅ 感謝回饋！您的寶貴建議已成功傳送，並為您存入 20 點！"
                            )
                    except Exception:
                        st.error("傳送失敗，請稍後再試。")
                    else:
                        if st.session_state.get("feedback_today_done", False):
                            st.rerun()
                else:
                    st.session_state["user_profile"]["credits"] += 20
                    st.session_state["feedback_today_done"] = True
                    st.success("✅ 感謝回饋！(本機測試模式已接收，並贈送 20 點)")
                    st.rerun()
        
    st.markdown("---")
    notice_html = (
        "<div style=\"font-size: 0.90em; line-height: 1.45; background-color: #f0f2f6; padding: 9px; border-radius: 8px; border-left: 5px solid #ff4b4b;\">"
        "<b>本系統為陳冠麟老師獨立開發製作，並擁有完整所有權。</b><br>"
        "目前所需要的開發及維護費用（包含所有贈送點數的模型費用），皆為個人負擔。<br>"
        "所以只先開放部分使用者測試，<b>每組學生 Email 初始提供試用額度</b>。請多多回饋系統使用經驗！"
        "</div>"
    )
    st.markdown(notice_html, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### ⚙️ 後臺管理系統")
    if not st.session_state["admin_unlocked"]:
        admin_pwd = st.text_input("輸入管理員密碼：", type="password", key="admin_pwd_input")
        if st.button("進入後臺管理"):
            if ADMIN_PASSWORD and hmac.compare_digest(admin_pwd, ADMIN_PASSWORD):
                st.session_state["admin_unlocked"] = True
                st.rerun()
            else:
                st.error("密碼錯誤，請重新輸入！")
    else:
        if st.button("登出後臺管理"):
            st.session_state["admin_unlocked"] = False
            st.rerun()
        st.success("歡迎回來！")
        
        st.markdown("#### 💰 儲值審核與管理")
        pending_requests = get_pending_topups()
        
        if not pending_requests:
            st.info("目前沒有待審核的儲值申請。")
        else:
            st.markdown("##### ⏳ 待審核清單")
            selected_req_ids = []
            for req in pending_requests:
                req_id = req.get("id")
                req_email = req.get("user_email")
                req_amt = req.get("amount")
                req_pts = req.get("points")
                if st.checkbox(f"帳號: {req_email} | 存入金額: {req_amt} 元 | 對應點數: {req_pts} 點", key=f"chk_{req_id}"):
                    selected_req_ids.append((req_id, req_email, req_pts))
            
            if st.button("✅ 儲值 (開通勾選的點數)", type="primary"):
                for req_id, req_email, req_pts in selected_req_ids:
                    add_user_credits(req_email, req_pts)
                    approve_topup_request(req_id)
                st.success("儲值開通成功！")
                st.rerun()

        st.markdown("##### ✍️ 手動派發點數")
        col_man1, col_man2 = st.columns(2)
        with col_man1:
            manual_email = st.text_input("用戶 Email：")
        with col_man2:
            manual_points = st.number_input("派發點數：", min_value=0, step=10)
            
        if st.button("⚡ 手動儲值"):
            if manual_email and manual_points > 0:
                add_user_credits(
                    manual_email,
                    manual_points,
                    reason="admin_manual_credit",
                )
                st.success(f"成功為 {manual_email} 加入 {manual_points} 點！")
                st.rerun()
            else:
                st.warning("請填寫正確的 Email 與大於 0 的點數。")

        st.markdown("#### 🎁 其他通路獎勵審核")
        pending_source_claims = get_pending_acquisition_claims()
        if not pending_source_claims:
            st.info("目前沒有待審核的其他通路獎勵。")
        else:
            selected_source_claims = []
            for claim in pending_source_claims:
                claim_id = claim.get("id")
                claim_email = claim.get("user_email", "")
                claim_detail = claim.get("source_detail", "")
                claim_points = int(
                    claim.get("reward_points") or 50
                )
                if st.checkbox(
                    f"{claim_email}｜{claim_detail}｜{claim_points} 點",
                    key=f"source_claim_{claim_id}",
                ):
                    selected_source_claims.append(claim)

            if st.button(
                "✅ 審核通過並發放勾選點數",
                type="primary",
                key="approve_source_claims",
            ):
                success_count = 0
                for claim in selected_source_claims:
                    if approve_acquisition_claim(claim):
                        success_count += 1
                st.success(f"已完成 {success_count} 筆通路獎勵。")
                st.rerun()

        st.markdown("#### 🎟️ 優惠碼管理")
        promo_col1, promo_col2, promo_col3 = st.columns(3)
        with promo_col1:
            admin_promo_code = st.text_input(
                "優惠碼",
                placeholder="例如：MATHAI50",
                key="admin_promo_code",
            )
        with promo_col2:
            admin_promo_points = st.number_input(
                "贈送點數",
                min_value=1,
                value=50,
                step=10,
                key="admin_promo_points",
            )
        with promo_col3:
            admin_promo_max_uses = st.number_input(
                "使用上限（0 為不限）",
                min_value=0,
                value=0,
                step=1,
                key="admin_promo_max_uses",
            )
        admin_promo_expiry = st.date_input(
            "到期日",
            value=date.today() + timedelta(days=30),
            key="admin_promo_expiry",
        )
        if st.button("建立／更新優惠碼", key="admin_save_promo"):
            if create_or_update_promo_code(
                admin_promo_code,
                admin_promo_points,
                admin_promo_max_uses,
                admin_promo_expiry,
            ):
                st.success(
                    f"優惠碼 {admin_promo_code.strip().upper()} 已啟用。"
                )
            else:
                st.error("優惠碼儲存失敗，請先執行 v0.6.12 SQL。")

        st.markdown("---")

        st.markdown("#### 📚 專屬題庫管理")
        if supabase_client:
            try:
                res_count = supabase_client.table("item_bank").select("id", count="exact").execute()
                st.info(f"目前的專屬 9 欄位題庫總量：**{res_count.count}** 題")
            except Exception:
                pass
                
        with st.expander("📂 CSV 批次匯入 9 欄位題庫", expanded=False):
            if not PANDAS_AVAILABLE:
                st.error("系統缺少 pandas 套件。")
            else:
                st.info("💡 請上傳您的 CSV 檔案，系統將自動提取 9 個欄位，並分批寫入 `item_bank`。")
                uploaded_csv = st.file_uploader("選擇 CSV 檔案", type=["csv"])
                if uploaded_csv is not None:
                    if st.button("🚀 開始批次匯入"):
                        with st.spinner("正在讀取並準備資料..."):
                            try:
                                df = pd.read_csv(uploaded_csv).fillna("")
                                all_records = []
                                for index, row in df.iterrows():
                                    all_records.append({
                                        "user_id": str(row.get('user_id', 'system_public_bank')),
                                        "index_code": str(row.get('index_code', f'CSV-{random.randint(10000,99999)}')),
                                        "grade": str(row.get('grade', '')),
                                        "unit": str(row.get('unit', '')),
                                        "knowledge_tag": str(row.get('knowledge_tag', '')),
                                        "original_question": str(row.get('original_question', '')),
                                        "new_question": str(row.get('new_question', '')),
                                        "correct_answer": str(row.get('correct_answer', '')),
                                        "status": str(row.get('status', 'pending'))
                                    })
                                
                                total_valid = len(all_records)
                                if total_valid == 0:
                                    st.warning("⚠️ 檔案中沒有找到有效的資料。")
                                else:
                                    batch_size = 500
                                    success_count = 0
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()
                                    
                                    for i in range(0, total_valid, batch_size):
                                        batch_data = all_records[i : i + batch_size]
                                        try:
                                            if supabase_client:
                                                supabase_client.table("item_bank").insert(batch_data).execute()
                                                success_count += len(batch_data)
                                        except Exception as batch_e:
                                            st.warning(f"⚠️ 批次寫入失敗。錯誤：{batch_e}")
                                            
                                        current_progress = min(1.0, (i + batch_size) / total_valid)
                                        progress_bar.progress(current_progress)
                                        status_text.text(f"🔄 處理進度：{min(i + batch_size, total_valid)} / {total_valid} 筆完成")
                                        
                                    st.success(f"✅ 恭喜！成功將 {success_count} 筆題目匯入 `item_bank`！")
                            except Exception:
                                st.error("匯入失敗，請確認檔案格式後再試。")

def render_math_content(content_text):
    """Render mixed Markdown + HTML while letting Streamlit display math cleanly."""
    st.markdown(normalize_math_markdown(content_text), unsafe_allow_html=True)


def show_trial_conversion_notice():
    notice_box = (
        "<div style='background-color: #fff3cd; color: #856404; padding: 20px; border-radius: 10px; border-left: 6px solid #ffeba2; margin: 15px 0; font-size: 1.05em; line-height: 1.7;'>"
        "<b>⚠️ 點數不足或試用額度已用完！</b><br><br>"
        "想要繼續產出更多專屬練習嗎？請至左側選單進行<b>「儲值點數」</b>或點擊頁籤至 <b>[🏠 帳號與設定]</b> 完成免費登入綁定！<br><br>"
        "<b>👉 為什麼你應該立即免費註冊綁定？</b><br>"
        "• 🎁 <b>免費送點數</b>：新用戶註冊綁定登入後，自動獲贈 <b>200 點</b>！<br>"
        "• 🧠 <b>自動建立專屬學習履歷</b>：系統將自動記錄每一次的錯題，精準追蹤你的知識盲點。<br>"
        "• 🎯 <b>弱點深度分析與迭代</b>：不再盲目刷題！唯有透過個人化錯題累積，才能進行高度客製化的「疊代升級練習」。<br>"
        "• ⚡ <b>倍增學習效率</b>：幫學生省下 80% 整理錯題本的時間，直擊弱點，用最短時間獲得最大幅度進步！<br><br>"
        "<i>( 綁定 Email 即可立即解鎖完整功能！ )</i>"
        "</div>"
    )
    st.markdown(notice_box, unsafe_allow_html=True)

# --- 🎯 獨立視窗彈出式列印 (內建 KaTeX 引擎) ---
def render_share_buttons(content_text, key_prefix):
    content_text = normalize_math_markdown(content_text)
    st.markdown("---")
    st.markdown("#### 📤 試卷輸出與分享選項")
    
    user_email = st.session_state["user_profile"].get("email", "")
    is_trial_user = (not user_email or user_email == "trial@example.com")

    json_safe_content = json.dumps(content_text)
    profile = st.session_state.get("user_profile", {})
    print_student_name = (
        f"{profile.get('last_name', '')}{profile.get('first_name', '')}".strip()
        or "學生"
    )
    print_grade = profile.get("grade", "")
    print_version = profile.get("version", "")
    print_header_text = json.dumps(
        f"MathAI 試卷｜{print_student_name}｜{print_grade}｜{print_version}",
        ensure_ascii=False,
    )

    c_share1, c_share2, c_share3 = st.columns(3)
    
    with c_share1:
        popup_print_script = f"""
        <script>
        function printOnlyExam() {{
            var rawContent = {json_safe_content};
            var formattedContent = rawContent
                .replace(/^\\s*#\\s*$/gm, '')
                .replace(/^###\\s+(.+)$/gm, '<h3>$1</h3>')
                .replace(/^##\\s+(.+)$/gm, '<h2 class="section-title">$1</h2>')
                .replace(/^#\\s+(.+)$/gm, '<h1 class="section-title">$1</h1>')
                .replace(/\\n/g, '<br>');

            var printWindow = window.open('', '', 'width=950,height=1000');
            printWindow.document.write('<!DOCTYPE html><html><head><title>試題與解答卷</title>');
            
            printWindow.document.write('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">');
            printWindow.document.write('<script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"><\\/script>');
            printWindow.document.write('<script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"><\\/script>');
            
            printWindow.document.write('<style>');
            printWindow.document.write('@page {{ size: A4 portrait; margin: 18mm 12mm 17mm 12mm; }}');
            printWindow.document.write('*, *::before, *::after {{ box-sizing: border-box; }}');
            printWindow.document.write('html, body {{ width: 100%; }}');
            printWindow.document.write('body {{ font-family: "PingFang TC", "Microsoft JhengHei", sans-serif; font-size: 10.5pt; line-height: 1.45; color: #000; margin: 0; padding: 0; background: #fff; overflow: visible; }}');
            printWindow.document.write('#exam-body {{ width: 100%; max-width: none; }}');
            printWindow.document.write('.section-title {{ font-size: 14pt; font-weight: bold; border-bottom: 1.5px solid #000; padding-bottom: 4px; margin: 10px 0 8px 0; break-after: avoid-page; page-break-after: avoid; }}');
            printWindow.document.write('h1, h2, h3, h4 {{ break-after: avoid-page; page-break-after: avoid; }}');
            printWindow.document.write('p, li, table, .katex-display {{ orphans: 3; widows: 3; }}');
            printWindow.document.write('.page-break {{ page-break-before: always !important; break-before: page !important; height: 0; margin: 0; padding: 0; clear: both; }}');
            printWindow.document.write('.print-header {{ position: fixed; top: -12mm; left: 0; right: 0; height: 8mm; border-bottom: 1px solid #666; font-size: 8.5pt; display: flex; justify-content: space-between; align-items: center; }}');
            printWindow.document.write('.print-footer {{ position: fixed; bottom: -11mm; left: 0; right: 0; height: 8mm; border-top: 1px solid #666; font-size: 8.5pt; display: flex; justify-content: space-between; align-items: center; }}');
            printWindow.document.write('@media print {{ .no-print {{ display: none !important; }} a {{ color: #000; text-decoration: none; }} }}');
            printWindow.document.write('</style></head><body>');
            
            var headerText = {print_header_text};
            printWindow.document.write('<div class="print-header"><span>' + headerText + '</span><span>錯題疊代訓練</span></div>');
            printWindow.document.write('<div class="print-footer"><span>' + headerText + '</span><span>MathAI 個人化學習履歷</span></div>');

            printWindow.document.write('<div class="no-print" style="position: fixed; top: 10px; right: 20px; z-index: 9999;">');
            printWindow.document.write('<button onclick="window.print()" style="padding: 10px 20px; font-size: 13pt; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">🖨️ 立即列印 / 另存為 PDF</button>');
            printWindow.document.write('</div>');
            
            printWindow.document.write('<div id="exam-body">' + formattedContent + '</div>');
            
            printWindow.document.write('<script>');
            printWindow.document.write('document.addEventListener("DOMContentLoaded", function() {{');
            printWindow.document.write('    renderMathInElement(document.body, {{');
            printWindow.document.write('        delimiters: [');
            printWindow.document.write('            {{left: "$$", right: "$$", display: true}},');
            printWindow.document.write('            {{left: "$", right: "$", display: false}}');
            printWindow.document.write('        ],');
            printWindow.document.write('        throwOnError: false');
            printWindow.document.write('    }});');
            printWindow.document.write('}});');
            printWindow.document.write('<\\/script>');
            
            printWindow.document.write('</body></html>');
            printWindow.document.close();
            printWindow.focus();
        }}
        </script>
        <button onclick="printOnlyExam()" style="
            width: 100%;
            background-color: #ff4b4b;
            color: white;
            padding: 10px;
            border: none;
            border-radius: 5px;
            font-weight: bold;
            cursor: pointer;
            font-size: 14px;
        ">🖨️ 列印 / 存PDF</button>
        """
        components.html(popup_print_script, height=45)
        
    with c_share2:
        mail_body = urllib.parse.quote(content_text)
        line_url = f"https://line.me/R/msg/text/?{mail_body[:500]}"
        st.markdown(f'<a href="{line_url}" target="_blank"><button style="width:100%; border-radius:5px; border:1px solid #06C755; background-color:#06C755; color:white; padding:10px; font-weight:bold; cursor:pointer; font-size: 14px;">💬 分享到 LINE</button></a>', unsafe_allow_html=True)
        
    with c_share3:
        if is_trial_user:
            st.button(
                "📩 登入後寄送到註冊 Email",
                key=f"{key_prefix}_send_btn_trial",
                use_container_width=True,
                disabled=True,
            )
        else:
            masked_email = user_email
            if "@" in user_email:
                local_part, domain_part = user_email.split("@", 1)
                masked_email = (
                    local_part[:3]
                    + "***@"
                    + domain_part
                )
            st.caption(f"收件信箱：{masked_email}")
            if st.button(
                "📩 寄送到我的註冊 Email",
                key=f"{key_prefix}_send_btn_reg",
                use_container_width=True,
            ):
                now = datetime.now()
                last_sent = st.session_state.get(
                    "last_exam_email_sent_at"
                )
                if (
                    isinstance(last_sent, datetime)
                    and (now - last_sent).total_seconds() < 60
                ):
                    st.warning("請等待 60 秒後再重新寄送，避免重複郵件。")
                else:
                    with st.spinner("正寄送到您的註冊信箱…"):
                        if send_exam_email(
                            user_email,
                            content_text,
                        ):
                            st.session_state[
                                "last_exam_email_sent_at"
                            ] = now
                            st.success(
                                "✅ 試卷與答案已寄送到您的註冊 Email。"
                            )
                        else:
                            st.info(
                                "管理員請確認 Streamlit Cloud Secrets "
                                "已設定 SMTP_USER 與 SMTP_PASSWORD。"
                            )


def parse_and_insert_9_col_json(ai_response_text):
    if not supabase_client: return
    json_match = re.search(r'```json(.*?)```', ai_response_text, re.DOTALL)
    if json_match:
        try:
            q_list = json.loads(json_match.group(1).strip())
            insert_data = []
            for q in q_list:
                q["user_id"] = st.session_state["user_profile"]["email"]
                q["status"] = "pending"
                insert_data.append(q)
            if insert_data:
                supabase_client.table("item_bank").insert(insert_data).execute()
        except Exception:
            pass

anti_duplicate_prompt = "【防重複出題機制】：為確保每次練習都有新體驗，請大幅隨機替換數字與情境。嚴禁產出與標準題庫一模一樣的題目。"

COMMON_LAYOUT_PROMPT = (
    "【★★★ 極度重要：排版與解答格式強制規定 ★★★】\n"
    "1. 必須將「試卷區」與「解答區」完全分開輸出！前面先輸出所有試題（絕對不能在題目旁附答案），最後再統一輸出解答。\n"
    "2. 在「試卷區」中，『除了是非題之外的所有題型』，每一道題目的結尾，都必須強制插入 5 個 HTML 換行標籤 <br><br><br><br><br> 讓學生有空間可以計算與作答。\n"
    "3. 在試題列完後，必須強制單獨空一行，並插入分頁符號代碼：<div class=\"page-break\" style=\"page-break-after: always; break-after: page;\"></div>\n"
    "4. 分頁符號後的「解答區」，請提供所有對應題目的正確答案與詳細步驟。\n"
)

LAYOUT_WITH_ANALYSIS = (
    "【★★★ 極度重要：排版與解答格式強制規定 ★★★】\n"
    "請嚴格套用以下結構輸出，使用繁體中文，絕對不可輸出無關說明、思考過程或英文標籤：\n"
    f"{MATH_OUTPUT_RULES}\n\n"
    "## 錯題詳細解析\n"
    "（請針對上方【錯題內容】中的每一道原始題目，精準算出並列出：「正確答案」與「詳細解題步驟與觀念解說」。）\n\n"
    "<div class=\"page-break\" style=\"page-break-after: always; break-after: page;\"></div>\n\n"
    "## 試卷區（模擬試題）\n"
    "（在這裡列出根據原錯題延伸出的模擬題目，絕對不能附上任何解答或提示！）\n"
    "（注意：除了「是非題」之外，『每一道題目』的最下方，必須強制加上 5 個換行標籤 <br><br><br><br><br> 讓學生作答寫字）\n\n"
    "<div class=\"page-break\" style=\"page-break-after: always; break-after: page;\"></div>\n\n"
    "## 解答區\n"
    "（在分頁符號後，請在此統一列出這所有模擬試題的正確解答與詳細步驟）\n"
)

LAYOUT_NORMAL = (
    "【★★★ 極度重要：排版與解答格式強制規定 ★★★】\n"
    "請你嚴格套用以下結構進行輸出，不可隨意省略、不可把解答寫在題目旁邊：\n"
    f"{MATH_OUTPUT_RULES}\n\n"
    "## 試卷區\n"
    "（在這裡列出所有的題目，絕對不能附上任何解答或提示！）\n"
    "（注意：除了「是非題」之外，『每一道題目』的最下方，必須強制加上 5 個換行標籤 <br><br><br><br><br> 讓學生作答寫字）\n\n"
    "<div class=\"page-break\" style=\"page-break-after: always; break-after: page;\"></div>\n\n"
    "## 解答區\n"
    "（在分頁符號後，請在此統一列出剛剛試卷區所有題目的正確解答與詳細步驟）\n"
)

JSON_TEMPLATE_MOCK = (
    '【資料儲存規定】：在回應的最底下，將「新出的模擬題目」結構化，用 ```json 包起來。\n'
    '```json\n[\n  {\n    "index_code": "AI-M001",\n    "grade": "",\n    "unit": "基礎掃描出題",\n    "knowledge_tag": "錯題解析",\n    "original_question": "原錯題文字...",\n    "new_question": "模擬題文字...",\n    "correct_answer": "解答文字..."\n  }\n]\n```\n'
)

JSON_TEMPLATE_VAR = (
    '【資料儲存規定】：在回應的最底下，將「新出的變形題目」結構化，用 ```json 包起來。\n'
    '```json\n[\n  {\n    "index_code": "AI-V001",\n    "grade": "",\n    "unit": "變形疊代題",\n    "knowledge_tag": "錯題變形",\n    "original_question": "原題內容",\n    "new_question": "新題內容",\n    "correct_answer": "新題解答"\n  }\n]\n```\n'
)

JSON_TEMPLATE_HIST = (
    '【資料儲存規定】：在回應的最底下，將「新出的複習題目」結構化，用 ```json 包起來。\n'
    '```json\n[\n  {\n    "index_code": "AI-H001",\n    "grade": "",\n    "unit": "歷史錯題複習",\n    "knowledge_tag": "TAG_PLACEHOLDER",\n    "original_question": "歷史錯題原題",\n    "new_question": "新題內容",\n    "correct_answer": "解答內容"\n  }\n]\n```\n'
)

JSON_TEMPLATE_CUSTOM = (
    '【資料儲存規定】：在回應的最底下，將「新出的自組卷題目」結構化，用 ```json 包起來。\n'
    '```json\n[\n  {\n    "index_code": "AI-C001",\n    "grade": "",\n    "unit": "UNIT_PLACEHOLDER",\n    "knowledge_tag": "選擇的題型",\n    "original_question": "",\n    "new_question": "題目內容...",\n    "correct_answer": "解答內容..."\n  }\n]\n```\n'
)

q_count_options = {
    "5 題包（微型檢討） - 扣 15 點": 5,
    "10 題包（小考/段考訂正） - 扣 28 點": 10,
    "15 題包（大單元複習） - 扣 40 點": 15,
    "20 題包（全冊總複習試卷） - 扣 50 點": 20
}

MAIN_TAB_LABELS = [
    "📸 錯題解析",
    "🏠 帳號與設定",
    "🌳 學習地圖",
    "🧠 學習診斷 🔒",
    "⚙️ 自組考卷 🔒",
]

MAIN_NAV_BUTTON_LABELS = [
    "錯題解析",
    "帳號設定",
    "學習地圖",
    "學習診斷",
    "自組試卷",
]


def request_page_top():
    """下一次 rerun 後把瀏覽器移到頁首。"""
    st.session_state["request_scroll_to_top"] = True


def render_requested_page_top():
    """Streamlit rerun 會保留瀏覽器捲動位置；需要時主動回到頁首。"""
    if not st.session_state.pop("request_scroll_to_top", False):
        return
    components.html(
        """
        <script>
        setTimeout(function () {
            try {
                window.parent.scrollTo({top: 0, left: 0, behavior: "instant"});
                var main = window.parent.document.querySelector(
                    'section.main, [data-testid="stMain"], .main'
                );
                if (main) {
                    main.scrollTo({top: 0, left: 0, behavior: "instant"});
                }
            } catch (e) {}
        }, 80);
        </script>
        """,
        height=0,
        width=0,
    )


def switch_main_tab(tab_label):
    """由桌面固定導覽列切換主功能。"""
    if queue_main_tab(st.session_state, tab_label, MAIN_TAB_LABELS):
        request_page_top()


def request_main_tab(tab_label):
    """Queue an in-page navigation request and start a clean Streamlit run."""
    if queue_main_tab(st.session_state, tab_label, MAIN_TAB_LABELS):
        request_page_top()
        st.rerun()


def switch_main_tab_from_mobile():
    """由手機下拉式選單切換主功能。"""
    selected_tab = st.session_state.get("mobile_main_nav_selector")
    if queue_main_tab(st.session_state, selected_tab, MAIN_TAB_LABELS):
        request_page_top()


SYSTEM_TIPS = [
    "本系統由陳冠林老師團隊獨立開發。",
    "試用期間免費點數大放送，請多加利用。",
    "點擊左上方雙箭頭，可以回饋問題增加免費點數，也可以儲值點數。",
    "手機版請從上方功能選單切換五個主要功能，不需要左右滑動。",
    "手機橫向旋轉可獲得更寬畫面，查看試卷與功能會更方便。",
    "第一次使用請先完成學生資料，AI 才能建立專屬學習履歷。",
    "每個 Email 建議只綁定一位學生，避免學習紀錄混在一起。",
    "拍照時盡量包含完整題目，提高辨識率。",
    "紅筆批改後再拍照，AI 可以更精準分析錯因。",
    "不知道該練什麼？直接使用錯題疊代即可。",
    "每完成一份試卷，再重新拍照即可開始下一輪練習。",
    "AI 會根據錯題，自動調整下一份試卷的難度與順序。",
    "學習地圖可以快速找到目前最需要補強的觀念。",
    "累積錯題都在學習診斷裡面。",
    "自組試卷適合段考、會考與競賽前集中練習。",
    "五題為一組，可以有效控制學習節奏與點數消耗。",
    "題目會依主單元、次單元與知識點分類。",
    "每次錯題都會累積成個人學習履歷。",
    "同一觀念反覆錯誤時，系統會安排更多基礎題。",
    "熟悉後，AI 會自動加入適量的進階變化題。",
    "學習不是刷更多題，而是補強真正不會的地方。",
    "建議固定使用同一帳號，讓 AI 更了解你的學習狀況。",
    "回饋建議可獲得點數，也能幫助系統持續優化。",
    "推薦獎勵：介紹人須先符合資格；被推薦人成功登記介紹人後，完成第一次有效出題或錯題解析，雙方各得 50 點。",
    "累積 3 次有效使用是「取得介紹人資格」的條件之一，不是被推薦人領取 50 點的必要條件。",
    "掃描到不同年級題目時，系統會先提醒再處理。",
    "學習履歷越完整，個人化出題會越準確。",
    "目標不是做最多題，而是用最少時間掌握最多重點。",
]


def render_system_tipbar():
    total_seconds = len(SYSTEM_TIPS) * 6
    items = []
    for index, text in enumerate(SYSTEM_TIPS):
        items.append(
            f'<div class="mathai-tipbar__tip" '
            f'style="animation-duration:{total_seconds}s;'
            f'animation-delay:{index * 6}s;">{text}</div>'
        )
    st.markdown(
        f"""
        <div class="mathai-tipbar">
            <div class="mathai-tipbar__viewport">{''.join(items)}</div>
            <div class="mathai-tipbar__label">使用小訣竅</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==========================================
# 第一頁：登入與試用頁面
# ==========================================
if not st.session_state["setup_complete"] and not st.session_state["is_trial"]:
    render_requested_page_top()
    st.title("🧙‍♂️ AI 數學錯題迭代系統")
    welcome_msg = (
        "<div style=\"background-color: #f0f7ff; padding: 16px; border-radius: 10px; border-left: 6px solid #1c83e1; font-size: 1.05em;\">\n"
        "<b>> 造就異數的不是 1 萬小時的重複，而是 1 萬次迭代。</b> —— Naval Ravikant\n"
        "</div>"
    )
    st.markdown(welcome_msg, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="mathai-mobile-guide">
            📱 <b>手機操作提醒</b><br>
            點擊左上方雙箭頭，可以回饋問題增加免費點數、儲值點數。
            完成註冊進入系統後，請從上方的「功能選單（共 5 項）」切換功能；
            將手機橫向旋轉，可以獲得較寬的試卷與內容畫面。
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    if is_localhost_request():
        st.info("🧪 本機開發模式：可跳過 Email 與 OTP，直接測試後續功能。此按鈕不會出現在公開網站。")
        if st.button(
            "🧪 本機開發者快速進入系統",
            type="secondary",
            use_container_width=True,
        ):
            remembered = get_recent_emails()
            dev_email = "developer@local.test"
            st.session_state["user_profile"].update({
                "email": dev_email,
                "credits": 9999,
                "last_name": st.session_state["user_profile"].get("last_name") or "測試",
                "first_name": st.session_state["user_profile"].get("first_name") or "學生",
                "city": st.session_state["user_profile"].get("city") or "新北市",
                "district": st.session_state["user_profile"].get("district") or "土城區",
                "school": st.session_state["user_profile"].get("school") or "MathAI 測試學校",
                "grade": st.session_state["user_profile"].get("grade") or "5年級(小五)",
                "version": st.session_state["user_profile"].get("version") or "康軒版",
                "traits": st.session_state["user_profile"].get("traits") or ["希望挑戰更高難度的數學"],
                "interests": st.session_state["user_profile"].get("interests") or ["魔術方塊"],
            })
            st.session_state["developer_mode"] = True
            st.session_state["is_verified"] = True
            st.session_state["is_trial"] = False
            st.session_state["setup_complete"] = True
            st.rerun()
        st.markdown("---")
    
    client_ip = get_client_ip()
    ip_today_key = f"{today_str}_{client_ip}"
    current_ip_trials = st.session_state["ip_trial_history"].get(ip_today_key, 0)

    col_trial_1, col_trial_2, col_trial_3 = st.columns([1, 2, 1])
    with col_trial_2:
        if current_ip_trials >= 1:
            st.error("⚠️ 您的 IP 今日試用額度已用盡！請使用下方 Email 驗證註冊/登入。")
        else:
            if st.button("🚀 立即試用（送 30 點，直接進入系統）", type="primary", use_container_width=True):
                reset_user_profile_for_new_account("", credits=30)
                st.session_state["developer_mode"] = False
                st.session_state["is_trial"] = True
                st.session_state["setup_complete"] = True
                st.rerun()
    st.markdown("---")

    st.subheader("📋 註冊綁定 / 登入個人資料庫 (新會員登入即送 200 點)")
    up = st.session_state["user_profile"]

    current_stored_email = st.session_state["user_profile"].get("email", "")
    is_verified = bool(current_stored_email and current_stored_email != "trial@example.com")

    if not is_verified:
        render_private_beta_auth_login()
        st.markdown("---")
        st.caption(
            "舊版 Email OTP 僅供相容使用，不會取得 Supabase ownership，也不會啟用跨 session 學習紀錄。"
        )
        recent_emails = get_recent_emails()
        manual_email_option = "➕ 手動輸入新 Email..."
        email_options = recent_emails + [manual_email_option]

        st.markdown("#### 📧 請選擇或輸入您的登入 Email (必填)")
        if recent_emails:
            st.caption("✅ 已載入這台裝置曾驗證過的 Email；最近使用的帳號會排在最前面。")
        elif not COOKIE_CONTROLLER_AVAILABLE:
            st.caption("ℹ️ 裝置記憶元件尚未安裝，目前仍可手動輸入 Email。")

        selected_option = st.selectbox(
            "點擊選擇曾登入過的帳號：",
            email_options,
            key="single_email_select",
        )

        if recent_emails:
            if st.button(
                "🧹 清除這台裝置記住的 Email",
                key="clear_device_emails",
            ):
                clear_recent_emails()
                st.session_state.pop("single_email_select", None)
                st.session_state["pending_email"] = ""
                st.success("已清除這台裝置的 Email 記錄。")
                st.rerun()

        if selected_option == manual_email_option:
            typed_email = st.text_input(
                "請輸入新的 Email (綁定與驗證用)：",
                value=st.session_state["pending_email"],
                placeholder="example@gmail.com",
            )
            user_email_input = typed_email.strip()
        else:
            user_email_input = normalize_email(selected_option)
            st.session_state["pending_email"] = user_email_input
            st.caption(
                "完成 OTP 驗證後，系統會自動載入此帳號之前儲存的資料。"
            )


        col_otp1, col_otp2 = st.columns([1, 2])
        with col_otp1:
            if st.button("📧 1. 傳送 6 位數驗證碼"):
                if user_email_input and "@" in user_email_input:
                    new_otp = str(random.randint(100000, 999999))
                    st.session_state["generated_otp"] = new_otp
                    st.session_state["pending_email"] = user_email_input
                    if send_otp_email(user_email_input, new_otp):
                        st.session_state["otp_sent"] = True
                        st.rerun()
                else:
                    st.warning("請輸入正確的 Email 格式！")
        
        if st.session_state["otp_sent"]:
            with col_otp2:
                st.info(f"🔧 **[測試模式] 您的登入驗證碼是： {st.session_state['generated_otp']}**")
                
                with st.form("otp_login_form", border=False):
                    user_otp_input = st.text_input("🔑 請輸入您收到的驗證碼（輸入後可直接按 Enter 鍵）：", max_chars=6)
                    submit_login = st.form_submit_button("🔗 2. 驗證 OTP 並登入", type="primary", use_container_width=True)
                    
                    if submit_login:
                        if user_otp_input == st.session_state["generated_otp"]:
                            clear_private_beta_auth_session()
                            verified_email = normalize_email(
                                st.session_state["pending_email"]
                            )
                            clear_profile_widget_state(verified_email)
                            db_profile = build_complete_user_profile(verified_email)
                            if db_profile:
                                apply_user_profile_to_session(
                                    db_profile,
                                    verified_email,
                                )
                                st.session_state["profile_load_notice"] = "existing"
                                st.session_state[
                                    "is_new_account_registration"
                                ] = False
                            else:
                                reset_user_profile_for_new_account(
                                    verified_email,
                                    credits=200,
                                )
                                st.session_state["profile_load_notice"] = "new"
                                st.session_state[
                                    "is_new_account_registration"
                                ] = True
                            # 正常 Email 登入必須退出本機開發者模式，
                            # 避免前一次 developer_mode 狀態污染正式會員。
                            st.session_state["developer_mode"] = False
                            st.session_state["is_trial"] = False
                            st.session_state["wallet_synced_email"] = ""
                            st.session_state["is_verified"] = True
                            st.session_state["otp_sent"] = False
                            save_recent_email(verified_email)

                            # v0.6.19：第一次把舊系統目前點數搬入 Supabase wallet，
                            # 之後跨裝置／重新登入都以雲端點數為準。
                            sync_wallet_balance_to_session(
                                verified_email,
                                force=True,
                                is_new_account=st.session_state.get(
                                    "is_new_account_registration",
                                    False,
                                ),
                            )
                            st.rerun()
                        else:
                            st.error("❌ 驗證碼錯誤，請重新確認！")
        st.markdown("---")
    else:
        st.success(f"✅ 您目前已登入 Email：**{current_stored_email}**")
        st.markdown("---")

    if not is_verified:
        st.info("請先完成 Email 驗證，驗證成功後才會顯示學生資料。")
        st.stop()

    verified_profile_email = normalize_email(
        st.session_state["user_profile"].get("email", "")
    )
    if verified_profile_email and verified_profile_email != "trial@example.com":
        sync_wallet_balance_to_session(verified_profile_email)
    if (
        verified_profile_email
        and verified_profile_email != "trial@example.com"
        and st.session_state.get("loaded_profile_email")
        != verified_profile_email
    ):
        complete_profile = build_complete_user_profile(
            verified_profile_email
        )
        if complete_profile:
            clear_profile_widget_state(
                verified_profile_email
            )
            apply_user_profile_to_session(
                complete_profile,
                verified_profile_email,
            )

    profile_load_notice = st.session_state.pop("profile_load_notice", "")
    if profile_load_notice == "existing":
        st.success("✅ 已載入此帳號之前儲存的基本資料、學習狀況與興趣。")
    elif profile_load_notice == "new":
        st.info("這是新帳號，請完成下方必填資料。")

    if (
        st.session_state.get("admin_unlocked", False)
        and st.session_state.get("source_claim_rpc_debug")
    ):
        with st.expander("管理員：來源獎勵狀態 RPC 錯誤"):
            st.code(st.session_state["source_claim_rpc_debug"])

    if (
        st.session_state.get("admin_unlocked", False)
        and st.session_state.get("source_retry_rpc_debug")
    ):
        with st.expander("管理員：推薦重填狀態 RPC 錯誤"):
            st.code(st.session_state["source_retry_rpc_debug"])

    if (
        st.session_state.get("admin_unlocked", False)
        and st.session_state.get("referrer_rpc_debug")
    ):
        with st.expander("管理員：推薦資格 RPC 錯誤"):
            st.code(st.session_state["referrer_rpc_debug"])

    if (
        st.session_state.get("admin_unlocked", False)
        and st.session_state.get("custom_exam_postprocess_debug")
    ):
        with st.expander("管理員：試卷後處理錯誤"):
            st.code(st.session_state["custom_exam_postprocess_debug"])

    if (
        st.session_state.get("admin_unlocked", False)
        and st.session_state.get("wallet_rpc_debug")
    ):
        with st.expander("管理員：雲端點數錢包 RPC 錯誤"):
            st.code(st.session_state["wallet_rpc_debug"])

    if (
        st.session_state.get("admin_unlocked", False)
        and st.session_state.get("referral_award_debug")
    ):
        with st.expander("管理員：推薦點數發放 RPC 錯誤"):
            st.code(st.session_state["referral_award_debug"])

    if (
        st.session_state.get("admin_unlocked", False)
        and st.session_state.get("referral_save_debug")
    ):
        with st.expander("管理員：推薦資料寫入錯誤"):
            st.code(st.session_state["referral_save_debug"])

    profile_read_warning = st.session_state.pop(
        "profile_cloud_read_warning",
        "",
    )
    if profile_read_warning:
        st.warning(
            "會員資料暫時無法從 Supabase 讀取。"
            "請確認 v0.7.0 資料架構 SQL 已執行。"
        )
        if st.session_state.get("admin_unlocked", False):
            st.code(profile_read_warning)

    profile_save_warning = st.session_state.pop(
        "profile_cloud_save_warning",
        "",
    )
    if profile_save_warning:
        st.warning(
            "會員資料尚未成功同步到 Supabase。"
            "請確認已執行「Supabase_v0.7.0_資料架構整理.sql」。"
        )

    restore_retry_state_to_session()
    up = st.session_state["user_profile"]

    # 推薦／優惠驗證失敗時，重新整理、重新登入、換裝置後仍保留修改權限。
    if up.get("source_reward_status") == "retry_allowed":
        st.session_state["is_new_account_registration"] = True

    def_ln = up.get("last_name", "")
    def_fn = up.get("first_name", "")
    def_city = up.get("city", "新北市")
    def_district = up.get("district", "土城區")
    def_school = up.get("school", "")
    def_grade = up.get("grade", "8年級(國二)")
    def_ver = up.get("version", "康軒版")
    def_traits = up.get("traits", [])
    def_interests = up.get("interests", [])

    st.markdown("#### 👤 學生基本資料設定")
    st.info(
        "📚 **一個 Email 建議只綁定一位學生。** "
        "MathAI 會累積錯題、程度變化、學習進度與歷年紀錄，"
        "再依個人表現調整下一份題目的難度與順序。多人共用同一帳號，"
        "會讓學習履歷混在一起，降低個人化出題的準確度。"
    )
    st.caption("紅色項目為必填欄位；姓名首次確認後鎖定，年級與版本每年可調整 2 次。")
    st.info(
        "🔒 隱私提醒：不一定要輸入完整真實姓名。"
        "姓氏可使用英文縮寫（例如 C），名字可使用英文名字或暱稱（例如 Kevin）。"
    )

    profile_account_source = current_stored_email or st.session_state.get("pending_email", "new_user")
    profile_account_key = hashlib.sha256(profile_account_source.encode("utf-8")).hexdigest()[:10]
    profile_control = get_profile_control(profile_account_source)
    identity_locked = bool(profile_control.get("identity_locked", False))
    locked_last_name = str(profile_control.get("locked_last_name") or "").strip()
    locked_first_name = str(profile_control.get("locked_first_name") or "").strip()
    name_identity_locked = bool(
        identity_locked and locked_last_name and locked_first_name
    )

    if not def_ln and locked_last_name:
        def_ln = locked_last_name
    if not def_fn and locked_first_name:
        def_fn = locked_first_name

    grade_version_remaining = remaining_grade_version_changes(profile_control)

    def show_required_label(label_text):
        st.markdown(
            f"<div style='color:#d32f2f;font-weight:700;margin:0.15rem 0 0.25rem 0;'>"
            f"{label_text} <span style='font-size:1.05em;'>*</span></div>",
            unsafe_allow_html=True,
        )

    col_name1, col_name2 = st.columns(2)
    with col_name1:
        show_required_label("姓氏")
        last_n = st.text_input(
            "姓氏",
            value=def_ln,
            label_visibility="collapsed",
            key=f"profile_last_name_{profile_account_key}",
            disabled=name_identity_locked and not st.session_state.get("developer_mode", False),
            help="可用英文縮寫／英文名字／暱稱，不必輸入完整真實姓名；首次確認後會鎖定。",
        )
    with col_name2:
        show_required_label("名字")
        first_n = st.text_input(
            "名字",
            value=def_fn,
            label_visibility="collapsed",
            key=f"profile_first_name_{profile_account_key}",
            disabled=name_identity_locked and not st.session_state.get("developer_mode", False),
            help="可用英文縮寫／英文名字／暱稱，不必輸入完整真實姓名；首次確認後會鎖定。",
        )

    col_geo1, col_geo2, col_geo3 = st.columns(3)
    with col_geo1:
        show_required_label("縣市")
        city_idx = taiwan_counties.index(def_city) if def_city in taiwan_counties else 1
        selected_city = st.selectbox(
            "縣市",
            taiwan_counties,
            index=city_idx,
            label_visibility="collapsed",
            key=f"profile_city_{profile_account_key}",
        )
    with col_geo2:
        show_required_label("鄉鎮市區")
        dist_options = taiwan_districts.get(selected_city, ["全區"])
        dist_idx = dist_options.index(def_district) if def_district in dist_options else 0
        selected_district = st.selectbox(
            "鄉鎮市區",
            dist_options,
            index=dist_idx,
            label_visibility="collapsed",
            key=f"profile_district_{profile_account_key}",
        )
    with col_geo3:
        show_required_label("就讀學校")
        school_name = st.text_input(
            "就讀學校",
            value=def_school,
            placeholder="例如：樹林國中",
            label_visibility="collapsed",
            key=f"profile_school_{profile_account_key}",
        )

    if identity_locked and not st.session_state.get("developer_mode", False):
        st.caption(
            f"本年度年級／版本尚可調整 **{grade_version_remaining} 次**。"
            "這項限制可避免多人輪流使用同一帳號，並保護學習履歷的連續性。"
        )

    col_edu1, col_geo2_edu = st.columns(2)
    with col_edu1:
        show_required_label("就讀年級")
        gr_idx = grade_options.index(def_grade) if def_grade in grade_options else 7
        selected_grade = st.selectbox(
            "就讀年級",
            grade_options,
            index=gr_idx,
            label_visibility="collapsed",
            key=f"profile_grade_{profile_account_key}",
            disabled=(
                identity_locked
                and grade_version_remaining <= 0
                and not st.session_state.get("developer_mode", False)
            ),
        )

    is_high_school = any(g in selected_grade for g in ["10年級", "11年級", "12年級", "高"])
    if is_high_school:
        valid_versions = ["A級 (數學A)", "B級 (數學B)", "C級 (數學C)", "報考私中", "參加數學競賽"]
    else:
        valid_versions = ["康軒版", "翰林版", "南一版", "報考私中", "參加數學競賽"]

    ver_idx = valid_versions.index(def_ver) if def_ver in valid_versions else 0
    with col_geo2_edu:
        show_required_label("教科書版本／類別")
        selected_version = st.selectbox(
            "教科書版本／類別",
            valid_versions,
            index=ver_idx,
            label_visibility="collapsed",
            key=f"profile_version_{profile_account_key}",
            help="此設定會連動學習地圖與自組考卷。",
            disabled=(
                identity_locked
                and grade_version_remaining <= 0
                and not st.session_state.get("developer_mode", False)
            ),
        )

    retry_source_state = load_source_retry_state(
        st.session_state["user_profile"].get("email", "")
    ) or {}
    retry_source_allowed = (
        str(retry_source_state.get("status") or "").strip()
        == "retry_allowed"
    )

    source_claim_status = get_registration_source_claim_status(
        st.session_state["user_profile"].get("email", "")
    )
    source_claimed = bool(
        source_claim_status.get("has_claim", False)
    )

    # 來源資料的優先順序：
    # 1. 尚未完成的 retry 資料
    # 2. 已載入會員資料
    # 3. 自行搜尋
    retry_source_type = str(
        retry_source_state.get("source_type") or ""
    ).strip()
    retry_source_detail = str(
        retry_source_state.get("source_detail") or ""
    ).strip()

    source_type_selection = (
        retry_source_type
        or str(up.get("discovery_source") or "").strip()
        or "自行搜尋／不申請額外點數"
    )
    source_value_input = ""
    source_detail_input = (
        retry_source_detail
        or str(up.get("source_detail") or "")
    )

    # 任何「尚未成功占用來源獎勵」的會員都不會被永久鎖死。
    # 新會員、曾驗證失敗、或尚未成功申請者，都可再次開啟修改。
    can_edit_source = bool(
        not source_claimed
        and (
            st.session_state.get("is_new_account_registration", False)
            or retry_source_allowed
            or st.session_state.get("source_edit_mode", False)
        )
    )

    if not source_claimed and not can_edit_source:
        st.markdown("---")
        st.markdown("#### 🎁 推薦／優惠資料")
        st.caption(
            "目前尚未成功領取來源獎勵。"
            "需要補填或修改介紹人 Email／優惠碼時，可直接重新開啟。"
        )
        if st.button(
            "✏️ 新增／修改推薦人 Email 或優惠碼",
            key=f"open_source_edit_{profile_account_key}",
            use_container_width=True,
        ):
            st.session_state["source_edit_mode"] = True
            st.session_state["is_new_account_registration"] = True
            request_page_top()
            st.rerun()

    if can_edit_source:
        st.markdown("---")
        if retry_source_allowed or up.get("source_reward_status") == "retry_allowed":
            st.warning(
                "上次推薦／優惠資料未通過驗證，這次可以重新輸入。"
                "只有驗證失敗的帳號會保留這個修改機會。"
            )
        st.markdown("#### 🎁 您是如何知道 MathAI 的？")
        st.caption(
            "每個新帳號只能申請一次來源獎勵。推薦或優惠資料不正確時，"
            "仍可完成註冊，但不會發放額外點數。"
        )
        source_options = [
            "親友／老師介紹",
            "MathAI 活動／優惠碼",
            "其他通路（審核後贈送 50 點）",
            "自行搜尋／不申請額外點數",
        ]
        source_default_index = (
            source_options.index(source_type_selection)
            if source_type_selection in source_options
            else 3
        )

        source_widget_key = (
            f"registration_source_type_{profile_account_key}"
        )
        if (
            retry_source_allowed
            and retry_source_type in source_options
            and st.session_state.get(source_widget_key)
            != retry_source_type
        ):
            st.session_state[source_widget_key] = retry_source_type

        source_type_selection = st.selectbox(
            "您是如何知道 MathAI 的？",
            source_options,
            index=source_default_index,
            key=source_widget_key,
        )

        if source_type_selection == "親友／老師介紹":
            ref_col1, ref_col2 = st.columns([4, 1.35])
            referrer_widget_key = (
                f"registration_referrer_email_{profile_account_key}"
            )
            if (
                retry_source_allowed
                and retry_source_type == "親友／老師介紹"
                and st.session_state.get(referrer_widget_key)
                != retry_source_detail
            ):
                st.session_state[referrer_widget_key] = retry_source_detail

            with ref_col1:
                source_value_input = st.text_input(
                    "介紹人的註冊 Email",
                    value=(
                        source_detail_input
                        if retry_source_allowed
                        or up.get("source_reward_status") == "retry_allowed"
                        else ""
                    ),
                    placeholder="例如：teacher@example.com",
                    key=referrer_widget_key,
                )
            with ref_col2:
                st.markdown("<div style='height:1.72rem'></div>", unsafe_allow_html=True)
                verify_referrer_now = st.button(
                    "🔎 驗證介紹人資格",
                    key=f"verify_referrer_{profile_account_key}",
                    use_container_width=True,
                )

            validation_key = f"referrer_validation_{profile_account_key}"
            normalized_source_email = normalize_email(source_value_input)

            if verify_referrer_now:
                valid_referrer, referrer_message = validate_referrer(
                    normalized_source_email,
                    st.session_state["user_profile"].get("email", ""),
                )
                st.session_state[validation_key] = {
                    "email": normalized_source_email,
                    "valid": bool(valid_referrer),
                    "message": referrer_message,
                }

            validation_result = st.session_state.get(validation_key, {})
            if (
                validation_result
                and validation_result.get("email") == normalized_source_email
            ):
                if validation_result.get("valid"):
                    st.success(
                        "✅ "
                        + str(validation_result.get("message") or "介紹人資格確認成功。")
                    )
                    # 只更新尚未完成的重填資料，不發點、不鎖定；
                    # 使用者仍需按「完成註冊／儲存」才正式登記。
                    if up.get("source_reward_status") == "retry_allowed":
                        save_source_retry_state(
                            st.session_state["user_profile"].get("email", ""),
                            "親友／老師介紹",
                            normalized_source_email,
                            status="retry_allowed",
                        )
                else:
                    st.warning(
                        "⚠️ "
                        + str(validation_result.get("message") or "介紹人目前不符合資格。")
                        + " 您可以直接修改 Email 後再次驗證。"
                    )

            st.info(
                "🎁 **推薦獎勵規則**：介紹人必須先符合資格（完成會員資料，且已儲值或至少完成 3 次有效使用；管理員指定資格亦可）。\n\n"
                "被推薦人成功登記這位介紹人後，**不需要自己先累積 3 次使用**；只要完成第一次有效出題或錯題解析，雙方各得 50 點。\n\n"
                "被推薦人之後累積 3 次有效使用，是讓自己取得「可以介紹別人」的資格，和領取本次推薦 50 點是兩件不同的事。"
            )
        elif source_type_selection == "MathAI 活動／優惠碼":
            promo_widget_key = (
                f"registration_promo_code_{profile_account_key}"
            )
            if (
                retry_source_allowed
                and retry_source_type == "MathAI 活動／優惠碼"
                and st.session_state.get(promo_widget_key)
                != retry_source_detail
            ):
                st.session_state[promo_widget_key] = retry_source_detail

            source_value_input = st.text_input(
                "優惠碼",
                value=(
                    source_detail_input
                    if retry_source_allowed
                    or up.get("source_reward_status") == "retry_allowed"
                    else ""
                ),
                placeholder="請輸入活動優惠碼",
                key=promo_widget_key,
            )
            st.caption("優惠碼通過驗證後，點數會直接加入此註冊帳號。")
        elif source_type_selection == "其他通路（審核後贈送 50 點）":
            source_detail_input = st.text_area(
                "請填寫您從哪個通路知道 MathAI",
                value=source_detail_input,
                placeholder="例如：Facebook 社團、老師研習、學校活動",
                key=f"registration_source_detail_{profile_account_key}",
            )
            st.caption("資料送出後由管理員審核；通過後贈送 50 點。")

    elif source_claimed and source_type_selection:
        st.caption(
            f"得知 MathAI 的方式：{source_type_selection}（來源獎勵已登記）"
        )
        if (
            source_claim_status.get("claim_type") == "referral"
            and source_claim_status.get("claim_status") == "pending"
        ):
            st.info(
                "🎁 推薦關係已登記，50 點尚未發放。"
                "您完成第一次有效出題或錯題解析後，您與介紹人會各得到 50 點。"
                "累積 3 次有效使用是之後取得『介紹人資格』的條件，不是領這次 50 點的條件。"
            )
    elif not can_edit_source and source_type_selection:
        st.caption(f"得知 MathAI 的方式：{source_type_selection}")

    def finalize_registration_source():
        if not can_edit_source:
            return

        result_type, result_message = process_registration_source(
            st.session_state["user_profile"].get("email", ""),
            source_type_selection,
            source_value_input,
            source_detail_input,
        )
        retry_allowed = (
            result_type in {"warning", "error"}
            and source_type_selection
            != "自行搜尋／不申請額外點數"
        )

        if retry_allowed:
            result_message = (
                result_message
                + " 您可到「帳號設定」重新輸入正確的推薦／優惠資料。"
            )

        st.session_state["registration_source_result"] = (
            f"{result_type}|{result_message}"
        )

        # 只有成功或主動不申請時才鎖定來源資料。
        # 推薦人／優惠碼驗證失敗時保留重填權限。
        st.session_state["is_new_account_registration"] = retry_allowed

        current_source_detail = (
            source_detail_input or source_value_input
        )
        current_user_email = st.session_state["user_profile"].get(
            "email",
            "",
        )

        if retry_allowed:
            save_source_retry_state(
                current_user_email,
                source_type_selection,
                current_source_detail,
                status="retry_allowed",
            )
            st.session_state["source_edit_mode"] = True
        else:
            clear_source_retry_state(current_user_email)
            st.session_state["source_edit_mode"] = False

        if source_type_selection == "親友／老師介紹":
            source_reward_status = (
                "pending_first_use"
                if result_type == "success"
                else "retry_allowed"
            )
        elif source_type_selection == "MathAI 活動／優惠碼":
            source_reward_status = (
                "awarded"
                if result_type == "success"
                else "retry_allowed"
            )
        elif source_type_selection == "其他通路（審核後贈送 50 點）":
            source_reward_status = (
                "pending_review"
                if result_type == "success"
                else "retry_allowed"
            )
        else:
            source_reward_status = "none"

        st.session_state["user_profile"][
            "source_reward_status"
        ] = source_reward_status
        save_user_profile_to_db(
            st.session_state["user_profile"]
        )

    if is_verified:
        if st.button(
            "✅ 完成註冊，儲存必填資料並進入系統",
            type="primary",
            use_container_width=True,
            key="profile_required_save_enter",
        ):
            if not last_n.strip() or not first_n.strip():
                st.error("⚠️ 請完整填寫學生的姓氏與名字。")
            elif not school_name.strip():
                st.error("⚠️ 請填寫學生的就讀學校。")
            else:
                if not name_identity_locked:
                    profile_control.update({
                        "email": profile_account_source,
                        "identity_locked": True,
                        "locked_last_name": last_n.strip(),
                        "locked_first_name": first_n.strip(),
                        "grade": selected_grade,
                        "version": selected_version,
                        "change_year": date.today().year,
                        "change_count": int(
                            profile_control.get("change_count") or 0
                        ),
                    })
                    save_profile_control(profile_control)

                st.session_state["user_profile"].update({
                    "last_name": last_n.strip(),
                    "first_name": first_n.strip(),
                    "city": selected_city,
                    "district": selected_district,
                    "school": school_name.strip(),
                    "grade": selected_grade,
                    "version": selected_version,
                    "discovery_source": source_type_selection,
                    "source_detail": (
                        source_detail_input
                        or source_value_input
                    ),
                })
                for stale_key in [
                    "custom_exam_main_units",
                    "custom_exam_subunits",
                    "custom_exam_topics",
                    "custom_exam_question_types",
                    "custom_exam_profile_signature",
                ]:
                    st.session_state.pop(stale_key, None)
                save_recent_email(st.session_state["user_profile"]["email"])
                save_user_profile_to_db(st.session_state["user_profile"])
                finalize_registration_source()
                st.session_state["setup_complete"] = True
                st.session_state["main_tabs_control"] = MAIN_TAB_LABELS[0]
                st.session_state["mobile_main_nav_selector"] = MAIN_TAB_LABELS[0]
                request_page_top()
                st.rerun()

    st.caption("下方學習狀況與興趣為選填，之後可以再修改。")
    st.markdown("---")
    
    st.markdown("#### 🧠 學生個人學習狀況")
    st.caption("直接勾選即可，可複選；選中的項目會立即整理到下方。")

    learning_traits = [
        "粗心大意",
        "計算力不足",
        "基礎觀念不佳",
        "應用題理解困難",
        "空間幾何薄弱",
        "專注力不足容易分心",
        "考試時間分配不佳",
        "缺乏訂正習慣",
        "對數學有濃厚興趣",
        "希望挑戰更高難度的數學",
        "渴望突破現在的數學能力",
    ]

    known_traits = set(learning_traits)
    def_selected_traits = [t for t in def_traits if t in known_traits]
    custom_trait_values = [t for t in def_traits if t not in known_traits]
    def_custom_trait = "、".join(custom_trait_values)
    account_key = profile_account_key

    selected_traits = []
    trait_columns = st.columns(3)
    for trait_idx, trait in enumerate(learning_traits):
        with trait_columns[trait_idx % 3]:
            if st.checkbox(
                trait,
                value=trait in def_selected_traits,
                key=f"profile_trait_{account_key}_{trait_idx}",
            ):
                selected_traits.append(trait)

    custom_trait = st.text_input(
        "📝 其他學習狀況（選填）",
        value=def_custom_trait,
        placeholder="例如：容易看錯題目中的單位",
        key=f"profile_custom_trait_{account_key}",
    )

    final_traits = selected_traits.copy()
    if custom_trait.strip():
        final_traits.append(custom_trait.strip())

    if final_traits:
        st.info("✅ 已選學習狀況：" + "、".join(final_traits))
    else:
        st.caption("目前尚未選擇學習狀況。")

    st.markdown("#### 🌟 學生有興趣的事物")
    st.caption("先點分類頁籤，再直接勾選喜歡的項目；不需要開啟下拉選單。")

    all_catalog_interests = {
        item
        for category_items in interests_catalog.values()
        for item in category_items
    }
    def_catalog_interests = {
        item for item in def_interests if item in all_catalog_interests
    }
    def_custom_interests = [
        item for item in def_interests if item not in all_catalog_interests
    ]

    cat_tabs = st.tabs(list(interests_catalog.keys()))
    all_interests = []
    for cat_idx, cat_name in enumerate(interests_catalog.keys()):
        with cat_tabs[cat_idx]:
            category_selected = []
            interest_columns = st.columns(3)
            for item_idx, item in enumerate(interests_catalog[cat_name]):
                with interest_columns[item_idx % 3]:
                    if st.checkbox(
                        item,
                        value=item in def_catalog_interests,
                        key=f"profile_interest_{account_key}_{cat_idx}_{item_idx}",
                    ):
                        category_selected.append(item)
                        all_interests.append(item)
            st.session_state["interest_selections"][cat_name] = category_selected

    custom_interest_default = "、".join(def_custom_interests)
    custom_interest = st.text_input(
        "其他個人興趣喜好（選填）",
        value=custom_interest_default,
        placeholder="例如：恐龍、烘焙、火車",
        key=f"profile_custom_interest_{account_key}",
    )
    st.session_state["custom_interest"] = custom_interest

    final_interests = all_interests.copy()
    if custom_interest.strip():
        final_interests.append(custom_interest.strip())

    if final_interests:
        st.success("🎯 已選興趣：" + "、".join(final_interests))
    else:
        st.caption("目前尚未選擇興趣。")

    st.markdown("---")

    if is_verified:
        if st.button("💾 儲存資料並進入系統", type="primary", use_container_width=True):
            if not last_n.strip() or not first_n.strip():
                st.error("⚠️ 請完整填寫學生的「姓氏」與「名字」！")
            elif not school_name.strip():
                st.error("⚠️ 請填寫學生的「就讀學校」！")
            else:
                current_year = date.today().year
                requested_name_changed = (
                    name_identity_locked
                    and (
                        last_n.strip() != profile_control.get("locked_last_name", "")
                        or first_n.strip() != profile_control.get("locked_first_name", "")
                    )
                )
                requested_grade_version_changed = (
                    identity_locked
                    and (
                        selected_grade != profile_control.get("grade", def_grade)
                        or selected_version != profile_control.get("version", def_ver)
                    )
                )

                if requested_name_changed and not st.session_state.get("developer_mode", False):
                    st.error(
                        "姓名已綁定此學習履歷，不能自行更換。"
                        "若確實填錯，請聯絡管理員協助更正。"
                    )
                    st.stop()

                if (
                    requested_grade_version_changed
                    and grade_version_remaining <= 0
                    and not st.session_state.get("developer_mode", False)
                ):
                    st.error("本年度年級與版本的 2 次調整額度已用完。")
                    st.stop()

                if not name_identity_locked:
                    profile_control.update({
                        "email": profile_account_source,
                        "identity_locked": True,
                        "locked_last_name": last_n.strip(),
                        "locked_first_name": first_n.strip(),
                        "grade": selected_grade,
                        "version": selected_version,
                        "change_year": current_year,
                        "change_count": 0,
                    })
                elif requested_grade_version_changed:
                    if int(profile_control.get("change_year") or current_year) != current_year:
                        profile_control["change_year"] = current_year
                        profile_control["change_count"] = 0
                    profile_control["change_count"] = int(
                        profile_control.get("change_count") or 0
                    ) + 1
                    profile_control["grade"] = selected_grade
                    profile_control["version"] = selected_version

                save_profile_control(profile_control)

                st.session_state["user_profile"]["last_name"] = last_n.strip()
                st.session_state["user_profile"]["first_name"] = first_n.strip()
                st.session_state["user_profile"]["city"] = selected_city
                st.session_state["user_profile"]["district"] = selected_district
                st.session_state["user_profile"]["school"] = school_name.strip()
                st.session_state["user_profile"]["grade"] = selected_grade
                st.session_state["user_profile"]["version"] = selected_version
                st.session_state["user_profile"]["discovery_source"] = source_type_selection
                st.session_state["user_profile"]["source_detail"] = (
                    source_detail_input or source_value_input
                )
                st.session_state["user_profile"]["traits"] = final_traits
                st.session_state["user_profile"]["interests"] = final_interests
                
                save_recent_email(st.session_state["user_profile"]["email"])
                save_user_profile_to_db(st.session_state["user_profile"])
                finalize_registration_source()
                st.session_state["setup_complete"] = True
                st.rerun()
        if st.button(
            "🔄 切換登入帳號（直接回 Email 登入頁）",
            use_container_width=True,
        ):
            previous_email = st.session_state["user_profile"].get("email", "")
            clear_private_beta_auth_session()
            clear_profile_widget_state(previous_email)
            reset_user_profile_for_new_account("", credits=30)
            st.session_state["is_verified"] = False
            st.session_state["otp_sent"] = False
            st.session_state["pending_email"] = ""
            st.session_state["loaded_profile_email"] = ""
            st.session_state["wallet_synced_email"] = ""
            st.session_state["developer_mode"] = False
            st.session_state["is_new_account_registration"] = False
            st.session_state["registration_source_result"] = ""
            st.session_state["setup_complete"] = False
            request_page_top()
            st.rerun()

# ==========================================
# 第二頁：主系統畫面
# ==========================================
elif st.session_state["setup_complete"]:
    render_requested_page_top()
    sync_wallet_balance_to_session()
    render_system_tipbar()
    restore_retry_state_to_session()

    wallet_notice = st.session_state.pop(
        "wallet_last_message",
        "",
    )
    if wallet_notice:
        st.info(wallet_notice)

    source_result_notice = st.session_state.pop(
        "registration_source_result",
        "",
    )
    if source_result_notice:
        if "|" in source_result_notice:
            notice_type, notice_message = source_result_notice.split("|", 1)
            if notice_type == "success":
                st.success(notice_message)
            elif notice_type == "warning":
                st.warning(notice_message)
            elif notice_type == "error":
                st.error(notice_message)
            else:
                st.info(notice_message)
        else:
            st.success(source_result_notice)

    if (
        st.session_state["user_profile"].get("source_reward_status")
        == "retry_allowed"
    ):
        st.info(
            "推薦／優惠資料尚未通過驗證。您可以使用同一個測試帳號反覆修改，"
            "直到驗證成功為止。"
        )
        if st.button(
            "🔄 重新填寫推薦／優惠資料",
            key="retry_registration_source_from_main",
            use_container_width=True,
        ):
            st.session_state["setup_complete"] = False
            st.session_state["is_trial"] = False
            st.session_state["is_new_account_registration"] = True
            st.session_state["source_edit_mode"] = True
            st.session_state["registration_source_result"] = ""
            request_page_top()
            st.rerun()

    is_trial = st.session_state.get("is_trial", False)

    current_main_tab = apply_pending_main_tab(
        st.session_state,
        MAIN_TAB_LABELS,
    )

    with st.container(key="main_nav_desktop"):
        nav_columns = st.columns(5)
        for nav_index, (nav_col, tab_label, button_label) in enumerate(
            zip(
                nav_columns,
                MAIN_TAB_LABELS,
                MAIN_NAV_BUTTON_LABELS,
            )
        ):
            with nav_col:
                is_active_tab = (
                    st.session_state["main_tabs_control"] == tab_label
                )
                st.button(
                    button_label,
                    key=f"main_nav_button_{nav_index}",
                    type="primary" if is_active_tab else "secondary",
                    use_container_width=True,
                    on_click=switch_main_tab,
                    args=(tab_label,),
                )

    current_main_tab = st.session_state["main_tabs_control"]
    if (
        st.session_state.get("mobile_main_nav_selector")
        not in MAIN_TAB_LABELS
        or st.session_state.get("mobile_main_nav_selector")
        != current_main_tab
    ):
        st.session_state["mobile_main_nav_selector"] = current_main_tab

    with st.container(key="main_nav_mobile"):
        st.markdown("**📱 功能選單（共 5 項），點選下拉選擇功能**")
        st.selectbox(
            "選擇功能",
            MAIN_TAB_LABELS,
            key="mobile_main_nav_selector",
            on_change=switch_main_tab_from_mobile,
            label_visibility="collapsed",
        )
        st.markdown(
            """
            <div class="mathai-mobile-guide" style="margin-bottom:0;">
                點擊左上方雙箭頭，可以回饋問題增加免費點數、儲值點數；
                旋轉成橫向畫面，可更方便查看試卷與較寬的內容。
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div class='main-nav-content-spacer'></div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(
        MAIN_TAB_LABELS,
        key="main_tabs_control",
        on_change="rerun",
    )
    (
        tab_scan,
        tab_back,
        tab_learning,
        tab_diag,
        tab_custom,
    ) = tabs
    learning_runtime = current_learning_runtime()
    with tab_back:
        st.subheader("🏠 帳號與個人化設定")
        if st.session_state.get("developer_mode", False):
            st.info(
                "🧪 開發者模式可回資料頁修改年級／教材版本；"
                "切換帳號則會直接回到 Email 登入頁。"
            )
        else:
            st.info(
                "需要修改學生資料時，回到資料頁即可；"
                "需要換另一個 Email 時，請直接使用「切換登入帳號」。"
            )

        account_col1, account_col2 = st.columns(2)
        with account_col1:
            if st.button(
                "✏️ 修改學生資料／推薦資料",
                type="primary",
                use_container_width=True,
                key="account_edit_profile",
            ):
                st.session_state["setup_complete"] = False
                st.session_state["is_trial"] = False
                if (
                    st.session_state["user_profile"].get("source_reward_status")
                    == "retry_allowed"
                ):
                    st.session_state["is_new_account_registration"] = True
                request_page_top()
                st.rerun()

        with account_col2:
            if st.button(
                "🔄 切換登入帳號（直接回 Email 登入頁）",
                use_container_width=True,
                key="account_direct_logout",
            ):
                previous_email = st.session_state["user_profile"].get("email", "")
                clear_private_beta_auth_session()
                clear_profile_widget_state(previous_email)
                reset_user_profile_for_new_account("", credits=30)
                st.session_state["is_verified"] = False
                st.session_state["otp_sent"] = False
                st.session_state["pending_email"] = ""
                st.session_state["loaded_profile_email"] = ""
                st.session_state["wallet_synced_email"] = ""
                st.session_state["developer_mode"] = False
                st.session_state["is_new_account_registration"] = False
                st.session_state["registration_source_result"] = ""
                st.session_state["setup_complete"] = False
                st.session_state["is_trial"] = False
                request_page_top()
                st.rerun()

    with tab_learning:
        if LEARNING_MAP_AVAILABLE and render_learning_map is not None:
            render_learning_map(
                st.session_state["user_profile"],
                is_trial=is_trial,
                learning_runtime=learning_runtime,
            )
        else:
            st.error("學習地圖模組尚未安裝，請確認 learning_map.py 已放在 app.py 同一個資料夾。")

    with tab_scan:
        st.subheader("📝 步驟一：上傳照片與解析")
        
        st.markdown(
            "<div style='background-color: #f0f7ff; padding: 12px 16px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 15px; font-size: 14px; line-height: 1.6;'>"
            "✍️ <b>上傳考卷照片：</b><br>"
            "• 請確保照片清晰，系統將自動擷取題目內容。<br>"
            "• 💡 <b>提示：如果需要指定特定錯題，建議在拍照前先用實體紅筆將要問的題目「打叉」、「畫線圈記」，或保留「空白未寫」，AI 即可優先精準擷取！</b><br>"
            "• 如果是試用帳號，系統會擷取前 5 題進行免費試用展示！"
            "</div>",
            unsafe_allow_html=True
        )

        scan_input_mode = st.radio(
            "錯題圖片來源：",
            ["📂 從相簿／檔案上傳", "📷 直接拍照"],
            horizontal=True,
            key="scan_image_input_mode",
        )
        if scan_input_mode == "📷 直接拍照":
            st.caption("手機可直接開啟相機拍攝；如有第二頁，可再拍第二張（選填）。")
            camera_file_1 = st.camera_input("📷 拍攝錯題照片", key="scan_camera_1")
            camera_file_2 = st.camera_input("📷 拍攝第二張（選填）", key="scan_camera_2")
            uploaded_files = collect_image_inputs(
                (camera_file_1, camera_file_2),
                limit=2,
            )
        else:
            uploaded_files = collect_image_inputs(
                st.file_uploader(
                    "📂 上傳錯題照片 (最多支援 2 張)",
                    type=["jpg", "png", "jpeg"],
                    accept_multiple_files=True,
                    key="scan_file_upload",
                ),
                limit=2,
            )

        valid_files = uploaded_files
        if uploaded_files and len(uploaded_files) > 2:
            st.warning("⚠️ 您上傳了超過 2 張照片，系統將自動為您保留前 2 張以確保處理品質喔！")
            valid_files = uploaded_files[:2]

        annotated_images = []

        if valid_files:
            st.markdown("#### 📸 已上傳的考卷照片")
            enable_image_fix = st.checkbox("🛠️ 啟用掃描增強 (自動去除灰暗背景)", value=True)

            mark_mode = st.radio(
                "圖片處理方式：",
                ["整張辨識", "圈選標註後辨識"],
                horizontal=True,
                help="圈選模式使用雲端穩定的點選標註：矩形框請依序點左上角與右下角；圓形標記只需點一下。",
            )

            if mark_mode == "圈選標註後辨識":
                if IMAGE_COORDINATES_AVAILABLE:
                    st.info(
                        "框選題目：選擇「矩形框選」後，在圖片上依序點選題目的左上角與右下角。"
                        "也可以選擇「圓形標記」，直接點一下要強調的位置。"
                    )
                    tool_col1, tool_col2, tool_col3, tool_col4 = st.columns([1.2, 1, 1, 1])
                    with tool_col1:
                        annotation_tool = st.selectbox(
                            "標註工具",
                            ["矩形框選", "圓形標記"],
                            index=0,
                            key="cloud_annotation_tool",
                        )
                    with tool_col2:
                        stroke_width = st.slider(
                            "線條粗細", 2, 20, 6, key="cloud_annotation_width"
                        )
                    with tool_col3:
                        stroke_color = st.color_picker(
                            "標註顏色", "#FF0000", key="cloud_annotation_color"
                        )
                    with tool_col4:
                        circle_radius = st.slider(
                            "圓形半徑", 15, 120, 45, key="cloud_annotation_radius"
                        )
                else:
                    st.warning(
                        "尚未安裝雲端圖片點選元件，暫時以原圖顯示。"
                        "請更新 requirements.txt 並重新部署。"
                    )

            # 圖片採上下排列，手機與電腦皆較容易操作。
            for idx, img_f in enumerate(valid_files):
                st.caption(f"錯題照片 {idx + 1}")
                source_bytes = image_bytes(img_f)
                image_id = hashlib.sha256(source_bytes).hexdigest()[:16]
                raw_img = load_rgb_image(img_f)

                if enable_image_fix and PIL_AVAILABLE:
                    enhancer = ImageEnhance.Contrast(raw_img)
                    raw_img = enhancer.enhance(1.4)

                if mark_mode == "圈選標註後辨識" and IMAGE_COORDINATES_AVAILABLE:
                    max_display_width = 900
                    scale = min(1.0, max_display_width / max(raw_img.width, 1))
                    display_width = max(320, int(raw_img.width * scale))
                    display_height = max(200, int(raw_img.height * scale))
                    display_img = raw_img.resize(
                        (display_width, display_height), Image.Resampling.LANCZOS
                    )

                    boxes_key = f"annotation_shapes_{image_id}"
                    pending_key = f"annotation_pending_{image_id}"
                    event_key = f"annotation_last_event_{image_id}"
                    version_key = f"annotation_version_{image_id}"

                    if boxes_key not in st.session_state:
                        st.session_state[boxes_key] = []
                    if pending_key not in st.session_state:
                        st.session_state[pending_key] = None
                    if event_key not in st.session_state:
                        st.session_state[event_key] = None
                    if version_key not in st.session_state:
                        st.session_state[version_key] = 0

                    preview_img = display_img.copy()
                    preview_draw = ImageDraw.Draw(preview_img)

                    for shape in st.session_state[boxes_key]:
                        shape_type = shape.get("type")
                        coords = shape.get("coords", [])
                        color = shape.get("color", "#FF0000")
                        width = int(shape.get("width", 6))
                        if shape_type == "rect" and len(coords) == 4:
                            preview_draw.rectangle(coords, outline=color, width=width)
                        elif shape_type == "ellipse" and len(coords) == 4:
                            preview_draw.ellipse(coords, outline=color, width=width)

                    pending_point = st.session_state[pending_key]
                    if pending_point and annotation_tool == "矩形框選":
                        x, y = pending_point
                        marker_r = max(5, stroke_width + 2)
                        preview_draw.ellipse(
                            [x - marker_r, y - marker_r, x + marker_r, y + marker_r],
                            fill=stroke_color,
                            outline=stroke_color,
                        )
                        st.caption("已選取第一點，請再點題目範圍的另一個對角。")

                    click_value = streamlit_image_coordinates(
                        preview_img,
                        key=(
                            f"exam_click_image_{idx}_{image_id}_"
                            f"{st.session_state[version_key]}"
                        ),
                    )

                    if click_value:
                        click_x = int(click_value.get("x", 0))
                        click_y = int(click_value.get("y", 0))
                        event_signature = (
                            click_x,
                            click_y,
                            click_value.get("unix_time"),
                        )

                        if event_signature != st.session_state[event_key]:
                            st.session_state[event_key] = event_signature

                            if annotation_tool == "矩形框選":
                                if st.session_state[pending_key] is None:
                                    st.session_state[pending_key] = (click_x, click_y)
                                else:
                                    x1, y1 = st.session_state[pending_key]
                                    left, right = sorted((x1, click_x))
                                    top, bottom = sorted((y1, click_y))
                                    if right - left >= 5 and bottom - top >= 5:
                                        st.session_state[boxes_key].append({
                                            "type": "rect",
                                            "coords": [left, top, right, bottom],
                                            "color": stroke_color,
                                            "width": stroke_width,
                                        })
                                    st.session_state[pending_key] = None
                                st.rerun()
                            else:
                                radius = int(circle_radius)
                                st.session_state[boxes_key].append({
                                    "type": "ellipse",
                                    "coords": [
                                        max(0, click_x - radius),
                                        max(0, click_y - radius),
                                        min(display_width - 1, click_x + radius),
                                        min(display_height - 1, click_y + radius),
                                    ],
                                    "color": stroke_color,
                                    "width": stroke_width,
                                })
                                st.rerun()

                    control_col1, control_col2, control_col3 = st.columns(3)
                    with control_col1:
                        if st.button(
                            "↩️ 復原上一個標記",
                            key=f"undo_annotation_{image_id}",
                            use_container_width=True,
                        ):
                            if st.session_state[pending_key] is not None:
                                st.session_state[pending_key] = None
                            elif st.session_state[boxes_key]:
                                st.session_state[boxes_key].pop()
                            st.session_state[version_key] += 1
                            st.rerun()
                    with control_col2:
                        if st.button(
                            "🧹 清除本張標記",
                            key=f"clear_annotation_{image_id}",
                            use_container_width=True,
                        ):
                            st.session_state[boxes_key] = []
                            st.session_state[pending_key] = None
                            st.session_state[version_key] += 1
                            st.rerun()
                    with control_col3:
                        st.metric("目前標記數", len(st.session_state[boxes_key]))

                    # 將顯示座標等比例換算回原始解析度，供 AI 讀取。
                    annotated_original = raw_img.copy()
                    original_draw = ImageDraw.Draw(annotated_original)
                    x_ratio = raw_img.width / max(display_width, 1)
                    y_ratio = raw_img.height / max(display_height, 1)

                    for shape in st.session_state[boxes_key]:
                        coords = shape.get("coords", [])
                        if len(coords) != 4:
                            continue
                        scaled_coords = [
                            int(coords[0] * x_ratio),
                            int(coords[1] * y_ratio),
                            int(coords[2] * x_ratio),
                            int(coords[3] * y_ratio),
                        ]
                        scaled_width = max(
                            2,
                            int(shape.get("width", 6) * max(x_ratio, y_ratio)),
                        )
                        if shape.get("type") == "ellipse":
                            original_draw.ellipse(
                                scaled_coords,
                                outline=shape.get("color", "#FF0000"),
                                width=scaled_width,
                            )
                        else:
                            original_draw.rectangle(
                                scaled_coords,
                                outline=shape.get("color", "#FF0000"),
                                width=scaled_width,
                            )

                    annotated_images.append(annotated_original)
                else:
                    st.image(raw_img, use_container_width=True)
                    annotated_images.append(raw_img)

            if mark_mode == "圈選標註後辨識" and IMAGE_COORDINATES_AVAILABLE:
                st.success(
                    "標註完成後，請按下方「開始免費辨識文字」。"
                    "AI 會優先辨識紅色矩形或圓形標記附近的題目。"
                )

        def perform_ai_scan(files, mode="normal"):
            """辨識考卷；失敗時切換人工輸入，且不消耗試用次數。"""
            client_ip = get_client_ip()
            ip_today_key = f"{today_str}_{client_ip}"
            current_ip_trials = st.session_state["ip_trial_history"].get(ip_today_key, 0)

            if is_trial and current_ip_trials >= 1:
                show_trial_conversion_notice()
                return False

            if not PIL_AVAILABLE:
                st.session_state["scan_manual_mode"] = True
                st.session_state["scan_error_code"] = "PIL_NOT_AVAILABLE"
                st.session_state["scan_error_message"] = "系統目前無法開啟圖片，請直接輸入錯題文字。"
                return False

            try:
                if mode == "loose":
                    prompt = (
                        "你是一個資深的數學老師與考卷辨識專家。\n"
                        "請精準辨識圖片中的數學題目，保留完整公式與符號。\n"
                        f"{MATH_OUTPUT_RULES}\n"
                        "若圖片上有使用者後加的紅色圈選、方框、畫線或打叉，請將被標記的題目視為最高優先。\n"
                        "優先擷取有紅筆加註、留白、打叉或訂正痕跡的題目。\n"
                        "打勾（✓）通常代表答對，請不要列入。\n"
                        "第一行請先輸出格式：[[SCOPE|grade=推測年級|version=推測版本或無法判定|confidence=高中低]]。\n"
                        "從第二行開始只輸出錯題文字，不要加入其他說明。\n"
                    )
                else:
                    prompt = (
                        "你是一個資深的數學老師與考卷辨識專家。\n"
                        "請精準辨識圖片中的數學題目，保留完整公式與符號。\n"
                        f"{MATH_OUTPUT_RULES}\n"
                        "若圖片上有使用者後加的紅色圈選、方框、畫線或打叉，請將被標記的題目視為最高優先。\n"
                        "只擷取有紅筆加註、留白或打叉（X）的題目。\n"
                        "打勾（✓）代表答對，請絕對不要列入。\n"
                        "第一行請先輸出格式：[[SCOPE|grade=推測年級|version=推測版本或無法判定|confidence=高中低]]。\n"
                        "從第二行開始只輸出錯題文字，不要加入其他說明。\n"
                    )

                if is_trial:
                    prompt += "這是試用請求，最多擷取 5 道符合條件的題目。\n"

                contents = [prompt]
                images_to_send = (
                    annotated_images
                    if annotated_images
                    else [load_rgb_image(f) for f in files]
                )
                for image in images_to_send:
                    contents.append(image.convert("RGB"))

                response_text = call_gemini_api(contents)
                if not response_text.strip():
                    raise AIServiceError(
                        code="EMPTY_SCAN_RESULT",
                        user_message="AI 沒有辨識到有效題目，請改用人工輸入模式。",
                    )

                scope_match = re.search(
                    r"^\[\[SCOPE\|grade=(.*?)\|version=(.*?)\|confidence=(.*?)\]\]\s*",
                    response_text.strip(),
                )
                cleaned_response_text = response_text.strip()
                st.session_state["scan_scope_warning"] = ""
                st.session_state["scan_scope_estimate"] = {}

                if scope_match:
                    estimated_grade = scope_match.group(1).strip()
                    estimated_version = scope_match.group(2).strip()
                    estimated_confidence = scope_match.group(3).strip()
                    cleaned_response_text = re.sub(
                        r"^\[\[SCOPE\|grade=.*?\|version=.*?\|confidence=.*?\]\]\s*",
                        "",
                        cleaned_response_text,
                        count=1,
                    ).strip()

                    st.session_state["scan_scope_estimate"] = {
                        "grade": estimated_grade,
                        "version": estimated_version,
                        "confidence": estimated_confidence,
                    }

                    profile_grade = st.session_state["user_profile"].get("grade", "")
                    profile_version = st.session_state["user_profile"].get("version", "")
                    profile_grade_number = re.search(r"(\d+)", profile_grade)
                    estimated_grade_number = re.search(r"(\d+)", estimated_grade)

                    grade_mismatch = (
                        profile_grade_number
                        and estimated_grade_number
                        and profile_grade_number.group(1) != estimated_grade_number.group(1)
                        and estimated_confidence in ["高", "中"]
                    )
                    version_mismatch = (
                        estimated_version
                        and estimated_version != "無法判定"
                        and profile_version
                        and estimated_version not in profile_version
                        and profile_version not in estimated_version
                        and estimated_confidence == "高"
                    )

                    if grade_mismatch or version_mismatch:
                        st.session_state["scan_scope_warning"] = (
                            f"系統推測這份題目屬於「{estimated_grade}／{estimated_version}」，"
                            f"但目前帳號設定是「{profile_grade}／{profile_version}」。"
                            "仍可繼續辨識；若只是臨時替別人查題，建議使用試用模式，"
                            "避免把其他學生內容寫進這個帳號的學習履歷。"
                        )

                st.session_state["scanned_text"] = cleaned_response_text
                st.session_state["manual_scan_text"] = cleaned_response_text
                st.session_state["scan_manual_mode"] = False
                st.session_state["scan_error_message"] = ""
                st.session_state["scan_error_code"] = ""

                if is_trial:
                    st.session_state["ip_trial_history"][ip_today_key] = current_ip_trials + 1
                return True

            except Exception as exc:
                st.session_state["scan_manual_mode"] = True
                st.session_state["scan_error_code"] = get_ai_error_code(exc)
                st.session_state["scan_error_message"] = get_ai_error_message(exc)
                if st.session_state.get("scanned_text", "").strip():
                    st.session_state["manual_scan_text"] = st.session_state["scanned_text"]
                return False

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if valid_files and st.button("🤖 開始免費辨識文字", use_container_width=True):
                with st.spinner("智慧掃描擷取錯題中..."):
                    success = perform_ai_scan(valid_files, "normal")
                if success:
                    st.success("✅ 圖片辨識完成。")
                    st.rerun()

        with col_btn2:
            if valid_files and st.button("🔄 寬鬆認定免費再辨識", use_container_width=True):
                with st.spinner("智慧掃描：尋找紅筆標記、留白與錯題中..."):
                    success = perform_ai_scan(valid_files, "loose")
                if success:
                    st.success("✅ 圖片重新辨識完成。")
                    st.rerun()

        if st.session_state.get("scan_manual_mode", False):
            st.warning("⚠️ " + st.session_state.get(
                "scan_error_message",
                "圖片辨識目前無法使用，請改用人工輸入。",
            ))
            st.info("圖片仍保留在上方。請依照圖片內容輸入或貼上錯題文字，之後仍可繼續解析與出題。")

            manual_text = st.text_area(
                "⌨️ 人工輸入錯題內容",
                value=st.session_state.get("manual_scan_text", ""),
                height=180,
                placeholder="例如：\n1. 解方程式 2x + 5 = 17。\n2. 已知直角三角形兩股長為 3、4，求斜邊長。",
                key="manual_scan_text_input",
            )

            manual_col1, manual_col2 = st.columns(2)
            with manual_col1:
                if st.button("✅ 確認使用這段錯題文字", type="primary", use_container_width=True):
                    cleaned_text = manual_text.strip()
                    if not cleaned_text:
                        st.warning("請先輸入至少一道錯題。")
                    else:
                        st.session_state["scanned_text"] = cleaned_text
                        st.session_state["manual_scan_text"] = cleaned_text
                        st.session_state["scan_manual_mode"] = False
                        st.session_state["scan_error_message"] = ""
                        st.session_state["scan_error_code"] = ""
                        st.success("錯題文字已儲存，可以繼續產生解析與變形題。")
                        st.rerun()

            with manual_col2:
                if st.button("取消人工輸入", use_container_width=True):
                    st.session_state["scan_manual_mode"] = False
                    st.session_state["scan_error_message"] = ""
                    st.session_state["scan_error_code"] = ""
                    st.rerun()

        st.markdown("---")
        
        if st.session_state.get("scan_scope_warning"):
            st.warning("⚠️ " + st.session_state["scan_scope_warning"])

        edited_text = st.text_area("確認題目內容 (可在框內直接微調要輸出的錯題)：", value=st.session_state["scanned_text"], height=120)
        st.session_state["scanned_text"] = edited_text

        if edited_text.strip():
            st.markdown("#### 📐 數學符號預覽")
            st.caption("下方是學生實際會看到的數學排版；上方文字框仍可直接修改內容。")
            render_math_content(edited_text)

        st.markdown("### 🎯 步驟三：自動產出解析與模擬試題")
        
        st.markdown("#### 🎯 選擇產出方案")
        selected_mock_plan = st.selectbox("請選擇產出題數與方案：", list(q_count_options.keys()), key="mock_plan")
        mock_q_count = q_count_options[selected_mock_plan]
        
        use_interests_1 = st.checkbox("🌟 模擬試題融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="scan_interest")

        col_mock1, col_mock2 = st.columns(2)
        with col_mock1:
            btn_mock1 = st.button("🚀 執行產出", type="primary", use_container_width=True)
        with col_mock2:
            btn_mock2 = st.button("🔄 重新再出一份", use_container_width=True)

        if btn_mock1 or btn_mock2:
            client_ip = get_client_ip()
            ip_today_key = f"{today_str}_{client_ip}"
            current_ip_trials = st.session_state["ip_trial_history"].get(ip_today_key, 0)

            if not edited_text:
                st.warning("請先輸入或辨識題目！")
            elif deduct_credit(mock_q_count) and GEMINI_KEY:
                if supabase_client and st.session_state["user_profile"]["email"] != "trial@example.com":
                    try:
                        supabase_client.table("user_mistakes_log").insert({
                            "user_email": st.session_state["user_profile"]["email"],
                            "original_mistake": edited_text,
                            "created_at": str(date.today())
                        }).execute()
                    except Exception:
                        pass
                
                with st.spinner("產出中..."):
                    try:
                        db_text = fetch_relevant_questions_from_db([edited_text[:20]], limit=5)
                        
                        limit_prompt = f" (請精準控管題目數量：產出最多 {mock_q_count} 題原錯題解析與改數字模擬題) "
                        
                        prompt_text = "【錯題內容】：\n" + edited_text + "\n\n"
                        prompt_text += "【題庫參考】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_text += f"請為【錯題內容】產出繁體中文的正解與詳細解析，並接著產出{limit_prompt}與詳細解析解答。\n\n"
                        prompt_text += LAYOUT_WITH_ANALYSIS
                        prompt_text += JSON_TEMPLATE_MOCK
                        
                        res_text = call_gemini_api([prompt_text])
                        if res_text:
                            st.session_state["generated_content"] = re.sub(r'```json.*?```', '', res_text, flags=re.DOTALL).strip()
                            parse_and_insert_9_col_json(res_text)
                            record_effective_usage(
                                st.session_state["user_profile"].get("email", ""),
                                "mistake_analysis_exam",
                            )
                            st.success("成功產出！")
                    except Exception as e: handle_api_error(e)
            else:
                show_trial_conversion_notice()

        if st.session_state["generated_content"]:
            render_math_content(st.session_state["generated_content"])
            render_share_buttons(st.session_state["generated_content"], "scan_res")
            
            st.markdown("---")
            st.subheader("🚀 步驟四：疊代升級 (變形題)")
            
            st.markdown("#### 🎯 選擇變形方案")
            selected_var_plan = st.selectbox("請選擇變形題數與方案：", list(q_count_options.keys()), key="var_plan")
            var_q_count = q_count_options[selected_var_plan]
            
            use_interests_var = st.checkbox("🌟 變形題融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="var_interest")

            c_var1, c_var2 = st.columns(2)
            with c_var1: btn_var1 = st.button("產出變形題", use_container_width=True)
            with c_var2: btn_var2 = st.button("🔄 重新產出不同變形題", use_container_width=True)
            
            if btn_var1 or btn_var2:
                if deduct_credit(var_q_count) and GEMINI_KEY:
                    with st.spinner("產出變形題中..."):
                        db_text = fetch_relevant_questions_from_db([edited_text[:30]], limit=10)
                        
                        prompt_var = "錯題內容：\n" + edited_text + "\n\n"
                        prompt_var += "【題庫優先使用】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_var += f"請產出 {var_q_count} 題變形試題。\n\n"
                        prompt_var += LAYOUT_NORMAL
                        prompt_var += JSON_TEMPLATE_VAR
                        
                        try:
                            res_text = call_gemini_api([prompt_var])
                            st.session_state["variation_content"] = re.sub(r'```json.*?```', '', res_text, flags=re.DOTALL).strip()
                            parse_and_insert_9_col_json(res_text)
                            record_effective_usage(
                                st.session_state["user_profile"].get("email", ""),
                                "variation_exam",
                            )
                        except Exception as e: handle_api_error(e)
                else:
                    show_trial_conversion_notice()
                        
            if st.session_state.get("variation_content"):
                st.markdown("### 🌟 變形試卷")
                render_math_content(st.session_state["variation_content"])
                render_share_buttons(st.session_state["variation_content"], "var_res")

    with tab_custom:
        st.subheader("⚙️ 自組試卷系統 🔒")
        st.caption("依學生年級、教材版本、主單元、次單元與題型產生專屬試卷。")

        st.info(
            "🔁 **更省事的方式：錯題迭代訓練**  \n"
            "把之前由系統產生、學生已作答並用紅筆批改的考卷拍照上傳。"
            "系統會辨識錯題、空白題與常見錯誤，直接產生下一份最適合的練習，"
            "不必每次重新選單元與題型。"
        )

        if is_trial:
            show_trial_conversion_notice()
        else:
            user_profile = st.session_state["user_profile"]
            user_ver = user_profile.get("version", "康軒版")
            user_gr = user_profile.get("grade", "8年級(國二)")

            custom_exam_profile_signature = f"{user_gr}|{user_ver}"
            if (
                st.session_state.get("custom_exam_profile_signature")
                != custom_exam_profile_signature
            ):
                for state_key in (
                    "custom_exam_main_units",
                    "custom_exam_subunits",
                    "custom_exam_topics",
                    "custom_exam_question_types",
                ):
                    st.session_state.pop(state_key, None)
                st.session_state[
                    "custom_exam_profile_signature"
                ] = custom_exam_profile_signature

            st.info(f"目前學生設定：**{user_gr}｜{user_ver}**")

            # 第一步：主單元
            st.markdown("### 1️⃣ 選擇出題範圍")
            if LEARNING_MAP_AVAILABLE and get_unit_names_for_profile is not None:
                unit_options = get_unit_names_for_profile(user_profile)
            else:
                unit_options = [
                    "數與量",
                    "計算與代數",
                    "分數與小數",
                    "比與比例",
                    "幾何與測量",
                    "統計與機率",
                    "生活應用與跨單元",
                ]

            sanitize_multiselect_state("custom_exam_main_units", unit_options)
            selected_mains = st.multiselect(
                f"主單元（{user_ver}，可複選）",
                unit_options,
                key="custom_exam_main_units",
                placeholder="請先選擇主單元",
            )

            # 第二步：次單元，嚴格依主單元連動
            if selected_mains and LEARNING_MAP_AVAILABLE and get_subunit_names_for_units is not None:
                subunit_options = get_subunit_names_for_units(
                    user_profile,
                    selected_mains,
                )
            else:
                subunit_options = []

            sanitize_multiselect_state("custom_exam_subunits", subunit_options)
            selected_subunits = st.multiselect(
                "次單元（依上方主單元連動）",
                subunit_options,
                key="custom_exam_subunits",
                placeholder="請先選擇主單元" if not selected_mains else "請選擇次單元",
                disabled=not selected_mains,
            )
            if selected_mains and not subunit_options:
                st.info("此年級／版本／主單元的次單元資料正在校對，暫不顯示通用假選項。")

            # 第三步：學習重點，嚴格依次單元連動
            if selected_subunits and LEARNING_MAP_AVAILABLE and get_topic_names_for_subunits is not None:
                topic_options = get_topic_names_for_subunits(
                    user_profile,
                    selected_subunits,
                )
            else:
                topic_options = []

            sanitize_multiselect_state("custom_exam_topics", topic_options)
            selected_topics = st.multiselect(
                "學習重點（依上方次單元連動）",
                topic_options,
                key="custom_exam_topics",
                placeholder="可不選；不選時由系統平均出題",
                disabled=not selected_subunits,
            )

            st.markdown("### 2️⃣ 選擇題型與難度")

            if selected_subunits and LEARNING_MAP_AVAILABLE and get_classic_question_type_names_for_units is not None:
                classic_type_options = get_classic_question_type_names_for_units(
                    user_profile,
                    selected_subunits,
                )
            else:
                classic_type_options = []

            sanitize_multiselect_state("custom_exam_question_types", classic_type_options)
            if classic_type_options:
                selected_question_types = st.multiselect(
                    "細部題型（依次單元連動，可複選）",
                    classic_type_options,
                    key="custom_exam_question_types",
                    placeholder="可不選；不選時由系統混合出題",
                )
            else:
                selected_question_types = []
                if selected_subunits:
                    st.caption("此範圍的細部題型尚未完成校對，因此暫時不顯示。")

            difficulty_options = ["基礎", "標準", "進階", "挑戰"]
            sanitize_multiselect_state(
                "custom_exam_difficulties",
                difficulty_options,
            )
            if not st.session_state.get("custom_exam_difficulties"):
                st.session_state["custom_exam_difficulties"] = ["標準"]

            selected_difficulties = st.multiselect(
                "難度（可複選）",
                difficulty_options,
                key="custom_exam_difficulties",
                help="例如同時選擇「標準」與「進階」，系統會混合兩種難度。",
            )
            difficulty = "、".join(selected_difficulties) if selected_difficulties else "標準"

            col_format1, col_format2 = st.columns(2)
            with col_format1:
                pack_label = st.selectbox(
                    "題數與點數",
                    list(q_count_options.keys()),
                    index=0,
                    key="custom_exam_pack",
                )
            display_q = q_count_options[pack_label]
            req_pts = get_required_credits(display_q)

            format_presets = {
                5: {
                    "混合題型：2 選擇＋1 填空＋2 計算": (2, 1, 2),
                    "全計算題：5 計算": (0, 0, 5),
                    "觀念練習：3 選擇＋2 填空": (3, 2, 0),
                },
                10: {
                    "混合題型：4 選擇＋3 填空＋3 計算": (4, 3, 3),
                    "計算加強：2 選擇＋2 填空＋6 計算": (2, 2, 6),
                    "觀念練習：6 選擇＋4 填空": (6, 4, 0),
                },
                15: {
                    "混合題型：5 選擇＋5 填空＋5 計算": (5, 5, 5),
                    "計算加強：3 選擇＋3 填空＋9 計算": (3, 3, 9),
                    "觀念練習：9 選擇＋6 填空": (9, 6, 0),
                },
                20: {
                    "混合題型：7 選擇＋6 填空＋7 計算": (7, 6, 7),
                    "計算加強：4 選擇＋4 填空＋12 計算": (4, 4, 12),
                    "觀念練習：12 選擇＋8 填空": (12, 8, 0),
                },
            }

            with col_format2:
                format_label = st.selectbox(
                    "題目配置",
                    list(format_presets[display_q].keys()),
                    key=f"custom_exam_format_{display_q}",
                )

            mc_cnt, fill_cnt, calc_cnt = format_presets[display_q][format_label]

            st.markdown("### 3️⃣ 確認本次試卷")
            summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
            summary_col1.metric("總題數", f"{display_q} 題")
            summary_col2.metric("難度", difficulty)
            summary_col3.metric("題型配置", f"{mc_cnt}/{fill_cnt}/{calc_cnt}")
            summary_col4.metric("需要點數", f"{req_pts} 點")

            with st.expander("查看完整出題設定", expanded=True):
                st.markdown(f"**主單元：** {'、'.join(selected_mains) if selected_mains else '尚未選擇'}")
                st.markdown(f"**次單元：** {'、'.join(selected_subunits) if selected_subunits else '尚未選擇'}")
                st.markdown(f"**學習重點：** {'、'.join(selected_topics) if selected_topics else '系統平均分配'}")
                st.markdown(f"**細部題型：** {'、'.join(selected_question_types) if selected_question_types else '系統混合題型'}")
                st.markdown(
                    f"**題目配置：** 選擇題 {mc_cnt} 題、填空題 {fill_cnt} 題、計算題 {calc_cnt} 題"
                )

            current_credits = user_profile.get("credits", 0)
            if current_credits < req_pts:
                st.warning(f"目前只有 {current_credits} 點，本次需要 {req_pts} 點。")

            generate_col, clear_col = st.columns([2, 1])
            with generate_col:
                btn_generate = st.button(
                    f"✨ 產生 {display_q} 題自組試卷（扣 {req_pts} 點）",
                    type="primary",
                    use_container_width=True,
                    disabled=current_credits < req_pts,
                )
            with clear_col:
                btn_clear = st.button(
                    "清除目前試卷",
                    use_container_width=True,
                )

            if btn_clear:
                st.session_state["custom_exam_content"] = ""
                st.session_state["custom_exam_last_summary"] = {}
                st.rerun()

            if btn_generate:
                if not selected_mains:
                    st.warning("請先選擇至少一個主單元。")
                elif not selected_subunits:
                    st.warning("請先選擇至少一個次單元。")
                else:
                    # 只在資料完整且點數足夠時扣點
                    if deduct_credit(display_q):
                        with st.spinner("正在依照教材範圍智慧組卷，請稍候…"):
                            main_topics_str = "、".join(selected_mains)
                            subunit_topics_str = "、".join(selected_subunits)
                            topic_str = "、".join(selected_topics) if selected_topics else "由系統平均分配"
                            type_str = "、".join(selected_question_types) if selected_question_types else "混合題型"
                            search_keywords = selected_mains + selected_subunits + selected_topics
                            db_text = fetch_relevant_questions_from_db(
                                search_keywords,
                                limit=max(20, display_q * 2),
                            )

                            prompt_custom = f"""
你是臺灣數學教師與試卷命題專家。請依照以下設定產生一份可直接給學生作答的數學試卷。

【學生與教材】
年級：{user_gr}
教材版本：{user_ver}

【出題範圍】
主單元：{main_topics_str}
次單元：{subunit_topics_str}
學習重點：{topic_str}
指定細部題型：{type_str}
難度：{difficulty}

【題數配置】
總題數：{display_q}
選擇題：{mc_cnt}
填空題：{fill_cnt}
計算題：{calc_cnt}

【系統題庫參考】
{db_text if db_text else "(目前沒有可用的系統題庫資料，請由 AI 依教材範圍補足)"}

【必要規則】
1. 題目只能出現在本次選定的主單元、次單元與學習重點內，不可跨越未選範圍。
2. 題目難度必須符合「{difficulty}」。
3. 嚴格符合選擇題、填空題、計算題的數量。
4. 選擇題每題提供四個選項。
5. 每題都要有標準答案與簡潔解析。
6. 題庫題只能作為參考，請調整數字、敘述或情境，避免直接複製。
7. 先輸出「學生作答卷」，再輸出「答案與解析」。
8. 使用繁體中文，數學符號清楚，題號連續。
"""

                            prompt_custom += "\n" + LAYOUT_NORMAL
                            prompt_custom += "\n" + JSON_TEMPLATE_CUSTOM.replace(
                                "UNIT_PLACEHOLDER",
                                main_topics_str,
                            )

                            custom_ai_succeeded = False
                            try:
                                # 只把真正的 Gemini 呼叫放在 try/except 內。
                                res_text = call_gemini_api([prompt_custom])
                                custom_ai_succeeded = True
                            except Exception as e:
                                # 只有 Gemini 真正失敗才退款。
                                add_user_credits(
                                    st.session_state["user_profile"].get("email", ""),
                                    req_pts,
                                    reason="ai_usage_refund",
                                    reference_type="custom_exam_refund",
                                    reference_id=str(uuid.uuid4()),
                                )
                                handle_api_error(e)

                            if custom_ai_succeeded:
                                final_custom_content = re.sub(
                                    r"```json.*?```",
                                    "",
                                    res_text,
                                    flags=re.DOTALL,
                                ).strip()

                                st.session_state["custom_exam_content"] = final_custom_content
                                st.session_state["custom_exam_last_summary"] = {
                                    "grade": user_gr,
                                    "version": user_ver,
                                    "main_units": selected_mains,
                                    "subunits": selected_subunits,
                                    "topics": selected_topics,
                                    "question_types": selected_question_types,
                                    "difficulty": difficulty,
                                    "question_count": display_q,
                                    "points": req_pts,
                                }

                                # 後處理失敗不能冒充 Gemini 失敗。
                                try:
                                    parse_and_insert_9_col_json(res_text)
                                except Exception as post_exc:
                                    st.session_state["custom_exam_postprocess_debug"] = str(post_exc)

                                record_effective_usage(
                                    st.session_state["user_profile"].get("email", ""),
                                    "custom_exam",
                                )
                                st.session_state["wallet_last_message"] = (
                                    "✅ 試卷已產生，點數已扣除。"
                                )

                                # Streamlit rerun 是控制流程，必須放在 AI try/except 外面。
                                st.rerun()
                    else:
                        st.warning("點數不足，請先儲值或調整題數。")

            if st.session_state.get("custom_exam_content"):
                st.markdown("---")
                st.markdown("### 📄 本次自組試卷")
                last_summary = st.session_state.get("custom_exam_last_summary", {})
                if last_summary:
                    st.caption(
                        f"{last_summary.get('grade', '')}｜"
                        f"{last_summary.get('version', '')}｜"
                        f"{last_summary.get('difficulty', '')}｜"
                        f"{last_summary.get('question_count', '')} 題"
                    )

                render_math_content(st.session_state["custom_exam_content"])
                render_share_buttons(
                    st.session_state["custom_exam_content"],
                    "cust_res",
                )

    with tab_diag:
        st.subheader("🧠 學習診斷與累積錯題 🔒")
        st.info(
            "這裡集中顯示累積錯題、常見錯因、弱點單元與下一份推薦練習。"
            "原本的「歷史錯題」已整合到本頁。"
        )

        # Phase 2B 只在本機開發者模式顯示，避免 Pilot 功能誤露出到公開網站。
        if is_local_developer_session():
            if DIAGNOSTIC_PILOT_AVAILABLE and render_diagnostic_pilot is not None:
                try:
                    render_diagnostic_pilot(
                        developer_mode=True,
                        learning_runtime=learning_runtime,
                        learning_map_tab_label=MAIN_TAB_LABELS[2],
                        request_main_tab=request_main_tab,
                    )
                except TypeError as exc:
                    # Streamlit may retain the pre-parameter renderer in sys.modules
                    # until the server process restarts. Keep that one stale signature
                    # usable without hiding unrelated TypeError exceptions.
                    if not any(
                        keyword in str(exc)
                        for keyword in (
                            "unexpected keyword argument 'developer_mode'",
                            "unexpected keyword argument 'request_main_tab'",
                        )
                    ):
                        raise
                    render_diagnostic_pilot()
            else:
                st.warning("初始診斷 Pilot 模組尚未載入。")
            st.info("完成診斷後，請前往「個人學習地圖」查看學習地圖、老師回饋與家長報告。")
            st.markdown("---")
            st.stop()

        if learning_runtime.persistence_enabled:
            if DIAGNOSTIC_PILOT_AVAILABLE and render_diagnostic_pilot is not None:
                render_diagnostic_pilot(
                    developer_mode=False,
                    learning_runtime=learning_runtime,
                    learning_map_tab_label=MAIN_TAB_LABELS[2],
                    request_main_tab=request_main_tab,
                )
            else:
                st.warning("診斷模組目前無法載入，請稍後再試。")
            st.info("完成診斷後，請前往「個人學習地圖」查看學習地圖、老師回饋與家長報告。")
            st.markdown("---")

        if (
            not learning_runtime.persistence_enabled
            and not is_trial
            and not st.session_state.get("developer_mode", False)
        ):
            diag_profile = st.session_state["user_profile"]
            diag_email = diag_profile.get("email", "")
            diag_credits = diag_profile.get("credits", 0)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("目前點數", f"{diag_credits} 點")
            d2.metric("累積錯題", "讀取中")
            d3.metric("優先補強", "待累積資料")
            d4.metric("能力趨勢", "待累積資料")

            st.markdown("### 📌 診斷內容規劃")
            st.markdown(
                "1. 累積錯題與原題紀錄  \n"
                "2. 主單元、次單元與學習重點的錯誤次數  \n"
                "3. 觀念錯誤、計算失誤、題意理解等錯因  \n"
                "4. 基礎、標準、進階能力變化  \n"
                "5. 最需要補強的三個知識點  \n"
                "6. AI 推薦下一份練習與錯題疊代"
            )

        st.markdown("---")
        st.markdown("### 📂 累積錯題與錯題疊代")
        if is_trial:
            show_trial_conversion_notice()
        else:
            user_profile = st.session_state["user_profile"]
            user_ver = user_profile.get("version", "康軒版")
            user_gr = user_profile.get("grade", "8年級(國二)")

            current_exam_profile_signature = f"{user_gr}|{user_ver}"
            previous_exam_profile_signature = st.session_state.get(
                "custom_exam_profile_signature",
                "",
            )
            if previous_exam_profile_signature != current_exam_profile_signature:
                for stale_key in [
                    "custom_exam_main_units",
                    "custom_exam_subunits",
                    "custom_exam_topics",
                    "custom_exam_question_types",
                ]:
                    st.session_state.pop(stale_key, None)
                st.session_state["custom_exam_profile_signature"] = (
                    current_exam_profile_signature
                )

            with st.expander(
                "🔁 上傳紅筆訂正考卷，直接產生下一份練習",
                expanded=False,
            ):
                st.markdown(
                    "請上傳 **1～2 張清楚的考卷照片**。建議老師或家長先用紅筆："
                    "打叉、圈出錯誤、寫上正確答案，或標示空白未作答題。"
                )
                iterative_files = st.file_uploader(
                    "上傳已作答並紅筆批改的考卷",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key="iterative_exam_upload",
                )

                iterative_count = st.selectbox(
                    "下一份練習題數",
                    [5, 10],
                    index=0,
                    key="iterative_exam_count",
                )
                iterative_strategy = st.multiselect(
                    "下一份試卷的出題策略（可複選）",
                    [
                        "針對錯題觀念重新練習",
                        "相同題型更換數字與情境",
                        "加入少量進階題",
                        "複習空白未作答題",
                    ],
                    default=[
                        "針對錯題觀念重新練習",
                        "相同題型更換數字與情境",
                        "加入少量進階題",
                    ],
                    key="iterative_exam_strategy",
                )

                iterative_points = get_required_credits(iterative_count)
                st.caption(
                    f"本次需要 {iterative_points} 點。建議配置："
                    "約 70% 錯題補強＋30% 適度進階。"
                )

                iterative_generate = st.button(
                    f"🧠 分析紅筆考卷並產生下一份（扣 {iterative_points} 點）",
                    type="primary",
                    use_container_width=True,
                    key="iterative_exam_generate",
                    disabled=user_profile.get("credits", 0) < iterative_points,
                )

                if iterative_generate:
                    valid_iterative_files = (iterative_files or [])[:2]
                    if not valid_iterative_files:
                        st.warning("請先上傳至少一張已批改考卷照片。")
                    elif not iterative_strategy:
                        st.warning("請至少選擇一項出題策略。")
                    elif deduct_credit(iterative_count):
                        with st.spinner("正在辨識紅筆批改結果並安排下一階段練習…"):
                            iterative_ai_succeeded = False
                            try:
                                iterative_prompt = f"""
你是臺灣數學教師與錯題診斷專家。請閱讀上傳的學生考卷照片。
照片可能包含學生作答、紅筆打叉、紅筆圈選、教師訂正答案與空白題。

【學生資料】
年級：{user_gr}
教材版本：{user_ver}

【任務】
1. 辨識學生答錯、空白未答、被紅筆圈選或打叉的題目。
2. 推論每一題對應的主單元、次單元、核心觀念與錯誤原因。
3. 先輸出「錯題診斷摘要」，內容包括：
   - 發現的錯題或弱點
   - 可能的錯誤原因
   - 建議優先補強順序
4. 再產生下一份 {iterative_count} 題練習。
5. 出題策略：{'、'.join(iterative_strategy)}
6. 約 70% 題目用於補強本次錯誤，約 30% 題目在學生可負擔範圍內適度進階。
7. 題目不可直接複製原題；要更換數字、敘述、圖形條件或生活情境。
8. 先輸出「學生作答卷」，再輸出「答案與解析」。
9. 使用繁體中文，題號連續，每題解答清楚。
10. 若照片無法確認某題是否錯誤，要明確標示不確定，不可捏造。
"""
                                contents = [iterative_prompt]
                                for uploaded_file in valid_iterative_files:
                                    uploaded_file.seek(0)
                                    image = Image.open(uploaded_file).convert("RGB")
                                    contents.append(image)

                                iterative_result = call_gemini_api(contents)
                                if not iterative_result.strip():
                                    raise AIServiceError(
                                        code="EMPTY_ITERATIVE_RESULT",
                                        user_message="AI 沒有辨識到有效的批改內容，請重新拍攝較清楚的照片。",
                                    )
                                iterative_ai_succeeded = True
                            except Exception as exc:
                                add_user_credits(
                                    st.session_state["user_profile"].get("email", ""),
                                    iterative_points,
                                    reason="ai_usage_refund",
                                    reference_type="iterative_exam_refund",
                                    reference_id=str(uuid.uuid4()),
                                )
                                handle_api_error(exc)

                            if iterative_ai_succeeded:
                                st.session_state["iterative_exam_analysis"] = iterative_result.strip()
                                st.session_state["custom_exam_content"] = iterative_result.strip()
                                st.session_state["custom_exam_last_summary"] = {
                                    "grade": user_gr,
                                    "version": user_ver,
                                    "main_units": ["依紅筆錯題自動判定"],
                                    "subunits": ["依錯誤觀念自動判定"],
                                    "topics": iterative_strategy,
                                    "question_types": ["錯題補強＋適度進階"],
                                    "difficulty": "依學生作答自動調整",
                                    "question_count": iterative_count,
                                    "points": iterative_points,
                                }
                                record_effective_usage(
                                    st.session_state["user_profile"].get("email", ""),
                                    "iterative_exam",
                                )
                                st.session_state["wallet_last_message"] = (
                                    "✅ 已完成錯題診斷，並產生下一份練習；點數已同步。"
                                )
                                st.rerun()
                    else:
                        st.warning("點數不足，請先儲值。")

            st.markdown("---")
            st.markdown("### 或者：自行選擇範圍組卷")
            st.info("這裡會記錄您過往上傳的所有錯題，這是建立專屬學習履歷最重要的一環！您也可以在下方手動補充錯題來產出考卷。")
            
            if supabase_client and st.session_state["user_profile"]["email"] != "trial@example.com":
                try:
                    hist_res = supabase_client.table("user_mistakes_log").select("original_mistake, created_at").eq("user_email", st.session_state["user_profile"]["email"]).order("id", desc=True).limit(10).execute()
                    if hist_res.data:
                        st.markdown("#### 📖 您的最新錯題紀錄")
                        for r in hist_res.data:
                            st.markdown(f"- **[{r['created_at']}]** {r['original_mistake']}")
                        st.markdown("---")
                except Exception:
                    pass
            
            history_text = st.text_area("欲複習之錯題內容：", value=st.session_state.get("history_mistakes", "請輸入歷史錯題..."), height=100)
            
            st.markdown("#### 🎯 選擇複習方案")
            selected_hist_plan = st.selectbox("請選擇複習題數與方案：", list(q_count_options.keys()), key="hist_plan")
            hist_q_count = q_count_options[selected_hist_plan]
            
            use_interests_history = st.checkbox("🌟 歷史複習卷融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="history_interest")
            
            if st.button("產生複習試卷"):
                if deduct_credit(hist_q_count) and GEMINI_KEY:
                    with st.spinner("產出中..."):
                        db_text = fetch_relevant_questions_from_db([history_text[:30]], limit=15)
                        
                        prompt_hist = "歷史錯題：\n" + history_text + "\n\n"
                        prompt_hist += "【題庫優先使用】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_hist += f"請產出 {hist_q_count} 題歷史錯題複習試卷。\n\n"
                        prompt_hist += LAYOUT_NORMAL
                        prompt_hist += JSON_TEMPLATE_HIST.replace("TAG_PLACEHOLDER", "歷史複習")
                        
                        try:
                            res_text = call_gemini_api([prompt_hist])
                            final_hist_content = re.sub(r'```json.*?```', '', res_text, flags=re.DOTALL).strip()
                            render_math_content(final_hist_content)
                            render_share_buttons(final_hist_content, "hist_res")
                            parse_and_insert_9_col_json(res_text)
                        except Exception as e: handle_api_error(e)
                else:
                    show_trial_conversion_notice()
