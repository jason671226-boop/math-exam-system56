"""Stage 7B-2 local-only PRIVATE_JH 100-question real mapping pilot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_provider import ProviderCallError, get_ai_provider
from services.stage5_question_mapping import build_candidate_packet
from services.stage7_profiles import PRIVATE_JH_CATALOG_GRADES, PRIVATE_JH_STYLES, load_curriculum_catalog, validate_mapping_result

LOCAL = ROOT / ".local/stage7_private_jh"
CORPUS = LOCAL / "raw_extracted/public_private_jh_questions.jsonl"
SOURCE_REGISTRY = LOCAL / "public_source_registry.json"
PILOT = LOCAL / "pilot100"
MANIFEST = PILOT / "sample_manifest.json"
DEEPSEEK_CHECKPOINT = PILOT / "deepseek_results.jsonl"
DEEPSEEK_CORRECTIONS = PILOT / "deepseek_corrections.jsonl"
DEEPSEEK_CORRECTIONS2 = PILOT / "deepseek_corrections2.jsonl"
DEEPSEEK_INVALID_ATTEMPTS = PILOT / "deepseek_invalid_attempts.jsonl"
GEMINI_RESULTS = PILOT / "gemini_validation20.jsonl"
COMPARISON = PILOT / "provider_comparison_private.json"
REVIEW = PILOT / "PRIVATE_JH_HUMAN_REVIEW.csv"
COVERAGE = PILOT / "coverage_private.json"
REPORT = PILOT / "pilot_validation_report.json"
PROFILE = "PRIVATE_JH"
DEEPSEEK_MODEL = "deepseek-v4-flash"
LOW_CONFIDENCE = 0.70
SAFE_SECRET_PATHS = (
    ROOT / ".streamlit/secrets.toml",
    Path(r"C:\MathAI_G5_Pilot\.streamlit\secrets.toml"),
    Path(r"C:\MathAI_G6_Pilot\.streamlit\secrets.toml"),
    Path(r"C:\MathAI_G8_Pilot\.streamlit\secrets.toml"),
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable(value: str) -> str:
    return hashlib.sha256(f"MATHAI_STAGE7B2:{value}".encode()).hexdigest()


def question_type(row: dict[str, Any]) -> str:
    text = row["question_text"]
    if any(word in text for word in ("圖", "面積", "體積", "角", "圓", "三角形")): return "GEOMETRY"
    if any(word in text for word in ("規律", "可能", "最多", "最少", "排列")): return "REASONING"
    if any(word in text for word in ("每分鐘", "經過", "共要", "相差", "剩餘")): return "APPLICATION"
    return "COMPUTATION"


def difficulty_hint(row: dict[str, Any]) -> str:
    topics = len(row.get("topic_groups") or [])
    length = len(row["question_text"])
    if topics >= 3 or length >= 180: return "HIGH"
    if topics >= 2 or length >= 100: return "MEDIUM"
    return "FOUNDATION"


def _pick(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []; remaining = list(rows)
    years: Counter[str] = Counter(); topics: Counter[str] = Counter(); types: Counter[str] = Counter(); levels: Counter[str] = Counter()
    while remaining and len(selected) < count:
        def score(row: dict[str, Any]) -> tuple[float, str]:
            row_topics = row.get("topic_groups") or ["UNCLASSIFIED"]
            diversity = 4/(1+years[row["source_year"]]) + 3*sum(1/(1+topics[t]) for t in row_topics)/len(row_topics)
            diversity += 2/(1+types[question_type(row)]) + 2/(1+levels[difficulty_hint(row)])
            return (-diversity, stable(row["fingerprint"]))
        chosen = min(remaining, key=score); remaining.remove(chosen); selected.append(chosen)
        years[chosen["source_year"]] += 1; types[question_type(chosen)] += 1; levels[difficulty_hint(chosen)] += 1
        for topic in chosen.get("topic_groups") or ["UNCLASSIFIED"]: topics[topic] += 1
    return selected


def prepare() -> dict[str, Any]:
    rows = read_jsonl(CORPUS)
    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8-sig"))
    if registry.get("status") != "CORPUS_READY" or len(rows) < 100:
        raise RuntimeError("CORPUS_NOT_READY")
    if len({row.get("fingerprint") for row in rows}) != len(rows):
        raise RuntimeError("CORPUS_DUPLICATE_FINGERPRINT")
    official_urls = {source["document_url"] for source in registry["sources"] if source["official_domain"] and source["usable_status"].startswith("USABLE")}
    if any(not row.get("question_text") or row.get("source_url") not in official_urls for row in rows):
        raise RuntimeError("SOURCE_INTEGRITY_FAILED")
    schools = sorted({row["source_school"] for row in rows})
    quotas = {school: 100 // len(schools) for school in schools}
    for school in schools[:100 % len(schools)]: quotas[school] += 1
    selected = [row for school in schools for row in _pick([x for x in rows if x["source_school"] == school], quotas[school])]
    if len(selected) != 100 or len({x["fingerprint"] for x in selected}) != 100:
        raise RuntimeError("SAMPLE_INTEGRITY_FAILED")
    selected.sort(key=lambda row: stable(row["fingerprint"]))
    selected_fps = {row["fingerprint"] for row in selected}
    holdout = [row["fingerprint"] for row in rows if row["fingerprint"] not in selected_fps]
    manifest = {"schema_version":"1.0", "profile_type":PROFILE, "questions":selected,
                "holdout_fingerprints":holdout, "integrity":{"sample":100,"unique_fingerprints":100,
                "official":True,"real_questions":True,"synthetic":False,"source_urls_traceable":True,
                "question_text_complete":True}, "distribution":distribution(selected)}
    write_json(MANIFEST, manifest); return manifest


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schools":dict(Counter(x["source_school"] for x in rows)), "years":dict(Counter(x["source_year"] for x in rows)),
            "topics":dict(Counter(t for x in rows for t in (x.get("topic_groups") or ["UNCLASSIFIED"]))),
            "question_types":dict(Counter(question_type(x) for x in rows)),
            "difficulty_hints":dict(Counter(difficulty_hint(x) for x in rows))}


def catalogs() -> tuple[list[dict], list[dict], dict[str, dict], dict[str, dict]]:
    skill_map, micro_map = load_curriculum_catalog(PRIVATE_JH_CATALOG_GRADES)
    return list(skill_map.values()), list(micro_map.values()), skill_map, micro_map


def mapping_prompt(question: dict[str, Any]) -> str:
    skills, micros, _, _ = catalogs()
    packet = build_candidate_packet({"fingerprint":question["fingerprint"], "question_text":question["question_text"],
        "unit":" ".join(question.get("topic_groups") or []), "knowledge_tag":question_type(question)}, skills, micros,
        skill_limit=14, micro_limit=50)
    context = {"skill_candidates":packet["skill_candidates"], "micro_candidates":packet["micro_candidates"]}
    guidance=json.loads((ROOT/"data/stage7/private_jh_topic_guidance_v1.json").read_text(encoding="utf-8"))
    return """You are mapping one official G6-to-G7 private-school entrance-style math question. The target band is G5/G6; real G1-G4 prerequisite curriculum IDs are also allowed.
Return one JSON object only. Do not invent IDs. A selected primary_micro_skill_id MUST have parent_skill_id equal to primary_skill_id. Every secondary_skill_id must be one of the listed skill candidates. Thinking skills are disabled.
High difficulty alone is NOT out of scope and does not imply COMPETITION. Use OUT_OF_SCOPE_PROFILE only with profile evidence that the item cannot reasonably support private-JH entrance assessment.
Required fields: scope_status (PRIVATE_JH or OUT_OF_SCOPE_PROFILE), primary_skill_id, primary_micro_skill_id, secondary_skill_ids (array), assessment_style, secondary_assessment_styles (array), difficulty (FOUNDATION/STANDARD/HIGH), confidence (0..1).
assessment_style and secondary_assessment_styles may only use: """ + ", ".join(sorted(PRIVATE_JH_STYLES)) + "\nCANDIDATE_GUIDANCE_ONLY (never Human Ground Truth):\n" + json.dumps(guidance,ensure_ascii=False) + "\nQUESTION:\n" + question["question_text"] + "\nCANDIDATE_CONTEXT:\n" + json.dumps(context, ensure_ascii=False)


def checkpoint_key(provider: str, fingerprint: str) -> str:
    return f"{PROFILE}:{fingerprint}:{provider}"


def _load_checkpoint(path: Path, provider: str, allowed: set[str]) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path); completed: dict[str, dict[str, Any]] = {}
    for row in rows:
        fp = row.get("fingerprint"); key = row.get("checkpoint_key")
        if fp not in allowed or key != checkpoint_key(provider, fp) or fp in completed:
            raise RuntimeError("INVALID_PROFILE_PROVIDER_CHECKPOINT")
        completed[fp] = row
    return completed


def _normalize_result(parsed: dict[str, Any], response: Any, question: dict[str, Any], provider: str, prompt_hash: str) -> dict[str, Any]:
    row = dict(parsed)
    row.update({"fingerprint":question["fingerprint"], "checkpoint_key":checkpoint_key(provider, question["fingerprint"]),
        "profile_type":PROFILE, "thinking_skill_ids":[], "primary_thinking_skill_id":"", "competition_level":None,
        "strategy_depth":None, "provider":provider, "model":response.model, "status":"COMPLETED",
        "latency_ms":round(response.latency_ms,2), "input_tokens":response.input_tokens, "output_tokens":response.output_tokens,
        "total_tokens":response.total_tokens, "prompt_fingerprint":prompt_hash, "source_school":question["source_school"],
        "source_year":question["source_year"], "topic_groups":question.get("topic_groups") or [],
        "question_type":question_type(question)})
    row.setdefault("secondary_skill_ids", []); row.setdefault("secondary_assessment_styles", [])
    return row


def run_provider(provider_name: str, questions: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    _, _, skill_map, micro_map = catalogs(); allowed = {q["fingerprint"] for q in questions}
    completed = _load_checkpoint(path, provider_name, allowed); path.parent.mkdir(parents=True, exist_ok=True)
    original_provider, original_ds = os.getenv("AI_PROVIDER"), os.getenv("DEEPSEEK_MODEL")
    try:
        os.environ["AI_PROVIDER"] = provider_name
        if provider_name == "deepseek": os.environ["DEEPSEEK_MODEL"] = DEEPSEEK_MODEL
        provider = get_ai_provider(secret_paths=SAFE_SECRET_PATHS)
        with path.open("a", encoding="utf-8") as handle:
            for question in questions:
                fp = question["fingerprint"]
                if fp in completed: continue
                prompt = mapping_prompt(question); prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
                response = provider.generate_json(prompt)
                row = _normalize_result(response.parsed_json or {}, response, question, provider_name, prompt_hash)
                errors = validate_mapping_result(row, grades=("G5","G6"))
                row["validation_errors"] = errors; row["validation_status"] = "VALID" if not errors else "INVALID"
                handle.write(json.dumps(row, ensure_ascii=False)+"\n"); handle.flush(); completed[fp] = row
    finally:
        if original_provider is None: os.environ.pop("AI_PROVIDER",None)
        else: os.environ["AI_PROVIDER"] = original_provider
        if original_ds is None: os.environ.pop("DEEPSEEK_MODEL",None)
        else: os.environ["DEEPSEEK_MODEL"] = original_ds
    return metrics(list(completed.values()), len(questions))


def correct_deepseek(manifest: dict[str, Any], correction_path: Path = DEEPSEEK_CORRECTIONS, attempt: int = 1) -> dict[str, Any]:
    """One bounded correction for rejected rows; valid completed keys are never called again."""
    original = read_jsonl(DEEPSEEK_CHECKPOINT)
    for row in original:
        errors=validate_mapping_result(row,grades=("G5","G6"));row["validation_errors"]=errors;row["validation_status"]="VALID" if not errors else "INVALID"
    invalid = {r["fingerprint"]:r for r in original if r.get("validation_status") != "VALID"}
    if not invalid:
        return metrics(original, 100)
    questions = {q["fingerprint"]:q for q in manifest["questions"]}
    targets = [questions[fp] for fp in invalid]
    _, _, skill_map, micro_map = catalogs(); allowed = set(invalid)
    completed = _load_checkpoint(correction_path, "deepseek", allowed)
    old_provider, old_model = os.getenv("AI_PROVIDER"), os.getenv("DEEPSEEK_MODEL")
    try:
        os.environ["AI_PROVIDER"]="deepseek"; os.environ["DEEPSEEK_MODEL"]=DEEPSEEK_MODEL
        provider=get_ai_provider(secret_paths=SAFE_SECRET_PATHS)
        correction_path.parent.mkdir(parents=True,exist_ok=True)
        with correction_path.open("a",encoding="utf-8") as handle:
            for question in targets:
                fp=question["fingerprint"]
                if fp in completed: continue
                base=mapping_prompt(question)
                prompt=(base+"\nCORRECTION REQUIREMENTS:\nThe prior result was rejected for: "+", ".join(invalid[fp]["validation_errors"])+
                    ". secondary_skill_ids must contain SKILL IDs only (never micro IDs). assessment_style cannot be blank. For OUT_OF_SCOPE_PROFILE all curriculum IDs must be blank/empty.")
                response=provider.generate_json(prompt); row=_normalize_result(response.parsed_json or {},response,question,"deepseek",hashlib.sha256(prompt.encode()).hexdigest())
                errors=validate_mapping_result(row,grades=("G5","G6"));row["validation_errors"]=errors;row["validation_status"]="VALID" if not errors else "INVALID";row["correction_attempt"]=attempt
                handle.write(json.dumps(row,ensure_ascii=False)+"\n");handle.flush();completed[fp]=row
    finally:
        if old_provider is None:os.environ.pop("AI_PROVIDER",None)
        else:os.environ["AI_PROVIDER"]=old_provider
        if old_model is None:os.environ.pop("DEEPSEEK_MODEL",None)
        else:os.environ["DEEPSEEK_MODEL"]=old_model
    corrected={r["fingerprint"]:r for r in original};corrected.update(completed)
    # Preserve the first rejected-attempt archive. A later bounded correction
    # must not overwrite the evidence needed to audit provider usage.
    if not DEEPSEEK_INVALID_ATTEMPTS.exists():
        DEEPSEEK_INVALID_ATTEMPTS.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in original if r["fingerprint"] in invalid),encoding="utf-8")
    DEEPSEEK_CHECKPOINT.write_text("".join(json.dumps(corrected[q["fingerprint"]],ensure_ascii=False)+"\n" for q in manifest["questions"]),encoding="utf-8")
    return metrics(list(corrected.values()),100)


def metrics(rows: list[dict[str, Any]], expected: int) -> dict[str, Any]:
    latencies = [float(r.get("latency_ms") or 0) for r in rows]; ordered=sorted(latencies)
    percentile = ordered[max(0, math.ceil(.95*len(ordered))-1)] if ordered else 0
    return {"completed":len(rows), "remaining":expected-len(rows), "in_scope":sum(r.get("scope_status")==PROFILE for r in rows),
        "out_of_scope":sum(r.get("scope_status")=="OUT_OF_SCOPE_PROFILE" for r in rows),
        "invalid":sum(r.get("validation_status")!="VALID" for r in rows), "json_failures":0, "provider_errors":0,
        "average_latency_ms":round(statistics.mean(latencies),2) if latencies else 0,
        "median_latency_ms":round(statistics.median(latencies),2) if latencies else 0, "p95_latency_ms":round(percentile,2),
        "input_tokens":sum(int(r.get("input_tokens") or 0) for r in rows), "output_tokens":sum(int(r.get("output_tokens") or 0) for r in rows),
        "total_tokens":sum(int(r.get("total_tokens") or 0) for r in rows)}


def validation20(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    questions = {q["fingerprint"]:q for q in manifest["questions"]}; deep = read_jsonl(DEEPSEEK_CHECKPOINT)
    if len(deep)!=100 or any(r.get("validation_status")!="VALID" for r in deep): raise RuntimeError("DEEPSEEK_GATE_NOT_PASS")
    ranked = sorted(deep, key=lambda r:(float(r.get("confidence") or 0), stable(r["fingerprint"])))
    priority = [r for r in ranked if float(r.get("confidence") or 0)<LOW_CONFIDENCE or r.get("scope_status")=="OUT_OF_SCOPE_PROFILE"
                or r.get("secondary_skill_ids") or r.get("assessment_style")=="CROSS_UNIT"]
    chosen: list[dict[str,Any]]=[]; seen:set[str]=set()
    for pool in (priority, ranked):
        while pool and len(chosen)<20:
            candidate=min((r for r in pool if r["fingerprint"] not in seen),
                key=lambda r:(sum(Counter(t for x in chosen for t in x.get("topic_groups",[]))[t] for t in (r.get("topic_groups") or ["UNCLASSIFIED"])), stable(r["fingerprint"])), default=None)
            if candidate is None: break
            chosen.append(candidate); seen.add(candidate["fingerprint"])
    return [questions[r["fingerprint"]] for r in chosen]


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    deep=read_jsonl(DEEPSEEK_CHECKPOINT); gem=read_jsonl(GEMINI_RESULTS); dmap={r["fingerprint"]:r for r in deep}; gmap={r["fingerprint"]:r for r in gem}
    if len(deep)!=100 or len(gem)!=20: raise RuntimeError("INCOMPLETE_PROVIDER_RESULTS")
    agree=Counter(); disagreements=[]
    for fp,g in gmap.items():
        d=dmap[fp]; scope=d.get("scope_status")==g.get("scope_status"); skill=d.get("primary_skill_id")==g.get("primary_skill_id"); micro=d.get("primary_micro_skill_id")==g.get("primary_micro_skill_id")
        agree["scope"]+=scope; agree["skill"]+=skill; agree["micro"]+=micro; agree["complete"]+=scope and skill and micro
        if not(scope and skill and micro): disagreements.append(fp)
    mapped=[r for r in deep if r.get("scope_status")==PROFILE and r.get("validation_status")=="VALID"]
    coverage={"raw_mapped_coverage":{"mapped_questions":len(mapped), "mapped_unique_primary_skills":len({r["primary_skill_id"] for r in mapped}),
        "mapped_unique_micros":len({r["primary_micro_skill_id"] for r in mapped}),
        "mapped_secondary_skills":len({s for r in mapped for s in r.get("secondary_skill_ids",[])}),
        "topic_groups_covered":len({t for r in mapped for t in r.get("topic_groups",[])}),
        "assessment_styles_covered":len({r.get("assessment_style") for r in mapped})},
        "human_validated_coverage":{"validated_questions":0,"validated_unique_primary_skills":0,"validated_unique_micros":0}}
    write_json(COVERAGE,coverage)
    reasons:dict[str,set[str]]={}
    def add(fp:str,reason:str): reasons.setdefault(fp,set()).add(reason)
    for r in deep:
        fp=r["fingerprint"]
        if r.get("validation_status")!="VALID": add(fp,"INVALID")
        if r.get("scope_status")=="OUT_OF_SCOPE_PROFILE": add(fp,"OUT_OF_SCOPE")
        if float(r.get("confidence") or 0)<LOW_CONFIDENCE: add(fp,"LOW_CONFIDENCE")
        if r.get("secondary_skill_ids") and r.get("difficulty")=="HIGH": add(fp,"CROSS_UNIT_HIGH_DIFFICULTY")
    for r in gem:
        if r.get("validation_status")!="VALID": add(r["fingerprint"],"INVALID")
    for fp in disagreements:add(fp,"PROVIDER_DISAGREEMENT")
    normal=[r for r in deep if r["fingerprint"] not in reasons]
    audit=_pick([{**next(q for q in manifest["questions"] if q["fingerprint"]==r["fingerprint"]),"_result":r} for r in normal],min(15,len(normal)))
    for q in audit:add(q["fingerprint"],"RANDOM_AUDIT")
    with REVIEW.open("w",newline="",encoding="utf-8-sig") as handle:
        fields=("fingerprint","source_school","source_year","question_number","topic_groups","reasons","scope_status","primary_skill_id","primary_micro_skill_id","confidence")
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        qmap={q["fingerprint"]:q for q in manifest["questions"]}
        for fp in sorted(reasons,key=stable):
            r=dmap[fp];q=qmap[fp];writer.writerow({"fingerprint":fp,"source_school":q["source_school"],"source_year":q["source_year"],"question_number":q["question_number"],
                "topic_groups":"|".join(q.get("topic_groups",[])),"reasons":"|".join(sorted(reasons[fp])),"scope_status":r.get("scope_status"),
                "primary_skill_id":r.get("primary_skill_id"),"primary_micro_skill_id":r.get("primary_micro_skill_id"),"confidence":r.get("confidence")})
    comparison={"questions":20,"scope_agreement":round(100*agree["scope"]/20,2),"skill_agreement":round(100*agree["skill"]/20,2),
        "micro_agreement":round(100*agree["micro"]/20,2),"complete_agreement":round(100*agree["complete"]/20,2),"agreement_is_accuracy":False}
    write_json(COMPARISON,comparison)
    reason_counts=Counter(reason for values in reasons.values() for reason in values)
    correction_calls=len(read_jsonl(DEEPSEEK_CORRECTIONS))+len(read_jsonl(DEEPSEEK_CORRECTIONS2))
    report={"sample":manifest["distribution"],"deepseek":metrics(deep,100),"gemini":metrics(gem,20),"agreement":comparison,"coverage":coverage,
        "human_review":{"total_queue":len(reasons),**dict(reason_counts)},"technical_pass":len(deep)==100 and not any(r.get("validation_status")!="VALID" for r in deep),
        "production_reads":0,"production_writes":0,
        "api_calls":{"deepseek":100+correction_calls,"deepseek_canonical":100,"deepseek_corrections":correction_calls,"gemini":20}}
    write_json(REPORT,report);return report


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("prepare","deepseek","correct","correct2","gemini","evaluate","all"));args=parser.parse_args()
    manifest=prepare() if args.command in ("prepare","all") else json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    if args.command in ("deepseek","all"): print(json.dumps(run_provider("deepseek",manifest["questions"],DEEPSEEK_CHECKPOINT)))
    if args.command in ("correct","all"): print(json.dumps(correct_deepseek(manifest)))
    if args.command=="correct2": print(json.dumps(correct_deepseek(manifest,DEEPSEEK_CORRECTIONS2,2)))
    if args.command in ("gemini","all"): print(json.dumps(run_provider("gemini",validation20(manifest),GEMINI_RESULTS)))
    if args.command in ("evaluate","all"): print(json.dumps(evaluate(manifest),ensure_ascii=False))
    return 0


if __name__=="__main__": raise SystemExit(main())
