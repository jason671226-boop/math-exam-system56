"""Prepare local-only teacher review files for the Stage 7 PRIVATE_JH pilot."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from services.stage7_profiles import load_curriculum_catalog, validate_mapping_result

PILOT = ROOT / ".local" / "stage7_private_jh" / "pilot100"
MANIFEST = PILOT / "sample_manifest.json"
DEEPSEEK = PILOT / "deepseek_results.jsonl"
GEMINI = PILOT / "gemini_validation20.jsonl"
QUEUE = PILOT / "PRIVATE_JH_HUMAN_REVIEW.csv"
TEACHER = PILOT / "PRIVATE_JH_HUMAN_REVIEW_FOR_TEACHER.csv"
SIMPLE = PILOT / "PRIVATE_JH_HUMAN_REVIEW_SIMPLE.csv"
STATUS = PILOT / "human_review_status.json"

PRIORITIES = (
    ("P0", "INVALID"), ("P1", "PROVIDER_DISAGREEMENT"),
    ("P2", "OUT_OF_SCOPE"), ("P3", "LOW_CONFIDENCE"),
    ("P4", "CROSS_UNIT_HIGH_DIFFICULTY"), ("P5", "RANDOM_AUDIT"),
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _name(identifier: Any, catalog: dict[str, dict[str, str]], *, micro: bool = False) -> str:
    value = str(identifier or "")
    if not value:
        return ""
    row = catalog.get(value)
    if row is None:
        return "INVALID_ID"
    return str((row.get("focus") if micro else row.get("skill_name")) or row.get("skill_name") or "INVALID_ID")


def structural_signature(text: str) -> str:
    """Conservative deterministic template; it is never treated as ground truth."""
    normalized = text.strip().lower().replace("臺", "台")
    normalized = re.sub(r"[０-９0-9]+(?:[.,，．][０-９0-9]+)?", "#", normalized)
    normalized = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩abcdefＡＢＣＤＥＦ]\s*[.、)]", "§", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _priority(reasons: set[str]) -> str:
    return next((priority for priority, reason in PRIORITIES if reason in reasons), "P5")


def _suggest(reasons: set[str], parent_error: bool) -> str:
    checks=[]
    if "INVALID" in reasons or parent_error: checks.append("確認ID存在、Micro隸屬Primary Skill")
    if "PROVIDER_DISAGREEMENT" in reasons: checks.append("獨立判斷Scope、Primary Skill與Micro")
    if "OUT_OF_SCOPE" in reasons: checks.append("確認是否仍可合理建立於G5/G6基礎")
    if "LOW_CONFIDENCE" in reasons: checks.append("檢查題意主結構與候選Skill")
    if "CROSS_UNIT_HIGH_DIFFICULTY" in reasons: checks.append("區分Primary與Secondary Skills並核對考法")
    if "RANDOM_AUDIT" in reasons: checks.append("例行抽查Scope、Skill、Micro與Assessment Style")
    return "；".join(checks)


def prepare() -> dict[str, Any]:
    required=(MANIFEST,DEEPSEEK,GEMINI,QUEUE)
    if not all(path.is_file() for path in required):
        raise RuntimeError("MISSING_PRIVATE_PILOT_ARTIFACT")
    before={path.name:file_hash(path) for path in (DEEPSEEK,GEMINI,QUEUE)}
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    questions={row["fingerprint"]:row for row in manifest["questions"]}
    deep={row["fingerprint"]:row for row in read_jsonl(DEEPSEEK)}
    gemini={row["fingerprint"]:row for row in read_jsonl(GEMINI)}
    with QUEUE.open(encoding="utf-8-sig",newline="") as handle:
        queue=list(csv.DictReader(handle))
    fingerprints=[row["fingerprint"] for row in queue]
    if len(queue)!=79 or len(fingerprints)!=len(set(fingerprints)):
        raise RuntimeError("REVIEW_QUEUE_INTEGRITY_FAILED")
    if any(fp not in questions or fp not in deep for fp in fingerprints):
        raise RuntimeError("REVIEW_SOURCE_MISSING")

    skills,micros=load_curriculum_catalog(("G5","G6"))
    signatures={fp:structural_signature(str(questions[fp].get("question_text") or "")) for fp in fingerprints}
    sizes=Counter(signatures.values())
    ordered=sorted(queue,key=lambda row:(int(_priority(set(filter(None,row["reasons"].split("|"))))[1]),row["fingerprint"]))
    records=[]
    for index,item in enumerate(ordered,1):
        fp=item["fingerprint"];q=questions[fp];d=deep[fp];g=gemini.get(fp,{})
        reasons=set(filter(None,item["reasons"].split("|")))
        errors=set(d.get("validation_errors") or []) | set(g.get("validation_errors") or [])
        parent_error=False
        mid=str(d.get("primary_micro_skill_id") or "");sid=str(d.get("primary_skill_id") or "")
        if mid and mid in micros and micros[mid].get("parent_skill_id")!=sid: parent_error=True
        validation_errors=validate_mapping_result(d,grades=("G5","G6"))
        errors.update(validation_errors)
        secondary=[]
        for secondary_id in d.get("secondary_skill_ids") or []:
            secondary.append(f"{secondary_id}（{_name(secondary_id,skills)}）")
        records.append({
            "序號":index,"優先級":_priority(reasons),"題目":q.get("question_text",""),"來源學校":q.get("source_school",""),
            "年份":q.get("source_year",""),"Topic":"|".join(q.get("topic_groups") or []),
            "DeepSeek Scope":d.get("scope_status",""),"DeepSeek Skill ID":sid,"DeepSeek Skill 中文名稱":_name(sid,skills),
            "DeepSeek Micro ID":mid,"DeepSeek Micro 中文名稱":_name(mid,micros,micro=True),
            "DeepSeek Secondary Skills":"|".join(secondary),"DeepSeek Assessment Style":d.get("assessment_style",""),
            "DeepSeek Confidence":d.get("confidence",""),"Gemini Scope（若有）":g.get("scope_status",""),
            "Gemini Skill":" / ".join(filter(None,(str(g.get("primary_skill_id") or ""),_name(g.get("primary_skill_id"),skills)))),
            "Gemini Micro":" / ".join(filter(None,(str(g.get("primary_micro_skill_id") or ""),_name(g.get("primary_micro_skill_id"),micros,micro=True)))),
            "Review Reason":"|".join(sorted(reasons)),"Validation Error":"|".join(sorted(errors)),
            "建議檢查點":_suggest(reasons,parent_error),"structural_group_id":"SG-"+signatures[fp],"group_size":sizes[signatures[fp]],
            "人工正確 Scope":"","人工正確 Primary Skill":"","人工正確 Primary Micro":"","人工 Secondary Skills":"",
            "人工 Assessment Style":"","人工備註":"",
        })

    teacher_fields=list(records[0])
    with TEACHER.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=teacher_fields);writer.writeheader();writer.writerows(records)
    simple_fields=("序號","優先級","題目","DeepSeek判斷","Gemini判斷","差異原因","建議檢查點","人工Scope","人工Skill","人工Micro","人工Secondary Skill","人工Assessment Style","人工備註","structural_group_id","group_size")
    with SIMPLE.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=simple_fields);writer.writeheader()
        for row in records:
            writer.writerow({"序號":row["序號"],"優先級":row["優先級"],"題目":row["題目"],
                "DeepSeek判斷":" / ".join(map(str,(row["DeepSeek Scope"],row["DeepSeek Skill 中文名稱"],row["DeepSeek Micro 中文名稱"],row["DeepSeek Assessment Style"]))),
                "Gemini判斷":" / ".join(filter(None,(row["Gemini Scope（若有）"],row["Gemini Skill"],row["Gemini Micro"]))),
                "差異原因":row["Review Reason"],"建議檢查點":row["建議檢查點"],"人工Scope":"","人工Skill":"","人工Micro":"",
                "人工Secondary Skill":"","人工Assessment Style":"","人工備註":"","structural_group_id":row["structural_group_id"],"group_size":row["group_size"]})
    after={path.name:file_hash(path) for path in (DEEPSEEK,GEMINI,QUEUE)}
    priority_counts=Counter(row["優先級"] for row in records)
    reason_counts=Counter(reason for item in queue for reason in filter(None,item["reasons"].split("|")))
    status={"total_unique_review":len(records),**{p:priority_counts[p] for p,_ in PRIORITIES},
        "reason_counts":dict(reason_counts),"structural_groups":len(sizes),"largest_group_size":max(sizes.values()),
        "duplicate_fingerprints":len(fingerprints)-len(set(fingerprints)),"human_validated":0,"remaining":len(records),
        "source_files_unchanged":before==after,"api_calls":0,"production_reads":0,"production_writes":0}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return status


if __name__=="__main__":
    print(json.dumps(prepare(),ensure_ascii=False))
