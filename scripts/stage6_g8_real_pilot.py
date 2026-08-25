"""Stage 6C local-only G8 real-question DeepSeek mapping pilot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_provider import ProviderCallError, get_ai_provider

SOURCE = Path(r"C:\MathAI_G8_Pilot\.local\stage5_g8_mapping_pilot\scope200")
PRIVATE = ROOT / ".local" / "stage6_real_g8_pilot"
SAFE_SECRETS = (ROOT / ".streamlit" / "secrets.toml",)
EXPECTED = 200
TRANSIENT_ERRORS = {"RATE_LIMIT", "SERVER", "OVERLOADED", "NETWORK_ERROR", "TIMEOUT"}
SOURCE_FILES = {
    "sample": "g8_pilot_sample.json",
    "input": "g8_mapping_input.jsonl",
    "gemini_baseline": "g8_scope_mapping_results.jsonl",
    "skills": "g8_curriculum_skills.json",
    "micros": "g8_curriculum_micro_skills.json",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprints(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("fingerprint") or "") for row in rows]


def prepare() -> dict[str, Any]:
    source_paths = {name: SOURCE / filename for name, filename in SOURCE_FILES.items()}
    missing = [name for name, path in source_paths.items() if not path.is_file() and name != "gemini_baseline"]
    if missing:
        raise RuntimeError(f"SOURCE_FILES_MISSING:{','.join(missing)}")
    sample = read_json(source_paths["sample"])
    packets = read_jsonl(source_paths["input"])
    baseline = read_jsonl(source_paths["gemini_baseline"])
    skills = read_json(source_paths["skills"]); micros = read_json(source_paths["micros"])
    sample_fp, packet_fp, baseline_fp = _fingerprints(sample), _fingerprints(packets), _fingerprints(baseline)
    if len(sample) != EXPECTED or len(set(sample_fp)) != EXPECTED or "" in sample_fp:
        raise RuntimeError("SOURCE_SAMPLE_INTEGRITY_FAILED")
    if len(packets) != EXPECTED or set(packet_fp) != set(sample_fp) or len(set(packet_fp)) != EXPECTED:
        raise RuntimeError("SOURCE_PACKET_INTEGRITY_FAILED")
    if any(bool(row.get("synthetic") or row.get("synthetic_validation")) for row in sample + packets):
        raise RuntimeError("SYNTHETIC_SOURCE_REJECTED")
    baseline_complete = len(baseline) == EXPECTED and len(set(baseline_fp)) == EXPECTED and set(baseline_fp) == set(sample_fp)
    skill_ids = {str(row.get("skill_id") or "") for row in skills}; micro_ids = {str(row.get("micro_skill_id") or "") for row in micros}
    if "" in skill_ids or len(skill_ids) != len(skills) or "" in micro_ids or len(micro_ids) != len(micros):
        raise RuntimeError("CURRICULUM_ID_INTEGRITY_FAILED")
    if any(str(row.get("parent_skill_id") or "") not in skill_ids for row in micros):
        raise RuntimeError("CURRICULUM_MICRO_PARENT_INTEGRITY_FAILED")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    for name, source in source_paths.items():
        if source.is_file():
            shutil.copy2(source, PRIVATE / source.name)
    manifest = {
        "schema_version": 1, "source": "G8_STAGE5_SCOPE200_LOCAL_REAL", "sample_size": EXPECTED,
        "unique_fingerprints": len(set(sample_fp)), "real_questions": True, "synthetic": False,
        "gemini_baseline": "COMPLETE" if baseline_complete else "BASELINE_NOT_COMPLETE",
        "catalog": {"skills": len(skills), "micros": len(micros), "skill_micro_parent_integrity": "PASS"},
        "source_hashes": {name: sha256(path) for name, path in source_paths.items() if path.is_file()},
        "sample_fingerprint": hashlib.sha256("\n".join(sorted(sample_fp)).encode()).hexdigest(),
        "production_reads": 0, "production_writes": 0,
    }
    write_json(PRIVATE / "source_manifest.json", manifest)
    return manifest


def scope_catalog(skills: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "main_units": sorted({str(row.get("main_unit") or "") for row in skills if row.get("main_unit")}),
        "skill_names": sorted({str(row.get("skill_name") or "") for row in skills if row.get("skill_name")}),
    }


def mapping_prompt(packet: dict[str, Any], catalog: dict[str, Any]) -> str:
    compact = {key: packet.get(key) for key in (
        "fingerprint", "question_text", "answer_text", "unit", "knowledge_tag", "skill_candidates", "micro_candidates"
    )}
    return f"""You are a Taiwan Grade 8 mathematics curriculum scope checker and classifier for MathAI.

STEP 1 - Scope gate:
Decide whether the mathematical content itself belongs to the supplied G8 curriculum catalog.
The source unit/knowledge_tag may be dirty or from a wrong grade, so treat them only as weak hints.
Earlier-grade prerequisite exercises should be OUT_OF_SCOPE_G8 unless the question genuinely tests a G8 skill.

Critical guardrails discovered in pilot data:
- Integer factors/multiples, prime factorization, GCD/LCM are NOT the same as G8 polynomial factorization. Do not map integer GCD/LCM questions to G8 polynomial factorization.
- G7 two-variable linear equations / simultaneous linear equations are NOT G8 one-variable quadratic equations. Do not force them into G8 quadratic equations.
- A question may be mathematically valid but still OUT_OF_SCOPE_G8.

STEP 2 - Mapping only if IN_SCOPE_G8:
Choose exactly one primary skill_id from skill_candidates.
Choose micro_skill_id only from micro_candidates and only when it belongs to the chosen skill_id; otherwise null.
Do not invent IDs.

Return JSON only with keys:
fingerprint, scope_status, out_of_scope_reason, skill_id, micro_skill_id, question_type, difficulty, confidence, rationale_short

Rules:
- scope_status must be exactly IN_SCOPE_G8 or OUT_OF_SCOPE_G8.
- If OUT_OF_SCOPE_G8: skill_id=null, micro_skill_id=null, question_type="OUT_OF_SCOPE", difficulty=null.
- If IN_SCOPE_G8: skill_id must be one supplied candidate; micro_skill_id must obey parent relation.
- confidence is 0..1 and represents confidence in the combined scope+mapping decision.

G8 curriculum catalog:
{json.dumps(catalog, ensure_ascii=False)}

Question packet:
{json.dumps(compact, ensure_ascii=False)}
"""


def validate(row: dict[str, Any], skills: dict[str, Any], micros: dict[str, Any]) -> list[str]:
    errors: list[str] = []; scope = str(row.get("scope_status") or "")
    if scope not in {"IN_SCOPE_G8", "OUT_OF_SCOPE_G8"}:
        return ["INVALID_SCOPE_STATUS"]
    try:
        if not 0 <= float(row.get("confidence")) <= 1: errors.append("CONFIDENCE_OUT_OF_RANGE")
    except (TypeError, ValueError): errors.append("INVALID_CONFIDENCE")
    sid, mid = str(row.get("skill_id") or ""), str(row.get("micro_skill_id") or "")
    if scope == "OUT_OF_SCOPE_G8":
        if sid: errors.append("OUT_OF_SCOPE_HAS_SKILL")
        if mid: errors.append("OUT_OF_SCOPE_HAS_MICRO")
        return errors
    if sid not in skills: errors.append("INVALID_SKILL")
    if mid and mid not in micros: errors.append("INVALID_MICRO")
    if mid in micros and micros[mid].get("parent_skill_id") != sid: errors.append("MICRO_PARENT_MISMATCH")
    return errors


def checkpoint_rows() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(PRIVATE / "deepseek_checkpoint.jsonl")
    completed: dict[str, dict[str, Any]] = {}
    for row in rows:
        fp = str(row.get("fingerprint") or "")
        if not fp or fp in completed or row.get("provider") != "deepseek":
            raise RuntimeError("INVALID_DEEPSEEK_CHECKPOINT")
        completed[fp] = row
    return completed


def run() -> dict[str, Any]:
    manifest = read_json(PRIVATE / "source_manifest.json")
    if manifest.get("sample_size") != EXPECTED or not manifest.get("real_questions") or manifest.get("synthetic"):
        raise RuntimeError("PRIVATE_SOURCE_MANIFEST_INVALID")
    packets = read_jsonl(PRIVATE / SOURCE_FILES["input"]); known = set(_fingerprints(packets))
    completed = checkpoint_rows()
    if not set(completed).issubset(known): raise RuntimeError("CHECKPOINT_FINGERPRINT_NOT_IN_SOURCE")
    skills = read_json(PRIVATE / SOURCE_FILES["skills"]); micros = read_json(PRIVATE / SOURCE_FILES["micros"])
    catalog = scope_catalog(skills); checkpoint = PRIVATE / "deepseek_checkpoint.jsonl"
    original_provider, original_model = os.getenv("AI_PROVIDER"), os.getenv("DEEPSEEK_MODEL")
    os.environ["AI_PROVIDER"] = "deepseek"; os.environ["DEEPSEEK_MODEL"] = "deepseek-v4-flash"
    try:
        provider = get_ai_provider(secret_paths=SAFE_SECRETS)
        with checkpoint.open("a", encoding="utf-8") as handle:
            for packet in packets:
                fp = packet["fingerprint"]
                if fp in completed: continue
                prompt = mapping_prompt(packet, catalog); last_error: ProviderCallError | None = None
                for attempt in range(3):
                    try:
                        response = provider.generate_json(prompt); parsed = dict(response.parsed_json or {})
                        parsed.update({"fingerprint": fp, "provider": "deepseek", "model": response.model,
                                       "latency_ms": response.latency_ms, "input_tokens": response.input_tokens,
                                       "output_tokens": response.output_tokens, "total_tokens": response.total_tokens,
                                       "request_status": response.request_status, "retry_count": attempt,
                                       "prompt_fingerprint": hashlib.sha256(prompt.encode()).hexdigest()})
                        handle.write(json.dumps(parsed, ensure_ascii=False) + "\n"); handle.flush(); completed[fp] = parsed
                        break
                    except ProviderCallError as exc:
                        last_error = exc
                        if exc.error_type not in TRANSIENT_ERRORS or attempt == 2: raise
                        time.sleep(min(2 ** attempt, 4))
                if last_error and fp not in completed: raise last_error
    finally:
        if original_provider is None: os.environ.pop("AI_PROVIDER", None)
        else: os.environ["AI_PROVIDER"] = original_provider
        if original_model is None: os.environ.pop("DEEPSEEK_MODEL", None)
        else: os.environ["DEEPSEEK_MODEL"] = original_model
    ordered = [completed[row["fingerprint"]] for row in packets]
    (PRIVATE / "deepseek_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ordered), encoding="utf-8")
    return {"completed": len(ordered), "remaining": EXPECTED - len(ordered)}


def _percent(n: int, d: int) -> float:
    return round(100 * n / d, 2) if d else 0.0


def _agreement_audit_sample(rows: list[dict[str, Any]], packets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []; seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        packet = packets[row["fingerprint"]]
        stratum = (str(row.get("skill_id") or "OUT"), str(row.get("micro_skill_id") or "OUT"),
                   str(row.get("question_type") or ""), str(packet.get("unit") or packet.get("knowledge_tag") or ""))
        if stratum not in seen:
            chosen.append(row); seen.add(stratum)
        if len(chosen) == 20: break
    if len(chosen) < 20:
        remaining = [row for row in rows if row not in chosen]
        chosen.extend(remaining[:20 - len(chosen)])
    return chosen


def evaluate() -> dict[str, Any]:
    manifest = read_json(PRIVATE / "source_manifest.json"); packets_list = read_jsonl(PRIVATE / SOURCE_FILES["input"])
    packets = {row["fingerprint"]: row for row in packets_list}; results = read_jsonl(PRIVATE / "deepseek_results.jsonl")
    if len(results) != EXPECTED or len(set(_fingerprints(results))) != EXPECTED: raise RuntimeError("DEEPSEEK_RESULTS_INCOMPLETE")
    skills_list = read_json(PRIVATE / SOURCE_FILES["skills"]); micros_list = read_json(PRIVATE / SOURCE_FILES["micros"])
    skills = {row["skill_id"]: row for row in skills_list}; micros = {row["micro_skill_id"]: row for row in micros_list}
    invalid = {row["fingerprint"]: validate(row, skills, micros) for row in results}; invalid = {k: v for k, v in invalid.items() if v}
    baseline_rows = read_jsonl(PRIVATE / SOURCE_FILES["gemini_baseline"]); baseline = {row["fingerprint"]: row for row in baseline_rows}
    baseline_complete = len(baseline) == EXPECTED and set(baseline) == set(packets)
    agreements = {"scope": 0, "skill": 0, "micro": 0, "complete": 0}; disagreement_types = {
        "scope": set(), "skill": set(), "micro": set(), "out_of_scope": set()
    }
    fully_agreed = []
    for row in results:
        fp = row["fingerprint"]
        if not baseline_complete: continue
        old = baseline[fp]
        checks = {"scope": row.get("scope_status") == old.get("scope_status"),
                  "skill": (row.get("skill_id") or None) == (old.get("skill_id") or None),
                  "micro": (row.get("micro_skill_id") or None) == (old.get("micro_skill_id") or None)}
        for key, ok in checks.items(): agreements[key] += int(ok)
        complete = all(checks.values()); agreements["complete"] += int(complete)
        if complete: fully_agreed.append(row)
        else:
            for key, ok in checks.items():
                if not ok: disagreement_types[key].add(fp)
            if "OUT_OF_SCOPE_G8" in {row.get("scope_status"), old.get("scope_status")}: disagreement_types["out_of_scope"].add(fp)
    out_scope = {row["fingerprint"] for row in results if row.get("scope_status") == "OUT_OF_SCOPE_G8"}
    suspicious = {row["fingerprint"] for row in results if float(row.get("confidence") or 0) < 0.7}
    disagreements = set().union(*disagreement_types.values()) if baseline_complete else set()
    audit_sample = _agreement_audit_sample(fully_agreed, packets) if baseline_complete else []
    audit_fps = {row["fingerprint"] for row in audit_sample}; queue_fps = disagreements | out_scope | set(invalid) | suspicious | audit_fps
    queue = []
    for fp in sorted(queue_fps):
        reasons = []
        if fp in disagreements: reasons.append("PROVIDER_DISAGREEMENT")
        if fp in out_scope: reasons.append("OUT_OF_SCOPE")
        if fp in invalid: reasons.append("INVALID")
        if fp in suspicious: reasons.append("SUSPICIOUS")
        if fp in audit_fps: reasons.append("AGREEMENT_AUDIT_SAMPLE")
        queue.append({"fingerprint": fp, "reasons": "|".join(reasons), "review_status": "PENDING"})
    with (PRIVATE / "human_review_private.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("fingerprint", "reasons", "review_status")); writer.writeheader(); writer.writerows(queue)
    latencies = sorted(float(row["latency_ms"]) for row in results); p95 = latencies[max(0, int(0.95 * len(latencies) + .999999) - 1)]
    usage = {}
    for key in ("input", "output", "total"):
        vals = [row.get(f"{key}_tokens") for row in results]
        usage[key] = sum(int(v) for v in vals) if all(v is not None for v in vals) else "NOT_AVAILABLE"
    mapped_skills = {row.get("skill_id") for row in results if row.get("skill_id")}; mapped_micros = {row.get("micro_skill_id") for row in results if row.get("micro_skill_id")}
    coverage = {"mapped_questions": EXPECTED, "mapped_unique_skills": len(mapped_skills), "mapped_unique_micros": len(mapped_micros),
                "total_skills": len(skills), "total_micros": len(micros), "raw_skill_coverage": _percent(len(mapped_skills), len(skills)),
                "raw_micro_coverage": _percent(len(mapped_micros), len(micros)), "human_review_required": len(queue),
                "human_validated_questions": 0, "validated_unique_skills": 0, "validated_unique_micros": 0,
                "human_validated_skill_coverage": 0.0, "human_validated_micro_coverage": 0.0}
    write_json(PRIVATE / "real_coverage_private.json", coverage)
    comparison = {"source": manifest, "deepseek": {"calls": EXPECTED, "completed": EXPECTED, "remaining": 0,
        "in_scope": sum(row.get("scope_status") == "IN_SCOPE_G8" for row in results), "out_of_scope": len(out_scope),
        "invalid": len(invalid), "json_failures": 0, "provider_errors": 0,
        "average_latency_ms": round(statistics.mean(latencies), 2), "median_latency_ms": round(statistics.median(latencies), 2),
        "p95_latency_ms": round(p95, 2), "input_tokens": usage["input"], "output_tokens": usage["output"], "total_tokens": usage["total"]},
        "baseline": "COMPLETE" if baseline_complete else "BASELINE_NOT_COMPLETE",
        "agreement": {key: _percent(value, EXPECTED) if baseline_complete else "NOT_AVAILABLE" for key, value in agreements.items()},
        "disagreement_count": len(disagreements) if baseline_complete else "NOT_AVAILABLE",
        "human_review": {"total": len(queue), "provider_disagreements": len(disagreements), "out_of_scope": len(out_scope),
                         "suspicious": len(suspicious), "agreement_audit_sample": len(audit_sample)},
        "coverage": coverage, "production_reads": 0, "production_writes": 0}
    write_json(PRIVATE / "provider_comparison_private.json", comparison)
    return comparison


def write_summary(value: dict[str, Any]) -> None:
    d, a, h, c = value["deepseek"], value["agreement"], value["human_review"], value["coverage"]
    text = f"""# Stage 6C G8 Real-Question DeepSeek Pilot Summary

- Source: {EXPECTED} local real questions; {EXPECTED} unique fingerprints; synthetic 0; Gemini baseline {value['baseline']}.
- DeepSeek: completed {d['completed']}, remaining {d['remaining']}, in-scope {d['in_scope']}, out-of-scope {d['out_of_scope']}, invalid {d['invalid']}, JSON failures {d['json_failures']}, provider errors {d['provider_errors']}.
- Latency: average {d['average_latency_ms']} ms; median {d['median_latency_ms']} ms; P95 {d['p95_latency_ms']} ms.
- Tokens: input {d['input_tokens']}; output {d['output_tokens']}; total {d['total_tokens']}.
- Raw mapped coverage: {c['mapped_unique_skills']}/{c['total_skills']} Skills ({c['raw_skill_coverage']}%); {c['mapped_unique_micros']}/{c['total_micros']} Micros ({c['raw_micro_coverage']}%).
- Human-validated coverage: {c['validated_unique_skills']}/{c['total_skills']} Skills ({c['human_validated_skill_coverage']}%); {c['validated_unique_micros']}/{c['total_micros']} Micros ({c['human_validated_micro_coverage']}%).
- Provider agreement: scope {a['scope']}%; skill {a['skill']}%; micro {a['micro']}%; complete {a['complete']}%; disagreements {value['disagreement_count']}.
- Human review queue: total {h['total']}; provider disagreements {h['provider_disagreements']}; out-of-scope {h['out_of_scope']}; suspicious {h['suspicious']}; stratified agreement audit {h['agreement_audit_sample']}.
- Recommendation: keep DeepSeek as the Stage 6 primary mapper, require human review before any database write, and do not use Gemini agreement as ground truth.
- Safety: production reads 0; production writes 0; Supabase not used; secrets exposed 0.
"""
    path = ROOT / "docs" / "stage6" / "STAGE6_G8_REAL_QUESTION_PILOT_SUMMARY.md"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("prepare", "run", "evaluate", "all")); args = parser.parse_args()
    if args.command in {"prepare", "all"}: prepare()
    if args.command in {"run", "all"}: run()
    if args.command in {"evaluate", "all"}:
        value = evaluate(); write_summary(value); print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
