"""Ingest coverage-set V2 rows 8-12 and enforce missing-image quality."""
from __future__ import annotations

import json,sys
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from services.math_extraction_quality import assess_fraction_structure_loss,assess_missing_required_image
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES,load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST,GT,CLEANING,PILOT,_csv,_jsonl,_write_csv
from scripts.stage7_private_jh_coverage_batch1 import NEXT_TEACHER as TEACHER_V2,_source_metadata

TEACHER_V3=PILOT/"PRIVATE_JH_TEACHER_COVERAGE_SET_V3.csv"
STATUS=PILOT/"coverage_review_batch2_status.json"
BATCH={
 8:{"scope":"PRIVATE_JH","skill":"G05-S-VOLUME-01","micro":"G05-S-VOLUME-01-R1","secondary":[],"assessment":"REVERSE_REASONING","note":"正方體 12 條邊總長為 60 公分，反求邊長後求體積；核心為體積公式中的逆向求未知。"},
 9:{"scope":"SOURCE_INVALID_PENDING_REEXTRACTION","skill":None,"micro":None,"secondary":[],"assessment":None,"candidate":"G05-S-ANGLE-01","reason":"MISSING_REQUIRED_DIAGRAM","note":"題幹依賴右圖，但 extraction/review artifact 未保存必要圖形資訊。"},
10:{"scope":"PRIVATE_JH","skill":"G06-N-BASE-02","micro":"G06-N-BASE-02-T1","secondary":["G05-N-PERCENT-01"],"assessment":"MULTI_STEP","note":"商品先 35% off，再依剩餘價格打 85 折；核心為連續比較量=基準量×倍數。"},
11:{"scope":"PRIVATE_JH","skill":"G05-N-TIME-02","micro":"G05-N-TIME-02-T1","secondary":[],"assessment":"MULTI_STEP","note":"總上場人時=6×60，再平均分配給9人；Speed 不作 Primary 或 Secondary。"},
12:{"scope":"PRIVATE_JH","skill":"G06-N-BASE-02","micro":"G06-N-BASE-02-X1","secondary":["G05-N-MASSUNIT-01"],"assessment":"CROSS_UNIT","note":"公噸換算後比較大象與河馬重量倍數；重量單位換算為 supporting skill。"},
}

def _locate()->dict[int,dict[str,Any]]:
    rows={int(r["序號"]):r for r in _csv(TEACHER_V2)};manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"));by_text:dict[str,list[dict[str,Any]]]={}
    for q in manifest["questions"]:by_text.setdefault(q["question_text"],[]).append(q)
    resolved={};seen=set()
    for number in BATCH:
        if number not in rows:raise RuntimeError("COVERAGE_SET_NUMBER_MISSING")
        matches=by_text.get(rows[number]["題目"],[])
        if len(matches)!=1:raise RuntimeError("COVERAGE_QUESTION_NOT_UNIQUE")
        q=matches[0];fp=q["fingerprint"]
        if fp in seen or q["question_text"]!=rows[number]["題目"]:raise RuntimeError("COVERAGE_LOCATOR_MISMATCH")
        seen.add(fp);resolved[number]={"coverage":rows[number],"question":q,"fingerprint":fp}
    return resolved

def _validate_ids()->None:
    skills,micros=load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES)
    for number,spec in BATCH.items():
        if spec["skill"] is None:continue
        if spec["skill"] not in skills:raise RuntimeError(f"UNKNOWN_SKILL:{number}")
        if spec["micro"] not in micros:raise RuntimeError(f"UNKNOWN_MICRO:{number}")
        if micros[spec["micro"]]["parent_skill_id"]!=spec["skill"]:raise RuntimeError(f"MICRO_PARENT_MISMATCH:{number}")
        if any(sid not in skills for sid in spec["secondary"]):raise RuntimeError(f"UNKNOWN_SECONDARY:{number}")

def ingest(*,force:bool=False)->dict[str,Any]:
    if not force and TEACHER_V3.is_file() and STATUS.is_file():
        status=json.loads(STATUS.read_text(encoding="utf-8-sig"))
        # Later teacher batches legitimately extend the shared cleaning queue.
        # Report its current totals without regenerating or overwriting V3.
        if CLEANING.is_file():
            current=json.loads(CLEANING.read_text(encoding="utf-8-sig")).get("items",[])
            status["source_cleaning_queue_total"]=len(current)
            status["human_coverage"]["missing_image_queue"]=sum(
                row.get("status")=="NEEDS_IMAGE_REEXTRACTION" for row in current)
        return status
    required=(TEACHER_V2,MANIFEST,GT,CLEANING)
    if not all(p.is_file() for p in required):raise RuntimeError("MISSING_COVERAGE_BATCH2_INPUT")
    resolved=_locate();_validate_ids();existing={r["fingerprint"]:r for r in _jsonl(GT)};now=datetime.now(timezone.utc).isoformat()
    for number,spec in BATCH.items():
        locator=resolved[number];fp=locator["fingerprint"];old=existing.get(fp,{})
        existing[fp]={"fingerprint":fp,"coverage_set_version":"V2","coverage_set_number":number,"source_review_number":int(locator["coverage"]["原Review序號"]),
          "human_scope":spec["scope"],"human_primary_skill_id":spec["skill"],"human_primary_micro_id":spec["micro"],"human_secondary_skill_ids":spec["secondary"],
          "human_assessment_style":spec["assessment"],"human_note":spec["note"],"validation_source":"TEACHER_APPROVED","validated_at":old.get("validated_at") or now,
          "source_status":"HUMAN_VALIDATED" if spec["skill"] else "SOURCE_IMAGE_REQUIRED"}
    GT.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in sorted(existing.values(),key=lambda x:(int(x.get("source_review_number") or 0),x["fingerprint"]))),encoding="utf-8")
    cleaning=json.loads(CLEANING.read_text(encoding="utf-8-sig"));items={r["fingerprint"]:r for r in cleaning.get("items",[]) if r.get("detection_source")!="DETERMINISTIC_MISSING_IMAGE_GATE"}
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"));manifest_by_fp={q["fingerprint"]:q for q in manifest["questions"]}
    # Repair queue completeness deterministically if an older regression was
    # rerun: every non-GT source adjudication must remain represented.
    for record in existing.values():
        if record["source_status"]=="HUMAN_VALIDATED" or record["fingerprint"] in items:continue
        source=manifest_by_fp.get(record["fingerprint"],{})
        items[record["fingerprint"]]={"fingerprint":record["fingerprint"],"source_document":source.get("source_url"),"question_number":source.get("question_number"),
          "reason":"SOURCE_QUALITY_REVIEW","status":"NEEDS_IMAGE_REEXTRACTION" if record["source_status"]=="SOURCE_IMAGE_REQUIRED" else "NEEDS_REEXTRACTION","replacement_status":"PENDING"}
    for candidate in manifest["questions"]:
        fp=candidate["fingerprint"]
        if fp in items or fp in existing:continue
        fraction=assess_fraction_structure_loss(candidate["question_text"],source_metadata=_source_metadata(candidate),pdf_text_discrepancy=False)
        if fraction.status=="SOURCE_NEEDS_REEXTRACTION":
            items[fp]={"fingerprint":fp,"source_document":candidate.get("source_url"),"question_number":candidate.get("question_number"),"reason":"MATH_FRACTION_NOTATION_LOST",
              "status":"NEEDS_REEXTRACTION","replacement_status":"PENDING","detection_source":"DETERMINISTIC_MULTI_SIGNAL_GATE"}
    image_locator=resolved[9];q=image_locator["question"]
    gate=assess_missing_required_image(q["question_text"],extracted_record=q)
    if gate.status!="SOURCE_IMAGE_REQUIRED":raise RuntimeError("MISSING_IMAGE_EVIDENCE_NOT_REPRODUCED")
    items[image_locator["fingerprint"]]={"fingerprint":image_locator["fingerprint"],"coverage_set_version":"V2","coverage_set_number":9,"source_school":q.get("source_school"),
      "source_year":q.get("source_year"),"source_document":q.get("source_url"),"question_number":q.get("question_number"),"page_number":2,"figure_reference":"右圖",
      "candidate_skill":"G05-S-ANGLE-01","reason":"MISSING_REQUIRED_DIAGRAM","status":"NEEDS_IMAGE_REEXTRACTION","replacement_status":"PENDING","pdf_visual_verification":"DIAGRAM_PRESENT"}
    processed={x["fingerprint"] for x in resolved.values()};new_risks=[]
    existing_gt=set(existing);existing_cleaning=set(items)
    for candidate in manifest["questions"]:
        fp=candidate["fingerprint"]
        if fp in processed or fp in existing_gt or fp in existing_cleaning:continue
        risk=assess_missing_required_image(candidate["question_text"],extracted_record=candidate)
        if risk.status=="SOURCE_IMAGE_REQUIRED":
            new_risks.append(fp);items[fp]={"fingerprint":fp,"source_school":candidate.get("source_school"),"source_year":candidate.get("source_year"),
              "source_document":candidate.get("source_url"),"question_number":candidate.get("question_number"),"page_number":None,"figure_reference":"EXPLICIT_TEXT_REFERENCE",
              "candidate_skill":None,"reason":"MISSING_REQUIRED_DIAGRAM","status":"NEEDS_IMAGE_REEXTRACTION","replacement_status":"PENDING","detection_source":"DETERMINISTIC_MISSING_IMAGE_GATE"}
    CLEANING.write_text(json.dumps({"items":list(items.values())},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    remove=processed|set(new_risks);rows=_csv(TEACHER_V2);by_text={q["question_text"]:q for q in manifest["questions"]};remaining=[r for r in rows if by_text[r["題目"]]["fingerprint"] not in remove]
    for index,row in enumerate(remaining,1):row["序號"]=index
    _write_csv(TEACHER_V3,remaining,list(rows[0]))
    valid=[r for r in existing.values() if r["source_status"]=="HUMAN_VALIDATED"];invalid=[r for r in existing.values() if r["source_status"]!="HUMAN_VALIDATED"]
    qmap={q["fingerprint"]:q for q in manifest["questions"]};topics={t for r in valid for t in qmap.get(r["fingerprint"],{}).get("topic_groups",[])};styles={r.get("human_assessment_style") for r in valid if r.get("human_assessment_style")}
    status={"reviewed":5,"human_validated":4,"image_reextraction":1,"id_validation_failures":0,"parent_failures":0,"missing_image_gate":"READY",
      "new_missing_image_risks_found":len(new_risks),"source_cleaning_queue_total":len(items),"human_coverage":{"direct_human_gt":len(valid),"source_reextraction":len(invalid),
        "missing_image_queue":sum(r.get("status")=="NEEDS_IMAGE_REEXTRACTION" for r in items.values()),"remaining_teacher_review":len(remaining),"unique_validated_skills":len({r["human_primary_skill_id"] for r in valid}),
        "unique_validated_micros":len({r["human_primary_micro_id"] for r in valid}),"validated_topics":len(topics),"validated_assessment_styles":len(styles)},
      "teacher_review":{"previous_questions":len(rows),"removed_by_human_gt":4,"removed_for_source_cleaning":1+sum(fp in {by_text[r["題目"]]["fingerprint"] for r in rows} for fp in new_risks),"remaining_questions":len(remaining)},
      "api_calls":0,"production_reads":0,"production_writes":0}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");return status

if __name__=="__main__":print(json.dumps(ingest(),ensure_ascii=False))
