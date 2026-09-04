from scripts.stage5_g8_coverage import pilot_status
from scripts.stage5_g8_cross_unit_validation import choose_skills


def test_coverage_status_thresholds():
    assert pilot_status(0, 0, 5) == "ZERO_COVERAGE"
    assert pilot_status(1, 1, 5) == "LIMITED_COVERAGE"
    assert pilot_status(3, 2, 5) == "PILOT_COVERED"


def test_cross_unit_selection_is_distinct_and_avoids_covered_when_possible():
    skills = []
    for index in range(8):
        skills.extend([
            {"skill_id": f"S{index}A", "main_unit": f"U{index}", "source_order": index * 2 + 1},
            {"skill_id": f"S{index}B", "main_unit": f"U{index}", "source_order": index * 2 + 2},
        ])
    chosen = choose_skills(skills, {f"S{i}A" for i in range(8)})
    assert len(chosen) == 8
    assert len({row["main_unit"] for row in chosen}) == 8
    assert all(row["skill_id"].endswith("B") for row in chosen)
