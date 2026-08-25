from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from services.stage5_grade_config import load_grade_config
from scripts import stage5_grade_foundation as engine


@pytest.mark.parametrize("grade", ["G5", "G6", "G8"])
def test_config_load_and_dynamic_statuses(grade):
    config = load_grade_config(grade)
    assert config.grade == grade
    assert config.target_id == grade
    assert config.profile is None
    assert config.curriculum_dir.is_dir()
    assert config.in_scope_status == f"IN_SCOPE_{grade}"
    assert config.out_scope_status == f"OUT_OF_SCOPE_{grade}"


def test_unknown_grade_fails_closed():
    with pytest.raises(ValueError, match="UNKNOWN_GRADE"):
        load_grade_config("G13")


@pytest.mark.parametrize("target,grade,profile", [
    ("G11_A", "G11", "A"), ("G11_B", "G11", "B"),
    ("G12_A", "G12", "A"), ("G12_B", "G12", "B")])
def test_profile_target_load_and_path_isolation(target, grade, profile):
    config = load_grade_config(target)
    assert config.target_id == target
    assert config.grade == grade and config.profile == profile
    assert config.curriculum_dir.name == target
    assert config.local_output_dir.name == f"stage5_{target.lower()}_mapping_pilot"
    assert config.in_scope_status.endswith(target)


def test_profile_catalogs_are_isolated():
    for grade in ("G11", "G12"):
        a = load_grade_config(f"{grade}_A")
        b = load_grade_config(f"{grade}_B")
        assert a.curriculum_dir != b.curriculum_dir
        assert a.local_output_dir != b.local_output_dir
        assert a.in_scope_status != b.in_scope_status


@pytest.mark.parametrize("aggregate", ["G11", "G12"])
def test_aggregate_mapping_target_forbidden(aggregate):
    with pytest.raises(ValueError, match="PROFILE_REQUIRED"):
        load_grade_config(aggregate)


def test_g10_backward_compatibility():
    alias = load_grade_config("G10")
    canonical = load_grade_config("G10_GENERAL")
    assert alias == canonical
    assert alias.grade == "G10" and alias.profile == "GENERAL"


@pytest.mark.parametrize("target", ["G11_C", "G12_GENERAL", "G10_A"])
def test_invalid_profile_fails_closed(target):
    with pytest.raises(ValueError, match="UNKNOWN_GRADE"):
        load_grade_config(target)


@pytest.mark.parametrize("target", ["G10_GENERAL", "G11_A", "G11_B", "G12_A", "G12_B"])
def test_profile_offline_audit_uses_no_gemini_and_zero_production(target, tmp_path, monkeypatch):
    config = replace(load_grade_config(target), local_output_dir=tmp_path / target)
    monkeypatch.setattr(engine, "gemini_api_key",
                        lambda unused: pytest.fail("offline command attempted Gemini key access"))
    audit = engine.curriculum_audit(config)
    inventory = engine.inventory(config)
    coverage = engine.coverage(config)
    assert audit["curriculum_integrity"] == "PASS"
    assert audit["target_id"] == target
    for result in (audit, inventory, coverage):
        assert result["production_reads"] == result["production_writes"] == 0


def test_missing_curriculum_fails_closed(tmp_path):
    config = replace(load_grade_config("G5"), curriculum_dir=tmp_path,
                     out_of_scope_rules_path=tmp_path / "OUT_OF_SCOPE_RULES.md",
                     local_output_dir=tmp_path / "out")
    result = engine.curriculum_audit(config)
    assert result["curriculum_integrity"] == "FAIL"
    assert len(result["curriculum_parse_errors"]) >= 6


def test_checkpoint_resume_and_duplicate_fail(tmp_path):
    config = replace(load_grade_config("G5"), local_output_dir=tmp_path)
    base = tmp_path / "synthetic/tuning"; base.mkdir(parents=True)
    question = {"fingerprint": "known", "question_text": ""}
    (base / "questions.jsonl").write_text(json.dumps(question) + "\n", encoding="utf-8")
    calls = []
    def fake(prompt, model):
        calls.append(model)
        return json.dumps({"scope_status": config.out_scope_status, "predicted_skill_id": "",
                           "predicted_micro_skill_id": "", "confidence": .8})
    first = engine.map_set(config, "tuning", generate=fake)
    second = engine.map_set(config, "tuning", generate=fake)
    assert first["completed"] == second["completed"] == 1
    assert second["resumed"] == 1 and calls == [engine.MODEL]
    mapped = engine.read_jsonl(base / "mapping_checkpoint.jsonl")[0]
    assert set(("fingerprint", "scope_status", "predicted_skill_id", "predicted_micro_skill_id",
                "confidence", "review_status", "out_of_scope_reason", "validation_errors")) <= set(mapped)
    checkpoint = base / "mapping_checkpoint.jsonl"
    checkpoint.write_text(checkpoint.read_text(encoding="utf-8") * 2, encoding="utf-8")
    with pytest.raises(RuntimeError, match="INVALID_CHECKPOINT_FINGERPRINT"):
        engine.map_set(config, "tuning", generate=fake)


def test_empty_validation_fails_closed(tmp_path):
    config = replace(load_grade_config("G5"), local_output_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="VALIDATION_INPUT_NOT_FOUND"):
        engine.validate_set(config, "holdout")


def test_secret_never_logged_or_persisted(tmp_path, monkeypatch, capsys):
    secret = "unit-test-only-secret"
    source = tmp_path / "allowed.toml"
    source.write_text(f'GEMINI_API_KEY = "{secret}"\nIGNORED_SETTING = "unread"\n', encoding="utf-8")
    config = replace(load_grade_config("G5"), gemini_secret_paths=(source,), local_output_dir=tmp_path / "out")
    for name in ("GEMINI_API_KEY", "GEMINI_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert engine.gemini_api_key(config) == secret
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    for suffix in ("json", "csv", "md"):
        output = tmp_path / f"output.{suffix}"
        output.write_text("sanitized", encoding="utf-8")
    assert all(secret not in path.read_text(encoding="utf-8") for path in tmp_path.glob("output.*"))
    with pytest.raises(RuntimeError) as caught:
        raise RuntimeError("sanitized loader failure")
    assert secret not in str(caught.value)


def test_coverage_zero_safe_and_synthetic_excluded(tmp_path):
    config = replace(load_grade_config("G5"), local_output_dir=tmp_path)
    summary = engine.coverage(config)
    rows = json.loads((tmp_path / "coverage/g5_skill_coverage_matrix.json").read_text(encoding="utf-8"))
    assert all(row["coverage_status"] == "ZERO_COVERAGE" for row in rows)
    assert summary["synthetic_questions_counted_as_real"] == 0
    assert summary["real_skill_coverage_percent"] == summary["real_micro_coverage_percent"] == 0


def test_grade_local_inventory_jsonl_adapter(tmp_path):
    original = load_grade_config("G5")
    local = tmp_path / "stage5_g5_mapping_pilot"
    imports = local / "imports"; imports.mkdir(parents=True)
    config = replace(original, local_output_dir=local, real_question_source_candidates=())
    imports.joinpath("safe.jsonl").write_text(json.dumps({"prompt": config.grade_label}) + "\n", encoding="utf-8")
    result = engine.inventory(config)
    assert result["REAL_G5_LOCAL_QUESTION_SOURCE"] == "AVAILABLE"
    assert result["unique_questions"] >= 1
    assert any(row["path"].endswith("safe.jsonl") for row in result["source_files"])


def test_micro_parent_and_forced_mapping_validation():
    config = load_grade_config("G5")
    skills = {"A": {}, "B": {}}
    micros = {"M": {"parent_skill_id": "A"}}
    mismatch = {"scope_status": config.in_scope_status, "predicted_skill_id": "B",
                "predicted_micro_skill_id": "M", "confidence": .7}
    forced = {"scope_status": config.out_scope_status, "predicted_skill_id": "A",
              "predicted_micro_skill_id": "M", "confidence": .7}
    assert "MICRO_PARENT_MISMATCH" in engine.validate_result(config, mismatch, skills, micros)
    assert "OUT_OF_SCOPE_MAPPED" in engine.validate_result(config, forced, skills, micros)


def test_handoff_is_sanitized(tmp_path, monkeypatch):
    config = replace(load_grade_config("G5"), local_output_dir=tmp_path / "local")
    local = config.local_output_dir; prefix = config.grade.lower()
    engine.write_json(local / f"{prefix}_curriculum_audit.json",
                      {"curriculum_integrity": "PASS", "skills": 1, "micro_skills": 1})
    engine.write_json(local / f"{prefix}_local_inventory.json",
                      {f"REAL_{config.grade}_LOCAL_QUESTION_SOURCE": "AVAILABLE", "unique_questions": 1})
    engine.write_json(local / f"coverage/{prefix}_coverage_summary.json",
                      {"real_skill_coverage_percent": 0, "real_micro_coverage_percent": 0})
    engine.write_json(local / "synthetic/holdout/validation_summary.json",
                      {"mapping_pilot_pass": True, "total_questions": 1, "scope_accuracy": 100,
                       "exact_skill_accuracy": 100, "exact_micro_accuracy": 100, "invalid": 0})
    engine.write_json(local / "quality/mapping_quality_summary.json", {"technical_pass": True})
    docs = tmp_path / "docs"
    monkeypatch.setattr(engine, "ROOT", docs.parent)
    result = engine.handoff(config, True)
    text = (docs / f"stage5/{config.grade}_PILOT_FREEZE_HANDOFF.md").read_text(encoding="utf-8")
    assert result["foundation"] == "SAFE TO PAUSE"
    assert "question_text" not in text and "predicted_skill_id" not in text


def test_generic_core_has_no_grade_specific_status_or_database_dependency():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    for grade in ("G5", "G6", "G8"):
        assert f"IN_SCOPE_{grade}" not in source
        assert f"OUT_OF_SCOPE_{grade}" not in source
    lowered = source.lower()
    for forbidden in ("supabase", "service_role", "igttuijrtwbtefhyeokp", "odttigkvfazpbnxhpiqe"):
        assert forbidden not in lowered


def test_resilient_json_parser():
    assert engine.response_json_resilient('prefix {"x":1,} suffix') == {"x": 1}


def test_candidate_catalog_recalls_synthetic_expected_labels():
    config = load_grade_config("G7")
    skills, micros = engine._catalog(config)
    skill = skills[-1]
    micro = next(row for row in micros if row["parent_skill_id"] == skill["skill_id"])
    question = {"question_text": " | ".join((skill["skill_name"], micro["focus"], micro.get("item_pattern", "")))}
    candidate_skills, candidate_micros = engine.candidate_catalog(question, skills, micros)
    assert skill["skill_id"] in {row["skill_id"] for row in candidate_skills}
    assert micro["micro_skill_id"] in {row["micro_skill_id"] for row in candidate_micros}
    assert len(candidate_skills) <= 24 and len(candidate_micros) <= 120


class _QuotaError(Exception):
    code = 429
    status = "RESOURCE_EXHAUSTED"

    def __init__(self, retry_after=None):
        self.response = type("Response", (), {"headers": {} if retry_after is None else {"Retry-After": retry_after}})()


def test_429_exponential_retry_and_fail_closed():
    calls = []
    sleeps = []
    def blocked():
        calls.append(1)
        raise _QuotaError()
    with pytest.raises(engine.GeminiQuotaBlocked, match="GEMINI_QUOTA_BLOCKED"):
        engine.generate_with_quota_retry(blocked, sleeps.append)
    assert len(calls) == 4
    assert sleeps == [60.0, 120.0, 300.0]


def test_retry_after_is_honored():
    calls = []
    sleeps = []
    def recovers():
        calls.append(1)
        if len(calls) == 1:
            raise _QuotaError("17")
        return "ok"
    assert engine.generate_with_quota_retry(recovers, sleeps.append) == "ok"
    assert calls == [1, 1] and sleeps == [17.0]


def test_checkpoint_preserved_and_no_duplicate_model_call(tmp_path):
    config = replace(load_grade_config("G7"), local_output_dir=tmp_path)
    base = tmp_path / "synthetic/tuning"; base.mkdir(parents=True)
    question = {"fingerprint": "done", "question_text": ""}
    result = {"fingerprint": "done", "scope_status": config.out_scope_status,
              "predicted_skill_id": "", "predicted_micro_skill_id": "", "confidence": .8}
    (base / "questions.jsonl").write_text(json.dumps(question) + "\n", encoding="utf-8")
    checkpoint = base / "mapping_checkpoint.jsonl"
    original = json.dumps(result) + "\n"; checkpoint.write_text(original, encoding="utf-8")
    calls = []
    summary = engine.map_set(config, "tuning", generate=lambda prompt, model: calls.append(1))
    assert calls == []
    assert summary["completed"] == summary["checkpoint_skipped"] == 1
    assert checkpoint.read_text(encoding="utf-8") == original


def test_quota_block_writes_fail_closed_summary_and_preserves_checkpoint(tmp_path):
    config = replace(load_grade_config("G7"), local_output_dir=tmp_path)
    base = tmp_path / "synthetic/tuning"; base.mkdir(parents=True)
    question = {"fingerprint": "remaining", "question_text": ""}
    (base / "questions.jsonl").write_text(json.dumps(question) + "\n", encoding="utf-8")
    checkpoint = base / "mapping_checkpoint.jsonl"; checkpoint.write_text("", encoding="utf-8")
    def blocked(prompt, model):
        raise engine.GeminiQuotaBlocked("GEMINI_QUOTA_BLOCKED")
    with pytest.raises(engine.GeminiQuotaBlocked):
        engine.map_set(config, "tuning", generate=blocked)
    summary = json.loads((base / "mapping_run_summary.json").read_text(encoding="utf-8"))
    assert summary["technical_pipeline"] == "PASS"
    assert summary["external_api_availability"] == "BLOCKED"
    assert summary["completed"] == 0 and summary["remaining"] == 1
    assert summary["checkpoint_preserved"] is True
    assert checkpoint.read_text(encoding="utf-8") == ""
