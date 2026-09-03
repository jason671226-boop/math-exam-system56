# QB2-F3 G5 Main App Integration Hotfix Release Authorization

Production adapter and app wiring were rechecked after the metadata backfill. `services/question_bank/production_item_bank.py` now selects native `difficulty`, `question_type`, and `solution` fields from `public.item_bank`; the G5 custom-exam branch in `app.py` uses this adapter and does not call AI when the Production pool is sufficient.

Read-only Production evidence: 1,014 QB2 records, all grade 5, unique IDs, complete difficulty/type/solution metadata, and valid canonical knowledge tags. Difficulty distribution: BASIC 353, STANDARD 324, ADVANCED 195, CHALLENGE 142. Question types: CALCULATION 923, FILL 29, WORD_PROBLEM 32, GEOMETRY 25, CHOICE 4, MULTI_STEP 1.

Local verification: app and adapter compile, adapter regression and Phase 3H tests pass, Streamlit HTTP smoke returns 200. A ten-record Production selection preview is available with complete question/answer/solution metadata and no AI calls or writes. Legacy CSV/fixture paths are not used by the G5 branch.

Release authorization was subsequently granted by the user. The release scope is limited to the local G5 retrieval adapter, custom-exam wiring, regression test, and this evidence update; no Production data mutation, question import, student/learning/wallet write, or deployment was performed.
