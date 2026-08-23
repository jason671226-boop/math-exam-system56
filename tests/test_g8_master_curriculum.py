import unittest

from services.curriculum_catalog import (
    PUBLISHERS, SEMESTERS, get_curriculum_path, knowledge_point_labels, micro_skill_ids,
    subunit_labels,
)
from services.g8_question_service import build_g8_request_spec
from services.master_curriculum_loader import load_g8_master_catalog


class G8MasterCurriculumTests(unittest.TestCase):
    def test_master_pack_has_canonical_pool_and_bounded_mapping(self):
        catalog = load_g8_master_catalog()
        self.assertEqual(len(catalog.skills), 102)
        self.assertGreater(len(catalog.mappings), 0)
        self.assertLess(len(set(item.skill_id for item in catalog.mappings)), 102)
        self.assertFalse(any(item.mapping_status == "NEEDS_REVIEW" for item in catalog.mappings))
        self.assertTrue(all(item.mapping_status in {"VERIFIED", "HIGH_CONFIDENCE", "CROSS_SHARED", "NEEDS_REVIEW"}
                            for item in catalog.mappings))

    def test_all_six_publisher_routes_are_complete(self):
        for publisher in PUBLISHERS:
            for semester in SEMESTERS:
                path = get_curriculum_path(8, publisher, semester)
                self.assertEqual(path.source.startswith("master_curriculum_v2_7"), True)
                self.assertGreater(len(path.units), 0)
                self.assertGreater(sum(len(unit.subunits) for unit in path.units), 0)
                points = [kp for unit in path.units for sub in unit.subunits for kp in sub.knowledge_points]
                self.assertGreater(len(points), 0)
                self.assertTrue(all(kp.skill_id and kp.micro_skill_ids for kp in points))

    def test_request_spec_uses_selected_skill_and_micro(self):
        path = get_curriculum_path(8, PUBLISHERS[0], SEMESTERS[0])
        unit = path.units[0]
        sub = unit.subunits[0]
        kp = sub.knowledge_points[0]
        qtype = kp.question_types[0]
        spec = build_g8_request_spec(
            path, main_unit=unit.name, subunit=sub.name,
            knowledge_point=kp.name, question_type=qtype,
            difficulty=kp.difficulty[0], question_count=5,
        )
        self.assertEqual(spec.skill_id, kp.skill_id)
        self.assertIn(spec.micro_skill_id, kp.micro_skill_ids)
        self.assertTrue(spec.official_main_unit_id and spec.official_subunit_id)
        self.assertEqual(spec.question_count, 5)
        label = knowledge_point_labels(path, subunit_labels(path, [unit.name]))[0]
        self.assertEqual(micro_skill_ids(path, [label]), kp.micro_skill_ids)


if __name__ == "__main__":
    unittest.main()
