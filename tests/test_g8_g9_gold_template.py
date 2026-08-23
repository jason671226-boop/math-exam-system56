"""G8 / G9 Gold Template — acceptance tests (Content Expansion)."""

import unittest
from datetime import datetime, timezone

from services.g8_g9_gold_template import build_grade_template, get_grade_record
from services.rollout import (
    all_formal_knowledge_ids,
    cross_grade_graph,
    domain_anchors,
    get_grade,
    high_school_anchors,
    recommend_for_record,
    validate_grade,
)
from services.checkpoint_gold import load_checkpoints
from services.evidence_mastery_gold import (
    Evidence,
    aggregate_knowledge_mastery,
    aggregate_thinking_mastery,
    calculate_mastery,
)
from services.g7_gold_template import get_gold_template
from services.g5_g6_gold_template import get_grade_record as get_g5_g6_record

ENRICHED_FIELDS = (
    "solving_strategy", "key_steps", "common_error_diagnosis", "underlying_principle",
    "variation_methods", "recommended_difficulty_range", "thinking_skill_ids",
)
ERROR_CATEGORIES = {
    "概念錯誤", "符號錯誤", "程序錯誤", "條件擷取錯誤",
    "模型建立錯誤", "運算錯誤", "策略選擇錯誤", "驗證不足",
}


def _now():
    return datetime.now(timezone.utc)


def _evidence(knowledge_id, skills, correct=True):
    return Evidence(
        knowledge_id=knowledge_id, thinking_skill_ids=tuple(skills), difficulty_level=2,
        variation_level=2, correct=correct, hints=0, attempts=1, timestamp=_now(),
        delayed_review=False, cross_unit=False, source_type="diagnostic",
    )


class G8GoldTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = build_grade_template(8)
        cls.record = get_grade_record(8)

    def test_core_knowledge_count_and_stable_ids(self):
        self.assertEqual(len(self.record.knowledge_points), 12)
        self.assertEqual(self.record.knowledge_ids, tuple(f"G8-C{i:02d}" for i in range(1, 13)))

    def test_question_types_enriched(self):
        self.assertEqual(len(self.record.question_types), 16)
        for q in self.record.question_types:
            self.assertTrue(q.type_id.startswith("G8-C"), q.type_id)
            for field in ENRICHED_FIELDS:
                self.assertTrue(getattr(q, field), q.type_id)
            self.assertGreaterEqual(len(q.key_steps), 2, q.type_id)
            self.assertIn(q.common_error_diagnosis["category"], ERROR_CATEGORIES, q.type_id)
            self.assertTrue(q.thinking_skill_ids, q.type_id)
            for sid in q.thinking_skill_ids:
                self.assertTrue(sid.startswith("TS-"))
                self.assertNotIn("G7", sid)

    def test_difficulty_coverage(self):
        for q in self.record.question_types:
            rng = q.recommended_difficulty_range
            self.assertIn(rng["min_level"], (1, 2, 3, 4, 5))
            self.assertIn(rng["max_level"], (1, 2, 3, 4, 5))
            self.assertIn(rng["default_level"], (1, 2, 3, 4, 5))

    def test_publisher_mapping_skeleton_needs_verification(self):
        mapping = self.record.publisher_mapping
        self.assertEqual(set(mapping), {"康軒", "翰林", "南一"})
        for pub, semesters in mapping.items():
            for sem in ("上學期", "下學期"):
                self.assertEqual(semesters[sem]["units"], [])
                self.assertEqual(semesters[sem]["verification_status"], "NEEDS_VERIFICATION")

    def test_curriculum_codes_not_fabricated(self):
        for p in self.record.knowledge_points:
            self.assertEqual(p.curriculum_codes, ())

    def test_checkpoints_exist(self):
        checkpoints = load_checkpoints(8)
        self.assertEqual(len(checkpoints), 4)
        semesters = {cp["semester"] for cp in checkpoints}
        self.assertEqual(semesters, {"上學期", "下學期"})


class G9GoldTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = get_grade_record(9)

    def test_core_knowledge_count_and_stable_ids(self):
        self.assertEqual(len(self.record.knowledge_points), 12)
        self.assertEqual(self.record.knowledge_ids, tuple(f"G9-C{i:02d}" for i in range(1, 13)))

    def test_question_types_enriched(self):
        self.assertEqual(len(self.record.question_types), 16)
        for q in self.record.question_types:
            self.assertTrue(q.solving_strategy)
            self.assertTrue(q.thinking_skill_ids)
            self.assertIn(q.common_error_diagnosis["category"], ERROR_CATEGORIES)

    def test_checkpoints_exist(self):
        checkpoints = load_checkpoints(9)
        self.assertEqual(len(checkpoints), 4)


class CrossGradePrerequisiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = cross_grade_graph()
        cls.known = set(domain_anchors()) | set(all_formal_knowledge_ids()) | set(high_school_anchors())

    def test_no_broken_links_and_acyclic(self):
        self.assertEqual(self.graph.broken_links(self.known), ())
        self.assertEqual(self.graph.cycles(), ())

    def test_g7_to_g8_bridge(self):
        self.assertIn("G8-C01", self.graph.successors("G7-C08"))

    def test_g8_to_g9_bridge(self):
        self.assertIn("G9-C01", self.graph.successors("G8-C01"))
        self.assertIn("G9-C04", self.graph.successors("G8-C05"))

    def test_g7_to_g9_transitive(self):
        follow = self.graph.transitive_follow_ups("G7-C08")
        self.assertIn("G8-C01", follow)
        self.assertIn("G9-C01", follow)

    def test_g9_to_high_school_anchor(self):
        self.assertIn("HS:代數", self.graph.successors("G9-C04"))
        self.assertIn("HS:空間與形狀", self.graph.successors("G9-C07"))


class IntegrationTests(unittest.TestCase):
    def test_mastery_consumes_g8_g9(self):
        for grade in (8, 9):
            record = get_grade_record(grade)
            q = record.question_types[0]
            mastery = calculate_mastery([_evidence(record.knowledge_ids[0], q.thinking_skill_ids)])
            self.assertIn(mastery.status, ("unassessed", "needs_work", "learning", "basic", "proficient"))

    def test_recommendation_produces_next_action(self):
        for grade in (8, 9):
            record = get_grade_record(grade)
            km = aggregate_knowledge_mastery([_evidence(record.knowledge_ids[0], ("TS-DEFINE",), True)])
            tm = aggregate_thinking_mastery([_evidence(record.knowledge_ids[0], ("TS-DEFINE",), False)])
            steps = recommend_for_record(record, km, tm)
            self.assertTrue(steps, grade)
            for step in steps:
                self.assertTrue(step.question_type_id)
                self.assertTrue(step.reason)

    def test_validator_zero_errors(self):
        for grade in (8, 9):
            report = validate_grade(get_grade(grade))
            self.assertTrue(report.passed, grade)
            self.assertEqual(len(report.errors), 0, grade)

    def test_g5_g6_g7_regression(self):
        g7 = get_gold_template()
        self.assertEqual(g7["core_knowledge_total"], 23)
        self.assertEqual(g7["question_type_total"], 164)
        self.assertEqual(len(get_g5_g6_record(5).knowledge_points), 30)
        self.assertEqual(len(get_g5_g6_record(6).knowledge_points), 16)


if __name__ == "__main__":
    unittest.main()
