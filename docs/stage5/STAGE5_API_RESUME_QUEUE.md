# Stage 5 API Resume Queue

Sanitized metadata only. No question content, mapping output, or credentials are included.

| Priority | Target | Strategy | Curriculum | Real source | Real unique | Tuning | HOLDOUT | Checkpoint done | Remaining | HOLDOUT-first | Fallback tuning | Fallback HOLDOUT2 | Best case | Worst case | Optional real | Resume status | Recommended action |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 0 | G7 | HOLDOUT_FIRST | PASS | YES | 18 | 34 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 18 | COMPLETED | Foundation complete; no validation calls required |
| 1 | G9 | HOLDOUT_FIRST | PASS | YES | 18 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 18 | READY | Start bounded API validation when quota is available |
| 2 | G4 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 3 | G10_GENERAL | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 4 | G3 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 5 | G2 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 6 | G1 | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 7 | G11_A | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 8 | G11_B | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 9 | G12_A | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |
| 10 | G12_B | HOLDOUT_FIRST | PASS | NO | 0 | 34 | 34 | 0 | 34 | 34 | 34 | 34 | 34 | 102 | 0 | READY | Start bounded API validation when quota is available |

## Totals

- Old minimum validation calls: 680
- Best-case validation calls: 340
- Worst-case validation calls: 1020
- Optional real mapping calls: 36
- Total estimated calls: 376
- Estimated savings: 340 (50.0%)
- Recommended order: G9, G4, G10_GENERAL, G3, G2, G1, G11_A, G11_B, G12_A, G12_B
