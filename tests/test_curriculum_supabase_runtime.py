import unittest
from types import SimpleNamespace

from services.curriculum_master_runtime import MicroSkill, RouteContext, SkillContext, StandardSkill
from services.curriculum_shadow_runtime_v27 import ShadowCurriculumRuntimeV27
from services.curriculum_shadow_v27 import compare_curriculum_route_v27
from services.curriculum_source_v27 import select_curriculum_runtime_v27
from services.curriculum_supabase_runtime import SupabaseCurriculumRuntime


class Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []
        self.in_filters = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def in_(self, key, values):
        self.in_filters.append((key, set(values)))
        return self

    def execute(self):
        rows = self.rows
        for key, value in self.filters:
            rows = [row for row in rows if row.get(key) == value]
        for key, values in self.in_filters:
            rows = [row for row in rows if row.get(key) in values]
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return Query(self.tables.get(name, []))


def fixture(status="staged", is_active=False, gate_status=None):
    profile = "CURRICULUM_V27:PREHIGH:G6:COMMON"
    release = "CURRICULUM_V27_EA0E6735"
    return Client(
        {
            "curriculum_releases": [
                {"release_id": release, "status": status, "is_active": is_active}
            ],
            "curriculum_profiles": [
                {
                    "release_id": release,
                    "profile_id": profile,
                    "grade": "G6",
                    "education_system": "PREHIGH",
                    "track": None,
                    "pack_relpath": "grade_packs/G6",
                    "scope_rules": "rules",
                }
            ],
            "curriculum_skills": [
                {
                    "release_id": release,
                    "profile_id": profile,
                    "skill_id": "G06-A",
                    "official_code_raw": "N-6-1",
                    "main_unit_id": "M1",
                    "subunit_id": "S1",
                    "main_unit": "數",
                    "subunit": "整數",
                    "skill_name": "Skill",
                    "focus": "Focus",
                    "difficulty": 2,
                    "source_order": 1,
                }
            ],
            "curriculum_micro_skills": [
                {
                    "release_id": release,
                    "profile_id": profile,
                    "micro_skill_id": "G06-A-M1",
                    "parent_skill_id": "G06-A",
                    "official_code_raw": "N-6-1",
                    "main_unit_id": "M1",
                    "subunit_id": "S1",
                    "skill_name": "Skill",
                    "question_type": "概念",
                    "focus": "Micro",
                    "item_pattern": "p",
                    "common_error": "e",
                    "difficulty": 1,
                    "source_order": 1,
                }
            ],
            "curriculum_skill_edges": [
                {
                    "release_id": release,
                    "skill_id": "G06-A",
                    "related_skill_id": "G05-Z",
                    "edge_type": "prerequisite",
                }
            ],
            "curriculum_release_checks": (
                [
                    {
                        "release_id": release,
                        "check_name": "activation_gate",
                        "status": gate_status,
                    }
                ]
                if gate_status is not None
                else []
            ),
        }
    )


class ZipRuntime:
    def __init__(self, mismatch=False):
        self.mismatch = mismatch

    def resolve_route(self, *args, **kwargs):
        return RouteContext("PREHIGH", "G6", None, "grade_packs/G6")

    def load_standard_skills(self, route):
        return (
            StandardSkill(
                "G06-A",
                "N-6-1",
                "數",
                "整數",
                "Skill",
                "Changed" if self.mismatch else "Focus",
                2,
            ),
        )

    def load_micro_skills(self, route):
        return (
            MicroSkill(
                "G06-A-M1",
                "G06-A",
                "N-6-1",
                "數",
                "整數",
                "Skill",
                "概念",
                "Micro",
                "p",
                "e",
                1,
            ),
        )

    def load_scope_rules(self, route):
        return "rules"

    def get_skill_context(self, route, skill_id):
        return SkillContext(
            route,
            self.load_standard_skills(route)[0],
            self.load_micro_skills(route),
            ("G05-Z",),
            (),
            self.load_scope_rules(route),
        )

    def validate(self):
        return {"release_gate": "PASS", "source": "zip"}


class G7ZipRuntime(ZipRuntime):
    def resolve_route(self, *args, **kwargs):
        return RouteContext("PREHIGH", "G7", None, "grade_packs/G7")


class TwoSkillZipRuntime:
    def resolve_route(self, *args, **kwargs):
        return RouteContext("PREHIGH", "G6", None, "grade_packs/G6")

    def load_standard_skills(self, route):
        return (
            StandardSkill("G06-Z", "N-6-1", "數", "整數", "First", "F1", 1),
            StandardSkill("G06-A", "N-6-1", "數", "整數", "Second", "F2", 1),
        )

    def load_micro_skills(self, route):
        return ()

    def load_scope_rules(self, route):
        return "rules"

    def get_skill_context(self, route, skill_id):
        skill = next(item for item in self.load_standard_skills(route) if item.skill_id == skill_id)
        return SkillContext(route, skill, (), (), (), "rules")


class ReverseTwoSkillDbRuntime(TwoSkillZipRuntime):
    def load_standard_skills(self, route):
        return tuple(reversed(super().load_standard_skills(route)))

    def load_skill_edges(self, route):
        return ()


class SupabaseRuntimeTests(unittest.TestCase):
    def test_read_staged_for_shadow(self):
        runtime = SupabaseCurriculumRuntime(
            fixture(), allowed_statuses=("staged", "verified", "active")
        )
        route = runtime.resolve_route("G6")
        self.assertEqual(route.profile_id, "CURRICULUM_V27:PREHIGH:G6:COMMON")
        self.assertEqual(runtime.load_standard_skills(route)[0].skill_id, "G06-A")
        micro = runtime.load_micro_skills(route)[0]
        self.assertEqual(micro.parent_skill_id, "G06-A")
        self.assertEqual((micro.main_unit, micro.subunit), ("數", "整數"))
        self.assertEqual(runtime.get_skill_context(route, "G06-A").prerequisite_ids, ("G05-Z",))

    def test_source_order_wins_over_identifier_sort(self):
        client = fixture()
        first = dict(client.tables["curriculum_skills"][0])
        first.update(
            {
                "skill_id": "G06-Z",
                "skill_name": "First",
                "focus": "F1",
                "source_order": 1,
            }
        )
        second = dict(client.tables["curriculum_skills"][0])
        second.update(
            {
                "skill_id": "G06-A",
                "skill_name": "Second",
                "focus": "F2",
                "source_order": 2,
            }
        )
        client.tables["curriculum_skills"] = [second, first]
        runtime = SupabaseCurriculumRuntime(
            client, allowed_statuses=("staged", "verified", "active")
        )
        route = runtime.resolve_route("G6")
        self.assertEqual(
            tuple(item.skill_id for item in runtime.load_standard_skills(route)),
            ("G06-Z", "G06-A"),
        )

    def test_missing_source_order_fails_closed(self):
        client = fixture()
        client.tables["curriculum_skills"][0].pop("source_order")
        runtime = SupabaseCurriculumRuntime(
            client, allowed_statuses=("staged", "verified", "active")
        )
        route = runtime.resolve_route("G6")
        with self.assertRaises(Exception):
            runtime.load_standard_skills(route)

    def test_live_rejects_staged(self):
        with self.assertRaises(Exception):
            select_curriculum_runtime_v27(object(), fixture(), source="supabase")

    def test_live_rejects_verified_inactive(self):
        with self.assertRaises(Exception):
            select_curriculum_runtime_v27(object(), fixture("verified"), source="supabase")

    def test_live_rejects_active_without_gate(self):
        with self.assertRaises(Exception):
            select_curriculum_runtime_v27(object(), fixture("active", True), source="supabase")

    def test_live_rejects_active_failed_gate(self):
        with self.assertRaises(Exception):
            select_curriculum_runtime_v27(object(), fixture("active", True, "FAIL"), source="supabase")

    def test_live_accepts_active_with_passed_gate(self):
        runtime = select_curriculum_runtime_v27(
            object(), fixture("active", True, "PASS"), source="supabase"
        )
        self.assertEqual(runtime.validate()["release_status"], "active")
        self.assertTrue(runtime.validate()["is_active"])

    def test_shadow_wraps_zip_and_observes_match(self):
        zip_runtime = ZipRuntime()
        runtime = select_curriculum_runtime_v27(
            zip_runtime, fixture(), source="supabase_shadow"
        )
        self.assertIsInstance(runtime, ShadowCurriculumRuntimeV27)
        route = runtime.resolve_route("G6")
        self.assertEqual(route.profile_id, "CURRICULUM_V27:PREHIGH:G6:COMMON")
        observation = runtime.shadow_observation(route.profile_id)
        self.assertIsNotNone(observation)
        self.assertTrue(observation.matched)
        self.assertIs(runtime.zip_runtime, zip_runtime)

    def test_shadow_without_client_returns_zip(self):
        zip_runtime = ZipRuntime()
        self.assertIs(
            select_curriculum_runtime_v27(zip_runtime, None, source="supabase_shadow"),
            zip_runtime,
        )

    def test_shadow_mismatch_never_changes_zip_visible_data(self):
        zip_runtime = ZipRuntime(True)
        runtime = select_curriculum_runtime_v27(
            zip_runtime, fixture(), source="supabase_shadow"
        )
        route = runtime.resolve_route("G6")
        observation = runtime.shadow_observation(route.profile_id)
        self.assertIsNotNone(observation)
        self.assertFalse(observation.matched)
        self.assertEqual(runtime.load_standard_skills(route)[0].focus, "Changed")

    def test_shadow_db_error_never_breaks_zip_route(self):
        release = "CURRICULUM_V27_EA0E6735"
        broken_client = Client(
            {
                "curriculum_releases": [
                    {"release_id": release, "status": "staged", "is_active": False}
                ]
            }
        )
        runtime = select_curriculum_runtime_v27(
            ZipRuntime(), broken_client, source="supabase_shadow"
        )
        route = runtime.resolve_route("G6")
        observation = runtime.shadow_observation(route.profile_id)
        self.assertEqual(route.grade, "G6")
        self.assertIsNotNone(observation)
        self.assertFalse(observation.matched)
        self.assertIsNotNone(observation.error)

    def test_shadow_skips_non_canary_route(self):
        runtime = select_curriculum_runtime_v27(
            G7ZipRuntime(), fixture(), source="supabase_shadow"
        )
        route = runtime.resolve_route("G7")
        self.assertEqual(route.grade, "G7")
        self.assertEqual(runtime.shadow_observations(), {})


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

    def test_shadow_detects_skill_order_mismatch(self):
        report = compare_curriculum_route_v27(
            TwoSkillZipRuntime(), ReverseTwoSkillDbRuntime(), "G6"
        )
        self.assertFalse(report.matched)
        self.assertIn("skill order mismatch", report.differences)


if __name__ == "__main__":
    unittest.main()