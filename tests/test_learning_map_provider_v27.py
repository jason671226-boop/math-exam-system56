from __future__ import annotations

from dataclasses import dataclass
import unittest

from services.curriculum_master_runtime import CurriculumMasterRuntime
from services.learning_map_provider_v27 import (
    resolve_learning_map_v27,
    try_resolve_learning_map_v27,
)


@dataclass(frozen=True)
class _Status:
    value: str


@dataclass(frozen=True)
class _Snapshot:
    mastery_status: _Status
    mastery_score: float
    confidence: float
    evidence_count: int


class _Repository:
    def __init__(self, snapshots=None):
        self.snapshots = snapshots or {}
        self.calls = []

    def load_latest_knowledge_mastery(self, student_id, profile_id):
        self.calls.append((student_id, profile_id))
        return self.snapshots


class LearningMapProviderV27Tests(unittest.TestCase):
    def setUp(self):
        self.runtime = CurriculumMasterRuntime()

    def test_pre_high_uses_route_specific_profile_id(self):
        repo = _Repository()
        result = resolve_learning_map_v27(
            self.runtime,
            user_profile={"grade": "7年級", "version": "康軒版"},
            repository=repo,
            student_id="student-1",
        )
        self.assertEqual(result.profile_id, "CURRICULUM_V27:PREHIGH:G7:COMMON")
        self.assertEqual(repo.calls, [("student-1", result.profile_id)])
        self.assertGreater(len(result.model["rows"]), 0)

    def test_existing_knowledge_id_dimension_accepts_canonical_skill(self):
        route = self.runtime.resolve_route("G7")
        skill = self.runtime.load_standard_skills(route)[0]
        snapshot = _Snapshot(_Status("learning"), 45.0, 0.8, 3)
        repo = _Repository({skill.skill_id: snapshot})
        result = resolve_learning_map_v27(
            self.runtime,
            user_profile={"grade": "7年級", "version": "翰林版"},
            repository=repo,
            student_id="student-2",
        )
        row = next(item for item in result.model["rows"] if item["skill_id"] == skill.skill_id)
        self.assertEqual(row["knowledge_id"], skill.skill_id)
        self.assertEqual(row["mastery_status"], "learning")
        self.assertEqual(row["mastery_score"], 45.0)

    def test_ambiguous_g11_fails_closed(self):
        repo = _Repository()
        result = try_resolve_learning_map_v27(
            self.runtime,
            user_profile={"grade": "11年級", "version": "普通高中"},
            repository=repo,
            student_id="student-3",
        )
        self.assertIsNone(result)
        self.assertEqual(repo.calls, [])

    def test_g11_a_route_isolated(self):
        repo = _Repository()
        result = resolve_learning_map_v27(
            self.runtime,
            user_profile={"grade": "11年級", "version": "數學A", "education_system": "GENERAL"},
            repository=repo,
            student_id="student-4",
        )
        self.assertEqual(result.profile_id, "CURRICULUM_V27:GENERAL:G11:A")
        self.assertEqual(result.route.pack_relpath, "grade_packs/G11_A")


if __name__ == "__main__":
    unittest.main()
