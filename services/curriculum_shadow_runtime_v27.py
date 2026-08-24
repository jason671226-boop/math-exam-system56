from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .curriculum_master_runtime import CurriculumMasterRuntime, RouteContext
from .curriculum_shadow_v27 import (
    CurriculumShadowReportV27,
    compare_curriculum_route_v27,
)
from .curriculum_supabase_runtime import DEFAULT_RELEASE_ID, SupabaseCurriculumRuntime

CANARY_PROFILE_IDS = frozenset(
    {
        "CURRICULUM_V27:PREHIGH:G6:COMMON",
        "CURRICULUM_V27:PREHIGH:G8:COMMON",
    }
)


class _ShadowSupabaseCurriculumRuntime(SupabaseCurriculumRuntime):
    """Route-scoped edge reads avoid the Data API's default 1,000-row cap."""

    def load_skill_edges(self, route: RouteContext) -> tuple[tuple[str, str, str], ...]:
        skill_ids = {x.skill_id for x in self.load_standard_skills(route)}
        if not skill_ids:
            return ()
        query = (
            self.client.table("curriculum_skill_edges")
            .select("*")
            .eq("release_id", self.release_id)
        )
        in_filter = getattr(query, "in_", None)
        if callable(in_filter):
            rows = in_filter("skill_id", sorted(skill_ids)).execute().data or []
        else:
            # Test/fallback clients without `in_` still preserve semantics.
            rows = self._rows(
                "curriculum_skill_edges",
                filters={"release_id": self.release_id},
            )
        edges = {
            (
                str(r.get("skill_id") or ""),
                str(r.get("related_skill_id") or ""),
                str(r.get("edge_type") or ""),
            )
            for r in rows
            if str(r.get("skill_id") or "") in skill_ids
        }
        return tuple(sorted(edges))


@dataclass(frozen=True)
class ShadowObservationV27:
    profile_id: str
    matched: bool
    report: CurriculumShadowReportV27 | None = None
    error: str | None = None


class ShadowCurriculumRuntimeV27:
    """ZIP-authoritative runtime with fail-open Supabase parity observation.

    All curriculum reads remain delegated to the validated ZIP runtime. For
    selected canary profiles, the first successful route resolution also runs
    a read-only ZIP↔Supabase comparison. Shadow failures are recorded but are
    never allowed to change user-visible curriculum behavior.
    """

    def __init__(
        self,
        zip_runtime: CurriculumMasterRuntime,
        supabase_client: Any,
        *,
        release_id: str = DEFAULT_RELEASE_ID,
        profile_ids: Iterable[str] = CANARY_PROFILE_IDS,
        report_sink: Callable[[ShadowObservationV27], None] | None = None,
    ) -> None:
        if zip_runtime is None:
            raise ValueError("zip_runtime is required")
        self.zip_runtime = zip_runtime
        self.release_id = str(release_id)
        self.profile_ids = frozenset(str(value) for value in profile_ids)
        self.report_sink = report_sink
        self.db_runtime = _ShadowSupabaseCurriculumRuntime(
            supabase_client,
            release_id=self.release_id,
            allowed_statuses=("staged", "verified", "active"),
        )
        self._observations: dict[str, ShadowObservationV27] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.zip_runtime, name)

    def resolve_route(
        self,
        grade: Any,
        *,
        education_system: Any = None,
        track: Any = None,
    ) -> RouteContext:
        route = self.zip_runtime.resolve_route(
            grade,
            education_system=education_system,
            track=track,
        )
        self._observe_route(route)
        return route

    def _observe_route(self, route: RouteContext) -> None:
        profile_id = route.profile_id
        if profile_id not in self.profile_ids or profile_id in self._observations:
            return
        try:
            report = compare_curriculum_route_v27(
                self.zip_runtime,
                self.db_runtime,
                route.grade,
                education_system=route.education_system,
                track=route.track,
            )
            observation = ShadowObservationV27(
                profile_id=profile_id,
                matched=report.matched,
                report=report,
            )
        except Exception as exc:
            observation = ShadowObservationV27(
                profile_id=profile_id,
                matched=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        self._observations[profile_id] = observation
        if self.report_sink is not None:
            try:
                self.report_sink(observation)
            except Exception:
                pass

    def shadow_observation(self, profile_id: str) -> ShadowObservationV27 | None:
        return self._observations.get(str(profile_id))

    def shadow_observations(self) -> Mapping[str, ShadowObservationV27]:
        return dict(self._observations)

    def validate(self) -> Mapping[str, Any]:
        state = dict(self.zip_runtime.validate())
        state["source"] = "zip"
        state["shadow_source"] = "supabase"
        state["shadow_release_id"] = self.release_id
        state["shadow_profiles"] = tuple(sorted(self.profile_ids))
        return state
