from __future__ import annotations

import unittest

from services.curriculum_master_contracts import GeneratedItemV27
from services.curriculum_master_runtime import RouteContext
from services.practice_mastery_bridge_v27 import apply_generated_item_result_v27


class _Runtime:
    def get_skill_context(self, route, skill_id):
        if skill_id != "G07-A-LINEQ-MEAN-01":
            raise KeyError(skill_id)
        return object()


class _Repository:
    def __init__(self):
        self.saved = None

    def load_latest_knowledge_mastery(self, student_id, profile):
        return {}

    def save_knowledge_mastery(self, student_id, profile, snapshots):
        self.saved = (student_id, profile, snapshots)


class PracticeMasteryBridgeV27Tests(unittest.TestCase):
    def test_generated_item_updates_canonical_skill(self):
        route = RouteContext("PREHIGH", "G7", None, "grade_packs/G7")
        repo = _Repository()
        item = GeneratedItemV27(
            prompt="x+1=3",
            answer="2",
            solution="x=2",
            skill_id="G07-A-LINEQ-MEAN-01",
            micro_skill_id=None,
            difficulty=3,
            validation={"scope": "PASS"},
        )
        updated = apply_generated_item_result_v27(
            _Runtime(),
            route=route,
            repository=repo,
            student_id="student-1",
            item=item,
            is_correct=True,
        )
        self.assertIn(item.skill_id, updated)
        self.assertEqual(repo.saved[1], route.profile_id)
        self.assertEqual(repo.saved[2][item.skill_id].knowledge_id, item.skill_id)


if __name__ == "__main__":
    unittest.main()
