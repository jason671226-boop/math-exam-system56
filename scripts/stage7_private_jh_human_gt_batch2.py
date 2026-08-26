"""Ingest teacher source-review numbers 16-22 and create the V3 local queue."""
from __future__ import annotations

import csv,json,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from services.math_extraction_quality import assess_math_extraction
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES,load_curriculum_catalog
from scripts.stage7_private_jh_human_gt import MANIFEST,QUEUE,DEEPSEEK,GT,CLEANING,PILOT,_csv,_jsonl,_sha,_write_csv

TEACHER_V1=PILOT/"PRIVATE_JH_HUMAN_REVIEW_FOR_TEACHER.csv"
TEACHER_V2=PILOT/"PRIVATE_JH_HUMAN_REVIEW_FOR_TEACHER_V2.csv"
SIMPLE_V2=PILOT/"PRIVATE_JH_HUMAN_REVIEW_SIMPLE_V2.csv"
TEACHER_V3=PILOT/"PRIVATE_JH_HUMAN_REVIEW_FOR_TEACHER_V3.csv"
SIMPLE_V3=PILOT/"PRIVATE_JH_HUMAN_REVIEW_SIMPLE_V3.csv"
STATUS=PILOT/"human_gt_batch2_status.json"

BATCH={
16:{"scope":"PRIVATE_JH","skill":"G05-N-DEC-MUL-02","micro":"G05-N-DEC-MUL-02-C1","secondary":[],"assessment":None,"note":"0.38 < 0.38；核心是小數乘法及乘數小於 1 時積的大小關係。"},
17:{"scope":"PRIVATE_JH","skill":"G05-S-FACE-01","micro":"G05-S-FACE-01-V1","secondary":[],"assessment":None,"note":"正方體展開圖摺成立體後判斷面與面相鄰關係；屬空間表徵轉換。"},
18:{"scope":"PRIVATE_JH","skill":"G04-R-PERIOD-01","micro":"G04-R-PERIOD-01-V1","secondary":[],"assessment":None,"note":"重複波形中判斷第 98～100 個位置；屬前置年級週期 Skill，PRIVATE_JH Scope 合法。"},
19:{"scope":"PRIVATE_JH","skill":"G06-R-MIXED-01","micro":"G06-R-MIXED-01-P1","secondary":[],"assessment":None,"note":"4.58 + 0.32 - 2.3，標準小數混合運算強化。"},
20:{"scope":"SOURCE_INVALID_PENDING_REEXTRACTION","skill":None,"micro":None,"secondary":[],"assessment":None,"candidate":"G05-N-FRAC-SUB-01","note":"MATH_NOTATION_LOST"},
21:{"scope":"SOURCE_INVALID_PENDING_REEXTRACTION","skill":None,"micro":None,"secondary":[],"assessment":None,"candidate":"G05-N-FRAC-DIVINT-01","candidate_secondary":"G04-S-PERIM-01","note":"MATH_NOTATION_LOST"},
22:{"scope":"PRIVATE_JH","skill":"G06-N-BASE-02","micro":"G06-N-BASE-02-A1","secondary":["G05-N-PERCENT-01"],"assessment":None,"note":"980 元打六折，核心為基準量 × 0.6，百分率概念為 supporting skill。"},
}

def _locate()->tuple[dict[int,str],dict[str,dict[str,Any]],dict[int,dict[str,str]]]:
    v1=_csv(TEACHER_V1);v2=_csv(TEACHER_V2);manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"));questions=manifest["questions"]
    original={int(row["序號"]):row for row in v1};v2_text=Counter(row["題目"] for row in v2);question_text:dict[str,list[dict[str,Any]]]={}
    for q in questions:question_text.setdefault(q["question_text"],[]).append(q)
    queue_fps={row["fingerprint"] for row in _csv(QUEUE)};resolved={};qmap={}
    for number in BATCH:
        if number not in original:raise RuntimeError("SOURCE_REVIEW_NUMBER_MISSING")
        text=original[number]["題目"]
        if v2_text[text]!=1:raise RuntimeError("V2_QUESTION_TEXT_MISMATCH")
        candidates=[q for q in question_text.get(text,[]) if q["fingerprint"] in queue_fps]
        if len(candidates)!=1:raise RuntimeError("FINGERPRINT_NOT_UNIQUE")
        resolved[number]=candidates[0]["fingerprint"];qmap[candidates[0]["fingerprint"]]=candidates[0]
    if len(set(resolved.values()))!=7:raise RuntimeError("BATCH_FINGERPRINT_DUPLICATE")
    return resolved,qmap,original

def _validate()->dict[str,str]:
    skills,micros=load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES);resolved={}
    for number,row in BATCH.items():
        if row["skill"] is None:
            if row["micro"] is not None or row["secondary"]:raise RuntimeError("SOURCE_INVALID_HAS_GT_IDS")
            continue
        if row["skill"] not in skills:raise RuntimeError(f"UNKNOWN_SKILL:{number}")
        micro=micros.get(row["micro"])
        if micro is None:raise RuntimeError(f"UNKNOWN_MICRO:{number}")
        if micro["parent_skill_id"]!=row["skill"]:raise RuntimeError(f"MICRO_PARENT_MISMATCH:{number}")
        if any(sid not in skills for sid in row["secondary"]):raise RuntimeError(f"UNKNOWN_SECONDARY:{number}")
        resolved[str(number)]=f'{row["skill"]}/{row["micro"]}'
    return resolved

def ingest()->dict[str,Any]:
    required=(TEACHER_V1,TEACHER_V2,SIMPLE_V2,MANIFEST,QUEUE,DEEPSEEK,GT,CLEANING)
    if not all(path.is_file() for path in required):raise RuntimeError("MISSING_BATCH2_INPUT")
    protected=(TEACHER_V1,TEACHER_V2,SIMPLE_V2,QUEUE,DEEPSEEK);before={p.name:_sha(p) for p in protected}
    resolved,qmap,original=_locate();id_resolutions=_validate();existing={row["fingerprint"]:row for row in _jsonl(GT)}
    now=datetime.now(timezone.utc).isoformat()
    for number,spec in BATCH.items():
        fp=resolved[number];old=existing.get(fp,{})
        source_invalid=spec["skill"] is None
        existing[fp]={"fingerprint":fp,"source_review_number":number,"human_scope":spec["scope"],"human_primary_skill_id":spec["skill"],"human_primary_micro_id":spec["micro"],
          "human_secondary_skill_ids":spec["secondary"],"human_assessment_style":spec["assessment"],"human_note":spec["note"],"validation_source":"TEACHER_APPROVED",
          "validated_at":old.get("validated_at") or now,"source_status":"SOURCE_NEEDS_REEXTRACTION" if source_invalid else "HUMAN_VALIDATED"}
    GT.write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in sorted(existing.values(),key=lambda x:int(x["source_review_number"]))),encoding="utf-8")
    cleaning=json.loads(CLEANING.read_text(encoding="utf-8-sig"));items={row["fingerprint"]:row for row in cleaning.get("items",[])}
    for number in (20,21):
        spec=BATCH[number];q=qmap[resolved[number]];items[resolved[number]]={"fingerprint":resolved[number],"source_review_number":number,
          "source_document":q.get("source_url"),"question_number":q.get("question_number"),"reason":"MATH_NOTATION_LOST","candidate_concept":spec.get("candidate"),
          "candidate_secondary":spec.get("candidate_secondary"),"status":"NEEDS_REEXTRACTION","replacement_status":"PENDING"}
    CLEANING.write_text(json.dumps({"items":list(items.values())},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    remove=set(resolved.values());v2=_csv(TEACHER_V2);text_to_original={row["題目"]:int(row["序號"]) for row in _csv(TEACHER_V1)}
    question_fp={q["question_text"]:q["fingerprint"] for q in json.loads(MANIFEST.read_text(encoding="utf-8-sig"))["questions"]}
    remaining=[row.copy() for row in v2 if question_fp.get(row["題目"]) not in remove]
    for row in remaining:row["source_review_number"]=text_to_original[row["題目"]];row["序號"]=row["source_review_number"]
    remaining.sort(key=lambda row:(int(row["優先級"][1]),int(row["source_review_number"])))
    teacher_fields=["source_review_number"]+list(v2[0]);_write_csv(TEACHER_V3,remaining,teacher_fields)
    simple=[]
    for row in remaining:simple.append({"source_review_number":row["source_review_number"],"序號":row["序號"],"優先級":row["優先級"],"題目":row["題目"],
      "DeepSeek判斷":" / ".join(map(str,(row["DeepSeek Scope"],row["DeepSeek Skill 中文名稱"],row["DeepSeek Micro 中文名稱"],row["DeepSeek Assessment Style"]))),
      "Gemini判斷":" / ".join(filter(None,(row["Gemini Scope（若有）"],row["Gemini Skill"],row["Gemini Micro"]))),"差異原因":row["Review Reason"],"建議檢查點":row["建議檢查點"],
      "人工Scope":"","人工Skill":"","人工Micro":"","人工Secondary Skill":"","人工Assessment Style":"","人工備註":"","structural_group_id":row["structural_group_id"],"group_size":row["group_size"]})
    _write_csv(SIMPLE_V3,simple,list(simple[0]))
    deep={row["fingerprint"]:row for row in _jsonl(DEEPSEEK)};risk=0;rule_count=0
    guidance=json.loads((ROOT/"data/stage7/private_jh_topic_guidance_v1.json").read_text(encoding="utf-8"))["rules"]
    for row in remaining:
        text=row["題目"];risk+=assess_math_extraction(text).status!="PASS"
        rule_count+=any(any(term in text for term in rule["evidence"]) for rule in guidance)
    priorities=Counter(row["優先級"] for row in remaining);skill_groups=Counter(deep[question_fp[row["題目"]]].get("primary_skill_id") or "OUT" for row in remaining)
    styles=Counter(deep[question_fp[row["題目"]]].get("assessment_style") or "NONE" for row in remaining)
    all_gt=list(existing.values());validated=[r for r in all_gt if r["source_status"]=="HUMAN_VALIDATED"]
    invalid=[r for r in all_gt if r["source_status"]!="HUMAN_VALIDATED"]
    after={p.name:_sha(p) for p in protected}
    status={"reviewed_rows":7,"human_validated_added":5,"source_reextraction":2,"curriculum_ids_resolved":id_resolutions,"id_validation_failures":0,"parent_validation_failures":0,
      "human_gt_total":{"human_validated_questions":len(validated),"source_invalid_reextraction":len(invalid),"unique_validated_skills":len({r["human_primary_skill_id"] for r in validated}),"unique_validated_micros":len({r["human_primary_micro_id"] for r in validated})},
      "review_queue":{"previous_active":64,"human_gt_removed":5,"source_cleaning_removed":2,"remaining_active":len(remaining),**{p:priorities[p] for p in ("P0","P1","P2","P3","P4","P5")}},
      "remaining_analysis":{"extraction_risk":risk,"high_frequency_skill_groups":skill_groups.most_common(10),"high_frequency_assessment_styles":styles.most_common(),"deterministic_rule_check":rule_count,"individual_teacher_review":len(remaining)-risk},
      "protected_inputs_unchanged":before==after,"math_notation_gate":"READY","api_calls":0,"production_reads":0,"production_writes":0}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");return status

if __name__=="__main__":print(json.dumps(ingest(),ensure_ascii=False))
