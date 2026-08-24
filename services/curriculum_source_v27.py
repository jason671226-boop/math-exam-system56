from __future__ import annotations

import os
from typing import Any, Callable

from .curriculum_master_runtime import CurriculumDataError, CurriculumMasterRuntime
from .curriculum_shadow_runtime_v27 import ShadowCurriculumRuntimeV27, ShadowObservationV27
from .curriculum_shadow_v27 import (
    CurriculumShadowReportV27,
    compare_curriculum_shadow_v27,
)
from .curriculum_supabase_runtime import DEFAULT_RELEASE_ID, SupabaseCurriculumRuntime

SOURCE_ENV = "CURRICULUM_MASTER_V27_SOURCE"
SOURCE_AUTO = "auto"
SOURCE_ZIP = "zip"
SOURCE_SHADOW = "supabase_shadow"
SOURCE_SUPABASE = "supabase"
VALID_SOURCES = frozenset({SOURCE_AUTO, SOURCE_ZIP, SOURCE_SHADOW, SOURCE_SUPABASE})
ACTIVATION_GATE = "activation_gate"


def curriculum_source_v27() -> str:
    """Return the requested curriculum source mode.

    Production defaults to ``auto``.  Auto mode is deliberately conservative:
    it uses Supabase only when an authenticated client is available *and* the
    release is active with ``activation_gate=PASS``.  Otherwise it returns the
    already-validated local v2.7 runtime.  Explicit ``supabase`` remains
    fail-closed for diagnostics and administrative verification.
    """
    value = os.getenv(SOURCE_ENV, SOURCE_AUTO).strip().lower() or SOURCE_AUTO
    if value not in VALID_SOURCES:
        raise ValueError(f"invalid {SOURCE_ENV}: {value}")
    return value


def _activation_gate_passed(client: Any, release_id: str) -> bool:
    rows = (
        client.table("curriculum_release_checks")
        .select("check_name,status")
        .eq("release_id", release_id)
        .eq("check_name", ACTIVATION_GATE)
        .execute()
        .data
        or []
    )
    return len(rows) == 1 and str(rows[0].get("status") or "") == "PASS"


def _active_supabase_runtime(client: Any, release_id: str) -> SupabaseCurriculumRuntime:
    runtime = SupabaseCurriculumRuntime(
        client,
        release_id=release_id,
        allowed_statuses=("active",),
    )
    state = runtime.validate()
    if state.get("release_status") != "active" or not state.get("is_active"):
        raise CurriculumDataError(
            f"curriculum release {release_id} is not an active cutover release"
        )
    if not _activation_gate_passed(client, release_id):
        raise CurriculumDataError(
            f"curriculum release {release_id} activation gate is not PASS"
        )
    return runtime


def select_curriculum_runtime_v27(
    zip_runtime: CurriculumMasterRuntime,
    supabase_client: Any | None,
    *,
    source: str | None = None,
    release_id: str = DEFAULT_RELEASE_ID,
    shadow_report_sink: Callable[[ShadowObservationV27], None] | None = None,
) -> Any:
    """Return the user-visible runtime for the selected source mode.

    ``auto`` is the production default and is rollback-safe: an authenticated
    active release with a passing activation gate uses Supabase; otherwise ZIP
    stays user-visible.  ``supabase_shadow`` is ZIP-authoritative with read-only
    parity observation.  Explicit ``supabase`` is fail-closed and raises if any
    live-cutover requirement is missing.
    """
    mode = (source or curriculum_source_v27()).strip().lower()
    if mode not in VALID_SOURCES:
        raise ValueError(f"invalid curriculum source: {mode}")

    if mode == SOURCE_ZIP:
        return zip_runtime

    if mode == SOURCE_AUTO:
        if supabase_client is None:
            return zip_runtime
        try:
            return _active_supabase_runtime(supabase_client, release_id)
        except Exception:
            # Automatic production rollback: a DB/auth/network/gate problem must
            # not take down curriculum reads while the validated local release is
            # still bundled with the application.
            return zip_runtime

    if mode == SOURCE_SHADOW:
        if supabase_client is None:
            return zip_runtime
        try:
            return ShadowCurriculumRuntimeV27(
                zip_runtime,
                supabase_client,
                release_id=release_id,
                report_sink=shadow_report_sink,
            )
        except Exception:
            # Shadow observability must never take down ZIP-authoritative reads.
            return zip_runtime

    if supabase_client is None:
        raise ValueError("Supabase curriculum source requires an authenticated client")
    return _active_supabase_runtime(supabase_client, release_id)


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
