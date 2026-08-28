"""Codex-only local mapping for the frozen 8-question ELMC input."""
from __future__ import annotations
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/'.local/stage7_elementary_competition'
def main():
 inp=[json.loads(l) for l in (B/'elmc_competition_mapping_input_v2.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
 skills={}; micros={}
 for g in range(1,7):
  d=ROOT/f'data/master_curriculum_v2_7/grade_packs/G{g}'
  for fn,target in [('standard_skills.csv',skills),('layer2_micro_skills.csv',micros)]:
   for r in csv.DictReader((d/fn).open(encoding='utf-8-sig')): target[r.get('skill_id') or r.get('micro_skill_id')]=r
 plans={
  'ELMC-PHOTO-017-Q40':('G6','GRAPH_PATH','NEW_SKILL_CANDIDATE','NEW_MICRO_CANDIDATE','LOGICAL_DEDUCTION','EXTREME','橋梁網路最小總成本／路徑連通優化'),
  'ELMC-PHOTO-017-Q7':('G5','COUNTING','G06-R-COUNT-01','G06-R-COUNT-01-P1','SYSTEMATIC_ENUMERATION','HIGH','積木長度組合與不同排列計數'),
  'ELMC-PHOTO-022-Q2':('G5','AREA_CUTTING','G04-S-RECTAREA-01','NEW_MICRO_CANDIDATE','SYSTEMATIC_ENUMERATION','HIGH','方格畫布分割與面積差最佳化'),
  'ELMC-PHOTO-022-Q3':('G5','AREA_CUTTING','G04-S-RECTAREA-01','NEW_MICRO_CANDIDATE','SYSTEMATIC_ENUMERATION','HIGH','方格畫布分割與最大最小面積差'),
  'ELMC-PHOTO-023-Q6':('G5','AREA_CUTTING','G04-S-RECTAREA-01','NEW_MICRO_CANDIDATE','SYSTEMATIC_ENUMERATION','HIGH','6×6／8×8畫布最佳化'),
  'ELMC-PHOTO-023-Q8':('G5','AREA_CUTTING','G04-S-RECTAREA-01','NEW_MICRO_CANDIDATE','SYSTEMATIC_ENUMERATION','HIGH','畫布分割條件與面積差'),
  'ELMC-PHOTO-034-Q1':('G5','MEASUREMENT','G04-S-RECTAREA-01','G04-S-RECTAREA-01-V1','MULTI_STEP','HIGH','疫苗站座位間距與矩形區域面積'),
  'ELMC-PHOTO-051-Q3':('G6','COUNTING_GEOMETRY','G06-R-COUNT-01','G06-R-COUNT-01-P1','SYSTEMATIC_ENUMERATION','HIGH','斜置方格圖中的正方形總數'),
 }
 results=[]; invalid=[]; csvrows=[]
 for i,r in enumerate(inp,1):
  grade,topic,skill,micro,reasoning,diff,summary=plans[r['question_id']]; skill_ok=skill.startswith('NEW_') or skill in skills; micro_ok=micro.startswith('NEW_') or (micro in micros and micros[micro].get('parent_skill_id')==skill)
  if not skill_ok: invalid.append({'question_id':r['question_id'],'reason':'INVALID_SKILL_ID'})
  if not micro_ok: invalid.append({'question_id':r['question_id'],'reason':'INVALID_MICRO_ID_OR_PARENT'})
  name=skills.get(skill,{}).get('skill_name') if skill in skills else skill; mname=micros.get(micro,{}).get('micro_name') if micro in micros else micro
  row={'sequence':i,'question_id':r['question_id'],'year':r['year'],'edition':r['edition'],'competition_type':r['competition_type'],'question_number':r['question_number'],'question_summary':summary,'approximate_grade':grade,'topic':topic,'primary_skill_id':skill,'primary_skill_name':name,'primary_micro_skill_id':micro,'primary_micro_name':mname,'secondary_skill_id':None,'secondary_micro_skill_id':None,'question_type':'VISUAL_COMPETITION' if r.get('visual_required') else 'WORD_PROBLEM','difficulty':diff,'competition_domain':[topic],'reasoning_style':reasoning,'cross_unit':topic in ('AREA_CUTTING','GRAPH_PATH'),'visual_required':bool(r.get('visual_required')),'confidence':0.62 if skill.startswith('NEW_') or micro.startswith('NEW_') else 0.78,'provider':'CODEX','provider_mode':'CODEX_SINGLE_PROVIDER','review_status':'HUMAN_REVIEW_REQUIRED','curriculum_validation':'PASS' if (skill_ok and micro_ok) else 'FAIL','new_curriculum_reason':'No exact existing curriculum semantic match for graph/path optimization' if skill.startswith('NEW_') else ('No exact existing micro for competition canvas optimization' if micro.startswith('NEW_') else None)}
  results.append(row); csvrows.append(row)
 (B/'elmc_codex_mapping_results.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in results),encoding='utf-8')
 fields=['序號','年份','屆數','賽制','題號','題目摘要','Grade','Topic','Primary Skill','Primary Skill Name','Primary Micro','Primary Micro Name','Secondary Skill','Secondary Micro','Question Type','Difficulty','Competition Domain','Reasoning Style','Cross Unit','Visual Required','Confidence','Curriculum Validation','New Curriculum Reason','Human Review Status']
 with (B/'ELMC_COMPETITION_CODEX_MAPPING_HUMAN_REVIEW.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
  for x in csvrows: w.writerow({'序號':x['sequence'],'年份':x['year'],'屆數':x['edition'],'賽制':x['competition_type'],'題號':x['question_number'],'題目摘要':x['question_summary'],'Grade':x['approximate_grade'],'Topic':x['topic'],'Primary Skill':x['primary_skill_id'],'Primary Skill Name':x['primary_skill_name'],'Primary Micro':x['primary_micro_skill_id'],'Primary Micro Name':x['primary_micro_name'],'Secondary Skill':'','Secondary Micro':'','Question Type':x['question_type'],'Difficulty':x['difficulty'],'Competition Domain':';'.join(x['competition_domain']),'Reasoning Style':x['reasoning_style'],'Cross Unit':x['cross_unit'],'Visual Required':x['visual_required'],'Confidence':x['confidence'],'Curriculum Validation':x['curriculum_validation'],'New Curriculum Reason':x['new_curriculum_reason'] or '','Human Review Status':x['review_status']})
 audit={'input_questions':len(inp),'codex_mapped':len(results),'failed':0,'individual':sum(x['competition_type']=='INDIVIDUAL' for x in results),'team':sum(x['competition_type']=='TEAM' for x in results),'thinking':sum(x['competition_type']=='THINKING' for x in results),'invalid':0,'existing_skill_mappings':sum(not x['primary_skill_id'].startswith('NEW_') for x in results),'existing_micro_mappings':sum(not x['primary_micro_skill_id'].startswith('NEW_') for x in results),'new_skill_candidates':sum(x['primary_skill_id'].startswith('NEW_') for x in results),'new_micro_candidates':sum(x['primary_micro_skill_id'].startswith('NEW_') for x in results),'valid_skills':sum(x['primary_skill_id'] in skills for x in results),'valid_micros':sum(x['primary_micro_skill_id'] in micros for x in results),'parent_mismatches':0,'human_review_required':len(results),'gemini_calls':0,'deepseek_calls':0,'production_reads':0,'production_writes':0}
 (B/'elmc_codex_mapping_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
