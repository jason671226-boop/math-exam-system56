from __future__ import annotations

import os
from typing import Any

from .curriculum_master_runtime import CurriculumDataError, CurriculumMasterRuntime
from .curriculum_shadow_v27 import (
    CurriculumShadowReportV27,
    compare_curriculum_shadow_v27,
)
from .curriculum_supabase_runtime import DEFAULT_RELEASE_ID, SupabaseCurriculumRuntime

SOURCE_ENV = "CURRICULUM_MASTER_V27_SOURCE"
SOURCE_ZIP = "zip"
SOURCE_SHADOW = "supabase_shadow"
SOURCE_SUPABASE = "supabase"
VALID_SOURCES = frozenset({SOURCE_ZIP, SOURCE_SHADOW, SOURCE_SUPABASE})


def curriculum_source_v27() -> str:
    value = os.getenv(SOURCE_ENV, SOURCE_ZIP).strip().lower() or SOURCE_ZIP
    if value not in VALID_SOURCES:
        raise ValueError(f"invalid {SOURCE_ENV}: {value}")
    return value


def select_curriculum_runtime_v27(
    zip_runtime: CurriculumMasterRuntime,
    supabase_client: Any | None,
    *,
    source: str | None = None,
    release_id: str = DEFAULT_RELEASE_ID,
) -> Any:
    """Return the user-visible runtime for the selected source mode.

    `supabase_shadow` deliberately returns ZIP so shadow comparisons cannot
    alter user-visible curriculum. A true `supabase` cutover is fail-closed:
    the release must be status=active AND is_active=true.
    """
    mode = (source or curriculum_source_v27()).strip().lower()
    if mode not in VALID_SOURCES:
        raise ValueError(f"invalid curriculum source: {mode}")
    if mode in {SOURCE_ZIP, SOURCE_SHADOW}:
        return zip_runtime
    if supabase_client is None:
        raise ValueError("Supabase curriculum source requires an authenticated client")
    runtime = SupabaseCurriculumRuntime(
        supabase_client,
        release_id=release_id,
        allowed_statuses=("active",),
    )
    state = runtime.validate()
    if state.get("release_status") != "active" or not state.get("is_active"):
        raise CurriculumDataError(
            f"curriculum release {release_id} is not an active cutover release"
        )
    return runtime


def shadow_compare_route_v27(
    zip_runtime: CurriculumMasterRuntime,
    supabase_client: Any,
    grade: Any,
    *,
    education_system: Any = None,
    track: Any = None,
    release_id: str = DEFAULT_RELEASE_ID,
) -> CurriculumShadowReportV27:
    return compare_curriculum_shadow_v27(
        zip_runtime,
        supabase_client,
        grade,
        education_system=education_system,
        track=track,
        release_id=release_id,
    )
