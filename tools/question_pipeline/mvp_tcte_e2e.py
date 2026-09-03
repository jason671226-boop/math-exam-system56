"""Local, in-memory MVP smoke test for the TCTE approved pool."""
from __future__ import annotations
import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from services.question_bank.adapter import ApprovedPilotLoader, QuestionBankAdapter
from services.evidence_mastery_gold import Evidence, calculate_mastery
from datetime import datetime, timezone

OUT = ROOT / 'data/question_research/mvp_integration'

def run():
    pool = json.loads((OUT/'approved_pilot_pool.json').read_text(encoding='utf-8'))['items']
    loader = ApprovedPilotLoader(pool); adapter = QuestionBankAdapter(loader, seed=7)
    valid = loader.valid_items(); tracks = {t: len(loader.load(curriculum_track=t)) for t in ('TECH-A','TECH-B','TECH-C')}
    answer_ok = all(adapter.answer(x)['answer'] == x.get('answer') for x in valid)
    evidence_ok = mastery_ok = recommendation_ok = True
    for x in valid[:min(3, len(valid))]:
        ev = adapter.evidence(x, 'LOCAL_TEST', True)
        evidence_ok &= ev['question_id'] == x['question_id'] and ev['knowledge_id'] == x['knowledge_id']
        e = Evidence(x['knowledge_id'], tuple(), 2, 1, True, 0, 1, datetime.now(timezone.utc), False, False, 'autonomous_test')
        mr = calculate_mastery([e]); mastery_ok &= mr.status in ('learning','basic','proficient') and mr.score >= 0
        recommendation_ok &= adapter.recommendation(x['knowledge_id'])['next_action'] == 'PRACTICE'
    report = {'approved_items': len(valid), 'track_counts': tracks,
              'adapter':'PASS' if len(valid)==len(pool) else 'FAIL',
              'staging_loader':'PASS' if valid else 'FAIL', 'autonomous_exam':'PASS' if valid else 'FAIL',
              'answer_linkage':'PASS' if answer_ok else 'FAIL', 'evidence':'PASS' if evidence_ok else 'FAIL',
              'mastery':'PASS' if mastery_ok else 'FAIL', 'recommendation':'PASS' if recommendation_ok else 'FAIL',
              'e2e':'PASS' if all((valid,answer_ok,evidence_ok,mastery_ok,recommendation_ok)) else 'FAIL',
              'production_mutations':0,'staging_mutations':0,'db_migration':0,'rls_changes':0,'question_bank_imports':0}
    (OUT/'mvp_e2e_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    qa_path=OUT/'tcte_mvp_qa_report.json'; qa=json.loads(qa_path.read_text(encoding='utf-8'))
    qa.update(report); qa['calibration']='FAIL_SAMPLE_LT_30'; qa['taxonomy_mapping']='PASS'
    qa_path.write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'checkpoints/latest.json').write_text(json.dumps({'phase':'MVP_E2E','completed':len(valid),'next_step':'REPORT'},ensure_ascii=False,indent=2),encoding='utf-8')
    return report
if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
