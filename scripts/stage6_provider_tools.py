"""Stage 6 provider probe and local-only A/B comparison tools."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_provider import ProviderCallError, get_ai_provider, load_minimal_secret
from services.stage5_grade_config import load_grade_config
import scripts.stage5_grade_foundation as engine


def probe(name: str) -> int:
    os.environ["AI_PROVIDER"] = name
    config = load_grade_config("G5")
    if name == "deepseek" and not load_minimal_secret(("DEEPSEEK_API_KEY",), config.gemini_secret_paths):
        print("DEEPSEEK_NOT_CONFIGURED")
        return 0
    try:
        provider = get_ai_provider(secret_paths=config.gemini_secret_paths)
        if name == "deepseek":
            result = provider.diagnose()
            print(json.dumps(result, sort_keys=True))
            return 0 if result["chat_completion"] == "PASS" else 1
        print(provider.health_check())
        return 0
    except Exception as exc:
        normalized = exc.error_type if isinstance(exc, ProviderCallError) else "UNKNOWN_PROVIDER_ERROR"
        print(json.dumps({"provider": name, "normalized_error": normalized}))
        return 1


def compare(target: str, set_name: str = "holdout") -> int:
    config = load_grade_config(target)
    source = config.local_output_dir / "synthetic" / set_name / "questions.jsonl"
    questions = engine.read_jsonl(source)
    skills, micros = engine._catalog(config)
    skill_map = {row["skill_id"]: row for row in skills}
    micro_map = {row["micro_skill_id"]: row for row in micros}
    root = ROOT / ".local" / "stage6_provider_ab" / target.lower()
    summaries = {}
    original = os.environ.get("AI_PROVIDER")
    try:
        for provider_name in ("gemini", "deepseek"):
            os.environ["AI_PROVIDER"] = provider_name
            provider = get_ai_provider(secret_paths=config.gemini_secret_paths)
            checkpoint = root / provider_name / "checkpoint.jsonl"
            existing = engine.read_jsonl(checkpoint)
            known = {row["fingerprint"] for row in questions}
            completed = {row.get("fingerprint"): row for row in existing}
            if "" in completed or None in completed or len(completed) != len(existing) or not set(completed).issubset(known):
                raise RuntimeError("INVALID_CHECKPOINT_FINGERPRINT")
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            latencies = []; token_in = token_out = token_total = parse_failures = provider_errors = 0
            with checkpoint.open("a", encoding="utf-8") as handle:
                for question in questions:
                    if question["fingerprint"] in completed:
                        continue
                    try:
                        response = provider.generate_json(engine.mapping_prompt(config, question, skills, micros))
                        row = dict(response.parsed_json or {})
                        row["fingerprint"] = question["fingerprint"]
                        row["_provider"] = provider.provider_name
                        row["_model"] = provider.model_name
                        row["_latency_ms"] = response.latency_ms
                        row["_input_tokens"] = response.input_tokens
                        row["_output_tokens"] = response.output_tokens
                        row["_total_tokens"] = response.total_tokens
                        handle.write(json.dumps(row, ensure_ascii=False) + "\n"); handle.flush()
                        completed[row["fingerprint"]] = row
                    except ProviderCallError as exc:
                        if exc.error_type == "INVALID_JSON": parse_failures += 1
                        else: provider_errors += 1
                        raise
            mismatches = invalid = 0
            for question in questions:
                row = completed[question["fingerprint"]]
                errors = engine.validate_result(config, row, skill_map, micro_map)
                invalid += bool(errors)
                mismatch = (row.get("scope_status") != question.get("expected_scope_status"))
                if not mismatch and question.get("expected_scope_status") == config.in_scope_status:
                    mismatch = (row.get("predicted_skill_id") != question.get("expected_skill_id") or
                                row.get("predicted_micro_skill_id") != question.get("expected_micro_skill_id"))
                mismatches += int(mismatch)
                latencies.append(float(row.get("_latency_ms") or 0))
                token_in += int(row.get("_input_tokens") or 0); token_out += int(row.get("_output_tokens") or 0)
                token_total += int(row.get("_total_tokens") or 0)
            total = len(questions)
            summaries[provider_name] = {
                "provider": provider_name, "model": provider.model_name, "questions": total,
                "invalid": invalid, "mismatches": mismatches, "json_parse_failures": parse_failures,
                "average_latency_ms": round(sum(latencies) / total, 2) if total else 0,
                "input_tokens": token_in, "output_tokens": token_out, "total_tokens": token_total,
                "provider_errors": provider_errors,
            }
    finally:
        if original is None: os.environ.pop("AI_PROVIDER", None)
        else: os.environ["AI_PROVIDER"] = original
    engine.write_json(root / "comparison_summary.json", {"target_id": target, "set": set_name, "providers": summaries})
    print("PROVIDER_AB_COMPARE_COMPLETE")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    probe_parser = sub.add_parser("probe"); probe_parser.add_argument("provider", choices=("gemini", "deepseek"))
    compare_parser = sub.add_parser("compare"); compare_parser.add_argument("target"); compare_parser.add_argument("--set", default="holdout")
    args = parser.parse_args()
    return probe(args.provider) if args.command == "probe" else compare(args.target, args.set)


if __name__ == "__main__":
    raise SystemExit(main())
