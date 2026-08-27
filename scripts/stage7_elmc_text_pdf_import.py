"""Import local-only ELMC text PDFs, optionally run two-provider classification, and audit."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from services.ai_provider import get_ai_provider
from services.elmc_text_pdf import EDITIONS, fingerprint, load_catalog, parse_pdf, validate_mapping
from services.elementary_competition import COMPETITION_THINKING_SKILLS, COMPETITION_TOPICS
from services.stage5_question_mapping import build_candidate_packet

LOCAL = ROOT / ".local/stage7_elementary_competition"
PDF_DIR = LOCAL / "elmc_text_pdfs"
NAMES = {edition: f"{edition}_文字整理版.pdf" for edition in EDITIONS}
SAFE_SECRETS = (ROOT/".streamlit/secrets.toml", Path(r"C:\MathAI_G5_Pilot\.streamlit\secrets.toml"),
                Path(r"C:\MathAI_G6_Pilot\.streamlit\secrets.toml"), Path(r"C:\MathAI_G8_Pilot\.streamlit\secrets.toml"))

def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False)+"\n" for x in rows), encoding="utf-8")

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()] if path.is_file() else []

def extract() -> tuple[list[dict], dict]:
    missing = [name for name in NAMES.values() if not (PDF_DIR/name).is_file()]
    if missing: raise RuntimeError("MISSING_ELMC_PDFS:"+",".join(missing))
    parsed = [parse_pdf(PDF_DIR/name, edition) for edition, name in NAMES.items()]
    raw = [q for pdf in parsed for q in pdf["questions"]]
    unique: list[dict] = []; seen: set[str] = set(); duplicates = 0
    for row in raw:
        if row["fingerprint"] in seen: duplicates += 1; continue
        seen.add(row["fingerprint"]); unique.append(row)
    manifest = {"profile":"ELEMENTARY_COMPETITION", "competition_family":"ELMC",
                "source_type":"USER_PROVIDED_DERIVED_TEXT_PDF", "source_quality":"OCR_DERIVED_TEXT",
                "pdfs":[{k:v for k,v in x.items() if k != "questions"} for x in parsed]}
    write_json(LOCAL/"elmc_pdf_manifest.json", manifest)
    write_jsonl(LOCAL/"elmc_extracted_questions.jsonl", unique)
    write_json(LOCAL/"elmc_solution_links.json", [{"fingerprint":x["fingerprint"],"has_solution":x["has_solution"],"solution_source_page":x["solution_source_page"]} for x in unique])
    quality = [x for x in unique if x["source_quality_risks"]]
    write_json(LOCAL/"elmc_quality_queue.json", quality)
    audit = {"pdfs":len(parsed), "editions":list(EDITIONS), "pages":sum(x["pages"] for x in parsed),
             "sections":sorted({s for x in parsed for s in x["sections"]}), "raw_questions":len(raw),
             "unique_questions":len(unique), "duplicates":duplicates, "questions_with_answers":0,
             "questions_with_solutions":sum(x["has_solution"] for x in unique),
             "ocr_review_required":len(quality), "source_invalid":0,
             "usable_for_mapping":sum(not x["source_quality_risks"] for x in unique)}
    write_json(LOCAL/"elmc_corpus_audit.json", audit)
    return unique, audit

def prompt(row: dict, skills: dict, micros: dict) -> str:
    packet = build_candidate_packet({"fingerprint":row["fingerprint"],"question_text":row["question_text"],"unit":"ELMC","knowledge_tag":"competition"}, list(skills.values()), list(micros.values()), skill_limit=18, micro_limit=60)
    context={"skills":packet["skill_candidates"],"micros":packet["micro_candidates"]}
    return """Classify one real ELMC elementary math competition question. Return JSON only. Never invent IDs. The micro parent must equal the primary skill. Difficulty alone is not out of elementary scope.
Required: scope (ELEMENTARY_COMPETITION or OUT_OF_SCOPE_ELEMENTARY), foundation_grade (G1..G6 or UNKNOWN), foundation_skill_id, foundation_micro_skill_id, secondary_skill_ids (array), competition_topic, thinking_skills (array), assessment_style, difficulty, confidence (0..1), reason.
Allowed topics: %s
Allowed thinking skills: %s
QUESTION:\n%s\nCANDIDATES:\n%s""" % (", ".join(COMPETITION_TOPICS), ", ".join(sorted(COMPETITION_THINKING_SKILLS)), row["question_text"], json.dumps(context,ensure_ascii=False))

def run_provider(name: str, rows: list[dict], skills: dict, micros: dict) -> list[dict]:
    path=LOCAL/f"elmc_{name}_results.jsonl"; done={x["fingerprint"]:x for x in read_jsonl(path)}
    for result in done.values():
        errors=validate_mapping(result,skills,micros,set(COMPETITION_TOPICS),set(COMPETITION_THINKING_SKILLS)); result["validation_errors"]=errors; result["validation_status"]="VALID" if not errors else "REJECT"
    old=os.getenv("AI_PROVIDER"); os.environ["AI_PROVIDER"]=name
    try:
        provider=get_ai_provider(secret_paths=SAFE_SECRETS)
        with path.open("a",encoding="utf-8") as h:
            for q in rows:
                if q["fingerprint"] in done: continue
                p=prompt(q,skills,micros); response=provider.generate_json(p); result=dict(response.parsed_json or {})
                result.update({"fingerprint":q["fingerprint"],"provider":name,"model":response.model,"status":"COMPLETED","latency_ms":round(response.latency_ms,2),"input_tokens":response.input_tokens,"output_tokens":response.output_tokens,"total_tokens":response.total_tokens,"prompt_fingerprint":hashlib.sha256(p.encode()).hexdigest()})
                errors=validate_mapping(result,skills,micros,set(COMPETITION_TOPICS),set(COMPETITION_THINKING_SKILLS)); result["validation_errors"]=errors; result["validation_status"]="VALID" if not errors else "REJECT"
                h.write(json.dumps(result,ensure_ascii=False)+"\n"); h.flush(); done[q["fingerprint"]]=result
    finally:
        if old is None: os.environ.pop("AI_PROVIDER",None)
        else: os.environ["AI_PROVIDER"]=old
    return [done[q["fingerprint"]] for q in rows if q["fingerprint"] in done]

def combine_and_review(unique: list[dict], ds: list[dict], gm: list[dict]) -> dict:
    d={x["fingerprint"]:x for x in ds}; g={x["fingerprint"]:x for x in gm}; results=[]; review=[]
    major=("scope","foundation_grade","foundation_skill_id","foundation_micro_skill_id","competition_topic")
    for q in unique:
        if q["source_quality_risks"]:
            review.append(("P2",q,"OCR / notation suspect")); continue
        a,b=d.get(q["fingerprint"]),g.get(q["fingerprint"])
        if not a or not b: review.append(("P0",q,"provider incomplete")); continue
        if a["validation_status"] != "VALID" or b["validation_status"] != "VALID": review.append(("P0",q,"invalid Skill/Micro"))
        elif any(a.get(k)!=b.get(k) for k in major): review.append(("P1",q,"provider major disagreement"))
        elif a.get("thinking_skills")!=b.get("thinking_skills"): review.append(("P5",q,"minor thinking-skill disagreement"))
        elif a.get("scope")=="OUT_OF_SCOPE_ELEMENTARY": review.append(("P3",q,"out-of-scope suspect"))
        elif str(a.get("difficulty")).upper()=="HIGH" or a.get("secondary_skill_ids"): review.append(("P4",q,"high difficulty / cross-unit"))
        results.append({"fingerprint":q["fingerprint"],"deepseek":a,"gemini":b,"agreement":"MAJOR" if any(a.get(k)!=b.get(k) for k in major) else "COMPLETE" if a.get("thinking_skills")==b.get("thinking_skills") else "MINOR_DISAGREEMENT"})
    write_jsonl(LOCAL/"elmc_mapping_results.jsonl",results)
    for filename in ("elmc_human_review_queue.csv","ELMC_HUMAN_REVIEW_SIMPLE.csv"):
        with (LOCAL/filename).open("w",encoding="utf-8-sig",newline="") as h:
            w=csv.writer(h); w.writerow(["priority","fingerprint","edition","section","question_number","question_text","reason","human_scope","human_skill","human_micro","human_note"])
            for p,q,r in sorted(review,key=lambda x:(x[0],x[1]["edition"],x[1]["section"],x[1]["question_number"])): w.writerow([p,q["fingerprint"],q["edition"],q["section"],q["question_number"],q["question_text"],r,"","","",""])
    # Preserve every prior complete IMC record, including the public-acquisition corpus and legacy inventory.
    imc_candidates=read_jsonl(LOCAL/"competition_unique_questions.jsonl")
    imc_candidates += [x for x in read_jsonl(LOCAL/"competition_raw_questions.jsonl") if x.get("extraction_status")=="COMPLETE"]
    imc_by_fp={x.get("fingerprint"):x for x in imc_candidates if x.get("fingerprint")}
    imc=list(imc_by_fp.values()); imc_fps=set(imc_by_fp); usable=[x for x in unique if not x["source_quality_risks"]]; cross=sum(x["fingerprint"] in imc_fps for x in usable)
    combined=[dict(x,source_family=x.get("source_family") or "IMC") for x in imc]+[dict(x,source_family="ELMC") for x in usable if x["fingerprint"] not in imc_fps]
    write_jsonl(LOCAL/"competition_corpus_v2.jsonl",combined)
    return {"results":results,"review":review,"imc":len(imc),"usable":len(usable),"cross":cross,"combined":len(combined)}

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--extract-only",action="store_true"); args=ap.parse_args()
    unique,audit=extract(); skills,micros=load_catalog(ROOT); usable=[x for x in unique if not x["source_quality_risks"]]
    ds=gm=[]
    if not args.extract_only:
        ds=run_provider("deepseek",usable,skills,micros); gm=run_provider("gemini",usable,skills,micros)
    combined=combine_and_review(unique,ds,gm)
    audit.update({"deepseek_mapped":len(ds),"gemini_mapped":len(gm),"combined":combined})
    write_json(LOCAL/"elmc_corpus_audit.json",audit); print(json.dumps({k:v for k,v in audit.items() if k!="combined"},ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
