import ast
from pathlib import Path
import unittest

from services.curriculum_catalog import PUBLISHERS, SEMESTERS, get_curriculum_path, knowledge_point_labels, question_type_labels, subunit_labels
from services.g8_question_service import build_g8_request_spec, deliver_questions, local_question_bank


class G8ButtonHandlerTests(unittest.TestCase):
    def test_streamlit_handler_is_wired_to_local_delivery(self):
        source = Path("app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = {node.func.id for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertIn("deliver_questions", calls)
        self.assertIn("deliver_mixed_questions", calls)
        self.assertIn("local_question_bank", calls)

    def test_real_selection_path_delivers_five_without_ai(self):
        path = get_curriculum_path(8, PUBLISHERS[0], SEMESTERS[0])
        main = next(unit.name for unit in path.units if "乘法公式" in unit.name)
        sub_label = next(label for label in subunit_labels(path, [main]) if "乘法公式" in label)
        kp_label = next(label for label in knowledge_point_labels(path, [sub_label]) if "平方差公式" in label)
        qtype = next(label for label in question_type_labels(path, [sub_label], [kp_label]) if "標準程序" in label)
        spec = build_g8_request_spec(path, main_unit=main, subunit=sub_label,
                                     knowledge_point=kp_label, question_type=qtype,
                                     difficulty="標準", question_count=5)
        calls = []
        rows, status = deliver_questions(local_question_bank(), spec,
                                          lambda _: calls.append(True))
        self.assertEqual(spec.skill_id, "G08-A-MULFORM-03")
        self.assertEqual(len(rows), 5)
        self.assertEqual(status, "local_generator")
        self.assertFalse(calls)
        self.assertTrue(all(row["source"] in {"STATIC_BANK", "LOCAL_GENERATOR"} for row in rows))


if __name__ == "__main__":
    unittest.main()
