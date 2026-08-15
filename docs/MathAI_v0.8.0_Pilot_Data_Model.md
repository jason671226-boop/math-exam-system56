# MathAI v0.8.0 Pilot Data Model — Phase 1.1

## 1. Purpose

This Phase 1.1 establishes a testable foundation for a G6 private-school entrance Pilot without connecting new UI or touching production Supabase. The central design separates three concerns:

- **Knowledge Point**: what mathematical content the student understands.
- **Thinking Skill**: what reasoning / representation tool the student can use when facing an unfamiliar problem.
- **Ability Tag**: a cross-cutting observed tendency such as number sense, calculation stability, calculation efficiency, or spatial sense. Ability tags are not curriculum domains and should not replace Thinking Skills.

Mastery is updated from evidence produced later by diagnostics, practice, teacher feedback, and integrated exams.

## 2. Knowledge IDs and grade meaning

Knowledge IDs are deliberately neutral. They do **not** encode publisher, private-school, gifted, competition, or exam identity.

Examples:

- `G6-K001`
- `G6-K104`
- `G6-K204`

The same Knowledge Point can later be referenced by different publisher mappings or school-exam profiles.

### Grade semantics

The `grade` stored on a Knowledge Point means the **source / placement grade of that mathematical content**, not the current grade of the student being assessed.

For example, a Grade 6 student preparing for a private-school entrance exam may still receive evidence against G5 Knowledge Points when a prerequisite weakness is detected. A student's current grade belongs to the student/profile layer, while a Knowledge Point's grade belongs to the curriculum-content layer.

The Pilot JSON contains three representative content domains:

1. 數與運算
2. 數量關係與應用問題
3. 幾何與圖像推理

Cross-cutting observations such as `數感` and `空間感` are separated into `ability_tags` instead of being merged into the content-domain name.

This dataset is an architecture-validation skeleton, **not** a verified official curriculum map and **not** a claim about any private school's weighting. Official curriculum codes are intentionally blank until the curriculum master table is verified.

### Diagnostic granularity note

The current Pilot nodes are intentionally coarse. Before large-scale diagnostic use, broad nodes such as fraction operations should be decomposed into finer mastery targets (for example equivalent fractions, reduction, common denominators, fraction addition/subtraction, multiplication, and division). Parent/unit nodes may aggregate the child mastery states.

## 3. Thinking Skill Map

Thinking Skill IDs are independent from Knowledge IDs. Phase 1.1 groups the initial skills into six families:

1. **理解與讀題** — `TS-READ`, `TS-DEFINE`
2. **表徵轉換** — `TS-DRAW`, `TS-TABLE`
3. **關係與結構** — `TS-DIFF`, `TS-UNIT`, `TS-PATTERN`
4. **解題策略** — `TS-ASSUME`, `TS-BACKWARD`, `TS-ENUM`, `TS-CASE`, `TS-LOGIC`
5. **計算與簡化** — `TS-SIMPLIFY`, `TS-EQUIV`
6. **驗證與反思** — `TS-ESTIMATE`, `TS-CHECK`

Phase 1.1 adds three important skills:

- `TS-EQUIV` 等價轉換
- `TS-LOGIC` 條件推理
- `TS-CHECK` 合理性檢核

Grade applicability is stored structurally as `min_grade` and `max_grade`; `G5-G9` is only a possible display label, not the database representation.

## 4. Primary vs Supporting Thinking Skills

A question may link to multiple Knowledge Points and multiple Thinking Skills, but MathAI should avoid marking every incidental skill as equally diagnostic.

Question-level Thinking Skill mappings therefore distinguish:

- **Primary Skill**: what the question mainly assesses. Usually 1–2 skills.
- **Supporting Skill**: a tool that may be used during the solution but should not receive the same diagnostic weight. Usually 0–3 skills.

Example — chicken/rabbit problem:

- Primary: `TS-ASSUME` 假設法, `TS-DIFF` 差量比較
- Supporting: `TS-READ` 語意拆解, `TS-DRAW` 圖像轉換, `TS-UNIT` 單位量思考

This prevents a single wrong answer from incorrectly lowering five or six independent skill scores at full weight.

Core links should be represented by junction tables instead of storing all relationships only in JSON arrays.

## 5. Knowledge vs ability vs skill

MathAI should keep the following distinction explicit:

- **Knowledge** — fraction division, ratio, area relationships, angle properties.
- **Thinking Skill** — representation, assumption, backward reasoning, equivalent transformation, answer checking.
- **Ability Tag** — number sense, calculation stability, calculation efficiency, spatial sense.

A Knowledge Point's `domain` should describe mathematical content. Do not use labels such as `數與計算／數感` as a single domain when `數感` is a cross-cutting ability signal.

## 6. Student identity direction

The existing v0.7.x app primarily uses normalized email as the member key. The new learning model should move toward a stable UUID:

`legacy email -> learning_students.id (UUID) -> mastery / diagnostic / practice / feedback / exam`

`legacy_email` remains only for compatibility lookup. Phase 1.1 does **not** modify the current login flow.

### Important identity / RLS constraint

The current app implements its own email OTP flow rather than Supabase Auth. Therefore `auth.uid()` is not currently a reliable identity for browser-side RLS policies. The migration proposal enables RLS on student-specific tables but intentionally adds no permissive anonymous policies. Before staging execution, MathAI must choose a safe access path, such as Supabase Auth or validated SECURITY DEFINER RPCs / trusted backend access.

## 7. Mastery service

`app/services/mastery_service.py` is intentionally independent from Streamlit and Supabase.

Each `MasteryEvidence` contains:

- correctness
- difficulty: `basic | standard | advanced`
- hints used
- attempts
- optional evidence weight
- source type

The service maintains:

- `status`
- `score_numeric` 0–100
- `confidence` 0–1
- `evidence_count`
- last assessment time
- next review time

Statuses:

- `unassessed` 尚未評估
- `needs_work` 需要加強
- `learning` 學習中
- `basic` 基本掌握
- `proficient` 熟練

The initial algorithm is intentionally simple and explainable. Difficulty changes evidence weight; hints and repeated attempts reduce the quality of a correct response. High accuracy on only easy questions remains `basic`; `proficient` requires repeated evidence plus success on standard or advanced items.

This module is a replaceable first version, not a final psychometric model.

## 8. Evidence model

Future flows should emit evidence rather than directly changing UI labels:

`existing mastery + new evidence -> mastery service -> new mastery state`

Evidence sources reserved in the proposal:

- diagnostic
- practice
- teacher_feedback
- integrated_exam
- system

This allows later additions such as retention decay, delayed review, speed, transformed questions, and cross-unit performance without rewriting the UI.

## 9. Database proposal highlights

The proposal creates new tables only and avoids production mutations. Main groups:

- `learning_students`
- `knowledge_points` with `ability_tags`
- `thinking_skills` with structural `min_grade` / `max_grade`
- `question_knowledge_links`
- `question_thinking_links` with `skill_role = primary | supporting`
- `student_mastery_states`
- `mastery_evidence_events`
- teacher-feedback skeleton + junction tables
- target-school profile skeleton

There is deliberately **no** `parent_report_snapshots` table in Phase 1.1. The first parent report should aggregate live mastery / diagnostic / practice / feedback / exam data. Snapshots can be added later when historical monthly or PDF reports are actually needed.

## 10. What Phase 1.1 does not do

- No change to `app/app.py`
- No production Supabase execution
- No member / wallet / referral changes
- No new diagnostic UI
- No teacher-login system
- No parent-report UI
- No school-exam claims or real school weights
- No complete G5/G6 curriculum import
- No Gemini workflow changes
- No full Calculation Technique Map yet; that can become a dedicated catalog after the Pilot validates the need

## 11. Phase 2 gate

Before Phase 2 connects UI or cloud persistence, verify:

1. Pilot Knowledge / Thinking / Ability-tag content.
2. Finer Knowledge Point granularity for diagnostic use.
3. Student UUID mapping strategy.
4. Staging Supabase access-control design.
5. Mastery thresholds with real student examples.
6. Which 15–25 diagnostic seed items should be authored and legally sourced.
7. Primary/supporting skill weights used when converting question results into mastery evidence.
