from services.stage7_private_jh_guidance import core_structure_guidance


def _guide(**evidence):
    return core_structure_guidance({"profile_type": "PRIVATE_JH", **evidence})


def test_common_factor_beats_decimal_surface_feature():
    result = _guide(common_factor_structure=True, decimal_surface=True)
    assert result["foundation_skill_id"] == "G05-R-LAW-01"


def test_segmented_total_without_distance_time_beats_speed_word():
    result = _guide(segmented_quantities=True, asks_total=True, daily_word=True,
                    distance_time_relation=False)
    assert result["foundation_skill_id"] == "G05-R-MULTISTEP-01"


def test_distinct_combination_results_use_counting_not_addition():
    result = _guide(distinct_combinations=True, deduplicate_results=True, result_operation="SUM")
    assert result["foundation_skill_id"] == "G06-R-COUNT-01"


def test_round_trip_average_speed_uses_total_distance_over_total_time():
    result = _guide(round_trip=True, average_speed=True)
    assert result["foundation_skill_id"] == "G06-N-SPEED-APP-01"
    assert result["formula"] == "TOTAL_DISTANCE/TOTAL_TIME"


def test_guidance_never_claims_human_validation():
    assert _guide(common_factor_structure=True)["human_validated"] is False
    assert core_structure_guidance({"profile_type": "STANDARD", "common_factor_structure": True}) is None
