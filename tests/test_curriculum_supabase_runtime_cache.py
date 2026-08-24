import unittest
from collections import Counter

from services.curriculum_supabase_runtime import SupabaseCurriculumRuntime
from tests.test_curriculum_supabase_runtime import Client, fixture


class CountingClient(Client):
    def __init__(self, tables):
        super().__init__(tables)
        self.table_calls = Counter()

    def table(self, name):
        self.table_calls[name] += 1
        return super().table(name)


class SupabaseRuntimeCacheTests(unittest.TestCase):
    def test_repeated_skill_context_reads_are_route_cached(self):
        base = fixture("active", True, "PASS")
        client = CountingClient(base.tables)
        runtime = SupabaseCurriculumRuntime(client, allowed_statuses=("active",))
        route = runtime.resolve_route("G6")

        for _ in range(20):
            context = runtime.get_skill_context(route, "G06-A")
            self.assertEqual(context.skill.skill_id, "G06-A")

        self.assertEqual(client.table_calls["curriculum_releases"], 1)
        self.assertEqual(client.table_calls["curriculum_profiles"], 1)
        self.assertEqual(client.table_calls["curriculum_skills"], 1)
        self.assertEqual(client.table_calls["curriculum_micro_skills"], 1)
        self.assertEqual(client.table_calls["curriculum_skill_edges"], 1)
        self.assertEqual(sum(client.table_calls.values()), 5)


if __name__ == "__main__":
    unittest.main()
