MathAI v0.8.5 Private Beta｜一鍵安裝

【你只需要做】
1. 解壓整個 ZIP。
2. 雙擊：
   MathAI_一鍵安裝_v0.8.5_PrivateBeta.bat

【批次檔會自動完成】
- 備份 C:\MathAI\app\app.py
- 備份 C:\MathAI\app\diagnostic_pilot_ui.py
- 停止 localhost:8501 的舊 Streamlit
- 覆蓋新版兩個 Python 檔
- 執行 py_compile 語法檢查
- 驗證 APP_VERSION=v0.8.5
- 失敗時自動還原
- 成功後自動重新啟動 MathAI
- 自動開啟瀏覽器

【完成後一次驗收】
1. 左側版本顯示 v0.8.5
2. 立即試用顯示 30 點
3. 新會員提示顯示 200 點
4. 姓名欄有隱私提示
5. 錯題解析可直接拍照
6. 診斷作答可拍照／上傳圖片
7. 數學公式顯示正常

【Supabase】
SQL 不會由批次檔自動執行，避免直接修改正式資料庫。
Python 端驗收通過後，再執行：
Supabase_PrivateBeta_新會員200點_v0.8.5.sql
