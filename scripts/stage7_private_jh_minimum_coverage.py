"""Deterministic greedy set-cover plans for PRIVATE_JH human review."""
from __future__ import annotations

import csv,json,math,sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES,load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import DEEPSEEK,GT,PILOT,_jsonl,_write_csv
from scripts.stage7_private_jh_review_optimization import _resolve,_risk

TEACHER_SET=PILOT/"PRIVATE_JH_TEACHER_COVERAGE_SET.csv"
DEFERRED=PILOT/"PRIVATE_JH_DEFERRED_AUDIT_V2.csv"
STATUS=PILOT/"minimum_coverage_status.json"
PLAN_TARGETS={"PLAN_A_STRICT":(.80,0.0),"PLAN_B_BALANCED":(.70,.80),"PLAN_C_MINIMUM":(.60,.70)}

def _items()->list[dict[str,Any]]:
    rows=_resolve();deep={r["fingerprint"]:r for r in _jsonl(DEEPSEEK)};gt=[r for r in _jsonl(GT) if r["source_status"]=="HUMAN_VALIDATED"]
    validated_skills={r["human_primary_skill_id"] for r in gt};validated_micros={r["human_primary_micro_id"] for r in gt};skills,micros=load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES)
    items=[]
    for row in rows:
        result=deep[row["fingerprint"]];risk=_risk(row,result,skills,micros,validated_skills,validated_micros);q=row["question"]
        items.append({"fingerprint":row["fingerprint"],"source_review_number":int(row["source_review_number"]),"priority":row["優先級"],"question_text":row["題目"],
          "school":q.get("source_school",""),"year":q.get("source_year",""),**risk})
    return items

def _universes(items:list[dict[str,Any]])->dict[str,set[Any]]:
    return {"new_skills":{x["skill"] for x in items if x["new_skill"]},"new_micros":{x["micro"] for x in items if x["new_micro"]},
      "topics":{x["topic"] for x in items},"styles":{x["style"] for x in items},
      "secondary_groups":{x["secondary"] for x in items if x["secondary"] and (x["level"] in {"CRITICAL","HIGH"})},
      "schools":{x["school"] for x in items},"years":{x["year"] for x in items}}

def _coverage(selected:set[str],items:list[dict[str,Any]],universe:dict[str,set[Any]])->dict[str,set[Any]]:
    rows=[x for x in items if x["fingerprint"] in selected]
    return {"new_skills":{x["skill"] for x in rows if x["new_skill"]},"new_micros":{x["micro"] for x in rows if x["new_micro"]},
      "topics":{x["topic"] for x in rows},"styles":{x["style"] for x in rows},"secondary_groups":{x["secondary"] for x in rows if x["secondary"] in universe["secondary_groups"]},
      "schools":{x["school"] for x in rows},"years":{x["year"] for x in rows}}

def _satisfied(cov:dict[str,set[Any]],universe:dict[str,set[Any]],micro_target:float,topic_target:float)->bool:
    return (cov["new_skills"]==universe["new_skills"] and cov["styles"]==universe["styles"] and cov["secondary_groups"]==universe["secondary_groups"]
      and len(cov["new_micros"])>=math.ceil(micro_target*len(universe["new_micros"]))
      and len(cov["topics"])>=math.ceil(topic_target*len(universe["topics"])))

def select_plan(items:list[dict[str,Any]],micro_target:float,topic_target:float)->set[str]:
    universe=_universes(items)
    selected={x["fingerprint"] for x in items if x["priority"]=="P3" or not x["parent_valid"] or not x["extraction_clean"]}
    while True:
        cov=_coverage(selected,items,universe)
        if _satisfied(cov,universe,micro_target,topic_target):break
        best=None
        for x in items:
            if x["fingerprint"] in selected:continue
            score=0
            if x["new_skill"] and x["skill"] not in cov["new_skills"]:score+=1000
            if x["style"] not in cov["styles"]:score+=500
            if x["secondary"] in universe["secondary_groups"] and x["secondary"] not in cov["secondary_groups"]:score+=450
            if x["new_micro"] and x["micro"] not in cov["new_micros"]:score+=120
            if x["topic"] not in cov["topics"]:score+=60
            if x["school"] not in cov["schools"]:score+=15
            if x["year"] not in cov["years"]:score+=10
            score+=x["score"]/100
            candidate=(-score,x["source_review_number"],x["fingerprint"],x)
            if best is None or candidate[:3]<best[:3]:best=candidate
        if best is None or -best[0]<=0:raise RuntimeError("SET_COVER_UNSATISFIABLE")
        selected.add(best[3]["fingerprint"])
    return selected

def _metric(selected:set[str],items:list[dict[str,Any]])->dict[str,Any]:
    u=_universes(items);c=_coverage(selected,items,u)
    pct=lambda key:round(100*len(c[key])/len(u[key]),2) if u[key] else 100.0
    return {"questions":len(selected),"skill_coverage":pct("new_skills"),"micro_coverage":pct("new_micros"),"topic_coverage":pct("topics"),"assessment_coverage":pct("styles"),
      "p3_coverage":round(100*sum(x["priority"]=="P3" and x["fingerprint"] in selected for x in items)/sum(x["priority"]=="P3" for x in items),2),
      "school_coverage":pct("schools"),"year_coverage":pct("years")}

def _representative(item:dict[str,Any],selected_items:list[dict[str,Any]])->dict[str,Any]|None:
    candidates=[]
    for rep in selected_items:
        shared_skill=rep["skill"]==item["skill"];shared_topic=rep["topic"]==item["topic"];shared_style=rep["style"]==item["style"]
        if shared_skill or (shared_topic and shared_style):candidates.append((not shared_skill,not shared_topic,not shared_style,rep["source_review_number"],rep))
    return min(candidates,key=lambda x:x[:4])[-1] if candidates else None

def build(*,force:bool=False)->dict[str,Any]:
    # Once issued to a teacher, coverage-set numbering is immutable. A later
    # regression must not silently regenerate or reorder the approved CSV.
    if not force and TEACHER_SET.is_file() and DEFERRED.is_file() and STATUS.is_file():
        return json.loads(STATUS.read_text(encoding="utf-8-sig"))
    items=_items();plans={name:select_plan(items,*targets) for name,targets in PLAN_TARGETS.items()};metrics={name:_metric(selected,items) for name,selected in plans.items()}
    recommended="PLAN_B_BALANCED";selected=set(plans[recommended]);item_by_fp={x["fingerprint"]:x for x in items}
    while True:
        selected_items=[item_by_fp[fp] for fp in selected];missing=[]
        for item in items:
            if item["fingerprint"] not in selected and _representative(item,selected_items) is None:missing.append(item)
        if not missing:break
        selected.update(x["fingerprint"] for x in missing)
    selected_items=[item_by_fp[fp] for fp in selected];teacher=[];deferred=[]
    for item in sorted(items,key=lambda x:x["source_review_number"]):
        if item["fingerprint"] in selected:
            contribution=[]
            if item["new_skill"]:contribution.append("NEW_SKILL")
            if item["new_micro"]:contribution.append("NEW_MICRO")
            contribution.extend(("TOPIC","ASSESSMENT_STYLE"))
            teacher.append({"序號":len(teacher)+1,"原Review序號":item["source_review_number"],"Risk":item["level"],"題目":item["question_text"],"Topic":item["topic"],
              "Primary Skill":item["skill"],"Primary Micro":item["micro"],"Secondary Skills":"|".join(item["secondary"]),"Assessment Style":item["style"],"Confidence":item["confidence"],
              "Coverage Contribution":"|".join(contribution),"Why Selected":"|".join(item["why"] or ["SET_COVER_REPRESENTATIVE"]),"人工Scope":"","人工Skill":"","人工Micro":"","人工Secondary":"","人工Assessment":"","人工備註":""})
        else:
            rep=_representative(item,selected_items)
            if rep is None:raise RuntimeError("DEFERRED_WITHOUT_REPRESENTATIVE")
            deferred.append({"fingerprint":item["fingerprint"],"status":"DEFERRED_AUDIT","reason_deferred":"COVERED_BY_DETERMINISTIC_REPRESENTATIVE",
              "covered_by_teacher_question":rep["source_review_number"],"shared_skill":item["skill"] if rep["skill"]==item["skill"] else "",
              "shared_topic":item["topic"] if rep["topic"]==item["topic"] else "","shared_assessment_style":item["style"] if rep["style"]==item["style"] else ""})
    _write_csv(TEACHER_SET,teacher,list(teacher[0]));_write_csv(DEFERRED,deferred,list(deferred[0]) if deferred else ["fingerprint","status","reason_deferred","covered_by_teacher_question","shared_skill","shared_topic","shared_assessment_style"])
    recommendation=_metric(selected,items)
    status={"plans":metrics,"recommendation":{"selected_plan":recommended,"teacher_questions":len(teacher),"deferred_questions":len(deferred),**recommendation,
      "all_p3_included":recommendation["p3_coverage"]==100.0},"direct_human_gt":sum(r["source_status"]=="HUMAN_VALIDATED" for r in _jsonl(GT)),
      "source_invalid":sum(r["source_status"]!="HUMAN_VALIDATED" for r in _jsonl(GT)),"unreviewed":len(teacher),"deferred_audit":len(deferred),
      "deferred_human_validated":0,"api_calls":0,"production_reads":0,"production_writes":0}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");return status

if __name__=="__main__":print(json.dumps(build(),ensure_ascii=False))
