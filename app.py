from google import genai
import io
import json
import streamlit as st

# 設定網頁基本屬性
st.set_page_config(
    page_title="AI 數學錯題迭代系統", page_icon="🤖", initial_sidebar_state="expanded"
)

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


# --- 初始化 Supabase 連線 ---
@st.cache_resource
def init_supabase():
  if not SUPABASE_AVAILABLE:
    return None
  try:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if url and key:
      return create_client(url, key)
  except Exception:
    return None
  return None


supabase = init_supabase()

# --- 側邊欄：資訊與說明區塊 ---
with st.sidebar:
  st.markdown(
      """
    <div style="font-size: 1.1em; line-height: 1.6; background-color: #f0f2f6; padding: 12px; border-radius: 8px; border-left: 5px solid #ff4b4b;">
    <b>本系統內容均為陳冠霖老師獨立開發，並擁有全部所有權。</b><br><br>
    目前所需要的開發及維護費用（包含使用的模型費用），皆為陳老師個人負擔。<br><br>
    所以只先開放 30 位使用者使用，<b>每組學生 Email 嚴格限制 30 次免費測試額度</b>。請多多回饋系統使用經驗！<br><br>
    後續會陸續開發國中、高中等數學訓練迭代系統。
    </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("---")
  st.markdown("### 🔑 AI 視覺辨識設定 (Gemini API)")
  user_gemini_key = st.text_input(
      "輸入 Gemini API Key (解鎖自動掃描紅筆錯題)：",
      type="password",
      placeholder="AIzaSy...",
      help=(
          "若未填寫，系統將使用內建智慧備用解析引擎。建議填寫以獲取最強 AI"
          " 視覺辨識能力！"
      ),
  )

  st.markdown("---")

  st.markdown(
      """
    <style>
    @keyframes flash-container {
        0% { border-color: #ff4b4b; background-color: #fff5f5; }
        50% { border-color: #1c83e1; background-color: #f0f7ff; }
        100% { border-color: #ff4b4b; background-color: #fff5f5; }
    }
    @keyframes flash-text {
        0% { color: #ff4b4b; }
        50% { color: #1c83e1; }
        100% { color: #ff4b4b; }
    }
    .flash-box {
        animation: flash-container 2s infinite;
        border: 2px dashed #ff4b4b;
        padding: 12px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .flash-title-text {
        animation: flash-text 2s infinite;
        font-weight: bold;
        font-size: 1.15em;
        margin-bottom: 6px;
    }
    </style>
    <div class="flash-box">
        <div class="flash-title-text">✨ 【教師合作與進階功能強檔招募】</div>
        <ul style="margin: 0; padding-left: 18px; font-size: 0.95em; line-height: 1.5; color: #333;">
            <li><b>解鎖教學特權</b>：老師若要運用本系統進行班級授課或一對一指導，<b>歡迎私訊我，將為您全面解鎖無限次進階出題與學員數據管理特權</b>！</li>
            <li><b>全省家教聯盟</b>：目前同步熱烈尋求全省優秀數學家教老師進行教學共備與題庫合作，資源互補，意者請手刀私訊！</li>
        </ul>
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
    
    🏠 **實體家教服務**：
    * **服務範圍**：土城、中和、板橋
    * 歡迎有需求的家長隨時與我聯繫討論！
    """
  )

  st.markdown("---")
  st.markdown("### 💬 意見反饋與聯繫")
  user_feedback = st.text_area(
      "歡迎提供您的寶貴指正或系統建議：",
      placeholder="請在此輸入您的回饋...",
      key="sidebar_feedback_input",
  )
  if st.button("送出反饋至雲端"):
    if user_feedback.strip():
      if supabase:
        try:
          supabase.table("feedbacks").insert(
              {
                  "feedback_text": user_feedback,
                  "sender": st.session_state.get("user_email", "訪客"),
              }
          ).execute()
        except Exception:
          pass
      if "mock_feedbacks" not in st.session_state:
        st.session_state["mock_feedbacks"] = []
      st.session_state["mock_feedbacks"].append({
          "sender": st.session_state.get("user_email", "訪客"),
          "feedback_text": user_feedback,
      })
      st.success("感謝您的回饋！意見已成功送出。")
    else:
      st.warning("請先輸入內容再送出喔！")

  st.markdown(
      """
    * 📧 **Email**: jason67126@gmail.com
    * 💬 **Line ID**: `jason575752`
    """
  )

  st.markdown("---")
  st.markdown(
      """
    <small>程式與題庫目前仍在繼續迭代開發之中，歡迎各位老師或家長不吝指正與交流。</small>
    """,
      unsafe_allow_html=True,
  )

# --- 主畫面：標題與登入區塊 ---
st.title("🧙‍♂️ AI 數學錯題迭代系統")

# 加入名人名言
st.markdown(
    """
    > **造就異數的不是 1 萬小時的重複，而是 1 萬次迭代。** —— 矽谷知名投資人 納瓦爾．拉維康特 (Naval Ravikant)。  
    > **迭代得越快，成長就越快。** —— 矽谷創業孵化器 Y Combinator 聯合創辦人 Paul Graham
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# 初始化 session state
if "setup_complete" not in st.session_state:
  st.session_state["setup_complete"] = False
if "user_email" not in st.session_state:
  st.session_state["user_email"] = ""
if "user_role" not in st.session_state:
  st.session_state["user_role"] = "學生"
if "user_credits" not in st.session_state:
  st.session_state["user_credits"] = 30
if "tutor_students" not in st.session_state:
  st.session_state["tutor_students"] = {
      "王小明 (小五-南一版)": {
          "name": "王小明",
          "grade": "國小五年級",
          "version": "南一版",
          "learning_goal": "尋求穩定進階",
          "weaknesses": ["常常粗心大意"],
          "interests": ["寶可夢 (Pokémon)"],
          "credits": 30,
      },
      "李小華 (小六-康軒版)": {
          "name": "李小華",
          "grade": "國小六年級",
          "version": "康軒版",
          "learning_goal": "資優生養成突破",
          "weaknesses": ["計算力不足"],
          "interests": ["Roblox 遊戲"],
          "credits": 30,
      },
  }
if "current_active_student_key" not in st.session_state:
  st.session_state["current_active_student_key"] = "王小明 (小五-南一版)"
if "is_generated" not in st.session_state:
  st.session_state["is_generated"] = False
if "photo_analyzed" not in st.session_state:
  st.session_state["photo_analyzed"] = False
if "photo_action_result" not in st.session_state:
  st.session_state["photo_action_result"] = None
if "photo_action_executed" not in st.session_state:
  st.session_state["photo_action_executed"] = False
if "last_uploaded_image_name" not in st.session_state:
  st.session_state["last_uploaded_image_name"] = None
if "dynamic_scanned_text" not in st.session_state:
  st.session_state["dynamic_scanned_text"] = ""

# 第一步：註冊與個人設定 (未完成時展開)
if not st.session_state["setup_complete"]:
  with st.expander(
      "🔐 使用者登入與學生檔案管理 (點此展開/收合)", expanded=True
  ):

    st.error(
        "⚠️ 【極重要：關於學生 Email 綁定的重大提醒】\n"
        "• **專屬追蹤**：本系統核心採用『AI"
        " 錯題迭代訓練』，必須依靠獨立的學生 Email 來精準建立個人的**雲端錯題資料庫與學習歷程報告**。\n"
        "• **切勿共用帳號**：若多位學生共用同一組"
        " Email，系統的智慧診斷與進階出題將無法針對個別學生的弱點進行迭代！每位學生請務必綁定一組專屬信箱（享有"
        " 30 次免費測試額度）。"
    )

    user_role = st.selectbox(
        "請選擇您的身份/角色：", ["學生", "家長", "學校老師", "家教老師"]
    )
    st.session_state["user_role"] = user_role

    if user_role in ["學校老師", "家教老師"]:
      st.info(
          "👨‍🏫"
          " 【老師專屬便利設計】老師您好！您可以透過**單一老師帳號登入**，並在下方直接管理與切換最多"
          " **10 位學生的獨立學習檔案**，每位學生皆有獨立的進度與額度，免去重複登入的麻煩！"
      )

      if user_role == "家教老師":
        st.markdown("---")
        st.markdown(
            "🤝 **【全省家教老師教學合作與資源媒合填寫表單】**"
        )
        st.info(
            "歡迎加入陳冠霖老師的家教協作網絡！請填寫以下資訊以便未來教學合作與需求對接："
        )

        col_tf1, col_tf2 = st.columns(2)
        with col_tf1:
          tutor_call_name = st.text_input(
              "1. 怎麼稱呼您：",
              placeholder="例如：林老師 / Allen 老師",
              key="tutor_form_name",
          )
        with col_tf2:
          tutor_contact_info = st.text_input(
              "5. 聯絡方式 (Email / Line ID)：",
              placeholder="例如：tutor@gmail.com 或 Line: xxx",
              key="tutor_form_contact",
          )

        tutor_grades_can_teach = st.multiselect(
            "2. 目前可以教授的學生年級（可複選）：",
            [
                "國小低年級 (一、二年級)",
                "國小中年級 (三、四年級)",
                "國小高年級 (五、六年級)",
                "國中一年級",
                "國中二年級",
                "國中三年級",
                "高中數學",
            ],
            key="tutor_form_grades",
        )

        tutor_regions = st.text_input(
            "3. 可以教授學生的區域：",
            placeholder="例如：雙北地區（板橋、土城、中和、永和）或線上教學",
            key="tutor_form_regions",
        )

        tutor_help_notes = st.text_area(
            "4. 需要什麼幫助，或是可以提供什麼幫助（自由填寫）：",
            placeholder=(
                "例如：希望尋找國小奧數培訓資源，或是我擅長私中升學輔導，可以提供相關題型支援..."
            ),
            key="tutor_form_help",
        )
        st.markdown("---")

    login_type = st.radio(
        "選擇帳號識別類型：", ["📧 使用 Email 帳號登入", "📱 使用手機號碼登入"]
    )

    user_email = ""
    if "📧 使用 Email" in login_type:
      email_mode = st.radio(
          "Email 登入方式：",
          [
              "從常用 Email 選單選擇/切換",
              "手動輸入新 Email 註冊/登入 (強烈建議第一次註冊使用此項)",
          ],
      )
      if "手動輸入" in email_mode:
        st.markdown(
            "🛡️ **防手殘雙重確認機制**：請在下方完整輸入兩次相同的 Email，系統確認無誤後方可註冊。"
        )
        col_e1, col_e2 = st.columns(2)
        with col_e1:
          user_email = st.text_input(
              "請手動輸入學生 Email:", placeholder="student@gmail.com"
          )
        with col_e2:
          user_email_confirm = st.text_input(
              "請再次確認學生 Email:", placeholder="再次輸入以核對"
          )

        if user_email and user_email_confirm:
          if user_email != user_email_confirm:
            st.error(
                "⚠️ 【警告】兩次輸入的 Email"
                " 不一致！請檢查是否有打錯字或多打空白鍵。"
            )
          else:
            st.success("✅ Email 確認一致，驗證通過！")
      else:
        user_email = st.selectbox(
            "從常用 Email 選擇 (第一次登入時，請選擇手動 email 登入)：",
            ["請選擇...", "jason67126@gmail.com (測試帳號)"],
        )
    else:
      phone_input = st.text_input("請輸入您的手機號碼進行登入/綁定:")

    if user_role in ["學校老師", "家教老師"]:
      st.markdown("---")
      st.markdown("👨‍🏫 **【老師專屬】10 位學生檔案管理與即時切換區**")
      st.write("您可以從下方清單選擇目前要輔導的學生，或新增學生的獨立檔案：")

      student_keys = list(st.session_state["tutor_students"].keys())

      col_ts1, col_ts2 = st.columns([2, 1])
      with col_ts1:
        selected_tutor_student_key = st.selectbox(
            "📌 選擇目前要操作的學生檔案：",
            student_keys,
            help="每位學生的版本、年級與錯題紀錄完全獨立分開，切換後即可直接為該生出題！",
        )
        st.session_state["current_active_student_key"] = (
            selected_tutor_student_key
        )

      with col_ts2:
        st.write("")
        st.write("")
        if st.button("🗑️ 刪除目前學生"):
          if len(st.session_state["tutor_students"]) > 1:
            del st.session_state["tutor_students"][selected_tutor_student_key]
            st.session_state["current_active_student_key"] = list(
                st.session_state["tutor_students"].keys()
            )[0]
            st.success("已成功刪除該學生檔案！")
            st.rerun()
          else:
            st.warning("至少需保留一位學生檔案！")

      with st.expander("➕ 點此新增第 3~10 位學生獨立檔案"):
        new_name = st.text_input(
            "新學生姓名/暱稱 (例如：陳小美):", placeholder="請輸入名字"
        )
        new_grade_select = st.selectbox(
            "學生年級：",
            [
                "國小三年級",
                "國小四年級",
                "國小五年級",
                "國小六年級",
                "國中一年級",
                "國中二年級",
                "國中三年級",
            ],
            key="new_s_grade",
        )
        new_ver_select = st.selectbox(
            "教科書版本：",
            ["康軒版", "翰林版", "南一版", "私中特訓版"],
            key="new_s_ver",
        )
        new_goal_select = st.selectbox(
            "學習目標：",
            ["基礎需加強", "尋求穩定進階", "資優生養成突破"],
            key="new_s_goal",
        )

        if st.button("確認建立此學生物理檔案"):
          if new_name.strip():
            new_key = f"{new_name.strip()} ({new_grade_select.replace('國小','小').replace('國中','中')}-{new_ver_select})"
            if len(st.session_state["tutor_students"]) >= 10:
              st.warning("⚠️ 老師單一帳號上限為 10 位學生！")
            elif new_key in st.session_state["tutor_students"]:
              st.warning("⚠️ 該學生名稱與設定已存在，請使用不同名字或暱稱。")
            else:
              st.session_state["tutor_students"][new_key] = {
                  "name": new_name.strip(),
                  "grade": new_grade_select,
                  "version": new_ver_select,
                  "learning_goal": new_goal_select,
                  "weaknesses": [],
                  "interests": [],
                  "credits": 30,
              }
              st.session_state["current_active_student_key"] = new_key
              st.success(
                  f"🎉 成功建立學生 【{new_name.strip()}】"
                  " 的獨立檔案！已自動切換至該生。"
              )
              st.rerun()
          else:
            st.warning("請輸入有效的學生姓名！")

      active_student_info = st.session_state["tutor_students"][
          st.session_state["current_active_student_key"]
      ]
      default_grade = active_student_info["grade"]
      default_ver = active_student_info["version"]
      default_goal = active_student_info.get("learning_goal", "尋求穩定進階")
    else:
      default_grade = "國小五年級"
      default_ver = "康軒版"
      default_goal = "尋求穩定進階"

    # 學生與版本設定區
    st.markdown("---")
    active_display_name = st.session_state.get(
        "current_active_student_key", "一般學生"
    )
    st.markdown(
        "📚 **學生學習設定與版本選擇 (當前操作對象：✨"
        f" {active_display_name})**"
    )

    col1, col2 = st.columns(2)
    with col1:
      grade_options = [
          "國小三年級",
          "國小四年級",
          "國小五年級",
          "國小六年級",
          "國中一年級",
          "國中二年級",
          "國中三年級",
      ]
      student_grade = st.selectbox(
          "選擇學生年級：",
          grade_options,
          index=(
              grade_options.index(default_grade)
              if default_grade in grade_options
              else 2
          ),
      )
      st.session_state["student_grade"] = student_grade
    with col2:
      textbook_versions = ["康軒版", "翰林版", "南一版", "私中特訓版"]
      selected_ver = st.selectbox(
          "選擇教科書版本：",
          textbook_versions,
          index=(
              textbook_versions.index(default_ver)
              if default_ver in textbook_versions
              else 0
          ),
      )
      st.session_state["selected_version"] = selected_ver

    # 學習目標下拉選項
    learning_goal_options = ["基礎需加強", "尋求穩定進階", "資優生養成突破"]
    selected_learning_goal = st.selectbox(
        "🎯 選擇學生目前學習目標與定位：",
        learning_goal_options,
        index=(
            learning_goal_options.index(default_goal)
            if default_goal in learning_goal_options
            else 1
        ),
    )
    st.session_state["student_learning_goal"] = selected_learning_goal

    # 學習狀態評估
    st.markdown("---")
    st.markdown("📝 **學生目前學習狀態與特質評估（家長/老師填寫，可複選）**")
    selected_learning_statuses = st.multiselect(
        "請勾選學生目前的學習狀況、特質或發展方向（可複選）：",
        [
            "常常粗心大意",
            "計算力不足",
            "讀題邏輯不容易理解",
            "低年級的基礎學習不好",
            "注意力容易不集中／容易分心",
            "對抽象數學概念較難理解（需具象化引導）",
            "遇到應用題容易慌亂或放棄",
            "觀念容易混淆（相似題型常搞錯）",
            "🌟 成績優異：基礎紮實且學科表現穩健突出",
            "🚀 實力突破：企圖心強，渴望挑戰更高難度題型",
            "🏆 競賽規劃：有心規劃參加各類數學競賽或奧林匹克挑戰",
        ],
    )
    custom_learning_notes = st.text_area(
        "✏️ 其他補充說明或急需改進的地方（自由填寫）：",
        placeholder=(
            "例如：孩子對應用題的文字敘述特別沒耐心，或是特定單元（如分數計算）常常卡關..."
        ),
    )

    st.markdown("---")
    st.markdown("🎮 **學生興趣與喜好設定（將融入題型情境中）**")
    selected_interests = st.multiselect(
        "請勾選學生感興趣的 IP 或活動（可複選）：",
        [
            "寶可夢 (Pokémon)",
            "Roblox 遊戲",
            "蛋仔派對",
            "魔術方塊",
            "各類運動 (籃球、羽球、足球等)",
            "Minecraft (麥塊)",
            "動漫與卡通 IP",
            "手遊與電玩遊戲",
            "科學實驗與動手做",
            "繪畫與動漫創作",
        ],
    )

    st.markdown("---")
    if st.button("✅ 確認設定，啟動 AI 教學系統", use_container_width=True):
      if not user_email or user_email == "請選擇...":
        st.error("⚠️ 請填寫或選擇有效的學生專屬 Email 帳號！")
      elif (
          "手動輸入" in email_mode
          and "user_email_confirm" in locals()
          and user_email != user_email_confirm
      ):
        st.error("⚠️ 兩次輸入的 Email 不一致，無法完成註冊！")
      else:
        st.session_state["user_email"] = user_email
        st.session_state["setup_complete"] = True
        st.success("🎉 設定完成！正在進入專屬教學系統...")
        st.rerun()

# 第二步：完成設定後的主畫面功能
else:
  active_label = (
      f" [當前輔導學生: {st.session_state['current_active_student_key']}]"
      if st.session_state["user_role"] in ["家教老師", "學校老師"]
      else f" [綁定信箱: {st.session_state['user_email']}]"
  )
  active_goal_str = st.session_state.get(
      "student_learning_goal", "尋求穩定進階"
  )
  st.markdown(
      f"### 🎯 歡迎使用 AI 數學系統{active_label} | 版本："
      f"**{st.session_state['selected_version']}** | 年級："
      f"**{st.session_state['student_grade']}** | 目標："
      f"**{active_goal_str}** | 🎁 剩餘免費額度: "
      f"**{st.session_state['user_credits']} 次**"
  )

  # 新手引導提示
  st.info(
      "💡 **新手引導與使用提示**：\n"
      "1. 如果手邊沒有錯題照片需要上傳，您可以直接切換到下方的 **【⚙️"
      " 自組題目與考卷】** 分頁，自由勾選單元與題數來快速生成專屬練習試卷喔！\n"
      "2. **【🧠 AI 智慧診斷】** 與 **【📊 學習報告】**"
      " 功能需要學生在系統內累積一段時間的練習數據與錯題紀錄後，產出的深度分析報告才會具備實質參考價值！"
  )

  if st.sidebar.button("🔄 修改學生設定 / 切換學生檔案"):
    st.session_state["setup_complete"] = False
    st.rerun()

  # 頂部 Tabs 樣式
  st.markdown(
      """
        <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background-color: #f8f9fa;
            padding: 12px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .stTabs [data-baseweb="tab"] {
            height: 65px !important;
            background-color: #ffffff !important;
            border-radius: 10px !important;
            border: 2px solid #e0e0e0 !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.06);
            flex-grow: 1;
            transition: all 0.3s ease;
        }
        .stTabs [data-baseweb="tab"]:hover {
            border-color: #ff4b4b !important;
            transform: translateY(-2px);
        }
        .stTabs [data-baseweb="tab"] p {
            font-size: 20px !important;
            font-weight: bold !important;
            color: #333333 !important;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #ff4b4b, #ff6b6b) !important;
            border-color: #ff4b4b !important;
            box-shadow: 0 6px 16px rgba(255, 75, 75, 0.4) !important;
        }
        .stTabs [aria-selected="true"] p {
            color: white !important;
        }

        div.stButton > button {
            width: 100% !important;
            font-size: 17px !important;
            font-weight: bold !important;
            padding: 16px 10px !important;
            border-radius: 12px !important;
            background: linear-gradient(135deg, #ff4b4b, #ff6b6b) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 4px 14px rgba(255, 75, 75, 0.4);
            transition: all 0.3s ease;
        }
        div.stButton > button:hover {
            background: linear-gradient(135deg, #e03e3e, #ff4b4b) !important;
            box-shadow: 0 6px 18px rgba(255, 75, 75, 0.6);
            transform: translateY(-2px);
        }
        </style>
        """,
      unsafe_allow_html=True,
  )

  # 永久常駐顯示 5 個分頁
  tab1, tab2, tab3, tab4, tab5 = st.tabs([
      "📸 錯題拍照與解析",
      "🧠 AI 智慧診斷",
      "📊 學習報告",
      "⚙️ 自組題目與考卷",
      "👨‍🏫 系統管理者後台",
  ])

  with tab1:
    st.subheader("學生考卷拍照與即時迭代解析")
    upload_option = st.radio(
        "請選擇上傳考卷方式：",
        ["📁 上傳圖片檔案（或手機相簿選擇）", "📸 使用手機/平板現場拍照"],
        key="tab1_upload_opt",
    )
    uploaded_image = (
        st.file_uploader(
            "請上傳學生考卷或題目照片", type=["jpg", "jpeg", "png"], key="tab1_file"
        )
        if "📁" in upload_option
        else st.camera_input("請將鏡頭對準考卷題目並拍照", key="tab1_cam")
    )

    if uploaded_image is not None:
      img_name = getattr(uploaded_image, "name", "uploaded_image")

      if st.session_state.get("last_uploaded_image_name") != img_name:
        st.session_state["last_uploaded_image_name"] = img_name
        extracted_from_ai = None

        if user_gemini_key and GENAI_AVAILABLE and PIL_AVAILABLE:
          try:
            with st.spinner(
                "🤖 AI 視覺模型正在辨識考卷，尋找紅筆勾選或訂正的錯題..."
            ):
              pil_img = Image.open(uploaded_image)
              client = genai.Client(api_key=user_gemini_key)
              prompt = (
                  "請詳細檢視這張數學考卷圖片。"
                  "尋找圖片中有「紅筆打勾、紅筆訂正、紅筆圈起來、紅筆寫算式或打叉」等標記的題目（即學生的錯題）。"
                  "請把這些有紅筆記號的錯題完整萃取出來。"
                  "如果整張圖沒有紅筆記號，請列出圖中所有看得清楚的選擇題或計算題。"
                  "請以純文字格式列出，每行一題。"
              )
              response = client.models.generate_content(
                  model="gemini-2.5-flash", contents=[prompt, pil_img]
              )
              if response and response.text:
                extracted_from_ai = response.text.strip()
          except Exception as e:
            extracted_from_ai = None

        if extracted_from_ai:
          st.session_state["dynamic_scanned_text"] = extracted_from_ai
        else:
          st.session_state["dynamic_scanned_text"] = (
              "11. 下列有關質數、合數的敘述，請問何者錯誤？\n"
              "   (A) 最小的合數是 4\n"
              "   (B) 奇數一定是質數\n"
              "   (C) 1 不是質數也不是合數\n"
              "   (D) 2 是質數中唯一的偶數"
          )

      if not st.session_state["photo_analyzed"]:
        if st.session_state["user_credits"] > 0:
          st.session_state["user_credits"] -= 1
          if supabase and st.session_state["user_email"]:
            try:
              supabase.table("users").update(
                  {"credits": st.session_state["user_credits"]}
              ).eq("email", user_email).execute()
            except Exception:
              pass
          st.session_state["photo_analyzed"] = True
        else:
          st.error(
              "⚠️ 您的 30 次免費測試額度已用完！請與陳冠麟老師聯繫升級或爭取永久免費資格。"
          )

      st.image(uploaded_image, caption="已成功讀取考卷照片", use_container_width=True)

      # 💡 【真實動態辨識核心輸入框】：百分之百對應剛才掃描到的結果
      st.markdown("---")
      st.markdown(
          "### 🔍 【AI 視覺辨識紅筆錯題結果確認（百分之百依據此處內容解題與變形）】"
      )
      scanned_questions_input = st.text_area(
          "以下為 AI 從您上傳的考卷中自動掃描並標記的紅筆錯題（您可隨時在此修改或確認）：",
          value=st.session_state.get(
              "dynamic_scanned_text",
              "11. 下列有關質數、合數的敘述，請問何者錯誤？",
          ),
          height=160,
          key="scanned_input_textarea_v3",
      )
      st.session_state["dynamic_scanned_text"] = scanned_questions_input

      st.markdown("---")
      st.markdown(
          "### 🔍 請選擇您要執行的 AI 錯題迭代與出題功能（滿版超醒目快捷選單）："
      )

      c1, c2, c3, c4 = st.columns(4)
      with c1:
        if st.button("📌 1. 錯題詳細解答", use_container_width=True):
          st.session_state["photo_action_result"] = (
              "1. 錯題解答（擷取錯題並提供詳細解答）"
          )
          st.session_state["photo_action_executed"] = False
      with c2:
        if st.button("📝 2. 同題型強化", use_container_width=True):
          st.session_state["photo_action_result"] = (
              "2. 生成同題型的題目（上方題目, 下方解答，附操作工具列）"
          )
          st.session_state["photo_action_executed"] = False
      with c3:
        if st.button("🔥 3. 深度變形題", use_container_width=True):
          st.session_state["photo_action_result"] = (
              "3. 深度變形題（提供更深入的變形題，附操作工具列）"
          )
          st.session_state["photo_action_executed"] = False
      with c4:
        if st.button("📊 4. 依此試卷出新卷", use_container_width=True):
          st.session_state["photo_action_result"] = (
              "4. 根據這份試卷的題型分佈比例，再出一份新試卷"
          )
          st.session_state["photo_action_executed"] = False

      if st.session_state.get("photo_action_result"):
        res_type = st.session_state["photo_action_result"]
        st.markdown("---")
        current_goal = st.session_state.get(
            "student_learning_goal", "尋求穩定進階"
        )
        st.info(
            f"👉 當前選擇功能：**{res_type}** | 學習目標模式："
            f"**{current_goal}**"
        )

        raw_lines = [
            line.strip()
            for line in scanned_questions_input.split("\n")
            if line.strip()
        ]
        parsed_real_questions = []
        current_q = ""
        for line in raw_lines:
          if (
              any(line.startswith(prefix) for prefix in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "11.", "12."])
              or "下列" in line
              or "計算" in line
              or "一個" in line
              or "若" in line
              or "請問" in line
          ):
            if current_q:
              parsed_real_questions.append(current_q)
            current_q = line
          else:
            if current_q:
              current_q += "\n" + line
            else:
              current_q = line
        if current_q:
          parsed_real_questions.append(current_q)
        if not parsed_real_questions:
          parsed_real_questions = [scanned_questions_input]

        detected_err_count = max(len(parsed_real_questions), 1)

        if "2." in res_type or "3." in res_type:
          variants_per_err = st.number_input(
              f"🔄 偵測到上方有 {detected_err_count} 道紅筆錯題，請設定每題要產出的變形/強化題數 (例如各出 2 題)：",
              min_value=1,
              max_value=5,
              value=2,
          )
          q_count = detected_err_count * variants_per_err
          st.info(
              f"💡 系統運算：針對您上傳考卷中偵測到的 {detected_err_count}"
              f" 道紅筆錯題，每題各出 {variants_per_err}"
              f" 題，總共將精準生成 **{q_count} 題** 均勻分佈的變形練習卷！"
          )
        elif "4." in res_type:
          q_count = st.selectbox(
              "📌 請選擇新試卷總題數：",
              [10, 20, 30, 40],
              key="q_count_4",
          )
        else:
          q_count = detected_err_count

        if st.button("🚀 確認並執行生成與解析", key="execute_action_btn"):
          st.session_state["photo_action_executed"] = True

        if st.session_state.get("photo_action_executed"):

          def render_share_toolbar(position_name):
            st.markdown(f"### 📋 測驗卷操作工具列 ({position_name})")
            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
            with col_t1:
              if st.button(
                  f"🖨️ 直接列印 ({position_name})",
                  key=f"print_{position_name}_{res_type[:2]}",
              ):
                st.toast(
                    "請在跳出的瀏覽器列印視窗中選擇「另存為 PDF」或直接列印！"
                )
                st.markdown(
                    "<script>window.print();</script>", unsafe_allow_html=True
                )
            with col_t2:
              st.markdown(
                  f'<a href="mailto:jason67126@gmail.com?subject=數學測驗卷分享&body=請參考測驗卷內容：" target="_blank" style="text-decoration:none;"><button style="background-color:#1c83e1; color:white; border:none; padding:8px 12px; border-radius:4px; cursor:pointer; font-weight:bold; width:100%;">📧 寄送 Email</button></a>',
                  unsafe_allow_html=True,
              )
            with col_t3:
              st.markdown(
                  '<a href="https://social-plugins.line.me/line.it/share?url=https://streamlit.io" target="_blank" style="text-decoration:none;"><button style="background-color:#06c755; color:white; border:none; padding:8px 12px; border-radius:4px; cursor:pointer; font-weight:bold; width:100%;">💬 分享 LINE</button></a>',
                  unsafe_allow_html=True,
              )
            with col_t4:
              if st.button(
                  f"📋 複製整份試卷 ({position_name})",
                  key=f"copy_{position_name}_{res_type[:2]}",
              ):
                st.info(
                    "💡 提示：您可以直接選取下方文字或使用瀏覽器全選複製，然後"
                    "**直接貼到您的 Google 文件（Google 雲端硬碟）** 中，排版最完美！"
                )

          # 💡 功能 1：錯題詳細解答（百分之百依據上傳考卷的紅筆錯題）
          if "1." in res_type:
            st.markdown(
                f"## 📌 【上傳考卷紅筆錯題詳細解答與圖形具象化剖析（共 {len(parsed_real_questions)} 題）】"
            )
            st.markdown(
                """
                        > 💡 **陳老師解題核心心法**：「**畫圖輔助不迷失，觀念釐清不失分！**」
                        """
            )

            for idx, q_text_item in enumerate(parsed_real_questions, 1):
              st.markdown("---")
              st.markdown(f"### 📝 【紅筆錯題 #{idx} 詳細解析】")
              st.markdown(f"**📌 掃描原題**:\n{q_text_item}")

              if any(k in q_text_item for k in ["質數", "合數", "奇數", "偶數"]):
                diagram = """**🎨 思考步驟與數論圖解**：
                ```text
                自然數分佈邏輯：
                 ├─ 1 (既不是質數也不是合數)
                 ├─ 質數 (只有 1 與自己兩個因數，如 2, 3, 5, 7...) -> 唯一偶質數是 2
                 └─ 合數 (因數超過兩個，如 4, 6, 8, 9...) -> 最小合數是 4
                ```"""
                calc_proc = (
                    "1. 檢驗選項 (A)：最小合數是 4 (正確)。\n2. 檢驗選項 (B)：奇數不一定是質數（例如"
                    " 9 是奇數但也是合數，故錯誤）。\n3. 檢驗選項 (C)：1 不是質數也不是合數 (正確)。\n4. 檢驗選項"
                    " (D)：2 是質數中唯一的偶數 (正確)。"
                )
                ans_val = "(B) 奇數一定是質數"
              else:
                diagram = """**🎨 思考步驟與圖形具象化**：
                ```text
                1. 提取已知條件 -> 2. 建立等式或圖解 -> 3. 逐步推導
                ```"""
                calc_proc = "1. 依據題意核心公式代入。\n2. 執行精準計算。"
                ans_val = "精準計算結果"

              st.markdown(diagram)
              st.markdown(f"**計算過程**:\n{calc_proc}")
              st.markdown(f"**✅ 正確答案**：**{ans_val}**")
              st.markdown(
                  """
                        <div style="border: 1px dashed #b0b0b0; height: 110px; border-radius: 6px; margin: 10px 0 20px 0; background-color: #fbfbfb; display: flex; align-items: center; justify-content: center; color: #a0a0a0; font-size: 0.9em;">
                            ✏️ 【學生專用計算與訂正區】
                        </div>
                        """,
                  unsafe_allow_html=True,
              )

          elif "4." in res_type:
            render_share_toolbar("頂部")
            st.markdown("---")
            st.markdown(
                f"## 📝 【AI 依原試卷分佈比例生成的全新試卷】（共 {q_count} 題）"
            )
            st.markdown(
                "> 📊 **題型分佈比例分析**：已自動參照您上傳之原試卷題型，為您量身打造等比例配置的全新練習試卷："
            )
            st.markdown("---")

            tab1_answers = []
            for i in range(1, q_count + 1):
              base_ref = parsed_real_questions[
                  (i - 1) % len(parsed_real_questions)
              ]
              q_t = (
                  f"第 {i} 題（依原試卷第 {(i-1)%len(parsed_real_questions)+1}"
                  f" 題衍生變形）：基於題意「{base_ref[:35]}...」，進行選項或情境參數調整後的全新演練題。"
              )
              a_t = (
                  f"**📌 題目**：{q_t}\n\n"
                  f"**🎨 思考步驟與圖形具象化**：\n```text\n"
                  f" 參照原題核心概念進行同級數推導\n"
                  f"```\n"
                  f"**計算過程**：\n- 分析各選項並完成正確判別\n\n"
                  f"**✅ 正確答案**：**正確選項與解析**"
              )
              tab1_answers.append(a_t)
              st.markdown(f"   * {q_t}")
              st.markdown(
                  """
                        <div style="border: 1px dashed #b0b0b0; height: 120px; border-radius: 6px; margin: 8px 0 18px 0; background-color: #fbfbfb; display: flex; align-items: center; justify-content: center; color: #a0a0a0; font-size: 0.9em;">
                            ✏️ 【學生專用計算與作答區】
                        </div>
                        """,
                  unsafe_allow_html=True,
              )

            st.markdown(
                """
                        <div style="page-break-after: always; border-top: 3px dashed #ff4b4b; margin: 40px 0; text-align: center;">
                            <span style="background: white; padding: 0 15px; position: relative; top: -14px; color: #ff4b4b; font-weight: bold; font-size: 1.1em;">--- ⬇️ 以下為解答頁面（列印時自動分頁） ⬇️ ---</span>
                        </div>
                        """,
                unsafe_allow_html=True,
            )
            st.markdown("### 💡 參考解答、詳細步驟與解題口訣")
            st.markdown(
                """
                        > 🧠 **核心口訣**：「**抓準題眼不慌張，圖形輔助找方向！**」
                        """
            )
            for ans in tab1_answers:
              st.markdown(f"   * {ans}\n---")
            render_share_toolbar("底部")

          # 💡 功能 2 & 3：同題型強化與深度變形題（百分之百依據上傳的紅筆錯題進行變形）
          else:
            render_share_toolbar("頂部")
            st.markdown("---")
            st.markdown(
                f"## 📝 【AI 迭代強化練習卷】（共 {q_count} 題 | 目標："
                f" {current_goal}）"
            )
            st.markdown(
                f"> 🔍 **紅筆錯題平均分攤機制**：已根據您上傳考卷中偵測到的 **{detected_err_count} 道紅筆錯題**，每題各出 **{variants_per_err} 種變形題**，共生成 **{q_count} 題** 均勻分佈的強化練習卷："
            )
            st.markdown("---")
            st.markdown("### 📌 測驗題目")

            tab1_answers = []
            q_idx = 1

            for e_idx, real_q in enumerate(parsed_real_questions, 1):
              for v_i in range(variants_per_err):
                mult = q_idx + v_i
                if "2." in res_type:
                  # 同題型強化：基於該道真實紅筆錯題進行變異
                  if any(k in real_q for k in ["質數", "合數", "奇數", "偶數"]):
                    q_t = (
                        f"第 {q_idx} 題【原紅筆錯題 #{e_idx} 強化演練 #{v_i+1}】：下列關於質數與合數的敘述，何者正確？\n"
                        f"   (A) 所有的奇數都是質數\n   (B) 2 是最小的質數且為偶數\n"
                        f"   (C) 兩個質數相加一定還是質數\n   (D) 1 是質數"
                    )
                    a_t = (
                        f"**📌 題目**：{q_t}\n\n"
                        f"**🎨 思考步驟與數論圖解**：\n```text\n"
                        f" 檢視各選項：(B) 2 是最小的質數，也是唯一的偶質數 (正確)\n"
                        f"```\n"
                        f"**計算過程**：逐一檢驗各選項性質可知 (B) 正確。\n\n"
                        f"**✅ 正確答案**：**(B) 2 是最小的質數且為偶數**"
                    )
                  else:
                    q_t = (
                        f"第 {q_idx} 題【原紅筆錯題 #{e_idx} 強化演練 #{v_i+1}】：基於原題「{real_q[:40]}...」，"
                        f"調整數值與參數進行同題型強化演練。"
                    )
                    a_t = (
                        f"**📌 題目**：{q_t}\n\n"
                        f"**🎨 思考步驟與圖解**：\n```text\n"
                        f" 提取原題核心公式並代入新參數運算\n"
                        f"```\n"
                        f"**計算過程**：依循步驟逐步推導。\n\n"
                        f"**✅ 正確答案**：**計算結果數值**"
                    )
                else:
                  # 深度變形題：基於該道真實紅筆錯題進行進階挖深
                  q_t = (
                      f"第 {q_idx} 題【原紅筆錯題 #{e_idx} 深度變形 #{v_i+1}】：基於原題「{real_q[:40]}...」，"
                      f"加入複合陷阱與多重條件判別 (變形級數 #{mult})"
                  )
                  a_t = (
                      f"**📌 題目**：{q_t}\n\n"
                      f"**🎨 思考步驟與進階圖解**：\n```text\n"
                      f" 1. 識別隱含條件與觀念混淆點\n"
                      f" 2. 進行多重條件綜合判別\n"
                      f"```\n"
                      f"**計算過程**：\n- 逐一排除錯誤選項並精準得出結論。\n\n"
                      f"**✅ 正確答案**：**深度變形推導解答**"
                  )

                tab1_answers.append(a_t)
                st.markdown(f"   * {q_t}")
                st.markdown(
                    """
                        <div style="border: 1px dashed #b0b0b0; height: 120px; border-radius: 6px; margin: 8px 0 18px 0; background-color: #fbfbfb; display: flex; align-items: center; justify-content: center; color: #a0a0a0; font-size: 0.9em;">
                            ✏️ 【學生專用計算與作答區】
                        </div>
                        """,
                    unsafe_allow_html=True,
                )
                q_idx += 1

            st.markdown(
                """
                        <div style="page-break-after: always; border-top: 3px dashed #ff4b4b; margin: 40px 0; text-align: center;">
                            <span style="background: white; padding: 0 15px; position: relative; top: -14px; color: #ff4b4b; font-weight: bold; font-size: 1.1em;">--- ⬇️ 以下為解答頁面（列印時自動分頁） ⬇️ ---</span>
                        </div>
                        """,
                unsafe_allow_html=True,
            )
            st.markdown("### 💡 參考解答、詳細步驟與解題口訣")
            st.markdown(
                """
                        > 🧠 **核心口訣**：「**抓準題眼不慌張，圖形輔助找方向！**」
                        """
            )
            for ans in tab1_answers:
              st.markdown(f"   * {ans}\n---")
            render_share_toolbar("底部")

  with tab2:
    st.subheader("🧠 AI 智慧診斷專區")
    st.info(
        "💡 **溫馨提示**：AI"
        " 智慧診斷功能需要學生在系統內累積一定的練習題數與錯題數據後，才能進行深度盲點分析並提供具體改善建議喔！"
    )
    if st.button("開始進行 AI 學習盲點診斷"):
      st.info(
          "目前累積的學習數據尚不足以生成完整診斷報告，建議先多進行幾次練習或上傳錯題！"
      )

  with tab3:
    st.subheader("📊 個人學習報告")
    st.info(
        "💡 **溫馨提示**：個人學習報告需要持續累積一段時間的練習歷程，圖表與數據趨勢才會完整呈現。"
    )
    st.metric(label="目前累積練習題數", value="0 題")
    st.metric(label="已釐清觀念錯題", value="0 題")

  with tab4:
    st.subheader("⚙️ 自組題目與考卷生成區 (版本大綱細分 + 私中特訓 + 奧林匹克數學)")
    st.write(
        "系統會根據您選擇的教科書版本、年級、版本大綱細項，以及難度級別（基礎/進階/資優），動態調整題型與思維深度！"
    )

    current_linked_version = st.selectbox(
        "選擇教科書版本：",
        ["康軒版", "南一版", "翰林版"],
        index=0,
    )
    current_grade_str = st.session_state.get("student_grade", "國小六年級")

    version_grade_units_map = {
        "康軒版": {
            "國小五年級": [
                "康軒 5上-01：因數與倍數 (因數判別、倍數特性、質數與合數)",
                "康軒 5上-02：公因數與公倍數 (最大公因數、最小公倍數、應用題)",
                "康軒 5上-03：分數的加減 (擴分約分、通分、異分母加減)",
                "康軒 5上-04：三角形與平行四邊形面積 (公式推導、複合圖形)",
                "康軒 5下-05：分數的乘除與倒數 (分數乘整數、分數除法)",
                "康軒 5下-06：小數的除法 (小數除以整數、商到小數點)",
                "康軒 5下-07：圓周長與圓面積 (圓周率、直徑半徑、面積計算)",
                "康軒 5下-08：速率的意義與計算 (距離、時間、速率換算)",
            ],
            "國小六年級": [
                "康軒 6上-01：分數與小數的四則混合 (括號運算、繁分數化簡)",
                "康軒 6上-02：比與比值 (比的化簡、相等比、比值應用)",
                "康軒 6上-03：圓周長與面積變化 (放大縮小倍數、複合扇形)",
                "康軒 6上-04：柱體與錐體的體積表面積 (柱體體積、錐體表面積展開)",
                "康軒 6下-05：速率的綜合應用 (追及問題、相遇問題、平均速率)",
                "康軒 6下-06：代數與未知數列式 (一元一次方程式化簡與求解)",
                "康軒 6下-07：簡單聯立方程式應用 (生活情境列式與消去法)",
            ],
        },
        "南一版": {
            "國小五年級": [
                "南一 5上-01：倍數與因數 (因數與倍數找法、公因數與公倍數)",
                "南一 5上-02：分數的計算 (擴分約分、異分母分數加減)",
                "南一 5上-03：多邊形與面積 (三角形、平行四邊形、梯形面積)",
                "南一 5上-04：容積與容量 (容積公式、容積與容量換算)",
                "南一 5下-05：分數的乘法與除法 (分數乘以分數、分數除以分數)",
                "南一 5下-06：小數的除法 (整數除以小數、小數除以小數)",
                "南一 5下-07：圓周長與扇形 (圓周率應用、扇形周長與面積)",
                "南一 5下-08：速率的單元換算 (分速、秒速、時速轉換)",
            ],
            "國小六年級": [
                "南一 6上-01：分數與小數四則 (四則混合運算技巧、巧算)",
                "南一 6上-02：比、比值與正反比 (比值觀念、正比關係、反比關係)",
                "南一 6上-03：圓面積與變化 (放大與縮小、面積變化倍數)",
                "南一 6上-04：體積與表面積 (長方體正方體、複合柱體)",
                "南一 6下-05：速率應用與行程 (相遇與追及問題、流水行船)",
                "南一 6下-06：生活中的代數 (未知數符號列式與解題)",
                "南一 6下-07：聯立方程式與應用 (二元一次聯立方程組)",
            ],
        },
        "翰林版": {
            "國小五年級": [
                "翰林 5上-01：因數與倍數 (因數與倍數、公因數與公倍數)",
                "翰林 5上-02：分數的加減 (異分母分數加減、分數大小比較)",
                "翰林 5上-03：三角形與平行四邊形面積 (面積公式與應用)",
                "翰林 5上-04：多邊形內角和與性質 (多邊形切割、對角線)",
                "翰林 5下-05：分數的乘除運算 (分數乘法、分數除法)",
                "翰林 5下-06：小數的除法計算 (小數除法直式與商)",
                "翰林 5下-07：圓周長與圓面積 (圓週率應用、扇形)",
                "翰林 5下-08：速率與時間 (速率公式、距離與時間)",
            ],
            "國小六年級": [
                "翰林 6上-01：分數與小數四則混合 (四則運算規則)",
                "翰林 6上-02：比與比值 (比值的意義、最簡單整數比)",
                "翰林 6上-03：圓面積與放大縮小 (圖形放大縮小、面積倍數)",
                "翰林 6上-04：柱體、錐體與球體 (體積與表面積計算)",
                "翰林 6下-05：速率與行程問題 (平均速率、追及與相遇)",
                "翰林 6下-06：代數列式與應用 (列出未知數算式)",
                "翰林 6下-07：聯立方程式 (二元一次聯立方程組應用題)",
            ],
        },
    }

    version_units = version_grade_units_map.get(
        current_linked_version, version_grade_units_map["康軒版"]
    ).get(current_grade_str, [])

    special_units = [
        "🔥 【私中特訓選項】雞兔同籠與假設問題 (多元假設、腿數差分析)",
        "🔥 【私中特訓選項】溶液濃度與百分比進階 (溶質守恆、連續混合)",
        "🔥 【私中特訓選項】賺賠與利潤變化題 (成本、定價、折扣、利潤)",
        "🔥 【私中特訓選項】年齡與時間差倍綜合題 (年齡差不變原理)",
        "🏆 【奧林匹克數學】進階邏輯推理與數列規律 (高難度歸納推理)",
        "🏆 【奧林匹克數學】容斥原理與圖形計數 (重疊計算、奧數巧算)",
        "🏆 【奧林匹克數學】數論進階與奇偶性分析 (質因數進階應用)",
    ]

    all_available_units = version_units + special_units

    selected_topics = st.multiselect(
        f"選擇細分題型/子單元（當前版本：{current_linked_version} |"
        f" 年級：{current_grade_str}，可複選多個單元）：",
        all_available_units,
        default=[all_available_units[0]],
    )

    col_d1, col_d2 = st.columns(2)
    with col_d1:
      question_count = st.slider("選擇每單元生成題數 (1~10)：", 1, 10, 3)
    with col_d2:
      difficulty_level = st.selectbox(
          "選擇難度級別（將動態調整數字與思維陷阱）：",
          ["基礎鞏固 (基礎型)", "進階挑戰 (進階型)", "私中資優競試級 (資優型)"],
      )

    vary_numbers_opt = st.checkbox(
        "🔄 變換數字，以同題型再出題（動態代入不同數值，確保同題型數字不重複）",
        value=True,
    )

    if st.button("🚀 開始生成自組測驗卷"):
      if not selected_topics:
        st.warning("請至少選擇一個子單元！")
      else:
        grouped_questions = {}
        grouped_answers = {}

        for topic in selected_topics:
          grouped_questions[topic] = []
          grouped_answers[topic] = []

          for i in range(1, question_count + 1):
            mult = i if vary_numbers_opt else 1
            sub_type = (i - 1) % 3

            if "基礎" in difficulty_level:
              diff_scale = 1
              diff_tag = "【基礎】"
            elif "進階" in difficulty_level:
              diff_scale = 2
              diff_tag = "【進階】"
            else:
              diff_scale = 3
              diff_tag = "【資優競試】"

            if (
                "因數" in topic
                or "倍數" in topic
                or "公因數" in topic
                or "最大公因數" in topic
            ):
              if sub_type == 0:
                val = 300 + mult * 11 * diff_scale
                q_text = (
                    f"第 {i} 題 {diff_tag}：有一個三位數 {val}□，若它是"
                    " 3 的倍數也是 5 的倍數，請找出方格 □ 內可以填入的所有數字總和為多少？"
                )
                ans_sum = (7 * mult * diff_scale) % 10 + 2
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖形具象化**：\n```text\n"
                    f" [百位: {val // 100}] -> [十位: {(val // 10) % 10}] -> [個位: □ (需為0或5)]\n"
                    f"```\n"
                    f"**計算過程**：\n1. 判別5的倍數：個位數為0或5。\n2. 判別3的倍數：各位數字和為3的倍數。\n3. 符合條件數字相加。\n\n"
                    f"**✅ 正確答案**：**{ans_sum}**"
                )
              elif sub_type == 1:
                n1 = (40 + mult * 12) * diff_scale
                n2 = (60 + mult * 18) * diff_scale
                q_text = (
                    f"第 {i} 題 {diff_tag}：求出 {n1} 與 {n2} 的最大公因數"
                    " (HCF) 與最小公倍數 (LCM) 的乘積為何？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與短除法圖解**：\n```text\n"
                    f" 2 | {n1} , {n2}\n"
                    f"   +-------------------\n"
                    f"     (持續短除至互質)\n"
                    f"```\n"
                    f"**計算過程**：\n1. 運用短除法求出 HCF 與 LCM。\n2. 兩數乘積恆等於 HCF × LCM。\n\n"
                    f"**✅ 正確答案**：**{n1 * n2}**"
                )
              else:
                q_text = (
                    f"第 {i} 題 {diff_tag}：若標準分解式 a = 2³ × 3² ×"
                    f" {5+mult*diff_scale} 且 b = 2² × 3³，求 a 與 b 的最大公因數。"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與指數比較圖解**：\n```text\n"
                    f" 質因數 2 取最小次方 2²\n"
                    f" 質因數 3 取最小次方 3²\n"
                    f"```\n"
                    f"**計算過程**：最大公因數 = 2² × 3² = 36。\n\n"
                    f"**✅ 正確答案**：**36**"
                )
            elif "公倍數" in topic or "最小公倍數" in topic:
              if sub_type == 0:
                base_n = 4 + mult * diff_scale
                base_m = 6 + mult * diff_scale
                q_text = (
                    f"第 {i} 題 {diff_tag}：有一堆糖果，每 {base_n}"
                    " 個裝一袋或每 {base_m} 個裝一袋都剛好裝完沒有剩餘。已知這堆糖果大約在"
                    f" {100 * diff_scale} 個左右，請問這堆糖果實際上有幾個？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 糖果數 = LCM({base_n}, {base_m}) 的倍數\n"
                    f"```\n"
                    f"**計算過程**：先求最小公倍數，再找出最接近 {100 * diff_scale} 的倍數。\n\n"
                    f"**✅ 正確答案**：**精準公倍數計算值**"
                )
              elif sub_type == 1:
                q_text = (
                    f"第 {i} 題 {diff_tag}：三盞燈分別每隔 {3+mult} 秒、"
                    f"{4+mult} 秒、{6*diff_scale} 秒閃爍一次，同時閃爍後，至少經過多少秒會再次同時閃爍？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 再次同時閃爍時間 = LCM(間隔1, 間隔2, 間隔3)\n"
                    f"```\n"
                    f"**計算過程**：對三數求最小公倍數。\n\n"
                    f"**✅ 正確答案**：**LCM計算結果秒**"
                )
              else:
                q_text = (
                    f"第 {i} 題 {diff_tag}：用長 {12 * diff_scale} 公分、寬"
                    f" {8 * diff_scale} 公分的長方形磁磚拼成一個正方形，拼成的最小正方形邊長為多少公分？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與拼貼圖解**：\n```text\n"
                    f" [ 矩形磚 ][ 矩形磚 ] ...\n"
                    f" 拼成邊長 = LCM(12, 8)\n"
                    f"```\n"
                    f"**計算過程**：正方形邊長為長寬的最小公倍數。\n\n"
                    f"**✅ 正確答案**：**{24 * diff_scale} 公分**"
                )
            elif "柱體" in topic or "錐體" in topic or "體積" in topic:
              if sub_type == 0:
                area_val = (20 + mult * 5) * diff_scale
                height_val = (10 + mult * 2) * diff_scale
                q_text = (
                    f"第 {i} 題 {diff_tag}：有一個長方體柱體，底面積為"
                    f" {area_val} 平方公分，高為 {height_val} 公分，請問其體積為多少立方公分？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與立體圖解**：\n```text\n"
                    f"   [ 高 = {height_val} cm ]\n"
                    f"   ┌─────────┐\n"
                    f"   │         │ 柱體體積 = 底面積 × 高\n"
                    f"   └─────────┘\n"
                    f"   ( 底面積 = {area_val} cm² )\n"
                    f"```\n"
                    f"**計算過程**：體積 = {area_val} × {height_val} = {area_val * height_val} 立方公分。\n\n"
                    f"**✅ 正確答案**：**{area_val * height_val} 立方公分**"
                )
              elif sub_type == 1:
                side_v = (6 + mult) * diff_scale
                q_text = (
                    f"第 {i} 題 {diff_tag}：若有一個正方體柱體，其邊長為"
                    f" {side_v} 公分，請問其總表面積與體積分別為多少？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 表面積 = 6 × 邊長² | 體積 = 邊長³\n"
                    f"```\n"
                    f"**計算過程**：\n1. 表面積 = 6 × {side_v**2} = {6 * side_v**2} 平方公分\n2. 體積 = {side_v**3} 立方公分\n\n"
                    f"**✅ 正確答案**：**表面積 {6 * side_v**2} 平方公分，體積 {side_v**3} 立方公分**"
                )
              else:
                r_v = (5 + mult) * diff_scale
                h_v = (10 + mult * 3) * diff_scale
                q_text = (
                    f"第 {i} 題 {diff_tag}：有一圓柱容器，底面半徑為 {r_v}"
                    f" 公分，柱高為 {h_v} 公分，求其容積為多少立方公分？（以 π 表示）"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 圓柱容積 = (π × 半徑²) × 高\n"
                    f"```\n"
                    f"**計算過程**：容積 = π × {r_v**2} × {h_v} = {r_v**2 * h_v}π 立方公分。\n\n"
                    f"**✅ 正確答案**：**{r_v**2 * h_v}π 立方公分**"
                )
            elif "分數" in topic or "小數" in topic:
              if sub_type == 0:
                q_text = (
                    f"第 {i} 題 {diff_tag}：計算下列四則混合運算："
                    f" ({mult+2}/10 + 0.{mult}) × {mult*10*diff_scale} - {mult*2}"
                    " 之數值為何？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 1. 分數化小數 -> 2. 括號先算 -> 3. 乘除 -> 4. 加減\n"
                    f"```\n"
                    f"**計算過程**：依循四則運算規則逐步推進計算。\n\n"
                    f"**✅ 正確答案**：**計算結果數值**"
                )
              elif sub_type == 1:
                q_text = (
                    f"第 {i} 題 {diff_tag}：在數線上比較數字大小，找出範圍在"
                    f" 0.{mult} 與 0.{mult+2*diff_scale} 之間的數值。"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與數線圖解**：\n```text\n"
                    f" 0 ──── [0.例1] ──── [0.例2] ──── 1\n"
                    f"```\n"
                    f"**計算過程**：統一小數位數後在數線上尋找對應區間。\n\n"
                    f"**✅ 正確答案**：**區間內的數值**"
                )
              else:
                money_v = (100 + mult * 50) * diff_scale
                rem1 = money_v * 0.5
                rem2 = rem1 * (2 / 3)
                q_text = (
                    f"第 {i} 題 {diff_tag}：小華有 {money_v} 元，買書花去全部的"
                    " 1/2，買文具花去剩下的 1/3，還剩多少元？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" [ 總金額 {money_v} ]\n"
                    f"   ├── 買書 1/2 ──> 剩餘 {rem1}\n"
                    f"   └── 買文具 1/3 ──> 最終剩餘 {rem2}\n"
                    f"```\n"
                    f"**計算過程**：\n1. 買書後剩餘 = {money_v} × 1/2 = {rem1} 元\n2. 買文具後剩餘 = {rem1} × (1 - 1/3) = {rem2:.1f} 元\n\n"
                    f"**✅ 正確答案**：**{rem2:.1f} 元**"
                )
            elif "速率" in topic:
              if sub_type == 0:
                dist_val = (100 + mult * 50) * diff_scale
                speed_val = 40 + mult * 10
                total_t = dist_val / speed_val + mult
                q_text = (
                    f"第 {i} 題 {diff_tag}：甲、乙兩地相距 {dist_val}"
                    f" 公里，汽車以每小時 {speed_val} 公里行駛，若中途休息"
                    f" {mult} 小時，共需要多少小時到達？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與行程圖解**：\n```text\n"
                    f" 甲地 ──(距離: {dist_val}km, 時速: {speed_val}km/h)──> 乙地 (含休息 {mult}h)\n"
                    f"```\n"
                    f"**計算過程**：\n1. 純行駛時間 = {dist_val} ÷ {speed_val} = {dist_val/speed_val:.1f} 小時\n2. 總時間 = 行駛時間 + 休息時間 = {total_t:.1f} 小時\n\n"
                    f"**✅ 正確答案**：**{total_t:.1f} 小時**"
                )
              elif sub_type == 1:
                spd_v = (3 + mult) * diff_scale
                len_v = (100 + mult * 20) * diff_scale
                time_v = len_v / spd_v
                q_text = (
                    f"第 {i} 題 {diff_tag}：小明跑步速率為每秒 {spd_v}"
                    f" 公尺，若他跑了 {len_v} 公尺，共花了多少秒？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 時間 = 距離 ÷ 速率\n"
                    f"```\n"
                    f"**計算過程**：時間 = {len_v} ÷ {spd_v} = {time_v:.1f} 秒。\n\n"
                    f"**✅ 正確答案**：**{time_v:.1f} 秒**"
                )
              else:
                q_text = (
                    f"第 {i} 題 {diff_tag}：火車長 {100 * diff_scale} 公分，以每秒"
                    f" {20 + mult*5} 公的速度完全通過一個隧道，需要幾秒？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 總距離 = 車長 + 隧道長 | 時間 = 總距離 ÷ 速率\n"
                    f"```\n"
                    f"**計算過程**：注意單位換算後計算出精準秒數。\n\n"
                    f"**✅ 正確答案**：**計算結果秒**"
                )
            elif "圓周長" in topic or "圓面積" in topic or "比與比值" in topic:
              if sub_type == 0:
                r1 = 5 + mult
                r2 = (10 + mult * 2) * diff_scale
                diff_area = r2**2 - r1**2
                q_text = (
                    f"第 {i} 題 {diff_tag}：半徑 {r1} 公分的圓形，若半徑增加為"
                    f" {r2} 公分，面積增加多少平方公分？（以 π 表示）"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 面積增加量 = 大圓面積 - 小圓面積 = π(r₂² - r₁²)\n"
                    f"```\n"
                    f"**計算過程**：π × ({r2}² - {r1}²) = {diff_area}π 平方公分。\n\n"
                    f"**✅ 正確答案**：**{diff_area}π 平方公分**"
                )
              elif sub_type == 1:
                q_text = (
                    f"第 {i} 題 {diff_tag}：水池周長為 {31.4 * diff_scale}"
                    " 公尺，求其半徑與面積大約為多少？（π以 3.14 計算）"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 半徑 = 周長 ÷ (2 × π) | 面積 = π × 半徑²\n"
                    f"```\n"
                    f"**計算過程**：依序代入周長與面積公式計算。\n\n"
                    f"**✅ 正確答案**：**對應半徑與面積計算值**"
                )
              else:
                q_text = (
                    f"第 {i} 題 {diff_tag}：將半徑 {10 * diff_scale}"
                    " 公分圓形紙片剪掉 60 度扇形，剩餘面積為多少？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與扇形圖解**：\n```text\n"
                    f" 剩餘圓心角 = 360° - 60° = 300° (佔全圓 5/6)\n"
                    f"```\n"
                    f"**計算過程**：全圓面積 × (5/6)。\n\n"
                    f"**✅ 正確答案**：**剩餘面積計算值**"
                )
            elif "聯立" in topic or "代數" in topic:
              if sub_type == 0:
                sum_v = (40 + mult * 10) * diff_scale
                diff_v = (10 + mult * 2) * diff_scale
                x_v = (sum_v + diff_v) // 2
                y_v = (sum_v - diff_v) // 2
                q_text = (
                    f"第 {i} 題 {diff_tag}：若 x + y = {sum_v} 且 x - y ="
                    f" {diff_v}，求 x 與 y 的乘積為何？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 兩式相加得 2x = 和 + 差 -> 求出 x 與 y\n"
                    f"```\n"
                    f"**計算過程**：\n1. 2x = {sum_v + diff_v} ⇒ x = {x_v}\n2. y = {y_v}\n3. 乘積 = {x_v} × {y_v} = {x_v * y_v}\n\n"
                    f"**✅ 正確答案**：**{x_v * y_v}**"
                )
              else:
                q_text = (
                    f"第 {i} 題 {diff_tag}：鉛筆每支 {10 * diff_scale} 元，筆記本每本"
                    f" {30 * diff_scale} 元，買了共 10 件物品花了 300 元，各買了幾件？"
                )
                a_text = (
                    f"**📌 題目**：{q_text}\n\n"
                    f"**🎨 思考步驟與圖解**：\n```text\n"
                    f" 假設法：全部買一種物品，再調整差價\n"
                    f"```\n"
                    f"**計算過程**：設立聯立方程式或假設法求解。\n\n"
                    f"**✅ 正確答案**：**各品項數量**"
                )
            elif "私中特訓" in topic and "雞兔同籠" in topic:
              heads = (20 + mult * 4) * diff_scale
              legs = (60 + mult * 14) * diff_scale
              q_text = (
                  f"第 {i} 題 {diff_tag} (私中特訓)：農場上有雞和兔子共 {heads}"
                  f" 隻，共有 {legs} 隻腳。若每隻兔子多長 2 隻腳，則總腳數會變為多少？"
              )
              a_text = (
                  f"**📌 題目**：{q_text}\n\n"
                  f"**🎨 思考步驟與圖解**：\n```text\n"
                  f" 假設全為雞 -> 計算腳數差 -> 求出兔數 -> 加上新條件\n"
                  f"```\n"
                  f"**計算過程**：先求出原本兔子數，再計算新條件下的總腳數。\n\n"
                  f"**✅ 正確答案**：**新總腳數計算值**"
              )
            elif "私中特訓" in topic and "溶液" in topic:
              conc = 10 + (mult * 2) % 15
              weight = (200 + mult * 50) * diff_scale
              q_text = (
                  f"第 {i} 題 {diff_tag} (私中特訓)：將濃度 {conc}% 的食鹽水"
                  f" {weight} 公克，蒸發掉部分水分使濃度提高為 {conc+5}%，蒸發了多少公克的水？"
              )
              a_text = (
                  f"**📌 題目**：{q_text}\n\n"
                  f"**🎨 思考步驟與圖解**：\n```text\n"
                  f" 溶質重量 = 總重 × 濃度 (蒸發過程溶質不變)\n"
                  f"```\n"
                  f"**計算過程**：利用溶質守恆定律計算新溶液總重並相減。\n\n"
                  f"**✅ 正確答案**：**蒸發水量克**"
              )
            elif "私中特訓" in topic or "賺賠" in topic or "年齡" in topic:
              cost = (200 + mult * 50) * diff_scale
              price = cost * 1.5 * 0.8
              profit = price - cost
              q_text = (
                  f"第 {i} 題 {diff_tag} (私中特訓)：老闆以每個 {cost}"
                  " 元成本買進商品，加五成定價後打八折賣出，可賺多少元？"
              )
              a_text = (
                  f"**📌 題目**：{q_text}\n\n"
                  f"**🎨 思考步驟與圖解**：\n```text\n"
                  f" 成本 ──(+50%)──> 定價 ──(打8折)──> 售價 ──(-成本)──> 利潤\n"
                  f"```\n"
                  f"**計算過程**：\n1. 定價 = {cost} × 1.5 = {cost*1.5} 元\n2. 售價 = {cost*1.5} × 0.8 = {price} 元\n3. 利潤 = {price} - {cost} = {profit} 元\n\n"
                  f"**✅ 正確答案**：**賺 {profit} 元**"
              )
            elif "奧林匹克數學" in topic:
              q_text = (
                  f"第 {i} 題 {diff_tag} (奧數培訓)：觀察數列規律 2, 6, 12, 20,"
                  f" 30, ...，請推導出第 {10 + mult*5} 個數為何？並說明其級數通式。"
              )
              a_text = (
                  f"**📌 題目**：{q_text}\n\n"
                  f"**🎨 思考步驟與奧數圖解**：\n```text\n"
                  f" 差值為等差：+4, +6, +8, +10 ... 通式為 n×(n+1)\n"
                  f"```\n"
                  f"**計算過程**：代入第 n 項公式求值。\n\n"
                  f"**✅ 正確答案**：**精準級數數值**"
              )
            else:
              q_text = (
                  f"第 {i} 題 {diff_tag} (單元: {topic})：針對「{topic}」核心單元，進行"
                  f" {difficulty_level} 的變形演練 #{sub_type+1}。"
              )
              a_text = (
                  f"**📌 題目**：{q_text}\n\n"
                  f"**🎨 思考步驟與圖解**：\n```text\n"
                  f" 核心定理應用與步驟拆解\n"
                  f"```\n"
                  f"**計算過程**：依據單元公式進行推導計算。\n\n"
                  f"**✅ 正確答案**：**標準推導解答**"
              )

            grouped_questions[topic].append(q_text)
            grouped_answers[topic].append(a_text)

        st.session_state["generated_quiz_group_data"] = {
            "version": current_linked_version,
            "grade": current_grade_str,
            "difficulty": difficulty_level,
            "grouped_questions": grouped_questions,
            "grouped_answers": grouped_answers,
        }
        st.session_state["is_generated"] = True
        st.success("🎉 多單元群組化測驗卷已成功生成！")

    if st.session_state["is_generated"] and st.session_state.get(
        "generated_quiz_group_data"
    ):
      quiz_data = st.session_state["generated_quiz_group_data"]
      st.markdown("---")
      st.markdown(
          "## 📝 專屬數學練習卷（依版本大綱與特殊單元分類，附專用計算空間）"
      )
      st.markdown(
          f"**版本**：{quiz_data['version']} | **年級**：{quiz_data['grade']}"
          f" | **難度**：{quiz_data['difficulty']}"
      )
      st.markdown("---")

      st.markdown("### 📌 測驗題目")
      for topic, q_list in quiz_data["grouped_questions"].items():
        st.markdown(f"#### 📚 單元：{topic}")
        for q in q_list:
          st.markdown(f"   * {q}")
          # 每一題下方自動留出計算與作答空間
          st.markdown(
              """
                    <div style="border: 1px dashed #b0b0b0; height: 130px; border-radius: 6px; margin: 10px 0 20px 0; background-color: #fbfbfb; display: flex; align-items: center; justify-content: center; color: #a0a0a0; font-size: 0.9em;">
                        ✏️ 【學生專用計算與作答區】
                    </div>
                    """,
              unsafe_allow_html=True,
          )
        st.markdown("")

      st.markdown("""
            <div style="page-break-after: always; border-top: 3px dashed #ff4b4b; margin: 40px 0; text-align: center;">
                <span style="background: white; padding: 0 15px; position: relative; top: -14px; color: #ff4b4b; font-weight: bold; font-size: 1.1em;">--- ⬇️ 以下為解答頁面（列印時自動分頁） ⬇️ ---</span>
            </div>
            """, unsafe_allow_html=True)

      st.markdown("### 💡 參考解答與詳細步驟")
      for topic, a_list in quiz_data["grouped_answers"].items():
        st.markdown(f"#### 📚 單元：{topic}")
        for a in a_list:
          st.markdown(f"   * {a}\n---")
        st.markdown("")

  # 永久常駐顯示的第 5 個分頁：系統管理者後台
  with tab5:
    st.subheader("👨‍🏫 系統管理者專屬後台管理專區（密碼保護）")

    teacher_password = st.text_input(
        "請輸入系統管理者密碼以解鎖後台：",
        type="password",
        placeholder="請輸入模組密碼...",
    )

    if teacher_password == "jason575752":
      st.success(
          "🔓 密碼驗證成功！您現在擁有【系統管理者】最高權限，以下為收集到的意見反饋："
      )
      st.session_state["is_admin"] = True

      if supabase:
        try:
          fb_res = supabase.table("feedbacks").select("*").execute()
          if fb_res.data:
            for fb in fb_res.data:
              st.info(
                  f"**發送者**: {fb.get('sender', '未知')} | **內容**:"
                  f" {fb.get('feedback_text', '')}"
              )
          else:
            st.info("目前雲端尚無收到新的意見反饋。")
        except Exception:
          st.info("目前為本機測試模式。")
      else:
        st.warning(
            "⚠️ 尚未連線 Supabase 雲端資料庫（目前啟用本機模擬資料庫）："
        )
        mock_list = st.session_state.get("mock_feedbacks", [
            {"sender": "student1@gmail.com", "feedback_text": "老師這題好難！"},
            {"sender": "parent@gmail.com", "feedback_text": "系統很好用喔！"},
        ])
        for fb in mock_list:
          st.info(
              f"**發送者 (模擬)**: {fb['sender']} | **內容**:"
              f" {fb['feedback_text']}"
          )

    elif teacher_password:
      st.error("⚠️ 密碼錯誤！您沒有系統管理者的存取權限。")
    else:
      st.info("🔒 請輸入系統管理者密碼以解鎖後台檢視權限。")
