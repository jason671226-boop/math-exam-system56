# Stage 7C-1B Elementary Competition Public Corpus

This stage acquires only publicly accessible files linked directly by an official competition site. IMC Taiwan preliminary papers are accepted from `imcct.net`; Math Kangaroo catalog entries that route through a login/platform boundary are recorded and skipped. No paywall, login, or access control is bypassed.

The pipeline stores source PDFs, page/question crops, OCR text, answers, fingerprints, quality queues, and pilot manifests under the ignored `.local/stage7_elementary_competition/` tree. Git receives only pipeline code, deterministic tests, and this sanitized description.

Every usable record requires an approved HTTPS domain, elementary grade scope, complete extraction, a local crop preserving the original visual and mathematical layout, and no source-quality risk. The existing diagram, chart, fraction, expression, contamination, table, sequence, and special-symbol gates fail closed. Competition topics remain profile metadata and do not create Curriculum Skill, Micro Skill, or Human Ground Truth.

Pilot selection is deterministic and diversity-first. It deduplicates presentation-only variations, preserves numerical variants, balances grade/year/source paper, and caps any topic-like cluster at 25 percent. If fewer than 100 eligible unique records remain, the corpus is reported insufficient; synthetic questions are never generated.

## Sanitized acquisition result

- Official pages checked: 4
- Official IMC papers downloaded: 12
- Math Kangaroo catalog entries skipped at the LMS/platform boundary: 2
- Raw extracted records: 271
- Unique records: 169
- Presentation duplicates removed: 102
- Source-quality rejected: 22
- Unique usable records: 147
- Pilot selected: 100
- Years represented: 2024 and 2025
- Rounds represented: preliminary and second round
- Largest single-paper share in the pilot: 15 percent
- Largest deterministic topic-like cluster share: 19 percent
- Mapping/API calls: 0

The 100 selected records are a corpus-readiness result only. No Skill, Micro Skill, Thinking Skill, AI mapping, or Human Ground Truth claim is made in this stage.
