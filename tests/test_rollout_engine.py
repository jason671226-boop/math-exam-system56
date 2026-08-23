"""G1-G9 Rollout Engine — acceptance tests (Phase 9).

Covers grade registry, rollout validator, cross-grade prerequisite graph,
publisher mapping framework, mastery/recommendation compatibility, the grade
template generator, and G7 regression.
"""

import unittest
from datetime import datetime, timezone

from services.rollout import (
    CURRICULUM_CODE_RE,
    DOMAIN_CODES,
    SEMESTERS,
    CrossGradeGraph,
    all_formal_knowledge_ids,
    cross_grade_graph,
    domain_anchors,
    generate_grade_template,
    get_grade,
    high_school_anchors,
    list_grades,
    recommend_for_record,
    scaffold_grade,
    validate_all,
    validate_grade,
)
from services.rollout.schema import (
    GradeRecord,
    KnowledgePoint,
    QuestionTypeRecord,
)
from services.evidence_mastery_gold import (
    Evidence,
    aggregate_knowledge_mastery,
    aggregate_thinking_mastery,
    calculate_mastery,
)
from services.g7_gold_template import get_gold_template

GRADES = (1, 2, 3, 4, 5, 6, 7, 8, 9)


def _now():
    return datetime.now(timezone.utc)


def _evidence(knowledge_id, skills, correct=True, difficulty=2, variation=2):
    return Evidence(
        knowledge_id=knowledge_id,
        thinking_skill_ids=tuple(skills),
        difficulty_level=difficulty,
        variation_level=variation,
        correct=correct,
        hints=0,
        attempts=1,
        timestamp=_now(),
        delayed_review=False,
        cross_unit=False,
        source_type="diagnostic",
    )


class GradeRegistryTests(unittest.TestCase):
    def test_nine_grades_registered(self):
        self.assertEqual(list_grades(), GRADES)

    def test_g7_is_formal_and_complete(self):
        record = get_grade(7)
        self.assertEqual(record.status, "formal")
        self.assertEqual(len(record.knowledge_points), 23)
        self.assertEqual(len(record.question_types), 164)
        self.assertEqual(record.domains, ("數與量", "代數", "空間與形狀", "資料與不確定性"))

    def test_skeletons_are_backward_compatible(self):
        for grade in (1, 2, 3, 4):
            record = get_grade(grade)
            self.assertEqual(record.status, "skeleton", grade)
            self.assertEqual(len(record.knowledge_points), 0, grade)
            self.assertEqual(len(record.question_types), 0, grade)
            self.assertEqual(record.semesters, SEMESTERS, grade)
            self.assertTrue(all(d in DOMAIN_CODES for d in record.domains), grade)
            self.assertEqual(set(record.publisher_mapping), {"康軒", "翰林", "南一"}, grade)

    def test_g7_stable_ids_preserved(self):
        record = get_grade(7)
        self.assertEqual(record.knowledge_ids, tuple(f"G7-C{i:02d}" for i in range(1, 24)))


class CrossGradeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = cross_grade_graph()
        cls.record = get_grade(7)
        cls.known = set(domain_anchors()) | set(all_formal_knowledge_ids()) | set(high_school_anchors())

    def test_no_broken_links(self):
        self.assertEqual(self.graph.broken_links(self.known), ())

    def test_acyclic(self):
        self.assertEqual(self.graph.cycles(), ())
        self.assertTrue(self.graph.is_acyclic())

    def test_same_domain_chain_queries(self):
        # G7-C09 (algebra) is fed by the algebra and number chains upstream.
        prereqs = self.graph.transitive_prerequisites("G7-C09")
        self.assertIn("G6:代數", prereqs)
        self.assertIn("G6:數與量", prereqs)

    def test_one_to_many_and_many_to_one(self):
        # one-to-many: G6:數與量 feeds several G7 knowledge points
        follow = self.graph.successors("G6:數與量")
        self.assertIn("G7-C01", follow)
        self.assertIn("G7-C09", follow)
        # many-to-one: G7-C09 has multiple predecessors
        preds = self.graph.predecessors("G7-C09")
        self.assertGreater(len(preds), 1)

    def test_follow_up_chain_reaches_g9(self):
        follow = self.graph.transitive_follow_ups("G7-C08")
        self.assertIn("G8:數與量", follow)
        self.assertIn("G9:數與量", follow)


class RolloutValidatorTests(unittest.TestCase):
    def test_g7_passes_with_zero_errors(self):
        report = validate_grade(get_grade(7))
        self.assertTrue(report.passed)
        self.assertEqual(len(report.errors), 0)

    def test_all_skeletons_pass(self):
        for report in validate_all():
            self.assertTrue(report.passed, report.grade)

    def test_detects_orphan_question_type(self):
        record = _record(
            knowledge=(_kp("G5-K01"),),
            question_types=(_qt("G5-K01-Q01", "G5-K99"),),  # references unknown knowledge
        )
        report = validate_grade(record)
        self.assertFalse(report.passed)
        self.assertTrue(any(i.check == "orphan_question_type" for i in report.errors))

    def test_detects_cycle(self):
        record = _record(
            knowledge=(_kp("G5-K01"), _kp("G5-K02")),
            prereq={"G5-K01": ("G5-K02",), "G5-K02": ("G5-K01",)},
        )
        report = validate_grade(record)
        self.assertFalse(report.passed)

    def test_detects_missing_prerequisite(self):
        record = _record(
            knowledge=(_kp("G5-K01"),),
            prereq={"G5-K01": ("G5-K99",)},  # missing
        )
        report = validate_grade(record)
        self.assertTrue(any(i.check == "missing_prerequisite" for i in report.errors))

    def test_detects_invalid_curriculum_code(self):
        record = _record(knowledge=(_kp("G5-K01", codes=("BAD",)),))
        report = validate_grade(record)
        self.assertTrue(any(i.check == "curriculum_code" for i in report.errors))

    def test_detects_invalid_publisher_mapping(self):
        record = _record(
            knowledge=(_kp("G5-K01"),),
            publisher_mapping={"康軒": {"上學期": {"units": [{"subunits": [{"core_ids": ["G5-K99"]}]}]}}},
        )
        report = validate_grade(record)
        self.assertTrue(any(i.check == "publisher_mapping" for i in report.errors))


class CurriculumCodeFormatTests(unittest.TestCase):
    def test_single_and_range_codes_valid(self):
        self.assertTrue(CURRICULUM_CODE_RE.fullmatch("N-7-3"))
        self.assertTrue(CURRICULUM_CODE_RE.fullmatch("S-7-1~S-7-5"))

    def test_invalid_codes_rejected(self):
        self.assertIsNone(CURRICULUM_CODE_RE.fullmatch("n-7-3"))
        self.assertIsNone(CURRICULUM_CODE_RE.fullmatch("7-N-3"))
        self.assertIsNone(CURRICULUM_CODE_RE.fullmatch("N-7"))


class PublisherMappingFrameworkTests(unittest.TestCase):
    def test_g7_three_publishers_complete(self):
        record = get_grade(7)
        mapping = record.publisher_mapping
        self.assertEqual(set(mapping), {"康軒", "翰林", "南一"})
        for publisher, semesters in mapping.items():
            self.assertEqual(set(semesters), set(SEMESTERS), publisher)
            for semester in SEMESTERS:
                for unit in semesters[semester]["units"]:
                    for subunit in unit["subunits"]:
                        for core_id in subunit["core_ids"]:
                            self.assertIn(core_id, record.knowledge_ids, core_id)


class MasteryRecommendationCompatibilityTests(unittest.TestCase):
    def test_mastery_consumes_g7_record(self):
        record = get_grade(7)
        q = record.question_types[0]
        evidence = [_evidence("G7-C01", q.thinking_skill_ids, correct=True)]
        mastery = calculate_mastery(evidence)
        self.assertIn(mastery.status, ("unassessed", "needs_work", "learning", "basic", "proficient"))

    def test_recommendation_consumes_g7_record(self):
        record = get_grade(7)
        km = aggregate_knowledge_mastery([_evidence("G7-C01", ("TS-DEFINE",), True)])
        tm = aggregate_thinking_mastery([_evidence("G7-C01", ("TS-DEFINE",), False)])
        steps = recommend_for_record(record, km, tm)
        self.assertTrue(steps)
        for step in steps:
            self.assertTrue(step.question_type_id)
            self.assertTrue(step.reason)

    def test_recommendation_empty_for_skeleton(self):
        record = get_grade(4)
        steps = recommend_for_record(record, {}, {})
        self.assertEqual(steps, ())


class GeneratorTests(unittest.TestCase):
    def test_generate_template_structure(self):
        template = generate_grade_template(4)
        for key in ("schema_version", "grade", "status", "semesters", "domains",
                    "knowledge_points", "question_type_catalog",
                    "publisher_mapping", "checkpoints", "templates"):
            self.assertIn(key, template)
        self.assertEqual(template["grade"], 4)
        self.assertEqual(template["status"], "skeleton")

    def test_scaffold_refuses_to_overwrite(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "g5_skeleton.json"
            scaffold_grade(5, target)
            self.assertTrue(target.exists())
            with self.assertRaises(FileExistsError):
                scaffold_grade(5, target)


class G7RegressionTests(unittest.TestCase):
    def test_gold_template_intact(self):
        template = get_gold_template()
        self.assertEqual(template["core_knowledge_total"], 23)
        self.assertEqual(template["question_type_total"], 164)
        self.assertEqual(set(template["publishers"]), {"康軒", "翰林", "南一"})

    def test_g7_question_type_ids_stable(self):
        record = get_grade(7)
        self.assertEqual(len(record.question_type_ids), 164)
        self.assertTrue(all(tid.startswith("G7-C") for tid in record.question_type_ids))


# --- helpers for building synthetic records ---

def _kp(kid, codes=("N-5-1",)):
    return KnowledgePoint(
        id=kid, grade=5, semester="上學期", domain="數與量", core_topic="t", subunit="s",
        curriculum_codes=tuple(codes), prerequisite_ids=(), follow_up_ids=(),
    )


def _qt(type_id, knowledge_id):
    return QuestionTypeRecord(
        type_id=type_id, knowledge_id=knowledge_id, name="q", category="計算", difficulty="標準",
        solving_strategy="s", key_steps=("a", "b"),
        common_error_diagnosis={"category": "運算錯誤", "error": "e", "diagnosis": "d"},
        underlying_principle="p", prerequisite_knowledge_ids=(), follow_up_knowledge_ids=(),
        variation_methods=(), recommended_difficulty_range={"min_level": 1, "max_level": 2, "default_level": 1},
        thinking_skill_ids=("TS-DEFINE",),
    )


def _record(knowledge=(), question_types=(), prereq=None, follow=None, publisher_mapping=None):
    kp = tuple(knowledge)
    knowledge_ids = {p.id for p in kp}
    return GradeRecord(
        grade_id=5,
        semesters=SEMESTERS,
        domains=("數與量",),
        status="formal",
        knowledge_points=kp,
        question_types=tuple(question_types),
        publisher_mapping=publisher_mapping if publisher_mapping is not None else {
            "康軒": {"上學期": {"units": []}, "下學期": {"units": []}},
            "翰林": {"上學期": {"units": []}, "下學期": {"units": []}},
            "南一": {"上學期": {"units": []}, "下學期": {"units": []}},
        },
        prerequisite_graph=dict(prereq or {}),
        follow_up_graph=dict(follow or {}),
    )


if __name__ == "__main__":
    unittest.main()
