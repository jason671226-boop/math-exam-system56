# MathAI v0.8 Phase 2A Diagnostic Model

## Scope

Phase 2A adds a pure-Python diagnostic foundation for the first five G6 private-school Pilot items. It does not add Streamlit UI, execute Supabase migrations, call AI APIs, or modify member / wallet / login flows.

## Data flow

Question → Answer Evaluation → Error Candidates → Targeted Mastery Evidence

A single wrong answer is treated as evidence, not a permanent student label.

## Question model

Each diagnostic question stores:

- stable `question_id`
- target profile and section
- answer specification
- Knowledge Point references
- Primary Thinking Skill references
- Supporting Thinking Skill references
- difficulty (`level` plus mastery-compatible `mastery_band`)
- expected time and hint policy
- standard solution
- candidate Error Type references

## Answer types in Phase 2A

- `numeric`
- `ordered_list`
- `ratio`
- `multipart`

Ratio answers are normalized, so an equivalent ratio such as `32:40` is accepted for `4:5`.

Multipart items keep part-level results. For DIAG-G6-005, area and perimeter are evaluated independently.

## Error Types

The first Error Type catalog contains 15 reusable errors grouped into:

- knowledge
- reading
- representation
- strategy
- execution
- verification

Phase 2A only emits deterministic `error_candidates`. It does not use generative AI to guess student misconceptions.

Implemented high-confidence Pilot rules:

- DIAG-G6-004: preserving the old ratio `3:5` after adding red balls → `ERR-RATIO-003`
- DIAG-G6-005: area `87` with perimeter `28` → `ERR-GEO-002`

Unknown wrong answers return no error candidate.

## Mastery Evidence policy

The existing `MasteryEvidence` and mastery algorithm remain unchanged.

Diagnostic results are adapted conservatively:

- Knowledge evidence weight: `1.00`
- Primary Thinking Skill evidence weight: `0.60`
- Supporting Thinking Skill positive evidence weight: `0.25`
- Supporting Thinking Skill negative evidence: **not created**

For multipart questions, evidence is split by part rather than converting partial credit into a boolean. With two parts, each per-part base evidence receives half the normal weight.

Existing hint / retry quality penalties remain centralized in `mastery_service.py`.

## Pilot mappings

| Question | Knowledge | Primary | Supporting |
|---|---|---|---|
| DIAG-G6-001 | G6-K001 | TS-DEFINE | TS-CHECK |
| DIAG-G6-002 | G6-K003 | TS-DEFINE | TS-EQUIV |
| DIAG-G6-003 | G6-K002 | TS-EQUIV | TS-ESTIMATE |
| DIAG-G6-004 | G6-K101 | TS-UNIT | TS-EQUIV, TS-READ |
| DIAG-G6-005 | G6-K201 | TS-DEFINE | TS-DRAW, TS-CHECK |

## Explicit non-goals

Phase 2A does not:

- create the final 18-item diagnostic exam
- create parent reports
- create student strategy labels
- persist diagnostic sessions to Supabase
- update production mastery rows
- infer errors with AI
- modify `app.py` or `learning_map.py`

Those integrations belong to later phases after local validation.
