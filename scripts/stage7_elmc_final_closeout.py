"""Freeze the reliable ELMC extraction subset; no AI or database access."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/'.local/stage7_elementary_competition'
def main():
 ids=json.loads((B/'elmc_source_identity_v6d.json').read_text(encoding='utf-8')); imap={x['sequence']:x for x in ids}
 raw=(B/'elmc_parent_questions_v6.jsonl').read_text(encoding='utf-8'); parents=json.loads(raw) if raw.lstrip().startswith('[') else [json.loads(l) for l in raw.splitlines() if l.strip()]
 eraw=(B/'elmc_individual_team_parents_v6e.jsonl').read_text(encoding='utf-8'); ev=json.loads(eraw) if eraw.lstrip().startswith('[') else [json.loads(l) for l in eraw.splitlines() if l.strip()]; evi={x['parent_question_id']:x for x in ev}
 links=json.loads((B/'elmc_solution_links_v6.json').read_text(encoding='utf-8')); lmap={x['parent_question_id']:x for x in links if x.get('status')=='MATCHED_EXACT'}
 final=[]; excluded=[]
 for p in parents:
  seq=p['source_pages'][0]; ident=imap.get(seq,{}); e=evi.get(p['parent_question_id'],{}); reason=None
  if ident.get('competition_type')=='THINKING': reason='THINKING_EXCLUDED'
  elif ident.get('competition_type') not in ('INDIVIDUAL','TEAM'): reason='SOURCE_IDENTITY_UNCERTAIN'
  elif ident.get('page_role') not in ('QUESTION_PAGE','QUESTION_AND_SOLUTION'): reason='QUESTION_STRUCTURE_UNCERTAIN'
  elif e.get('boundary_status')!='MATERIALIZED': reason=e.get('boundary_status') or 'PARENT_BOUNDARY_DATA_MISSING'
  if reason:
   excluded.append({**p,'excluded':True,'reason':reason,'source_identity':ident}); continue
  link=lmap.get(p['parent_question_id']); solstatus='MATCHED_EXACT' if link else 'NO_RELIABLE_SOLUTION'
  final.append({**p,'source_identity':ident,'excluded':False,'visual_required':p.get('quality_status')=='CANONICAL_VISUAL_REQUIRED','source_reference':{'photo':p.get('source_photo'),'page':seq},'solution_status':solstatus,'solution_link':link})
 # exact source/question dedup; retain first canonical record
 seen=set(); unique=[]; dup=0
 for p in final:
  key=(p['source_identity'].get('year'),p['source_identity'].get('edition'),p['source_identity'].get('competition_type'),p['question_number'])
  if key in seen: dup+=1; excluded.append({**p,'excluded':True,'reason':'DUPLICATE_CANONICAL_RECORD'})
  else: seen.add(key); unique.append(p)
 final=unique
 def lines(path, rows): path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
 lines(B/'elmc_competition_parents_final.jsonl',final); lines(B/'elmc_competition_solutions_final.jsonl',[{'question_id':p['parent_question_id'],'solution_link':p.get('solution_link'),'solution_status':p['solution_status']} for p in final if p['solution_status']=='MATCHED_EXACT']); lines(B/'elmc_competition_excluded_final.jsonl',excluded)
 mapping=[]
 for p in final:
  ident=p['source_identity']; mapping.append({'question_id':p['parent_question_id'],'year':ident.get('year'),'edition':ident.get('edition'),'competition_type':ident.get('competition_type'),'question_number':p['question_number'],'question_text':None,'visual_required':p['visual_required'],'source_reference':p['source_reference'],'solution_status':p['solution_status']})
 lines(B/'elmc_competition_mapping_input.jsonl',mapping)
 from collections import Counter
 rc=Counter(x['reason'] for x in excluded); reliable=sum(p['solution_status']=='MATCHED_EXACT' for p in final); ambiguous=sum(p['solution_status']=='UNMATCHED_OR_AMBIGUOUS' for p in final)
 audit={'individual_usable':sum(p['source_identity']['competition_type']=='INDIVIDUAL' for p in final),'team_usable':sum(p['source_identity']['competition_type']=='TEAM' for p in final),'thinking_excluded':sum(x.get('reason')=='THINKING_EXCLUDED' for x in excluded),'total_final_usable':len(final),'excluded_by_reason':dict(rc),'total_excluded':len(excluded),'reliable_matched':reliable,'no_reliable_solution':len(final)-reliable-ambiguous,'ambiguous_unmatched':ambiguous,'duplicate_records_removed':dup,'final_unique_questions':len(final),'mapping_input_created':True,'mapping_input_questions':len(mapping),'thinking_in_mapping_input':sum(x['competition_type']=='THINKING' for x in mapping),'invalid_records_in_mapping_input':sum(not x['competition_type'] in ('INDIVIDUAL','TEAM') for x in mapping),'extraction_frozen':True,'gemini_calls':0,'deepseek_calls':0,'production_reads':0,'production_writes':0}
 (B/'elmc_competition_final_manifest.json').write_text(json.dumps({'profile':'ELEMENTARY_COMPETITION','source_priority':'PHOTO_BACKED_CANONICAL_SOURCE','scope':['INDIVIDUAL','TEAM'],'thinking_excluded':True,'question_count':len(final),'excluded_count':len(excluded),'extraction_status':'FROZEN'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (B/'elmc_competition_final_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
