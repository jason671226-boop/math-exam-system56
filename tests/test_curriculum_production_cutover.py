from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.curriculum_source_v27 import (
    SOURCE_AUTO,
    curriculum_source_v27,
    select_curriculum_runtime_v27,
)
from services.curriculum_supabase_runtime import SupabaseCurriculumRuntime
from tests.test_curriculum_supabase_runtime import ZipRuntime, fixture


class CurriculumProductionCutoverTests(unittest.TestCase):
    def test_default_source_is_auto(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(curriculum_source_v27(), SOURCE_AUTO)

    def test_auto_inactive_release_keeps_zip(self):
        zip_runtime = ZipRuntime()
        selected = select_curriculum_runtime_v27(
            zip_runtime,
            fixture("verified", False, "FAIL"),
            source="auto",
        )
        self.assertIs(selected, zip_runtime)

    def test_auto_active_pass_uses_supabase(self):
        zip_runtime = ZipRuntime()
        selected = select_curriculum_runtime_v27(
            zip_runtime,
            fixture("active", True, "PASS"),
            source="auto",
        )
        self.assertIsInstance(selected, SupabaseCurriculumRuntime)
        self.assertEqual(selected.validate()["source"], "supabase")
        self.assertTrue(selected.validate()["is_active"])

    def test_auto_missing_client_keeps_zip(self):
        zip_runtime = ZipRuntime()
        self.assertIs(
            select_curriculum_runtime_v27(zip_runtime, None, source="auto"),
            zip_runtime,
        )

    def test_auto_broken_db_keeps_zip(self):
        class BrokenClient:
            def table(self, name):
                raise RuntimeError("database unavailable")

        zip_runtime = ZipRuntime()
        self.assertIs(
            select_curriculum_runtime_v27(zip_runtime, BrokenClient(), source="auto"),
            zip_runtime,
        )


if __name__ == "__main__":
    unittest.main()
