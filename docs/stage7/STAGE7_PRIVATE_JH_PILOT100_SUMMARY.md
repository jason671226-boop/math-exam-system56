# Stage 7B-2 PRIVATE_JH Pilot100 Summary

## Boundary and interpretation

- Profile: `PRIVATE_JH`
- Primary provider/model: DeepSeek / `deepseek-v4-flash`
- Independent comparison: Gemini, 20 stratified questions
- Thinking-skill mapping: disabled
- Production reads/writes: 0 / 0
- Provider agreement is a consistency signal, not accuracy or ground truth.
- Human-validated coverage remains 0 pending independent review.

## Sample integrity and distribution

The deterministic stratified sample contains 100 unique, complete, non-synthetic questions from traceable official sources. Seventy corpus questions remain outside this pilot as holdout material.

| Dimension | Distribution |
|---|---:|
| Schools | 2 (50 / 50) |
| Year labels | 6 (12–24 questions each) |
| Recognized topic groups | 15 |
| Unclassified topic metadata | 25 questions |
| Geometry / computation / application / reasoning | 37 / 49 / 6 / 8 |
| Foundation / medium / high sampling hints | 51 / 32 / 17 |

## Provider results

DeepSeek produced 100 canonical completed mappings after 47 bounded correction calls. The latency and token values below describe the 100 canonical results; correction calls are disclosed separately and are not hidden as fallback traffic. Gemini processed only the planned 20-question validation sample.

| Metric | DeepSeek canonical 100 | Gemini validation 20 |
|---|---:|---:|
| Completed / remaining | 100 / 0 | 20 / 0 |
| In scope / out of scope | 89 / 11 | 18 / 2 |
| Invalid | 0 | 1 |
| JSON failures / provider errors | 0 / 0 | 0 / 0 |
| Average latency (ms) | 1,619.78 | 8,470.37 |
| Median latency (ms) | 1,398.97 | 7,520.85 |
| P95 latency (ms) | 1,885.59 | 13,424.49 |
| Input / output / total tokens | 820,313 / 12,083 / 832,396 | 181,628 / 2,748 / 212,273 |
| Actual provider calls | 147 (100 initial + 47 corrections) | 20 |

## Independent-provider agreement

| Comparison | Agreement |
|---|---:|
| Scope | 70% |
| Primary Skill | 60% |
| Primary Micro | 25% |
| Scope + Skill + Micro | 20% |

## Raw mapped coverage

| Metric | Count |
|---|---:|
| In-scope mapped questions | 89 |
| Unique primary Skills | 43 |
| Unique Micros | 68 |
| Unique secondary Skills | 57 |
| Topic groups | 15 |
| Assessment styles | 7 |

## Human review queue

The queue contains 79 unique questions. Reasons overlap and therefore do not sum to the queue size.

| Reason | Count |
|---|---:|
| Invalid validation mapping | 1 |
| Out of scope | 11 |
| Provider disagreement | 16 |
| Low confidence | 9 |
| Cross-unit and high difficulty | 50 |
| Stratified normal-result audit | 15 |

Technical execution passed because all 100 DeepSeek canonical results completed, none remained, and none was invalid. Mapping accuracy and real-question readiness still require human ground truth review.
