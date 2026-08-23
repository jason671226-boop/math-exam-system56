from pathlib import Path
import unittest

from services.curriculum_catalog import (
    DIFFICULTIES,
    PUBLISHERS,
    SEMESTERS,
    SUPPORTED_GRADES,
    SelectedExamSpec,
    build_generation_context,
    curriculum_versions,
    exam_output_has_question_count,
    get_curriculum_path,
    knowledge_point_labels,
    micro_skill_ids,
    main_unit_names,
    question_type_labels,
    reset_dependent_selections,
    subunit_labels,
)
from services.publisher_catalog_g1_g4 import (
    LOWER_TYPES,
    MIDDLE_TYPES,
    all_catalogs,
)


ROOT = Path(__file__).resolve().parents[1]


class CurriculumMatrixTests(unittest.TestCase):
    G1_G4 = (1, 2, 3, 4)
    G5_G9 = (5, 6, 7, 8, 9)
    G10_G12 = (10, 11, 12)

    def _assert_paths_complete(self, grades, expected):
        checked = 0
        for grade in grades:
            for publisher in curriculum_versions(grade):
                for semester in SEMESTERS:
                    with self.subTest(grade=grade, publisher=publisher, semester=semester):
                        path = get_curriculum_path(grade, publisher, semester)
                        units = main_unit_names(path)
                        self.assertTrue(units)
                        subunits = subunit_labels(path, units)
                        self.assertTrue(subunits)
                        self.assertTrue(question_type_labels(path, subunits))
                        self.assertEqual(DIFFICULTIES, ("基礎", "標準", "進階", "挑戰"))
                        self.assertTrue(all(unit.subunits for unit in path.units))
                        checked += 1
        self.assertEqual(checked, expected)

    def test_all_g1_g4_paths_have_complete_selection_options(self):
        self._assert_paths_complete(self.G1_G4, 24)

    def test_all_g5_g9_paths_have_complete_selection_options(self):
        self._assert_paths_complete(self.G5_G9, 34)

    def test_all_g1_g12_master_paths_total_74(self):
        self._assert_paths_complete(SUPPORTED_GRADES, 74)

    def test_all_high_school_paths_reach_exam_selection(self):
        self._assert_paths_complete(self.G10_G12, 16)

    def test_every_grade_exposes_master_knowledge_points_and_micro_skills(self):
        for grade in SUPPORTED_GRADES:
            path = get_curriculum_path(grade, curriculum_versions(grade)[0], "上學期")
            unit = main_unit_names(path)[0]
            subunit = subunit_labels(path, [unit])[0]
            points = knowledge_point_labels(path, [subunit])
            self.assertTrue(points, f"G{grade} knowledge points")
            self.assertTrue(micro_skill_ids(path, [points[0]]), f"G{grade} micro skills")

    def test_g7_uses_master_catalog(self):
        for publisher in PUBLISHERS:
            for semester in SEMESTERS:
                path = get_curriculum_path(7, publisher, semester)
                self.assertIn("master_curriculum_v2_7", path.source)

    def test_g6_knsh_regression_has_subunits_types_and_difficulty(self):
        for semester in SEMESTERS:
            path = get_curriculum_path(6, "康軒", semester)
            units = main_unit_names(path)
            subunits = subunit_labels(path, units)
            self.assertTrue(subunits)
            self.assertTrue(question_type_labels(path, subunits))
            self.assertTrue(DIFFICULTIES)

    def test_g6_special_routes_remain_selectable_and_scoped(self):
        self.assertEqual(
            curriculum_versions(6),
            ("康軒", "翰林", "南一", "報考私中", "參加數學競賽"),
        )
        private_path = get_curriculum_path(6, "報考私中", "上學期")
        competition_path = get_curriculum_path(6, "參加數學競賽", "上學期")
        self.assertIn("private-school", private_path.source)
        self.assertIn("COMPETITION", competition_path.source)
        for path in (private_path, competition_path):
            units = main_unit_names(path)
            subunits = subunit_labels(path, units)
            points = knowledge_point_labels(path, subunits)
            self.assertTrue(units)
            self.assertTrue(subunits)
            self.assertTrue(points)
            self.assertTrue(question_type_labels(path, subunits, points))

        regular_names = set(main_unit_names(get_curriculum_path(6, "康軒", "上學期")))
        competition_names = set(main_unit_names(competition_path))
        self.assertNotEqual(regular_names, competition_names)

    def test_app_displays_g6_version_type_labels_without_changing_semesters(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"教材版本／類型"', source)
        self.assertIn('"報考私立國中"', source)
        self.assertIn('if value == "報考私中"', source)
        self.assertIn('"學期",\n                    SELF_BUILT_SEMESTERS,', source)


class PublisherCatalogDataTests(unittest.TestCase):
    """G1-G4 official publisher catalogs must be publisher-specific, not generic."""

    def test_24_catalogs_with_complete_metadata(self):
        catalogs = all_catalogs()
        self.assertEqual(len(catalogs), 24)
        seen = set()
        for cat in catalogs:
            key = (cat["grade"], cat["publisher"], cat["semester"])
            self.assertNotIn(key, seen, key)
            seen.add(key)
            for field in (
                "grade", "publisher", "semester", "volume",
                "verification_status", "source_url", "source_type", "units",
            ):
                self.assertIn(field, cat, key)
            self.assertGreaterEqual(cat["volume"], 1)
            self.assertTrue(cat["source_url"], key)
            self.assertIn(cat["verification_status"], ("verified", "partial"), key)
            for unit in cat["units"]:
                self.assertTrue(unit["official_unit_name"], key)
                self.assertGreaterEqual(unit["unit_order"], 1)
                self.assertTrue(unit["subunits"], key)

    def test_each_subunit_has_full_documented_fields(self):
        required = (
            "subunit_id", "standard_name", "publisher_original_unit",
            "learning_focus", "prerequisite", "common_errors",
            "question_types", "difficulty_range", "variation_levels",
        )
        for cat in all_catalogs():
            for unit in cat["units"]:
                for sub in unit["subunits"]:
                    for field in required:
                        self.assertIn(field, sub, sub.get("subunit_id"))
                    self.assertTrue(sub["question_types"])
                    self.assertTrue(sub["difficulty_range"])
                    self.assertTrue(sub["variation_levels"])
                    self.assertEqual(
                        sub["publisher_original_unit"], unit["official_unit_name"]
                    )

    def test_three_publishers_have_distinct_unit_lists(self):
        for grade in (1, 2, 3, 4):
            for semester in SEMESTERS:
                unit_lists = {}
                for cat in all_catalogs():
                    if cat["grade"] == grade and cat["semester"] == semester:
                        unit_lists[cat["publisher"]] = tuple(
                            unit["official_unit_name"] for unit in cat["units"]
                        )
                self.assertEqual(set(unit_lists), set(PUBLISHERS), (grade, semester))
                # anti-fake-PASS: no two publishers may share an identical ordered list
                self.assertEqual(len(set(unit_lists.values())), 3, (grade, semester))

    def test_no_generic_neutral_unit_names(self):
        # The old neutral baseline surfaced bare domain names as "units".
        # Real publisher units never carry these domain-only titles.
        generic = ("數與計算", "圖形與空間", "數與量", "幾何", "測量", "統計")
        for cat in all_catalogs():
            for unit in cat["units"]:
                self.assertNotIn(
                    unit["official_unit_name"], generic, cat["publisher"]
                )

    def test_g1_g4_paths_use_master_catalog_not_baseline(self):
        for grade in (1, 2, 3, 4):
            for publisher in PUBLISHERS:
                for semester in SEMESTERS:
                    path = get_curriculum_path(grade, publisher, semester)
                    self.assertIn("master_curriculum_v2_7", path.source)

    def test_question_types_within_grade_band_and_no_exam_type(self):
        for cat in all_catalogs():
            allowed = LOWER_TYPES if cat["grade"] <= 2 else MIDDLE_TYPES
            for unit in cat["units"]:
                for sub in unit["subunits"]:
                    for question_type in sub["question_types"]:
                        self.assertIn(question_type, allowed, sub["subunit_id"])
                        self.assertNotIn("會考", question_type)

    def test_question_types_vary_across_subunits(self):
        for cat in all_catalogs():
            types = {
                question_type
                for unit in cat["units"]
                for sub in unit["subunits"]
                for question_type in sub["question_types"]
            }
            self.assertGreater(
                len(types), 1, (cat["grade"], cat["publisher"], cat["semester"])
            )


class GenerationContractTests(unittest.TestCase):
    def test_incomplete_or_placeholder_exam_output_is_rejected(self):
        self.assertFalse(exam_output_has_question_count("", 5))
        self.assertFalse(exam_output_has_question_count("1. 題目\n2. 題目", 5))
        self.assertFalse(exam_output_has_question_count("```python\nprint(1)\n```", 1))
        complete = "\n".join(f"{number}. 正式題目" for number in range(1, 6))
        self.assertTrue(exam_output_has_question_count(complete, 5))

    def test_each_grade_reaches_generation_context_without_field_loss(self):
        for grade in SUPPORTED_GRADES:
            publisher = curriculum_versions(grade)[0]
            semester = SEMESTERS[grade % 2]
            path = get_curriculum_path(grade, publisher, semester)
            unit = main_unit_names(path)[0]
            subunit = subunit_labels(path, [unit])[0]
            question_type = question_type_labels(path, [subunit])[0]
            spec = SelectedExamSpec(
                grade=grade,
                publisher=publisher,
                semester=semester,
                main_units=(unit,),
                subunits=(subunit,),
                question_types=(question_type,),
                difficulty=("進階",),
                question_count=10,
            )
            context = build_generation_context(spec)
            for expected in (
                f"G{grade}", publisher, semester, unit, subunit,
                question_type, "進階", "10",
            ):
                self.assertIn(expected, context)

    def test_high_school_context_uses_high_school_band(self):
        path = get_curriculum_path(12, "數學甲", "下學期")
        unit = main_unit_names(path)[0]
        subunit = subunit_labels(path, [unit])[0]
        spec = SelectedExamSpec(
            grade=12,
            publisher="數學甲",
            semester="下學期",
            main_units=(unit,),
            subunits=(subunit,),
            question_types=(),
            difficulty=("標準",),
            question_count=5,
        )
        self.assertIn("年段：高中", build_generation_context(spec))

    def test_app_passes_spec_to_bank_and_ai_fallback_and_math_renderer(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("exam_spec = SelectedExamSpec(", source)
        self.assertIn("generation_context = build_generation_context(exam_spec)", source)
        self.assertIn("exam_publisher, exam_semester", source)
        self.assertIn("{generation_context}", source)
        self.assertIn("render_math_content(st.session_state[\"custom_exam_content\"])", source)
        self.assertIn("必須生成全新題目", source)
        self.assertIn("題庫正在建置中，請稍等", source)
        self.assertNotIn("APP_VERSION = \"v0.8.7.4\"", source)


class CurriculumStateTransitionTests(unittest.TestCase):
    def test_grade_publisher_and_semester_changes_clear_old_dependents(self):
        state = {
            "custom_exam_catalog_signature": "5|康軒|上學期",
            "custom_exam_main_units": ["old unit"],
            "custom_exam_subunits": ["old subunit"],
            "custom_exam_question_types": ["old type"],
            "unrelated": "preserved",
        }
        for signature in ("6|康軒|上學期", "6|翰林|上學期", "6|翰林|下學期"):
            state.update(
                custom_exam_main_units=["old unit"],
                custom_exam_subunits=["old subunit"],
                custom_exam_question_types=["old type"],
            )
            reset_dependent_selections(state, signature)
            self.assertNotIn("custom_exam_main_units", state)
            self.assertNotIn("custom_exam_subunits", state)
            self.assertNotIn("custom_exam_question_types", state)
            self.assertEqual(state["unrelated"], "preserved")

    def test_unit_change_filters_subunits_and_types(self):
        path = get_curriculum_path(8, "南一", "上學期")
        units = main_unit_names(path)
        first = subunit_labels(path, [units[0]])
        second = subunit_labels(path, [units[-1]])
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertTrue(set(first).isdisjoint(second))
        self.assertTrue(question_type_labels(path, first))
        self.assertTrue(question_type_labels(path, second))


if __name__ == "__main__":
    unittest.main()
