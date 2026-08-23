# MathAI Runtime Load Policy v2.7

1. Resolve education system and track first.
2. Load SKILL.md + runtime router.
3. Load exactly one target curriculum pack.
4. Resolve only prerequisite/successor IDs actually referenced.
5. Load functional module requested by the action.
6. Read target pack OUT_OF_SCOPE_RULES.md before diagnosis acceptance, item generation or assessment assembly.
7. Never load all G1-G12, all G11/G12 routes, or GENERAL+TECHNICAL simultaneously by default.

## Functional actions
- diagnose_wrong_answer -> diagnostic_interpreter
- generate_variant -> item_generator
- recommend_next -> learning_map_recommender
- build_assessment -> assessment_blueprint_builder

## Learning map
Start from SKILL_INDEX_ALL_RELEASED.csv. Expand detailed micro-skills only for visible/current nodes.
