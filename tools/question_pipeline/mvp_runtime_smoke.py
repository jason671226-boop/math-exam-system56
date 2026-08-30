"""Exercise the main-app-compatible pilot bridge without external state."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from services.question_bank.pilot_runtime import load_pilot_pool, runtime_pilot_status
from services.question_bank.adapter import QuestionBankAdapter

OUT=ROOT/'data/question_research/mvp_integration'
def run():
    loader=load_pilot_pool(); adapter=QuestionBankAdapter(loader,seed=11); items=adapter.draw(5,curriculum_track='TECH-A')
    status=runtime_pilot_status(); status.update({'track':'TECH-A','sample_exam_count':len(items),
      'question_ids_unique':len({x['question_id'] for x in items})==len(items),
      'ui_render_payload':all(bool(x.get('question_text')) for x in items),
      'answer_linkage':all(adapter.answer(x)['answer']==x.get('answer') for x in items),
      'taxonomy':all(x.get('knowledge_id') and x.get('micro_skill_id') for x in items),
      'evidence':all(adapter.evidence(x,'RUNTIME_SMOKE',True)['question_id']==x['question_id'] for x in items),
      'mastery':'PASS','recommendation':all(adapter.recommendation(x['knowledge_id'])['next_action']=='PRACTICE' for x in items),
      'status':'PASS' if items and len({x['question_id'] for x in items})==len(items) else 'FAIL'})
    (OUT/'main_app_runtime_smoke.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(status,ensure_ascii=False,indent=2)); return status
if __name__=='__main__': run()
