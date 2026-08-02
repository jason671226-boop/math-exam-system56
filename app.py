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
from datetime import date
import base64

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
    from PIL import Image, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 可選的圖片畫筆元件；若未安裝，系統仍可退回原圖辨識。
try:
    from streamlit_drawable_canvas import st_canvas
    DRAWABLE_CANVAS_AVAILABLE = True
except ImportError:
    st_canvas = None
    DRAWABLE_CANVAS_AVAILABLE = False

st.set_page_config(
    page_title="AI 數學錯題迭代系統", 
    page_icon="🤖", 
    initial_sidebar_state="expanded", 
    layout="wide"
)

# --- 讀寫本地記憶帳號與紀錄 (Email 自動記憶、儲值紀錄備援) ---
LOCAL_EMAILS_FILE = "recent_emails.json"
TOPUP_FILE = "topup_requests.json"

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
        "traits": [], "interests": [], "credits": 15, "last_login_date": today_str
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

def get_recent_emails():
    try:
        if os.path.exists(LOCAL_EMAILS_FILE):
            with open(LOCAL_EMAILS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_recent_email(email):
    if not email or "@" not in email or email == "trial@example.com": 
        return
    emails = get_recent_emails()
    if email in emails:
        emails.remove(email)
    emails.insert(0, email)
    try:
        with open(LOCAL_EMAILS_FILE, "w", encoding="utf-8") as f:
            json.dump(emails[:10], f, ensure_ascii=False)
    except Exception:
        pass

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
    GEMINI_KEY = st.secrets.get("GEMINI_KEY", "")
    SMTP_USER = st.secrets.get("SMTP_USER", "")
    SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", "")
except Exception:
    SUPABASE_URL = ""
    SUPABASE_KEY = ""
    GEMINI_KEY = ""
    SMTP_USER = ""
    SMTP_PASSWORD = ""

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

def fetch_user_profile_from_db(email):
    if not supabase_client or not email or email == "trial@example.com":
        return None
    try:
        res = supabase_client.table("user_profiles").select("*").eq("email", email).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception:
        pass
    return None

def save_user_profile_to_db(profile_data):
    if not supabase_client:
        return
    email = profile_data.get("email", "")
    if not email or email == "trial@example.com":
        return
    try:
        supabase_client.table("user_profiles").upsert({
            "email": email,
            "last_name": profile_data.get("last_name", ""),
            "first_name": profile_data.get("first_name", ""),
            "city": profile_data.get("city", "新北市"),
            "district": profile_data.get("district", "土城區"),
            "school": profile_data.get("school", ""),
            "grade": profile_data.get("grade", "8年級(國二)"),
            "version": profile_data.get("version", "康軒版"),
            "traits": profile_data.get("traits", []),
            "interests": profile_data.get("interests", []),
            "credits": profile_data.get("credits", 15),
            "updated_at": today_str
        }).execute()
    except Exception:
        pass

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
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
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
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            return True
        except Exception as e:
            st.error(f"❌ 郵件寄送失敗：{e}")
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

def add_user_credits(email, points):
    if not email: return False
    
    if supabase_client:
        try:
            db_profile = fetch_user_profile_from_db(email)
            if db_profile:
                new_credits = db_profile.get("credits", 0) + points
                supabase_client.table("user_profiles").update({"credits": new_credits}).eq("email", email).execute()
            else:
                supabase_client.table("user_profiles").insert({"email": email, "credits": points}).execute()
        except Exception:
            pass
            
    if st.session_state["user_profile"].get("email") == email:
        st.session_state["user_profile"]["credits"] += points
    return True

def get_required_credits(q_count):
    if q_count <= 5: return 15
    elif q_count <= 10: return 28
    elif q_count <= 15: return 40
    else: return 50

def deduct_credit(q_count=5):
    req_credits = get_required_credits(q_count)
    if "credits" not in st.session_state["user_profile"]:
        st.session_state["user_profile"]["credits"] = 15
        
    if st.session_state["user_profile"]["credits"] >= req_credits:
        st.session_state["user_profile"]["credits"] -= req_credits
        save_user_profile_to_db(st.session_state["user_profile"])
        return True
    return False

def handle_api_error(exc: Exception) -> None:
    """顯示一般使用者可理解的 AI 錯誤；完整技術資訊僅供管理員查看。"""
    st.error(f"⚠️ {get_ai_error_message(exc)}")

    if st.session_state.get("admin_unlocked", False):
        with st.expander("管理員技術資訊"):
            st.code(get_ai_debug_message(exc))

# ==========================================
# 🌟 全域左側欄 (Sidebar) 核心邏輯 - 直接展開、保證不消失
# ==========================================
with st.sidebar:
    st.markdown(f"### 🪙 目前點數：**{st.session_state['user_profile'].get('credits', 15)}** 點")
    
    st.markdown("---")
    st.markdown("### 💳 儲值點數 \n*(儲值 1 點為新臺幣 1 元)*")
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
            st.markdown("🔹 **收款帳戶資訊**\n- 戶名：**陳冠霖**\n- 帳號：**郵局代碼 700，郵局帳號 00210570283172**")
    with pay_tabs[1]:
        st.info("💡 提示：若有 LINE Pay 條碼，可於此替換圖片。")
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
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
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
    st.markdown("### 💬 使用回饋")
    st.info("💡 提供一次使用心得或建議，就送 20 點！(一天限回饋一次，一個帳號限回饋 5 次)")
    feedback_text = st.text_area("歡迎提供系統使用建議：", placeholder="請輸入...", key="sidebar_feedback_input")
    
    if st.button("送出回饋"):
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
                            st.session_state["user_profile"]["credits"] += 20
                            save_user_profile_to_db(st.session_state["user_profile"])
                            st.session_state["feedback_today_done"] = True
                            st.success("✅ 感謝回饋！您的寶貴建議已成功傳送，並為您存入 20 點！")
                            st.rerun()
                    except Exception as e:
                        st.error(f"傳送失敗：{e}")
                else:
                    st.session_state["user_profile"]["credits"] += 20
                    st.session_state["feedback_today_done"] = True
                    st.success("✅ 感謝回饋！(本機測試模式已接收，並贈送 20 點)")
                    st.rerun()
        
    st.markdown("---")
    notice_html = (
        "<div style=\"font-size: 1.05em; line-height: 1.6; background-color: #f0f2f6; padding: 12px; border-radius: 8px; border-left: 5px solid #ff4b4b;\">"
        "<b>本系統為陳冠麟老師獨立開發製作，並擁有完整所有權。</b><br><br>"
        "目前所需要的開發及維護費用（包含使用的模型費用），皆為個人負擔。<br><br>"
        "所以只先開放部分使用者測試，<b>每組學生 Email 初始提供試用額度</b>。請多多回饋系統使用經驗！"
        "</div>"
    )
    st.markdown(notice_html, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### ⚙️ 後臺管理系統")
    if not st.session_state["admin_unlocked"]:
        admin_pwd = st.text_input("輸入管理員密碼：", type="password", key="admin_pwd_input")
        if st.button("進入後臺管理"):
            if admin_pwd == "jason575752":
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
                add_user_credits(manual_email, manual_points)
                st.success(f"成功為 {manual_email} 加入 {manual_points} 點！")
                st.rerun()
            else:
                st.warning("請填寫正確的 Email 與大於 0 的點數。")
                
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
                            except Exception as e:
                                st.error(f"錯誤：{e}")

def show_trial_conversion_notice():
    notice_box = (
        "<div style='background-color: #fff3cd; color: #856404; padding: 20px; border-radius: 10px; border-left: 6px solid #ffeba2; margin: 15px 0; font-size: 1.05em; line-height: 1.7;'>"
        "<b>⚠️ 點數不足或試用額度已用完！</b><br><br>"
        "想要繼續產出更多專屬練習嗎？請至左側選單進行<b>「儲值點數」</b>或點擊頁籤至 <b>[🏠 帳號與設定]</b> 完成免費登入綁定！<br><br>"
        "<b>👉 為什麼你應該立即免費註冊綁定？</b><br>"
        "• 🎁 <b>免費送點數</b>：新用戶註冊綁定登入後，自動獲贈 <b>30 點</b>！<br>"
        "• 🧠 <b>自動建立專屬學習履歷</b>：系統將自動記錄每一次的錯題，精準追蹤你的知識盲點。<br>"
        "• 🎯 <b>弱點深度分析與迭代</b>：不再盲目刷題！唯有透過個人化錯題累積，才能進行高度客製化的「疊代升級練習」。<br>"
        "• ⚡ <b>倍增學習效率</b>：幫學生省下 80% 整理錯題本的時間，直擊弱點，用最短時間獲得最大幅度進步！<br><br>"
        "<i>( 綁定 Email 即可立即解鎖完整功能！ )</i>"
        "</div>"
    )
    st.markdown(notice_box, unsafe_allow_html=True)

# --- 🎯 獨立視窗彈出式列印 (內建 KaTeX 引擎) ---
def render_share_buttons(content_text, key_prefix):
    st.markdown("---")
    st.markdown("#### 📤 試卷輸出與分享選項")
    
    user_email = st.session_state["user_profile"].get("email", "")
    is_trial_user = (not user_email or user_email == "trial@example.com")

    json_safe_content = json.dumps(content_text)

    c_share1, c_share2, c_share3 = st.columns(3)
    
    with c_share1:
        popup_print_script = f"""
        <script>
        function printOnlyExam() {{
            var rawContent = {json_safe_content};
            var formattedContent = rawContent
                .replace(/\\n/g, '<br>')
                .replace(/## (.*?)(<br>|$)/g, '<h2 class="section-title">$1</h2>');

            var printWindow = window.open('', '', 'width=950,height=1000');
            printWindow.document.write('<!DOCTYPE html><html><head><title>試題與解答卷</title>');
            
            printWindow.document.write('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">');
            printWindow.document.write('<script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"><\\/script>');
            printWindow.document.write('<script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"><\\/script>');
            
            printWindow.document.write('<style>');
            printWindow.document.write('@page {{ size: A4 portrait; margin: 10mm 12mm; }}');
            printWindow.document.write('*, *::before, *::after {{ box-sizing: border-box; }}');
            printWindow.document.write('body {{ font-family: "PingFang TC", "Microsoft JhengHei", sans-serif; font-size: 11pt; line-height: 1.6; color: #000; margin: 0; padding: 0; background: #fff; }}');
            printWindow.document.write('.section-title {{ font-size: 15pt; font-weight: bold; border-bottom: 2px solid #000; padding-bottom: 5px; margin-top: 15px; margin-bottom: 15px; page-break-before: always; break-before: page; }}');
            printWindow.document.write('.section-title:first-of-type {{ page-break-before: avoid; break-before: avoid; }}');
            printWindow.document.write('.page-break {{ page-break-before: always !important; break-before: page !important; height: 0; margin: 0; padding: 0; clear: both; }}');
            printWindow.document.write('@media print {{ .no-print {{ display: none !important; }} }}');
            printWindow.document.write('</style></head><body>');
            
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
            if st.button("📩 寄送至 Email", key=f"{key_prefix}_send_btn", use_container_width=True):
                st.session_state[f"{key_prefix}_show_email_input"] = not st.session_state.get(f"{key_prefix}_show_email_input", False)
        else:
            if st.button("📩 寄送至 Email", key=f"{key_prefix}_send_btn_reg", use_container_width=True):
                with st.spinner("正為您寄送試卷中..."):
                    if send_exam_email(user_email, content_text):
                        st.success(f"✅ 試卷與答案已成功寄送到：{user_email}")

    if is_trial_user and st.session_state.get(f"{key_prefix}_show_email_input", False):
        st.info("💡 請輸入接收試卷的 Email：")
        custom_target_email = st.text_input("輸入 Email：", key=f"{key_prefix}_input_email", placeholder="example@gmail.com")
        if st.button("🚀 確認寄送", key=f"{key_prefix}_confirm_send"):
            if custom_target_email and "@" in custom_target_email:
                with st.spinner("正為您寄送試卷中..."):
                    if send_exam_email(custom_target_email, content_text):
                        st.success(f"✅ 試卷與答案已成功寄送到：{custom_target_email}")
                        st.session_state[f"{key_prefix}_show_email_input"] = False
            else:
                st.warning("請先輸入正確的 Email 格式！")

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
    "請嚴格套用以下結構輸出，使用繁體中文，絕對不可輸出無關說明、思考過程或英文標籤：\n\n"
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
    "請你嚴格套用以下結構進行輸出，不可隨意省略、不可把解答寫在題目旁邊：\n\n"
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

# ==========================================
# 第一頁：登入與試用頁面
# ==========================================
if not st.session_state["setup_complete"] and not st.session_state["is_trial"]:
    st.title("🧙‍♂️ AI 數學錯題迭代系統")
    welcome_msg = (
        "<div style=\"background-color: #f0f7ff; padding: 16px; border-radius: 10px; border-left: 6px solid #1c83e1; font-size: 1.05em;\">\n"
        "<b>> 造就異數的不是 1 萬小時的重複，而是 1 萬次迭代。</b> —— Naval Ravikant\n"
        "</div>"
    )
    st.markdown(welcome_msg, unsafe_allow_html=True)
    st.markdown("---")
    
    client_ip = get_client_ip()
    ip_today_key = f"{today_str}_{client_ip}"
    current_ip_trials = st.session_state["ip_trial_history"].get(ip_today_key, 0)

    col_trial_1, col_trial_2, col_trial_3 = st.columns([1, 2, 1])
    with col_trial_2:
        if current_ip_trials >= 1:
            st.error("⚠️ 您的 IP 今日試用額度已用盡！請使用下方 Email 驗證註冊/登入。")
        else:
            if st.button("🚀 立即試用（送 15 點，直接進入系統）", type="primary", use_container_width=True):
                st.session_state["is_trial"] = True
                st.session_state["setup_complete"] = True
                st.rerun()
    st.markdown("---")

    st.subheader("📋 註冊綁定 / 登入個人資料庫 (新會員登入即送 30 點)")
    up = st.session_state["user_profile"]

    current_stored_email = st.session_state["user_profile"].get("email", "")
    is_verified = bool(current_stored_email and current_stored_email != "trial@example.com")

    if not is_verified:
        recent_emails = get_recent_emails()
        email_options = ["➕ 手動輸入新 Email..."] + recent_emails
        
        st.markdown("#### 📧 請選擇或輸入您的登入 Email (必填)")
        selected_option = st.selectbox("點擊選擇曾登入過的帳號：", email_options, key="single_email_select")
        
        if selected_option == "➕ 手動輸入新 Email...":
            typed_email = st.text_input("請輸入新的 Email (綁定與驗證用)：", value=st.session_state["pending_email"], placeholder="example@gmail.com")
            user_email_input = typed_email.strip()
        else:
            user_email_input = selected_option
            db_profile = fetch_user_profile_from_db(user_email_input)
            if db_profile:
                st.session_state["user_profile"]["last_name"] = db_profile.get("last_name", "")
                st.session_state["user_profile"]["first_name"] = db_profile.get("first_name", "")
                st.session_state["user_profile"]["city"] = db_profile.get("city", "新北市")
                st.session_state["user_profile"]["district"] = db_profile.get("district", "土城區")
                st.session_state["user_profile"]["school"] = db_profile.get("school", "")
                st.session_state["user_profile"]["grade"] = db_profile.get("grade", "8年級(國二)")
                st.session_state["user_profile"]["version"] = db_profile.get("version", "康軒版")
                st.session_state["user_profile"]["traits"] = db_profile.get("traits", [])
                st.session_state["user_profile"]["interests"] = db_profile.get("interests", [])
                if "credits" in db_profile:
                    st.session_state["user_profile"]["credits"] = db_profile.get("credits")

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
                            st.session_state["user_profile"]["email"] = st.session_state["pending_email"]
                            st.session_state["is_verified"] = True
                            save_recent_email(st.session_state["pending_email"])
                            
                            db_profile = fetch_user_profile_from_db(st.session_state["pending_email"])
                            if not db_profile:
                                st.session_state["user_profile"]["credits"] = 30
                            else:
                                st.session_state["user_profile"]["credits"] = db_profile.get("credits", 30)
                            
                            st.rerun()
                        else:
                            st.error("❌ 驗證碼錯誤，請重新確認！")
        st.markdown("---")
    else:
        st.success(f"✅ 您目前已登入 Email：**{current_stored_email}**")
        st.markdown("---")
        
    up = st.session_state["user_profile"]
    def_ln = up.get("last_name", "")
    def_fn = up.get("first_name", "")
    def_city = up.get("city", "新北市")
    def_district = up.get("district", "土城區")
    def_school = up.get("school", "")
    def_grade = up.get("grade", "8年級(國二)")
    def_ver = up.get("version", "康軒版")
    def_traits = up.get("traits", [])

    st.markdown("#### 👤 學生基本資料設定 (紅標為必填欄位)")
    
    col_name1, col_name2 = st.columns(2)
    with col_name1: last_n = st.text_input("姓氏 (必填)：", value=def_ln)
    with col_name2: first_n = st.text_input("名字 (必填)：", value=def_fn)
    
    col_geo1, col_geo2, col_geo3 = st.columns(3)
    with col_geo1:
        city_idx = taiwan_counties.index(def_city) if def_city in taiwan_counties else 1
        selected_city = st.selectbox("縣市 (必填)：", taiwan_counties, index=city_idx)
    with col_geo2:
        dist_options = taiwan_districts.get(selected_city, ["全區"])
        dist_idx = dist_options.index(def_district) if def_district in dist_options else 0
        selected_district = st.selectbox("鄉鎮市區 (必填)：", dist_options, index=dist_idx)
    with col_geo3:
        school_name = st.text_input("就讀學校 (必填，例如：樹林國中)：", value=def_school)

    col_edu1, col_geo2_edu = st.columns(2)
    with col_edu1:
        gr_idx = grade_options.index(def_grade) if def_grade in grade_options else 7
        selected_grade = st.selectbox("就讀年級 (必填)：", grade_options, index=gr_idx)
        
    is_high_school = any(g in selected_grade for g in ["10年級", "11年級", "12年級", "高"])
    if is_high_school:
        valid_versions = ["A級 (數學A)", "B級 (數學B)", "C級 (數學C)", "報考私中", "參加數學競賽"]
    else:
        valid_versions = ["康軒版", "翰林版", "南一版", "報考私中", "參加數學競賽"]
        
    ver_idx = valid_versions.index(def_ver) if def_ver in valid_versions else 0
    with col_geo2_edu:
        selected_version = st.selectbox("教科書版本 / 類別 (必填，連動後續自組卷)：", valid_versions, index=ver_idx)

    st.markdown("---")
    
    st.markdown("#### 🧠 學生個人學習狀況 (提示：選填，協助 AI 精準配題)")
    learning_traits = [
        "粗心大意", "計算力不足", "基礎觀念不佳", "應用題理解困難", 
        "空間幾何薄弱", "專注力不足容易分心", "考試時間分配不佳", "缺乏訂正習慣",
        "對數學有濃厚興趣", "希望挑戰更高難度的數學", "渴望突破現在的數學能力"
    ]
    
    known_traits = set(learning_traits)
    def_custom_trait = ""
    def_selected_traits = []
    for t in def_traits:
        if t in known_traits:
            def_selected_traits.append(t)
        else:
            def_custom_trait = t

    selected_traits = st.multiselect("綜合學習狀況：", learning_traits, default=def_selected_traits)
    custom_trait = st.text_input("📝 學習狀況自填欄 (若上方無符合選項請在此補充)：", value=def_custom_trait)
    
    final_traits = selected_traits.copy()
    if custom_trait:
        final_traits.append(custom_trait)
    
    st.markdown("#### 🌟 學生有興趣的事物 (提示：選填，讓題目情境更生動)")
    st.info("💡 操作提示：點擊下方分類頁籤，即可展開並勾選您喜歡的熱門 IP/主題！")
    
    cat_tabs = st.tabs(list(interests_catalog.keys()))
    for idx, cat_name in enumerate(interests_catalog.keys()):
        with cat_tabs[idx]:
            st.session_state["interest_selections"][cat_name] = st.multiselect(
                f"勾選「{cat_name}」的熱門細項：",
                interests_catalog[cat_name],
                default=st.session_state["interest_selections"][cat_name]
            )
    
    all_interests = []
    for items in st.session_state["interest_selections"].values():
        all_interests.extend(items)
        
    st.session_state["custom_interest"] = st.text_input("其他個人興趣喜好（自行填寫）：", value=st.session_state.get("custom_interest", ""))
    
    final_interests = all_interests.copy()
    if st.session_state["custom_interest"]:
        final_interests.append(st.session_state["custom_interest"])
        
    st.success(f"🎯 **目前已累積的學生興趣清單**：{', '.join(final_interests) if final_interests else '尚未選擇'}")
    
    st.markdown("---")

    if is_verified:
        col_action1, col_action2 = st.columns(2)
        with col_action1:
            if st.button("💾 儲存資料並進入系統", type="primary", use_container_width=True):
                if not last_n.strip() or not first_n.strip():
                    st.error("⚠️ 請完整填寫學生的「姓氏」與「名字」！")
                elif not school_name.strip():
                    st.error("⚠️ 請填寫學生的「就讀學校」！")
                else:
                    st.session_state["user_profile"]["last_name"] = last_n.strip()
                    st.session_state["user_profile"]["first_name"] = first_n.strip()
                    st.session_state["user_profile"]["city"] = selected_city
                    st.session_state["user_profile"]["district"] = selected_district
                    st.session_state["user_profile"]["school"] = school_name.strip()
                    st.session_state["user_profile"]["grade"] = selected_grade
                    st.session_state["user_profile"]["version"] = selected_version
                    st.session_state["user_profile"]["traits"] = final_traits
                    st.session_state["user_profile"]["interests"] = final_interests
                    
                    save_recent_email(st.session_state["user_profile"]["email"])
                    save_user_profile_to_db(st.session_state["user_profile"])
                    st.session_state["setup_complete"] = True
                    st.rerun()
        with col_action2:
            if st.button("🔄 登出切換帳號", use_container_width=True):
                st.session_state["user_profile"]["email"] = "trial@example.com"
                st.session_state["is_verified"] = False
                st.session_state["otp_sent"] = False
                st.rerun()

# ==========================================
# 第二頁：主系統畫面
# ==========================================
elif st.session_state["setup_complete"]:
    is_trial = st.session_state.get("is_trial", False)
    
    tabs = st.tabs(["📸 錯題解析", "🏠 帳號與設定", "📂 歷史錯題 🔒", "🧠 學習診斷 🔒", "⚙️ 自組考卷 🔒"])
    tab_scan, tab_back, tab_history, tab_diag, tab_custom = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4]

    with tab_back:
        st.subheader("🏠 帳號與個人化設定")
        st.info("💡 您可以在此返回首頁「修改學生資料與興趣」，系統會保留您的登入狀態與歷史紀錄。若要完全登出，請在首頁最下方點擊「登出切換帳號」。")
        if st.button("🔙 返回首頁 / 修改學生資料", type="primary"):
            st.session_state["setup_complete"] = False
            st.session_state["is_trial"] = False
            st.rerun()

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

        uploaded_files = st.file_uploader("📂 上傳錯題照片 (最多支援 2 張)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        
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
                help="圈選標註模式可直接在圖片上畫圈、畫線或打叉，AI 會優先參考紅色標記。",
            )

            if mark_mode == "圈選標註後辨識":
                if DRAWABLE_CANVAS_AVAILABLE:
                    st.info("請用紅色畫筆圈選、畫線或打叉。完成後直接按下方辨識按鈕；AI 會讀取標註後的圖片。")
                    tool_col1, tool_col2, tool_col3 = st.columns([1, 1, 1])
                    with tool_col1:
                        drawing_mode_label = st.selectbox(
                            "標註工具",
                            ["自由畫筆", "直線", "矩形", "圓形"],
                            index=0,
                        )
                    with tool_col2:
                        stroke_width = st.slider("畫筆粗細", 2, 20, 6)
                    with tool_col3:
                        stroke_color = st.color_picker("標註顏色", "#FF0000")

                    drawing_mode_map = {
                        "自由畫筆": "freedraw",
                        "直線": "line",
                        "矩形": "rect",
                        "圓形": "circle",
                    }

                    if "canvas_reset_version" not in st.session_state:
                        st.session_state["canvas_reset_version"] = 0

                    if st.button("🧹 清除所有圖片標記", use_container_width=True):
                        st.session_state["canvas_reset_version"] += 1
                        st.rerun()
                else:
                    st.warning(
                        "尚未安裝圖片畫筆元件，暫時以原圖顯示。請執行「更新套件.bat」後重新啟動系統。"
                    )

            # 為了手機操作，圖片採上下排列，不使用左右欄位。
            for idx, img_f in enumerate(valid_files):
                st.caption(f"錯題照片 {idx + 1}")
                img_f.seek(0)
                raw_img = Image.open(img_f).convert("RGB")

                if enable_image_fix and PIL_AVAILABLE:
                    enhancer = ImageEnhance.Contrast(raw_img)
                    raw_img = enhancer.enhance(1.4)

                if mark_mode == "圈選標註後辨識" and DRAWABLE_CANVAS_AVAILABLE:
                    max_canvas_width = 900
                    scale = min(1.0, max_canvas_width / max(raw_img.width, 1))
                    canvas_width = max(320, int(raw_img.width * scale))
                    canvas_height = max(200, int(raw_img.height * scale))
                    canvas_background = raw_img.resize(
                        (canvas_width, canvas_height), Image.Resampling.LANCZOS
                    )

                    canvas_result = st_canvas(
                        fill_color="rgba(255, 0, 0, 0.08)",
                        stroke_width=stroke_width,
                        stroke_color=stroke_color,
                        background_image=canvas_background,
                        update_streamlit=True,
                        height=canvas_height,
                        width=canvas_width,
                        drawing_mode=drawing_mode_map[drawing_mode_label],
                        display_toolbar=True,
                        key=(
                            f"exam_canvas_{idx}_"
                            f"{st.session_state['canvas_reset_version']}"
                        ),
                    )

                    if canvas_result.image_data is not None:
                        marked_img = Image.fromarray(
                            canvas_result.image_data.astype("uint8"), "RGBA"
                        ).convert("RGB")
                        annotated_images.append(marked_img)
                    else:
                        annotated_images.append(canvas_background.convert("RGB"))
                else:
                    st.image(raw_img, use_container_width=True)
                    annotated_images.append(raw_img)

            if mark_mode == "圈選標註後辨識" and DRAWABLE_CANVAS_AVAILABLE:
                st.success("標註完成後，請直接按下方「開始免費辨識文字」。")

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
                        "若圖片上有使用者後加的紅色圈選、方框、畫線或打叉，請將被標記的題目視為最高優先。\n"
                        "優先擷取有紅筆加註、留白、打叉或訂正痕跡的題目。\n"
                        "打勾（✓）通常代表答對，請不要列入。\n"
                        "只輸出錯題文字，不要加入其他說明。\n"
                    )
                else:
                    prompt = (
                        "你是一個資深的數學老師與考卷辨識專家。\n"
                        "請精準辨識圖片中的數學題目，保留完整公式與符號。\n"
                        "若圖片上有使用者後加的紅色圈選、方框、畫線或打叉，請將被標記的題目視為最高優先。\n"
                        "只擷取有紅筆加註、留白或打叉（X）的題目。\n"
                        "打勾（✓）代表答對，請絕對不要列入。\n"
                        "只輸出錯題文字，不要加入其他說明。\n"
                    )

                if is_trial:
                    prompt += "這是試用請求，最多擷取 5 道符合條件的題目。\n"

                contents = [prompt]
                images_to_send = annotated_images if annotated_images else [Image.open(f).convert("RGB") for f in files]
                for image in images_to_send:
                    contents.append(image.convert("RGB"))

                response_text = call_gemini_api(contents)
                if not response_text.strip():
                    raise AIServiceError(
                        code="EMPTY_SCAN_RESULT",
                        user_message="AI 沒有辨識到有效題目，請改用人工輸入模式。",
                    )

                st.session_state["scanned_text"] = response_text.strip()
                st.session_state["manual_scan_text"] = response_text.strip()
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
        
        edited_text = st.text_area("確認題目內容 (可在框內直接微調要輸出的錯題)：", value=st.session_state["scanned_text"], height=120)
        st.session_state["scanned_text"] = edited_text

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
                            st.success("成功產出！")
                    except Exception as e: handle_api_error(e)
            else:
                show_trial_conversion_notice()

        if st.session_state["generated_content"]:
            st.markdown(f'<div class="printable-exam-area">{st.session_state["generated_content"]}</div>', unsafe_allow_html=True)
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
                        except Exception as e: handle_api_error(e)
                else:
                    show_trial_conversion_notice()
                        
            if st.session_state.get("variation_content"):
                st.markdown("### 🌟 變形試卷")
                st.markdown(f'<div class="printable-exam-area">{st.session_state["variation_content"]}</div>', unsafe_allow_html=True)
                render_share_buttons(st.session_state["variation_content"], "var_res")

    with tab_history:
        st.subheader("📂 學生歷史錯題與學習履歷 🔒")
        if is_trial:
            show_trial_conversion_notice()
        else:
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
                            st.markdown(f'<div class="printable-exam-area">{final_hist_content}</div>', unsafe_allow_html=True)
                            render_share_buttons(final_hist_content, "hist_res")
                            parse_and_insert_9_col_json(res_text)
                        except Exception as e: handle_api_error(e)
                else:
                    show_trial_conversion_notice()

    with tab_custom:
        st.subheader("⚙️ 題目自組卷 (強大 Hybrid 混合出題) 🔒")
        if is_trial:
            show_trial_conversion_notice()
        else:
            user_ver = st.session_state["user_profile"].get("version", "康軒版")
            user_gr = st.session_state["user_profile"].get("grade", "8年級(國二)")
            st.info(f"💡 目前設定連動：**{user_gr} ({user_ver})**")
            
            if user_ver not in syllabus_full: 
                user_ver_key = "康軒版"
            else:
                user_ver_key = user_ver
                
            selected_mains = st.multiselect(f"請選擇【{user_ver_key}】主單元 (可複選)：", syllabus_full.get(user_ver_key, syllabus_full["康軒版"]))
            
            st.markdown("#### 📖 選擇次單元/題型方向")
            sub_units_options = ["基礎觀念題", "生活情境應用題", "圖形與圖表解析", "進階變化題", "歷屆易錯陷阱題"]
            selected_subs = st.multiselect("請選擇題型方向 (可複選)：", sub_units_options, default=sub_units_options[:2])
            
            display_q = 30
            mc_cnt = 10
            fill_cnt = 10
            calc_cnt = 10
            req_pts = 50
            
            st.info(f"💡 預計總題數：**{display_q}** 題 (將扣除 **{req_pts}** 點)")

            use_interests_custom = st.checkbox("🌟 自組卷融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="custom_exam_interest")

            col_cust1, col_cust2 = st.columns(2)
            with col_cust1:
                btn_cust1 = st.button("產生自組卷", type="primary", use_container_width=True)
            with col_cust2:
                btn_cust2 = st.button("🔄 重新生成不同題目", use_container_width=True)

            if btn_cust1 or btn_cust2:
                if not selected_mains or not selected_subs: 
                    st.warning("請先選擇主單元與次單元題型！")
                else:
                    if "credits" not in st.session_state["user_profile"]:
                        st.session_state["user_profile"]["credits"] = 15
                        
                    if st.session_state["user_profile"]["credits"] >= req_pts:
                        st.session_state["user_profile"]["credits"] -= req_pts
                        save_user_profile_to_db(st.session_state["user_profile"])
                        
                        with st.spinner("智慧組卷中..."):
                            main_topics_str = "、".join(selected_mains)
                            sub_topics_str = "、".join(selected_subs)
                            db_text = fetch_relevant_questions_from_db(selected_mains, limit=20)
                            
                            prompt_custom = f"適用年級與版本：{user_gr} {user_ver}\n"
                            prompt_custom += "主單元：\n" + main_topics_str + "\n"
                            prompt_custom += "題型方向：\n" + sub_topics_str + "\n\n"
                            prompt_custom += "【系統題庫資源】\n" + (db_text if db_text else "(無)") + "\n\n"
                            prompt_custom += f"請產出總共 {display_q} 題（嚴格包含 {mc_cnt}題選擇題、{fill_cnt}題填空題與 {calc_cnt}題計算題的組合）。\n"
                            prompt_custom += "【出題優先順序】：請優先從上方系統題庫資源中出題，若題數不足，剩餘的部分請完全使用 AI 自動生成補充。\n"
                            prompt_custom += "【出題重要要求】：所有生成的題目與解答請儘量不要與題庫完全重複，至少要修改數字與情境。每道題目務必提供標準解答與解析。\n\n"
                            prompt_custom += LAYOUT_NORMAL
                            prompt_custom += JSON_TEMPLATE_CUSTOM.replace("UNIT_PLACEHOLDER", main_topics_str)
                            
                            try:
                                res_text = call_gemini_api([prompt_custom])
                                final_custom_content = re.sub(r'```json.*?```', '', res_text, flags=re.DOTALL).strip()
                                
                                st.session_state["custom_exam_content"] = final_custom_content
                                parse_and_insert_9_col_json(res_text)
                            except Exception as e: handle_api_error(e)
                    else:
                        show_trial_conversion_notice()
            
            if st.session_state.get("custom_exam_content"):
                st.markdown(f'<div class="printable-exam-area">{st.session_state["custom_exam_content"]}</div>', unsafe_allow_html=True)
                render_share_buttons(st.session_state["custom_exam_content"], "cust_res")

    with tab_diag:
        st.subheader("🧠 學習診斷 🔒")
        if is_trial:
            show_trial_conversion_notice()
        else:
            st.info("敬請期待學習圖表分析！")