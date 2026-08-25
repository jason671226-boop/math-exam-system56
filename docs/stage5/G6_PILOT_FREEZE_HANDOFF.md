# G6 Pilot Freeze / Handoff

## Status

**G6 PILOT FOUNDATION: SAFE TO PAUSE**

Foundation completion and real-question coverage are intentionally separate. Foundation completion: **100%**. Real question Skill/Micro coverage: **0% / 0%**.

## Curriculum counts

- Skills: 53
- Micro Skills: 357
- Prerequisite edges: 106
- Publisher units: 43 unique units (127 rows)
- Integrity: PASS

## Pilot architecture

The local-only runner performs environment and curriculum audit, fingerprint inventory, complete zero-safe coverage matrices, cross-unit synthetic preparation, resumable mapping checkpoints, validation, quality audit, G8 regression, and sanitized handoff generation. The required model is `gemini-3.6-flash`. G6 scope decisions use only the G6 Curriculum Master and G6 `OUT_OF_SCOPE_RULES.md`.

## Real local question inventory

- Source status: AVAILABLE
- Unique local diagnostic questions: 36
- Provisional local mappings: 36; all remain in a human-review queue.
- Provisional distinct Skills/Micros: 14 / 16.
- Validated Stage 5 mappings counted as formal coverage: 0.
- Real Skill coverage: 0.0%
- Real Micro coverage: 0.0%

## Synthetic and HOLDOUT validation

Two separately generated local-only sets cover 10 curriculum Skills across distinct main units, three in-scope questions per Skill plus explicit below-G6 and above-G6 scope cases. Synthetic items never enter item_bank or real coverage.

- HOLDOUT questions: 34
- Scope accuracy: 100.0%
- Exact Skill accuracy: 100.0%
- Exact Micro accuracy: 100.0%
- Invalid: 0
- Known mismatches: 0; details remain local only.
- Known ambiguity: generic Micro Skill types can overlap semantically; mismatches must be reviewed rather than changing expected labels post hoc.

## Safety and regression

- Production reads: 0
- Production writes: 0
- Secrets exposed: NO
- Raw/local/synthetic question data committed by this foundation: NO
- G8 regression: PASS

## Unfinished work

None for the Pilot Foundation gate.

## First next action

Human-review the 36 provisional local mappings in the `.local` review queue; only approved mappings may begin validated real coverage without Production access.
