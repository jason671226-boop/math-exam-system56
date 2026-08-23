"""Validate G8 ingestion batches against Master Curriculum and basic algebra."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "master_curriculum_v2_7" / "grade_packs" / "G8"
DEFAULT_BATCH = ROOT / "app" / "data" / "question_ingestion" / "g8" / "our_g8_linear_model_batch_001.json"
REQUIRED = {
    "question_id", "skill_id", "micro_skill_id", "question_type",
    "item_pattern", "difficulty", "common_error", "question_text", "answer",
    "solution", "source_kind", "rights_status", "quality_status", "validated",
    "archetype_key", "source_item_ref", "validation",
}


def _master_micros() -> dict[str, dict[str, str]]:
    with (MASTER / "layer2_micro_skills.csv").open(encoding="utf-8-sig", newline="") as handle:
        return {row["micro_skill_id"]: row for row in csv.DictReader(handle)}


def _normalized(value: str, *, semantic: bool = False) -> str:
    value = re.sub(r"\s+", "", value).lower()
    if semantic:
        value = re.sub(r"\d+(?:\.\d+)?", "#", value)
    return value


def _hash(value: str, *, semantic: bool = False) -> str:
    return hashlib.sha256(_normalized(value, semantic=semantic).encode("utf-8")).hexdigest()


def _evaluate(expression: str, values: dict[str, float]) -> float:
    """Evaluate the tiny arithmetic grammar used in validation metadata."""
    operators = {
        ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
        ast.USub: lambda a: -a, ast.UAdd: lambda a: a,
    }

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in values:
            return float(values[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.operand))
        raise ValueError("unsupported validation expression")

    return visit(ast.parse(expression, mode="eval"))


def _math_valid(spec: dict[str, Any]) -> bool:
    if spec["kind"] == "linear_equation":
        variable = str(spec["variable"])
        f0 = _evaluate(spec["lhs"], {variable: 0})
        f1 = _evaluate(spec["lhs"], {variable: 1})
        f2 = _evaluate(spec["lhs"], {variable: 2})
        expected = float(spec["expected"])
        return (
            abs((f2 - f1) - (f1 - f0)) < 1e-9
            and abs(f1 - f0) > 1e-9
            and abs(_evaluate(spec["lhs"], {variable: expected}) - float(spec["rhs"])) < 1e-9
        )
    if spec["kind"] == "linear_model":
        names = {node.id for node in ast.walk(ast.parse(spec["equation"], mode="eval"))
                 if isinstance(node, ast.Name)}
        return len(names) == 1 and abs(
            _evaluate(spec["equation"], {next(iter(names)): float(spec["input"])})
            - float(spec["expected"])
        ) < 1e-9
    return False


def validate_batch(path: Path) -> tuple[dict[str, Any], list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    micros = _master_micros()
    errors: list[str] = []
    exact_hashes: set[str] = set()
    semantic_groups: dict[str, list[str]] = {}
    for index, question in enumerate(payload.get("questions", []), 1):
        label = str(question.get("question_id") or index)
        missing = REQUIRED - set(question)
        if missing:
            errors.append(f"{label}: missing {','.join(sorted(missing))}")
            continue
        master = micros.get(question["micro_skill_id"])
        if not master:
            errors.append(f"{label}: unknown micro_skill_id")
            continue
        for item_key, master_key in (
            ("skill_id", "parent_skill_id"), ("question_type", "question_type"),
            ("item_pattern", "item_pattern"), ("difficulty", "difficulty"),
            ("common_error", "common_error"),
        ):
            if question[item_key] != master[master_key]:
                errors.append(f"{label}: {item_key} mismatch")
        content_hash = _hash(question["question_text"])
        semantic_hash = _hash(question["question_text"], semantic=True)
        if content_hash in exact_hashes:
            errors.append(f"{label}: exact duplicate")
        exact_hashes.add(content_hash)
        semantic_groups.setdefault(semantic_hash, []).append(label)
        question["content_hash"] = content_hash
        question["semantic_hash"] = semantic_hash
        if not _math_valid(question["validation"]):
            errors.append(f"{label}: answer validation failed")
        if question["rights_status"] != payload["source"]["rights_status"]:
            errors.append(f"{label}: rights_status mismatch")
    payload["validation_summary"] = {
        "question_count": len(payload.get("questions", [])),
        "exact_duplicates": len(payload.get("questions", [])) - len(exact_hashes),
        "shared_semantic_groups": sum(1 for ids_ in semantic_groups.values() if len(ids_) > 1),
        "errors": errors,
    }
    return payload, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", nargs="?", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--write-hashes", action="store_true")
    args = parser.parse_args()
    payload, errors = validate_batch(args.batch)
    if args.write_hashes:
        args.batch.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = payload["validation_summary"]
    print(
        f"G8 BATCH VALIDATION: {'FAIL' if errors else 'PASS'} "
        f"questions={summary['question_count']} exact_duplicates={summary['exact_duplicates']} "
        f"shared_semantic_groups={summary['shared_semantic_groups']} errors={len(errors)}"
    )
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
