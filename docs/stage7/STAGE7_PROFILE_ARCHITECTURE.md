# Stage 7 Profile Architecture

Stage 7 separates assessment intent from curriculum identity. `STANDARD`, `PRIVATE_JH`, and `COMPETITION` are closed enum values. They reuse the master curriculum packs; no Stage 7 Skill or Micro tree is created.

`PRIVATE_JH_V1` permits G5/G6 curriculum IDs, secondary Skills, cross-unit work, and the eight assessment-style tags. `COMPETITION_V1` permits G4–G6 curriculum IDs plus an independent Thinking Skill layer. A mapping has one primary Skill, one primary Micro, zero or more secondary Skills, and—only for Competition—one primary and zero or more secondary Thinking Skills.

Validation is fail closed: the primary Micro must be parented by the primary Skill; all secondary Skills and Thinking Skills must exist; unknown profile and curriculum IDs are rejected. Difficulty alone does not select Competition. An in-scope item receives its requested profile; only content outside a reasonable configured elementary curriculum foundation receives `OUT_OF_SCOPE_PROFILE`.

Omitting `profile_type` normalizes to `STANDARD`, preserving the existing generic mapping path. Checkpoint identity is `profile_type:fingerprint`, preventing cross-profile resume collisions. Mapping output also requires provider, model, status, latency, and token usage. Provider fallback is never automatic.

Schemas: `schemas/stage7_profile.schema.json` and `schemas/stage7_mapping_result.schema.json`.

Safety boundary: local-only; no database access, migration, API mapping, production read, or production write is part of Stage 7A.
