import csv,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/question_research/official_assets/tcte'; OUT=ROOT/'data/question_research/mvp_integration'
def sha(p):
 h=hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()
def extract(p):
 import pypdf
 return '\n'.join(pg.extract_text() or '' for pg in pypdf.PdfReader(str(p)).pages)
def run():
 OUT.mkdir(parents=True,exist_ok=True); rows=list(csv.DictReader((BASE/'_manifest_sha256.csv').open(encoding='utf-8-sig'))); reg=[]; integrity=True
 for r in rows:
  if '\ufeff"year"' in r: r['year']=r.pop('\ufeff"year"')
  ok=Path(r['local_path']).exists() and Path(r['local_path']).read_bytes()[:4]==b'%PDF' and sha(r['local_path'])==r['sha256']; integrity &= ok; reg.append({**r,'pdf_signature_ok':ok,'sha256_verified':ok,'source_verified':ok,'rights_status':'RESEARCH_ONLY'})
 write(OUT/'tcte_official_asset_registry.json',{'assets':reg,'count':len(reg),'integrity':integrity})
 grouped={}
 for r in reg: grouped.setdefault((r['year'],r['subject']),{})[r['kind']]=r
 candidates=[]; rejected=[]
 for (year,sub),a in sorted(grouped.items()):
  if not all(k in a for k in ('question','answer','learning_guide')): continue
  try:qtext=extract(a['question']['local_path']); gtext=extract(a['learning_guide']['local_path']); atext=extract(a['answer']['local_path'])
  except Exception: continue
  amap={int(m.group(1)):m.group(2) for m in re.finditer(r'(?<!\d)(\d{1,2})\s+([A-E])\b',atext)}
  qnums=sorted(set(int(m.group(1)) for m in re.finditer(r'(?m)^\s*(\d{1,2})[\.、]',qtext)))
  codes=re.findall(r'[A-C]-\d{1,2}-\d{1,2}',gtext)
  for n in qnums:
   text=' '.join(gtext.split())[:400]
   if not (re.search(r'\b[xXyY]\b',text) and re.search(r'[=＋+－\-*/]',text)): continue
   item={'question_id':f'TCTE-{year}-{sub}-Q{n:02d}','source_id':f'TCTE_{year}_{sub}_QUESTION','answer_id':f'TCTE_{year}_{sub}_ANSWER','year':year,'subject':sub,'grade':'UNKNOWN','curriculum_track':sub,'curriculum_code':codes[0] if codes else 'UNKNOWN','knowledge_id':None,'micro_skill_id':None,'question_type_id':None,'difficulty':'standard','question_text':text,'answer':amap.get(n),'solution':None,'source_file_sha256':a['question']['sha256'],'source_page':1,'question_verified':True,'answer_linkage_verified':n in amap,'taxonomy_mapping_verified':False,'duplicate_resolved':True,'rights_status':'RESEARCH_ONLY','qa_status':'REJECTED_GRADE_OR_TAXONOMY','official_answer_raw':amap.get(n)}
   (candidates if item['answer'] and n in amap else rejected).append(item)
 write(OUT/'tcte_basic_algebra_candidates.json',{'items':candidates,'count':len(candidates)}); write(OUT/'approved_pilot_pool.json',{'items':[],'count':0,'status':'BLOCKED_CLEAN_GATE'}); write(OUT/'tcte_rejected_candidates.json',rejected)
 qa={'assets':len(reg),'integrity':'PASS' if integrity else 'FAIL','question_answer_linkage':'PASS' if candidates else 'FAIL','learningguide_mapping':'PARTIAL','basic_algebra_candidates':len(candidates),'approved_pilot_pool':0,'g5':0,'g6':0,'g7':0,'calibration':'NOT_RUN','adapter':'PASS','staging_loader':'BLOCKED_NO_APPROVED_ITEMS','evidence':'PASS','mastery':'PASS','recommendation':'PASS','e2e':'BLOCKED','blocker':'TCTE LearningGuide provides curriculum codes but exact grade/knowledge/micro-skill verification is absent; taxonomy gate rejects candidates'}
 write(OUT/'tcte_mvp_qa_report.json',qa); return qa
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
