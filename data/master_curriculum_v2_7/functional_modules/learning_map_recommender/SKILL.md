# Learning Map Recommender

## Goal
Answer: what should the learner learn next?

## Inputs
- mastery by canonical skill/micro-skill
- recent evidence
- prerequisite graph
- target course route

## Decision order
1. Repair blocking prerequisite gaps.
2. Stabilize current target if evidence is weak/unstable.
3. Advance to ready successors.
4. Prefer high-leverage prerequisites shared by several weak skills.
5. Avoid recommending out-of-route high-school tracks.

## Output per recommendation
skill_id, reason, prerequisite_status, mastery_gap, expected_gain, priority, evidence.
