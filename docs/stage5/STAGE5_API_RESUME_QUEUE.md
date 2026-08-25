# Stage 5 API Resume Queue

Sanitized metadata only. No question content, mapping output, or credentials are included.

| Priority | Target | Strategy | Curriculum | Real source | Real unique | Tuning | HOLDOUT | Checkpoint done | Remaining | HOLDOUT-first | Fallback tuning | Fallback HOLDOUT2 | Best case | Worst case | Optional real | Resume status | Recommended action |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 0 | G7 | HOLDOUT_FIRST | PASS | YES | 18 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 18 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G9 | HOLDOUT_FIRST | PASS | YES | 18 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 18 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G4 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G10_GENERAL | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G3 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G2 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G1 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G11_A | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | COMPLETED | Foundation complete; no validation calls required |
| 0 | G11_B | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | COMPLETED | Foundation complete; no validation calls required |
| 1 | G12_A | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 2 | G12_B | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |

## Totals

- Old minimum validation calls: 136
- Best-case validation calls: 68
- Worst-case validation calls: 204
- Optional real mapping calls: 36
- Total estimated calls: 104
- Estimated savings: 68 (50.0%)
- Recommended order: G12_A, G12_B
