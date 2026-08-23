# Diagnostic Interpreter

## Goal
Turn a wrong-answer observation into a structured diagnosis. Do not merely name the chapter.

## Mandatory flow
1. Resolve route_context before curriculum lookup.
2. Search target pack standard_skills first.
3. Narrow to layer2_micro_skills using evidence: operation, representation, procedure, condition, and common_error.
4. Read OUT_OF_SCOPE_RULES before accepting a diagnosis that might exceed grade scope.
5. Return ranked candidates when evidence is ambiguous.

## Output
- canonical skill_id
- micro_skill_id
- error_type / common_error
- evidence
- confidence 0..1
- prerequisite_gap_candidates
- remediation_focus
- next_action: reteach | variant_practice | prerequisite_review | verify

## Confidence rule
Never return confidence=1 unless the student's work directly distinguishes the micro-skill.
