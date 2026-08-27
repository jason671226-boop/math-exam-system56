from services.stage7_private_jh_guidance import divisibility_extension_guidance


def test_divisibility_by_three_uses_g5_foundation_and_advanced_profile():
    result = divisibility_extension_guidance({"profile_type": "PRIVATE_JH",
        "divisibility_condition": True, "divisor": 3, "systematic_enumeration": True,
        "difficulty": "HIGH"})
    assert result["foundation_skill_id"] == "G05-N-MULTIPLE-01"
    assert result["assessment_style"] == "PRIVATE_JH_ADVANCED"
    assert result["secondary_skill_ids"] == ["G06-R-COUNT-01"]
    assert result["guidance_status"] == "CANDIDATE_ONLY" and result["human_validated"] is False


def test_difficulty_without_profile_and_divisibility_evidence_does_not_route():
    assert divisibility_extension_guidance({"profile_type": "PRIVATE_JH", "difficulty": "HIGH"}) is None
    assert divisibility_extension_guidance({"profile_type": "STANDARD", "divisibility_condition": True}) is None
