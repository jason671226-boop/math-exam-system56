from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.curriculum_catalog import SelectedExamSpec, build_generation_context


class CurriculumCatalogFeatureBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = SelectedExamSpec(
            grade=7,
            publisher="康軒",
            semester="上學期",
            main_units=("數與數線",),
            subunits=("數與數線 ＞ 整數與數線",),
            question_types=("基本觀念",),
            difficulty=("標準",),
            question_count=5,
        )

    def test_flag_off_keeps_legacy_context(self) -> None:
        with patch.dict(os.environ, {"CURRICULUM_MASTER_V27_ENABLED": "0"}, clear=False):
            context = build_generation_context(self.spec)
        self.assertIn("年級：G7", context)
        self.assertIn("出版社：康軒", context)
        self.assertIn("題數：5", context)
        self.assertNotIn("canonical context", context)

    def test_missing_v27_data_falls_back_to_legacy(self) -> None:
        with patch.dict(os.environ, {"CURRICULUM_MASTER_V27_ENABLED": "1"}, clear=False):
            context = build_generation_context(self.spec)
        self.assertIn("年級：G7", context)
        self.assertIn("題數：5", context)


if __name__ == "__main__":
    unittest.main()
