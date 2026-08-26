# Stage 7B-0 PRIVATE_JH Real Corpus Inventory

This was a read-only inventory of the Stage 7 repository and identifiable local pilot metadata in the authorized G5/G6 workspaces. The G8 workspace was used only to confirm artifact format. No G8 question was counted. No API or database was accessed.

## Sanitized counts

| Classification | Rows found | Unique counted | PRIVATE_JH usable |
|---|---:|---:|---:|
| A. Explicit private-JH entrance | 0 | 0 | 0 |
| B. G5/G6 gifted or advanced candidate | 0 | 0 | 0 |
| C. General curriculum | 36 | 36 | 0 |
| D. Competition | 36 | 35 | 0 |
| E. Unknown source | 0 | 0 | 0 |
| Total inventoried | 72 | 71 | 0 |

Four identifiable batches were found: G5 baseline (18), G5 competition (18), G6 general pilot (18), and G6 competition (18). All have question text in the local source and an answer specification in the corresponding repository asset. One fingerprint is duplicated across the two competition batches.

The baseline/general batches are excluded because their provenance does not identify them as private-JH, entrance, gifted, or advanced material. The competition batches are excluded because Competition must remain separate from PRIVATE_JH. Difficulty alone was not used to reclassify a question.

Across all excluded batches, 44 rows have provisional existing Skill and Micro predictions. These are AI predictions requiring human review, not Ground Truth, and none are counted as usable PRIVATE_JH mappings. Usable topic diversity, existing Skill mappings, and existing Micro mappings are therefore all zero.

## Decision

Unique usable questions: 0. Status: `CORPUS_INSUFFICIENT`. At least 100 additional diverse, legally usable questions with explicit private-JH provenance—or independently reviewed G5/G6 advanced-candidate provenance—are needed before a 100-question pilot can be prepared.

Safety counters: API calls 0; production reads 0; production writes 0; private data committed 0. The detailed manifest remains only under `.local/stage7_private_jh/` and is excluded from Git.
