from __future__ import annotations

import unittest

from services.curriculum_master_contracts import DiagnosisV27
from services.curriculum_master_runtime import CurriculumMasterRuntime
from services.diagnostic_mastery_bridge_v27 import persist_diagnosis_mastery_v27
from services.mastery_repository import SessionStateMasteryRepository


class DiagnosticMasteryBridgeV27Tests(unittest.TestCase):
    def setUp(self):
        self.runtime = CurriculumMasterRuntime()
        self.state = {}
        self.repo = SessionStateMasteryRepository(self.state)

    def test_canonical_skill_id_is_persisted_as_knowledge_id(self):
        route = self.runtime.resolve_route("G7")
        skill = self.runtime.load_standard_skills(route)[0]
        diagnosis = DiagnosisV27(
            skill_id=skill.skill_id,
            micro_skill_id=None,
            error_type="concept",
            confidence=0.8,
        )
        updated = persist_diagnosis_mastery_v27(
            self.runtime,
            route,
            repository=self.repo,
            student_id="local-student",
            diagnosis=diagnosis,
            is_correct=False,
        )
        self.assertIn(skill.skill_id, updated)
        stored = self.repo.load_latest_knowledge_mastery("local-student", route.profile_id)
        self.assertIn(skill.skill_id, stored)
        self.assertEqual(stored[skill.skill_id].knowledge_id, skill.skill_id)
        self.assertEqual(stored[skill.skill_id].source_profiles, (route.profile_id,))

    def test_wrong_track_skill_is_rejected(self):
        route_a = self.runtime.resolve_route("G11", education_system="GENERAL", track="A")
        route_b = self.runtime.resolve_route("G11", education_system="GENERAL", track="B")
        skill_b = self.runtime.load_standard_skills(route_b)[0]
        diagnosis = DiagnosisV27(
            skill_id=skill_b.skill_id,
            micro_skill_id=None,
            error_type="route_leak",
            confidence=0.9,
        )
        with self.assertRaises(KeyError):
            persist_diagnosis_mastery_v27(
                self.runtime,
                route_a,
                repository=self.repo,
                student_id="local-student",
                diagnosis=diagnosis,
                is_correct=False,
            )

    def test_low_confidence_is_downweighted_not_promoted(self):
        route = self.runtime.resolve_route("G8")
        skill = self.runtime.load_standard_skills(route)[0]
        diagnosis = DiagnosisV27(
            skill_id=skill.skill_id,
            micro_skill_id=None,
            error_type="uncertain",
            confidence=0.3,
        )
        updated = persist_diagnosis_mastery_v27(
            self.runtime,
            route,
            repository=self.repo,
            student_id="local-student",
            diagnosis=diagnosis,
            is_correct=True,
        )
        self.assertLess(updated[skill.skill_id].confidence, 0.3)


if __name__ == "__main__":
    unittest.main()
