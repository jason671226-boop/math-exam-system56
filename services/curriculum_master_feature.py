from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Callable

from .curriculum_master_runtime import CurriculumMasterRuntime
from .curriculum_shadow_runtime_v27 import ShadowObservationV27
from .curriculum_source_v27 import (
    SOURCE_SHADOW,
    curriculum_source_v27,
    select_curriculum_runtime_v27,
)

ENV_FLAG = "CURRICULUM_MASTER_V27_ENABLED"
_SHADOW_RUNTIME_CACHE: dict[int, tuple[Any, Any]] = {}


def curriculum_master_v27_enabled() -> bool:
    """Whether the v2.7 curriculum layer is enabled.

    Production cutover defaults this feature on.  Rollback remains explicit and
    deterministic: setting ``CURRICULUM_MASTER_V27_ENABLED=0`` returns the
    legacy learning-map path, while the source selector itself can independently
    fall back to the validated local v2.7 runtime.
    """
    return os.getenv(ENV_FLAG, "1").strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def curriculum_master_v27() -> CurriculumMasterRuntime:
    """Return the validated local runtime used as the production fallback."""
    runtime = CurriculumMasterRuntime()
    if runtime.validate().get("release_gate") != "PASS":
        raise RuntimeError("Curriculum Master v2.7 release gate is not PASS")
    return runtime


def _session_supabase_client() -> Any | None:
    """Reuse the app's already-authenticated client without reading credentials."""
    try:
        import streamlit as st

        return st.session_state.get("private_beta_auth_client")
    except Exception:
        return None


def curriculum_master_v27_runtime(
    supabase_client: Any | None = None,
    *,
    shadow_report_sink: Callable[[ShadowObservationV27], None] | None = None,
) -> Any:
    """Return the user-visible v2.7 runtime.

    Default source mode is ``auto``: signed-in sessions use Supabase only after
    the release is active and the activation gate passes; trial/anonymous or
    degraded sessions keep using the validated local v2.7 release.  Explicit
    shadow mode stays ZIP-authoritative and is cached per authenticated client.
    """
    source = curriculum_source_v27()
    client = supabase_client if supabase_client is not None else _session_supabase_client()

    if source == SOURCE_SHADOW and client is not None and shadow_report_sink is None:
        cache_key = id(client)
        cached = _SHADOW_RUNTIME_CACHE.get(cache_key)
        if cached is not None and cached[0] is client:
            return cached[1]
        runtime = select_curriculum_runtime_v27(
            curriculum_master_v27(),
            client,
            source=source,
        )
        _SHADOW_RUNTIME_CACHE[cache_key] = (client, runtime)
        return runtime

    return select_curriculum_runtime_v27(
        curriculum_master_v27(),
        client,
        source=source,
        shadow_report_sink=shadow_report_sink,
    )
