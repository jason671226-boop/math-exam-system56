import unittest

from tests.test_curriculum_master_runtime import make_fixture
from services.curriculum_master_runtime import CurriculumMasterRuntime
from services.curriculum_catalog_v27 import (
    get_curriculum_path_v27,
    main_unit_names_v27,
    subunit_labels_v27,
    build_exam_generation_context_v27,
)


class CatalogV27Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = make_fixture()
        self.runtime = CurriculumMasterRuntime(self.fixture)

    def tearDown(self):
        from pathlib import Path
        Path(self.fixture).unlink(missing_ok=True)

    def test_generation_context_uses_canonical_skill(self):
        path = get_curriculum_path_v27(self.runtime, "G9")
        unit = main_unit_names_v27(path)[0]
        sub = subunit_labels_v27(path, [unit])[0]
        selection, context = build_exam_generation_context_v27(
            self.runtime,
            path,
            main_units=[unit],
            subunit_labels=[sub],
            difficulty=["標準"],
            question_count=5,
        )
        self.assertIn(selection.skill_ids[0], context)
        self.assertIn("canonical Skill", context)


if __name__ == "__main__":
    unittest.main()
