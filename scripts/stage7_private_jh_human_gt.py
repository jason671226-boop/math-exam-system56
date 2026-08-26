"""Ingest the teacher-approved PRIVATE_JH review batch without changing AI results."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES, load_curriculum_catalog

PILOT=ROOT/".local"/"stage7_private_jh"/"pilot100"
SIMPLE_V1=PILOT/"PRIVATE_JH_HUMAN_REVIEW_SIMPLE.csv"
TEACHER_V1=PILOT/"PRIVATE_JH_HUMAN_REVIEW_FOR_TEACHER.csv"
QUEUE=PILOT/"PRIVATE_JH_HUMAN_REVIEW.csv"
MANIFEST=PILOT/"sample_manifest.json"
DEEPSEEK=PILOT/"deepseek_results.jsonl"
GEMINI=PILOT/"gemini_validation20.jsonl"
GT=PILOT/"private_jh_human_ground_truth.jsonl"
CLEANING=PILOT/"source_cleaning_queue.json"
SIMPLE_V2=PILOT/"PRIVATE_JH_HUMAN_REVIEW_SIMPLE_V2.csv"
TEACHER_V2=PILOT/"PRIVATE_JH_HUMAN_REVIEW_FOR_TEACHER_V2.csv"
STATUS=PILOT/"human_gt_batch_status.json"

APPROVED: dict[int,dict[str,Any]]={
  1:{"scope":"SOURCE_INVALID","skill":None,"micro":None,"secondary":[],"assessment":None,"note":"題目抽取污染／多題黏在同一題幹，不能建立 Human Skill Ground Truth。"},
  2:{"scope":"PRIVATE_JH","skill":"G05-S-AREA-TRAP-01","micro":"G05-S-AREA-TRAP-01-V1","secondary":[],"assessment":"PRIVATE_JH_ADVANCED","note":"梯形面積＋圖形判讀／表徵轉換。"},
  3:{"scope":"PRIVATE_JH","skill":"G05-S-FACE-01","micro":"G05-S-FACE-01-V1","secondary":[],"assessment":None,"note":"正方體展開圖與相鄰面空間判讀。"},
  4:{"scope":"PRIVATE_JH","skill":"G05-S-FACE-01","micro":"G05-S-FACE-01-V1","secondary":[],"assessment":None,"note":"正方體展開圖辨識；原模型分類不夠精準。"},
  5:{"scope":"PRIVATE_JH","skill":"G05-N-LCM-01","micro":"G05-N-LCM-01-X1","secondary":["G04-R-PERIOD-01"],"assessment":None,"note":"最小公倍數＋星期週期跨單元應用。"},
  6:{"scope":"PRIVATE_JH","skill":"G05-R-LAW-01","micro":"G05-R-LAW-01-T1","secondary":[],"assessment":None,"note":"運算規律、湊整與簡化計算。"},
  7:{"scope":"PRIVATE_JH","skill":"G05-N-FACTOR-01","micro":"G05-N-FACTOR-01-V1","secondary":[],"assessment":None,"note":"以長方形排列辨認因數配對。"},
  8:{"scope":"PRIVATE_JH","skill":"G05-N-RATE-01","micro":"G05-N-RATE-01-R1","secondary":["G05-N-PERCENT-01"],"assessment":"REVERSE_REASONING","note":"糖水濃度逆推；核心是部分量／全體量比率，百分率互換為次要技能。"},
  9:{"scope":"PRIVATE_JH","skill":"G05-R-LAW-01","micro":"G05-R-LAW-01-T1","secondary":[],"assessment":None,"note":"運算規律、湊整與簡化計算。"},
 10:{"scope":"PRIVATE_JH","skill":"G06-N-GCFLCM-APP-01","micro":"G06-N-GCFLCM-APP-01-T1","secondary":[],"assessment":None,"note":"500～550 範圍內，同時符合 12 人與 30 人分組；屬公倍數／LCM 應用。"},
 11:{"scope":"PRIVATE_JH","skill":"G06-R-PATTERN-01","micro":"G06-R-PATTERN-01-P1","secondary":[],"assessment":None,"note":"火柴棒圖形規律。"},
 12:{"scope":"PRIVATE_JH","skill":"G04-S-ANGLECALC-01","micro":"G04-S-ANGLECALC-01-T1","secondary":["G04-N-TIMEAPP-01"],"assessment":None,"note":"鐘面時刻＋夾角；PRIVATE_JH 應允許必要的前置年級 G4 Skill。"},
 13:{"scope":"PRIVATE_JH","skill":"G06-N-COPRIME-01","micro":"G06-N-COPRIME-01-C1","secondary":[],"assessment":None,"note":"互質概念辨識。"},
 14:{"scope":"PRIVATE_JH","skill":"G05-N-FRAC-DIVREP-01","micro":"G05-N-FRAC-DIVREP-01-V1","secondary":["G05-N-FRAC-MUL-01"],"assessment":None,"note":"除法與分數乘法表徵轉換。"},
 15:{"scope":"PRIVATE_JH","skill":"G05-N-FRAC-COMMON-01","micro":"G05-N-FRAC-COMMON-01-P1","secondary":[],"assessment":None,"note":"異分母分數通分與大小比較。"},
}

def _jsonl(path:Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]

def _sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()

def _csv(path:Path)->list[dict[str,str]]:
    with path.open(encoding="utf-8-sig",newline="") as handle:return list(csv.DictReader(handle))

def _write_csv(path:Path,rows:list[dict[str,Any]],fields:list[str])->None:
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(rows)

def _resolve(simple:list[dict[str,str]],teacher:list[dict[str,str]],questions:list[dict[str,Any]],queue_fps:set[str])->dict[int,str]:
    if {int(row["序號"]) for row in simple} < set(APPROVED): raise RuntimeError("APPROVED_REVIEW_NUMBER_MISSING")
    by_text:dict[str,list[str]]={}
    for q in questions:by_text.setdefault(str(q.get("question_text") or ""),[]).append(q["fingerprint"])
    teacher_by_number={int(row["序號"]):row for row in teacher}
    resolved={}
    for row in simple:
        number=int(row["序號"])
        if number not in APPROVED:continue
        if number not in teacher_by_number or teacher_by_number[number]["題目"]!=row["題目"]:raise RuntimeError("REVIEW_TEXT_MISMATCH")
        candidates=[fp for fp in by_text.get(row["題目"],[]) if fp in queue_fps]
        if len(candidates)!=1:raise RuntimeError("REVIEW_FINGERPRINT_NOT_UNIQUE")
        resolved[number]=candidates[0]
    if len(resolved)!=15 or len(set(resolved.values()))!=15:raise RuntimeError("APPROVED_MAPPING_NOT_UNIQUE")
    return resolved

def _validate_ids()->tuple[dict[str,dict],dict[str,dict]]:
    skills,micros=load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES);errors=[]
    for number,row in APPROVED.items():
        if row["scope"]=="SOURCE_INVALID":
            if row["skill"] is not None or row["micro"] is not None or row["secondary"]:errors.append(f"{number}:SOURCE_INVALID_HAS_IDS")
            continue
        if row["skill"] not in skills:errors.append(f"{number}:UNKNOWN_PRIMARY_SKILL")
        micro=micros.get(row["micro"])
        if micro is None:errors.append(f"{number}:UNKNOWN_PRIMARY_MICRO")
        elif micro.get("parent_skill_id")!=row["skill"]:errors.append(f"{number}:MICRO_PARENT_MISMATCH")
        for sid in row["secondary"]:
            if sid not in skills:errors.append(f"{number}:UNKNOWN_SECONDARY_SKILL")
    if errors:raise RuntimeError("HUMAN_GT_ID_VALIDATION_FAILED:"+",".join(errors))
    return skills,micros

def ingest()->dict[str,Any]:
    required=(SIMPLE_V1,TEACHER_V1,QUEUE,MANIFEST,DEEPSEEK,GEMINI)
    if not all(p.is_file() for p in required):raise RuntimeError("MISSING_HUMAN_REVIEW_INPUT")
    protected=(SIMPLE_V1,TEACHER_V1,QUEUE,DEEPSEEK,GEMINI);before={p.name:_sha(p) for p in protected}
    simple,teacher,queue=_csv(SIMPLE_V1),_csv(TEACHER_V1),_csv(QUEUE)
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"));questions=manifest["questions"]
    resolved=_resolve(simple,teacher,questions,{row["fingerprint"] for row in queue});_validate_ids()
    existing={row["fingerprint"]:row for row in _jsonl(GT)} if GT.exists() else {}
    now=datetime.now(timezone.utc).isoformat();records=[]
    for number in sorted(APPROVED):
        spec=APPROVED[number];fp=resolved[number];old=existing.get(fp,{})
        records.append({"fingerprint":fp,"source_review_number":number,"human_scope":spec["scope"],
            "human_primary_skill_id":spec["skill"],"human_primary_micro_id":spec["micro"],
            "human_secondary_skill_ids":spec["secondary"],"human_assessment_style":spec["assessment"],"human_note":spec["note"],
            "validation_source":"TEACHER_APPROVED","validated_at":old.get("validated_at") or now,
            "source_status":"SOURCE_INVALID" if spec["scope"]=="SOURCE_INVALID" else "HUMAN_VALIDATED"})
    merged=dict(existing);merged.update({row["fingerprint"]:row for row in records})
    GT.write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in sorted(merged.values(),key=lambda x:int(x["source_review_number"]))),encoding="utf-8")
    invalid=next(row for row in records if row["source_status"]=="SOURCE_INVALID")
    source={q["fingerprint"]:q for q in questions}[invalid["fingerprint"]]
    CLEANING.write_text(json.dumps({"items":[{"fingerprint":invalid["fingerprint"],"source":{"school":source.get("source_school"),"year":source.get("source_year"),"exam":source.get("source_exam"),"url":source.get("source_url")},"reason":"題目抽取污染／多題黏在同一題幹","status":"NEEDS_REEXTRACTION","replacement_status":"PENDING"}]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    removed=set(resolved.values());teacher_q={row["題目"]:row for row in teacher}
    by_text={q["question_text"]:q["fingerprint"] for q in questions if q["question_text"] in teacher_q}
    remaining=[row.copy() for row in teacher if by_text.get(row["題目"]) not in removed]
    remaining.sort(key=lambda row:(int(row["優先級"][1]),by_text[row["題目"]]))
    for index,row in enumerate(remaining,1):row["序號"]=index
    _write_csv(TEACHER_V2,remaining,list(teacher[0]))
    simple_rows=[]
    for row in remaining:
        simple_rows.append({"序號":row["序號"],"優先級":row["優先級"],"題目":row["題目"],
          "DeepSeek判斷":" / ".join(map(str,(row["DeepSeek Scope"],row["DeepSeek Skill 中文名稱"],row["DeepSeek Micro 中文名稱"],row["DeepSeek Assessment Style"]))),
          "Gemini判斷":" / ".join(filter(None,(row["Gemini Scope（若有）"],row["Gemini Skill"],row["Gemini Micro"]))),
          "差異原因":row["Review Reason"],"建議檢查點":row["建議檢查點"],"人工Scope":"","人工Skill":"","人工Micro":"","人工Secondary Skill":"","人工Assessment Style":"","人工備註":"",
          "structural_group_id":row["structural_group_id"],"group_size":row["group_size"]})
    _write_csv(SIMPLE_V2,simple_rows,list(simple_rows[0]))
    valid=[row for row in records if row["source_status"]=="HUMAN_VALIDATED"]
    priorities=Counter(row["優先級"] for row in remaining)
    after={p.name:_sha(p) for p in protected}
    status={"approved_review_rows":15,"human_validated":len(valid),"source_invalid":1,"id_validation_failures":0,"parent_validation_failures":0,
      "human_coverage":{"questions":len(valid),"unique_primary_skills":len({r["human_primary_skill_id"] for r in valid}),"unique_micros":len({r["human_primary_micro_id"] for r in valid}),"secondary_skills":len({s for r in valid for s in r["human_secondary_skill_ids"]}),"source_invalid_excluded":True},
      "review_queue":{"previous":79,"human_gt_removed":14,"source_invalid_removed":1,"remaining":len(remaining),**{p:priorities[p] for p in ("P0","P1","P2","P3","P4","P5")}},
      "protected_inputs_unchanged":before==after,"api_calls":0,"production_reads":0,"production_writes":0}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");return status

if __name__=="__main__":print(json.dumps(ingest(),ensure_ascii=False))
