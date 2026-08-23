import unittest

from services.curriculum_catalog import get_curriculum_path
from services.g8_question_service import (
    audit_question_bank,
    build_g8_request_spec,
    coverage_gaps,
    retrieve_questions,
    validate_generated_payload,
)


def _case(publisher, semester, main_text, sub_text, kp_text, qtype, difficulty):
    path = get_curriculum_path(8, publisher, semester)
    unit = next(unit for unit in path.units if main_text in unit.name)
    subunit = next(sub for sub in unit.subunits if sub_text in sub.name)
    kp = next(point for point in subunit.knowledge_points if kp_text in point.name)
    spec = build_g8_request_spec(
        path, main_unit=unit.name, subunit=subunit.name, knowledge_point=kp.name,
        question_type=qtype, difficulty=difficulty, question_count=5,
    )
    return path, spec


class G8QuestionAcceptanceTests(unittest.TestCase):
    def test_five_publisher_skill_cases(self):
        cases = (
            ("康軒", "上學期", "乘法公式與多項式", "乘法公式", "和平方公式", "標準程序", "基礎"),
            ("康軒", "上學期", "乘法公式與多項式", "乘法公式", "平方差公式", "逆向與驗證", "進階"),
            ("康軒", "上學期", "因式分解", "十字交乘法", "首項係數1", "標準程序", "進階"),
            ("翰林", "上學期", "平方根與畢氏定理", "平方根的意義", "畢氏定理", "標準程序", "標準"),
            ("南一", "下學期", "三角形的性質與尺規作圖", "內角與外角", "凸多邊形內角和", "標準程序", "標準"),
        )
        for case in cases:
            with self.subTest(case=case):
                _, spec = _case(*case)
                self.assertTrue(spec.skill_id.startswith("G08-"))
                self.assertTrue(spec.micro_skill_id)
                self.assertEqual(spec.question_count, 5)
                self.assertEqual(spec.question_type, case[-2])
                self.assertEqual(spec.difficulty, case[-1])

    def test_retrieval_prefers_exact_micro_skill(self):
        _, spec = _case("康軒", "上學期", "乘法公式與多項式", "乘法公式", "平方差公式", "逆向與驗證", "進階")
        rows = [
            {"id": "sub", "skill_id": spec.skill_id, "micro_skill_id": "other",
             "official_subunit": spec.official_subunit, "question_type": spec.question_type,
             "difficulty": spec.difficulty},
            {"id": "exact", "skill_id": spec.skill_id, "micro_skill_id": spec.micro_skill_id,
             "official_subunit": spec.official_subunit, "question_type": spec.question_type,
             "difficulty": spec.difficulty},
        ]
        self.assertEqual(retrieve_questions(rows, spec)[0]["id"], "exact")

    def test_coverage_and_validator_contract(self):
        _, spec = _case("康軒", "上學期", "乘法公式與多項式", "乘法公式", "和平方公式", "標準程序", "基礎")
        rows = [{"grade": 8, "skill_id": spec.skill_id, "micro_skill_id": spec.micro_skill_id,
                 "question_type": spec.question_type, "difficulty": spec.difficulty}]
        audit = audit_question_bank(rows)
        self.assertEqual(audit[0]["available_question_count"], 1)
        self.assertEqual(coverage_gaps(audit)[0]["gap"], 4)
        prompts = ("identify concept", "apply procedure", "analyze error", "reverse check", "transfer context")
        payload = [{"grade": 8, "skill_id": spec.skill_id, "micro_skill_id": spec.micro_skill_id,
                    "question_type": spec.question_type, "difficulty": spec.difficulty,
                    "variation_level": 1, "question": prompts[i], "answer": str(i),
                    "solution": f"solution answer is {i}"} for i in range(5)]
        ok, reason, valid = validate_generated_payload(payload, spec)
        self.assertTrue(ok, reason)
        self.assertEqual(len(valid), 5)


if __name__ == "__main__":
    unittest.main()
