"""V6C local-only materialization audit; never invents boundaries."""
from __future__ import annotations
import json, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'.local/stage7_elementary_competition'
def f(n):
 p=Path(r'C:\Windows\Fonts\msjh.ttc'); return ImageFont.truetype(str(p),n) if p.exists() else ImageFont.load_default()
def main():
 ps=[json.loads(l) for l in (BASE/'elmc_parent_questions_v6.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
 links=json.loads((BASE/'elmc_solution_links_v6.json').read_text(encoding='utf-8'))
 eligible=[p for p in ps if p.get('section') in ('個人賽','個人賽第一回','個人賽第二回','團體賽')]
 out=BASE/'parent_crops_v6c'; out.mkdir(exist_ok=True); solout=BASE/'solution_crops_v6c'; solout.mkdir(exist_ok=True)
 for p in eligible:
  src=BASE/p.get('parent_crop','')
  if src.exists(): shutil.copy2(src,out/f"{p['parent_question_id']}.png")
 matched={x['parent_question_id']:x for x in links if x.get('status','').startswith('MATCHED')}
 photos=sorted((BASE/'original_photos').glob('*.jpg'))
 # deterministic sample: individual first, then team, then visual/matched
 sample=[]; seen=set()
 def add(p):
  if p['parent_question_id'] not in seen: sample.append(p); seen.add(p['parent_question_id'])
 for p in eligible:
  if p['section'].startswith('個人') and p['question_number'] in {str(i) for i in range(1,13)} and sum(x['section'].startswith('個人') for x in sample)<12: add(p)
 for p in eligible:
  if p['section']=='團體賽' and sum(x['section']=='團體賽' for x in sample)<8: add(p)
 for p in eligible:
  if p['parent_question_id'] in matched and sum(x['parent_question_id'] in matched for x in sample)<5: add(p)
 for p in eligible:
  if p.get('shared_visuals') or p['parent_question_id'] in matched: add(p)
  if len(sample)>=30: break
 sample=sample[:30]; pages=[]; tf,bf=f(28),f(18)
 for i,p in enumerate(sample,1):
  im=Image.new('RGB',(1800,2400),'white'); d=ImageDraw.Draw(im); seq=p['source_pages'][0]
  d.text((45,30),f'ELMC V6C PARENT VALIDATION #{i}',font=tf,fill='black'); d.text((45,75),f"{p['year']} {p['edition']} {p['section']} | Q{p['question_number']} | {p['quality_status']}",font=bf,fill='black')
  d.text((45,110),f"parent crop: {'MATERIALIZED' if (out/f'{p['parent_question_id']}.png').exists() else 'PARENT_BOUNDARY_DATA_MISSING'} | solution: {'MATCHED' if p['parent_question_id'] in matched else 'NO MATCHED SOLUTION'}",font=bf,fill=(120,0,0))
  boxes=[(40,180,570,2320),(610,180,1190,2320),(1230,180,1760,2320)]
  for box,label in zip(boxes,['SOURCE PAGE','PARENT CROP','MATCHED SOLUTION CROP']): d.rectangle(box,outline='black',width=2); d.text((box[0]+10,box[1]+8),label,font=bf,fill='black')
  def paste(path,box):
   try:
    with Image.open(path) as x: x=x.convert('RGB'); x.thumbnail((box[2]-box[0]-20,box[3]-box[1]-55),Image.Resampling.LANCZOS); im.paste(x,(box[0]+10,box[1]+45)); return True
   except Exception:return False
  src=photos[seq-1] if 0<seq<=len(photos) else None; paste(src,boxes[0]) if src else None
  cp=out/f"{p['parent_question_id']}.png"
  if not paste(cp,boxes[1]): d.text((boxes[1][0]+20,boxes[1][1]+100),'PARENT CROP\nUNAVAILABLE\n(boundary data missing)',font=bf,fill=(150,0,0))
  if p['parent_question_id'] in matched: d.text((boxes[2][0]+20,boxes[2][1]+100),'SOLUTION CROP\nUNAVAILABLE\n(no coordinates)',font=bf,fill=(150,0,0))
  else: d.text((boxes[2][0]+20,boxes[2][1]+100),'NO MATCHED SOLUTION',font=bf,fill=(150,0,0))
  pages.append(im)
 outpdf=BASE/'ELMC_V6C_INDIVIDUAL_TEAM_PARENT_VALIDATION.pdf'; pages[0].save(outpdf,'PDF',resolution=150,save_all=True,append_images=pages[1:])
 audit={'individual_parents':sum(p['section'].startswith('個人') for p in eligible),'team_parents':sum(p['section']=='團體賽' for p in eligible),'thinking_excluded':sum(p.get('section')=='思考賽' for p in ps),'eligible_parents':len(eligible),'materialized':sum((out/f"{p['parent_question_id']}.png").exists() for p in eligible),'boundary_missing':len(eligible)-sum((out/f"{p['parent_question_id']}.png").exists() for p in eligible),'matched_solutions':len(matched),'solution_crops_materialized':0,'solution_crop_unavailable':len(matched),'samples':len(sample),'individual_samples':sum(p['section'].startswith('個人') for p in sample),'team_samples':sum(p['section']=='團體賽' for p in sample),'visual_samples':sum(bool(p.get('shared_visuals')) for p in sample),'matched_samples':sum(p['parent_question_id'] in matched for p in sample),'validation':'FAIL' if len(eligible)-sum((out/f"{p['parent_question_id']}.png").exists() for p in eligible)>0 else 'PASS'}
 (BASE/'elmc_v6c_crop_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
