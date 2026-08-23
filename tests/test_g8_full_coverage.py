import unittest

from services.curriculum_catalog import DIFFICULTIES, PUBLISHERS, SEMESTERS, get_curriculum_path
from services.g8_question_service import (
    build_g8_subunit_request_specs,
    build_runtime_coverage_matrix,
    coverage_summary,
    deliver_mixed_questions,
    deliver_questions,
    deliver_g8_ui_selection,
    g8_selectable_ui_cases,
    g8_selectable_paths,
    local_question_bank,
    validate_generated_question,
)


class G8FullCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = local_question_bank()
        cls.paths = g8_selectable_paths()

    def test_every_selectable_exact_path_delivers_five_offline(self):
        self.assertTrue(self.paths)
        for spec in self.paths:
            with self.subTest(
                publisher=spec.publisher,
                semester=spec.semester,
                skill=spec.skill_id,
                micro=spec.micro_skill_id,
                difficulty=spec.difficulty,
            ):
                ai_calls = []
                questions, status = deliver_questions(
                    self.bank, spec, lambda _spec: ai_calls.append(_spec)
                )
                self.assertEqual(len(questions), 5)
                self.assertIn(status, {"local", "local_generator"})
                self.assertFalse(ai_calls)
                self.assertEqual(len({row["question"] for row in questions}), 5)
                self.assertGreaterEqual(len({row["archetype_id"] for row in questions}), 5)
                accepted = []
                for row in questions:
                    ok, reason = validate_generated_question(row, spec, accepted)
                    self.assertTrue(ok, reason)
                    self.assertEqual(row["skill_id"], spec.skill_id)
                    self.assertEqual(row["micro_skill_id"], spec.micro_skill_id)
                    self.assertEqual(row["question_type"], spec.question_type)
                    self.assertEqual(row["difficulty"], spec.difficulty)
                    self.assertTrue(row["answer"])
                    self.assertIn(row["answer"], row["solution"])
                    accepted.append(row)

    def test_every_subunit_delivers_mixed_five_offline(self):
        for publisher in PUBLISHERS:
            for semester in SEMESTERS:
                path = get_curriculum_path(8, publisher, semester)
                for unit in path.units:
                    for subunit in unit.subunits:
                        for difficulty in DIFFICULTIES:
                            with self.subTest(
                                publisher=publisher,
                                semester=semester,
                                subunit=subunit.name,
                                difficulty=difficulty,
                            ):
                                specs = build_g8_subunit_request_specs(
                                    path,
                                    main_unit=unit.name,
                                    subunit=subunit.name,
                                    difficulty=difficulty,
                                    question_count=5,
                                )
                                questions, status = deliver_mixed_questions(self.bank, specs)
                                self.assertEqual(len(questions), 5)
                                self.assertIn(status, {"local", "local_generator"})
                                self.assertTrue(all(row["official_subunit"] == subunit.name for row in questions))
                                self.assertTrue(all(row["difficulty"] == difficulty for row in questions))

    def test_runtime_matrix_has_no_blocked_or_dead_end_path(self):
        matrix = build_runtime_coverage_matrix(self.bank)
        summary = coverage_summary(matrix)
        self.assertEqual(len(matrix), len(g8_selectable_ui_cases()))
        self.assertEqual(summary["blocked_paths"], 0)
        self.assertEqual(summary["dead_end_paths"], 0)
        self.assertTrue(all(row["deliverable_5"] for row in matrix))
        self.assertTrue(all(route["blocked_paths"] == 0 for route in summary["routes"].values()))

    def test_every_ui_case_uses_production_delivery_offline(self):
        for case in g8_selectable_ui_cases():
            with self.subTest(mode=case["mode"], subunit=case["subunit"], difficulty=case["difficulties"]):
                ai_calls = []
                rows, status, specs = deliver_g8_ui_selection(
                    case["path"], main_unit=case["main_unit"], subunit=case["subunit"],
                    knowledge_points=case["knowledge_points"], question_types=case["question_types"],
                    difficulties=case["difficulties"], question_count=5,
                    records=self.bank, ai_generator=lambda spec: ai_calls.append(spec),
                )
                self.assertTrue(specs)
                self.assertEqual(len(rows), 5)
                self.assertIn(status, {"local", "local_generator"})
                self.assertFalse(ai_calls)


if __name__ == "__main__":
    unittest.main()
