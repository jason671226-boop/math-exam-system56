# Stage 6C G8 Real-Question DeepSeek Pilot Summary

- Source: 200 local real questions; 200 unique fingerprints; synthetic 0; Gemini baseline COMPLETE.
- DeepSeek: completed 200, remaining 0, in-scope 189, out-of-scope 11, invalid 5, JSON failures 0, provider errors 0.
- Latency: average 2083.71 ms; median 1982.66 ms; P95 2474.39 ms.
- Tokens: input 971511; output 35163; total 1006674.
- Raw mapped coverage: 4/102 Skills (3.92%); 4/660 Micros (0.61%).
- Human-validated coverage: 0/102 Skills (0.0%); 0/660 Micros (0.0%).
- Provider agreement: scope 99.5%; skill 89.0%; micro 88.5%; complete 86.0%; disagreements 28.
- Human review queue: total 56; provider disagreements 28; out-of-scope 11; suspicious 1; stratified agreement audit 20.
- Recommendation: keep DeepSeek as the Stage 6 primary mapper, require human review before any database write, and do not use Gemini agreement as ground truth.
- Safety: production reads 0; production writes 0; Supabase not used; secrets exposed 0.
