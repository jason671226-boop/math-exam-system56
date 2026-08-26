"""Ingest coverage-set rows 8-13 and harden fraction extraction checks."""
from __future__ import annotations

import csv,json,sys
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from services.math_extraction_quality import assess_fraction_structure_loss
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES,load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST,GT,CLEANING,PILOT,_csv,_jsonl,_write_csv
from scripts.stage7_private_jh_minimum_coverage import TEACHER_SET,DEFERRED

NEXT_TEACHER=PILOT/"PRIVATE_JH_TEACHER_COVERAGE_SET_V2.csv"
STATUS=PILOT/"coverage_review_batch1_status.json"
PDF_ROOT=PILOT.parent/"source_pdfs"
PDF_BY_SOURCE={"110":"YONGNIAN_110_EXAM_MATH.pdf","112":"MINGDA_112_EXAM_MATH.pdf","113":"MINGDA_113_EXAM_MATH.pdf"}
BATCH={
 8:{"scope":"PRIVATE_JH","skill":"G05-R-MULTISTEP-01","micro":"G05-R-MULTISTEP-01-V1","secondary":[],"assessment":"MULTI_STEP","note":"24瓶一箱、6箱共2448元，判斷每瓶單價的正確算式；核心為解析多步驟情境並轉成單一算式。"},
 9:{"scope":"PRIVATE_JH","skill":"G05-S-SURFACE-01","micro":"G05-S-SURFACE-01-X1","secondary":["G05-S-VOLUME-01"],"assessment":"CROSS_UNIT","note":"由相同體積先求長方體未知邊長，再計算表面積。"},
10:{"scope":"SOURCE_INVALID_PENDING_REEXTRACTION","skill":None,"micro":None,"secondary":[],"assessment":None,"reason":"MATH_FRACTION_NOTATION_LOST","note":"分數及選項分數在抽取後分數線遺失。"},
11:{"scope":"SOURCE_INVALID_PENDING_REEXTRACTION","skill":None,"micro":None,"secondary":[],"assessment":None,"reason":"MATH_FRACTION_NOTATION_LOST","note":"分數加法被抽成連續整數字串。"},
12:{"scope":"PRIVATE_JH","skill":"G05-S-SYM-01","micro":"G05-S-SYM-01-V1","secondary":[],"assessment":"PRIVATE_JH_CLASSIC","note":"依圖形判斷對稱軸、對稱點與對稱邊。"},
13:{"scope":"SOURCE_INVALID_PENDING_REEXTRACTION","skill":None,"micro":None,"secondary":[],"assessment":None,"reason":"MATH_FRACTION_NOTATION_LOST","note":"多個分數加減的分數線全部遺失。"},
}

def _locate()->tuple[dict[int,dict[str,Any]],dict[str,dict[str,Any]]]:
    coverage=_csv(TEACHER_SET);manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"));by_text:dict[str,list[dict[str,Any]]]={}
    for q in manifest["questions"]:by_text.setdefault(q["question_text"],[]).append(q)
    rows={int(row["序號"]):row for row in coverage};resolved={};qmap={}
    for number in BATCH:
        if number not in rows:raise RuntimeError("COVERAGE_SET_NUMBER_MISSING")
        matches=by_text.get(rows[number]["題目"],[])
        if len(matches)!=1:raise RuntimeError("COVERAGE_QUESTION_NOT_UNIQUE")
        fp=matches[0]["fingerprint"]
        if fp in qmap:raise RuntimeError("COVERAGE_FINGERPRINT_DUPLICATE")
        # The coverage row, resolved manifest fingerprint, and exact text form one immutable locator.
        if matches[0]["question_text"]!=rows[number]["題目"]:raise RuntimeError("COVERAGE_TEXT_MISMATCH")
        resolved[number]={"coverage":rows[number],"question":matches[0],"fingerprint":fp};qmap[fp]=matches[0]
    return resolved,qmap

def _validate_ids()->tuple[dict[str,dict],dict[str,dict]]:
    skills,micros=load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES)
    for number,spec in BATCH.items():
        if spec["skill"] is None:continue
        if spec["skill"] not in skills:raise RuntimeError(f"UNKNOWN_SKILL:{number}")
        if spec["micro"] not in micros:raise RuntimeError(f"UNKNOWN_MICRO:{number}")
        if micros[spec["micro"]]["parent_skill_id"]!=spec["skill"]:raise RuntimeError(f"MICRO_PARENT_MISMATCH:{number}")
        if any(sid not in skills for sid in spec["secondary"]):raise RuntimeError(f"UNKNOWN_SECONDARY:{number}")
    return skills,micros

def _source_metadata(q:dict[str,Any])->dict[str,Any]:
    year=str(q.get("source_year") or "");pdf=PDF_ROOT/PDF_BY_SOURCE.get(year,"")
    return {"official_pdf":pdf.is_file(),"question_number":q.get("question_number"),"fraction_expected":"分數" in (q.get("topic_groups") or [])}

def ingest(*,force:bool=False)->dict[str,Any]:
    if not force and NEXT_TEACHER.is_file() and STATUS.is_file():
        return json.loads(STATUS.read_text(encoding="utf-8-sig"))
    required=(TEACHER_SET,DEFERRED,MANIFEST,GT,CLEANING)
    if not all(path.is_file() for path in required):raise RuntimeError("MISSING_COVERAGE_BATCH_INPUT")
    resolved,_=_locate();_validate_ids();existing={r["fingerprint"]:r for r in _jsonl(GT)};now=datetime.now(timezone.utc).isoformat()
    for number,spec in BATCH.items():
        fp=resolved[number]["fingerprint"];old=existing.get(fp,{})
        existing[fp]={"fingerprint":fp,"coverage_set_number":number,"source_review_number":int(resolved[number]["coverage"]["原Review序號"]),"human_scope":spec["scope"],
          "human_primary_skill_id":spec["skill"],"human_primary_micro_id":spec["micro"],"human_secondary_skill_ids":spec["secondary"],"human_assessment_style":spec["assessment"],
          "human_note":spec["note"],"validation_source":"TEACHER_APPROVED","validated_at":old.get("validated_at") or now,
          "source_status":"HUMAN_VALIDATED" if spec["skill"] else "SOURCE_NEEDS_REEXTRACTION"}
    GT.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in sorted(existing.values(),key=lambda x:(int(x.get("source_review_number") or 0),x["fingerprint"]))),encoding="utf-8")
    cleaning=json.loads(CLEANING.read_text(encoding="utf-8-sig"));items={r["fingerprint"]:r for r in cleaning.get("items",[])
        if r.get("detection_source")!="DETERMINISTIC_MULTI_SIGNAL_GATE"}
    for number in (10,11,13):
        locator=resolved[number];q=locator["question"]
        evidence=assess_fraction_structure_loss(q["question_text"],source_metadata=_source_metadata(q),pdf_text_discrepancy=True)
        if evidence.status!="SOURCE_NEEDS_REEXTRACTION":raise RuntimeError("TEACHER_EXTRACTION_EVIDENCE_NOT_REPRODUCED")
        items[locator["fingerprint"]]={"fingerprint":locator["fingerprint"],"coverage_set_number":number,"source_document":q.get("source_url"),"question_number":q.get("question_number"),
          "reason":"MATH_FRACTION_NOTATION_LOST","status":"NEEDS_REEXTRACTION","replacement_status":"PENDING","pdf_visual_verification":"FRACTION_BAR_PRESENT"}
    processed={x["fingerprint"] for x in resolved.values()};coverage=_csv(TEACHER_SET);manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"));by_text={q["question_text"]:q for q in manifest["questions"]};by_fp={q["fingerprint"]:q for q in manifest["questions"]}
    new_risks=[]
    already_cleaning=set(items)
    for row in _csv(DEFERRED)+coverage:
        text=row.get("題目");q=by_text.get(text) if text else by_fp.get(row.get("fingerprint"));fp=q and q["fingerprint"]
        if q and not text:text=q["question_text"]
        if not q or fp in processed or fp in already_cleaning:continue
        risk=assess_fraction_structure_loss(text,source_metadata=_source_metadata(q),pdf_text_discrepancy=False)
        if risk.status=="SOURCE_NEEDS_REEXTRACTION":
            new_risks.append(fp);items[fp]={"fingerprint":fp,"source_document":q.get("source_url"),"question_number":q.get("question_number"),"reason":"MATH_FRACTION_NOTATION_LOST",
              "status":"NEEDS_REEXTRACTION","replacement_status":"PENDING","detection_source":"DETERMINISTIC_MULTI_SIGNAL_GATE"}
    CLEANING.write_text(json.dumps({"items":list(items.values())},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    remove=processed|set(new_risks);remaining=[]
    for row in coverage:
        q=by_text.get(row["題目"])
        if q and q["fingerprint"] not in remove:remaining.append(row)
    for index,row in enumerate(remaining,1):row["序號"]=index
    _write_csv(NEXT_TEACHER,remaining,list(coverage[0]))
    status={"reviewed":6,"human_validated":3,"source_reextraction":3,"resolved_skills":3,"resolved_micros":3,"parent_failures":0,
      "new_extraction_risk_questions":len(new_risks),"teacher_questions_remaining":len(remaining),"api_calls":0,"production_reads":0,"production_writes":0}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");return status

if __name__=="__main__":print(json.dumps(ingest(),ensure_ascii=False))
