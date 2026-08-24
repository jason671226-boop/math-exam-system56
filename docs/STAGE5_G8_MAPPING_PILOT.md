# MathAI Stage 5B-2A — Local G8 Mapping Pilot

## Goal
Map a deterministic 200-question G8 pilot sample from the existing production `item_bank` to Curriculum Master v2.7 Skill / Micro Skill IDs without writing anything back to production.

## Safety boundary
- Production Supabase project is hard-pinned to `igttuijrtwbtefhyeokp`.
- Live database access in this pilot is SELECT-only.
- The script contains no insert/update/delete/upsert/RPC/DDL path.
- Generated snapshots, mappings, and review files stay under `.local/stage5_g8_mapping_pilot/` and are gitignored.
- `main` and the production Streamlit app are not changed by running the pilot branch.

## Pipeline
1. `prepare` — read G8 item rows + G8 Curriculum v2.7 rows, normalize/fingerprint, deduplicate, stratify, select 200 unique questions, and generate candidate packets.
2. `map` — locally call Gemini using only candidate Skill/Micro Skill IDs. Results are checkpointed in JSONL so the run can resume.
3. `validate` — reject unknown Skill IDs, unknown Micro Skill IDs, parent mismatches, and invalid confidence values; produce a human review CSV.
4. Human review — mark sampled mappings correct/incorrect before any production import is designed.

## Commands
```bash
python scripts/stage5_g8_mapping_pilot.py prepare --sample-size 200
python scripts/stage5_g8_mapping_pilot.py map --limit 20
python scripts/stage5_g8_mapping_pilot.py validate
```

After the 20-question cost-control smoke passes, rerun `map` without `--limit` to resume and finish the 200-question sample.

## Secrets
The script reads environment variables or local `.streamlit/secrets.toml`:
- `SUPABASE_URL`
- `SUPABASE_KEY` (or anon/service-role aliases)
- `GEMINI_API_KEY` or `GEMINI_KEY`

Secrets are never printed or written to pilot artifacts.

## Pilot acceptance gate
Before Stage 5B-2A can be called PASS:
- prepare manifest matches expected G8 scale and has `production_writes = 0`;
- 200 deterministic unique questions are produced;
- every mapping passes Skill/Micro Skill FK and parent validation;
- human review accuracy target is agreed and met;
- no production table is modified.
