"""G8 / G9 fine-grained publisher catalog — acceptance tests.

These tests pin the L1-L4 contract for the self-built exam curriculum:
  L1 official main unit -> L2 official subunit -> L3 knowledge point -> L4 type/difficulty/variation.
"""

import re
import unittest

from services.publisher_catalog_g8_g9 import (
    JUNIOR_TYPES,
    all_catalogs,
    get_catalog,
)
from services.curriculum_catalog import (
    BANK_SEARCH_TIERS,
    PUBLISHERS,
    SEMESTERS,
    SelectedExamSpec,
    get_curriculum_path,
    knowledge_point_ids,
    knowledge_point_labels,
    main_unit_names,
    question_bank_search_plan,
    question_type_labels,
    standard_knowledge_ids,
    subunit_labels,
)

KP_ID_RE = re.compile(r"^G[89]-(KX|HL|NY)-(A|B)-U\d+-S\d+-KP\d+$")
STANDARD_ID_RE = re.compile(r"^[NSADGF]-\d+-\d+")

G8_G9 = (8, 9)
G1_G7 = (1, 2, 3, 4, 5, 6, 7)

GENERIC_UNITS = ("數與計算", "圖形與空間", "數與量", "幾何", "測量", "統計", "代數", "方程與關係")


class CatalogCompletenessTests(unittest.TestCase):
    def test_12_catalogs_with_complete_metadata(self):
        catalogs = all_catalogs()
        self.assertEqual(len(catalogs), 12)
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

    def test_each_catalog_has_units_subunits_and_knowledge_points(self):
        for cat in all_catalogs():
            key = (cat["grade"], cat["publisher"], cat["semester"])
            self.assertTrue(cat["units"], key)  # main_unit > 0
            for unit in cat["units"]:
                self.assertTrue(unit["official_main_unit"], key)
                self.assertGreaterEqual(unit["unit_order"], 1)
                self.assertTrue(unit["subunits"], key)  # subunit > 0
                for subunit in unit["subunits"]:
                    self.assertTrue(subunit["official_subunit"], key)
                    self.assertTrue(subunit["knowledge_points"], key)  # knowledge_point > 0

    def test_each_knowledge_point_has_all_required_fields(self):
        required = (
            "knowledge_point_id", "official_main_unit", "official_subunit",
            "knowledge_point", "standard_knowledge_id", "question_types",
            "difficulty", "variation_levels",
        )
        for cat in all_catalogs():
            for unit in cat["units"]:
                for subunit in unit["subunits"]:
                    for kp in subunit["knowledge_points"]:
                        for field in required:
                            self.assertIn(field, kp, kp.get("knowledge_point_id"))
                        self.assertTrue(kp["question_types"], kp["knowledge_point_id"])
                        self.assertTrue(kp["difficulty"], kp["knowledge_point_id"])
                        self.assertTrue(kp["variation_levels"], kp["knowledge_point_id"])
                        self.assertTrue(kp["standard_knowledge_id"], kp["knowledge_point_id"])
                        self.assertEqual(kp["official_main_unit"], unit["official_main_unit"])
                        self.assertEqual(kp["official_subunit"], subunit["official_subunit"])


class CatalogQualityTests(unittest.TestCase):
    def test_knowledge_point_ids_are_stable_and_unique(self):
        ids = []
        for cat in all_catalogs():
            for unit in cat["units"]:
                for subunit in unit["subunits"]:
                    for kp in subunit["knowledge_points"]:
                        self.assertRegex(kp["knowledge_point_id"], KP_ID_RE)
                        ids.append(kp["knowledge_point_id"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_standard_knowledge_ids_follow_curriculum_code_format(self):
        for cat in all_catalogs():
            for unit in cat["units"]:
                for subunit in unit["subunits"]:
                    for kp in subunit["knowledge_points"]:
                        self.assertRegex(kp["standard_knowledge_id"], STANDARD_ID_RE)

    def test_three_publishers_have_distinct_unit_lists(self):
        for grade in G8_G9:
            for semester in SEMESTERS:
                unit_lists = {}
                for cat in all_catalogs():
                    if cat["grade"] == grade and cat["semester"] == semester:
                        unit_lists[cat["publisher"]] = tuple(
                            unit["official_main_unit"] for unit in cat["units"]
                        )
                self.assertEqual(set(unit_lists), set(PUBLISHERS), (grade, semester))
                self.assertEqual(len(set(unit_lists.values())), 3, (grade, semester))

    def test_no_generic_neutral_unit_names(self):
        for cat in all_catalogs():
            for unit in cat["units"]:
                self.assertNotIn(unit["official_main_unit"], GENERIC_UNITS, cat["publisher"])

    def test_question_types_within_junior_high_vocabulary(self):
        for cat in all_catalogs():
            for unit in cat["units"]:
                for subunit in unit["subunits"]:
                    for kp in subunit["knowledge_points"]:
                        for qt in kp["question_types"]:
                            self.assertIn(qt, JUNIOR_TYPES, kp["knowledge_point_id"])

    def test_question_types_vary_across_knowledge_points(self):
        for cat in all_catalogs():
            types = {
                qt
                for unit in cat["units"]
                for subunit in unit["subunits"]
                for kp in subunit["knowledge_points"]
                for qt in kp["question_types"]
            }
            self.assertGreater(len(types), 1, (cat["grade"], cat["publisher"], cat["semester"]))


class CurriculumPathIntegrationTests(unittest.TestCase):
    def test_g8_g9_paths_use_publisher_catalog(self):
        for grade in G8_G9:
            for publisher in PUBLISHERS:
                for semester in SEMESTERS:
                    path = get_curriculum_path(grade, publisher, semester)
                    self.assertIn("master_curriculum_v2_7", path.source)
                    self.assertTrue(main_unit_names(path))
                    self.assertTrue(any(subunit.knowledge_points for unit in path.units for subunit in unit.subunits))

    def test_knowledge_point_labels_and_ids_round_trip(self):
        path = get_curriculum_path(8, "康軒", "上學期")
        units = main_unit_names(path)
        subunits = subunit_labels(path, [units[0]])
        kp_labels = knowledge_point_labels(path, subunits)
        self.assertTrue(kp_labels)
        ids = knowledge_point_ids(path, kp_labels)
        self.assertEqual(len(ids), len(kp_labels))
        std_ids = standard_knowledge_ids(path, kp_labels)
        self.assertTrue(std_ids)

    def test_question_types_derive_from_knowledge_points(self):
        path = get_curriculum_path(9, "南一", "下學期")
        units = main_unit_names(path)
        subunits = subunit_labels(path, [units[0]])
        kp_labels = knowledge_point_labels(path, subunits)
        # Selecting knowledge points narrows the question-type surface.
        self.assertTrue(question_type_labels(path, subunits, kp_labels))

    def test_g1_g7_regression_unaffected(self):
        for grade in G1_G7:
            for publisher in PUBLISHERS:
                for semester in SEMESTERS:
                    path = get_curriculum_path(grade, publisher, semester)
                    self.assertTrue(main_unit_names(path))
                    self.assertNotIn("publisher_catalog_g8_g9", path.source)


class RetrievalOrderTests(unittest.TestCase):
    def _spec(self, grade, publisher, semester):
        path = get_curriculum_path(grade, publisher, semester)
        units = main_unit_names(path)
        subunits = subunit_labels(path, [units[0]])
        kp_labels = knowledge_point_labels(path, subunits)
        spec = SelectedExamSpec(
            grade=grade,
            publisher=publisher,
            semester=semester,
            main_units=(units[0],),
            subunits=tuple(subunits),
            question_types=tuple(question_type_labels(path, subunits, kp_labels)),
            difficulty=("標準",),
            question_count=5,
            knowledge_points=tuple(kp_labels),
            standard_knowledge_ids=standard_knowledge_ids(path, kp_labels),
        )
        return path, spec

    def test_plan_follows_ordered_tiers(self):
        path, spec = self._spec(8, "康軒", "上學期")
        plan = question_bank_search_plan(path, spec)
        self.assertEqual(
            tuple(tier for tier, _ in plan), BANK_SEARCH_TIERS
        )
        names = {tier: terms for tier, terms in plan}
        self.assertTrue(names["knowledge_point_id"])
        self.assertTrue(names["standard_knowledge_id"])
        self.assertTrue(names["subunit"])
        self.assertTrue(names["main_unit"])
        self.assertEqual(names["ai_fallback"], ())

    def test_every_g8_g9_plan_is_complete(self):
        for grade in G8_G9:
            for publisher in PUBLISHERS:
                for semester in SEMESTERS:
                    path, spec = self._spec(grade, publisher, semester)
                    plan = question_bank_search_plan(path, spec)
                    self.assertTrue(plan[0][1])  # knowledge_point_id tier non-empty


if __name__ == "__main__":
    unittest.main()
