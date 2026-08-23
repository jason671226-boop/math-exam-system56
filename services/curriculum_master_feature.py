from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from .curriculum_master_runtime import CurriculumMasterRuntime
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


def curriculum_master_v27_runtime(supabase_client: Any | None = None) -> Any:
    """Return the user-visible runtime selected by CURRICULUM_MASTER_V27_SOURCE.

    Default is ZIP. Shadow mode also returns ZIP by design. Supabase becomes
    user-visible only when the selected release is verified/active.
    """
    return select_curriculum_runtime_v27(
        curriculum_master_v27(),
        supabase_client,
        source=curriculum_source_v27(),
    )
