# Assessment Blueprint Builder

## Goal
Create a balanced self-test or worksheet specification before item generation.

## Inputs
route_context, target skills, question count, difficulty mix, diagnostic intent.

## Rules
- Select canonical skills before generating questions.
- Allocate questions across micro-skills, not chapter titles only.
- Include prerequisite probes when diagnosis confidence is low.
- Respect OUT_OF_SCOPE_RULES.
- Do not mix GENERAL and TECHNICAL packs.
- For G11/G12 GENERAL, do not mix A/B or 甲/乙 unless explicitly building a comparison assessment.
