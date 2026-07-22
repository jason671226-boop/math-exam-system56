import io
import streamlit as st
import re

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

# 嘗試載入 PIL 套件用於圖片處理
try:
  from PIL import Image
  PIL_AVAILABLE = True
except ImportError:
  PIL_AVAILABLE = False

# 設定網頁基本屬性
st.set_page_config(
    page_title="AI 數學錯題迭代系統 (最新穩定版)", page_icon="🤖", initial_sidebar_state="expanded"
)

# --- 側邊欄：資訊與說明區塊 ---
with st.sidebar:
  st.markdown(
      """
    <div style="font-size: 1.1em; line-height: 1.6; background-color: #f0f2f6; padding: 12px; border-radius: 8px; border-left: 5px solid #ff4b4b;">
    <b>本系統內容均為陳冠霖老師獨立開發，並擁有全部所有權。</b><br><br>
    目前所需要的開發及維護費用（包含使用的模型費用），皆為陳老師個人負擔。<br><br>
    所以只先開放 30 位使用者使用，<b>每組學生 Email 嚴格限制 30 次免費測試額度（跨日累計扣除）</b>。請多多回饋系統使用經驗！
    </div>
    """,
      unsafe_allow_html=True,
  )
  st.markdown("---")
  st.markdown("### 👨‍🏫 陳冠霖老師簡介")
  st.markdown(
      """
    * **認證奧林匹克數學老師** / 曾經擔任補習班資深教師
    * 具備私中升學成功經驗與 **ADHD、AS 學員**教學經驗
    * 擅長 **AI 迭代訓練** 提升學生解題與應變能力
    * **教學專長**：圖形具象化、專屬口訣、私中熱門應用題（賺賠、溶液、量倍、年齡、雞兔同籠等）
    * **核心理念**：建立思考模式遠比死背解題重要；會算更要會教，幫孩子找回自信！
    """
  )

# --- 主畫面：標題與登入區塊 ---
st.title("🧙‍♂️ AI 數學錯題迭代系統")
st.markdown(
    """
    <div style="background-color: #f0f7ff; padding: 16px; border-radius: 10px; border-left: 6px solid #1c83e1; color: #004085; font-size: 1.05em; line-height: 1.6;">
    <b>> 造就異數的不是 1 萬小時的重複，而是 1 萬次迭代。</b> —— 矽谷知名投資人 Naval Ravikant。<br>
    <b>> 迭代得越快，成長就越快。</b> —— Y Combinator 聯合創辦人 Paul Graham
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# 初始化 session state
if "setup_complete" not in st.session_state:
  st.session_state["setup_complete"] = False
if "user_email" not in st.session_state:
  st.session_state["user_email"] = ""
if "user_credits" not in st.session_state:
  st.session_state["user_credits"] = 30
if "last_uploaded_image_id" not in st.session_state:
  st.session_state["last_uploaded_image_id"] = None

# 💡 確保文字框狀態與畫面完美同步
if "scanned_text" not in st.session_state:
  st.session_state["scanned_text"] = "請在上方輸入 API Key 後，上傳考卷照片以啟動 AI 自動錯題掃描..."

# 第一步：註冊與個人設定
if not st.session_state["setup_complete"]:
  with st.expander("🔐 使用者登入與學生檔案管理 (點此展開/收合)", expanded=True):
    user_email = st.text_input("請手動輸入學生/老師 Email 以綁定額度:", placeholder="student@gmail.com")
    if st.button("✅ 確認設定，啟動 AI 教學系統", use_container_width=True):
      if not user_email:
        st.error("⚠️ 請填寫有效的 Email 帳號！")
      else:
        st.session_state["user_email"] = user_email
        st.session_state["setup_complete"] = True
        st.success("🎉 設定完成！正在進入專屬教學系統...")
        st.rerun()

# 第二步：完成設定後的主畫面功能
else:
  # 條列式使用者資訊
  st.markdown(
      f"""
      <div style="font-size: 0.88em; line-height: 1.6; background-color: #f8fafc; padding: 14px 18px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 15px;">
        <b style="color: #1e293b; font-size: 1.15em;">🎯 歡迎使用 AI 數學系統</b><br><br>
        <b style="color: #0f172a;">身份與對象</b><br>
        <span style="color: #475569; margin-left: 5px;">{st.session_state['user_email']}</span><br>
        <b style="color: #0f172a;">剩餘免費額度</b><br>
        <span style="color: #475569; margin-left: 5px;">🎁 {st.session_state['user_credits']} 次 (跨日累計扣除)</span>
      </div>
      """,
      unsafe_allow_html=True,
  )

  tab1, tab2, tab3 = st.tabs(["📸 錯題拍照與解析出題", "📊 學習報告", "👨‍🏫 管理者後台"])

  with tab1:
    st.subheader("📝 步驟一：設定金鑰與上傳考卷")
    
    # 💡 確保三個金鑰欄位完美顯示
    st.markdown("### 🔑 【系統金鑰與資料庫設定】")
    SUPABASE_URL = st.text_input("SUPABASE_URL =", value="https://your-project.supabase.co")
    SUPABASE_KEY = st.text_input("SUPABASE_KEY =", value="sb_publishable_fa0t2W8U5iwi42GrNJD5Hg_p-J5JsJ5", type="password")
    GEMINI_KEY = st.text_input("GEMINI_KEY =", type="password", placeholder="AIzaSy...", help="請填寫您的 Google Gemini API Key")
    st.markdown("---")

    uploaded_image = st.file_uploader("📸 請上傳學生考卷照片", type=["jpg", "jpeg", "png"])

    # === 獨立的 AI 掃描函式 ===
    def perform_ai_scan(image, mode="normal"):
        if not GEMINI_KEY:
            st.session_state["scanned_text"] = "⚠️ 系統提示：請先在上方輸入『GEMINI_KEY』，再重新上傳或點擊再次掃描。"
            return
        
        if GENAI_AVAILABLE and PIL_AVAILABLE:
            try:
                client = genai.Client(api_key=GEMINI_KEY)
                pil_img = Image.open(image)
                
                if mode == "loose":
                    prompt = (
                        "你是資深的數學批改老師。請以『極度寬鬆』的標準檢視這張考卷圖片。\n"
                        "規則：只要有紅筆打勾、打叉、塗改、計算痕跡、旁邊空白處寫字，或是未完成的題目，全部判定為錯題！\n"
                        "請把題目文字完整萃取出來，每行一題，不要遺漏任何有嫌疑的題目！不要解釋，只要列出純題目文字。"
                    )
                else:
                    prompt = (
                        "你是資深的數學批改老師。請檢視這張數學考卷圖片。\n"
                        "找出被紅筆標記、打叉、扣分或空白的錯題，將題目完整萃取出來。\n"
                        "每行一題，純文字輸出，不需要其他問候語。"
                    )
                
                # 💡 使用 gemini-3.5-flash 模型，確保高相容性與卓越的多模態推理表現
                response = client.models.generate_content(
                    model="gemini-3.5-flash", contents=[prompt, pil_img]
                )
                
                if response and response.text:
                    st.session_state["scanned_text"] = response.text.strip()
                else:
                    st.session_state["scanned_text"] = "⚠️ 系統未能從圖片辨識出文字，請點擊『再次掃描』，或確保圖片清晰。"
            except Exception as e:
                st.session_state["scanned_text"] = f"⚠️ AI 掃描發生錯誤：{str(e)}"
        else:
            st.session_state["scanned_text"] = "⚠️ 系統環境缺少必要套件 (google-genai 或 pillow)，請聯絡管理員。"

    # === 圖片上傳觸發掃描 ===
    if uploaded_image is not None:
      img_id = f"{getattr(uploaded_image, 'name', 'img')}_{uploaded_image.size}"
      if st.session_state.get("last_uploaded_image_id") != img_id:
        st.session_state["last_uploaded_image_id"] = img_id
        with st.spinner("🤖 AI 視覺模型正在掃描新考卷..."):
            perform_ai_scan(uploaded_image, mode="normal")
        st.rerun() # 強制刷新畫面，確保文字框同步！

      st.image(uploaded_image, caption="已成功讀取考卷照片", use_container_width=True)

    # 💡 步驟二：錯題確認與編輯區
    st.markdown("---")
    st.subheader("📝 步驟二：錯題確認與編輯")
    
    col_a, col_b = st.columns([3, 2])
    with col_b:
      if st.button("🔄 再次掃描 (極度寬鬆標準)", use_container_width=True):
          if uploaded_image:
              with st.spinner("🤖 啟動極度寬鬆模式，高精度抓取所有錯題..."):
                  perform_ai_scan(uploaded_image, mode="loose")
              st.success("✅ 已完成極度寬鬆掃描並強制匯入！")
              st.rerun()
          else:
              st.warning("⚠️ 請先上傳考卷照片再執行再次掃描！")

    # 綁定 st.session_state["scanned_text"] 的終極文字框
    st.text_area(
        "以下為偵測到的錯題（您可隨時在此修改、增刪題目）：",
        key="scanned_text", # 直接使用 key 綁定，完美避免卡死問題
        height=220
    )

    # 💡 步驟三：一鍵出題引擎
    st.markdown("---")
    st.subheader("🎯 步驟三：執行解析與出題")
    
    if st.button("🚀 執行一鍵錯題解析與出題", type="primary", use_container_width=True):
        if not GEMINI_KEY:
            st.error("⚠️ 請先在最上方輸入 GEMINI_KEY 才能啟動出題功能！")
        elif not st.session_state["scanned_text"].strip() or "請上傳考卷" in st.session_state["scanned_text"]:
            st.warning("⚠️ 錯題欄內目前沒有題目，請確認掃描結果或手動輸入題目！")
        else:
            with st.spinner("🤖 AI 正在根據您的錯題，全力產出解題、變形題與進階題，請稍候..."):
                try:
                    client = genai.Client(api_key=GEMINI_KEY)
                    
                    # 💡 嚴格限制格式、禁用複雜 LaTeX、並確保分頁的終極 Prompt
                    action_prompt = f"""
                    請擔任一位專業且具備資優水準的數學老師。
                    以下是學生考卷上的錯題內容：
                    ---
                    {st.session_state['scanned_text']}
                    ---
                    
                    請依照以下四個部分，為學生產出專屬的學習內容。
                    
                    【重要格式規定 - 絕對要遵守】：
                    1. 嚴禁使用複雜的 LaTeX 語法（例如 \\frac、\\times 等），請一律使用「純文字」或「基本符號」來表示數學式（例如：1又1/2，20平方公分，x^2，*，/），避免前端網頁產生亂碼。
                    2. 請確保「錯題詳細解題」、「延伸變形題」、「進階挑戰題」的題數與上方錯題欄的題目數量【完全一致】（有幾道錯題，就出幾道變形題和進階題）。
                    
                    請嚴格依照此 Markdown 結構輸出：
                    
                    ## 📝 第一部分：錯題詳細解題
                    （請針對上述錯題，逐題提供清楚的思考步驟與正確答案）
                    
                    ## 🔄 第二部分：延伸變形題
                    （根據原錯題觀念，每題出一道數字與情境不同的延伸變形題，【絕對不要】在此寫出解答）
                    
                    ## 🔥 第三部分：進階挑戰題
                    （根據原錯題觀念，每題出一道難度更高的進階挑戰題，【絕對不要】在此寫出解答）
                    
                    <div style="page-break-after: always; padding: 20px 0; text-align: center; border-bottom: 2px dashed #ff4b4b; color: #ff4b4b;"><b>--- 以下為解答頁，列印時將自動分頁 ---</b></div>
                    
                    ## 💡 第四部分：試題解答與解析
                    （請在此提供「第二部分」與「第三部分」所有您新出題目的詳細計算過程與正確答案）
                    """
                    
                    # 💡 使用 gemini-3.5-flash 模型執行高效率出題與解析
                    response = client.models.generate_content(
                        model="gemini-3.5-flash", contents=[action_prompt]
                    )
                    
                    if response and response.text:
                        st.success("🎉 生成成功！請參考下方內容（可直接列印，解答會自動分頁）。")
                        st.markdown("---")
                        st.markdown(response.text, unsafe_allow_html=True)
                        
                        # 提供列印按鈕
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🖨️ 將此畫面直接列印 / 存成 PDF"):
                             st.markdown("<script>window.print();</script>", unsafe_allow_html=True)
                    else:
                        st.error("⚠️ AI 未回傳結果，請稍後再試。")
                        
                except Exception as e:
                    st.error(f"⚠️ 出題發生錯誤，請檢查 API Key 權限或網路連線：{e}")

  with tab2:
    st.subheader("📊 學習報告")
    st.info("累積足夠錯題與測驗數據後，將在此自動生成圖表與盲點診斷。")
    
  with tab3:
    st.subheader("👨‍🏫 管理者後台")
    pwd = st.text_input("輸入密碼", type="password")
    if pwd == "jason575752":
        st.success("🔓 登入成功！本機暫無新增的家長意見。")
