import unittest
from types import SimpleNamespace

from services.curriculum_master_runtime import MicroSkill, RouteContext, SkillContext, StandardSkill
from services.curriculum_shadow_v27 import compare_curriculum_route_v27
from services.curriculum_source_v27 import select_curriculum_runtime_v27
from services.curriculum_supabase_runtime import SupabaseCurriculumRuntime


class Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def execute(self):
        rows = self.rows
        for key, value in self.filters:
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return Query(self.tables.get(name, []))


def fixture(status="staged", is_active=False):
    profile = "CURRICULUM_V27:PREHIGH:G6:COMMON"
    release = "CURRICULUM_V27_EA0E6735"
    return Client({
        "curriculum_releases": [
            {"release_id": release, "status": status, "is_active": is_active}
        ],
        "curriculum_profiles": [{
            "release_id": release, "profile_id": profile, "grade": "G6",
            "education_system": "PREHIGH", "track": None,
            "pack_relpath": "grade_packs/G6", "scope_rules": "rules",
        }],
        "curriculum_skills": [{
            "release_id": release, "profile_id": profile, "skill_id": "G06-A",
            "official_code_raw": "N-6-1", "main_unit_id": "M1", "subunit_id": "S1",
            "main_unit": "數", "subunit": "整數", "skill_name": "Skill",
            "focus": "Focus", "difficulty": 2,
        }],
        "curriculum_micro_skills": [{
            "release_id": release, "profile_id": profile, "micro_skill_id": "G06-A-M1",
            "parent_skill_id": "G06-A", "official_code_raw": "N-6-1",
            "main_unit_id": "M1", "subunit_id": "S1", "main_unit": "數",
            "subunit": "整數", "skill_name": "Skill", "question_type": "概念",
            "focus": "Micro", "item_pattern": "p", "common_error": "e", "difficulty": 1,
        }],
        "curriculum_skill_edges": [{
            "release_id": release, "skill_id": "G06-A",
            "related_skill_id": "G05-Z", "edge_type": "prerequisite",
        }],
    })


class ZipRuntime:
    def __init__(self, mismatch=False):
        self.mismatch = mismatch

    def resolve_route(self, *args, **kwargs):
        return RouteContext("PREHIGH", "G6", None, "grade_packs/G6")

    def load_standard_skills(self, route):
        return (StandardSkill(
            "G06-A", "N-6-1", "數", "整數", "Skill",
            "Changed" if self.mismatch else "Focus", 2,
        ),)

    def load_micro_skills(self, route):
        return (MicroSkill(
            "G06-A-M1", "G06-A", "N-6-1", "數", "整數", "Skill",
            "概念", "Micro", "p", "e", 1,
        ),)

    def load_scope_rules(self, route):
        return "rules"

    def get_skill_context(self, route, skill_id):
        return SkillContext(
            route, self.load_standard_skills(route)[0], self.load_micro_skills(route),
            ("G05-Z",), (), self.load_scope_rules(route),
        )


class SupabaseRuntimeTests(unittest.TestCase):
    def test_read_staged_for_shadow(self):
        runtime = SupabaseCurriculumRuntime(
            fixture(), allowed_statuses=("staged", "verified", "active")
        )
        route = runtime.resolve_route("G6")
        self.assertEqual(route.profile_id, "CURRICULUM_V27:PREHIGH:G6:COMMON")
        self.assertEqual(runtime.load_standard_skills(route)[0].skill_id, "G06-A")
        self.assertEqual(runtime.load_micro_skills(route)[0].parent_skill_id, "G06-A")
        self.assertEqual(runtime.get_skill_context(route, "G06-A").prerequisite_ids, ("G05-Z",))

    def test_live_rejects_staged(self):
        with self.assertRaises(Exception):
            select_curriculum_runtime_v27(object(), fixture(), source="supabase")

    def test_live_rejects_verified_inactive(self):
        with self.assertRaises(Exception):
            select_curriculum_runtime_v27(
                object(), fixture("verified"), source="supabase"
            )

    def test_live_accepts_active(self):
        runtime = select_curriculum_runtime_v27(
            object(), fixture("active", True), source="supabase"
        )
        self.assertEqual(runtime.validate()["release_status"], "active")
        self.assertTrue(runtime.validate()["is_active"])

    def test_shadow_returns_zip(self):
        zip_runtime = object()
        self.assertIs(
            select_curriculum_runtime_v27(
                zip_runtime, fixture(), source="supabase_shadow"
            ),
            zip_runtime,
        )


class ShadowTests(unittest.TestCase):
    def test_shadow_match(self):
        db = SupabaseCurriculumRuntime(
            fixture(), allowed_statuses=("staged", "verified", "active")
        )
        report = compare_curriculum_route_v27(ZipRuntime(), db, "G6")
        self.assertTrue(report.matched)
        self.assertEqual(report.zip_skill_count, 1)
        self.assertEqual(report.db_edge_count, 1)

    def test_shadow_detects_field_mismatch(self):
        db = SupabaseCurriculumRuntime(
            fixture(), allowed_statuses=("staged", "verified", "active")
        )
        report = compare_curriculum_route_v27(ZipRuntime(True), db, "G6")
        self.assertFalse(report.matched)
        self.assertTrue(any("field mismatch" in item for item in report.differences))


if __name__ == "__main__":
    unittest.main()
