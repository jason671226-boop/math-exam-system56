from __future__ import annotations
import os
from functools import lru_cache
from .curriculum_master_runtime import CurriculumMasterRuntime

ENV_FLAG="CURRICULUM_MASTER_V27_ENABLED"

def curriculum_master_v27_enabled() -> bool:
    return os.getenv(ENV_FLAG,"").strip().lower() in {"1","true","yes","on"}

@lru_cache(maxsize=1)
def curriculum_master_v27() -> CurriculumMasterRuntime:
    runtime=CurriculumMasterRuntime()
    if runtime.validate().get("release_gate")!="PASS":
        raise RuntimeError("Curriculum Master v2.7 release gate is not PASS")
    return runtime
