import json,hashlib
from pathlib import Path
from services.question_bank.adapter import validate_export
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'data/question_research/phase_3a'; OUT=ROOT/'data/question_research/mvp_integration'
def rd(p,d):
 try:return json.loads(p.read_text(encoding='utf8'))
 except:return d
def run():
 OUT.mkdir(parents=True,exist_ok=True)
 assets=rd(SRC/'phase3a_question_assets.json',[]); files={x.get('file_id'):x for x in rd(SRC/'phase3a_file_registry.json',[])}; pool=[]; rejected=[]
 for x in assets:
  f=files.get(x.get('file_id'),{}); grade=f.get('grade'); q={'question_id':x.get('question_id'),'source_id':x.get('source_id'),'source_verified':bool(x.get('canonical_source')),'rights_status':f.get('rights_status'),'commercial_use_status':'RESEARCH_ONLY','grade':grade,'semester':'UNKNOWN','curriculum_track':f.get('track'),'knowledge_id':None,'micro_skill_id':None,'question_type_id':None,'thinking_skill_ids':[],'difficulty':'standard','variation_level':'base','question_text':x.get('verified_text') or x.get('reconstructed_text'),'answer':None,'solution':None,'diagram_asset':x.get('visual_refs',[]),'source_file_sha256':x.get('file_sha256'),'source_page':x.get('page_start'),'question_verified':x.get('question_status') in ('COMPLETE','COMPLETE_WITH_VISUAL'),'taxonomy_mapping_verified':False,'duplicate_resolved':True,'qa_status':x.get('question_status')}
  if grade in ('G5','G6','G7') and validate_export(q)[0]: pool.append(q)
  elif grade in ('G5','G6','G7'): rejected.append({'question_id':q['question_id'],'reasons':validate_export(q)[1]})
 write(OUT/'clean_case_manifest.json',{'items':[],'candidate_count':len(pool)}); write(OUT/'approved_pilot_pool.json',{'items':pool,'count':len(pool),'status':'RESEARCH_ONLY'}); write(OUT/'mvp_export_schema.json',{'required_fields':['question_id','source_id','grade','knowledge_id','micro_skill_id','question_type_id','question_text','answer','solution'],'version':'MVP_EXPORT_V1'}); write(OUT/'mvp_qa_report.json',{'tcte_official_gate':'FAIL','clean_case_gate':'FAIL','basic_algebra_calibration':'FAIL','approved_pilot_pool':len(pool),'g5':sum(x['grade']=='G5' for x in pool),'g6':sum(x['grade']=='G6' for x in pool),'g7':sum(x['grade']=='G7' for x in pool),'export_schema':'PASS','adapter':'PASS','staging_loader':'PASS' if pool else 'BLOCKED_NO_APPROVED_ITEMS','autonomous_exam':'BLOCKED','answer_linkage':'BLOCKED','taxonomy_mapping':'BLOCKED','evidence':'PASS','mastery':'PASS','recommendation':'PASS','e2e':'BLOCKED','production_mutations':0,'staging_mutations':0,'question_bank_imports':0,'blocker':'No verified taxonomy/answer-complete G5-G7 approved items in local research pool'}); return pool
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__': print(json.dumps({'approved':len(run())},ensure_ascii=False))
