from __future__ import annotations

import unittest
from types import SimpleNamespace

from services.curriculum_master_runtime import MicroSkill, RouteContext, SkillContext, StandardSkill
from services.curriculum_source_v27 import select_curriculum_runtime_v27


class TrackingQuery:
    def __init__(self, rows, client):
        self.rows = list(rows)
        self.client = client
        self.filters = []
        self.in_filters = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def in_(self, key, values):
        values = tuple(values)
        self.in_filters.append((key, values))
        self.client.in_calls.append((key, values))
        return self

    def execute(self):
        rows = self.rows
        for key, value in self.filters:
            rows = [row for row in rows if row.get(key) == value]
        for key, values in self.in_filters:
            allowed = set(values)
            rows = [row for row in rows if row.get(key) in allowed]
        return SimpleNamespace(data=rows)


class TrackingClient:
    def __init__(self, tables):
        self.tables = tables
        self.in_calls = []

    def table(self, name):
        return TrackingQuery(self.tables.get(name, []), self)


class ZipRuntime:
    def resolve_route(self, *args, **kwargs):
        return RouteContext("PREHIGH", "G6", None, "grade_packs/G6")

    def load_standard_skills(self, route):
        return (StandardSkill("G06-A", "N-6-1", "數", "整數", "Skill", "Focus", 2),)

    def load_micro_skills(self, route):
        return (
            MicroSkill(
                "G06-A-M1", "G06-A", "N-6-1", "數", "整數", "Skill",
                "概念", "Micro", "p", "e", 1,
            ),
        )

    def load_scope_rules(self, route):
        return "rules"

    def get_skill_context(self, route, skill_id):
        return SkillContext(
            route, self.load_standard_skills(route)[0], self.load_micro_skills(route),
            ("G05-Z",), (), "rules",
        )

    def validate(self):
        return {"release_gate": "PASS"}


def client_fixture():
    release = "CURRICULUM_V27_EA0E6735"
    profile = "CURRICULUM_V27:PREHIGH:G6:COMMON"
    return TrackingClient({
        "curriculum_releases": [{"release_id": release, "status": "staged", "is_active": False}],
        "curriculum_profiles": [{
            "release_id": release, "profile_id": profile, "grade": "G6",
            "education_system": "PREHIGH", "track": None,
            "pack_relpath": "grade_packs/G6", "scope_rules": "rules",
        }],
        "curriculum_skills": [{
            "release_id": release, "profile_id": profile, "skill_id": "G06-A",
            "official_code_raw": "N-6-1", "main_unit_id": "M1", "subunit_id": "S1",
            "main_unit": "數", "subunit": "整數", "skill_name": "Skill",
            "focus": "Focus", "difficulty": 2, "source_order": 1,
        }],
        "curriculum_micro_skills": [{
            "release_id": release, "profile_id": profile, "micro_skill_id": "G06-A-M1",
            "parent_skill_id": "G06-A", "official_code_raw": "N-6-1",
            "main_unit_id": "M1", "subunit_id": "S1", "skill_name": "Skill",
            "question_type": "概念", "focus": "Micro", "item_pattern": "p",
            "common_error": "e", "difficulty": 1, "source_order": 1,
        }],
        "curriculum_skill_edges": [
            {"release_id": release, "skill_id": "G06-A", "related_skill_id": "G05-Z", "edge_type": "prerequisite"},
            {"release_id": release, "skill_id": "G08-X", "related_skill_id": "G07-Y", "edge_type": "prerequisite"},
        ],
    })


class ShadowEdgeScopeTests(unittest.TestCase):
    def test_edge_query_is_scoped_to_route_skill_ids(self):
        client = client_fixture()
        runtime = select_curriculum_runtime_v27(ZipRuntime(), client, source="supabase_shadow")
        route = runtime.resolve_route("G6")
        self.assertTrue(runtime.shadow_observation(route.profile_id).matched)
        self.assertIn(("skill_id", ("G06-A",)), client.in_calls)


if __name__ == "__main__":
    unittest.main()