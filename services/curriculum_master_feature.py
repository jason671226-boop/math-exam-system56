from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Callable

from .curriculum_master_runtime import CurriculumMasterRuntime
from .curriculum_shadow_runtime_v27 import ShadowObservationV27
from .curriculum_source_v27 import curriculum_source_v27, select_curriculum_runtime_v27

ENV_FLAG = "CURRICULUM_MASTER_V27_ENABLED"


def curriculum_master_v27_enabled() -> bool:
    return os.getenv(ENV_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def curriculum_master_v27() -> CurriculumMasterRuntime:
    """Return the validated ZIP runtime. Existing callers keep this behavior."""
    runtime = CurriculumMasterRuntime()
    if runtime.validate().get("release_gate") != "PASS":
        raise RuntimeError("Curriculum Master v2.7 release gate is not PASS")
    return runtime


def curriculum_master_v27_runtime(
    supabase_client: Any | None = None,
    *,
    shadow_report_sink: Callable[[ShadowObservationV27], None] | None = None,
) -> Any:
    """Return the user-visible runtime selected by CURRICULUM_MASTER_V27_SOURCE.

    Default is ZIP. Shadow mode remains ZIP-authoritative while optionally
    running read-only Supabase parity checks. Supabase becomes user-visible only
    after the explicit active + activation-gate cutover.
    """
    return select_curriculum_runtime_v27(
        curriculum_master_v27(),
        supabase_client,
        source=curriculum_source_v27(),
        shadow_report_sink=shadow_report_sink,
    )
