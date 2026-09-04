# G8 Pilot Freeze / Handoff

## 結論與完成度

**G8 PILOT FOUNDATION: SAFE TO FREEZE**

目前估計完成度：**60–65%（Pilot Foundation Complete）**。這代表 local 技術基礎可安全暫停，不代表完整題庫覆蓋或 Production 上線。

## 已完成 Stage

- Stage 5B-2A：local G8 mapping pilot preparation
- Stage 5B-2B：200 題 scope-aware pilot（checkpoint/resume、Scope Gate、resilient JSON parser）
- Stage 5B-2C：quality audit
- Stage 5B-2D：102 Skills / 660 Micro Skills coverage matrices
- Stage 5B-2E：8 Skills、24 題 local synthetic cross-unit technical validation

## Curriculum 與 200 題 Pilot 現況

- Profile：`CURRICULUM_V27:PREHIGH:G8:COMMON`
- Release：`CURRICULUM_V27_EA0E6735`
- Skills：102；Micro Skills：660
- 200 題完成：200/200；IN_SCOPE_G8：190；OUT_OF_SCOPE_G8：10；invalid：0
- 現有題庫映射集中於 2 個 Skills / 2 個 Micro Skills，僅代表本次 sample 分布。

## Coverage Matrix 摘要

- Skills covered：2；zero：100；coverage：1.96%
- Micro Skills covered：2；zero：658；coverage：0.3%
- Coverage artifacts 不含題目原文，完整矩陣保留於 `.local/stage5_g8_mapping_pilot/freeze/`。

## 跨單元驗證

- Questions：24；completed：24；invalid：0
- Scope accuracy：100.0%
- Exact skill accuracy：87.5%
- Exact micro accuracy：58.33%
- Technical PASS：TRUE
- Mapping Pilot PASS：FALSE
- 建議準確率門檻未全數達成；10 筆 mismatch 已完整記錄於 local report，不影響 technical pipeline correctness。

## 已知限制與尚未 Production 化項目

- Coverage 很低且高度集中；此成果不是完整題庫 coverage certification。
- Synthetic validation 只驗證代表性跨單元 routing，不替代真人審題或大規模 benchmark。
- 尚未將 G8 mappings、coverage 或 synthetic 題目寫入正式 item_bank。
- 尚未建立 Production migration、cutover 或正式資料回填。
- 未降低 RLS，未使用 staging 作為正式來源。

## Production 安全狀態

- Production project ref `igttuijrtwbtefhyeokp` 僅作禁止寫入環境標識。
- `production_reads = 0`
- `production_writes = 0`
- Secrets exposed：NO
- Local/raw/synthetic question data committed：NO

## 下次回到 G8 的第一步

先依 coverage matrix 的 `HIGH` / `ZERO_COVERAGE` 清單設計人工審核過的跨單元補題 blueprint；完成 local benchmark 後再討論任何 Production 設計。

## 建議補題優先順序

優先補完全零覆蓋且課程順序較前的核心 Skills，再擴大已有限覆蓋 Skill 的 Micro Skill breadth。首批候選：

- `G08-A-MULFORM-01` — 和平方公式
- `G08-A-MULFORM-02` — 差平方公式
- `G08-A-MULFORM-04` — 雙二項式展開
- `G08-A-MULFORM-APP-01` — 公式逆辨識與數值簡算
- `G08-A-POLY-TERM-01` — 項係數常數項
- `G08-A-POLY-DEG-01` — 次數與最高次項
- `G08-A-POLY-ORDER-01` — 升冪與降冪排列
- `G08-A-POLY-ADD-01` — 多項式加法
- `G08-A-POLY-SUB-01` — 多項式減法
- `G08-A-POLY-MUL-MONO-01` — 單項式乘多項式
- `G08-A-POLY-MUL-01` — 多項式乘多項式
- `G08-A-POLY-DIV-01` — 多項式除法
- `G08-A-POLY-ID-01` — 乘法公式驗證
- `G08-N-SQRT-MEAN-01` — 平方根與根號
- `G08-N-SQRT-PERFECT-01` — 完全平方數平方根

---

本文件不含題目原文、API key、service role key、secrets 或逐題 mapping data。
