# Stage 7 Legacy Inventory

Inventory scope was the repository only. No credentials, external databases, production, staging, or other workspaces were read. Counts below are sanitized metadata; no prompt, answer, solution, student, review, or raw model content is reproduced.

| Asset | Type | Rows / IDs | Existing mapping | Disposition |
|---|---|---:|---|---|
| `data/diagnostic_questions_g5_competition_core_v1.json` | legacy competition diagnostic | 18 question IDs | legacy knowledge/thinking IDs present | REVIEW; file has legacy encoding/JSON integrity concerns |
| `data/diagnostic_questions_g6_competition_core_v1.json` | legacy competition diagnostic | 18 question IDs | legacy knowledge/thinking IDs present | REVIEW; file has legacy encoding/JSON integrity concerns |
| `data/competition_knowledge_weights_v1.json` | legacy competition weights | 2 grade blocks | knowledge IDs present | REVIEW; do not treat as Stage 7 validation |
| `data/thinking_skills_v1.json` | legacy thinking taxonomy | 16 intended entries | independent IDs present | Retained; legacy encoding/JSON integrity concern |
| `data/thinking_skills_gold.json` | legacy expanded taxonomy | 26 intended entries | independent IDs present | Retained; not silently migrated |
| `catalog/competition_loader.py` | loader | n/a | validates legacy weights | Retain; no data migration |
| `catalog/thinking_loader.py` | loader | n/a | validates legacy taxonomy | Retain; Stage 7 uses explicit CSV |
| `services/curriculum_catalog.py` | legacy UI catalog generator | dynamic `G6-COMP-*` IDs | separate generated tree | REVIEW; excluded from Stage 7 curriculum IDs |
| `learning_map.py` | legacy private/competition presentation hierarchy | metadata hierarchy | not master Skill/Micro mapping | Inventory only |

No repository asset matching private-school terminology was found as a validated private-question corpus. UI labels such as `報考私中` are presentation metadata, not validated legacy mappings.

Legacy question IDs total: 36. Human-validated Stage 7 mappings: 0. All legacy mappings remain UNMAPPED/REVIEW. The migration CSV is deliberately blank and cannot imply Ground Truth.
