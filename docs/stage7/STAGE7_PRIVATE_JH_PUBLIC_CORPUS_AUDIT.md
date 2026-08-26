# Stage 7B-1 PRIVATE_JH Public Corpus Audit

Stage 7B-1 acquired only publicly accessible exams linked from official school pages. No login, paywall, commercial material, model API, or database was used. PDFs, extracted text, answers, fingerprints, and the detailed source registry remain under `.local/stage7_private_jh/` and are not committed.

## Official sources

| School | Years | Official exam page | PDFs downloaded | Complete questions retained | Exams with parsed answers |
|---|---|---|---:|---:|---:|
| 永年高級中學 | 110-113 | https://www.ynhs.ylc.edu.tw/news/2/96 | 4 | 117 | 3 |
| 明達高級中學 | 112-114 | https://www.lmsh.tn.edu.tw/ischool/publish_page/53/?cid=660 | 4 | 53 | 0 |

The official pages of 新民高級中學 and 普門中學 were also checked and confirmed to publish relevant historical exams, but their documents were not needed for this acquisition batch. The eight acquired documents all passed the official-domain and public-exam-page checks.

## Corpus counts

| Measure | Count |
|---|---:|
| PDFs downloaded | 8 |
| Declared questions across documents | 220 |
| Complete math questions retained | 170 |
| Unique usable fingerprints | 170 |
| Duplicate fingerprints removed | 0 |
| Incomplete or unparsed questions removed | 50 |
| Schools represented | 2 |
| Distinct year labels represented | 6 |

## Coarse topic counts

| Topic | Count | Topic | Count |
|---|---:|---|---:|
| 整數 | 6 | 因數倍數 | 11 |
| 分數 | 4 | 小數 | 14 |
| 百分率 | 5 | 比與比例 | 0 |
| 速率 | 2 | 時間 | 12 |
| 平均 | 5 | 單位換算 | 41 |
| 面積 | 15 | 體積 | 13 |
| 幾何 | 21 | 規律 | 2 |
| 邏輯 | 9 | 多步驟應用 | 9 |

Topic counts are deterministic keyword-based coarse labels and may overlap. They are not AI mapping or Ground Truth. Fifteen of the sixteen requested topic groups are represented; explicit ratio/proportion coverage remains a future corpus-diversity gap.

## Decision and safety

The 170 unique complete questions exceed the 100-question threshold: `CORPUS_READY`. This establishes source and corpus readiness only; Stage 7B mapping has not started.

Safety counters: Gemini calls 0; DeepSeek calls 0; production reads 0; production writes 0; private data committed 0.
