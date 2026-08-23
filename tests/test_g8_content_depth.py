import unittest

from services.g8_question_service import (
    GENERIC_PLACEHOLDER_TERMS,
    build_content_depth_audit,
    content_depth_summary,
    deliver_questions,
    g8_selectable_paths,
    local_question_bank,
    validate_five_pack,
    validate_generic_placeholder,
    validate_math_rendering,
    validate_semantic_match,
)


class G8ContentDepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = build_content_depth_audit()
        cls.summary = content_depth_summary(cls.audit)

    def test_all_micro_difficulty_paths_have_production_depth(self):
        self.assertTrue(self.audit)
        self.assertEqual(self.summary["invalid"], 0)
        self.assertEqual(self.summary["repetitive"], 0)
        self.assertEqual(self.summary["generic_placeholder_count"], 0)
        self.assertEqual(self.summary["semantic_mismatch_count"], 0)
        self.assertEqual(self.summary["near_duplicate_failures"], 0)
        self.assertTrue(all(row["unique_structure_count"] >= 4 for row in self.audit))

    def test_every_unique_exact_path_delivers_a_diverse_renderable_pack(self):
        seen = set()
        bank = local_question_bank()
        for spec in g8_selectable_paths():
            key = (spec.skill_id, spec.micro_skill_id, spec.difficulty)
            if key in seen:
                continue
            seen.add(key)
            rows, status = deliver_questions(bank, spec)
            with self.subTest(key=key):
                self.assertIn(status, {"local", "local_generator"})
                self.assertEqual(validate_five_pack(rows), (True, "ok"))
                for row in rows:
                    self.assertEqual(validate_generic_placeholder(row), (True, "ok"))
                    self.assertEqual(validate_semantic_match(row, spec), (True, "ok"))
                    self.assertEqual(validate_math_rendering(row), (True, "ok"))
                    if row.get("source") == "LOCAL_GENERATOR":
                        self.assertIs(row.get("concrete_data"), True)

    def test_placeholder_and_wrong_function_semantics_are_rejected(self):
        spec = next(item for item in g8_selectable_paths() if item.skill_id.startswith("G08-F-"))
        bad = {
            "grade": 8, "skill_id": spec.skill_id, "micro_skill_id": spec.micro_skill_id,
            "question_type": spec.question_type, "difficulty": spec.difficulty,
            "variation_level": spec.variation_level, "source": "LOCAL_GENERATOR",
            "semantic_anchor": spec.skill_id, "question": f"{GENERIC_PLACEHOLDER_TERMS[0]}：首項與公比",
            "answer": "等比數列", "solution": "最終答案：等比數列",
        }
        self.assertFalse(validate_generic_placeholder(bad)[0])
        self.assertFalse(validate_semantic_match(bad, spec)[0])

    def test_four_difficulties_change_reasoning_contract_not_number_size(self):
        paths = g8_selectable_paths()
        sample_skill = paths[0].skill_id
        sample_micro = paths[0].micro_skill_id
        specs = [item for item in paths if item.skill_id == sample_skill and item.micro_skill_id == sample_micro]
        unique = {}
        for spec in specs:
            unique.setdefault(spec.difficulty, spec)
        self.assertEqual(len(unique), 4)
        packs = {difficulty: deliver_questions((), spec)[0] for difficulty, spec in unique.items()}
        self.assertEqual({rows[0]["reasoning_steps"] for rows in packs.values()}, {1, 2, 3, 4})
        self.assertEqual(len({rows[0]["question"] for rows in packs.values()}), 4)


if __name__ == "__main__":
    unittest.main()
