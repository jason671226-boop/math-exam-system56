# G6 Pilot Freeze / Handoff

## Status

**G6 PILOT FOUNDATION: BLOCKED**

Foundation completion and real-question coverage are intentionally separate. Foundation completion: **70%**. Real question Skill/Micro coverage: **0% / 0%**.

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
- Validated Stage 5 mappings: not available; none are counted as coverage.
- Real Skill coverage: 0.0%
- Real Micro coverage: 0.0%

## Synthetic and HOLDOUT validation

Two separately generated local-only sets cover 10 curriculum Skills across distinct main units, three in-scope questions per Skill plus explicit below-G6 and above-G6 scope cases. Synthetic items never enter item_bank or real coverage.

- HOLDOUT questions: 0
- Scope accuracy: NOT_RUN%
- Exact Skill accuracy: NOT_RUN%
- Exact Micro accuracy: NOT_RUN%
- Invalid: NOT_RUN
- Known mismatches: NOT_RUN; details remain local only.
- Known ambiguity: generic Micro Skill types can overlap semantically; mismatches must be reviewed rather than changing expected labels post hoc.

## Safety and regression

- Production reads: 0
- Production writes: 0
- Secrets exposed: NO
- Raw/local/synthetic question data committed by this foundation: NO
- G8 regression: PASS

## Unfinished work

Complete the Gemini HOLDOUT run and/or resolve failing quality or G8 regression gates.

## First next action

Obtain an approved local G6 question export with provenance, then map and human-review it locally to begin real coverage without Production access.
