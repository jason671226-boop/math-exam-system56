# Stage 7C-1 Elementary Competition Corpus Foundation

## Profile isolation

`ELEMENTARY_COMPETITION` is a local-first assessment profile for elementary mathematics competitions in G3-G6, with G4-G6 prioritized for the first pilot. It is isolated from `PRIVATE_JH`, general curriculum practice, and secondary-school competitions. Existing G1-G6 Curriculum Master v2.7 Skill/Micro IDs remain the only curriculum foundation; competition topics and thinking skills are metadata layers only.

## Source classification

Sources are classified as `EXPLICIT_COMPETITION`, `COMPETITION_CANDIDATE`, `GENERAL_ADVANCED`, `PRIVATE_JH`, `GENERAL_CURRICULUM`, or `UNKNOWN`. Only explicit sources, or candidates subsequently upgraded with verifiable competition provenance, may enter a pilot. Difficulty alone is never competition evidence.

The repository audit identified two G5/G6 competition-profile candidate files containing 36 rows. They lack verifiable contest provenance and therefore contribute zero usable pilot questions. Eight PRIVATE_JH sources and two general-curriculum files were explicitly excluded. No synthetic questions were generated.

## Taxonomy and quality

The foundation defines 20 competition-topic metadata groups and 13 thinking-skill metadata labels. Neither taxonomy creates or replaces Curriculum Skill/Micro IDs. Existing source-quality gates are retained, with additional fail-closed checks for geometry figures, table layout, sequence layout, and special-symbol loss.

## Readiness and safety

- Sources scanned: 12
- Raw competition candidates: 36
- Unique competition candidates: 35
- Normalized duplicates removed: 1
- Verified usable competition questions: 0
- Pilot target: 100
- Additional verified questions needed: 100
- Corpus status: `CORPUS_INSUFFICIENT`
- API, Gemini, and DeepSeek calls: 0
- Production reads and writes: 0
- Supabase used: no

Foundation readiness means the isolation, taxonomy, inventory, quality gates, and tests exist. It does not mean a real 100-question competition corpus or mapping pilot is ready.
