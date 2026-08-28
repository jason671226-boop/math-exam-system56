"""Materialize V6E parent crops from existing page anchors; fail closed on ambiguity."""
from __future__ import annotations
import json, re, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/'.local/stage7_elementary_competition'
def font(n):
 p=Path(r'C:\Windows\Fonts\msjh.ttc'); return ImageFont.truetype(str(p),n) if p.exists() else ImageFont.load_default()
def main():
 ocr={json.loads(l)['image']:json.loads(l) for l in (B/'elmc_photo_ocr_v5_rebuild.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()}
 ids=json.loads((B/'elmc_source_identity_v6d.json').read_text(encoding='utf-8'))
 idmap={x['sequence']:x for x in ids}; raw=(B/'elmc_individual_team_parents_v6d.jsonl').read_text(encoding='utf-8'); ps=json.loads(raw) if raw.lstrip().startswith('[') else [json.loads(l) for l in raw.splitlines() if l.strip()]
 links=json.loads((B/'elmc_solution_links_v6.json').read_text(encoding='utf-8')); matched={x['parent_question_id']:x for x in links if x.get('status')=='MATCHED_EXACT'}
 photos=sorted((B/'original_photos').glob('*.jpg')); out=B/'parent_crops_v6e'; out.mkdir(exist_ok=True)
 bypage={}
 for p in ps: bypage.setdefault(p['source_pages'][0],[]).append(p)
 materialized=[]; missing=[]; records=[]
 for seq,group in sorted(bypage.items()):
  src=photos[seq-1]; im=Image.open(src).convert('RGB'); w,h=im.size; rec=ocr.get(f'photo_{seq:03d}.png',{})
  anchors=[]
  for line in rec.get('lines',[]):
   words=line.get('words',[]) if isinstance(line,dict) else []
   if not words: continue
   first=words[0].get('text',''); m=re.fullmatch(r'[（(]?([0-9]{1,2})[.、):）]?',str(first).strip())
   if m and (str(first).strip()!=m.group(1) or len(words)>1): anchors.append((m.group(1),min(int(x.get('y',0)) for x in words)))
  anchors=list(dict((n,y) for n,y in anchors).items()); pnums=[str(p['question_number']) for p in group]
  # reliable only when one-to-one question-number anchors are available; single-parent pages use content bounds.
  amap={n:y for n,y in anchors if n in pnums}
  reliable=(len(group)==1 and len(anchors)<=1) or (len(group)>1 and len(amap)==len(group))
  ordered=sorted(group,key=lambda p: amap.get(str(p['question_number']),10**9))
  for i,p in enumerate(ordered):
   pid=p['parent_question_id']; status='PARENT_BOUNDARY_DATA_MISSING'; crop_path=None
   if reliable:
    if len(group)==1:
     top=max(0, min([y for _,y in anchors], default=80)-40); bottom=h
    else:
     y=amap[str(p['question_number'])]; nextys=[yy for nn,yy in amap.items() if yy>y]; top=max(0,y-45); bottom=min(h,(min(nextys)-35) if nextys else h)
    if bottom-top>120:
     crop=im.crop((0,top,w,bottom)); crop_path=out/f'{pid}.png'; crop.save(crop_path); materialized.append(pid); status='MATERIALIZED'
   if status!='MATERIALIZED': missing.append(pid)
   records.append({'parent_question_id':pid,'source_photo':src.name,'source_page':seq,'question_number':p['question_number'],'boundary_status':status,'crop_path':str(crop_path.relative_to(B)).replace('\\','/') if crop_path else None,'anchor_y':amap.get(str(p['question_number'])),'next_parent_anchor_y':None if not reliable else None,'quality_status':p.get('quality_status')})
 dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 dump(B/'elmc_individual_team_parents_v6e.jsonl',records); dump(B/'elmc_v6e_crop_audit.json',{'individual_parents':sum(idmap[p['source_pages'][0]]['competition_type']=='INDIVIDUAL' for p in ps),'team_parents':sum(idmap[p['source_pages'][0]]['competition_type']=='TEAM' for p in ps),'eligible_parents':len(ps),'valid_boundary':len(materialized),'materialized':len(materialized),'boundary_missing':len(missing),'quarantined':len(missing),'success_rate':len(materialized)/len(ps) if ps else 0,'missing_ids':missing,'matched_solutions':len(matched),'solution_crops_materialized':0,'solution_crop_unavailable':len(matched),'samples':0,'gemini_calls':0,'deepseek_calls':0,'production_reads':0,'production_writes':0})
 # sample with required individual and team representation
 sample=[]; seen=set()
 def add(p):
  if p['parent_question_id'] not in seen: sample.append(p); seen.add(p['parent_question_id'])
 for p in ps:
  if idmap[p['source_pages'][0]]['competition_type']=='INDIVIDUAL' and p['question_number'] in {str(i) for i in range(1,13)} and sum(idmap[x['source_pages'][0]]['competition_type']=='INDIVIDUAL' for x in sample)<12: add(p)
 for p in ps:
  if idmap[p['source_pages'][0]]['competition_type']=='TEAM' and sum(idmap[x['source_pages'][0]]['competition_type']=='TEAM' for x in sample)<10: add(p)
 for p in ps:
  if p.get('quality_status')=='CANONICAL_VISUAL_REQUIRED': add(p)
  if len(sample)>=30: break
 audit=json.loads((B/'elmc_v6e_crop_audit.json').read_text(encoding='utf-8')); audit['samples']=len(sample); audit['individual_samples']=sum(idmap[p['source_pages'][0]]['competition_type']=='INDIVIDUAL' for p in sample); audit['team_samples']=sum(idmap[p['source_pages'][0]]['competition_type']=='TEAM' for p in sample); dump(B/'elmc_v6e_crop_audit.json',audit)
 canv=[]; tf,bf=font(30),font(18)
 for i,p in enumerate(sample,1):
  seq=p['source_pages'][0]; ident=idmap[seq]; page=Image.new('RGB',(1800,2400),'white'); d=ImageDraw.Draw(page); d.text((45,35),f'ELMC V6E VALIDATION #{i}',font=tf,fill='black'); d.text((45,80),f"{ident['year']} 第{ident['edition']}屆 {ident['competition_type']} | Q{p['question_number']} | {p.get('quality_status')}",font=bf,fill='black'); rr=next((r for r in records if r['parent_question_id']==p['parent_question_id']),{}); d.text((45,115),f"parent crop: {rr.get('boundary_status')} | solution: {'MATCHED (crop unavailable)' if p['parent_question_id'] in matched else 'NO MATCHED SOLUTION'}",font=bf,fill=(120,0,0)); boxes=[(40,180,570,2320),(610,180,1190,2320),(1230,180,1760,2320)]
  for box,label in zip(boxes,['SOURCE PAGE','PARENT CROP','MATCHED SOLUTION']): d.rectangle(box,outline='black',width=2); d.text((box[0]+10,box[1]+8),label,font=bf,fill='black')
  def paste(path,box):
   try:
    with Image.open(path) as x: x=x.convert('RGB'); x.thumbnail((box[2]-box[0]-20,box[3]-box[1]-55),Image.Resampling.LANCZOS); page.paste(x,(box[0]+10,box[1]+45)); return True
   except Exception:return False
  paste(photos[seq-1],boxes[0]); cp=B/rr['crop_path'] if rr.get('crop_path') else None
  if not cp or not paste(cp,boxes[1]): d.text((boxes[1][0]+20,boxes[1][1]+100),'PARENT CROP\nUNAVAILABLE',font=bf,fill=(150,0,0))
  d.text((boxes[2][0]+20,boxes[2][1]+100),'SOLUTION CROP\nUNAVAILABLE' if p['parent_question_id'] in matched else 'NO MATCHED SOLUTION',font=bf,fill=(150,0,0)); canv.append(page)
 outpdf=B/'ELMC_V6E_FINAL_PARENT_VALIDATION.pdf'; canv[0].save(outpdf,'PDF',resolution=150,save_all=True,append_images=canv[1:]); print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
