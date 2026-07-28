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

# --- 修正 Streamlit 新版本導致 Canvas 圖片顯示空白的問題 (強制轉換為 Base64 Data URI) ---
import streamlit.elements.image as st_image

def _compat_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="PNG", image_id=None):
    try:
        if isinstance(image, str):
            return image
        buffered = io.BytesIO()
        if hasattr(image, 'save'):
            image.save(buffered, format="PNG")
        elif isinstance(image, bytes):
            buffered.write(image)
        else:
            from PIL import Image as PILImage
            img_obj = PILImage.fromarray(image)
            img_obj.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception:
        return image

st_image.image_to_url = _compat_image_to_url

try:
    import streamlit.type_util as st_type_util
    st_type_util.image_to_url = _compat_image_to_url
except Exception:
    pass

# 嘗試載入 Canvas 畫布套件 (必須在修補函式注入後載入)
try:
    import streamlit_drawable_canvas
    if hasattr(streamlit_drawable_canvas, 'image_to_url'):
        streamlit_drawable_canvas.image_to_url = _compat_image_to_url
    from streamlit_drawable_canvas import st_canvas
    CANVAS_AVAILABLE = True
except ImportError:
    CANVAS_AVAILABLE = False

# 嘗試載入 Pandas (處理 CSV)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# 嘗試載入 Google GenAI 套件
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# 嘗試載入 Supabase 套件
try:
    from supabase import Client, create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

st.set_page_config(
    page_title="AI 數學錯題迭代系統", 
    page_icon="🤖", 
    initial_sidebar_state="expanded", 
    layout="wide"
)

# --- 讀寫本地記憶帳號 (Email 自動記憶功能) ---
LOCAL_EMAILS_FILE = "recent_emails.json"

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

# 取得連線使用者 IP 位址函式 (支援 Cloudflare 代理標頭)
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
    "台北市": [
        "中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", 
        "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"
    ],
    "新北市": [
        "板橋區", "新莊區", "中和區", "永和區", "土城區", "樹林區", 
        "三峽區", "鶯歌區", "三重區", "蘆洲區", "五股區", "泰山區", 
        "林口區", "八里區", "淡水區", "三芝區", "石門區", "金山區", 
        "萬里區", "汐止區", "瑞芳區", "貢寮區", "雙溪區", "平溪區", 
        "新店區", "深坑區", "石碇區", "坪林區", "烏來區"
    ],
    "基隆市": [
        "仁愛區", "信義區", "中正區", "中山區", "安樂區", "暖暖區", "七堵區"
    ],
    "桃園市": [
        "桃園區", "中壢區", "平鎮區", "八德區", "楊梅區", "蘆竹區", 
        "大溪區", "龍潭區", "龜山區", "大園區", "觀音區", "新屋區", "複興區"
    ],
    "新竹市": [
        "東區", "北區", "香山區"
    ],
    "新竹縣": [
        "竹北市", "竹東鎮", "新埔鎮", "關西鎮", "湖口鄉", "新豐鄉", 
        "芎林鄉", "橫山鄉", "北埔鄉", "寶山鄉", "峨眉鄉", "尖石鄉", "五峰鄉"
    ],
    "苗栗縣": [
        "苗栗市", "頭份市", "竹南鎮", "後龍鎮", "通霄鎮", "苑裡鎮", 
        "卓欄鎮", "造橋鄉", "西湖鄉", "頭屋鄉", "公館鄉", "銅鑼鄉", 
        "三義鄉", "大湖鄉", "獅潭鄉", "三灣鄉", "南庄鄉", "泰安鄉"
    ],
    "台中市": [
        "中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", 
        "南屯區", "太平區", "大里區", "霧峰區", "烏日區", "豐原區", 
        "后里區", "石岡區", "東勢區", "和平區", "新社區", "潭子區", 
        "大雅區", "神岡區", "大肚區", "沙鹿區", "龍井區", "梧棲區", 
        "清水區", "大甲區", "外埔區", "大安區"
    ],
    "彰化縣": [
        "彰化市", "員林市", "和美鎮", "鹿港鎮", "溪湖鎮", "二林鎮", 
        "田中鎮", "北斗鎮", "花壇鄉", "芬園鄉", "大村鄉", "永靖鄉", 
        "伸港鄉", "線西鄉", "福興鄉", "秀水鄉", "埔心鄉", "埔鹽鄉", 
        "大城鄉", "芳苑鄉", "竹塘鄉", "社頭鄉", "二水鄉", "田尾鄉", 
        "埤頭鄉", "溪州鄉"
    ],
    "南投縣": [
        "南投市", "埔里鎮", "草屯鎮", "竹山鎮", "集集鎮", "名間鄉", 
        "鹿谷鄉", "中寮鄉", "魚池鄉", "國姓鄉", "水里鄉", "信義鄉", "仁愛鄉"
    ],
    "雲林縣": [
        "斗六市", "斗南鎮", "虎尾鎮", "西螺鎮", "土庫鎮", "北港鎮", 
        "古坑鄉", "大埤鄉", "莿桐鄉", "林內鄉", "二崙鄉", "崙背鄉", 
        "麥寮鄉", "東勢鄉", "褒忠鄉", "臺西鄉", "元長鄉", "四湖鄉", 
        "口湖鄉", "水林鄉"
    ],
    "嘉義市": [
        "東區", "西區"
    ],
    "嘉義縣": [
        "太保市", "朴子市", "布袋鎮", "大林鎮", "民雄鄉", "溪口鄉", 
        "新港鄉", "六腳鄉", "東石鄉", "義竹鄉", "鹿草鄉", "水上鄉", 
        "中埔鄉", "竹崎鄉", "梅山鄉", "番路鄉", "大埔鄉", "阿里山鄉"
    ],
    "台南市": [
        "中西區", "東區", "南區", "北區", "安平區", "安南區", "永康區", 
        "歸仁區", "新化區", "左鎮區", "玉井區", "楠西區", "南化區", 
        "仁德區", "關廟區", "龍崎區", "官田區", "麻豆區", "佳里區", 
        "西港區", "七股區", "將軍區", "學甲區", "北門區", "新營區", 
        "後壁區", "白河區", "東山區", "六甲區", "下營區", "柳營區", 
        "鹽水區", "善化區", "大內區", "山上區", "新市區", "安定區"
    ],
    "高雄市": [
        "楠梓區", "左營區", "鼓山區", "三民區", "鹽埕區", "前金區", 
        "新興區", "苓雅區", "前鎮區", "旗津區", "小港區", "鳳山區", 
        "林園區", "大寮區", "大樹區", "大社區", "仁武區", "鳥松區", 
        "岡山區", "橋頭區", "燕巢區", "田寮區", "阿蓮區", "路竹區", 
        "湖內區", "茄萣區", "永安區", "彌陀區", "梓官區", "旗山區", 
        "美濃區", "六龜區", "杉林區", "甲仙區", "桃源區", "朱溪區", 
        "茂林區", "內門區"
    ],
    "屏東縣": [
        "屏東市", "潮州鎮", "東港鎮", "恆春鎮", "萬丹鄉", "長治鄉", 
        "麟洛鄉", "九如鄉", "里港鄉", "鹽埔鄉", "高樹鄉", "萬欄鄉", 
        "內埔鄉", "竹田鄉", "新埤鄉", "枋寮鄉", "新園鄉", "崁頂鄉", 
        "林邊鄉", "南州鄉", "佳冬鄉", "琉球鄉", "車城鄉", "滿州鄉", 
        "枋山鄉", "三地門鄉", "霧臺鄉", "瑪家鄉", "泰武鄉", "來義鄉", 
        "春日鄉", "獅子鄉", "牡丹鄉"
    ],
    "宜蘭縣": [
        "宜蘭市", "羅東鎮", "蘇澳鎮", "頭城鎮", "礁溪鄉", "壯圍鄉", 
        "員山鄉", "冬山鄉", "五結鄉", "三星鄉", "大同鄉", "南澳鄉"
    ],
    "花蓮縣": [
        "花蓮市", "鳳林鎮", "玉里鎮", "新城鄉", "吉安鄉", "壽豐鄉", 
        "光複鄉", "豐濱鄉", "瑞穗鄉", "富里鄉", "秀林鄉", "萬榮鄉", "卓溪鄉"
    ],
    "台東縣": [
        "台東市", "成功鎮", "關山鎮", "長濱鄉", "海端鄉", "池上鄉", 
        "東河鄉", "鹿野鄉", "延平鄉", "卑南鄉", "太麻里鄉", "大武鄉", 
        "綠島鄉", "蘭嶼鄉", "金峰鄉", "達仁鄉"
    ],
    "澎湖縣": [
        "馬公市", "湖西鄉", "白沙鄉", "西嶼鄉", "望安鄉", "七美鄉"
    ],
    "金門縣": [
        "金城鎮", "金沙鎮", "金湖鎮", "金寧鄉", "烈嶼鄉", "烏坵鄉"
    ],
    "連江縣(馬祖)": [
        "南竿鄉", "北竿鄉", "莒光鄉", "東引鄉"
    ]
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

DISPOSABLE_DOMAINS = [
    "10minutemail.com", "tempmail.com", "guerrillamail.com", 
    "yopmail.com", "mailinator.com", "throwawaymail.com", 
    "dropmail.me", "temp-mail.org", "fakeinbox.com"
]

today_str = date.today().isoformat()

# 初始化 session state
if "setup_complete" not in st.session_state:
    st.session_state["setup_complete"] = False
if "is_trial" not in st.session_state:
    st.session_state["is_trial"] = False
if "user_profile" not in st.session_state:
    st.session_state["user_profile"] = {
        "last_name": "", "first_name": "", 
        "email": "trial@example.com", "city": "新北市", "district": "土城區", "school": "",
        "grade": "8年級(國二)", "version": "康軒版", 
        "traits": [], "interests": [], "credits": 5, "last_login_date": today_str
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
if "interest_selections" not in st.session_state:
    st.session_state["interest_selections"] = {k: [] for k in interests_catalog.keys()}
if "custom_interest" not in st.session_state: st.session_state["custom_interest"] = ""
if "ip_trial_history" not in st.session_state: st.session_state["ip_trial_history"] = {}
if "otp_sent" not in st.session_state: st.session_state["otp_sent"] = False
if "generated_otp" not in st.session_state: st.session_state["generated_otp"] = ""
if "pending_email" not in st.session_state: st.session_state["pending_email"] = ""

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

if not GEMINI_KEY:
    part1 = "AQ.Ab8RN6IC4WFN0ATL"
    part2 = "7omykAqJl156F4g3FM_K_PyTZzUPcNbp1g"
    GEMINI_KEY = part1 + part2
if not SUPABASE_URL:
    SUPABASE_URL = "https://igttuijrtwbtefhyeokp.supabase.co"
if not SUPABASE_KEY:
    s_part1 = "sb_publishable_fa0t2W8U5iwi42Gr"
    s_part2 = "NJD5Hg_p-J5JsJ5"
    SUPABASE_KEY = s_part1 + s_part2

if not SMTP_USER:
    SMTP_USER = "system.math.ai@gmail.com"
if not SMTP_PASSWORD:
    SMTP_PASSWORD = "xvyz abcd efgh ijkl"

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
            "credits": profile_data.get("credits", 5),
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
        except Exception as e:
            st.error(f"郵件發送失敗: {e}")
            return False
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
            st.error(f"❌ 郵件寄送失敗，請確認網路或 Email 格式。錯誤訊息：{e}")
            return False
    else:
        st.warning("⚠️ 系統後台尚未設定 SMTP 郵件發送金鑰（SMTP_USER / SMTP_PASSWORD）。如欲在網路上真實寄信，請至 Streamlit Secrets 設定。")
        return False

syllabus_full = {
    "康軒版": [
        "5上_單元 1：多位小數與加減", "5上_單元 2：因數與公因數", "5上_單元 3：倍數與公倍數",
        "5上_單元 4：擴分、約分和通分", "5上_單元 5：多邊形與扇形", "5上_單元 6：異分母分數的加減",
        "5上_單元 7：線對稱圖形", "5上_單元 8：整數四則運算", "5上_單元 9：面積", "5上_單元 10：柱體、錐體和球",
        "5下_第一、三、七單元：立體形體", "5下_第二、四、六單元：分數與小數計算",
        "5下_第五單元：大數與折線圖", "5下_第八單元：比率與百分率", "5下_第九單元：時間的乘除", "5下_第十單元：生活中的大單位",
        "🔥 私中特訓：濃度問題與溶液混合計算", "🔥 私中特訓：年齡問題與差倍、和倍", "🔥 私中特訓：和差問題與雞兔同籠"
    ],
    "南一版": [
        "5上_單元 1：大數與概數", "5上_單元 2：因數與倍數", "5上_單元 3：分數的加減", "5上_單元 4：小數的加減",
        "5上_單元 5：體積與容積", "5上_單元 6：未知數", "5下_單元 1：分數的乘除", "5下_單元 2：小數的乘除",
        "5下_單元 3：面積與表面積", "5下_單元 4：時間的計算", "5下_單元 5：比率與百分率", "5下_單元 6：折線圖"
    ],
    "翰林版": [
        "5上_單元 1：最大公因數與最小公倍數", "5上_單元 2：異分母分數加減", "5上_單元 3：多邊形面積",
        "5上_單元 4：小數的乘除", "5上_單元 5：線對稱圖形", "5下_單元 1：分數乘除法", "5下_單元 2：長方體與正方體體積",
        "5下_單元 3：容積與容量", "5下_單元 4：時間的運算", "5下_單元 5：百分率與折扣", "5下_單元 6：圓面積"
    ],
    "其他": ["基礎計算", "幾何圖形", "應用問題", "統計與機率", "🔥 私中特訓：綜合應用"]
}

all_topics_set = set()
for topics_list in syllabus_full.values():
    all_topics_set.update(topics_list)
all_topics_sorted = sorted(list(all_topics_set))

with st.sidebar:
    st.markdown("### 💬 使用回饋")
    feedback_text = st.text_area("歡迎提供系統使用建議：", placeholder="請輸入...", key="sidebar_feedback_input")
    if st.button("送出回饋"):
        if feedback_text and supabase_client:
            try:
                current_email = st.session_state["user_profile"].get("email", "試用者/未綁定")
                supabase_client.table("user_feedback").insert({"user_email": current_email, "content": feedback_text}).execute()
                st.success("感謝回饋！您的寶貴建議已成功傳送。")
            except Exception as e:
                st.error(f"傳送失敗：{e}")
        elif feedback_text:
            st.success("感謝回饋！(本機測試模式已接收)")
        else:
            st.warning("請先輸入您的建議內容再點擊送出喔！")
        
    st.markdown("---")
    
    notice_html = (
        "<div style=\"font-size: 1.05em; line-height: 1.6; background-color: #f0f2f6; padding: 12px; border-radius: 8px; border-left: 5px solid #ff4b4b;\">"
        "<b>本系統內容均獨立開發，並擁有全部所有權。</b><br><br>"
        "目前所需要的開發及維護費用（包含使用的模型費用），皆為個人負擔。<br><br>"
        "所以只先開放部分使用者測試，<b>每組學生 Email 初始提供 5 次測試額度，並享每日登入發放 2 次免費額度</b>。請多多回饋系統使用經驗！"
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

def deduct_credit():
    if "credits" not in st.session_state["user_profile"]:
        st.session_state["user_profile"]["credits"] = 5
        
    if st.session_state["user_profile"]["credits"] > 0:
        st.session_state["user_profile"]["credits"] -= 1
        return True
    return False

def handle_api_error(e):
    error_msg = str(e)
    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
        st.error("⚠️ **Google API 額度已耗盡！** 請更換 API 金鑰。")
    else:
        st.error(f"錯誤：{error_msg}")

def show_trial_conversion_notice():
    notice_box = (
        "<div style='background-color: #fff3cd; color: #856404; padding: 20px; border-radius: 10px; border-left: 6px solid #ffeba2; margin: 15px 0; font-size: 1.05em; line-height: 1.7;'>"
        "<b>⚠️ 今天的免費試用額度已使用完畢（每日限體驗 1 次）。</b><br><br>"
        "想要繼續掃描錯題、產出更多專屬練習嗎？請點擊頁籤至 <b>[🏠 返回首頁設定]</b> 完成免費登入綁定！<br><br>"
        "<b>👉 為什麼你應該立即免費註冊綁定？</b><br>"
        "• 🧠 <b>自動建立專屬學習履歷</b>：系統將自動記錄每一次的錯題，精準追蹤你的知識盲點。<br>"
        "• 🎯 <b>弱點深度分析與迭代</b>：不再盲目刷題！唯有透過個人化錯題累積，才能進行高度客製化的「疊代升級練習」。<br>"
        "• ⚡ <b>倍增學習效率</b>：幫學生省下 80% 整理錯題本的時間，直擊弱點，用最短時間獲得最大幅度進步！<br><br>"
        "<i>( 綁定 Email 即可立即解鎖每日免費額度與完整功能！ )</i>"
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
            st.error("⚠️ 您的 IP 今日試用額度已用盡！請使用下方 Email 驗證登入。")
        else:
            if st.button("🚀 立即試用（直接進入錯題輸入畫面）", type="primary", use_container_width=True):
                st.session_state["is_trial"] = True
                st.session_state["setup_complete"] = True
                st.rerun()
    st.markdown("---")

    st.subheader("📋 建立 / 登入 / 修改專屬學生個人資料庫")
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
                if not SMTP_USER:
                    st.info(f"🔧 **[測試模式] 驗證碼是： {st.session_state['generated_otp']}**")
                
                with st.form("otp_login_form", border=False):
                    user_otp_input = st.text_input("🔑 請輸入您收到的驗證碼（輸入後可直接按 Enter 鍵）：", max_chars=6)
                    submit_login = st.form_submit_button("🔗 2. 驗證 OTP 並登入", type="primary", use_container_width=True)
                    
                    if submit_login:
                        if user_otp_input == st.session_state["generated_otp"]:
                            st.session_state["user_profile"]["email"] = st.session_state["pending_email"]
                            st.session_state["is_verified"] = True
                            save_recent_email(st.session_state["pending_email"])
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
    
    # 頂部 5 個頁籤全部保留呈現
    tabs = st.tabs(["🏠 返回首頁設定", "📸 錯題解析", "📂 歷史錯題 🔒", "🧠 學習診斷 🔒", "⚙️ 自組考卷 🔒"])
    tab_back, tab_scan, tab_history, tab_diag, tab_custom = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4]

    with tab_back:
        st.subheader("🏠 帳號與個人化設定")
        st.info("💡 您可以在此返回首頁「修改學生資料與興趣」，系統會保留您的登入狀態與歷史紀錄。若要完全登出，請在首頁最下方點擊「登出切換帳號」。")
        if st.button("🔙 返回首頁 / 修改學生資料", type="primary"):
            st.session_state["setup_complete"] = False
            st.session_state["is_trial"] = False
            st.rerun()

    with tab_scan:
        st.subheader("📝 步驟一：上傳照片與圖形劃記確認")
        
        # 潤色後的畫畫圈選引導說明
        st.markdown(
            "<div style='background-color: #f0f7ff; padding: 12px 16px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 15px; font-size: 14px; line-height: 1.6;'>"
            "✍️ <b>考卷智慧標記與圈選（選填）：</b><br>"
            "• <b>精準解答標記：</b> 如果 AI 辨識出的題目不是您想要的，或是遇到<b>空白未寫的題目</b>，您可以直接用手指/滑鼠在<b>題目題號或整道題目上「畫圈圈標記」</b>。<br>"
            "• <b>優先處理：</b> 系統將會優先針對您<b>圈選標記的題目</b>進行精準萃取、詳細解題與產出延伸練習題！"
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
            st.markdown("#### 📸 考卷圈選與標記（請直接在想解答的題目或題號上畫圈）")
            enable_image_fix = st.checkbox("🛠️ 啟用掃描增強 (自動去除灰暗背景/修正空白)", value=True)
            
            cols_img = st.columns(len(valid_files))
            for idx, img_f in enumerate(valid_files):
                with cols_img[idx]:
                    st.caption(f"錯題照片 {idx+1}")
                    raw_img = Image.open(img_f).convert("RGB")
                    
                    # 修正掃描空白/灰暗背景的處理
                    if enable_image_fix:
                        gray_img = raw_img.convert("L")
                        threshold = 200
                        binary_img = gray_img.point(lambda p: 255 if p > threshold else p)
                        raw_img = binary_img.convert("RGB")
                    
                    if CANVAS_AVAILABLE:
                        w, h = raw_img.size
                        canvas_width = 450
                        canvas_height = int(h * (canvas_width / w))
                        
                        canvas_result = st_canvas(
                            fill_color="rgba(255, 0, 0, 0.1)",
                            stroke_width=4,
                            stroke_color="#FF0000", # 固定醒目紅色筆刷
                            background_image=raw_img,
                            update_streamlit=True,
                            height=canvas_height,
                            width=canvas_width,
                            drawing_mode="freedraw",
                            key=f"canvas_{idx}"
                        )
                        if canvas_result.image_data is not None:
                            annotation_overlay = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                            base_img = raw_img.resize((canvas_width, canvas_height)).convert("RGBA")
                            final_img = Image.alpha_composite(base_img, annotation_overlay).convert("RGB")
                            annotated_images.append(final_img)
                        else:
                            annotated_images.append(raw_img)
                    else:
                        st.image(raw_img, use_container_width=True)
                        st.info("💡 提示：安裝 `streamlit-drawable-canvas` 套件即可開啟手寫圈選題目功能！")
                        annotated_images.append(raw_img)

        def perform_ai_scan(files, mode="normal"):
            client_ip = get_client_ip()
            ip_today_key = f"{today_str}_{client_ip}"
            current_ip_trials = st.session_state["ip_trial_history"].get(ip_today_key, 0)

            if is_trial and current_ip_trials >= 1:
                show_trial_conversion_notice()
                return

            if not deduct_credit():
                st.error("⚠️ 您的免費額度已用盡！請明天再來領取每日獎勵。")
                return

            if GENAI_AVAILABLE and PIL_AVAILABLE and GEMINI_KEY:
                try:
                    client = genai.Client(api_key=GEMINI_KEY)
                    
                    if mode == "loose":
                        prompt = "你是資深數學老師。請優先擷取圖片中『被紅筆劃線/圈選註記』、『空白未寫』或『被扣分』的題目。請萃取出題目純文字與完整數學符號。\n"
                    else:
                        prompt = "請萃取圖片中的數學題目文字（特別注意圖片中被畫筆或紅筆圈選標記的重點題目），每行一題，包含完整數學符號。\n"
                    
                    if is_trial:
                        prompt += "【數量限制】：這是試用請求，請精準控管，最多只需要萃取 5 道題目即可。\n"

                    contents = [prompt]
                    images_to_send = annotated_images if annotated_images else [Image.open(f) for f in files]
                    for img in images_to_send:
                        contents.append(img)
                        
                    response = client.models.generate_content(model="gemini-3.5-flash", contents=contents)
                    if response and response.text:
                        st.session_state["scanned_text"] = response.text.strip()
                        if is_trial:
                            st.session_state["ip_trial_history"][ip_today_key] = current_ip_trials + 1
                except Exception as e:
                    handle_api_error(e)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if valid_files and st.button("🤖 開始辨識（包含圖片圈選標記）", use_container_width=True):
                with st.spinner("智慧掃描圈選題目中..."): perform_ai_scan(valid_files, "normal")
                st.rerun()
        with col_btn2:
            if valid_files and st.button("🔄 寬鬆認定再辨識", use_container_width=True):
                with st.spinner("智慧掃描：尋找紅筆標記、留白與錯題中..."): perform_ai_scan(valid_files, "loose")
                st.rerun()

        st.markdown("---")
        
        # 僅在試用狀態下顯示 5 題限制提示，已註冊用戶自動隱藏
        if is_trial:
            st.info("💡 **試用版提示：** 系統將自動辨識並最多擷取 **5 道** 題目（包含您在圖片上圈選標記的重點/空白題目）。完成免費登入後可無限制全卷辨識與存檔！")
        
        edited_text = st.text_area("確認題目內容 (可在框內直接微調圈選要輸出的錯題)：", value=st.session_state["scanned_text"], height=120)
        st.session_state["scanned_text"] = edited_text

        st.markdown("### 🎯 步驟三：自動產出解析與模擬試題")
        
        use_interests_1 = st.checkbox("🌟 模擬試題融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="scan_interest")

        col_mock1, col_mock2 = st.columns(2)
        with col_mock1:
            btn_mock1 = st.button("🚀 執行一鍵產出 (扣1次額度)", type="primary", use_container_width=True)
        with col_mock2:
            btn_mock2 = st.button("🔄 再出一次模擬試題 (扣1次額度)", use_container_width=True)

        if btn_mock1 or btn_mock2:
            client_ip = get_client_ip()
            ip_today_key = f"{today_str}_{client_ip}"
            current_ip_trials = st.session_state["ip_trial_history"].get(ip_today_key, 0)

            if is_trial and current_ip_trials >= 1 and st.session_state["generated_content"]:
                show_trial_conversion_notice()
            elif not edited_text:
                st.warning("請先輸入或辨識題目！")
            elif deduct_credit() and GEMINI_KEY:
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
                        client = genai.Client(api_key=GEMINI_KEY)
                        
                        limit_prompt = " (請精準控管題目數量：產出最多 5 題原錯題解析，與 5 題改數字模擬題) " if is_trial else " (請產出 8 題模擬試題) "
                        
                        prompt_text = "【錯題內容】：\n" + edited_text + "\n\n"
                        prompt_text += "【題庫參考】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_text += f"請為【錯題內容】產出繁體中文的正解與詳細解析，並接著產出{limit_prompt}與詳細解析解答。\n\n"
                        prompt_text += LAYOUT_WITH_ANALYSIS
                        prompt_text += JSON_TEMPLATE_MOCK
                        
                        response = client.models.generate_content(model="gemini-3.5-flash", contents=[prompt_text])
                        if response:
                            st.session_state["generated_content"] = re.sub(r'```json.*?```', '', response.text, flags=re.DOTALL).strip()
                            parse_and_insert_9_col_json(response.text)
                            if is_trial:
                                st.session_state["ip_trial_history"][ip_today_key] = current_ip_trials + 1
                            st.success("成功產出！")
                    except Exception as e: handle_api_error(e)

        if st.session_state["generated_content"]:
            st.markdown(f'<div class="printable-exam-area">{st.session_state["generated_content"]}</div>', unsafe_allow_html=True)
            render_share_buttons(st.session_state["generated_content"], "scan_res")
            
            st.markdown("---")
            st.subheader("🚀 步驟四：疊代升級 (變形題)")
            
            use_interests_var = st.checkbox("🌟 變形題融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="var_interest")

            c_var1, c_var2 = st.columns(2)
            with c_var1: btn_var1 = st.button("產出 5 題變形題 (扣1次額度)", use_container_width=True)
            with c_var2: btn_var2 = st.button("🔄 再生成一次變形題 (扣1次額度)", use_container_width=True)
            
            if btn_var1 or btn_var2:
                if is_trial:
                    show_trial_conversion_notice()
                elif deduct_credit() and GEMINI_KEY:
                    with st.spinner("產出變形題中..."):
                        db_text = fetch_relevant_questions_from_db([edited_text[:30]], limit=10)
                        
                        prompt_var = "錯題內容：\n" + edited_text + "\n\n"
                        prompt_var += "【題庫優先使用】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_var += "請產出 5 題變形試題。\n\n"
                        prompt_var += LAYOUT_NORMAL
                        prompt_var += JSON_TEMPLATE_VAR
                        
                        try:
                            client = genai.Client(api_key=GEMINI_KEY)
                            res_var = client.models.generate_content(model="gemini-3.5-flash", contents=[prompt_var])
                            st.session_state["variation_content"] = re.sub(r'```json.*?```', '', res_var.text, flags=re.DOTALL).strip()
                            parse_and_insert_9_col_json(res_var.text)
                        except Exception as e: handle_api_error(e)
                        
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
            
            use_interests_history = st.checkbox("🌟 歷史複習卷融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="history_interest")
            
            if st.button("產生 10 題複習試卷"):
                if deduct_credit() and GEMINI_KEY:
                    with st.spinner("產出中..."):
                        db_text = fetch_relevant_questions_from_db([history_text[:30]], limit=15)
                        
                        prompt_hist = "歷史錯題：\n" + history_text + "\n\n"
                        prompt_hist += "【題庫優先使用】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_hist += "請產出 10 題歷史錯題複習試卷。\n\n"
                        prompt_hist += LAYOUT_NORMAL
                        prompt_hist += JSON_TEMPLATE_HIST.replace("TAG_PLACEHOLDER", "歷史複習")
                        
                        try:
                            client = genai.Client(api_key=GEMINI_KEY)
                            res_hist = client.models.generate_content(model="gemini-3.5-flash", contents=[prompt_hist])
                            final_hist_content = re.sub(r'```json.*?```', '', res_hist.text, flags=re.DOTALL).strip()
                            st.markdown(f'<div class="printable-exam-area">{final_hist_content}</div>', unsafe_allow_html=True)
                            render_share_buttons(final_hist_content, "hist_res")
                            parse_and_insert_9_col_json(res_hist.text)
                        except Exception as e: handle_api_error(e)

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
            
            st.markdown("#### 📝 選擇試卷題型與數量")
            c_q1, c_q2, c_q3 = st.columns(3)
            with c_q1: tfc_cnt = st.selectbox("是非觀念題", [5, 10, 15])
            with c_q2: mc_cnt = st.selectbox("選擇題", [10, 15, 20])
            with c_q3: calc_cnt = st.selectbox("計算題", [5, 10])

            use_interests_custom = st.checkbox("🌟 自組卷融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="custom_exam_interest")

            col_cust1, col_cust2 = st.columns(2)
            with col_cust1:
                btn_cust1 = st.button("產生自組卷 (扣1次額度)", type="primary", use_container_width=True)
            with col_cust2:
                btn_cust2 = st.button("🔄 再生成不同題目的自組卷 (扣1次額度)", use_container_width=True)

            if btn_cust1 or btn_cust2:
                if not selected_mains or not selected_subs: 
                    st.warning("請先選擇主單元與次單元題型！")
                elif deduct_credit() and GEMINI_KEY:
                    with st.spinner("智慧組卷中..."):
                        main_topics_str = "、".join(selected_mains)
                        sub_topics_str = "、".join(selected_subs)
                        db_text = fetch_relevant_questions_from_db(selected_mains, limit=20)
                        
                        prompt_custom = f"適用年級與版本：{user_gr} {user_ver}\n"
                        prompt_custom += "主單元：\n" + main_topics_str + "\n"
                        prompt_custom += "題型方向：\n" + sub_topics_str + "\n\n"
                        prompt_custom += "【系統題庫資源】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_custom += f"請產出 {tfc_cnt}題是非題、{mc_cnt}題選擇題與 {calc_cnt}題計算題。優先使用上方題庫。\n\n"
                        prompt_custom += LAYOUT_NORMAL
                        prompt_custom += JSON_TEMPLATE_CUSTOM.replace("UNIT_PLACEHOLDER", main_topics_str)
                        
                        try:
                            client = genai.Client(api_key=GEMINI_KEY)
                            res_custom = client.models.generate_content(model="gemini-3.5-flash", contents=[prompt_custom])
                            final_custom_content = re.sub(r'```json.*?```', '', res_custom.text, flags=re.DOTALL).strip()
                            
                            st.session_state["custom_exam_content"] = final_custom_content
                            parse_and_insert_9_col_json(res_custom.text)
                        except Exception as e: handle_api_error(e)
            
            if st.session_state.get("custom_exam_content"):
                st.markdown(f'<div class="printable-exam-area">{st.session_state["custom_exam_content"]}</div>', unsafe_allow_html=True)
                render_share_buttons(st.session_state["custom_exam_content"], "cust_res")

    with tab_diag:
        st.subheader("🧠 學習診斷 🔒")
        if is_trial:
            show_trial_conversion_notice()
        else:
            st.info("敬請期待學習圖表分析！")
