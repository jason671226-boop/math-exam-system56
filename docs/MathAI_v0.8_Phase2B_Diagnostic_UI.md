# MathAI v0.8 Phase 2B — Diagnostic UI Pilot

## 目的

Phase 2B 將 Phase 2A 已完成的 5 題診斷資料與純 Python 診斷服務，接入既有 Streamlit「學習診斷」頁，首次驗證完整流程：

學生作答 → deterministic 判定 → Error Candidate → Knowledge / Thinking Evidence → 本機除錯顯示。

## 接線方式

- `app.py` 只做薄接線：載入 `render_diagnostic_pilot()`，並在既有「學習診斷」頁的開發者模式中呼叫。
- UI 主體集中於 `app/diagnostic_pilot_ui.py`。
- 正確性、比例正規化、multipart partial credit、錯因規則與 Mastery Evidence 仍由 Phase 2A `diagnostic_service.py` 負責。

## Session State

Phase 2B 全部暫存狀態使用 `diag_pilot_` 前綴。重新開始只刪除此命名空間，不使用 `st.session_state.clear()`，避免影響登入、學生資料與其他既有功能。

## Pilot 限制

本階段：

- 不寫入正式 Supabase。
- 不更新永久 Student Mastery。
- 不呼叫 Gemini / OpenAI / DeepSeek。
- 不建立正式家長報告。
- 不做第 6～18 題。
- 不做正式能力分型或錄取機率預測。

## 人工驗收重點

1. 全部答對 → 5/5，無不合理 Error Candidate。
2. Q4 輸入 `3:5` → 錯，顯示「新增數量後仍沿用原比例」。
3. Q4 輸入 `32:40` → 正確。
4. Q5 輸入面積 `87`、周長 `28` → 部分答對、credit 0.5、顯示「剪切後邊界判定錯誤」。
5. 空白或格式不完整 → 顯示輸入提示，不產生 Evidence，不 crash。
