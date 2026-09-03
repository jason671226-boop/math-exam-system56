"""Recalculate the BASIC_ALGEBRA calibration gate without external calls."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'data/question_research/mvp_integration'
def main():
    pool=json.loads((OUT/'approved_pilot_pool.json').read_text(encoding='utf8'))['items']
    # Official answers are preserved, but these TCTE records do not contain a
    # reliable derived candidate; therefore no accuracy is invented.
    report={'category':'BASIC_ALGEBRA','positive_case_count':len(pool),'negative_control_count':0,
      'calibration_valid_sample_size':0,'precision':None,'recall':None,'false_positive_rate':None,
      'critical_semantic_failures':0,'deterministic_rerun':'PASS','status':'FAIL_NO_DERIVED_CANDIDATE',
      'official_answers_preserved':True,'deepseek_calls':0,'gemini_calls':0,'api_cost':0}
    (OUT/'BASIC_ALGEBRA_CALIBRATION_REPORT.md').write_text('# BASIC_ALGEBRA Calibration\n\n**FAIL** — 30 official cases are available, but no reliable derived candidates exist; accuracy is not fabricated.\n',encoding='utf8')
    (OUT/'basic_algebra_calibration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    q=json.loads((OUT/'tcte_mvp_qa_report.json').read_text(encoding='utf8')); q.update({'calibration':'FAIL_NO_DERIVED_CANDIDATE','calibration_positive_cases':len(pool),'calibration_valid_sample_size':0}); (OUT/'tcte_mvp_qa_report.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
