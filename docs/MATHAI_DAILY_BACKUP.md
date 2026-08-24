# MathAI 每日收工備份

目的：讓 `C:\MathAI` 在換電腦、硬碟故障或本機環境損毀時可以快速復原。

## 雙層保護

1. GitHub：正式程式碼、branch、commit、版本歷史。
2. Google Drive：每日換機 ZIP，補回未追蹤文件、資料包與本機工作成果。

Google Drive 根目錄固定使用 `MathAI_Backups`。

## 每天收工流程

1. 確認今天的程式任務已停止。
2. 雙擊 `MathAI_每日收工備份.bat`。
3. 看到 `BACKUP PASS` 才算完成。
4. 若顯示 `Cloud detected: False`，代表只有本機備份，需先設定 Google Drive Desktop 的同步路徑。

## 第一次設定 / 容量盤點

雙擊 `MathAI_備份容量盤點.bat`。

此模式只讀，不會建立 ZIP，也不會修改 Git / Supabase / Production。

如自動偵測不到 Google Drive，可在 repo 根目錄建立 `.mathai_backup_target.txt`，內容只放本機 Google Drive 同步資料夾的完整路徑，例如：

```text
G:\My Drive\MathAI_Backups
```

`.mathai_backup_target.txt` 已加入 `.gitignore`，不會上傳 GitHub。

## 預設備份排除

為控制容量與避免洩漏，預設不收錄：

- `.git`
- `.venv` / `venv`
- cache / `__pycache__`
- `.local`
- `node_modules` / build / dist
- tmp / temp / backup(s) 目錄
- `secrets.toml`
- `.env*`
- credentials / token / service-account JSON
- log / pyc / tmp runtime artifacts

重要 ZIP、資料、Markdown、CSV、JSON 與一般工作文件不會因副檔名而被排除，因此 Curriculum rollback / handoff 類 ZIP 可被保存，只要不位於被排除的 backup 目錄。

## Secrets

API keys / secrets 故意不放進每日 ZIP。換電腦時應從 Streamlit Cloud、Supabase / provider console 或密碼管理工具重新設定。

## 保留策略

第一版保留最新 14 個每日 ZIP，超過後自動刪除最舊 ZIP 與 checksum。每次執行都會顯示：

- 本次候選備份容量
- ZIP 實際容量
- 目前保留份數
- 備份資料夾總使用量

等實測一週後，可再依 Google Drive 真實容量調整為 7 日 + 4 週 + 月備份。

## 換機原則

1. 新電腦安裝 Git / Python。
2. 從 GitHub clone `jason671226-boop/math-exam-system56`。
3. 下載最新 `MathAI_Backup_*.zip`。
4. 用 ZIP 補回 GitHub 沒有的本機資料。
5. 重建 `.venv` 並安裝 `requirements.txt`。
6. 重新填入 Secrets。
7. 執行 smoke tests，再開始開發。

不要把舊電腦的 `.venv` 直接搬到新電腦。
