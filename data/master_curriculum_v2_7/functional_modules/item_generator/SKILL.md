# Item Generator

## Goal
Generate a new item that trains the diagnosed micro-skill, not a cosmetic number swap.

## Mandatory flow
1. Accept canonical diagnosis.
2. Load the exact parent skill + micro-skill only.
3. Read grade/track OUT_OF_SCOPE_RULES.
4. Keep mathematical structure invariant unless requested mode explicitly changes it.
5. Use micro question_type / item_pattern / common_error to select the variation axis.
6. Produce answer, worked solution, skill metadata, difficulty and validation notes.

## Variation modes
- same_structure_new_numbers
- representation_shift
- condition_shift
- error_targeted_distractor
- multi_step_extension
- cross_skill_extension (only when prerequisites are mastered)

## Safety against leakage
Never import a skill from another high-school track merely because the name is similar.
