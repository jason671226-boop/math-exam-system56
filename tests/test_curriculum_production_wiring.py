from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.curriculum_master_runtime import (
    CurriculumDataError,
    MicroSkill,
    RouteContext,
    StandardSkill,
)
from services.master_curriculum_loader import load_g8_master_catalog, load_master_catalog


class _FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.skills = (
            StandardSkill(
                "FAKE-SKILL-01",
                "n-FAKE-1",
                "測試主單元",
                "測試次單元",
                "Runtime canonical skill",
                "runtime focus",
                2,
            ),
        )
        self.micros = (
            MicroSkill(
                "FAKE-MICRO-01",
                "FAKE-SKILL-01",
                "n-FAKE-1",
                "測試主單元",
                "測試次單元",
                "Runtime canonical skill",
                "測試題型",
                "runtime micro focus",
                "pattern",
                "error",
                2,
            ),
        )

    def resolve_route(self, grade, **kwargs):
        self.calls.append((str(grade), dict(kwargs)))
        g = str(grade)
        system = kwargs.get("education_system") or (
            "PREHIGH" if g in {f"G{i}" for i in range(1, 10)} else "GENERAL"
        )
        track = kwargs.get("track")
        return RouteContext(system, g, track, f"fake/{g}")

    def load_standard_skills(self, route):
        return self.skills

    def load_micro_skills(self, route):
        return self.micros


class ProductionCurriculumWiringTests(unittest.TestCase):
    def _feature_patches(self, runtime):
        return (
            patch(
                "services.curriculum_master_feature.curriculum_master_v27_enabled",
                return_value=True,
            ),
            patch(
                "services.curriculum_master_feature.curriculum_master_v27_runtime",
                return_value=runtime,
            ),
        )

    def test_regular_self_built_catalog_reads_canonical_data_through_runtime(self):
        runtime = _FakeRuntime()
        enabled, selected = self._feature_patches(runtime)
        with enabled, selected:
            catalog = load_master_catalog(6, "康軒")

        self.assertEqual(runtime.calls[0], ("G6", {}))
        self.assertEqual(tuple(skill.skill_id for skill in catalog.skills), ("FAKE-SKILL-01",))
        self.assertEqual(catalog.skills[0].micro_skills[0].micro_skill_id, "FAKE-MICRO-01")

    def test_high_school_version_routes_to_correct_runtime_profile(self):
        runtime = _FakeRuntime()
        enabled, selected = self._feature_patches(runtime)
        with enabled, selected:
            load_master_catalog(10, "數學 B")
            load_master_catalog(11, "數學 A")
            load_master_catalog(12, "數學乙")

        self.assertEqual(
            runtime.calls,
            [
                ("G10", {"education_system": "TECHNICAL", "track": "B"}),
                ("G11", {"education_system": "GENERAL", "track": "A"}),
                ("G12", {"education_system": "GENERAL", "track": "乙"}),
            ],
        )

    def test_g8_publisher_crosswalk_uses_runtime_canonical_pool(self):
        runtime = _FakeRuntime()
        enabled, selected = self._feature_patches(runtime)
        with enabled, selected:
            catalog = load_g8_master_catalog()

        self.assertEqual(runtime.calls[0], ("G8", {}))
        self.assertTrue(catalog.publisher_units)
        self.assertEqual(tuple(skill.skill_id for skill in catalog.skills), ("FAKE-SKILL-01",))

    def test_feature_off_preserves_local_rollback_loader(self):
        runtime = MagicMock()
        with (
            patch(
                "services.curriculum_master_feature.curriculum_master_v27_enabled",
                return_value=False,
            ),
            patch("services.curriculum_master_feature.curriculum_master_v27_runtime", runtime),
        ):
            catalog = load_master_catalog(6, "康軒")

        runtime.assert_not_called()
        self.assertTrue(catalog.skills)
        self.assertNotEqual(catalog.skills[0].skill_id, "FAKE-SKILL-01")

    def test_runtime_failure_does_not_silently_bypass_explicit_supabase_fail_closed(self):
        with (
            patch(
                "services.curriculum_master_feature.curriculum_master_v27_enabled",
                return_value=True,
            ),
            patch(
                "services.curriculum_master_feature.curriculum_master_v27_runtime",
                side_effect=CurriculumDataError("activation gate closed"),
            ),
        ):
            with self.assertRaisesRegex(CurriculumDataError, "activation gate closed"):
                load_master_catalog(6, "康軒")


if __name__ == "__main__":
    unittest.main()
