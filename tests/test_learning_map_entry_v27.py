from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import learning_map


class LearningMapEntryV27Tests(unittest.TestCase):
    def setUp(self):
        self.profile = {"grade": "7年級", "version": "康軒版"}

    def test_flag_off_delegates_to_legacy(self):
        with patch.dict(os.environ, {"CURRICULUM_MASTER_V27_ENABLED": "0"}, clear=False):
            with patch.object(learning_map._legacy, "render_learning_map") as legacy:
                learning_map.render_learning_map(self.profile, False, None)
                legacy.assert_called_once_with(self.profile, False, None)

    def test_v27_runtime_failure_falls_back_to_legacy(self):
        with patch.dict(os.environ, {"CURRICULUM_MASTER_V27_ENABLED": "1"}, clear=False):
            with patch(
                "services.curriculum_master_feature.curriculum_master_v27_runtime",
                side_effect=RuntimeError("shadow unavailable"),
            ):
                with patch.object(learning_map._legacy, "render_learning_map") as legacy:
                    learning_map.render_learning_map(self.profile, False, None)
                    legacy.assert_called_once_with(self.profile, False, None)


if __name__ == "__main__":
    unittest.main()
