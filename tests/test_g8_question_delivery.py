import json
import unittest

from services.curriculum_catalog import PUBLISHERS, SEMESTERS, get_curriculum_path
from services.g8_question_service import (
    build_g8_request_spec, build_g8_subunit_request_specs,
    deliver_mixed_questions, deliver_questions, local_question_bank,
)


def _spec():
    path = get_curriculum_path(8, PUBLISHERS[0], SEMESTERS[0])
    unit = next(item for item in path.units if "乘法公式" in item.name)
    sub = next(item for item in unit.subunits if item.name == "乘法公式")
    kp = next(item for item in sub.knowledge_points if item.name == "平方差公式")
    return build_g8_request_spec(path, main_unit=unit.name, subunit=sub.name,
                                 knowledge_point=kp.name, question_type=kp.question_types[1],
                                 difficulty="標準", question_count=5)


class G8QuestionDeliveryTests(unittest.TestCase):
    def test_local_bank_is_used_without_ai(self):
        spec = _spec()
        called = []
        rows, status = deliver_questions(local_question_bank(), spec,
                                          lambda _: called.append(True))
        self.assertEqual(len(rows), 5)
        self.assertEqual(status, "local_generator")
        self.assertFalse(called)
        self.assertTrue(all(row["skill_id"] == spec.skill_id for row in rows))

    def test_partial_local_plus_ai(self):
        spec = _spec()
        local = [row for row in local_question_bank()
                 if row["micro_skill_id"] == spec.micro_skill_id and row["difficulty"] == spec.difficulty][:3]
        def generator(ai_spec):
            rows = [dict(row, id=f"AI-{i}") for i, row in enumerate(local_question_bank()[:2])]
            for row in rows:
                row.update(skill_id=ai_spec.skill_id, micro_skill_id=ai_spec.micro_skill_id,
                           question_type=ai_spec.question_type, difficulty=ai_spec.difficulty)
            return json.dumps(rows, ensure_ascii=False)
        rows, status = deliver_questions(local, spec, generator)
        self.assertEqual(len(rows), 5)
        self.assertEqual(status, "local_generator")

    def test_ai_failure_keeps_safe_local_questions(self):
        spec = _spec()
        local = [row for row in local_question_bank()
                 if row["micro_skill_id"] == spec.micro_skill_id and row["difficulty"] == spec.difficulty][:3]
        rows, status = deliver_questions(local, spec, lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
        self.assertEqual(len(rows), 5)
        self.assertEqual(status, "local_generator")

    def test_zero_local_and_ai_failure_is_explicit(self):
        spec = _spec()
        rows, status = deliver_questions([], spec, lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
        self.assertEqual(len(rows), 5)
        self.assertEqual(status, "local_generator")

    def test_subunit_mixed_mode_uses_mapped_skills_without_ai(self):
        path = get_curriculum_path(8, "\u5eb7\u8ed2", "\u4e0a\u5b78\u671f")
        unit = next(item for item in path.units if item.name == "\u5e73\u65b9\u6839\u8207\u7562\u6c0f\u5b9a\u7406")
        sub = next(item for item in unit.subunits if item.name == "\u6839\u5f0f\u7684\u904b\u7b97")
        specs = build_g8_subunit_request_specs(
            path, main_unit=unit.name, subunit=sub.name,
            difficulty="\u6311\u6230", question_count=5,
        )
        rows, status = deliver_mixed_questions(local_question_bank(), specs)
        self.assertGreater(len(specs), 0)
        self.assertEqual(len(rows), 5)
        self.assertEqual(status, "local")
        self.assertTrue(all(row["official_subunit"] == sub.name for row in rows))
        self.assertTrue(all(row["difficulty"] == "\u6311\u6230" for row in rows))


if __name__ == "__main__":
    unittest.main()
