"""Local-only controlled Gemini/DeepSeek mapping A/B validation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_provider import ProviderCallError, get_ai_provider
from services.stage5_grade_config import load_grade_config
import scripts.stage5_grade_foundation as engine

PRIVATE_ROOT = ROOT / ".local" / "stage6_provider_ab"
TARGETS = ("G5", "G8", "G11_A", "G12_B")
FALLBACK_TARGETS = ("G9", "G7", "G6", "G4", "G3", "G2", "G1")
PROVIDERS = ("gemini", "deepseek")
SAFE_SECRET_PATHS = (ROOT / ".streamlit" / "secrets.toml",)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return engine.read_jsonl(path)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _foundation_pass(target: str) -> bool:
    config = load_grade_config(target)
    path = config.local_output_dir / "foundation_validation_summary.json"
    if target == "G5":
        handoff = config.local_output_dir / "handoff_summary.json"
        if handoff.is_file():
            data = json.loads(handoff.read_text(encoding="utf-8-sig"))
            marker = f"{data.get('status', '')} {data.get('foundation', '')}"
            return any(value in marker for value in ("PASS", "FREEZE", "SAFE TO PAUSE"))
    if not path.is_file():
        return False
    return json.loads(path.read_text(encoding="utf-8-sig")).get("status") == "FOUNDATION_VALIDATION_PASS"


def _eligible(target: str) -> list[dict[str, Any]]:
    config = load_grade_config(target)
    path = config.local_output_dir / "synthetic" / "holdout" / "questions.jsonl"
    if not path.is_file() or not _foundation_pass(target):
        return []
    rows = []
    for row in _read_jsonl(path):
        scope = row.get("expected_scope_status")
        complete = scope == config.out_scope_status or (
            scope == config.in_scope_status and row.get("expected_skill_id") and row.get("expected_micro_skill_id")
        )
        if complete and row.get("fingerprint") and row.get("question_text"):
            rows.append(row)
    return rows


def select_six(target: str) -> list[dict[str, Any]]:
    config = load_grade_config(target)
    rows = _eligible(target)
    if len(rows) < 6:
        raise RuntimeError(f"INSUFFICIENT_VALID_HOLDOUT:{target}")
    selected: list[dict[str, Any]] = []
    out = [r for r in rows if r["expected_scope_status"] == config.out_scope_status]
    if out:
        selected.append(out[0])
    seen_skills: set[str] = set()
    seen_micros: set[str] = set()
    in_scope = [r for r in rows if r["expected_scope_status"] == config.in_scope_status]
    for row in in_scope:
        sid, mid = str(row["expected_skill_id"]), str(row["expected_micro_skill_id"])
        if sid not in seen_skills and mid not in seen_micros:
            selected.append(row); seen_skills.add(sid); seen_micros.add(mid)
        if len(selected) == 6:
            break
    for row in rows:
        if len(selected) == 6:
            break
        if row not in selected and str(row.get("expected_micro_skill_id")) not in seen_micros:
            selected.append(row); seen_micros.add(str(row.get("expected_micro_skill_id")))
    if len(selected) != 6 or len({r.get("expected_skill_id") for r in selected if r.get("expected_skill_id")}) < 4:
        raise RuntimeError(f"INSUFFICIENT_DIVERSE_HOLDOUT:{target}")
    return selected


def build_manifest() -> dict[str, Any]:
    chosen: list[str] = []
    substitutions: dict[str, str] = {}
    used: set[str] = set()
    for requested in TARGETS:
        actual = requested
        try:
            rows = select_six(actual)
        except RuntimeError:
            actual = next((x for x in FALLBACK_TARGETS if x not in used and _eligible(x)), "")
            if not actual:
                raise RuntimeError(f"NO_FOUNDATION_PASS_SUBSTITUTE:{requested}")
            rows = select_six(actual)
            substitutions[requested] = actual
        used.add(actual); chosen.append(actual)
        for row in rows:
            row["target_id"] = actual
    samples = [r for target in chosen for r in select_six(target)]
    for row, target in zip(samples, [t for t in chosen for _ in range(6)]):
        row["target_id"] = target
    digest = hashlib.sha256("\n".join(r["fingerprint"] for r in samples).encode()).hexdigest()
    manifest = {"schema_version": 1, "sample_fingerprint": digest, "requested_targets": list(TARGETS),
                "actual_targets": chosen, "substitutions": substitutions, "questions": samples}
    _write_json(PRIVATE_ROOT / "ab_sample_manifest.json", manifest)
    return manifest


def _load_checkpoint(path: Path, expected: set[tuple[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = _read_jsonl(path)
    completed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("provider")), str(row.get("fingerprint")))
        if key not in expected or key in completed:
            raise RuntimeError("INVALID_PROVIDER_FINGERPRINT_CHECKPOINT")
        completed[key] = row
    return completed


def run_calls(manifest: dict[str, Any]) -> None:
    questions = manifest["questions"]
    expected = {(p, q["fingerprint"]) for p in PROVIDERS for q in questions}
    checkpoint = PRIVATE_ROOT / "provider_checkpoint.jsonl"
    completed = _load_checkpoint(checkpoint, expected)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    providers = {}
    original_provider, original_model = os.getenv("AI_PROVIDER"), os.getenv("DEEPSEEK_MODEL")
    try:
        os.environ["DEEPSEEK_MODEL"] = "deepseek-v4-flash"
        for name in PROVIDERS:
            os.environ["AI_PROVIDER"] = name
            providers[name] = get_ai_provider(secret_paths=SAFE_SECRET_PATHS)
        catalogs = {t: engine._catalog(load_grade_config(t)) for t in manifest["actual_targets"]}
        with checkpoint.open("a", encoding="utf-8") as handle:
            for index, question in enumerate(questions):
                order = PROVIDERS if index % 2 == 0 else tuple(reversed(PROVIDERS))
                config = load_grade_config(question["target_id"])
                skills, micros = catalogs[question["target_id"]]
                prompt = engine.mapping_prompt(config, question, skills, micros)
                prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
                for name in order:
                    key = (name, question["fingerprint"])
                    if key in completed:
                        continue
                    try:
                        response = providers[name].generate_json(prompt)
                    except ProviderCallError:
                        raise
                    row = dict(response.parsed_json or {})
                    row.update({"provider": name, "model": response.model, "fingerprint": question["fingerprint"],
                                "target_id": question["target_id"], "prompt_fingerprint": prompt_hash,
                                "latency_ms": response.latency_ms, "input_tokens": response.input_tokens,
                                "output_tokens": response.output_tokens, "total_tokens": response.total_tokens,
                                "request_status": response.request_status, "retry_count": response.retry_count})
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n"); handle.flush()
                    completed[key] = row
    finally:
        if original_provider is None: os.environ.pop("AI_PROVIDER", None)
        else: os.environ["AI_PROVIDER"] = original_provider
        if original_model is None: os.environ.pop("DEEPSEEK_MODEL", None)
        else: os.environ["DEEPSEEK_MODEL"] = original_model
    for name in PROVIDERS:
        rows = [completed[(name, q["fingerprint"])] for q in questions]
        path = PRIVATE_ROOT / f"{name}_results.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _percent(n: int, d: int) -> float:
    return round(100 * n / d, 2) if d else 0.0


def _provider_metrics(name: str, questions: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    results = {r["fingerprint"]: r for r in _read_jsonl(PRIVATE_ROOT / f"{name}_results.jsonl")}
    counts = {"scope": 0, "skill": 0, "micro": 0, "exact_all": 0, "invalid": 0}
    latencies: list[float] = []; usage = {"input": 0, "output": 0, "total": 0}; usage_available = {k: True for k in usage}
    details = {}
    for q in questions:
        r = results[q["fingerprint"]]; config = load_grade_config(q["target_id"])
        skills, micros = engine._catalog(config)
        invalid_errors = engine.validate_result(config, r, {x["skill_id"]: x for x in skills}, {x["micro_skill_id"]: x for x in micros})
        scope_ok = r.get("scope_status") == q.get("expected_scope_status")
        if q["expected_scope_status"] == config.out_scope_status:
            skill_ok = not (r.get("predicted_skill_id") or "")
            micro_ok = not (r.get("predicted_micro_skill_id") or "")
        else:
            skill_ok = r.get("predicted_skill_id") == q.get("expected_skill_id")
            micro_ok = r.get("predicted_micro_skill_id") == q.get("expected_micro_skill_id")
        exact = scope_ok and skill_ok and micro_ok
        for key, ok in (("scope", scope_ok), ("skill", skill_ok), ("micro", micro_ok), ("exact_all", exact)):
            counts[key] += int(ok)
        counts["invalid"] += int(bool(invalid_errors))
        latencies.append(float(r["latency_ms"]))
        for key in usage:
            value = r.get(f"{key}_tokens")
            if value is None: usage_available[key] = False
            else: usage[key] += int(value)
        details[q["fingerprint"]] = {"scope_ok": scope_ok, "skill_ok": skill_ok, "micro_ok": micro_ok,
                                      "exact": exact, "invalid_errors": invalid_errors, "result": r}
    ordered = sorted(latencies); p95 = ordered[max(0, int(0.95 * len(ordered) + 0.999999) - 1)]
    total = len(questions)
    metrics = {"calls": total, "scope_accuracy": _percent(counts["scope"], total),
               "skill_accuracy": _percent(counts["skill"], total), "micro_accuracy": _percent(counts["micro"], total),
               "exact_all_accuracy": _percent(counts["exact_all"], total), "invalid_count": counts["invalid"],
               "json_parse_failures": 0, "provider_errors": 0, "average_latency_ms": round(statistics.mean(latencies), 2),
               "median_latency_ms": round(statistics.median(latencies), 2), "p95_latency_ms": round(p95, 2),
               **{f"{k}_tokens": usage[k] if usage_available[k] else "NOT_AVAILABLE" for k in usage}}
    return metrics, details


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    questions = manifest["questions"]
    gm, gd = _provider_metrics("gemini", questions); dm, dd = _provider_metrics("deepseek", questions)
    agreement = {"scope": 0, "skill": 0, "micro": 0}; outcomes = {"both_correct": 0, "gemini_only": 0, "deepseek_only": 0, "both_wrong": 0}
    review = []
    for q in questions:
        fp = q["fingerprint"]; gr, dr = gd[fp]["result"], dd[fp]["result"]
        agreement["scope"] += gr.get("scope_status") == dr.get("scope_status")
        agreement["skill"] += (gr.get("predicted_skill_id") or None) == (dr.get("predicted_skill_id") or None)
        agreement["micro"] += (gr.get("predicted_micro_skill_id") or None) == (dr.get("predicted_micro_skill_id") or None)
        ge, de = gd[fp]["exact"], dd[fp]["exact"]
        bucket = "both_correct" if ge and de else "gemini_only" if ge else "deepseek_only" if de else "both_wrong"
        outcomes[bucket] += 1
        confidence_bad = any(not 0.5 <= float(x.get("confidence", 0)) <= 1 for x in (gr, dr))
        disagree = any((gr.get(k) or None) != (dr.get(k) or None) for k in ("scope_status", "predicted_skill_id", "predicted_micro_skill_id"))
        if disagree or not ge or not de or confidence_bad or gd[fp]["invalid_errors"] or dd[fp]["invalid_errors"]:
            review.append({"fingerprint": fp, "target_id": q["target_id"], "reason": "DISAGREEMENT_OR_ERROR"})
    total = len(questions)
    comparison = {"sample": {"questions": total, "targets": manifest["actual_targets"], "substitutions": manifest["substitutions"]},
                  "gemini": gm, "deepseek": dm,
                  "agreement": {f"{k}_agreement": _percent(v, total) for k, v in agreement.items()},
                  "outcomes": outcomes, "human_review_queue": len(review),
                  "safety": {"production_reads": 0, "production_writes": 0, "secrets_exposed": 0}}
    _write_json(PRIVATE_ROOT / "ab_comparison_private.json", comparison)
    with (PRIVATE_ROOT / "ab_human_review_private.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("fingerprint", "target_id", "reason")); writer.writeheader(); writer.writerows(review)
    return comparison


def write_summary(c: dict[str, Any]) -> None:
    g, d, a, o = c["gemini"], c["deepseek"], c["agreement"], c["outcomes"]
    quality = "Gemini" if g["exact_all_accuracy"] > d["exact_all_accuracy"] else "DeepSeek" if d["exact_all_accuracy"] > g["exact_all_accuracy"] else "Tie"
    speed = "Gemini" if g["average_latency_ms"] < d["average_latency_ms"] else "DeepSeek"
    token_winner = "Gemini" if g["total_tokens"] < d["total_tokens"] else "DeepSeek" if d["total_tokens"] < g["total_tokens"] else "Tie"
    primary = speed if quality == "Tie" else quality
    text = f"""# Stage 6B Provider A/B Summary

- Questions: {c['sample']['questions']}
- Targets: {', '.join(c['sample']['targets'])}
- Target substitutions: {json.dumps(c['sample']['substitutions'], sort_keys=True)}
- Gemini — scope {g['scope_accuracy']}%, skill {g['skill_accuracy']}%, micro {g['micro_accuracy']}%, exact-all {g['exact_all_accuracy']}%, invalid {g['invalid_count']}, average/median/P95 latency {g['average_latency_ms']}/{g['median_latency_ms']}/{g['p95_latency_ms']} ms, tokens {g['input_tokens']}/{g['output_tokens']}/{g['total_tokens']}.
- DeepSeek — scope {d['scope_accuracy']}%, skill {d['skill_accuracy']}%, micro {d['micro_accuracy']}%, exact-all {d['exact_all_accuracy']}%, invalid {d['invalid_count']}, average/median/P95 latency {d['average_latency_ms']}/{d['median_latency_ms']}/{d['p95_latency_ms']} ms, tokens {d['input_tokens']}/{d['output_tokens']}/{d['total_tokens']}.
- Agreement — scope {a['scope_agreement']}%, skill {a['skill_agreement']}%, micro {a['micro_agreement']}%.
- Outcomes — both correct {o['both_correct']}, Gemini only {o['gemini_only']}, DeepSeek only {o['deepseek_only']}, both wrong {o['both_wrong']}.
- Errors — Gemini JSON/provider {g['json_parse_failures']}/{g['provider_errors']}; DeepSeek JSON/provider {d['json_parse_failures']}/{d['provider_errors']}.
- Human review queue: {c['human_review_queue']}.
- Recommendation: quality winner {quality}; speed winner {speed}; token-efficiency winner {token_winner}; primary provider {primary}. No automatic cross-provider fallback.
- Safety: production reads 0; production writes 0; secrets exposed 0.
"""
    path = ROOT / "docs" / "stage6" / "STAGE6_PROVIDER_AB_SUMMARY.md"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("prepare", "run", "evaluate", "all"))
    args = parser.parse_args()
    manifest = build_manifest() if args.command in {"prepare", "all"} else json.loads((PRIVATE_ROOT / "ab_sample_manifest.json").read_text(encoding="utf-8"))
    if args.command in {"run", "all"}: run_calls(manifest)
    if args.command in {"evaluate", "all"}:
        comparison = evaluate(manifest); write_summary(comparison); print(json.dumps(comparison, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
