import csv
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from scripts.stage7_git_guard import validate_staged
from services.stage7_profiles import (
    ProfileType, build_profile, checkpoint_key, load_curriculum_catalog,
    load_thinking_taxonomy, mapping_output_schema, normalize_profile_type,
    profile_scope_status, validate_mapping_result,
)


def valid_mapping(profile="COMPETITION"):
    grades = ("G4", "G5", "G6") if profile == "COMPETITION" else ("G5", "G6")
    skills, micros = load_curriculum_catalog(grades)
    micro_id, micro = next(iter(micros.items()))
    return {"profile_type": profile, "scope_status": profile, "primary_skill_id": micro["parent_skill_id"],
            "primary_micro_skill_id": micro_id, "secondary_skill_ids": [],
            "thinking_skill_ids": ["TS-ENUM"] if profile == "COMPETITION" else [],
            "primary_thinking_skill_id": "TS-ENUM" if profile == "COMPETITION" else "",
            "competition_level": "FOUNDATION" if profile == "COMPETITION" else None,
            "strategy_depth": 1 if profile == "COMPETITION" else None,
            "assessment_style": "COMPETITION_STRATEGY" if profile == "COMPETITION" else "MULTI_STEP"}


def test_standard_backward_compatibility():
    assert normalize_profile_type() is ProfileType.STANDARD
    assert normalize_profile_type("") is ProfileType.STANDARD
    assert profile_scope_status(True) == "STANDARD"


def test_profiles_reuse_curriculum_without_duplicate_tree():
    private = build_profile("PRIVATE_JH")
    competition = build_profile("COMPETITION")
    assert private.curriculum_grade == private.curriculum_target_grade == ("G5", "G6")
    assert private.curriculum_foundation_grade == ("G1", "G2", "G3", "G4") and private.allowed_skill_ids
    assert competition.curriculum_grade == ("G4", "G5", "G6") and competition.thinking_skill_enabled
    assert all(not item.startswith("TS-") for item in competition.allowed_skill_ids + competition.allowed_micro_ids)


def test_invalid_profile_fails_closed():
    with pytest.raises(ValueError, match="UNKNOWN_PROFILE"):
        normalize_profile_type("OLYMPIAD")


def test_valid_private_jh_and_competition():
    private = valid_mapping("PRIVATE_JH")
    assert validate_mapping_result(private, grades=("G5", "G6")) == []
    competition = valid_mapping()
    assert validate_mapping_result(competition, grades=("G4", "G5", "G6")) == []


def test_private_jh_allows_real_g4_prerequisite_catalog_ids():
    row = valid_mapping("COMPETITION")
    skills_g4, micros_g4 = load_curriculum_catalog(("G4",))
    micro_id, micro = next(iter(micros_g4.items()))
    row.update({"profile_type": "PRIVATE_JH", "scope_status": "PRIVATE_JH", "primary_skill_id": micro["parent_skill_id"],
                "primary_micro_skill_id": micro_id, "thinking_skill_ids": [],
                "primary_thinking_skill_id": "", "competition_level": None,
                "strategy_depth": None, "assessment_style": "HIGH_DIFFICULTY"})
    assert validate_mapping_result(row, grades=("G5", "G6")) == []


def test_private_jh_out_of_scope_must_be_unmapped():
    row = valid_mapping("PRIVATE_JH")
    row.update(scope_status="OUT_OF_SCOPE_PROFILE", primary_skill_id="", primary_micro_skill_id="")
    assert validate_mapping_result(row, grades=("G5", "G6")) == []
    row["primary_skill_id"] = next(iter(load_curriculum_catalog(("G5", "G6"))[0]))
    assert "OUT_OF_SCOPE_MAPPED" in validate_mapping_result(row, grades=("G5", "G6"))


def test_parent_constraint_and_invalid_ids():
    row = valid_mapping()
    skills, micros = load_curriculum_catalog(("G4", "G5", "G6"))
    row["primary_skill_id"] = next(key for key in skills if key != micros[row["primary_micro_skill_id"]]["parent_skill_id"])
    assert "MICRO_PARENT_MISMATCH" in validate_mapping_result(row, grades=("G4", "G5", "G6"))
    row["primary_skill_id"] = "NO-SKILL"
    row["primary_micro_skill_id"] = "NO-MICRO"
    row["secondary_skill_ids"] = ["NO-SECONDARY"]
    errors = validate_mapping_result(row, grades=("G4", "G5", "G6"))
    assert {"UNKNOWN_SKILL_ID", "UNKNOWN_MICRO_SKILL_ID", "UNKNOWN_SECONDARY_SKILL_ID"} <= set(errors)


def test_thinking_taxonomy_and_invalid_thinking_rejected():
    taxonomy = load_thinking_taxonomy()
    assert len(taxonomy) == 24 and len({row["category"] for row in taxonomy.values()}) == 4
    row = valid_mapping(); row["thinking_skill_ids"] = ["TS-NOT-REAL"]
    assert "UNKNOWN_THINKING_SKILL_ID" in validate_mapping_result(row, grades=("G4", "G5", "G6"))


def test_competition_metadata_cannot_pollute_private_jh():
    row = valid_mapping("PRIVATE_JH"); row["thinking_skill_ids"] = ["TS-ENUM"]
    assert "COMPETITION_METADATA_NOT_ALLOWED" in validate_mapping_result(row, grades=("G5", "G6"))


def test_secondary_skills_are_validated():
    row = valid_mapping(); row["secondary_skill_ids"] = [row["primary_skill_id"]]
    assert validate_mapping_result(row, grades=("G4", "G5", "G6")) == []


def test_checkpoint_key_includes_profile_and_fingerprint():
    assert checkpoint_key("abc") == "STANDARD:abc"
    assert checkpoint_key("abc", "PRIVATE_JH") == "PRIVATE_JH:abc"


def test_mapping_schema_has_provider_observability_fields():
    required = set(mapping_output_schema()["required"])
    assert {"provider", "model", "status", "latency", "token_usage", "profile_type"} <= required


def test_legacy_template_cannot_claim_human_validation():
    path = Path("data/stage7/legacy_profile_mapping_template.csv")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows and all(row["mapping_status"] != "HUMAN_VALIDATED" for row in rows)


def test_private_data_git_guard():
    assert validate_staged([".local/stage7_private_jh/questions.jsonl"])
    assert validate_staged(["review/human_review.csv"])
    assert validate_staged(["services/stage7_profiles.py"]) == []


def test_pilot_configs_are_disabled_and_local():
    for name in ("private_jh", "competition"):
        data = json.loads(Path(f"data/stage7/{name}_pilot_config.json").read_text(encoding="utf-8"))
        assert data["run_enabled"] is False and data["input_root"].startswith(".local/")
        assert data["automatic_fallback"] is False and data["target_count"] == 100


def test_private_jh_pattern_reasoning_style_is_formal_enum():
    assert "PATTERN_REASONING" in build_profile("PRIVATE_JH").assessment_style
