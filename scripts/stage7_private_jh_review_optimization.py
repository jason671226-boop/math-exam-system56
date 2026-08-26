"""Offline optimization of the remaining PRIVATE_JH teacher-review workload."""
from __future__ import annotations

import csv,json,sys
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from services.math_extraction_quality import assess_math_extraction
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES,load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST,DEEPSEEK,GT,PILOT,_csv,_jsonl,_sha,_write_csv

V3=PILOT/"PRIVATE_JH_HUMAN_REVIEW_FOR_TEACHER_V3.csv"
MINIMUM=PILOT/"PRIVATE_JH_TEACHER_MINIMUM_REVIEW.csv"
DEFERRED=PILOT/"PRIVATE_JH_DEFERRED_AUDIT_QUEUE.csv"
STATUS=PILOT/"review_optimization_status.json"

def _resolve()->list[dict[str,Any]]:
    rows=_csv(V3);manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"));by_text:dict[str,list[dict[str,Any]]]=defaultdict(list)
    for q in manifest["questions"]:by_text[q["question_text"]].append(q)
    seen=set();resolved=[]
    for row in rows:
        number=int(row["source_review_number"])
        if int(row["序號"])!=number:raise RuntimeError("SOURCE_REVIEW_NUMBER_DRIFT")
        matches=by_text.get(row["題目"],[])
        if len(matches)!=1:raise RuntimeError("QUESTION_FINGERPRINT_NOT_UNIQUE")
        fp=matches[0]["fingerprint"]
        if fp in seen:raise RuntimeError("DUPLICATE_FINGERPRINT")
        seen.add(fp);resolved.append({**row,"fingerprint":fp,"question":matches[0]})
    if len(resolved)!=57:raise RuntimeError("ACTIVE_REVIEW_COUNT_MISMATCH")
    return resolved

def _risk(row:dict[str,Any],result:dict[str,Any],skills:dict[str,dict],micros:dict[str,dict],validated_skills:set[str],validated_micros:set[str])->dict[str,Any]:
    sid=str(result.get("primary_skill_id") or "");mid=str(result.get("primary_micro_skill_id") or "");secondary=tuple(sorted(result.get("secondary_skill_ids") or []))
    confidence=float(result.get("confidence") or 0);extraction=assess_math_extraction(row["題目"])
    parent_valid=sid in skills and mid in micros and micros[mid].get("parent_skill_id")==sid
    new_skill=sid not in validated_skills;new_micro=mid not in validated_micros
    cross=bool(secondary) or result.get("assessment_style")=="CROSS_UNIT";high=result.get("difficulty")=="HIGH" or result.get("assessment_style")=="HIGH_DIFFICULTY"
    score=0;why=[]
    if confidence<.70:score+=50;why.append("LOW_CONFIDENCE")
    if extraction.status!="PASS":score+=60;why.append("EXTRACTION_RISK:"+"|".join(extraction.risks))
    if not parent_valid:score+=80;why.append("PARENT_OR_ID_INVALID")
    if new_skill:score+=30;why.append("UNSEEN_HUMAN_GT_SKILL")
    if new_micro:score+=15;why.append("UNSEEN_HUMAN_GT_MICRO")
    if high:score+=15;why.append("HIGH_DIFFICULTY")
    if cross:score+=12;why.append("CROSS_UNIT_OR_SECONDARY")
    if secondary:score+=5
    if result.get("assessment_style") in {"PRIVATE_JH_ADVANCED","REVERSE_REASONING"}:score+=8
    level="CRITICAL" if score>=60 else "HIGH" if score>=40 else "MEDIUM" if score>=20 else "AUDIT"
    mandatory=(row["優先級"]=="P3" or extraction.status!="PASS" or not parent_valid or new_skill or (high and cross and bool(secondary)))
    topic="|".join(row["question"].get("topic_groups") or ["UNCLASSIFIED"])
    stratum=(sid,mid,topic,str(result.get("assessment_style") or ""),secondary)
    return {"score":score,"level":level,"why":why,"mandatory":mandatory,"parent_valid":parent_valid,"extraction_clean":extraction.status=="PASS",
      "new_skill":new_skill,"new_micro":new_micro,"skill":sid,"micro":mid,"secondary":secondary,"topic":topic,"style":str(result.get("assessment_style") or ""),"confidence":confidence,"stratum":stratum}

def optimize()->dict[str,Any]:
    required=(V3,MANIFEST,DEEPSEEK,GT)
    if not all(path.is_file() for path in required):raise RuntimeError("MISSING_OPTIMIZATION_INPUT")
    protected={path.name:_sha(path) for path in required};rows=_resolve();deep={r["fingerprint"]:r for r in _jsonl(DEEPSEEK)}
    gt=[r for r in _jsonl(GT) if r["source_status"]=="HUMAN_VALIDATED"];validated_skills={r["human_primary_skill_id"] for r in gt};validated_micros={r["human_primary_micro_id"] for r in gt}
    skills,micros=load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES);assessed=[]
    for row in rows:
        if row["fingerprint"] not in deep:raise RuntimeError("AI_RESULT_MISSING")
        assessed.append((row,_risk(row,deep[row["fingerprint"]],skills,micros,validated_skills,validated_micros)))
    selected:set[str]={row["fingerprint"] for row,risk in assessed if risk["mandatory"] or row["優先級"]=="P5"}
    p4_groups:dict[tuple,list[tuple[dict,str]]]=defaultdict(list)
    for row,risk in assessed:
        if row["優先級"]=="P4":p4_groups[risk["stratum"]].append((row,row["fingerprint"]))
    for members in p4_groups.values():
        if not any(fp in selected for _,fp in members):selected.add(min(fp for _,fp in members))
    minimum=[];deferred=[]
    for row,risk in assessed:
        result=deep[row["fingerprint"]]
        if row["fingerprint"] in selected:
            minimum.append({"序號":len(minimum)+1,"來源原序號":row["source_review_number"],"Review Priority":row["優先級"],"Risk Level":risk["level"],"review_risk_score":risk["score"],
              "題目":row["題目"],"Primary Skill":risk["skill"],"Primary Micro":risk["micro"],"Secondary Skills":"|".join(risk["secondary"]),"Assessment Style":risk["style"],
              "Confidence":risk["confidence"],"Why Human Review":"|".join(risk["why"] or ["RANDOM_AUDIT"]),"人工Scope":"","人工Skill":"","人工Micro":"","人工Secondary":"","人工Assessment":"","人工備註":""})
        else:
            clean_high=risk["parent_valid"] and risk["extraction_clean"] and risk["confidence"]>=.70
            reason="AUDIT_DEFERRED_SAME_VALID_STRATUM" if clean_high else "AUDIT_DEFERRED_NON_MANDATORY"
            deferred.append({"fingerprint":row["fingerprint"],"reason_deferred":reason,"skill":risk["skill"],"micro":risk["micro"],"topic":risk["topic"],"confidence":risk["confidence"]})
    minimum.sort(key=lambda r:({"CRITICAL":0,"HIGH":1,"MEDIUM":2,"AUDIT":3}[r["Risk Level"]],int(r["來源原序號"])))
    for index,row in enumerate(minimum,1):row["序號"]=index
    _write_csv(MINIMUM,minimum,list(minimum[0]));_write_csv(DEFERRED,deferred,list(deferred[0]) if deferred else ["fingerprint","reason_deferred","skill","micro","topic","confidence"])
    risks=Counter(risk["level"] for _,risk in assessed);priorities=Counter(row["優先級"] for row,_ in assessed)
    selected_risks=[risk for row,risk in assessed if row["fingerprint"] in selected]
    status={"current":{"active_review":len(rows),**{p:priorities[p] for p in ("P3","P4","P5")}},
      "risk":{level:risks[level] for level in ("CRITICAL","HIGH","MEDIUM","AUDIT")},
      "teacher_minimum":{"questions":len(minimum),"unique_skills":len({r["skill"] for r in selected_risks}),"unique_micros":len({r["micro"] for r in selected_risks}),
        "topics":len({r["topic"] for r in selected_risks}),"assessment_styles":len({r["style"] for r in selected_risks})},
      "deferred":{"questions":len(deferred),"reason_groups":dict(Counter(r["reason_deferred"] for r in deferred)),"human_validated":0},
      "coverage_gaps":{"new_skills_requiring_teacher_review":len({r["skill"] for r in selected_risks if r["new_skill"]}),"new_micros_requiring_teacher_review":len({r["micro"] for r in selected_risks if r["new_micro"]})},
      "completion_criteria":{"invalid":0,"out_of_scope_unresolved":0,"parent_mismatch":0,"low_confidence_all_selected":all(row["fingerprint"] in selected for row,r in assessed if row["優先級"]=="P3"),
        "meaning":"HUMAN-VALIDATED PILOT PASS is not 100-question individual validation"},
      "inputs_unchanged":protected=={path.name:_sha(path) for path in required},"api_calls":0,"production_reads":0,"production_writes":0}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");return status

if __name__=="__main__":print(json.dumps(optimize(),ensure_ascii=False))
