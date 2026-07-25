import io
import json
import streamlit as st
import re
import urllib.parse
import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import date

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
    page_title="AI 數學錯題迭代系統", page_icon="🤖", initial_sidebar_state="expanded", layout="wide"
)

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

# 興趣目錄定義
interests_catalog = {
    "流行 IP": ["寶可夢 (Pokémon)", "角落小夥伴", "卡比", "汪汪隊立大功", "迪士尼系列"],
    "動漫": ["鬼滅之刃", "咒術迴戰", "葬送的芙莉蓮", "航海王", "名偵探柯南"],
    "手遊": ["傳說對決", "荒野亂鬥", "Roblox", "崩壞：星穹鐵道", "原神"],
    "益智遊戲": ["魔術方塊", "數獨", "密室逃脫", "樂高積木", "大富翁"],
    "體育運動": ["籃球", "羽球", "桌球", "排球", "躲避球"]
}

# 常見免洗信箱黑名單
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
        "email": "trial@example.com", "version": "康軒版", 
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

@st.cache_resource
def init_supabase(url, key):
    if not SUPABASE_AVAILABLE or not url or not key: return None
    try:
        return create_client(url, key)
    except Exception:
        return None

supabase_client = init_supabase(SUPABASE_URL, SUPABASE_KEY)

# --- 🚀 核心功能：從資料庫撈取既有題庫 (Hybrid Generation) ---
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

def render_share_buttons(content_text, key_prefix):
    st.markdown("---")
    st.markdown("#### 📤 試卷輸出與分享選項")
    c_share1, c_share2, c_share3 = st.columns(3)
    with c_share1:
        if st.button("🖨️ 列印 / 轉存 PDF", key=f"{key_prefix}_print", use_container_width=True):
            st.markdown("<script>window.print();</script>", unsafe_allow_html=True)
    with c_share2:
        mail_body = urllib.parse.quote(content_text)
        line_url = f"https://line.me/R/msg/text/?{mail_body[:500]}"
        st.markdown(f'<a href="{line_url}" target="_blank"><button style="width:100%; border-radius:5px; border:1px solid #06C755; background-color:#06C755; color:white; padding:8px; cursor:pointer;">💬 分享到 LINE</button></a>', unsafe_allow_html=True)
    with c_share3:
        st.markdown(f'<a href="mailto:?subject=AI數學專屬試卷與解析&body={mail_body[:1000]}" target="_blank"><button style="width:100%; border-radius:5px; border:1px solid #ccc; background-color:#f8f9fa; padding:8px; cursor:pointer;">📧 Email 傳送</button></a>', unsafe_allow_html=True)

# 9 欄位 JSON 結構化解析與寫入共用函式
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

# ==========================================
# 🌟 全新升級：最高強制級別排版模板 (絕對防呆、保證分離)
# ==========================================
COMMON_LAYOUT_PROMPT = (
    "【★★★ 極度重要：排版與解答格式強制規定 ★★★】\n"
    "1. 必須將「試卷區」與「解答區」完全分開輸出！前面先輸出所有試題（絕對不能在題目旁附答案），最後再統一輸出解答。\n"
    "2. 在「試卷區」中，『除了是非題之外的所有題型』，每一道題目的結尾，都必須強制插入 5 個 HTML 換行標籤 <br><br><br><br><br> 讓學生有空間可以計算與作答。\n"
    "3. 在試題列完後，必須強制單獨空一行，並插入分頁符號代碼：<div style=\"page-break-after: always;\"></div>\n"
    "4. 分頁符號後的「解答區」，請提供所有對應題目的正確答案與詳細步驟。\n"
)

LAYOUT_WITH_ANALYSIS = (
    "【★★★ 極度重要：排版與解答格式強制規定 ★★★】\n"
    "請你嚴格套用以下結構進行輸出，不可隨意省略、不可把解答寫在題目旁邊：\n\n"
    "## 錯題詳細解析\n"
    "（請針對上方學生上傳的錯題，提供正確且詳細的解題步驟）\n\n"
    "## 試卷區（模擬試題）\n"
    "（在這裡列出所有的題目，絕對不能附上任何解答或提示！）\n"
    "（注意：除了「是非題」之外，『每一道題目』的最下方，必須強制加上 5 個換行標籤 <br><br><br><br><br> 讓學生作答寫字）\n\n"
    "<div style=\"page-break-after: always;\"></div>\n\n"
    "## 解答區\n"
    "（在分頁符號後，請在此統一列出這所有題目的正確解答與詳細步驟）\n"
)

LAYOUT_NORMAL = (
    "【★★★ 極度重要：排版與解答格式強制規定 ★★★】\n"
    "請你嚴格套用以下結構進行輸出，不可隨意省略、不可把解答寫在題目旁邊：\n\n"
    "## 試卷區\n"
    "（在這裡列出所有的題目，絕對不能附上任何解答或提示！）\n"
    "（注意：除了「是非題」之外，『每一道題目』的最下方，必須強制加上 5 個換行標籤 <br><br><br><br><br> 讓學生作答寫字）\n\n"
    "<div style=\"page-break-after: always;\"></div>\n\n"
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
        if current_ip_trials >= 2:
            st.error("⚠️ 您的 IP 今日試用額度已用盡！請使用下方 Email 驗證登入。")
        else:
            if st.button("🚀 立即試用（直接進入錯題輸入畫面）", type="primary", use_container_width=True):
                st.session_state["ip_trial_history"][ip_today_key] = current_ip_trials + 1
                st.session_state["is_trial"] = True
                st.session_state["setup_complete"] = True
                st.rerun()
    st.markdown("---")

    st.subheader("📋 建立 / 登入 / 修改專屬學生個人資料庫")
    up = st.session_state["user_profile"]
    def_ln = up.get("last_name", "")
    def_fn = up.get("first_name", "")
    def_email = up.get("email", "") if up.get("email", "") != "trial@example.com" else ""
    def_ver = up.get("version", "康軒版")
    def_traits = up.get("traits", [])

    current_stored_email = st.session_state["user_profile"].get("email", "")
    is_verified = bool(current_stored_email and current_stored_email != "trial@example.com")

    if not is_verified:
        user_email_input = st.text_input("Email (綁定與驗證用)", value=st.session_state["pending_email"] if st.session_state["pending_email"] else def_email)
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
        
        user_otp_input = ""
        if st.session_state["otp_sent"]:
            with col_otp2:
                if not SMTP_USER:
                    st.info(f"🔧 **[測試模式] 驗證碼是： {st.session_state['generated_otp']}**")
                user_otp_input = st.text_input("🔑 請輸入您收到的驗證碼：", max_chars=6)
        st.markdown("---")
    else:
        st.success(f"✅ 您目前已登入 Email：**{current_stored_email}**")
        st.markdown("---")
        
    col_name1, col_name2 = st.columns(2)
    with col_name1: last_n = st.text_input("姓氏", value=def_ln)
    with col_name2: first_n = st.text_input("名字", value=def_fn)
    version_choice = st.selectbox("學習版本", ["康軒版", "南一版", "翰林版", "其他"], index=0)
    
    # === 完美恢復：學生狀況與興趣設定 ===
    learning_traits = [
        "粗心大意", "計算力不足", "基礎觀念不佳", "應用題理解困難", 
        "空間幾何薄弱", "專注力不足容易分心", "考試時間分配不佳", "缺乏訂正習慣",
        "對數學有濃厚興趣", "希望挑戰更高難度的數學", "渴望突破現在的數學能力"
    ]
    selected_traits = st.multiselect("綜合學習狀況：", learning_traits, default=def_traits)
    
    st.markdown("#### 🔹 學生有興趣的事物 (📝 可跨類別複選，系統會自動幫您累積)")
    st.info("💡 系統用途說明：選中興趣大類後，下方會自動展開對應的熱門細項供您勾選。")
    
    selected_category = st.radio("選擇興趣大類：", list(interests_catalog.keys()), horizontal=True)
    
    st.session_state["interest_selections"][selected_category] = st.multiselect(
        f"選擇「{selected_category}」的熱門細項：",
        interests_catalog[selected_category],
        default=st.session_state["interest_selections"][selected_category]
    )
    
    all_interests = []
    for items in st.session_state["interest_selections"].values():
        all_interests.extend(items)
        
    st.session_state["custom_interest"] = st.text_input("其他個人興趣喜好（自行填寫沒列出來的興趣）：", value=st.session_state.get("custom_interest", ""))
    
    final_interests = all_interests.copy()
    if st.session_state["custom_interest"]:
        final_interests.append(st.session_state["custom_interest"])
        
    st.success(f"🎯 **目前已累積的學生興趣清單**：{', '.join(final_interests) if final_interests else '尚未選擇'}")
    
    st.markdown("---")

    if is_verified:
        col_action1, col_action2 = st.columns(2)
        with col_action1:
            if st.button("💾 儲存修改並返回系統", type="primary", use_container_width=True):
                st.session_state["user_profile"]["last_name"] = last_n
                st.session_state["user_profile"]["first_name"] = first_n
                st.session_state["user_profile"]["version"] = version_choice
                st.session_state["user_profile"]["traits"] = selected_traits
                st.session_state["user_profile"]["interests"] = final_interests
                st.session_state["setup_complete"] = True
                st.rerun()
        with col_action2:
            if st.button("🔄 登出切換帳號", use_container_width=True):
                st.session_state["user_profile"]["email"] = "trial@example.com"
                st.session_state["otp_sent"] = False
                st.rerun()
    else:
        if st.button("🔗 2. 驗證 OTP 並登入", type="primary", use_container_width=True):
            if st.session_state["otp_sent"] and user_otp_input == st.session_state["generated_otp"]:
                st.session_state["user_profile"]["email"] = st.session_state["pending_email"]
                st.session_state["user_profile"]["last_name"] = last_n
                st.session_state["user_profile"]["first_name"] = first_n
                st.session_state["user_profile"]["version"] = version_choice
                st.session_state["user_profile"]["traits"] = selected_traits
                st.session_state["user_profile"]["interests"] = final_interests
                st.session_state["setup_complete"] = True
                st.rerun()
            else:
                st.error("❌ 驗證碼錯誤或尚未發送！")

# ==========================================
# 第二頁：主系統畫面
# ==========================================
elif st.session_state["setup_complete"]:
    is_trial = st.session_state.get("is_trial", False)
    if is_trial:
        tabs = st.tabs(["🏠 返回首頁設定", "📸 錯題解析"])
        tab_back, tab_scan = tabs[0], tabs[1]
    else:
        # --- 完美還原：標籤頁名稱 ---
        tabs = st.tabs(["🏠 返回首頁設定", "📸 錯題解析", "📂 歷史錯題", "🧠 學習診斷", "⚙️ 自組考卷"])
        tab_back, tab_scan, tab_history, tab_diag, tab_custom = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4]

    with tab_back:
        # --- 完美還原：不登出說明與按鈕 ---
        st.subheader("🏠 帳號與個人化設定")
        st.info("💡 您可以在此返回首頁「修改學生資料與興趣」，系統會保留您的登入狀態與歷史紀錄。若要完全登出，請在首頁最下方點擊「登出切換帳號」。")
        if st.button("🔙 返回首頁 / 修改學生資料", type="primary"):
            st.session_state["setup_complete"] = False
            st.session_state["is_trial"] = False
            st.rerun()

    with tab_scan:
        st.subheader("📝 步驟一：上傳照片")
        # 支援多圖上傳
        uploaded_files = st.file_uploader("📂 上傳錯題照片 (最多支援 2 張)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        
        valid_files = uploaded_files
        if uploaded_files and len(uploaded_files) > 2:
            st.warning("⚠️ 您上傳了超過 2 張照片，系統將自動為您保留前 2 張以確保處理品質喔！")
            valid_files = uploaded_files[:2]

        def perform_ai_scan(files, mode="normal"):
            if not deduct_credit():
                st.error("⚠️ 您的免費額度已用盡！請明天再來領取每日獎勵。")
                return
            if GENAI_AVAILABLE and PIL_AVAILABLE and GEMINI_KEY:
                try:
                    client = genai.Client(api_key=GEMINI_KEY)
                    anti_latex_prompt = "【強制警告】：絕對禁止使用 LaTeX (如 \\frac, $ $ 等符號)，遇到分數請一律轉換為純文字，例如『5又5/8』或『3/4』，避免系統產生亂碼。"
                    
                    if mode == "loose":
                        prompt = (
                            "你是資深數學老師。請以『寬鬆認定』標準，把考卷上有「紅筆劃掉」、「被扣分」、「空白沒寫」，或是「感覺是學生寫錯的」所有題目，通通掃描萃取出來。只要題目純文字即可。\n" 
                            + anti_latex_prompt
                        )
                    else:
                        prompt = "請萃取圖片中的數學題目文字，每行一題，只要題目。\n" + anti_latex_prompt
                    
                    contents = [prompt]
                    for f in files:
                        contents.append(Image.open(f))
                        
                    response = client.models.generate_content(model="gemini-3.5-flash", contents=contents)
                    if response and response.text:
                        st.session_state["scanned_text"] = response.text.strip()
                except Exception as e:
                    handle_api_error(e)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if valid_files and st.button("🤖 開始辨識", use_container_width=True):
                with st.spinner("掃描中..."): perform_ai_scan(valid_files, "normal")
                st.rerun()
        with col_btn2:
            if valid_files and st.button("🔄 寬鬆認定再辨識", use_container_width=True):
                with st.spinner("智慧掃描：尋找紅筆、留白與錯題中..."): perform_ai_scan(valid_files, "loose")
                st.rerun()

        st.markdown("---")
        edited_text = st.text_area("確認題目內容：", value=st.session_state["scanned_text"], height=120)
        st.session_state["scanned_text"] = edited_text

        st.markdown("### 🎯 步驟三：自動產出解析與模擬試題")
        
        use_interests_1 = st.checkbox("🌟 模擬試題融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="scan_interest")

        # 雙按鈕 (一鍵產出 vs 再出一次模擬試題)
        col_mock1, col_mock2 = st.columns(2)
        with col_mock1:
            btn_mock1 = st.button("🚀 執行一鍵產出 (扣1次額度)", type="primary", use_container_width=True)
        with col_mock2:
            btn_mock2 = st.button("🔄 再出一次模擬試題 (扣1次額度)", use_container_width=True)

        if btn_mock1 or btn_mock2:
            if not edited_text: st.warning("請先輸入或辨識題目！")
            elif deduct_credit() and GEMINI_KEY:
                with st.spinner("產出中..."):
                    try:
                        db_text = fetch_relevant_questions_from_db([edited_text[:20]], limit=5)
                        client = genai.Client(api_key=GEMINI_KEY)
                        
                        # --- 套用最強排版指令 ---
                        prompt_text = "錯題內容：\n" + edited_text + "\n\n"
                        prompt_text += "【題庫參考】\n" + (db_text if db_text else "(無)") + "\n\n"
                        prompt_text += "請產出 8 題模擬試題與詳細解析解答。\n\n"
                        prompt_text += LAYOUT_WITH_ANALYSIS
                        prompt_text += JSON_TEMPLATE_MOCK
                        
                        response = client.models.generate_content(model="gemini-3.5-flash", contents=[prompt_text])
                        if response:
                            st.session_state["generated_content"] = re.sub(r'```json.*?```', '', response.text, flags=re.DOTALL).strip()
                            parse_and_insert_9_col_json(response.text)
                            st.success("成功產出！")
                    except Exception as e: handle_api_error(e)

        if st.session_state["generated_content"]:
            st.markdown(st.session_state["generated_content"], unsafe_allow_html=True)
            # 分享與列印按鈕
            render_share_buttons(st.session_state["generated_content"], "scan_res")
            
            st.markdown("---")
            st.subheader("🚀 步驟四：疊代升級 (變形題)")
            
            use_interests_var = st.checkbox("🌟 變形題融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="var_interest")

            # 雙按鈕 (產出變形題 vs 再生成一次變形題)
            c_var1, c_var2 = st.columns(2)
            with c_var1: btn_var1 = st.button("產出 5 題變形題 (扣1次額度)", use_container_width=True)
            with c_var2: btn_var2 = st.button("🔄 再生成一次變形題 (扣1次額度)", use_container_width=True)
            
            if btn_var1 or btn_var2:
                if deduct_credit() and GEMINI_KEY:
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
                st.markdown(st.session_state["variation_content"], unsafe_allow_html=True)
                # 分享與列印按鈕
                render_share_buttons(st.session_state["variation_content"], "var_res")

    if not is_trial:
        with tab_history:
            st.subheader("📂 學生歷史錯題")
            history_text = st.text_area("錯題內容：", value=st.session_state.get("history_mistakes", "請輸入歷史錯題..."), height=100)
            
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
                            st.markdown(final_hist_content, unsafe_allow_html=True)
                            render_share_buttons(final_hist_content, "hist_res")
                            parse_and_insert_9_col_json(res_hist.text)
                        except Exception as e: handle_api_error(e)

        with tab_custom:
            st.subheader("⚙️ 題目自組卷 (強大 Hybrid 混合出題)")
            
            # 主單元與次單元題型（雙複選）
            user_ver = st.session_state["user_profile"].get("version", "康軒版")
            if user_ver not in syllabus_full: user_ver = "康軒版"
            selected_mains = st.multiselect(f"請選擇【{user_ver}】主單元 (可複選)：", syllabus_full[user_ver])
            
            st.markdown("#### 📖 選擇次單元/題型方向")
            sub_units_options = ["基礎觀念題", "生活情境應用題", "圖形與圖表解析", "進階變化題", "歷屆易錯陷阱題"]
            selected_subs = st.multiselect("請選擇題型方向 (可複選)：", sub_units_options, default=sub_units_options[:2])
            
            # 題型數量選項
            st.markdown("#### 📝 選擇試卷題型與數量")
            c_q1, c_q2, c_q3 = st.columns(3)
            with c_q1: tfc_cnt = st.selectbox("是非觀念題", [5, 10, 15])
            with c_q2: mc_cnt = st.selectbox("選擇題", [10, 15, 20])
            with c_q3: calc_cnt = st.selectbox("計算題", [5, 10])

            use_interests_custom = st.checkbox("🌟 自組卷融合學生興趣情境 (等正式版的時候再開放)", value=False, disabled=True, key="custom_exam_interest")

            # 雙按鈕 (產生自組卷 vs 再生成不同題目)
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
                        
                        prompt_custom = "主單元：\n" + main_topics_str + "\n"
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
                st.markdown(st.session_state["custom_exam_content"], unsafe_allow_html=True)
                # 分享與列印按鈕
                render_share_buttons(st.session_state["custom_exam_content"], "cust_res")

        with tab_diag:
            st.info("敬請期待學習圖表分析！")
