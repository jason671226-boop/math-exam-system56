# Stage 7C ELMC Text-PDF Import

This local-first pipeline imports four user-provided, OCR-derived ELMC text PDFs without reading Downloads, ZIP archives, network sources, Supabase, or Production.

The parser separates editions, explicit competition sections, questions, and solutions. It preserves the IMC corpus and adds ELMC as a distinct `source_family`. ELMC topics and thinking skills use the existing Stage 7C taxonomies; Curriculum Master v2.7 remains the only source of Foundation Skill and Micro IDs.

OCR-derived text is fail-closed. Missing diagrams/charts, fraction or expression loss, lost table/sequence layout, special-symbol loss, and cross-document contamination enter a local quality queue and cannot become mapping or Human Ground Truth. Provider agreement is quality evidence only; every Human Ground Truth decision remains teacher-approved and local-only.

All PDFs, question/answer/solution text, provider raw results, and review files remain under `.local/stage7_elementary_competition/` and are excluded from Git. Production reads and writes are zero.

## Sanitized run audit

- Sources: 4 editions, 63 pages; sections identified: individual, team, and thinking competition.
- Extraction: 103 raw/unique records; 24 OCR/source-quality review records; 79 records eligible for mapping.
- Provider execution: 79 DeepSeek primary and 79 Gemini verifier results. Agreement is review evidence, never Ground Truth.
- Corpus coexistence: 182 existing IMC records preserved and 79 ELMC usable records added; combined local corpus contains 261 records.
- Human review: 102 unique records (quality risks plus provider validation/disagreement/audit categories). No record is marked Human Validated.
- Safety: Production reads/writes 0; all source text and mapping/review artifacts remain local-only.
