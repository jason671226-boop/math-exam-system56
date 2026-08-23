"""G5 / G6 Gold Template — acceptance tests (Content Expansion).

Locks: stable IDs, core knowledge counts, question-type enrichment, thinking-skill
mapping coverage, difficulty coverage, eight-category error diagnosis, prerequisite /
follow-up graph, publisher-mapping skeleton (NEEDS_VERIFICATION), cross-grade
G4->G5->G6->G7 edges, shared Evidence/Mastery/Recommendation integration,
integrated checkpoints, validator (0 blocking errors), and G7 regression.
"""

import unittest
from datetime import datetime, timezone

from services.g5_g6_gold_template import build_grade_template, get_grade_record
from services.rollout import (
    DOMAIN_CODES,
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


class G5GoldTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = build_grade_template(5)
        cls.record = get_grade_record(5)

    def test_core_knowledge_count_and_stable_ids(self):
        self.assertEqual(len(self.record.knowledge_points), 30)
        self.assertEqual(self.record.knowledge_ids, tuple(f"G5-C{i:02d}" for i in range(1, 31)))

    def test_question_type_count_and_stable_ids(self):
        self.assertEqual(len(self.record.question_types), 88)
        self.assertTrue(all(t.type_id.startswith("G5-C") for t in self.record.question_types))

    def test_semester_split(self):
        from collections import Counter
        counts = Counter(p.semester for p in self.record.knowledge_points)
        self.assertEqual(counts, {"上學期": 15, "下學期": 15})

    def test_all_question_types_enriched(self):
        for q in self.record.question_types:
            for field in ENRICHED_FIELDS:
                self.assertTrue(getattr(q, field), q.type_id)
            self.assertGreaterEqual(len(q.key_steps), 2, q.type_id)
            self.assertIn(q.common_error_diagnosis["category"], ERROR_CATEGORIES, q.type_id)

    def test_thinking_skill_mapping_full_coverage(self):
        for q in self.record.question_types:
            self.assertTrue(q.thinking_skill_ids, q.type_id)
            for skill_id in q.thinking_skill_ids:
                self.assertTrue(skill_id.startswith("TS-"), q.type_id)
                self.assertNotIn("G7", skill_id)

    def test_difficulty_coverage(self):
        for q in self.record.question_types:
            rng = q.recommended_difficulty_range
            self.assertIn(rng["min_level"], (1, 2, 3, 4, 5))
            self.assertIn(rng["max_level"], (1, 2, 3, 4, 5))
            self.assertIn(rng["default_level"], (1, 2, 3, 4, 5))

    def test_prerequisite_follow_up_graph(self):
        ids = set(self.record.knowledge_ids)
        for kid, prereqs in self.record.prerequisite_graph.items():
            self.assertIn(kid, ids)
            for p in prereqs:
                self.assertIn(p, ids)
        for kid, follow in self.record.follow_up_graph.items():
            for f in follow:
                self.assertIn(f, ids)

    def test_publisher_mapping_skeleton_needs_verification(self):
        mapping = self.record.publisher_mapping
        self.assertEqual(set(mapping), {"康軒", "翰林", "南一"})
        for pub, semesters in mapping.items():
            for sem in ("上學期", "下學期"):
                self.assertEqual(semesters[sem]["units"], [])
                self.assertEqual(semesters[sem]["verification_status"], "NEEDS_VERIFICATION")

    def test_curriculum_codes_not_fabricated(self):
        # no authoritative 108-curriculum mapping yet -> codes remain empty
        for p in self.record.knowledge_points:
            self.assertEqual(p.curriculum_codes, ())


class G6GoldTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = build_grade_template(6)
        cls.record = get_grade_record(6)

    def test_core_knowledge_count_and_stable_ids(self):
        self.assertEqual(len(self.record.knowledge_points), 16)
        self.assertEqual(self.record.knowledge_ids, tuple(f"G6-C{i:02d}" for i in range(1, 17)))

    def test_question_type_count_and_enrichment(self):
        self.assertEqual(len(self.record.question_types), 48)
        for q in self.record.question_types:
            self.assertTrue(q.solving_strategy)
            self.assertTrue(q.thinking_skill_ids)
            self.assertIn(q.common_error_diagnosis["category"], ERROR_CATEGORIES)

    def test_domains_in_canonical_vocabulary(self):
        for domain in self.record.domains:
            self.assertIn(domain, DOMAIN_CODES)

    def test_checkpoints_exist(self):
        checkpoints = load_checkpoints(6)
        self.assertEqual(len(checkpoints), 4)
        semesters = {cp["semester"] for cp in checkpoints}
        self.assertEqual(semesters, {"上學期", "下學期"})
        for cp in checkpoints:
            for cid in cp["core_ids"]:
                self.assertIn(cid, self.record.knowledge_ids)


class CrossGradePrerequisiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = cross_grade_graph()
        cls.known = set(domain_anchors()) | set(all_formal_knowledge_ids()) | set(high_school_anchors())

    def test_no_broken_links_and_acyclic(self):
        self.assertEqual(self.graph.broken_links(self.known), ())
        self.assertEqual(self.graph.cycles(), ())

    def test_g4_to_g5_bridge(self):
        self.assertIn("G5-C01", self.graph.successors("G4:數與量"))

    def test_g5_to_g6_bridge(self):
        self.assertIn("G6-C03", self.graph.successors("G5-C13"))

    def test_g6_to_g7_bridge(self):
        self.assertIn("G7-C09", self.graph.successors("G6-C06"))
        self.assertIn("G7-C07", self.graph.successors("G6-C03"))

    def test_g4_to_g7_transitive_chain(self):
        follow = self.graph.transitive_follow_ups("G4:數與量")
        self.assertIn("G5-C01", follow)
        self.assertIn("G7-C01", follow)


class IntegrationTests(unittest.TestCase):
    def test_mastery_consumes_g5_g6(self):
        for grade in (5, 6):
            record = get_grade_record(grade)
            q = record.question_types[0]
            mastery = calculate_mastery([_evidence(record.knowledge_ids[0], q.thinking_skill_ids)])
            self.assertIn(mastery.status, ("unassessed", "needs_work", "learning", "basic", "proficient"))

    def test_recommendation_produces_next_action(self):
        for grade in (5, 6):
            record = get_grade_record(grade)
            km = aggregate_knowledge_mastery([_evidence(record.knowledge_ids[0], ("TS-DEFINE",), True)])
            tm = aggregate_thinking_mastery([_evidence(record.knowledge_ids[0], ("TS-DEFINE",), False)])
            steps = recommend_for_record(record, km, tm)
            self.assertTrue(steps, grade)
            for step in steps:
                self.assertTrue(step.question_type_id)
                self.assertTrue(step.reason)

    def test_validator_zero_errors(self):
        for grade in (5, 6):
            report = validate_grade(get_grade(grade))
            self.assertTrue(report.passed, grade)
            self.assertEqual(len(report.errors), 0, grade)

    def test_g7_regression(self):
        template = get_gold_template()
        self.assertEqual(template["core_knowledge_total"], 23)
        self.assertEqual(template["question_type_total"], 164)


if __name__ == "__main__":
    unittest.main()
