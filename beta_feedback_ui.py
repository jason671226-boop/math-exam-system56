from __future__ import annotations

from typing import Any

try:
    from services.beta_feedback_service import (
        APP_VERSION,
        BetaFeedback,
        BetaFeedbackError,
        submit_feedback,
    )
except ModuleNotFoundError:
    from app.services.beta_feedback_service import (
        APP_VERSION,
        BetaFeedback,
        BetaFeedbackError,
        submit_feedback,
    )


CATEGORY_LABELS = {
    "一般建議": "GENERAL",
    "登入問題": "LOGIN",
    "題目輸出": "QUESTION_OUTPUT",
    "數學符號／公式": "MATH_OUTPUT",
    "學習診斷": "DIAGNOSTIC",
    "相機／圖片上傳": "CAMERA_UPLOAD",
    "學習紀錄保存": "PERSISTENCE",
    "教師回饋": "TEACHER_FEEDBACK",
    "家長報告": "PARENT_REPORT",
    "點數": "CREDITS",
    "其他": "OTHER",
}


def render_beta_feedback(st: Any, *, auth_client: Any | None, context: str) -> None:
    with st.expander("📝 Private Beta 意見回饋", expanded=False):
        st.caption("請勿輸入密碼、驗證碼、Token、API Key 或其他登入資訊。")
        if auth_client is None:
            st.info("登入 Private Beta 後即可安全提交回饋。")
            return
        with st.form("private_beta_feedback_v0871"):
            category_label = st.selectbox("回饋類型", tuple(CATEGORY_LABELS))
            rating = st.select_slider("使用體驗", options=(1, 2, 3, 4, 5), value=4)
            message = st.text_area("你的意見", max_chars=2000, height=100)
            submitted = st.form_submit_button("送出回饋", use_container_width=True)
        if not submitted:
            return
        try:
            submit_feedback(
                auth_client,
                BetaFeedback(
                    context=context or "app",
                    category=CATEGORY_LABELS[category_label],
                    rating=rating,
                    message=message,
                    app_version=APP_VERSION,
                ),
            )
        except BetaFeedbackError:
            st.error("回饋暫時無法送出，請稍後再試；系統不會顯示內部錯誤資訊。")
        else:
            st.success("謝謝你的回饋，已安全送出。")
