import json

import pytest

from services.elementary_competition import (COMPETITION_THINKING_SKILLS, COMPETITION_TOPICS,
    classify_source, normalized_fingerprint, pilot_eligible, select_pilot, source_quality_risks)
from services.stage7_profiles import build_profile
from scripts import stage7_elementary_competition_inventory as inventory
from scripts.stage7_git_guard import validate_staged


def test_elementary_competition_profile_isolated_and_curriculum_reused():
    profile = build_profile("ELEMENTARY_COMPETITION")
    assert profile.profile_type.value == "ELEMENTARY_COMPETITION"
    assert profile.curriculum_target_grade == ("G3", "G4", "G5", "G6")
    assert profile.thinking_skill_enabled and "G05-N-MULTIPLE-01" in profile.allowed_skill_ids
    assert build_profile("PRIVATE_JH").profile_type.value == "PRIVATE_JH"


def test_source_classification_excludes_private_and_general_curriculum():
    assert classify_source({"target_profile": "PRIVATE_JH"}) == "PRIVATE_JH"
    assert classify_source({"general_curriculum": True}) == "GENERAL_CURRICULUM"
    assert not pilot_eligible("PRIVATE_JH", "G6", [], {"source_complete": True, "source_url": "official"})
    assert not pilot_eligible("GENERAL_CURRICULUM", "G5", [], {"source_complete": True, "source_url": "official"})


def test_no_fake_competition_source_or_difficulty_upgrade():
    assert classify_source({"target_profile": "G5_COMPETITION_CORE"}) == "COMPETITION_CANDIDATE"
    assert classify_source({"advanced": True}) == "GENERAL_ADVANCED"
    assert classify_source({"difficulty": "EXTREME"}) == "UNKNOWN"
    assert not pilot_eligible("COMPETITION_CANDIDATE", "G5", [], {"source_complete": True, "source_url": "x"})
    assert classify_source({"official_competition_source": True, "source_url": "official",
        "competition_name": "Verified Contest"}) == "EXPLICIT_COMPETITION"


def test_grade_scope_and_out_of_scope_fail_closed():
    meta = {"source_complete": True, "source_url": "official"}
    assert pilot_eligible("EXPLICIT_COMPETITION", "G4", [], meta)
    assert not pilot_eligible("EXPLICIT_COMPETITION", "G7", [], meta)
    assert source_quality_risks({"scope_status": "OUT_OF_SCOPE_ELEMENTARY"}) == ["OUT_OF_SCOPE_ELEMENTARY"]


def test_fingerprint_normalizes_layout_but_preserves_numbers():
    assert normalized_fingerprint("Ａ：12， B：3") == normalized_fingerprint("A 12 B 3")
    assert normalized_fingerprint("A 12 B 3") != normalized_fingerprint("A 13 B 3")


def test_source_quality_inherited_and_competition_layout_gates():
    risks = source_quality_risks({"prompt": "數陣中的特殊符號排列", "fraction_notation_lost": True})
    assert {"TABLE_LAYOUT_LOST", "SEQUENCE_LAYOUT_LOST", "MATH_FRACTION_NOTATION_LOST"} <= set(risks)
    assert source_quality_risks({"prompt": "方格圖", "visualization": "usable grid"}) == []


def test_competition_topic_and_thinking_taxonomies_are_exact_and_separate():
    assert len(COMPETITION_TOPICS) == 20 and len(COMPETITION_THINKING_SKILLS) == 13
    assert {"NUMBER_PATTERN", "COUNTING", "GRAPH_PATH", "COMBINED"} <= set(COMPETITION_TOPICS)
    assert {"SYSTEMATIC_ENUMERATION", "INVARIANT_REASONING", "MULTI_STEP_INFERENCE"} <= COMPETITION_THINKING_SKILLS
    assert all(not item.startswith("G0") for item in set(COMPETITION_TOPICS) | set(COMPETITION_THINKING_SKILLS))


def test_inventory_is_local_private_deduplicated_and_fail_closed():
    audit = inventory.build()
    assert audit["raw_questions"] == 36 and audit["unique_questions"] == 35
    assert audit["duplicates_removed"] == 1 and audit["usable_competition_questions"] == 0
    assert audit["status"] == "CORPUS_INSUFFICIENT" and audit["additional_questions_needed"] == 100
    assert not inventory.PILOT_JSONL.exists() and not inventory.PILOT_MANIFEST.exists()
    assert inventory.LOCAL in inventory.UNIQUE_JSONL.parents


def test_pilot100_requires_100_and_enforces_topic_diversity():
    with pytest.raises(RuntimeError, match="CORPUS_INSUFFICIENT"):
        select_pilot([], 100)
    rows = []
    for index in range(100):
        rows.append({"fingerprint": f"fp-{index}", "source_class": "EXPLICIT_COMPETITION",
            "grade": "G4" if index % 2 else "G5", "risks": [], "source_complete": True,
            "source_url": "official", "source": f"source-{index % 5}", "year": str(2020 + index % 4),
            "competition_topic": f"TOPIC-{index % 4}"})
    selected = select_pilot(rows, 100)
    counts = {topic: sum(row["competition_topic"] == topic for row in selected)
              for topic in {row["competition_topic"] for row in selected}}
    assert len(selected) == 100 and max(counts.values()) <= 25


def test_inventory_has_zero_external_calls_and_sanitized_source_counts():
    audit = json.loads(inventory.INVENTORY_JSON.read_text(encoding="utf-8-sig"))
    assert audit["api_calls"] == audit["gemini_calls"] == audit["deepseek_calls"] == 0
    assert audit["production_reads"] == audit["production_writes"] == 0
    assert audit["source_counts"] == {"COMPETITION_CANDIDATE": 2, "PRIVATE_JH": 8,
        "GENERAL_CURRICULUM": 2}


def test_competition_private_artifacts_are_blocked_from_git():
    violations = validate_staged([".local/stage7_elementary_competition/competition_unique_questions.jsonl"])
    assert violations
