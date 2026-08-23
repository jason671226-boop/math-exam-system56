---
name: mathai-tw-math-master-curriculum
version: 2.7
description: Production-ready MathAI Taiwan G1-G12 curriculum runtime: canonical skills, micro-skills, track routing, prerequisites, scope guardrails and functional-module wiring.
---

# MathAI Master Curriculum Skill v2.7

## Release gate
G1-G12 GLOBAL QA: PASS

## Coverage
- released curriculum packs: 17
- canonical standard skills: 977
- layer-2 micro-skills: 6056
- official-code coverage: 100%
- broken prerequisite refs: 0
- broken successor refs: 0
- unresolved future refs: 0
- duplicate canonical IDs: 0
- duplicate same-pack skill names: 0

## Runtime architecture
ONE Master Skill
+ deterministic route resolver
+ one target curriculum pack
+ referenced prerequisite nodes
+ one requested functional module.

## Core functional modules
1. diagnostic_interpreter
2. item_generator
3. learning_map_recommender
4. assessment_blueprint_builder

## Routing
PREHIGH G1-G9: grade only.
GENERAL G10: common.
GENERAL G11: A or B required.
GENERAL G12: 甲 or 乙 required.
TECHNICAL G10: A/B/C required.

Do not infer or mix high-school tracks from similar skill names.

## Source of truth
Curriculum packs are authoritative for scope and canonical IDs.
AI interprets evidence and generates content; it does not invent curriculum structure.

## Required generation rule
Read OUT_OF_SCOPE_RULES.md before generating any question.

## Required diagnosis rule
If evidence cannot distinguish micro-skills, return ranked candidates and confidence rather than false certainty.
