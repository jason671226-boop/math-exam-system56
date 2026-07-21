from google import genai
import json
import random
import string
import urllib.parse
import re
import os
import getpass
from pydantic import BaseModel, Field
from typing import List
from supabase import create_client, Client
from PIL import Image
import streamlit as st

# ==========================================
# 0. Pydantic 架構 (確保 AI 輸出格式正確)
# ==========================================
class QuestionItem(BaseModel):
    education_level: str = Field(description="學製，例如：國小")
    grade: str = Field(description="年級，例如：國小五年級")
    unit_name: str = Field(description="核心單元名稱")
    knowledge_tag: str = Field(description="知識點標籤")
    original_question_text: str = Field(description="原題完整文字內容")
    original_question_answer: str = Field(description="原題正確答案")
    original_question_explanation: str = Field(description="原題的詳細解題步驟與觀念說明")
    original_diagram: str = Field(description="原題的文字圖解 ASCII art，若無圖形則填空字串")
    concept_tip: str = Field(description="解題引導提示")
    new_question: str = Field(description="全新設計的變形挑戰題")
    new_question_diagram: str = Field(description="變形題的文字圖解 ASCII art，若無圖形則填空字串")
    correct_answer: str = Field(description="變形題的正確答案")
    detailed_explanation: str = Field(description="變形題的詳細計算說明")

class QuestionList(BaseModel):
    questions: List[QuestionItem]

# ==========================================
# 1. 核心工具函式 (全方位 LaTeX 符號清洗引擎)
# ==========================================
def clean_latex_tags(text):
    if not text:
        return ""
    
    # 1. 處理填空底線與空格
    text = re.sub(r'\\underline\{\\hspace\{[^}]+\}\}', '<u style="display:inline-block; width:100px; border-bottom:1px solid #333; text-align:center;">&nbsp;</u>', text)
    text = re.sub(r'\\underline\{([^}]+)\}', r'<u>\1</u>', text)
    text = re.sub(r'\\hspace\{[^}]+\}', '&nbsp;&nbsp;&nbsp;&nbsp;', text)
    
    # 2. 處理分數與根號 (包含 \dfrac, \frac)
    text = re.sub(r'\\d?frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', text)
    text = re.sub(r'\\sqrt\{([^}]+)\}', r'√( \1 )', text)
    
    # 3. 替換常見的 LaTeX 數學與幾何符號
    replacements = {
        r'\times': '×', r'\div': '÷', r'\pm': '±', r'\mp': '∓',
        r'\leq': '≤', r'\le': '≤', r'\geq': '≥', r'\ge': '≥',
        r'\neq': '≠', r'\approx': '≈', r'\equiv': '≡',
        r'\pi': 'π', r'\circ': '°', r'\infty': '∞',
        r'\angle': '∠', r'\triangle': '△', r'\square': '□',
        r'\parallel': '∥', r'\perp': '⊥', r'\cdot': '・'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    # 4. 清除多餘的 LaTeX 包裹語法，如 \text{...}, \mathrm{...}, \mathbf{...}
    text = re.sub(r'\\(text|mathrm|mathbf|mathit)\{([^}]+)\}', r'\2', text)
    
    # 5. 清除殘留的錢字號美元符號 ($x + y$ -> x + y)
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    
    # 6. 清理殘留反斜線
    text = text.replace(r'\\', ' ').replace(r'\{', '{').replace(r'\}', '}')
    return text

def render_share_toolbar(unique_id, title_text, download_data, file_name):
    st.markdown(f"#### 📤 「{title_text}」快捷操作與分享列")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.download_button(
            label="📥 下載/列印 HTML 試卷",
            data=download_data,
            file_name=file_name,
            mime="text/html",
            key=f"dl_{unique_id}"
        )
    
    share_msg = urllib.parse.quote(f"分享來自 AI 數學系統的專業試卷：{title_text}！快來一起挑戰！")
    with c2:
        st.markdown(f'<a href="https://social-plugins.line.me/lineit/share?text={share_msg}" target="_blank"><button style="width:100%; background-color:#06C755; color:white; border:none; padding:8px; border-radius:5px; font-weight:bold; cursor:pointer;">💚 分享到 LINE</button></a>', unsafe_allow_html=True)
        
    with c3:
        st.markdown(f'<a href="mailto:?subject={urllib.parse.quote(title_text)}&body={share_msg}" target="_blank"><button style="width:100%; background-color:#4285F4; color:white; border:none; padding:8px; border-radius:5px; font-weight:bold; cursor:pointer;">📧 分享到 Email</button></a>', unsafe_allow_html=True)
        
    with c4:
        copy_html = f"""
        <button onclick="navigator.clipboard.writeText('【{title_text}】已透過 AI 數學系統產生！'); alert('已成功複製分享文字！');" style="width:100%; background-color:#718096; color:white; border:none; padding:8px; border-radius:5px; font-weight:bold; cursor:pointer;">🔗 複製分享連結/文字</button>
        """
        st.markdown(copy_html, unsafe_allow_html=True)
    st.markdown("---")

def get_print_banner_html():
    return """
    <div class="no-print" style="background: linear-gradient(135deg, #2b6cb0, #2c5282); color: white; padding: 20px; text-align: center; border-radius: 8px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="margin: 0 0 8px 0; color: #fff;">🖨️ AI 智慧數學試卷中心</h2>
        <p style="margin: 0 0 15px 0; font-size: 12pt; opacity: 0.9;">點擊下方按鈕即可直接列印或另存為 PDF。列印時建議勾選「背景圖形」以保留完美排版！</p>
        <button onclick="window.print()" style="background-color: #48bb78; color: white; border: none; padding: 12px 30px; font-size: 15pt; font-weight: bold; border-radius: 6px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">🖨️ 立即列印 / 存成 PDF</button>
    </div>
    <style>
        @media print {
            .no-print { display: none !important; }
        }
    </style>
    """

# 嵌入全球標準 MathJax 數學渲染腳本，確保列印 PDF 時防亂碼
MATHJAX_SCRIPT = """
<script>
MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
  },
  svg: { fontCache: 'global' }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
"""

def generate_printable_html(title, items, user_meta):
    diff_text = f" | 困難點：{user_meta.get('parent_difficulty', '')}" if user_meta.get('parent_difficulty', '') else ""
    
    html_questions = ""
    html_answers = ""
    
    for idx, item in enumerate(items):
        q_text = clean_latex_tags(item.get('original_q', ''))
        new_q_text = clean_latex_tags(item.get('new_q', ''))
        
        html_questions += f"""
        <div class="card">
            <div class="card-header">第 {idx + 1} 題 (使用者：{user_meta.get('username', '訪客')} | 版本：{user_meta.get('textbook_version', '通用')} | 目標：{user_meta.get('target_level', '未指定')}{diff_text} )</div>
            <div class="meta"><b>學製年級：</b> {item.get('grade', '')} | <b>核心單元：</b> {item.get('unit', '')}</div>
            <div class="section-title">🛑 原錯題內容：</div>
            <p>{q_text}</p>
            <div class="section-ans">📌 原題解答：{item.get('original_q_ans', '')}</div>
        """
        if item.get('original_diagram'):
            html_questions += f"""<pre class="diagram">{item.get('original_diagram')}</pre>"""
            
        html_questions += f"""
            <div class="section-title">🎯 練習題目：</div>
            <div class="highlight">{new_q_text}</div>
        """
        if item.get('new_q_diagram'):
            html_questions += f"""<pre class="diagram">{item.get('new_q_diagram')}</pre>"""
        html_questions += f"""</div>"""
        
        html_answers += f"""
        <div style="margin-bottom: 25px; border-bottom: 1px dashed #cbd5e0; padding-bottom: 15px;">
            <h3>第 {idx + 1} 題解析（單元：{item.get('unit', '')}）</h3>
            <p><b>正確答案：</b> <span style="color: #2b6cb0; font-size: 16pt;">{item.get('correct_answer', '')}</span></p>
            <p><b>解題引導提示：</b> {clean_latex_tags(item.get('concept_tip', ''))}</p>
            <p><b>詳細計算與觀念說明：</b></p>
            <div style="white-space: pre-wrap; background: #f7fafc; padding: 10px; border-radius: 4px;">{clean_latex_tags(item.get('detailed_explanation', ''))}</div>
        </div>
        """

    teacher_notes = f"""
    <div style="background: #edf2f7; padding: 20px; border-radius: 8px; margin-top: 30px;">
        <h2>👨‍🏫 名師叮囑與題型重點說明</h2>
        <p><b>學生帳號：</b> {user_meta.get('username', '訪客')} | <b>教材版本：</b> {user_meta.get('textbook_version', '康軒版')} | <b>目標等級：</b> {user_meta.get('target_level', 'C級')}</p>
        <p><b>核心複習重點：</b></p>
        <ul>
            <li>本回測驗嚴格對應 108 課綱與指定版本之核心單元，請學生在計算時特別留意進位、小數點位數以及應用題的單位換算。</li>
            <li>若遭遇觀念卡關處，請先對照「原題解題說明」釐清盲點，再進行變形題的二次突破。</li>
            <li>建議家長與老師可根據學生的錯誤頻率，搭配系統的「AI 學習診斷報告」進行針對性強化。</li>
        </ul>
        <p style="text-align: right; margin-top: 20px; font-weight: bold;">—— AI 智慧數學迭代系統 製作 ——</p>
    </div>
    """

    return f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
    {MATHJAX_SCRIPT}
    <style>
        body {{ font-family: "Microsoft JhengHei", "PingFang TC", "Heiti TC", sans-serif; font-size: 14pt !important; line-height: 1.6; color: #333; padding: 20px; }}
        .card {{ margin-bottom: 30px; border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px; }}
        .section-title {{ font-weight: bold; color: #1a365d; margin-top: 15px; font-size: 14pt !important; }}
        p, .highlight, .tip, .explanation {{ font-size: 14pt !important; white-space: pre-wrap; }}
        .diagram {{ background: #1a202c; color: #ae7; padding: 10px; font-family: Courier; white-space: pre; border-radius: 4px; font-size: 12pt; }}
        .page-break {{ page-break-before: always; }}
    </style></head>
    <body>
        {get_print_banner_html()}
        <h1>🧙‍♂️ {title} - 📋 試題卷</h1>
        {html_questions}
        <div class="page-break"></div>
        <h1>🔑 {title} - 📝 答案與詳細解析卷</h1>
        {html_answers}
        {teacher_notes}
    </body></html>
    """

def generate_independent_html(title, items, user_meta):
    html_questions = ""
    html_answers = ""
    for idx, item in enumerate(items):
        q_text = clean_latex_tags(item.get('new_question', ''))
        html_questions += f"""
        <div style="margin-bottom: 30px; border: 1px solid #cbd5e0; padding: 20px; border-radius: 8px;">
            <h3>第 {idx + 1} 題 （單元：{item.get('unit_name', '')} | 知識點：{item.get('knowledge_tag', '')}）</h3>
            <p style="font-size: 14pt; font-weight: bold; white-space: pre-wrap;">{q_text}</p>
        """
        if item.get('new_question_diagram'):
            html_questions += f"""<pre style="background: #edf2f7; padding: 10px; font-family: Courier; white-space: pre;">{item.get('new_question_diagram')}</pre>"""
        html_questions += f"""</div>"""

        html_answers += f"""
        <div style="margin-bottom: 20px; border-bottom: 1px dashed #cbd5e0; padding-bottom: 10px;">
            <p><b>第 {idx + 1} 題答案：</b> <span style="color: #2b6cb0; font-size: 16pt;">{item.get('correct_answer', '')}</span></p>
            <div style="white-space: pre-wrap; background: #f7fafc; padding: 8px;">{clean_latex_tags(item.get('detailed_explanation', ''))}</div>
        </div>
        """

    teacher_notes = f"""
    <div style="background: #edf2f7; padding: 20px; border-radius: 8px; margin-top: 30px;">
        <h2>👨‍🏫 名師叮囑與獨立題型重點</h2>
        <p>獨立變形題旨在針對原題的數字與情境進行邏輯置換，請確保學生完全掌握核心公式而非死記答案。</p>
    </div>
    """

    return f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
    {MATHJAX_SCRIPT}
    <style>
        body {{ font-family: "Microsoft JhengHei", "PingFang TC", "Heiti TC", sans-serif; font-size: 14pt !important; line-height: 1.6; color: #333; padding: 20px; }}
        .page-break {{ page-break-before: always; }}
    </style></head>
    <body>
        {get_print_banner_html()}
        <h1>📋 {title} - 試題卷</h1>
        <p>使用者：{user_meta.get('username', '訪客')} | 版本：{user_meta.get('textbook_version', '通用')}</p>
        <hr>
        {html_questions}
        <div class="page-break"></div>
        <h1>🔑 {title} - 答案與解析卷</h1>
        <hr>
        {html_answers}
        {teacher_notes}
    </body></html>
    """

def generate_mixed_html(title, markdown_text, user_meta):
    markdown_text = clean_latex_tags(markdown_text)
    parts = markdown_text.split("【參考答案】" if "【參考答案】" in markdown_text else "參考答案")
    q_part = parts[0].replace("\n", "<br>")
    a_part = parts[1].replace("\n", "<br>") if len(parts) > 1 else "詳見題目說明"

    teacher_notes = f"""
    <div style="background: #edf2f7; padding: 20px; border-radius: 8px; margin-top: 30px;">
        <h2>👨‍🏫 名師叮囑與總結複習</h2>
        <p>本全真模擬卷嚴格遵守黃金配分（選擇10題、填空20題、計算10題，總分100分）與末題跨單元綜合挑戰。建議於考前 30 分鐘進行計時模擬測驗，培養應試節奏。</p>
    </div>
    """

    return f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
    {MATHJAX_SCRIPT}
    <style>
        body {{ font-family: "Microsoft JhengHei", "PingFang TC", "Heiti TC", sans-serif; font-size: 14pt !important; line-height: 1.6; color: #333; padding: 20px; }}
        .page-break {{ page-break-before: always; }}
    </style></head>
    <body>
        {get_print_banner_html()}
        <h1>🌟 {title} - 試題卷</h1>
        <p>使用者：{user_meta.get('username', '訪客')} | 版本：{user_meta.get('textbook_version', '通用')}</p>
        <hr>
        <div style="white-space: pre-wrap; font-size: 14pt;">{q_part}</div>
        <div class="page-break"></div>
        <h1>🔑 {title} - 答案、配分解析與名師叮囑</h1>
        <hr>
        <div style="white-space: pre-wrap; font-size: 14pt;">{a_part}</div>
        {teacher_notes}
    </body></html>
    """

# ==========================================
# 2. 初始化與設定 (安全讀取 secrets)
# ==========================================
try:
    sb_url = st.secrets.get("SUPABASE_URL", "").strip() if "SUPABASE_URL" in st.secrets else ""
    sb_key = st.secrets.get("SUPABASE_KEY", "").strip() if "SUPABASE_KEY" in st.secrets else ""
    gm_key = st.secrets.get("GEMINI_KEY", "").strip() if "GEMINI_KEY" in st.secrets else ""
except Exception:
    sb_url, sb_key, gm_key = "", "", ""

with st.sidebar:
    st.subheader("⚙️ 雲端與 API 設定")
    if not gm_key: 
        gm_key = st.text_input("🔑 Gemini API Key:", type="password", value="AQ.Ab8RN6K0HfL2do7um5bQtwC0qKpGfCyXwFilrPHRW-Y3ulaBtg")
    if not sb_url: 
        sb_url = st.text_input("🌐 Supabase URL:")
    if not sb_key: 
        sb_key = st.text_input("⚡ Supabase Anon Key:", type="password")

# 初始化 Gemini Client
client = genai.Client(api_key=gm_key) if gm_key else None

db_client = None
if sb_url and sb_key:
    try:
        db_client = create_client(sb_url, sb_key)
    except Exception:
        db_client = None

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_results" not in st.session_state: st.session_state.current_results = None
if "local_item_bank" not in st.session_state: st.session_state.local_item_bank = []
if "mixed_exam_result" not in st.session_state: st.session_state.mixed_exam_result = None
if "auto_quiz_result" not in st.session_state: st.session_state.auto_quiz_result = None
if "saved_accounts" not in st.session_state:
    try:
        sys_user = getpass.getuser()
    except Exception:
        sys_user = "user"
    st.session_state.saved_accounts = [f"{sys_user.lower()}@gmail.com"]

if "user_data" not in st.session_state: 
    st.session_state.user_data = {
        "username": "",
        "login_method": "Email",
        "role": "學生",
        "sub_role": "一般學生",
        "textbook_version": "康軒版",
        "parent_difficulty": "",
        "target_level": "C 級：60 分以上"
    }

# ==========================================
# 3. 註冊與登入系統 (動態記憶功能與帳號重要性說明)
# ==========================================
if not st.session_state.logged_in:
    st.title("🧙‍♂️ AI 數學錯題迭代系統 - 快速登入與註冊")
    
    st.info(
        "💡 **【重要說明：關於綁定 Email / 手機號碼】**\n\n"
        "為了精準記錄學生的個人學習歷程、建構專屬的雲端錯題資料庫，並針對學生容易出錯的盲點進行智慧迭代升級與考前組卷，**綁定專屬的 Email 或手機號碼非常重要！**\n\n"
        "✨ **動態記憶功能**：系統會自動記住您曾輸入過的帳號。下次登入時，直接從選單中點選即可無縫接軌您之前的學習資產與題庫。"
    )
    
    login_type = st.radio("📱 選擇帳號識別類型：", [
        "📧 使用 Email 帳號登入", 
        "📱 使用手機號碼登入"
    ])
    
    if login_type == "📧 使用 Email 帳號登入":
        login_method = st.radio("🔐 Email 登入方式：", [
            "📂 從常用 Email 選單選擇 / 切換", 
            "✉️ 手動輸入新 Email 註冊/登入"
        ])
        if login_method == "📂 從常用 Email 選單選擇 / 切換":
            selected_account = st.selectbox("📬 請選擇您的常用 Email 帳號：", st.session_state.saved_accounts)
            account_input = selected_account
        else:
            account_input = st.text_input("✉️ 請輸入您的 Email：", placeholder="example@email.com")
    else:
        account_input = st.text_input("📱 請輸入您的手機號碼：", placeholder="0912345678")
        
    st.markdown("---")
    
    textbook_version = st.selectbox("📚 請選擇數學教材版本 (將連動考前智慧組卷單元大綱)：", [
        "康軒版", 
        "南一版", 
        "翰林版", 
        "均一教育平台 / 課綱綜合"
    ])

    role = st.selectbox("👨‍🏫 請選擇您的身份：", ["學生", "家長", "老師"])
    
    sub_role = ""
    parent_difficulty = ""
    
    if role == "老師":
        teacher_type = st.selectbox("🏫 老師身份細分：", ["學校老師", "補習班老師", "家教老師", "其他自填"])
        sub_role = teacher_type
    elif role == "家長":
        parent_type = st.selectbox("🎯 家長需求分類：", ["希望報考私立國中", "一般學生練習"])
        sub_role = parent_type
        parent_difficulty = st.text_area(
            "📝 目前學生學習的困難點（例如：觀念不清楚、計算粗心、應用題看不懂等）：",
            placeholder="請簡述學生目前遇到的數學瓶頸或弱點..."
        )
    else:
        sub_role = "一般學生"

    target_level = st.selectbox("📈 希望提升到什麼等級：", [
        "A 級：90 分以上 (難度高、私中資優/進階挑戰)", 
        "B 級：75 分以上 (難度適中、實力扎實標準題)", 
        "C 級：60 分以上 (難度簡單、基礎觀念拆解)"
    ])

    st.markdown("---")
    if st.button("🚀 開始進入系統"):
        clean_account = account_input.strip()
        if clean_account:
            if clean_account not in st.session_state.saved_accounts:
                st.session_state.saved_accounts.append(clean_account)
                
            st.session_state.user_data = {
                "username": clean_account,
                "login_method": login_type,
                "textbook_version": textbook_version,
                "role": role,
                "sub_role": sub_role,
                "parent_difficulty": parent_difficulty,
                "target_level": target_level
            }
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.warning("請填寫對應的帳號聯絡資訊或手機號碼！")
else:
    u_info = st.session_state.user_data
    current_username = u_info.get('username', '訪客')
    current_version = u_info.get('textbook_version', '康軒版')
    
    with st.sidebar:
        st.write(f"👤 **登入帳號：** {current_username}")
        st.write(f"📚 **版本：** {current_version}")
        st.write(f"🏷️ **身份：** {u_info.get('role', '學生')} ({u_info.get('sub_role', '一般')})")
        if u_info.get('role') == '家長' and u_info.get('parent_difficulty'):
            st.write(f"⚠️ **學生困難點：** {u_info.get('parent_difficulty')}")
        st.write(f"📈 **目標：** {u_info.get('target_level', 'C級')}")
        st.markdown("---")
        if st.button("🚪 登出 / 切換帳號"):
            st.session_state.logged_in = False
            st.session_state.current_results = None
            st.session_state.mixed_exam_result = None
            st.session_state.auto_quiz_result = None
            st.rerun()

    # --- 整合分頁功能 ---
    tab_gen, tab_diag, tab_quiz = st.tabs(["⚡ 智慧出題工作台", "📊 AI 學習診斷報告", "📝 考前自動組卷"])

    with tab_gen:
        diff_notice = f" | 關注困難點：{u_info.get('parent_difficulty')}" if u_info.get('parent_difficulty') else ""
        st.info(f"💡 目前出題設定：教材【{current_version}】 | 身份【{u_info.get('role', '學生')} - {u_info.get('sub_role', '一般')}】 | 目標【{u_info.get('target_level', 'C級')}】{diff_notice}")
        
        uploaded_file = st.file_uploader("📸 上傳考卷圖片", type=["png", "jpg", "jpeg"])
        is_marked = st.checkbox("🔍 我在照片旁做了記號")
        
        if st.button("✨ 執行出題"):
            if not client:
                st.error("請先提供有效的 Gemini API Key！")
            elif uploaded_file:
                with st.spinner("🤖 AI 正在依據您的數學版本、身分、等級目標與學習困難點掃描題目、產生變形挑戰題中..."):
                    try:
                        image = Image.open(uploaded_file)
                        
                        target_lvl = u_info.get('target_level', 'C 級')
                        if "A 級" in target_lvl:
                            difficulty_instruction = "【出題難度：A 級 (90分以上)】請設計高難度、具備私立國中資優班水準、多步驟邏輯推理、隱含條件與觀念綜合應用的變形題。"
                        elif "B 級" in target_lvl:
                            difficulty_instruction = "【出題難度：B 級 (75分以上)】請設計標準學校測驗水準、中等難度、核心觀念熟練與標準題型變化的變形題。"
                        else:
                            difficulty_instruction = "【出題難度：C 級 (60分以上)】請設計簡單、基礎概念扎實、數字友善、觀念步驟清楚拆解的入門變形題。"

                        difficulty_context = f" 學生目前學習盲點與困難點為：【{u_info.get('parent_difficulty')}】，請在引導提示與變形題中特別加強此部分的破口訓練。" if u_info.get('parent_difficulty') else ""
                        
                        prompt = f"""
                        你是一個專業的國小高年級數學名師。使用者採用的是「{current_version}」教材，身分為「{u_info.get('role', '學生')}（{u_info.get('sub_role', '一般')}）」。
                        {difficulty_instruction}{difficulty_context}
                        【重要符號規範】：請一律使用學生看得懂的 Unicode 數學符號（如 ×、÷、°、±、≠、≤、≥、1/2），【絕對不要】產生 LaTeX 語法（如 \\times, \\div, \\frac, \\underline 等）。

                        請仔細掃描並分析照片中的【每一道數學題目】：
                        1. 如果照片中有好幾題，請務必【把每一題都獨立抓出來】，在回傳的清單中建立對應的項目。
                        2. 針對每一道被抓到的題目，請完整提供：
                           - 原題完整文字內容與正確答案。
                           - 原題的詳細解題步驟與觀念說明 (original_question_explanation)。
                           - 若原題包含幾何圖形、數線或表格，請用文字圖解 (ASCII art) 繪製在 original_diagram 欄位（若無則留空）。
                           - 解題引導提示 (concept_tip)。
                           - 一道全新的「變形挑戰題」(new_question)，其難度與用語風格必須符合該版本與 A/B/C 級要求。
                           - 變形題的圖解 (new_question_diagram，若有需要繪製圖形輔助請提供，否則留空)。
                           - 變形題的正確答案與詳細計算說明。
                        請務必嚴格依照指定的 Pydantic (QuestionList) 格式輸出 JSON。
                        """
                        
                        response = client.models.generate_content(
                            model='gemini-3.5-flash',
                            contents=[image, prompt],
                            config={
                                "response_mime_type": "application/json",
                                "response_schema": QuestionList,
                            }
                        )
                        
                        result_data = json.loads(response.text)
                        questions = result_data.get("questions", [])
                        st.session_state.current_results = questions
                        st.session_state.mixed_exam_result = None
                        
                        if questions:
                            success_count = 0
                            for q in questions:
                                index_code = f"MATH-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
                                row_data = {
                                    "user_id": current_username,
                                    "index_code": index_code,
                                    "grade": q.get('grade', '國小高年級'),
                                    "unit": q.get('unit_name', '綜合單元'),
                                    "knowledge_tag": q.get('knowledge_tag', '數學觀念'),
                                    "original_question": q.get('original_question_text', ''),
                                    "new_question": q.get('new_question', ''),
                                    "correct_answer": q.get('correct_answer', ''),
                                    "status": "pending"
                                }
                                
                                if db_client:
                                    try:
                                        db_client.table("item_bank").insert(row_data).execute()
                                    except Exception:
                                        pass
                                        
                                st.session_state.local_item_bank.append(row_data)
                                success_count += 1
                            
                            st.success(f"✅ 成功辨識並為帳號【{current_username}】儲存了 {success_count} 道題目的個人化迭代解析！")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"解析發生錯誤：{e}")
            else:
                st.warning("請先上傳圖片！")

        if st.session_state.current_results:
            st.subheader("📊 迭代出題結果與複習專區 (試題與答案完全分頁)")
            
            # 🎯 獨立變形題複習卷
            if st.button("🎯 一鍵整合所有變形題為獨立複習卷"):
                st.markdown("### 📋 【所有變形挑戰題整合複習卷】")
                ind_html = generate_independent_html("獨立變形題複習卷", st.session_state.current_results, u_info)
                
                # 📌 頂部分享列
                render_share_toolbar("ind_top", "獨立變形題複習卷", ind_html, "independent_review_exam.html")

                for idx, item in enumerate(st.session_state.current_results):
                    q_text_disp = clean_latex_tags(item.get('new_question', ''))
                    st.markdown(f"**第 {idx + 1} 題（單元：{item.get('unit_name')} / 標籤：{item.get('knowledge_tag')}）**")
                    st.markdown(f"> {q_text_disp}", unsafe_allow_html=True)
                    if item.get('new_question_diagram'):
                        st.code(item.get('new_question_diagram'), language="text")
                    st.markdown(f"*答案：`{item.get('correct_answer')}`*")
                    st.markdown("---")
                
                # 📌 底部分享列
                render_share_toolbar("ind_bottom", "獨立變形題複習卷", ind_html, "independent_review_exam.html")

            # 🌟 全真綜合模擬卷
            if st.button(f"🌟 產生符合【{current_version}】規範之全真綜合模擬卷 (10選擇20填空10計算•總分100•末題跨單元)"):
                with st.spinner(f"🤖 AI 正在嚴格依據【{current_version}】版本配分與題型架構生成全真模擬卷中..."):
                    try:
                        unit_name = st.session_state.current_results[0].get('unit_name', '綜合數學單元')
                        target_lvl = u_info.get('target_level', 'C 級')
                        
                        mixed_prompt = f"""
                        你是一個專業的國小高年級數學名師。請依據「{current_version}」教材與目標等級「{target_lvl}」，針對單元「{unit_name}」設計一份【完全符合以下規範】的標準全真模擬測驗卷：
                        【重要符號規範】：請一律使用 Unicode 數學符號（×、÷、°、±、≠、1/2），【嚴禁產生 LaTeX 排版標籤】（如 \\times, \\dfrac, \\underline 等）。

                        1. 配分與題型結構嚴格規定：
                           - 一、選擇題：10 題，每題 2 分（共 20 分）
                           - 二、填空題：20 題，每題 2 分（共 40 分）
                           - 三、計算題：10 題，每題 4 分（共 40 分）
                           - 總分：100 分。
                        2. 壓軸題特殊規定：整張考卷的【最後一題】必須是「跨單元綜合題」，必須結合 2 到 3 個不同單元的數學重點來組合出題。
                        3. 輸出格式要求：請明確區分為「一、選擇題」、「二、填空題」、「三、計算題」，並在文章最下方附上「【參考答案】與詳細解析」。請以清晰的 Markdown 格式輸出。
                        """
                        mixed_res = client.models.generate_content(
                            model='gemini-3.5-flash',
                            contents=mixed_prompt
                        )
                        st.session_state.mixed_exam_result = mixed_res.text
                    except Exception as e:
                        st.error(f"產生綜合混和卷發生錯誤：{e}")

            if st.session_state.mixed_exam_result:
                st.markdown("---")
                st.markdown(f"### 🌟 【全真綜合模擬測驗卷 ({current_version}黃金配分版)】")
                
                mixed_html = generate_mixed_html(f"{current_version}全真綜合模擬測驗卷", st.session_state.mixed_exam_result, u_info)
                
                # 📌 頂部分享列
                render_share_toolbar("mixed_top", f"{current_version}全真綜合模擬測驗卷", mixed_html, "mixed_mock_exam.html")
                
                st.markdown(clean_latex_tags(st.session_state.mixed_exam_result), unsafe_allow_html=True)
                
                # 📌 底部分享列
                render_share_toolbar("mixed_bottom", f"{current_version}全真綜合模擬測驗卷", mixed_html, "mixed_mock_exam.html")
                st.markdown("---")

            formatted_items = []
            for item in st.session_state.current_results:
                formatted_items.append({
                    "ip_tag": "GEN",
                    "grade": item.get('grade', ''),
                    "unit": item.get('unit_name', ''),
                    "original_q": item.get('original_question_text', ''),
                    "original_q_ans": item.get('original_question_answer', ''),
                    "original_q_exp": item.get('original_question_explanation', ''),
                    "original_diagram": item.get('original_diagram', ''),
                    "new_q": item.get('new_question', ''),
                    "new_q_diagram": item.get('new_question_diagram', ''),
                    "concept_tip": item.get('concept_tip', ''),
                    "correct_answer": item.get('correct_answer', ''),
                    "detailed_explanation": item.get('detailed_explanation', '')
                })
            
            html_report = generate_printable_html("國小高年級數學錯題迭代報告", formatted_items, u_info)
            
            st.markdown("---")
            st.markdown("### 📥 完整迭代解析報告 快捷操作與分享列")
            # 📌 主報告頂部分享列
            render_share_toolbar("main_top", "國小高年級數學錯題迭代報告", html_report, "math_iteration_report.html")
            
            for idx, item in enumerate(st.session_state.current_results):
                with st.expander(f"第 {idx + 1} 題：【{item.get('unit_name', '')}】 {item.get('knowledge_tag', '')}"):
                    st.markdown(f"**🛑 原題內容：**\n{clean_latex_tags(item.get('original_question_text'))}", unsafe_allow_html=True)
                    st.markdown(f"**📌 原題解答：** {item.get('original_question_answer')}")
                    st.markdown(f"**📝 原題解題說明：**\n{clean_latex_tags(item.get('original_question_explanation'))}")
                    if item.get('original_diagram'):
                        st.code(item.get('original_diagram'), language="text")
                    
                    st.markdown("---")
                    st.markdown(f"**🎯 變形挑戰題：**\n{clean_latex_tags(item.get('new_question'))}", unsafe_allow_html=True)
                    if item.get('new_question_diagram'):
                        st.code(item.get('new_question_diagram'), language="text")
                    st.markdown(f"**💡 引導提示：** {clean_latex_tags(item.get('concept_tip'))}")
                    st.markdown(f"**🔑 變形題正確答案：** {item.get('correct_answer')}")
                    st.markdown(f"**📝 變形題詳細說明：**\n{clean_latex_tags(item.get('detailed_explanation'))}")
            
            # 📌 主報告底部分享列
            render_share_toolbar("main_bottom", "國小高年級數學錯題迭代報告", html_report, "math_iteration_report.html")

    with tab_diag:
        st.subheader("🤖 AI 學習診斷室")
        st.write(f"目前檢視帳號：**{current_username}** ({current_version} / {u_info.get('role')} / {u_info.get('target_level')}) 的全數據診斷報告")
        if st.button("🔍 點擊產生個人化全數據診斷報告"):
            try:
                data_rows = []
                if db_client:
                    try:
                        res = db_client.table("item_bank").select("*").eq("user_id", current_username).execute()
                        data_rows = res.data
                    except Exception:
                        data_rows = []
                
                local_rows = [item for item in st.session_state.local_item_bank if item.get("user_id") == current_username]
                existing_codes = {r.get('index_code') for r in data_rows}
                for lr in local_rows:
                    if lr.get('index_code') not in existing_codes:
                        data_rows.append(lr)

                if data_rows:
                    history_summary = ""
                    for idx, r in enumerate(data_rows):
                        history_summary += f"\n[記錄 {idx+1}] 單元: {r.get('unit')} | 知識點: {r.get('knowledge_tag')} | 原題: {r.get('original_question')} | 變形挑戰題: {r.get('new_question')} | 狀態: {r.get('status')}"
                    
                    diff_analysis = f" 家長特別提到的學生困難點為：【{u_info.get('parent_difficulty')}】。" if u_info.get('parent_difficulty') else ""
                    
                    diagnostic_prompt = f"""
                    請擔任資深數學名師與學習數據分析專家。
                    使用者帳號：{current_username}
                    教材版本：{current_version}
                    身分：{u_info.get('role', '學生')} - {u_info.get('sub_role', '一般')}
                    目標等級：{u_info.get('target_level', 'C級')}
                    {diff_analysis}
                    
                    以下是該學生在資料庫中累積的所有【歷史錯題輸入】與【AI 產出變形題紀錄】：
                    {history_summary}
                    
                    請全面分析上述所有資料，產出一份結構完整的「AI 學習診斷報告」，包含：
                    1. 核心盲點與知識漏洞總體體檢。
                    2. 針對該教材版本與目標等級（{u_info.get('target_level')}）的具體突破策略。
                    3. 針對這些錯題型態的專屬複習與加強建議。
                    """

                    response = client.models.generate_content(
                        model='gemini-3.5-flash',
                        contents=diagnostic_prompt
                    )
                    st.markdown(clean_latex_tags(response.text), unsafe_allow_html=True)
                else:
                    st.warning(f"目前帳號【{current_username}】在雲端與本機記憶體中查無錯題紀錄。但您仍可直接前往「考前自動組卷」產生高標模擬卷！")
            except Exception as e: 
                st.warning(f"診斷產生發生異常：{e}")

    with tab_quiz:
        st.subheader(f"📝 考前自動組卷（已連動【{current_version}】• 3倍豐富選項•五六年級全單元•支援無錯題直接生成）")
        st.write(f"目前檢視帳號：**{current_username}** (教材版本：**{current_version}**) 的智慧組卷中心")
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            quiz_mode = st.selectbox("⚙️ 選擇組卷模式：", [
                "🎯 錯題覆蓋與重點單元智慧混和卷", 
                "🌟 康軒黃金配分全真模擬考 (選擇10題、填空20題、計算10題•總分100)", 
                "⚡ 高強度跨單元壓軸資優挑戰卷"
            ])
        with col_m2:
            quiz_focus = st.selectbox("🎯 選擇題型偏好：", [
                "綜合平均配分 (均衡訓練)", 
                "重點加強應用題與列式題", 
                "重點加強計算與概念推理題"
            ])

        advanced_olympiad_units = [
            "🏆 資優專題-和差與年齡問題", 
            "🏆 資優專題-雞兔同籠與假設問題", 
            "🏆 資優專題-流水問題與逆流順流", 
            "🏆 資優專題-濃度與食鹽水問題", 
            "🏆 資優專題-工作問題與分工合作", 
            "🏆 資優專題-植樹問題與間隔計算"
        ]

        if "南一" in current_version:
            standard_g5_g6_units = [
                "5上(南一)-長條圖和折線圖", "5上(南一)-因數和倍數", "5上(南一)-多邊形", 
                "5上(南一)-擴分約分和通分", "5上(南一)-線對稱圖形", "5上(南一)-異分母分數的加減", 
                "5上(南一)-整數四則計算", "5上(南一)-平行四邊形三角形和梯形面積", "5上(南一)-時間的乘除",
                "5下(南一)-小數的乘法", "5下(南一)-扇形", "5下(南一)-體積", 
                "5下(南一)-整數小數除以整數", "5下(南一)-生活中的大單位", "5下(南一)-比率和百分率", "5下(南一)-容積和容量",
                "6上(南一)-小數的除法", "6上(南一)-圓周率和圓面積", "6上(南一)-比和比值", 
                "6上(南一)-扇形的弧長和面積", "6上(南一)-速率", "6上(南一)-數量關係",
                "6下(南一)-放大圖縮圖和比例尺", "6下(南一)-怎樣解題與搭配問題", "6下(南一)-圓形圖", 
                "6下(南一)-小數與分數綜合應用", "6下(南一)-國小數學總複習"
            ] + advanced_olympiad_units
        elif "翰林" in current_version:
            standard_g5_g6_units = [
                "5上(翰林)-平面圖形", "5上(翰林)-公倍數與公因數", "5上(翰林)-立體形體", 
                "5上(翰林)-四則運算", "5上(翰林)-擴約分與加減", "5上(翰林)-面積", "5上(翰林)-乘以幾分之一",
                "5下(翰林)-整數與小數的乘除", "5下(翰林)-容積與體積", "5下(翰林)-平均與速率", 
                "5下(翰林)-線對稱圖形與扇形", "5下(翰林)-百分率與圓形圖",
                "6上(翰林)-最大公因數與最小公倍數", "6上(翰林)-分數除法", "6上(翰林)-規律問題", 
                "6上(翰林)-比與比值", "6上(翰林)-小數除法", "6上(翰林)-兩量關係與比", 
                "6上(翰林)-圓周長與扇形周長", "6上(翰林)-放大縮小與比例尺",
                "6下(翰林)-等量公理與列式", "6下(翰林)-體積與容積變化", "6下(翰林)-速率與時間應用", 
                "6下(翰林)-怎樣解題與邏輯推理", "6下(翰林)-國小數學總複習"
            ] + advanced_olympiad_units
        elif "均一" in current_version or "綜合" in current_version:
            standard_g5_g6_units = [
                "均一-和差與年齡問題", "均一-雞兔同籠與假設問題", "均一-基準量與比較量", 
                "均一-速率與火車過山洞", "均一-流水問題與逆流順流", "均一-濃度與食鹽水問題",
                "均一-工作問題與分工合作", "均一-植樹問題與間隔計算", "均一-代數列式與未知數",
                "均一-圖形面積與複合圖形", "均一-體積與容積變化綜合", "均一-高年級資優數學總複習"
            ] + advanced_olympiad_units
        else:
            standard_g5_g6_units = [
                "5上-因數與倍數", "5上-公因數與公倍數", "5上-分數的加減與擴約分", "5上-小數的乘法", "5上-多邊形與扇形", "5上-面積與周長", "5上-生活中的單位", "5上-平均數",
                "5下-整數四則運算", "5下-分數的乘除法", "5下-小數的除法", "5下-線對稱圖形", "5下-容積與體積", "5下-長方體與正方體表面積", "5下-折線圖與長條圖", "5下-生活中的速率",
                "6上-分數的除法", "6上-小數除以小數", "6上-比與比值", "6上-圓面積與圓周長", "6上-速率與時間", "6上-柱體、錐體與球", "6上-列式與未知數", "6上-基準量與比較量",
                "6下-比例尺與地圖", "6下-圓形圖與百分率", "6下-等量公理與方程式", "6下-體積與容積變化", "6下-小數與分數綜合應用", "6下-國小數學總複習"
            ] + advanced_olympiad_units

        db_units = []
        if db_client:
            try:
                res_u = db_client.table("item_bank").select("unit").eq("user_id", current_username).execute()
                db_units = [r.get('unit') for r in res_u.data if r.get('unit')]
            except Exception:
                pass
        local_units = [item.get('unit') for item in st.session_state.local_item_bank if item.get("user_id") == current_username and item.get('unit')]
        
        all_available_units = list(dict.fromkeys(standard_g5_g6_units + db_units + ["綜合總複習單元"]))

        selected_units = st.multiselect(f"📂 選擇【{current_version}】組卷核心單元 (含資優專題，可複選多個單元)：", all_available_units, default=[all_available_units[0]])
        
        selected_quiz_level = st.selectbox("🎯 選擇組卷難易度（A/B/C 級）：", [
            "A 級：90 分以上 (高難度/私中進階)", 
            "B 級：75 分以上 (難度適中/實力扎實)", 
            "C 級：60 分以上 (簡單/基礎觀念)"
        ])

        if st.button("🎲 立即生成考前智慧複習卷 (支援無錯題自動組卷)"):
            if not selected_units:
                st.warning("請至少勾選一個核心單元！")
            else:
                with st.spinner(f"🤖 AI 正在綜合您的錯題庫、教材【{current_version}】、多重單元與難度等級，為您現場生成高水準考前複習卷中..."):
                    try:
                        data_rows = []
                        if db_client:
                            try:
                                res = db_client.table("item_bank").select("*").eq("user_id", current_username).eq("status", "pending").execute()
                                data_rows = [r for r in res.data if r.get('unit') in selected_units]
                            except Exception:
                                data_rows = []
                        
                        local_rows = [item for item in st.session_state.local_item_bank if item.get("user_id") == current_username and item.get("unit") in selected_units and item.get("status") == "pending"]
                        existing_codes = {r.get('index_code') for r in data_rows}
                        for lr in local_rows:
                            if lr.get('index_code') not in existing_codes:
                                data_rows.append(lr)

                        target_lvl = u_info.get('target_level', 'C 級')
                        units_str = "、".join(selected_units)
                        
                        ai_quiz_prompt = f"""
                        你是一個資深的國小高年級數學名師。請根據「{current_version}」教材、目標等級「{target_lvl}」、選擇的單元「{units_str}」，以及組卷模式「{quiz_mode}（偏好：{quiz_focus}）」：
                        設計一份專業的考前複習測驗卷。
                        【重要符號規範】：請一律使用 Unicode 數學符號（×、÷、°、±、≠、1/2），【嚴禁產生 LaTeX 排版標籤】（如 \\times, \\dfrac, \\underline 等）。

                        規範要求：
                        1. 題型與數量分配必須嚴格符合：
                           - 一、選擇題：10 題，每題 2 分（共 20 分）
                           - 二、填空題：20 題，每題 2 分（共 40 分）
                           - 三、計算題：10 題，每題 4 分（共 40 分）
                           - 總分：100 分。
                        2. 【壓軸題特殊規定】整張考卷的【最後一題】必須是「跨單元綜合題」，必須融合所選單元中 2 到 3 個核心觀念進行綜合命題。
                        3. 輸出結構必須嚴格分為【試題卷】與【答案與詳細解析卷】兩大部分，並在答案卷最後附上名師叮囑與題型重點。
                        請以清晰的 Markdown 格式輸出。
                        """
                        
                        ai_quiz_res = client.models.generate_content(
                            model='gemini-3.5-flash',
                            contents=ai_quiz_prompt
                        )
                        st.session_state.auto_quiz_result = ai_quiz_res.text
                        st.success("✅ 考前智慧複習卷已成功生成！")
                    except Exception as e:
                        st.error(f"組卷產生發生異常：{e}")

        if st.session_state.auto_quiz_result:
            st.markdown("---")
            st.markdown(f"### 📝 【{current_version} 考前智慧複習測驗卷】")
            
            auto_html = generate_mixed_html(f"{current_version} 考前智慧複習測驗卷", st.session_state.auto_quiz_result, u_info)
            
            # 📌 頂部分享列
            render_share_toolbar("auto_top", f"{current_version} 考前智慧複習測驗卷", auto_html, "pre_exam_smart_quiz.html")
            
            st.markdown(clean_latex_tags(st.session_state.auto_quiz_result), unsafe_allow_html=True)
            
            # 📌 底部分享列
            render_share_toolbar("auto_bottom", f"{current_version} 考前智慧複習測驗卷", auto_html, "pre_exam_smart_quiz.html")
            st.markdown("---")