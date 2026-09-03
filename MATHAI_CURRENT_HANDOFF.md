# MathAI Current Handoff

HANDOFF_RESOLUTION = NEW_CANONICAL_CREATED
HANDOFF_UPDATED_AT = 2026-09-01 (Asia/Taipei)

## 對話名稱

目前工作主線：MathAI 題庫第二階段

## 語言與操作方式

- 全程使用繁體中文。
- 使用者不是專業程式設計師。
- 操作說明必須簡單、直接、可操作。
- 優先提供大任務／批次任務。
- 能讓 Codex 一次完成就不要逐檔逐行要求人工修改。

## 快捷指令 P

如果使用者只輸入 `P`，意思是直接依目前既定計畫繼續下一步。

一般 Local audit、test、QA、研究、mock、安全 hotfix 可以自主繼續。

以下仍必須取得使用者明確授權：

- Git commit 若涉及正式 Release gate
- Git push
- merge main
- 正式 Deploy
- Production Supabase mutation
- DB migration
- RLS 修改
- 正式會員／學生／wallet／點數修改
- 付款／授權／不可逆操作

## Cursor / Codex 啟動規則

在 Cursor 裡啟動 Codex，預設工作目錄為 `C:\MathAI`。

標準流程：Cursor → Terminal → New Terminal，確認提示字元為 `PS C:\MathAI>`；如果不是，執行 `cd C:\MathAI`。

PowerShell ExecutionPolicy 會阻擋 `codex.ps1`，因此不要優先輸入 `codex`。標準啟動使用：

```powershell
PS C:\MathAI> codex.cmd
```

若無法直接執行，備援：

```powershell
& "$env:APPDATA\npm\codex.cmd"
```

不要為了啟動 Codex 修改 PowerShell ExecutionPolicy，除非使用者另外明確授權。

- `C:\MathAI` = Codex 啟動／working artifacts／QA／backup／research 工作區
- `C:\Users\ASUS\Documents\GitHub\math-exam-system56` = 正式 Application Repo／Git／正式主程式來源
- 正式 Streamlit entry = `C:\Users\ASUS\Documents\GitHub\math-exam-system56\app.py`
- 不得把 `C:\MathAI\app.py` 認成正式 Application 主程式。

## Supabase 固定規則

- Production project_id = `igttuijrtwbtefhyeokp`
- Staging project_id = `odttigkvfazpbnxhpiqe`
- 禁止把 Staging 當 Production。
- PRODUCTION_MUTATIONS = 0
- STAGING_MUTATIONS = 0
- DB_MIGRATIONS = 0
- RLS_CHANGES = 0
- QUESTION_BANK_IMPORTS = 0

## Phase 3J2-L3B — Safe Main RC Lock（2026-09-02）

- PHASE_3J2_L3B = PASS
- RELEASE_CANDIDATE_LOCK = PASS
- RC_WORKTREE = C:\MathAI\release_worktrees\MathAI_3J2_MAIN_RC
- RC_WORKTREE_BRANCH = main
- RC_BASE_HEAD = 1fb194d548f3d214d862e5ecfa8709da296c2ce6
- RELEASE_APPLICATION_FILES = app.py, services/derived_answer_adapter.py, services/manual_question_parser.py, tests/test_phase3j1_derived_adapter.py, tools/run_phase3h_regression.py
- RELEASE_SAFETY_FILES = .gitignore
- BLOCKER = NONE
- NEXT_PHASE = Phase 3J3 Formal Release Preparation
- Git commit / Push / Deploy 尚未授權，禁止執行。

## Phase 3J3 — Formal Release Preparation（2026-09-02）

- PHASE_3J3 = PREPARED
- RELEASE_CANDIDATE_LOCK = PASS
- RELEASE_FILES = app.py, services/derived_answer_adapter.py, services/manual_question_parser.py, tests/test_phase3j1_derived_adapter.py, tools/run_phase3h_regression.py
- RELEASE_FILE_COUNT = 5
- RELEASE_SAFETY_FILES = .gitignore
- FINAL_DIFF_CHECK = PASS
- RELEASE_SCOPE_CLEAN = YES
- SECRET_SCAN = PASS
- PRE_RELEASE_BACKUP = PASS
- PRE_RELEASE_BACKUP_PATH = C:\MathAI\backups\MathAI_PreRelease_3J3_20260902_105052
- PRE_RELEASE_BACKUP_ZIP = C:\MathAI\backups\MathAI_PreRelease_3J3_20260902_105052.zip
- PROPOSED_COMMIT_TITLE = feat: integrate confirmed-question derived-answer runtime
- DEPLOY_TARGET_VERIFIED = YES
- FORMAL_RELEASE_PREP = READY
- BLOCKER = NONE
- NEXT_ACTION = 先確認正式 Streamlit app 設定為正式 GitHub repo / main / app.py，再等待使用者正式授權 Commit、Push main、Streamlit deploy、Hosted smoke test。
- Git commit / Push / Deploy 仍未授權且未執行。

## Phase 3J3-A — Streamlit Production Target Verification（2026-09-02）

- PRODUCTION_STREAMLIT_URL = https://math-exam-system56-jasonlin.streamlit.app/
- HOSTED_APP_REACHABLE = YES
- PHASE_3J3 = PREPARED
- DEPLOY_REPO = jason671226-boop/math-exam-system56
- DEPLOY_BRANCH = main
- DEPLOY_ENTRY_FILE = app.py
- DEPLOY_TARGET_VERIFIED = YES
- FORMAL_RELEASE_PREP = READY
- BLOCKER = NONE
- DEPLOYMENT_TARGET_VERIFICATION = MANUAL_STREAMLIT_CONTROL_PANEL_PASS
- PRODUCTION_APP = math-exam-system56  main  app.py
- SHADOW_APP = math-exam-system56  test/curriculum-supabase-shadow-v0.9  app.py
- SHADOW_APP_RULE = test/curriculum-supabase-shadow-v0.9 是測試／shadow App，不得作為正式 Production deployment target。
- NEXT_ACTION = 等待使用者明確授權 Commit、Push main、Streamlit Production update、Hosted smoke test；目前不要執行。

## Phase 3J4 — Formal Release Execution（2026-09-02）

- PHASE_3J4 = FAIL
- FORMAL_RELEASE = FAIL
- RELEASE_COMMIT = PASS
- RELEASE_COMMIT_SHA = 1077d8dbb5932b8245f21d69b5c1718dfbbc9b3b
- RELEASE_COMMIT_TITLE = feat: integrate confirmed-question derived-answer runtime
- PUSH_TARGET = origin/main
- GIT_PUSH = FAIL
- REMOTE_MAIN_UPDATED = NO
- DEPLOYMENT = 0
- HOSTED_SMOKE_TEST = NOT_RUN
- PRODUCTION_STREAMLIT_STATUS = EXISTING_APP_UNCHANGED
- POST_RELEASE_BACKUP = NOT_CREATED
- BLOCKER = REMOTE_MAIN_DIVERGED_NON_FAST_FORWARD
- SAFETY = push 遭 non-fast-forward 拒絕後已停止；未 pull、merge、rebase、force-push 或 deploy。
- NEXT_ACTION = 另行執行 read-only remote-main divergence audit，確認安全整合策略並取得明確授權；禁止 force-push。
- PRODUCTION_MUTATIONS = 0
- STAGING_MUTATIONS = 0
- DB_MIGRATIONS = 0
- RLS_CHANGES = 0
- QUESTION_BANK_IMPORTS = 0

### Phase 3J4 remote-main divergence audit

- REMOTE_MAIN_SHA = 1509d945987adb4ec476c13dcd666f88301f5f9a
- COMMON_ANCESTOR = 44a7ea99fd4af776532bd56e36d7ea48d33621bd
- LOCAL_ONLY_COMMITS = 2
- REMOTE_ONLY_COMMITS = 78
- SAFE_FAST_FORWARD_PUSH = NO
- APP_PY_CHANGED_ON_BOTH_SIDES = YES
- DOT_GITIGNORE_CHANGED_ON_BOTH_SIDES = YES
- MERGE_REBASE_CHERRYPICK_FORCE_PUSH = 0
- BLOCKER = REMOTE_MAIN_INTEGRATION_AUTHORIZATION_REQUIRED
- NEXT_ACTION = 取得明確整合授權後，從最新 origin/main 建立新的隔離 integration RC，安全重放 release scope、處理衝突並重跑 release gates；禁止 force-push。

## Phase 3J4-B — Safe Remote Main Integration（2026-09-02）

- INTEGRATION_BASE = 1509d945987adb4ec476c13dcd666f88301f5f9a
- INTEGRATION_BRANCH = mathai-3j4-integration-20260902_115619
- INTEGRATION_COMMIT = cb738c843e423adabab8c3801dda3f6dd05f6c1e
- CHERRY_PICK = PASS
- AMBIGUOUS_CONFLICT = NO
- INTEGRATION_SCOPE_CLEAN = YES
- INTEGRATION_REGRESSION_TESTS = PASS
- INTEGRATION_LOCAL_BOOT = PASS
- INTEGRATION_HTTP = PASS
- ORIGIN_MAIN_IS_ANCESTOR = YES
- REMOTE_MAIN_CHANGED_DURING_INTEGRATION = NO
- REMOTE_MAIN_UPDATED = YES
- PUSHED_COMMIT_SHA = cb738c843e423adabab8c3801dda3f6dd05f6c1e
- FORCE_PUSH_USED = NO
- PRODUCTION_APP_REACHABLE = YES_AUTH_REDIRECT
- HOSTED_RELEASE_COMMIT_VERIFIED = NO
- HOSTED_SMOKE_TEST = FAIL_BLOCKED_BY_STREAMLIT_APP_AUTH
- PHASE_3J4 = FAIL
- FORMAL_RELEASE = FAIL
- BLOCKER = HOSTED_AUTHENTICATED_SMOKE_VERIFICATION_REQUIRED
- POST_RELEASE_BACKUP = NOT_CREATED
- NEXT_ACTION = 使用已登入 Streamlit Community Cloud 的合法瀏覽器，唯讀完成 Production hosted smoke 與 deployed commit verification；不得觸發 AI、扣點或資料寫入。
- PRODUCTION_MUTATIONS = 0
- STAGING_MUTATIONS = 0
- DB_MIGRATIONS = 0
- RLS_CHANGES = 0
- QUESTION_BANK_IMPORTS = 0
- 除非使用者另外明確授權，繼續維持 0。

## Phase 3J4-H2 — Login Email History + Referral Hotfix（2026-09-02）

- Hosted Production 已部署；Hosted Acceptance 尚未完成。
- FORMAL_RELEASE = DEPLOYED_BUT_HOSTED_ACCEPTANCE_PENDING
- Current regressions: Email 歷史登入 selector 遺失；推薦／介紹人贈點 UI 接線遺失。
- PHASE_3J4_H2 = LOCAL_PASS_PENDING_USER_UI_ACCEPTANCE
- LOGIN_REFERRAL_HOTFIX_LOCAL = READY
- EMAIL_KNOWN_GOOD_COMMIT = `e012d5a`
- REFERRAL_KNOWN_GOOD_COMMIT = `d0a8c18`
- EMAIL_HISTORY_STORAGE = device localStorage + legacy cookie bridge; localhost-only file fallback; maximum 10; newest-first and deduplicated
- REFERRAL_DB_CONTRACT = existing v070 RPC contract (`mathai_referrer_status_v070`, `mathai_create_referral_v070`, `mathai_source_claim_status`, `mathai_record_use_and_award_referral_v070`); no schema change
- REFERRER_REWARD_POINTS = 50
- REFERRED_USER_REWARD_POINTS = 50
- Local no-network regression = 37 passed
- Local Streamlit boot/HTTP = PASS / PASS
- Local rendered-widget validation = PASS; interactive in-app browser instance was unavailable
- PHASE_3H_GOLDEN_LOCK_UNCHANGED = PASS
- Production/staging/referral/wallet/ledger mutations = 0
- Hotfix files: `app_release_v0_8_8_3.py`, `tests/test_device_email_history.py`, `tests/test_login_referral_hotfix.py`
- BLOCKER = NONE
- NEXT_ACTION = 使用者 Local UI 驗收；其後等待明確 Hotfix Release 授權，再做 commit、normal non-force push main、Hosted re-validation。現在不要 commit、push 或 deploy。

## Phase 3J4-H3 — Hotfix Release Preparation（2026-09-02）

- EMAIL_HISTORY_HUMAN_UI = PASS
- REFERRAL_HUMAN_UI = PASS
- LOGIN_REFERRAL_HOTFIX_HUMAN_GATE = PASS
- PHASE_3J4_H3 = PREPARED
- HOTFIX_RC_WORKTREE = `C:\MathAI\release_worktrees\MathAI_3J4_HOTFIX_RC_20260902_151552`
- HOTFIX_RC_BASE = `origin/main` / `cb738c843e423adabab8c3801dda3f6dd05f6c1e`
- HOTFIX_RC_BRANCH = `mathai-3j4-login-referral-hotfix-20260902_151552`
- PRODUCTION_HOTFIX_FILES = `app_release_v0_8_8_3.py`
- RELEASE_TEST_SAFETY_FILES = `tests/test_login_referral_hotfix.py`
- EXCLUDED_LOCAL_TEST_FILES = H2A local new-member shortcut; H2B network-independent local OTP/session fixture and local referral mock guards/assertions
- EXCLUDED_FIXTURE_FILES = `recent_emails.json`; student.latest/student.second/student.third Human UI data
- LOCAL_TEST_SESSION_RELEASE_WORTHY = NO (temporary Human Validation workaround; Production Supabase Auth flow preserved)
- EMAIL_PRODUCTION_CONTRACT = PASS
- REFERRAL_PRODUCTION_CONTRACT = PASS
- FIXTURE_SCAN = PASS
- SECRET_SCAN = PASS
- HOTFIX_REGRESSION_TESTS = PASS (42 passed, 8 subtests passed)
- HOTFIX_RC_LOCAL_BOOT = PASS
- HOTFIX_RC_HTTP = PASS
- PHASE_3H_GOLDEN_LOCK_UNCHANGED = PASS
- PRE_HOTFIX_BACKUP = PASS
- PRE_HOTFIX_BACKUP_PATH = `C:\MathAI\backups\MathAI_PreHotfix_3J4H3_20260902_152028`
- PRE_HOTFIX_BACKUP_ZIP = `C:\MathAI\backups\MathAI_PreHotfix_3J4H3_20260902_152028.zip`
- PROPOSED_HOTFIX_COMMIT_TITLE = `fix: restore login email history and referral flow`
- HOTFIX_RELEASE_PREP = READY
- BLOCKER = NONE
- NEXT_ACTION = 等待使用者明確授權 Hotfix Release：逐檔 commit、normal non-force push origin/main、Streamlit Production update、Hosted re-validation。不要提前執行。
- GIT_COMMIT = 0; GIT_PUSH = 0; DEPLOYMENT = 0; FORCE_PUSH_USED = NO
- Production/staging/DB/RLS/referral/wallet/ledger mutations = 0

## Phase 3J4-H4 — Formal Login + Referral Hotfix Release（2026-09-02）

- PHASE_3J4_H4 = DEPLOYED
- HOTFIX_COMMIT_SHA = `7d4b00f4600daddbb4dc74fb04fb6a27eada6a41`
- HOTFIX_COMMIT_TITLE = `fix: restore login email history and referral flow`
- REMOTE_MAIN_UPDATED = YES (`cb738c8..7d4b00f`, normal non-force push)
- PRODUCTION_APP_REACHABLE = YES
- HOSTED_READONLY_SMOKE = PASS (Streamlit authentication redirect and login surface reachable; no login/mutation)
- EMAIL_HISTORY_LOCAL_HUMAN = PASS
- REFERRAL_LOCAL_HUMAN = PASS
- HOSTED_EMAIL_HISTORY_HUMAN = PASS
- HOSTED_REFERRAL_HUMAN = DEFERRED
- DEFER_REASON = Existing-member-only account pool; new-user hosted referral check deferred until a legitimate new-member flow occurs.
- HOTFIX_DEPLOYMENT = PASS
- HOTFIX_HOSTED_ACCEPTANCE = ACCEPTED_WITH_DEFERRED_NEW_USER_REFERRAL_CHECK
- PHASE_3H_GOLDEN_LOCK_UNCHANGED = PASS
- POST_HOTFIX_BACKUP = PASS
- POST_HOTFIX_BACKUP_PATH = `C:\MathAI\backups\MathAI_PostHotfix_3J4H4_20260902_153259`
- POST_HOTFIX_BACKUP_ZIP = `C:\MathAI\backups\MathAI_PostHotfix_3J4H4_20260902_153259.zip`
- FORCE_PUSH_USED = NO
- Production/staging/DB/RLS/referral/wallet/ledger mutations = 0
- NEXT_ACTION = 使用者在正式網站人工驗收：最後登入 Email 預設、歷史 dropdown、最後一項手動輸入、新會員親友／老師介紹、介紹人 Email、介紹人資格驗證。不要開始 Phase 3J5。

## Phase 3J5-A — Hosted Private Beta Existing-Member Validation（2026-09-02）

- LAST_COMPLETED_RELEASE = Phase 3J4-H4 Login + Referral Hotfix
- HOTFIX_ACCEPTANCE = ACCEPTED_WITH_DEFERRED_NEW_USER_REFERRAL_CHECK
- PHASE_3J5_A = PASS
- HOSTED_EMAIL_HISTORY_HUMAN = PASS
- REFERRAL_LOCAL_HUMAN = PASS
- REFERRAL_HOSTED_NEW_USER_CHECK = DEFERRED_UNTIL_LEGITIMATE_NEW_USER
- HOSTED_LOGIN_UI = PASS
- HOSTED_EMAIL_HISTORY = PASS
- HOSTED_EXISTING_MEMBER_FLOW = PASS
- HOSTED_SESSION = PASS
- EXISTING_MEMBER_REFERRAL_REPROMPT = NO
- UNEXPECTED_REFERRAL_MUTATION = 0
- HOSTED_NAVIGATION = PASS
- MISTAKE_ANALYSIS / MISTAKE_OUTPUT / VARIANT_PRACTICE / CUSTOM_EXAM = PASS (existing Hosted evidence; no rerun or point deduction)
- HOSTED_FATAL_EXCEPTION = NO
- HOSTED_STABILITY = PASS
- DESKTOP_LAYOUT = PASS
- MOBILE_LAYOUT = DEFERRED_HUMAN_DEVICE
- HISTORY_COMPATIBILITY = PASS
- ITERATIVE_PRACTICE_CONTRACT = PASS
- PHASE_3H_GOLDEN_LOCK_UNCHANGED = PASS
- GOLD_RUNTIME_LOOKUP_USED = NO
- PRODUCTION_RELEASE_PRESENT = YES (`7d4b00f` remains origin/main)
- HOSTED_PRIVATE_BETA_EXISTING_MEMBER = READY
- BLOCKER = NONE
- Production test mutations, DB migrations, RLS changes, question-bank imports, referral rewards, wallet and ledger mutations = 0
- FOLLOW_UPS = Mobile real-device UI; legitimate new-member Hosted referral check when naturally available; observe Private Beta latency/API cost without synthetic calls.
- NEXT_ACTION = Continue small-scale existing-member Private Beta only. Do not create a fake Production member and do not begin a large new feature.

## Phase 3J5-B — Private Beta Gap Triage（2026-09-02）

- LAST_COMPLETED_PHASE = 3J5-A
- PHASE_3J5_B = COMPLETED
- LIMITED_PRIVATE_BETA = READY
- P0 = NONE (count 0)
- P1 = Mobile real-device validation; legitimate-new-member Hosted referral lifecycle and natural 50/50 reward observation; normal-traffic latency/API-cost/retry/runtime monitoring; Private Beta feedback and recoverability UX evidence
- P2 = optional legacy Email-history migration if demand is demonstrated; evidence-driven UI/loading/error/formula/OCR/parser polish only after reproducible Beta findings
- DEFERRED = Mobile `DEFERRED_HUMAN_DEVICE`; Referral Hosted New User `DEFERRED_UNTIL_LEGITIMATE_NEW_USER`; natural referral reward `DEFERRED_UNTIL_LEGITIMATE_EVENT`; latency UNKNOWN pending normal Beta traffic
- NEXT_BATCH_1 = Limited-beta observation and feedback operations: Hosted errors/session stability, user feedback, and reproducible issue capture without synthetic AI load or Production test mutations
- NEXT_BATCH_2 = Mobile real-device validation for Login/Email selector/navigation/mistake/custom-exam, then evidence-backed responsive fixes only
- NEXT_BATCH_3 = Legitimate-new-member referral lifecycle observation when naturally available, including pending relation and first-valid-use 50/50 idempotency; do not manufacture an account or reward
- BLOCKER = NONE
- Safety = no DB/RLS/question-bank/referral/wallet/ledger mutation; no commit, push, or deployment

## Phase 3J6-A — Private Beta Operations Monitoring / Issue Collection（2026-09-02）

- LAST_COMPLETED_PHASE = 3J5-B
- PHASE_3J6_A = COMPLETED
- LIMITED_PRIVATE_BETA = READY
- PRIVATE_BETA_OPERATIONS_CENTER = C:\MathAI\private_beta_ops
- PRIVATE_BETA_OPERATIONS_READY = YES
- P0_COUNT = 0
- CURRENT_P1_ITEMS = Mobile real-device validation; legitimate new-member Hosted referral and natural first-valid-use 50/50 observation; latency/API cost/retry/runtime observation under natural Beta traffic; user feedback and reproducible issue collection
- CURRENT_P2_ITEMS = Legacy Email history migration on demand; evidence-driven UI/loading/error/formula/OCR/parser polish
- EXISTING_LOGGING_CAPABILITY = PARTIAL
- AI_PROVIDER_OBSERVABILITY = PARTIAL
- AI_RETRY_OBSERVABILITY = PARTIAL
- AI_LATENCY_OBSERVABILITY = MISSING
- AI_COST_OBSERVABILITY = MISSING
- LOGIN_OBSERVABILITY = PARTIAL
- SESSION_OBSERVABILITY = PARTIAL
- POINT_AUDITABILITY = PARTIAL
- REFERRAL_AUDITABILITY = PARTIAL
- DOUBLE_REWARD_PROTECTION_STATUS = PASS_BY_CONTRACT
- CURRENT_OPERATING_MODE = Observe real Private Beta usage; collect evidence; batch P1/P2 fixes; immediate response only for P0.
- NEXT_PHASE = Phase 3J6-B  First Private Beta Observation Cycle
- Safety = no synthetic AI traffic; no Production/Staging mutation; no DB/RLS/question-bank change; no commit, push, or deployment

## Phase 3J6-B — First Private Beta Observation Cycle（2026-09-02）

- LAST_COMPLETED_PHASE = 3J6-A
- PHASE_3J6_B = COMPLETED
- FIRST_PRIVATE_BETA_OBSERVATION = PB-CYCLE-001
- PRIVATE_BETA_STATUS = ACTIVE
- PRODUCTION_REACHABLE = YES
- PRODUCTION_RELEASE_PRESENT = YES
- CURRENT_REMOTE_MAIN_HEAD = 7d4b00f4600daddbb4dc74fb04fb6a27eada6a41
- NEW_ISSUES = NONE
- P0 = 0
- P1 = 0 confirmed registry issues; 4 operational/deferred watch items
- P2 = 0 confirmed registry issues; 2 non-blocking watch categories
- NEW_FEEDBACK_COUNT = 0
- LOGIN / SESSION = STABLE_NO_NEW_FAILURE_EVIDENCE
- EMAIL_HISTORY = PASS
- CORE_MATH_FLOW = PASS_NO_NEW_REGRESSION_EVIDENCE
- LATENCY_STATUS = UNKNOWN_NEEDS_NATURAL_TRAFFIC
- API_COST_STATUS = OBSERVABILITY_GAP
- MOBILE_STATUS = DEFERRED_HUMAN_DEVICE
- NEXT_FIX_BATCH_CANDIDATES = NONE_WITH_SUFFICIENT_NEW_EVIDENCE
- NEXT_ACTION = Continue Limited Private Beta and collect natural evidence.
- NEXT_PHASE = Continue Private Beta Observation Cycle
- BLOCKER = NONE
- Safety = no synthetic AI traffic; no Production/Staging mutation; no DB/RLS change; no commit, push, or deployment

## QB2-A — Existing Question Bank Authoritative Inventory（2026-09-02）

- WORKSTREAM = 題庫第二階段
- CURRENT_STAGE = QB2-A Existing Question Bank Authoritative Inventory
- TOTAL_SOURCE_FILES = 239
- TOTAL_RAW_QUESTIONS = 8888
- TOTAL_UNIQUE_QUESTIONS = 935
- EXACT_DUPLICATES = 7953
- NEAR_DUPLICATE_CANDIDATE_GROUPS = 8
- G5_RAW = 57
- G5_UNIQUE = 50
- G5_MAPPED = 36
- G5_VERIFIED = 7
- G5_APPROVED_EXISTING = 0
- G5_READY_FOR_IMPORT = 0
- G5_MISSING_KNOWLEDGE_POINTS = 50
- G5_LOW_CAPACITY_KNOWLEDGE_POINTS = 25
- HIGH_COPYRIGHT_RISK_COUNT = 791
- INVENTORY_ROOT = C:\MathAI\data\question_research\qb2_inventory
- NEXT_STAGE = QB2-B  G5 Targeted Gap Filling + Verification
- BLOCKER = NONE
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no AI call; no commit, push, or deployment
- Startup rule preserved = launch Codex from C:\MathAI using codex.cmd

## QB2-E2H G5 Canonical Mapping Human Resolution (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E2
- CURRENT_STAGE = QB2-E2H G5 Canonical Mapping Human Resolution
- PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
- PRODUCTION_IMPORT_AUTHORIZED = NO
- FAILED_RECORD_COUNT = 275
- FAILED_UNIQUE_RESEARCH_KP_COUNT = 20
- SAFE_RESOLVED_KP_COUNT = 1
- SAFE_RESOLVED_RECORDS = 14 newly resolved exception records
- DIRECT_MATCH_RECORDS = 599
- SEMANTIC_EQUIVALENT_KP_COUNT = 11
- SEMANTIC_EQUIVALENT_RECORDS = 154
- MANUAL_HOLD_RECORDS = 261
- E2H_FK_TOTAL = 1014
- E2H_FK_PASS = 753
- E2H_FK_FAIL = 261
- AMBIGUOUS_KP_COUNT = 19
- NO_MATCH_KP_COUNT = 0
- MAPPING_GATE = FAIL
- NEXT_STAGE = QB2-E2H2 G5 Canonical Mapping Final Human Decisions
- BLOCKER = PRODUCTION_KNOWLEDGE_POINT_CANONICAL_MAPPING_REQUIRED
- Safety = read-only Production verification; no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment

## QB2-D3 G5 Systemic Difficulty + Question Type Audit (2026-09-02)

- LAST_COMPLETED_STAGE = QB2-D2H3
- CURRENT_STAGE = QB2-D3 Systemic Difficulty + Question Type Audit
- HUMAN_SAMPLE_RESULT = 5 PASS / 7 NEEDS_FIX / 0 REJECT
- SYSTEMIC_CLASSIFICATION_QUALITY_RISK = YES
- TOTAL_CANDIDATES = 1010
- DIFFICULTY_CHANGED = 294
- QUESTION_TYPE_CHANGED = 484
- SKILL_ALIGNMENT_WEAK = 1
- CONTENT_REPAIR_REQUIRED_COUNT = 1
- CAPACITY_REGRESSION_KP_COUNT = 30
- POST_CLASSIFICATION_AUTOMATED_GATE = FAIL (skill-alignment content repair required)
- G5_IMPORT_GATE = WAITING_CLASSIFICATION_HUMAN_SAMPLE
- NEXT_STAGE = QB2-D3H Classification Human Sample Review
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment

## QB2-D3H G5 Classification Human Sample Review (2026-09-02)

- LAST_COMPLETED_STAGE = QB2-D3
- CURRENT_STAGE = QB2-D3H Classification Human Sample Review + Content Repair Planning
- DIFFICULTY_AUDIT = PASS
- QUESTION_TYPE_AUDIT = PASS
- SKILL_ALIGNMENT_AUDIT = REVIEW_REQUIRED
- WEAK_SKILL_ALIGNMENT_COUNT = 1
- RELATED_WEAK_DESIGN_COUNT = 0
- WEAK_SKILL_ALIGNMENT_IDS = QB2D2H2-0003 (POST-REPAIR-003)
- POST_REPAIR_003_CONTENT_REPAIR_REQUIRED = YES
- POST_CLASSIFICATION_SAMPLE_COUNT = 20
- HIGH_PRIORITY_COUNT = 1
- MEDIUM_PRIORITY_COUNT = 20
- LOW_PRIORITY_COUNT = 0
- G5_IMPORT_GATE = NOT_READY
- NEXT_STAGE = QB2-D3R Targeted POST-REPAIR-003 Content Repair
- BLOCKER = CONTENT_REPAIR_REQUIRED
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- G6 = NOT_STARTED

## QB2-E2 G5 Production Knowledge Point Canonical Mapping (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E
- CURRENT_STAGE = QB2-E2 G5 Production Knowledge Point Canonical Mapping
- PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
- PRODUCTION_IMPORT_AUTHORIZED = NO
- MANIFEST_RECORD_COUNT = 1014
- FK_DIRECT_MATCH_COUNT = 45 (599 records)
- SEMANTIC_EQUIVALENT_COUNT = 10 (140 records)
- AMBIGUOUS_KP_COUNT = 7
- NO_MATCH_KP_COUNT = 13
- DIRECT_MATCH_RECORDS = 599
- SAFE_MAPPED_RECORDS = 140
- MANUAL_HOLD_RECORDS = 275
- POST_MAPPING_FK_FAIL = 275
- MAPPING_GATE = FAIL
- NEXT_STAGE = QB2-E2H G5 Canonical Mapping Human Resolution
- BLOCKER = PRODUCTION_KNOWLEDGE_POINT_CANONICAL_MAPPING_REQUIRED
- Safety = read-only mapping resolution; no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- G6 = NOT_STARTED

## QB2-E G5 Production Import Authorization Gate (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-D3R2H
- CURRENT_STAGE = QB2-E G5 Production Import Authorization Gate
- G5_HUMAN_GATE = PASS
- G5_IMPORT_PREPARATION_GATE = PASS
- PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
- PRODUCTION_PROJECT_VERIFIED = YES
- STAGING_PROJECT_ID = odttigkvfazpbnxhpiqe
- STAGING_USED_AS_TARGET = NO
- TARGET_SCHEMA = public
- TARGET_TABLE = item_bank
- MANIFEST_COUNT = 1014
- PLANNED_INSERT_COUNT = 1014 (pre-gate plan)
- CURRENT_PRODUCTION_QUESTION_COUNT = 110123
- CURRENT_G5_QUESTION_COUNT = 0
- PRODUCTION_ID_COLLISIONS = 0
- PRODUCTION_EXACT_DUPLICATES = 0
- PRODUCTION_CANONICAL_DUPLICATES = 0
- FK_VALIDATION_FAIL = 415 (internal G5-K IDs lack verified Production G05 canonical mapping)
- PRODUCTION_SCHEMA_CONTRACT = PASS
- PRE_IMPORT_BACKUP_REQUIRED = YES
- ROLLBACK_PLAN_READY = YES
- PRODUCTION_IMPORT_AUTHORIZED = NO
- QB2_E_AUTHORIZATION_GATE = FAIL
- NEXT_STAGE = QB2-E2 G5 Knowledge Point Canonical Mapping Exception Resolution
- BLOCKER = PRODUCTION_KNOWLEDGE_POINT_FK_MAPPING_REQUIRED
- Safety = read-only verification only; no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- G6 = NOT_STARTED

## QB2-D3R2H G5-K001 Final Human Review (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-D3R2H
- G5_FINAL_HUMAN_REVIEW = 5 / 5 PASS
- HUMAN_REVIEW_GATE = PASS
- G5_K001_CAPACITY_GATE = PASS (BASIC 5 / STANDARD 5 / ADVANCED 3 / CHALLENGE 2)
- MATH_GATE = PASS
- SEMANTIC_GATE = PASS
- SKILL_ALIGNMENT_GATE = PASS
- DIFFICULTY_GATE = PASS
- QUESTION_TYPE_GATE = PASS
- DUPLICATE_GATE = PASS
- APP_CONTRACT_GATE = PASS
- IMPORT_DRY_RUN = PASS
- IMPORT_DRY_RUN_FAIL = 0
- ID_COLLISION_COUNT = 0
- G5_HUMAN_GATE = PASS
- G5_IMPORT_PREPARATION_GATE = PASS
- NEXT_STAGE = QB2-E G5 Production Import Authorization Gate
- G5 = READY_PENDING_EXPLICIT_IMPORT_AUTHORIZATION
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- G6 = NOT_STARTED

## QB2-D3R2 G5-K001 Remaining Capacity Repair (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-D3R
- CURRENT_STAGE = QB2-D3R2 G5-K001 Remaining Capacity Repair
- G5_K001_BASIC = 5
- G5_K001_STANDARD = 5
- G5_K001_ADVANCED = 3
- G5_K001_CHALLENGE = 2
- NEW_BASIC_READY = 1
- NEW_ADVANCED_READY = 1
- NEW_CHALLENGE_READY = 2
- MATH_PASS = 4
- SEMANTIC_PASS = 4
- SKILL_ALIGNMENT_PASS = 4
- DIFFICULTY_PASS = 4
- DUPLICATE_PASS = 4
- APP_CONTRACT_PASS = 4
- IMPORT_DRY_RUN = PASS
- IMPORT_DRY_RUN_FAIL = 0
- ID_COLLISION_COUNT = 0
- HUMAN_SAMPLE_COUNT = 5 (PENDING)
- G5_IMPORT_GATE = WAITING_FINAL_HUMAN_REVIEW
- NEXT_STAGE = QB2-D3R2H G5-K001 Final Human Review
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- G6 = NOT_STARTED

## QB2-D3R Targeted POST-REPAIR-003 Content Repair (2026-09-02)

- LAST_COMPLETED_STAGE = QB2-D3H
- CURRENT_STAGE = QB2-D3R Targeted POST-REPAIR-003 Content Repair
- RELATED_WEAK_DESIGN_COUNT = 0
- POST_REPAIR_003_REPAIRED = YES
- OLD_QUESTION_ID = QB2D2H2-0003 (historical NEEDS_FIX preserved)
- REPLACEMENT_QUESTION_ID = QB2D3R-G5-K001-0001
- MATH_GATE = PASS
- SEMANTIC_GATE = PASS
- SKILL_ALIGNMENT_GATE = PASS
- DIFFICULTY_GATE = PASS
- QUESTION_TYPE_GATE = PASS
- DUPLICATE_GATE = PASS
- APP_CONTRACT_GATE = PASS
- G5_K001_CAPACITY_BEFORE = BASIC 4 / STANDARD 4 / ADVANCED 2 / CHALLENGE 0 (defective candidate excluded)
- G5_K001_CAPACITY_AFTER = BASIC 4 / STANDARD 5 / ADVANCED 2 / CHALLENGE 0 (remaining research gap)
- IMPORT_DRY_RUN = PASS
- ID_COLLISION_COUNT = 0
- REPLACEMENT_HUMAN_SAMPLE_COUNT = 4
- G5_IMPORT_GATE = NOT_READY (capacity threshold still incomplete; human review pending)
- NEXT_STAGE = QB2-D3R2 G5-K001 Remaining Capacity Repair + Replacement Human Review
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- G6 = NOT_STARTED

## QB2-D2H2 — G5 Systemic Semantic Generator Repair (2026-09-02)

- LAST_COMPLETED_STAGE = QB2-D2H1
- CURRENT_STAGE = QB2-D2H2 G5 Systemic Semantic Generator Repair
- SYSTEMIC_GENERATOR_DEFECT = YES
- AFFECTED_TEMPLATE_COUNT = 12
- AFFECTED_KP_COUNT = 8
- TOTAL_IMPACTED_CANDIDATES = 12
- IMPACTED_IN_IMPORT_MANIFEST = 3
- SEMANTIC_FAIL_IMPACTED = 12
- REPAIR_QUESTIONS_GENERATED = 12
- REPAIR_SEMANTIC_PASS = 12
- REPAIR_READY = 12
- FULL_CANDIDATE_SEMANTIC_TOTAL = 1010
- FULL_CANDIDATE_SEMANTIC_FAIL = 0
- FINAL_ENOUGH_KP_AFTER_REPAIR = 30
- FINAL_LOW_KP_AFTER_REPAIR = 45
- FINAL_MISSING_KP_AFTER_REPAIR = 0
- IMPORT_DRY_RUN_RECORDS = 1010
- IMPORT_DRY_RUN_FAIL = 0
- ID_COLLISION_COUNT = 0
- POST_REPAIR_AUTOMATED_IMPORT_GATE = PASS
- G5_IMPORT_GATE = WAITING_POST_REPAIR_HUMAN_SAMPLE
- NEXT_STAGE = QB2-D2H3 G5 Post-Repair Human Sample Review
- BLOCKER = POST_REPAIR_HUMAN_SAMPLE_PENDING
- SEMANTIC_REPAIR_ROOT = C:\MathAI\data\question_research\qb2_g5_semantic_repair
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment

## QB2-D2H1 — G5 Full Semantic Consistency Audit (2026-09-02)

- SEMANTIC_AUDIT_TOTAL = 60
- SEMANTIC_PASS = 48
- SEMANTIC_FAIL = 12
- FAIL_SAMPLE_IDS = G5-SAMPLE-028, 029, 026, 027, 030, 032, 035, 033, 034, 024, 023, 022
- WRONG_KNOWLEDGE_POINT_COUNT = 3
- WRONG_MICRO_SKILL_COUNT = 0
- WRONG_OPERATION_COUNT = 0
- ANSWER_QUESTION_MISMATCH_COUNT = 9
- SYSTEMIC_PATTERN_FOUND = YES
- SYSTEMIC_GENERATOR_DEFECT = YES
- AFFECTED_KNOWLEDGE_POINTS = G05-N-FRAC-SUB-01, G5-K001, G5-K102, G5-K106, G5-K201, G5-K204, G5-K301, G5-K404
- SAMPLE_034_RESULT = NEEDS_FIX
- NEXT_STAGE = QB2-D2H2 G5 Semantic Repair Review
- BLOCKER = HUMAN_SAMPLE_SEMANTIC_REVIEW_REQUIRED
- Safety = no question edit; no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment

## QB2-D2 — G5 Human Sample Review Package (2026-09-02)

- WORKSTREAM = 題庫第二階段
- LAST_COMPLETED_STAGE = QB2-D
- CURRENT_STAGE = QB2-D2 G5 Human Sample Review
- ORIGINAL_SAMPLE_COUNT = 60
- FINAL_SAMPLE_COUNT = 60
- AUTO_REVIEW_PASS = 50
- AUTO_REVIEW_FLAG = 10
- FLAGGED_SAMPLE_IDS = C3 similarity-boundary records; see G5_HUMAN_REVIEW_PRIORITY.csv
- HUMAN_SAMPLE_STATUS = WAITING_USER_REVIEW
- AUTOMATED_IMPORT_GATE = PASS
- G5_IMPORT_GATE = WAITING_HUMAN_SAMPLE
- NEXT_STAGE = QB2-D2H Await Human Review
- BLOCKER = HUMAN_SAMPLE_PENDING
- REVIEW_ROOT = C:\MathAI\data\question_research\qb2_g5_human_review
- HUMAN_REVIEWED_COUNT = 1
- HUMAN_NEEDS_FIX_COUNT = 1
- HUMAN_REVIEW_ISSUE = G5-SAMPLE-034 / WRONG_KNOWLEDGE_POINT
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- Startup rule preserved = launch Codex from C:\MathAI using codex.cmd

## QB2-D — G5 Final Verification + Human Sampling + Import Gate (2026-09-02)

- WORKSTREAM = 題庫第二階段
- LAST_COMPLETED_STAGE = QB2-C3
- CURRENT_STAGE = QB2-D G5 Final Verification + Human Sampling + Import Gate
- G5_FINAL_CANDIDATES = 1001
- G5_FINAL_ENOUGH_KP = 27
- G5_FINAL_LOW_CAPACITY_KP = 48
- G5_FINAL_MISSING_KP = 0
- CAPACITY_REGRESSION_KP = 48 (C3 high-similarity review exclusions)
- FINAL_EXACT_DUPLICATES = 0
- FINAL_HIGH_SIMILARITY = 0
- FINAL_DIRECT_VARIANTS = 0
- POSSIBLE_DERIVATIVE_COUNT = 0
- FINAL_ANSWER_PASS = 1001
- FINAL_ANSWER_FAIL = 0
- MATH_RENDER_PASS = PASS
- PARSE_FAIL_COUNT = 0
- CURRICULUM_INTEGRITY_PASS = PASS
- ORPHAN_KNOWLEDGE_POINT_COUNT = 0
- DIFFICULTY_AUDIT = PASS
- DIFFICULTY_REVIEW_COUNT = 0
- APP_CONTRACT_PASS_COUNT = 1001
- APP_CONTRACT_FAIL_COUNT = 0
- LOW_RISK_IMPORT_COUNT = 1001
- MEDIUM_RISK_REVIEW_COUNT = 0
- HIGH_RISK_REJECT_COUNT = 0
- HUMAN_SAMPLE_COUNT = 60
- HUMAN_SAMPLE_STATUS = PENDING
- IMPORT_SCHEMA_DRY_RUN = PASS
- IMPORT_DRY_RUN_RECORDS = 1001
- IMPORT_DRY_RUN_FAIL = 0
- IMPORT_ID_STRATEGY = qb2-g5- plus first 24 hexadecimal fingerprint characters
- ID_COLLISION_COUNT = 0
- AUTOMATED_IMPORT_GATE = PASS
- G5_IMPORT_GATE = WAITING_HUMAN_SAMPLE
- QB2_D_ROOT = C:\MathAI\data\question_research\qb2_g5_final
- NEXT_STAGE = QB2-D2 G5 Human Sample Review
- BLOCKER = HUMAN_SAMPLE_PENDING
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no commit, push, or deployment
- Startup rule preserved = launch Codex from C:\MathAI using codex.cmd

## QB2-C3 — G5 Targeted Manual Template Repair (2026-09-02)

- WORKSTREAM = 題庫第二階段
- LAST_COMPLETED_STAGE = QB2-C2
- CURRENT_STAGE = QB2-C3 Targeted Manual Template Repair
- C3_TARGET_KP_COUNT = 75
- C3_TOTAL_DEFICIT = 976
- C3_BASIC_DEFICIT = 268
- C3_STANDARD_DEFICIT = 347
- C3_ADVANCED_DEFICIT = 211
- C3_CHALLENGE_DEFICIT = 150
- C3_GENERATED = 976
- C3_ANSWER_VALIDATED = 976
- C3_READY = 976
- C3_REVIEW = 0
- C3_EXACT_DUPLICATES = 0
- C3_HIGH_SIMILARITY = 0
- C3_DIRECT_VARIANTS = 0
- APP_CONTRACT_PASS_COUNT = 976
- APP_CONTRACT_FAIL_COUNT = 0
- G5_MISSING_KP_AFTER_C3 = 0
- G5_LOW_CAPACITY_KP_AFTER_C3 = 0
- G5_ENOUGH_KP_AFTER_C3 = 75
- MANUAL_REVIEW_REQUIRED_KP = 0
- C3_QUALITY_GATE = PASS
- C3_ROOT = C:\MathAI\data\question_research\qb2_g5_original_c3
- NEXT_STAGE = QB2-D G5 Final Verification + Human Sampling + Import Gate
- BLOCKER = NONE
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no external AI call; no commit, push, or deployment
- Startup rule preserved = launch Codex from C:\MathAI using codex.cmd

## QB2-B — G5 Targeted Gap Filling + Verification（2026-09-02）

- WORKSTREAM = 題庫第二階段
- LAST_COMPLETED_STAGE = QB2-A
- CURRENT_STAGE = QB2-B G5 Targeted Gap Filling + Verification
- TARGET_KP_COUNT = 75
- SEARCHED_KP_COUNT = 16
- NEW_RAW_FOUND = 18
- NEW_UNIQUE_FOUND = 18
- NEW_VERIFIED = 18
- NEW_READY_FOR_IMPORT = 0
- G5_MISSING_KP_BEFORE = 50
- G5_MISSING_KP_AFTER = 35
- G5_LOW_CAPACITY_KP_BEFORE = 25
- G5_LOW_CAPACITY_KP_AFTER = 40
- G5_ENOUGH_KP_BEFORE = 0
- G5_ENOUGH_KP_AFTER = 0
- COPYRIGHT_REVIEW = 18 (official public source, explicit reuse license not confirmed)
- ANSWER_CONFLICTS = 0
- REMAINING_SOURCE_GAPS = 75 knowledge points remain below threshold; 59 received no new safe item in this bounded cycle
- READY_FOR_IMPORT = 0; no Production import performed
- GAPFILL_ROOT = C:\MathAI\data\question_research\qb2_g5_gapfill
- NEXT_STAGE = QB2-C  G5 Original Question Generation for Remaining Safe Gaps
- BLOCKER = NONE
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no Gemini/DeepSeek call; no commit, push, or deployment

## QB2-C — G5 Original Question Generation（2026-09-02）

- WORKSTREAM = 題庫第二階段
- LAST_COMPLETED_STAGE = QB2-B
- CURRENT_STAGE = QB2-C G5 Original Question Generation
- TARGET_KP_COUNT = 75
- TOTAL_ORIGINAL_PLANNED = 1071
- TOTAL_ORIGINAL_GENERATED = 73
- TOTAL_ORIGINAL_VERIFIED = 73
- TOTAL_ORIGINAL_READY = 55
- TOTAL_ORIGINAL_NEEDS_REVIEW = 20
- EXACT_DUPLICATE_REJECTED = 18
- ANSWER_VALIDATION_FAIL = 0
- QUALITY_GATE = FAIL
- QUALITY_BLOCKER = BATCH_001_DUPLICATE_RATE_EXCEEDS_20_PERCENT (18/73 = 24.66%)
- G5_MISSING_KP_BEFORE = 35
- G5_MISSING_KP_AFTER = 10
- G5_LOW_CAPACITY_KP_BEFORE = 40
- G5_LOW_CAPACITY_KP_AFTER = 65
- G5_ENOUGH_KP_AFTER = 0
- ORIGINAL_ROOT = C:\MathAI\data\question_research\qb2_g5_original
- NEXT_STAGE = QB2-C2  G5 Remaining Gap Repair
- Safety = generation stopped at Batch 001 quality threshold; no Production/Staging mutation; no DB/RLS change; no question-bank import; no external AI call; no commit, push, or deployment

### Phase 3J4-H2B — Network-independent Local Test Session

- Root cause = Local test login still called `create_local_test_user_session`, whose Auth administrator lookup required a remote Supabase network connection and raised `httpx.ConnectError` / WinError 10013.
- LOCAL_TEST_SESSION_SUPABASE_NETWORK_DEPENDENCY = RESOLVED
- Local test OTP/session/new-user flow = in-memory localhost-only fixture
- REMOTE_AUTH_CALL_DURING_LOCAL_TEST = 0
- SUPABASE_NETWORK_CALL_DURING_LOCAL_TEST = 0
- PRODUCTION_AUTH_FLOW_UNCHANGED = YES
- PRODUCTION_TEST_BYPASS = NO
- Local regression = 39 passed
- LOCAL_REFERRAL_HUMAN_VALIDATION = READY
- Local URL = http://localhost:8512/
- NEXT_ACTION = 使用者人工驗收「你從哪裡知道 MathAI？」→「親友／老師介紹」→「介紹人 Email／驗證介紹人資格」。不要 commit、push 或 deploy。

## Phase 狀態

- Phase 3H = PASS / FROZEN
- Phase 3J0 = PASS
- Phase 3J1 = PASS
- Phase 3J2-L1 = PASS
- Phase 3J2-L2 True Gemini Runtime = PASS
- ANSWER_VALUE = 6
- ANSWER_OPTION = C
- POINT_DEDUCTION = 0
- LOCAL_RELEASE_CANDIDATE = READY
- FINAL_REGRESSION_TESTS = PASS
- LOCAL_BOOT = PASS
- HTTP = PASS
- FINAL_BACKUP = PASS
- RELEASE_CANDIDATE_LOCK = FAIL

Release Candidate Lock 失敗原因：目前已驗收 working tree 不是正式 main Release Candidate 工作區。不要因此 reset / clean 現有 tree。

下一階段：Phase 3J2-L3B — Safe Main Release Worktree / RC Lock。

策略：建立乾淨 main Release Candidate worktree，只帶入已確認需要正式 Release 的 changes；不要直接清洗目前 working tree。

## 下一個 Session 禁止重做事項

- 不要重新做 Phase 3H。
- 不要重新跑 30 題 Calibration。
- 不要重新做 True Gemini Runtime 單題驗收。
- 不要重新設定 Gemini Key。
- 不要重新研究已完成題庫 taxonomy。
- 不要重新建立 Cloud Beta。
- 不要 reset / clean 現有 dirty tree。
- 不要未授權就 Push / Deploy。

下一個真正工作：Phase 3J2-L3B — Safe Main Release Worktree / RC Lock。

## Secret Security 永久規則

任何 `secrets.toml`、API key、token、password、service role key、SMTP credential 不得 commit、push、放入一般 ZIP backup、QA report、handoff，也不得 print、echo 或 log。

本 handoff 不保存任何 Secret VALUE。

SECURITY_FOLLOWUP = 下一次維護時安排 Secret Rotation Review；至少檢查並在必要時 rotate Supabase service role credential、Gemini credential、DeepSeek credential、SMTP App Password、Staging test account passwords。今天不執行 rotation。

## Crash Recovery / Git Safety Audit（2026-09-01）

- REPO_ACCESSIBLE = YES
- CURRENT_BRANCH = private-beta-derived-v1
- CURRENT_HEAD = e4c2dbf3545eebc0f0b999fd6f844c677cfa3962
- GIT_LOCK_PRESENT = NO
- WORKING_TREE_DIRTY = YES（合法現況，不代表 FAIL；不得清洗）
- SECRET_GIT_IGNORED = YES
- SECRET_TRACKED = NO
- SECRET_STAGED = NO
- CRASH_RECOVERY = PASS

## End-of-Day Backup（最終結果）

- EOD_BACKUP_DATE = 2026-09-01
- HANDOFF_UPDATED_PRE_BACKUP = PASS
- CRASH_RECOVERY = PASS
- LOCAL_BACKUP = PASS
- LOCAL_BACKUP_FOLDER = C:\MathAI\backups\MathAI_EOD_20260901_223750
- LOCAL_BACKUP_ZIP = C:\MathAI\backups\MathAI_EOD_20260901_223750.zip
- LOCAL_SHA256_FOLDER_INTEGRITY = PASS（132 files verified）
- LOCAL_ZIP_READABLE = YES
- EXTERNAL_DRIVE_CANDIDATES = NONE
- EXTERNAL_DRIVE_SELECTED = NONE
- EXTERNAL_BACKUP = FAIL
- EXTERNAL_BACKUP_FOLDER = NOT_CREATED
- EXTERNAL_BACKUP_ZIP = NOT_CREATED
- EXTERNAL_BACKUP_ZIP_READABLE = NO
- LOCAL_EXTERNAL_ZIP_HASH_MATCH = NO（未偵測到外接硬碟，無法比對）
- SECRET_FILES_INCLUDED = NO
- SOURCE_HEAD_UNCHANGED = YES
- SOURCE_STATUS_SET_UNCHANGED = YES
- HANDOFF_UPDATED_FINAL = PASS
- SAFE_TO_SHUTDOWN = NO
- SHUTDOWN_SCHEDULED = NO
- BLOCKER = EXTERNAL_DRIVE_NOT_FOUND
- LAST_COMPLETED_PHASE = 3J2-L2
- NEXT_PHASE = 3J2-L3B
- RELEASE_CANDIDATE_LOCK = FAIL
- CURRENT_BLOCKER = 需建立 clean main Release Candidate worktree 並重新確認 release scope。

## 本次禁止操作計數

- GIT_COMMIT = 0
- GIT_PUSH = 0
- DEPLOYMENT = 0
- PRODUCTION_MUTATIONS = 0
- STAGING_MUTATIONS = 0
- DB_MIGRATIONS = 0
- RLS_CHANGES = 0
- QUESTION_BANK_IMPORTS = 0

## QB2-C2 — G5 Remaining Gap Repair (2026-09-02)

- WORKSTREAM = 題庫第二階段
- LAST_COMPLETED_STAGE = QB2-C
- CURRENT_STAGE = QB2-C2 G5 Remaining Gap Repair
- QB2_C_BLOCKER = BATCH_001_DUPLICATE_RATE_EXCEEDS_20_PERCENT
- ROOT_CAUSE = overlapping G5-K and G05 curriculum targets reused 18 identical generator branches
- QB2_C2_RESULT = QUALITY_PASS_WITH_REMAINING_LOW_CAPACITY_GAPS
- C2_GENERATED = 40
- C2_ANSWER_VALIDATED = 40
- C2_READY = 40
- C2_REVIEW = 0
- C2_EXACT_DUPLICATES = 0
- C2_HIGH_SIMILARITY = 0
- C2_DIRECT_VARIANTS = 0
- QUARANTINED_TEMPLATE_COUNT = 18
- ANSWER_PASS_RATE = 100.00%
- TEXT_QUALITY_PASS_RATE = 100.00%
- APP_CONTRACT_PASS_RATE = 100.00%
- STRUCTURAL_DIVERSITY_STATUS = PASS_FOR_C2_BATCH
- G5_MISSING_KP_AFTER_C2 = 0
- G5_LOW_CAPACITY_KP_AFTER_C2 = 75
- G5_ENOUGH_KP_AFTER_C2 = 0
- QUALITY_GATE = PASS
- C2_ROOT = C:\MathAI\data\question_research\qb2_g5_original_c2
- NEXT_STAGE = QB2-C3 Targeted Manual Template Repair
- BLOCKER = REMAINING_LOW_CAPACITY_KP_75
- Safety = no Production/Staging mutation; no DB/RLS change; no question-bank import; no external AI call; no commit, push, or deployment
- Startup rule preserved = launch Codex from C:\MathAI using codex.cmd

## QB2-E2H2 G5 Canonical Mapping Final Human Decisions (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E2H
- CURRENT_STAGE = QB2-E2H2 G5 Canonical Mapping Final Human Decisions
- MANUAL_HOLD_RECORDS = 261
- UNRESOLVED_UNIQUE_RESEARCH_KP_COUNT = 19
- E2H2_SAFE_RESOLVED_KP_COUNT = 0
- E2H2_SAFE_RESOLVED_RECORDS = 0
- HUMAN_DECISION_REQUIRED_KP_COUNT = 19
- HUMAN_DECISION_REQUIRED_RECORDS = 261
- PRODUCTION_CURRICULUM_GAP_KP_COUNT = 0
- PRODUCTION_CURRICULUM_GAP_RECORDS = 0
- E2H2_FK_TOTAL = 1014
- E2H2_FK_PASS = 753
- E2H2_FK_FAIL = 261
- MAPPING_GATE = FAIL
- PRODUCTION_IMPORT_AUTHORIZED = NO
- NEXT_STAGE = QB2-E2H3 Final KP Human Decisions
- BLOCKER = PRODUCTION_KNOWLEDGE_POINT_CANONICAL_MAPPING_REQUIRED
- Safety = KP-level local-only resolution; no Production/Staging mutation, import, migration, RLS change, commit, push, or deployment

## QB2-E2H4 G5 Production Curriculum Gap Resolution Planning (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E2H3-B
- CURRENT_STAGE = QB2-E2H4 G5 Production Curriculum Gap Resolution Planning
- PRODUCTION_CURRICULUM_GAP_KP_COUNT = 7
- PRODUCTION_CURRICULUM_GAP_RECORDS = 100
- HUMAN_CHOICE_KP_COUNT = 3
- HUMAN_CHOICE_RECORDS = 43
- PROPOSED_NEW_CANONICAL_KP_COUNT = 7
- SPLIT_MAPPING_KP_COUNT = 1
- SINGLE_CANONICAL_MAPPING_KP_COUNT = 2
- SIMULATED_FK_TOTAL = 1014
- SIMULATED_FK_PASS = 1014
- SIMULATED_FK_FAIL = 0
- SIMULATED_UNRESOLVED_RECORDS = 0
- PRODUCTION_CURRICULUM_MUTATION_AUTHORIZED = NO
- PRODUCTION_IMPORT_AUTHORIZED = NO
- NEXT_STAGE = QB2-E2H5 G5 Production Curriculum Update Authorization Gate
- BLOCKER = NONE (authorization still required)
- Safety = local planning and simulation only; no Production/Staging mutation, import, migration, RLS change, commit, push, or deployment

## QB2-E2H5 G5 Production Curriculum Update Authorization Gate (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E2H4
- CURRENT_STAGE = QB2-E2H5 G5 Production Curriculum Update Authorization Gate
- PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
- PROPOSED_NEW_CANONICAL_KP_COUNT = 7
- PLANNED_INSERT_COUNT = 7
- EXISTING_NODE_UPDATE_COUNT = 0
- POST_UPDATE_SIMULATED_FK_TOTAL = 1014
- POST_UPDATE_SIMULATED_FK_PASS = 1014
- POST_UPDATE_SIMULATED_FK_FAIL = 0
- CURRICULUM_UPDATE_AUTHORIZATION_GATE = PASS
- PRODUCTION_CURRICULUM_MUTATION_AUTHORIZED = NO
- PRODUCTION_IMPORT_AUTHORIZED = NO
- NEXT_STAGE = WAITING_USER_CURRICULUM_UPDATE_AUTHORIZATION
- BLOCKER = NONE
- Safety = read-only preflight and local mutation preview; no Production/Staging mutation, import, migration, RLS change, commit, push, or deployment

## QB2-E2H5 G5 Production Curriculum Update (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E2H5
- CURRENT_STAGE = QB2-E2H5 G5 Production Curriculum Update Completed
- PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
- CURRICULUM_UPDATE_AUTHORIZED = YES (explicit user confirmation)
- CURRICULUM_UPDATE_BATCH_ID = G5-CURRICULUM-QB2-E2H5
- CURRICULUM_UPDATE_MODE = INSERT_ONLY
- CURRICULUM_INSERTED_ROWS = 7
- EXISTING_NODE_UPDATE_COUNT = 0
- RELATION_INSERT_COUNT = 0
- DELETE_COUNT = 0
- PRODUCTION_G05_CURRICULUM_COUNT_AFTER = 52
- POST_UPDATE_VERIFICATION = PASS
- PRODUCTION_IMPORT_AUTHORIZED = NO
- QUESTION_BANK_IMPORTS = 0
- PRODUCTION_MUTATIONS = 7 curriculum inserts only
- NEXT_STAGE = QB2-E3 G5 Production Import Authorization Recheck
- BLOCKER = NONE
- Safety = no question-bank import, student/auth/learning/wallet mutation, migration, RLS change, commit, push, or deployment

## QB2-E3 G5 Production Question Bank Import Authorization Recheck (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E2H5
- CURRENT_STAGE = QB2-E3 G5 Production Question Bank Import Authorization Recheck
- PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
- FINAL_IMPORT_MANIFEST = C:\MathAI\data\question_research\qb2_g5_production_mapping\G5_IMPORT_MANIFEST_PRODUCTION_MAPPED_PREVIEW_E3.csv
- MANIFEST_COUNT = 1014
- CURRENT_PRODUCTION_QUESTION_COUNT = 110123
- CURRENT_G5_QUESTION_COUNT = 0
- FK_VALIDATION_TOTAL = 1014
- FK_VALIDATION_PASS = 896
- FK_VALIDATION_FAIL = 118
- PLANNED_INSERT_COUNT = 896
- PRODUCTION_IMPORT_AUTHORIZED = NO
- NEXT_STAGE = WAITING_USER_PRODUCTION_IMPORT_AUTHORIZATION
- BLOCKER = NONE (explicit import authorization still required)
- Safety = read-only recheck/local preview; no question-bank import, no student/auth/wallet mutation, no migration, RLS change, commit, push, or deployment

## QB2-E3 G5 Production Question Bank Import Authorization Recheck (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E2H5
- CURRENT_STAGE = QB2-E3 G5 Production Question Bank Import Authorization Recheck
- PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
- FINAL_IMPORT_MANIFEST = C:\MathAI\data\question_research\qb2_g5_production_mapping\G5_IMPORT_MANIFEST_PRODUCTION_MAPPED_PREVIEW_E3.csv
- MANIFEST_COUNT = 1014
- CURRENT_PRODUCTION_QUESTION_COUNT = 110123
- CURRENT_G5_QUESTION_COUNT = 0
- FK_VALIDATION_TOTAL = 1014
- FK_VALIDATION_PASS = 896
- FK_VALIDATION_FAIL = 118
- PLANNED_INSERT_COUNT = 896
- PRODUCTION_IMPORT_AUTHORIZED = NO
- NEXT_STAGE = QB2-E3H Remaining KP Canonical Mapping Resolution
- BLOCKER = UNRESOLVED_PRODUCTION_KP_MAPPING
- Safety = read-only recheck/local preview; no question-bank import, no student/auth/wallet mutation, no migration, RLS change, commit, push, or deployment

## QB2-E3R G5 Remaining KP Canonical Mapping Reconciliation (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E3
- CURRENT_STAGE = QB2-E3R Remaining KP Canonical Mapping Reconciliation
- E3_INITIAL_UNRESOLVED_RECORDS = 118
- E3_INITIAL_UNRESOLVED_KP_COUNT = 9
- MAPPING_NOT_APPLIED_KP_COUNT = 0
- SPLIT_ROUTING_NOT_MATERIALIZED_KP_COUNT = 0
- PRODUCTION_ID_MISMATCH_KP_COUNT = 0
- STALE_MAPPING_SOURCE_KP_COUNT = 0
- ACTUAL_PRODUCTION_CURRICULUM_GAP_KP_COUNT = 9
- E3R_FK_TOTAL = 1014
- E3R_FK_PASS = 896
- E3R_FK_FAIL = 118
- CANONICAL_MAPPING_RECONCILIATION_GATE = FAIL
- PRODUCTION_IMPORT_AUTHORIZED = NO
- NEXT_STAGE = QB2-E3H Remaining KP Canonical Mapping Resolution
- BLOCKER = UNRESOLVED_PRODUCTION_KP_MAPPING
- Safety = local routing only; no Production/Staging mutation, curriculum addition, question-bank import, migration, RLS change, commit, push, or deployment

## QB2-E3H G5 Remaining 9 KP Canonical Mapping Resolution (2026-09-03)

- LAST_COMPLETED_STAGE = QB2-E3R
- CURRENT_STAGE = QB2-E3H Remaining 9 KP Canonical Mapping Resolution
- INITIAL_FK_PASS = 896
- INITIAL_FK_FAIL = 118
- EXACT_MAPPING_KP_COUNT = 0
- PARENT_MAPPING_KP_COUNT = 0
- SPLIT_MAPPING_KP_COUNT = 4
- LOCAL_MAPPING_NOT_APPLIED_KP_COUNT = 0
- PRODUCTION_CURRICULUM_GAP_KP_COUNT = 5
- HUMAN_DECISION_REQUIRED_KP_COUNT = 0
- E3H_FK_PASS = 933
- E3H_FK_FAIL = 81
- PRODUCTION_IMPORT_AUTHORIZED = NO
- NEXT_STAGE = QB2-E3H2 Production Curriculum Gap Resolution
- BLOCKER = UNRESOLVED_PRODUCTION_KP_MAPPING
- Safety = local question-level routing only; no Production/Staging mutation, curriculum addition, question-bank import, migration, RLS change, commit, push, or deployment


## QB2-E3H2 G5 Remaining Curriculum Gap Resolution (read-only, 2026-09-03T10:41:56)
LAST_COMPLETED_STAGE = QB2-E3H
CURRENT_STAGE = QB2-E3H2 Remaining G5 Production Curriculum Gap Resolution
INITIAL_FK_PASS = 933
INITIAL_FK_FAIL = 81
CONFIRMED_CURRICULUM_GAP_KP_COUNT = 8
CONFIRMED_CURRICULUM_GAP_RECORD_COUNT = 81
EXISTING_TARGET_RECOVERED_KP_COUNT = 0
PROPOSED_NEW_CANONICAL_KP_COUNT = 8
SIMULATED_FK_PASS = 1014
SIMULATED_FK_FAIL = 0
E3H2_CURRICULUM_UPDATE_AUTHORIZATION_GATE = PASS
PRODUCTION_CURRICULUM_MUTATION_AUTHORIZED = NO
PRODUCTION_IMPORT_AUTHORIZED = NO
NEXT_STAGE = WAITING_USER_REMAINING_CURRICULUM_UPDATE_AUTHORIZATION
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED


## QB2-E3H2 G5 Remaining Curriculum Gap Resolution (read-only, 2026-09-03T10:42:42)
LAST_COMPLETED_STAGE = QB2-E3H
CURRENT_STAGE = QB2-E3H2 Remaining G5 Production Curriculum Gap Resolution
INITIAL_FK_PASS = 933
INITIAL_FK_FAIL = 81
CONFIRMED_CURRICULUM_GAP_KP_COUNT = 8
CONFIRMED_CURRICULUM_GAP_RECORD_COUNT = 81
EXISTING_TARGET_RECOVERED_KP_COUNT = 0
PROPOSED_NEW_CANONICAL_KP_COUNT = 8
SIMULATED_FK_PASS = 1014
SIMULATED_FK_FAIL = 0
E3H2_CURRICULUM_UPDATE_AUTHORIZATION_GATE = PASS
PRODUCTION_CURRICULUM_MUTATION_AUTHORIZED = NO
PRODUCTION_IMPORT_AUTHORIZED = NO
NEXT_STAGE = WAITING_USER_REMAINING_CURRICULUM_UPDATE_AUTHORIZATION
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED


## QB2-E3H2 G5 Remaining Curriculum Gap Resolution (read-only, 2026-09-03T10:43:17)
LAST_COMPLETED_STAGE = QB2-E3H
CURRENT_STAGE = QB2-E3H2 Remaining G5 Production Curriculum Gap Resolution
INITIAL_FK_PASS = 933
INITIAL_FK_FAIL = 81
CONFIRMED_CURRICULUM_GAP_KP_COUNT = 8
CONFIRMED_CURRICULUM_GAP_RECORD_COUNT = 81
EXISTING_TARGET_RECOVERED_KP_COUNT = 0
PROPOSED_NEW_CANONICAL_KP_COUNT = 8
SIMULATED_FK_PASS = 1014
SIMULATED_FK_FAIL = 0
E3H2_CURRICULUM_UPDATE_AUTHORIZATION_GATE = PASS
PRODUCTION_CURRICULUM_MUTATION_AUTHORIZED = NO
PRODUCTION_IMPORT_AUTHORIZED = NO
NEXT_STAGE = WAITING_USER_REMAINING_CURRICULUM_UPDATE_AUTHORIZATION
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED


## QB2-E3H2 G5 Remaining Curriculum Gap Resolution (read-only, 2026-09-03T10:43:53)
LAST_COMPLETED_STAGE = QB2-E3H
CURRENT_STAGE = QB2-E3H2 Remaining G5 Production Curriculum Gap Resolution
INITIAL_FK_PASS = 933
INITIAL_FK_FAIL = 81
CONFIRMED_CURRICULUM_GAP_KP_COUNT = 8
CONFIRMED_CURRICULUM_GAP_RECORD_COUNT = 81
EXISTING_TARGET_RECOVERED_KP_COUNT = 0
PROPOSED_NEW_CANONICAL_KP_COUNT = 8
SIMULATED_FK_PASS = 1014
SIMULATED_FK_FAIL = 0
E3H2_CURRICULUM_UPDATE_AUTHORIZATION_GATE = PASS
PRODUCTION_CURRICULUM_MUTATION_AUTHORIZED = NO
PRODUCTION_IMPORT_AUTHORIZED = NO
NEXT_STAGE = WAITING_USER_REMAINING_CURRICULUM_UPDATE_AUTHORIZATION
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
## QB2-E3H2 Production Curriculum Update Completed

PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
LAST_COMPLETED_STAGE = QB2-E3H2
CURRENT_STAGE = QB2-E3H2 Production Curriculum Update Completed; awaiting QB2-E3 recheck
CURRICULUM_UPDATE_AUTHORIZED = YES
CURRICULUM_UPDATE_MODE = INSERT_ONLY
CURRICULUM_UPDATE_BATCH_ID = G5-CURRICULUM-QB2-E3H2
NEW_CANONICAL_CURRICULUM_NODES = 8
EXISTING_NODE_UPDATES = 0
RELATION_INSERTS = 0
DELETES = 0
POST_UPDATE_G5_CURRICULUM_SKILLS = 60
POST_UPDATE_VERIFICATION = PASS
PRODUCTION_CURRICULUM_MUTATIONS = 8
PRODUCTION_IMPORT_AUTHORIZED = NO
QUESTION_BANK_IMPORTS = 0
NEXT_STAGE = QB2-E3 G5 Production Import Authorization Recheck
PRODUCTION_MUTATIONS = 8
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0


## QB2-E3B G5 Final Production Import Authorization Recheck (2026-09-03T10:58:39)
LAST_COMPLETED_STAGE = QB2-E3H2
CURRENT_STAGE = QB2-E3B G5 Final Production Import Authorization Recheck
G5_PRODUCTION_CURRICULUM_SKILLS = 60
FINAL_FK_PASS = 1014
FINAL_FK_FAIL = 0
FINAL_MANIFEST_COUNT = 1014
PLANNED_INSERT_COUNT = 1014
QB2_E3B_IMPORT_AUTHORIZATION_GATE = PASS
PRODUCTION_IMPORT_AUTHORIZED = NO
NEXT_STAGE = WAITING_USER_G5_FINAL_IMPORT_AUTHORIZATION
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
## QB2-E3B G5 Production Question Bank Import Completed

PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
LAST_COMPLETED_STAGE = QB2-E3B
CURRENT_STAGE = QB2-E3B G5 Production Question Bank Import Completed
QUESTION_IMPORT_BATCH_ID = G5-QB2-QUESTION-IMPORT-E3B-20260903-105839
IMPORT_MODE = INSERT_ONLY
FINAL_MANIFEST_COUNT = 1014
QUESTION_BANK_RECORDS_INSERTED = 1014
QUESTION_BANK_DUPLICATE_SKIPS = 0
QUESTION_BANK_BLOCKED_COLLISIONS = 0
POST_IMPORT_TOTAL_ITEM_BANK_RECORDS = 111137
POST_IMPORT_GRADE_5_RECORDS = 1019
CURRICULUM_MUTATIONS_THIS_STAGE = 0
QUESTION_BANK_IMPORTS = 1014
PRODUCTION_IMPORT_AUTHORIZED = YES
POST_IMPORT_VERIFICATION = PASS
NEXT_STAGE = QB2-E4 G5 Post-Import Verification and Smoke Test
PRODUCTION_MUTATIONS = 1014
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED

## QB2-F3 G5 Main App Integration Hotfix Released

LAST_COMPLETED_STAGE = QB2-F3
CURRENT_STAGE = QB2-F3 G5 Main App Integration Hotfix Released
PRODUCTION_RELEASE_AUTHORIZED = YES
RELEASE_SCOPE = G5 Production item_bank adapter and custom-exam selection wiring
RELEASE_COMMIT = current release commit (see git log)
RELEASE_PUSH = YES (authorized)
DEPLOYMENT = 0 (no deployment target configured)
NEXT_STAGE = QB2-F4 G5 Post-Release Production Smoke Verification
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
G6 = NOT_STARTED
## QB2-E4 G5 Post-Import Verification Completed

LAST_COMPLETED_STAGE = QB2-E3B
CURRENT_STAGE = QB2-E4 G5 Post-Import Verification
G5_PRODUCTION_IMPORT_COUNT = 1014
G5_PRODUCTION_QUESTION_BANK_STATUS = VERIFIED
QB2_E4_POST_IMPORT_GATE = PASS
QUESTION_COUNT_BEFORE = 110123
QUESTION_COUNT_AFTER = 111137
QUESTION_COUNT_DELTA = 1014
PRODUCTION_G5_BATCH_COUNT = 1014
POST_IMPORT_FK_FAIL = 0
NULL_REQUIRED_FIELD_COUNT = 0
DUPLICATE_ID_COUNT = 0
ORPHAN_KP_RECORD_COUNT = 0
NEXT_STAGE = QB2-F G5 Main App Production Question Bank Integration Verification
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
ADDITIONAL_QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
## QB2-F G5 Main App Production Integration Verification

LAST_COMPLETED_STAGE = QB2-E4
CURRENT_STAGE = QB2-F G5 Main App Production Question Bank Integration Verification
G5_PRODUCTION_QUESTION_BANK_STATUS = VERIFIED
PRODUCTION_PROJECT_VERIFIED = YES
STAGING_USED_AS_SOURCE = NO
NEW_G5_IMPORT_VISIBLE_TO_APP = NO
CUSTOM_EXAM_G5_INTEGRATION = FAIL
MAIN_APP_CODE_CHANGE_REQUIRED = YES
QB2_F_MAIN_APP_INTEGRATION_GATE = FAIL
BLOCKER = MAIN_APP_CUSTOM_EXAM_NOT_USING_PRODUCTION_ITEM_BANK
NEXT_STAGE = QB2-F2 G5 Main App Question Bank Integration Hotfix Plan
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
## QB2-F2 G5 Main App Production item_bank Hotfix

LAST_COMPLETED_STAGE = QB2-F
CURRENT_STAGE = QB2-F2 G5 Main App Production item_bank Integration Hotfix
ROOT_CAUSE_CLASS = I_PRODUCTION_PATH_EXISTS_BUT_NOT_CALLED
ROOT_CAUSE_FILE = app.py
ROOT_CAUSE_FUNCTION = custom exam generation branch / call_gemini_api
PRODUCTION_ITEM_BANK_TABLE = public.item_bank
MAIN_APP_CODE_CHANGE_REQUIRED = YES
PRE_HOTFIX_BACKUP = backups/QB2_F2_PRE_HOTFIX_BACKUP.md
CUSTOM_EXAM_PRODUCTION_ITEM_BANK_USED = PARTIAL_LOCAL_IMPLEMENTATION
CUSTOM_EXAM_PRODUCTION_MATCH_COUNT = NOT_FULLY_TRACED
NEW_G5_IMPORT_VISIBLE_TO_APP = YES_FOR_DIRECT_ITEM_BANK_READ
LEGACY_SOURCE_ACTIVE_IN_G5_FLOW = NO
GEMINI_CALLS = 0
DEEPSEEK_CALLS = 0
EXTERNAL_AI_CALLS = 0
QB2_F2_LOCAL_HOTFIX_GATE = FAIL
NEXT_STAGE = QB2-F2R Integration Hotfix Repair
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
## QB2-F2R G5 item_bank Schema / Contract Repair

LAST_COMPLETED_STAGE = QB2-F2
CURRENT_STAGE = QB2-F2R G5 item_bank Schema / App Contract Repair
ROOT_CAUSE_CLASS = F_IMPORT_DATA_LOSS
DIFFICULTY_STORAGE = MISSING
QUESTION_TYPE_STORAGE = MISSING
SOLUTION_STORAGE = MISSING
MICRO_SKILL_STORAGE = MISSING
PRODUCTION_SCHEMA_CHANGE_REQUIRED = YES
PRODUCTION_DATA_BACKFILL_REQUIRED = YES
MAIN_APP_CODE_CHANGE_REQUIRED = YES
QB2_F2R_LOCAL_REPAIR_GATE = BLOCKED
NEXT_STAGE = QB2-F2R2 Production Item Bank Schema Compatibility Plan
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED


## QB2-F2R2 Production item_bank Schema Compatibility Plan (2026-09-03T11:56:37)
LAST_COMPLETED_STAGE = QB2-F2R
CURRENT_STAGE = QB2-F2R2 Production Item Bank Schema Compatibility Plan
ROOT_CAUSE_CLASS = F_IMPORT_DATA_LOSS
DIFFICULTY_STORAGE = MISSING
QUESTION_TYPE_STORAGE = MISSING
SOLUTION_STORAGE = MISSING
RECOMMENDED_SCHEMA_STRATEGY = NATIVE_COLUMNS
PRODUCTION_SCHEMA_CHANGE_REQUIRED = YES
PRODUCTION_DATA_BACKFILL_REQUIRED = YES
BACKFILL_TARGET_RECORD_COUNT = 1014
QB2_F2R2_SCHEMA_COMPATIBILITY_AUTHORIZATION_GATE = PASS
PRODUCTION_SCHEMA_MUTATION_AUTHORIZED = NO
PRODUCTION_BACKFILL_AUTHORIZED = NO
NEXT_STAGE = WAITING_USER_G5_ITEM_BANK_SCHEMA_BACKFILL_AUTHORIZATION
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
## QB2-F2R2 G5 item_bank Schema and Metadata Backfill Completed

LAST_COMPLETED_STAGE = QB2-F2R2
CURRENT_STAGE = QB2-F2R2 G5 item_bank Schema and Metadata Backfill Completed
PRODUCTION_PROJECT_ID = igttuijrtwbtefhyeokp
SCHEMA_MUTATION_AUTHORIZED = YES
BACKFILL_AUTHORIZED = YES
SCHEMA_COLUMNS_ADDED = difficulty, question_type, solution
BACKFILL_TARGET_RECORD_COUNT = 1014
BACKFILL_DIFFICULTY_COUNT = 1014
BACKFILL_QUESTION_TYPE_COUNT = 1014
BACKFILL_SOLUTION_COUNT = 1014
LEGACY_RECORD_UPDATE_COUNT = 0
BACKFILL_VERIFICATION = PASS
PRODUCTION_SCHEMA_MUTATIONS = 1 migration
PRODUCTION_METADATA_BACKFILL_UPDATES = 1014
QUESTION_BANK_IMPORTS = 0
NEXT_STAGE = QB2-F3 G5 Main App Integration Hotfix Release Authorization
PRODUCTION_MUTATIONS = 1014 metadata rows plus schema migration
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 1
RLS_CHANGES = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
## QB2-F3 G5 Main App Production item_bank Integration Authorization

LAST_COMPLETED_STAGE = QB2-F2R2
CURRENT_STAGE = QB2-F3 G5 Main App Integration Hotfix Release Authorization
G5_ITEM_BANK_SCHEMA_BACKFILL = COMPLETED
CUSTOM_EXAM_PRODUCTION_ITEM_BANK_USED = YES
NEW_G5_IMPORT_VISIBLE_TO_APP = YES
PRODUCTION_ADAPTER_CONTRACT = PASS
UI_DIFFICULTY_MAPPING = PASS
UI_QUESTION_TYPE_MAPPING = PASS
UI_KP_MAPPING_VALID = PASS
CUSTOM_EXAM_PREVIEW_COUNT = 10
CUSTOM_EXAM_PRODUCTION_MATCH_COUNT = 10
CUSTOM_EXAM_DB_CONTENT_MATCH = PASS
ANSWER_FETCH = PASS
SOLUTION_FETCH = PASS
LEGACY_CSV_USED = NO
LOCAL_FIXTURE_USED = NO
HARDCODED_SOURCE_USED = NO
GEMINI_CALLS = 0
DEEPSEEK_CALLS = 0
EXTERNAL_AI_CALLS = 0
LOCAL_BOOT = PASS
HTTP = PASS
CUSTOM_EXAM_UI_SMOKE = PASS
PYTHON_COMPILE = PASS
ADAPTER_REGRESSION = PASS
CUSTOM_EXAM_REGRESSION = PASS
PHASE_3H_GOLDEN_LOCK_UNCHANGED = PASS
SECRET_SCAN = PASS
QB2_F3_RELEASE_AUTHORIZATION_GATE = PASS
MAIN_APP_CODE_CHANGE_REQUIRED = YES
PRODUCTION_RELEASE_AUTHORIZED = NO
NEXT_STAGE = WAITING_USER_G5_MAIN_APP_HOTFIX_RELEASE_AUTHORIZATION
PRODUCTION_MUTATIONS = 0
STAGING_MUTATIONS = 0
DB_MIGRATIONS = 0
RLS_CHANGES = 0
QUESTION_BANK_IMPORTS = 0
GIT_COMMIT = 0
GIT_PUSH = 0
DEPLOYMENT = 0
G6 = NOT_STARTED
