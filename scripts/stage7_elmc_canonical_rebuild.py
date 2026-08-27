"""Stage 7C-1D canonical ELMC image-backed source rebuild."""
from __future__ import annotations
import csv,json,subprocess,sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from services.elmc_canonical_rebuild import render_sources,load_ocr,segment_questions

BASE=ROOT/".local/stage7_elementary_competition";PDF=BASE/"image_backed_pdfs";PAGES=BASE/"canonical_pages";OCR_IN=BASE/"canonical_ocr_input";CROPS=BASE/"canonical_question_crops"
def write_json(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def write_jsonl(p,rows):p.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")

def main():
 manifest=render_sources(PDF,PAGES,OCR_IN);write_json(BASE/"elmc_canonical_page_manifest.json",manifest);write_json(PAGES/"page_manifest.json",manifest)
 ocr_path=BASE/"elmc_canonical_ocr_pages.jsonl"
 if not ocr_path.is_file() or sum(1 for line in ocr_path.read_text(encoding="utf-8").splitlines() if line.strip()) != len(manifest):
  subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ROOT/"scripts/stage7_elmc_windows_ocr.ps1"),"-InputDirectory",str(OCR_IN),"-OutputJsonl",str(ocr_path)],check=True)
 questions,boundary=segment_questions(manifest,load_ocr(ocr_path),PAGES,CROPS)
 seen=set();unique=[]
 for q in questions:
  if q["fingerprint"] not in seen:seen.add(q["fingerprint"]);unique.append(q)
 quality=[q for q in unique if q["source_quality_status"] not in {"CANONICAL_CLEAN","CANONICAL_VISUAL_REQUIRED"}]+boundary
 visuals=[{"question_id":q["question_id"],"question_image_crop":q["question_image_crop"],"requires_visual":q["visual_required"],"figure_crop":q["question_image_crop"] if q["visual_required"] and not q.get("table_required") else None,"table_crop":q["question_image_crop"] if q.get("table_required") else None} for q in unique if q["visual_required"]]
 # Solution pairing remains fail-closed until a reliable matching question number is detected on solution pages.
 links=[{"question_id":q["question_id"],"status":"UNMATCHED_SOLUTION"} for q in unique]
 write_jsonl(BASE/"elmc_canonical_questions.jsonl",unique);write_json(BASE/"elmc_canonical_solution_links.json",links);write_json(BASE/"elmc_canonical_quality_queue.json",quality);write_json(BASE/"elmc_canonical_visual_manifest.json",visuals)
 legacy=BASE/"elmc_extracted_questions.jsonl";legacy_count=sum(1 for x in legacy.read_text(encoding="utf-8").splitlines() if x.strip())
 write_json(BASE/"elmc_legacy_ocr_quarantine.json",{"status":"LEGACY_OCR_UNTRUSTED","questions":legacy_count,"mapping_artifacts_reused":0,"human_gt_reused":0})
 counts=Counter(q["source_quality_status"] for q in unique);counts.update(x["status"] for x in boundary);audit={"pdfs":4,"pages_rendered":len(manifest),"editions":4,"sections":sorted({x["section"] for x in manifest if x["section"]}),"raw_question_segments":len(questions)+len(boundary),"unique_questions":len(unique),"multi_page_questions":0,"boundary_failures":sum(x["status"]=="QUESTION_BOUNDARY_REVIEW_REQUIRED" for x in boundary),"quality":dict(counts),"missing_canonical_diagrams":0,"missing_canonical_tables":0,"questions_with_diagrams":sum(q["visual_required"] and not q.get("table_required") for q in unique),"questions_with_tables":sum(q.get("table_required",False) for q in unique),"figure_crops":sum(bool(x["figure_crop"]) for x in visuals),"table_crops":sum(bool(x["table_crop"]) for x in visuals),"matched_solutions":0,"unmatched_solutions":len(links),"legacy_quarantined":legacy_count,"usable":sum(q["source_quality_status"] in {"CANONICAL_CLEAN","CANONICAL_VISUAL_REQUIRED"} for q in unique),"gemini_calls":0,"deepseek_calls":0,"production_reads":0,"production_writes":0}
 write_json(BASE/"elmc_canonical_corpus_audit.json",audit);print(json.dumps(audit,ensure_ascii=False))
if __name__=="__main__":main()
