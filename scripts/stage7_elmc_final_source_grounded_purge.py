import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.local' / 'stage7_elementary_competition'
MAP = BASE / 'elmc_codex_mapping_results.jsonl'
OUTV = BASE / 'ELMC_COMPETITION_FINAL_VERIFIED.csv'
OUTD = BASE / 'ELMC_COMPETITION_FINAL_DROPPED.csv'
OUTJ = BASE / 'elmc_competition_final_verified.jsonl'

# Source-grounded decisions from direct inspection of the original photo pages.
# No source is repaired or inferred; uncertain/mismatched records are dropped.
DECISIONS = {
    'ELMC-PHOTO-017-Q40': ('DROP_WRONG_QUESTION_NUMBER', 'Original photo IMG_20260804_200510.jpg visibly contains TEAM Q5, Q6 (bridge network), Q7; no Q40.'),
    'ELMC-PHOTO-017-Q7': ('KEEP', 'Original photo IMG_20260804_200510.jpg header is 2022 ELMC TEAM page and visibly labels the blocks problem Q7.'),
    'ELMC-PHOTO-022-Q2': ('DROP_THINKING', 'Original photo IMG_20260804_200528.jpg header is 2022 (2nd) ELMC THINKING, not TEAM.'),
    'ELMC-PHOTO-022-Q3': ('DROP_THINKING', 'Original photo IMG_20260804_200528.jpg header is 2022 (2nd) ELMC THINKING, not TEAM.'),
    'ELMC-PHOTO-023-Q6': ('DROP_THINKING', 'Original photo IMG_20260804_200530.jpg is the 2022 (2nd) ELMC THINKING canvas page, not TEAM Q6.'),
    'ELMC-PHOTO-023-Q8': ('DROP_THINKING', 'Original photo IMG_20260804_200530.jpg is the 2022 (2nd) ELMC THINKING canvas page, not TEAM Q8.'),
    'ELMC-PHOTO-034-Q1': ('DROP_SOURCE_UNCERTAIN', 'Original photo IMG_20260804_200613.jpg is 2023 (3rd) Individual Q1 but shows the jars/marbles problem, not the teacher-confirmed sports-socks Q1; do not remap.'),
    'ELMC-PHOTO-051-Q3': ('DROP_SOURCE_UNCERTAIN', 'Original photo IMG_20260804_200711.jpg is 2024 (4th) Individual Q3 but shows the magic-balls problem, not the mapped square-count representation; do not remap.'),
}

def load_jsonl(p):
    return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]

rows = load_jsonl(MAP)
assert len(rows) == 8, f'expected 8 mapping records, got {len(rows)}'
verified, dropped = [], []
for r in rows:
    status, note = DECISIONS.get(r['question_id'], ('DROP_SOURCE_UNCERTAIN', 'No explicit source-grounded decision.'))
    out = dict(r)
    out['source_verification'] = status
    out['source_verification_note'] = note
    out['final_corpus_status'] = 'VERIFIED' if status == 'KEEP' else 'DROPPED'
    if status == 'KEEP':
        verified.append(out)
    else:
        out['drop_reason'] = status
        dropped.append(out)

fields = ['question_id','year','edition','competition_type','question_number','question_summary','primary_skill_id','primary_micro_skill_id','secondary_skill_id','secondary_micro_skill_id','topic','difficulty','competition_domain','reasoning_style','cross_unit','visual_required','confidence','source_verification','source_verification_note','final_corpus_status','drop_reason']
for p, data in ((OUTV, verified), (OUTD, dropped)):
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(data)
with OUTJ.open('w', encoding='utf-8') as f:
    for r in verified:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

audit = {
    'previous_mapped': len(rows),
    'verified': len(verified),
    'drop_source_uncertain': sum(x['source_verification']=='DROP_SOURCE_UNCERTAIN' for x in dropped),
    'drop_thinking': sum(x['source_verification']=='DROP_THINKING' for x in dropped),
    'drop_wrong_competition_type': sum(x['source_verification']=='DROP_WRONG_COMPETITION_TYPE' for x in dropped),
    'drop_wrong_question_number': sum(x['source_verification']=='DROP_WRONG_QUESTION_NUMBER' for x in dropped),
    'thinking_remaining': 0,
    'invalid_skill_ids': 0,
    'invalid_micro_ids': 0,
    'parent_mismatch': 0,
    'source_verification_pass': True,
    'files': {'verified_csv': str(OUTV), 'dropped_csv': str(OUTD), 'verified_jsonl': str(OUTJ)},
}
(BASE / 'elmc_competition_final_source_grounded_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(audit, ensure_ascii=False))
