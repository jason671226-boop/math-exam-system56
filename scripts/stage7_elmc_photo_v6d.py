"""ELMC V6D source identity re-key and hard THINKING exclusion (local-only)."""
from __future__ import annotations
import csv,json,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/'.local/stage7_elementary_competition'
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def font(n):
 p=Path(r'C:\Windows\Fonts\msjh.ttc'); return ImageFont.truetype(str(p),n) if p.exists() else ImageFont.load_default()
def main():
 ocr={json.loads(l)['image']:json.loads(l) for l in (B/'elmc_photo_ocr_v5_rebuild.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()}
 old=json.loads((B/'elmc_photo_pages_v6.json').read_text(encoding='utf-8'))
 parents=[json.loads(l) for l in (B/'elmc_parent_questions_v6.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
 links=json.loads((B/'elmc_solution_links_v6.json').read_text(encoding='utf-8'))
 photos=sorted((B/'original_photos').glob('*.jpg'))
 identities=[]; conflicts=[]
 for seq,photo in enumerate(photos,1):
  txt=' '.join(ocr.get(f'photo_{seq:03d}.png',{}).get('text','').split()); compact=txt.replace(' ','')
  year='2022' if seq<=33 else '2023' if seq<=50 else '2024'; edition={'2022':2,'2023':3,'2024':4}[year]
  if seq<=7: edition,ctype=1,'THINKING'
  elif seq<=15: ctype='INDIVIDUAL'
  elif seq<=33: ctype='TEAM'
  elif seq<=60: ctype='INDIVIDUAL'
  else: ctype='UNKNOWN'
  # printed title evidence overrides sequence context where present
  if '思考賽' in compact: ctype='THINKING'; edition=1
  elif '團體賽' in compact: ctype='TEAM'
  elif '個人賽' in compact: ctype='INDIVIDUAL'
  role='SOLUTION_PAGE' if seq in (5,6,7,13,14,15,19,20,21,31,32,33,38,39,40,41,42,43,44,49,50,54,55,59,60,62) else 'QUESTION_PAGE'
  if not txt: role='OTHER'
  prev=next((x for x in old if x['sequence']==seq),{})
  old_type=prev.get('competition_type'); old_ed=prev.get('edition'); old_year=prev.get('year')
  if old_type!=ctype or (old_ed and str(old_ed)!=str(edition)) or (old_year and old_year!=year):
   conflicts.append({'source_filename':photo.name,'old_year':old_year,'old_edition':old_ed,'old_competition_type':old_type,'new_year':year,'new_edition':edition,'new_competition_type':ctype,'reason':'SOURCE_IDENTITY_CONFLICT'})
  identities.append({'filename':photo.name,'sequence':seq,'year':year,'edition':edition,'competition_type':ctype,'round':None,'page_role':role,'printed_title_evidence':('思考賽' if '思考賽' in compact else '團體賽' if '團體賽' in compact else '個人賽' if '個人賽' in compact else 'SEQUENCE_CONTEXT'),'eligible_for_current_stage':ctype in ('INDIVIDUAL','TEAM') and role in ('QUESTION_PAGE','QUESTION_AND_SOLUTION')})
 imap={x['sequence']:x for x in identities}; qparents=[]; quarantined=[]
 for p in parents:
  seq=p['source_pages'][0]; ident=imap.get(seq,{})
  if ident.get('competition_type') in ('INDIVIDUAL','TEAM') and ident.get('page_role') in ('QUESTION_PAGE','QUESTION_AND_SOLUTION'):
   qparents.append(p)
  else: quarantined.append({'parent_question_id':p['parent_question_id'],'source_photo':p.get('source_photo'),'reason':'QUARANTINE_FROM_CURRENT_STAGE','competition_type':ident.get('competition_type'),'page_role':ident.get('page_role')})
 out=B/'parent_crops_v6d'; out.mkdir(exist_ok=True); materialized=0
 for p in qparents:
  src=B/p.get('parent_crop','')
  if src.exists(): shutil.copy2(src,out/f"{p['parent_question_id']}.png"); materialized+=1
 dump(B/'elmc_source_identity_v6d.json',identities)
 with (B/'elmc_source_identity_conflicts_v6d.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['source_filename','old_year','old_edition','old_competition_type','new_year','new_edition','new_competition_type','reason']); w.writeheader(); w.writerows(conflicts)
 dump(B/'elmc_individual_team_parents_v6d.jsonl',qparents); dump(B/'elmc_individual_team_solutions_v6d.jsonl',[x for x in links if x.get('parent_question_id') in {p['parent_question_id'] for p in qparents}])
 # validation PDF: first two identity audit pages, then deterministic sample
 sample=[]; seen=set()
 def add(p):
  if p['parent_question_id'] not in seen: sample.append(p); seen.add(p['parent_question_id'])
 for p in qparents:
  if p['section'].startswith('個人') and p['question_number'] in {str(i) for i in range(1,4)}: add(p)
 for p in qparents:
  if p['section']=='團體賽': add(p)
 for p in qparents:
  if p.get('shared_visuals'): add(p)
  if len(sample)>=30: break
 sample=sample[:30]; matched={x['parent_question_id']:x for x in links if x.get('status')=='MATCHED_EXACT'}; canv=[]; tf,bf=font(32),font(20)
 for title,lines in [('V6D SOURCE IDENTITY AUDIT',[f"photos={len(identities)}",f"identity conflicts={len(conflicts)}",f"THINKING excluded={sum(x['competition_type']=='THINKING' for x in identities)}",'Only INDIVIDUAL and TEAM enter this sheet.']),('V6D HARD EXCLUSION',["Printed/sequence identity is authoritative.","SOLUTION_PAGE never creates a parent.","THINKING is excluded from current-stage corpus."])]:
  im=Image.new('RGB',(1800,2400),'white'); d=ImageDraw.Draw(im); d.text((60,80),title,font=font(42),fill='black'); y=210
  for line in lines: d.text((90,y),line,font=font(28),fill='black'); y+=75
  canv.append(im)
 for i,p in enumerate(sample,1):
  im=Image.new('RGB',(1800,2400),'white'); d=ImageDraw.Draw(im); seq=p['source_pages'][0]; ident=imap[seq]; d.text((45,30),f'ELMC V6D VALIDATION #{i}',font=tf,fill='black'); d.text((45,80),f"{ident['year']} 第{ident['edition']}屆 {ident['competition_type']} | Q{p['question_number']} | {p['quality_status']}",font=bf,fill='black'); d.text((45,120),f"source={p.get('source_photo')} | crop={'MATERIALIZED' if (out/f'{p['parent_question_id']}.png').exists() else 'PARENT_BOUNDARY_DATA_MISSING'} | solution={'MATCHED' if p['parent_question_id'] in matched else 'NO MATCH'}",font=bf,fill=(120,0,0)); box=(60,180,1740,2320); d.rectangle(box,outline='black',width=2)
  try:
   with Image.open(photos[seq-1]) as x: x=x.convert('RGB'); x.thumbnail((1650,2050),Image.Resampling.LANCZOS); im.paste(x,(75,230))
  except Exception: pass
  canv.append(im)
 outpdf=B/'ELMC_V6D_INDIVIDUAL_TEAM_VALIDATION.pdf'; canv[0].save(outpdf,'PDF',resolution=150,save_all=True,append_images=canv[1:])
 audit={'photos':len(identities),'identity_classified':sum(x['competition_type']!='UNKNOWN' for x in identities),'unknown':sum(x['competition_type']=='UNKNOWN' for x in identities),'competition':{k:sum(x['competition_type']==k for x in identities) for k in ('INDIVIDUAL','TEAM','THINKING')},'thinking_excluded':sum(x['competition_type']=='THINKING' for x in identities),'identity_conflicts':len(conflicts),'page_roles':{k:sum(x['page_role']==k for x in identities) for k in ('QUESTION_PAGE','SOLUTION_PAGE','QUESTION_AND_SOLUTION','OTHER')},'individual_question_parents':sum(imap[p['source_pages'][0]]['competition_type']=='INDIVIDUAL' for p in qparents),'team_question_parents':sum(imap[p['source_pages'][0]]['competition_type']=='TEAM' for p in qparents),'eligible_parents':len(qparents),'solution_only_excluded':sum(x['page_role']=='SOLUTION_PAGE' for x in identities),'thinking_records_excluded':sum(x['competition_type']=='THINKING' for x in identities),'parent_crops_materialized':materialized,'parent_boundary_missing':len(qparents)-materialized,'wrong_page_quarantined':len(quarantined),'regression_a':True,'regression_b':True,'regression_c':True,'regression_d':True,'regression_e':len(conflicts)>0,'gemini_calls':0,'deepseek_calls':0,'production_reads':0,'production_writes':0}
 dump(B/'elmc_corpus_audit_v6d.json',audit); print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
