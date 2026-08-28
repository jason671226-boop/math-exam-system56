"""Validate and build ELMC mapping input v2 from frozen local corpus only."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/'.local/stage7_elementary_competition'
def main():
 rows=[json.loads(l) for l in (B/'elmc_competition_mapping_input.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
 final=[json.loads(l) for l in (B/'elmc_competition_parents_final.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
 v6e_raw=(B/'elmc_individual_team_parents_v6e.jsonl').read_text(encoding='utf-8'); v6e=json.loads(v6e_raw) if v6e_raw.lstrip().startswith('[') else [json.loads(l) for l in v6e_raw.splitlines() if l.strip()]
 crops={x['parent_question_id']:x for x in v6e if x.get('boundary_status')=='MATERIALIZED'}
 passed=[]; failures=[]
 for r in rows:
  f=next((x for x in final if x['parent_question_id']==r['question_id']),None); c=crops.get(r['question_id']);
  if not f: failures.append({'question_id':r['question_id'],'reason':'SOURCE_UNRELIABLE'}); continue
  if not c or not c.get('crop_path') or not (B/c['crop_path']).exists(): failures.append({'question_id':r['question_id'],'reason':'VISUAL_REQUIRED_WITHOUT_REFERENCE'}); continue
  passed.append({**r,'question_text_or_summary':None,'visual_reference':c['crop_path'],'representation_quality':'VISUAL_REQUIRED_CANONICAL_CROP'})
 out=B/'elmc_competition_mapping_input_v2.jsonl'; out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in passed),encoding='utf-8')
 from collections import Counter
 reasons=Counter(x['reason'] for x in failures); audit={'previous_questions':len(rows),'pass':len(passed),'fail':len(failures),'excluded':len(failures),'mapping_ready':len(passed),'failure_reasons':dict(reasons),'per_question_failures':failures,'gemini_calls':0,'deepseek_calls':0,'production_reads':0,'production_writes':0}
 (B/'elmc_mapping_representation_gate_v2.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
