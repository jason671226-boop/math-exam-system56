import os
import unittest
from unittest.mock import patch

from services.curriculum_master_feature import curriculum_master_v27_enabled


class FeatureTests(unittest.TestCase):
    def test_flag_on_by_default_for_production_cutover(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(curriculum_master_v27_enabled())

    def test_explicit_flag_off_still_rolls_back(self):
        with patch.dict(os.environ, {"CURRICULUM_MASTER_V27_ENABLED": "0"}, clear=False):
            self.assertFalse(curriculum_master_v27_enabled())


if __name__ == "__main__":
    unittest.main()
