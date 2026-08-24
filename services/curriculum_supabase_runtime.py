from __future__ import annotations

from typing import Any, Iterable, Mapping

from .curriculum_master_runtime import (
    CurriculumDataError,
    CurriculumMasterRuntime,
    MicroSkill,
    RouteContext,
    SkillContext,
    StandardSkill,
)

DEFAULT_RELEASE_ID = "CURRICULUM_V27_EA0E6735"


class SupabaseCurriculumRuntime:
    """Read-only Curriculum Master v2.7 adapter backed by Supabase.

    The adapter never creates a Supabase client and never reads credentials.
    A table-capable client must be injected by the caller. Live DB cutover should
    use the default allowed statuses (verified/active); shadow reads may opt into
    staged releases explicitly.

    Route-scoped curriculum payloads are cached for the lifetime of this runtime
    instance.  Learning-map rendering asks for many skill contexts in one pass;
    without these caches each context would re-fetch the same skills, micro
    skills and prerequisite edges over REST, creating hundreds of production
    requests for a single grade.
    """

    def __init__(
        self,
        client: Any,
        *,
        release_id: str = DEFAULT_RELEASE_ID,
        allowed_statuses: Iterable[str] = ("verified", "active"),
    ) -> None:
        if client is None or not callable(getattr(client, "table", None)):
            raise ValueError("a table-capable Supabase client is required")
        self.client = client
        self.release_id = str(release_id)
        self.allowed_statuses = frozenset(str(x) for x in allowed_statuses)
        self._release_cache: Mapping[str, Any] | None = None
        self._profile_cache: dict[str, Mapping[str, Any]] = {}
        self._skills_cache: dict[str, tuple[StandardSkill, ...]] = {}
        self._micro_skills_cache: dict[str, tuple[MicroSkill, ...]] = {}
        self._skill_edges_cache: dict[str, tuple[tuple[str, str, str], ...]] = {}
        self._skill_context_cache: dict[tuple[str, str], SkillContext] = {}

    def _rows(
        self,
        table: str,
        *,
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query = self.client.table(table).select("*")
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        response = query.execute()
        return [dict(row) for row in (getattr(response, "data", None) or [])]

    def _release(self) -> Mapping[str, Any]:
        if self._release_cache is None:
            rows = self._rows(
                "curriculum_releases",
                filters={"release_id": self.release_id},
            )
            if len(rows) != 1:
                raise CurriculumDataError(
                    f"curriculum release not found: {self.release_id}"
                )
            row = rows[0]
            status = str(row.get("status") or "")
            if status not in self.allowed_statuses:
                raise CurriculumDataError(
                    f"curriculum release {self.release_id} status {status!r} is not allowed"
                )
            self._release_cache = row
        return self._release_cache

    @staticmethod
    def _route_parts(
        grade: Any,
        *,
        education_system: Any = None,
        track: Any = None,
    ) -> tuple[str, str, str | None, str]:
        g = CurriculumMasterRuntime.normalize_grade(grade)
        system = CurriculumMasterRuntime.normalize_system(education_system, g)
        t = CurriculumMasterRuntime.normalize_track(track, grade=g, system=system)
        profile_id = f"CURRICULUM_V27:{system}:{g}:{t or 'COMMON'}"
        return g, system, t, profile_id

    def _profile(self, profile_id: str) -> Mapping[str, Any]:
        self._release()
        if profile_id not in self._profile_cache:
            rows = self._rows(
                "curriculum_profiles",
                filters={"release_id": self.release_id, "profile_id": profile_id},
            )
            if len(rows) != 1:
                raise CurriculumDataError(
                    f"curriculum profile not found: {profile_id}"
                )
            self._profile_cache[profile_id] = rows[0]
        return self._profile_cache[profile_id]

    def resolve_route(
        self,
        grade: Any,
        *,
        education_system: Any = None,
        track: Any = None,
    ) -> RouteContext:
        g, system, t, profile_id = self._route_parts(
            grade,
            education_system=education_system,
            track=track,
        )
        row = self._profile(profile_id)
        if str(row.get("grade")) != g or str(row.get("education_system")) != system:
            raise CurriculumDataError(
                f"curriculum profile metadata mismatch: {profile_id}"
            )
        db_track = row.get("track") or None
        if (db_track or None) != (t or None):
            raise CurriculumDataError(
                f"curriculum profile track mismatch: {profile_id}"
            )
        return RouteContext(system, g, t, str(row.get("pack_relpath") or ""))

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _ordered_rows(
        cls,
        rows: Iterable[Mapping[str, Any]],
        *,
        label: str,
        id_field: str,
    ) -> list[dict[str, Any]]:
        decorated: list[tuple[int, str, dict[str, Any]]] = []
        seen_orders: set[int] = set()
        for item in rows:
            row = dict(item)
            row_id = str(row.get(id_field) or "")
            order = cls._int(row.get("source_order"))
            if order <= 0:
                raise CurriculumDataError(
                    f"{label} source_order missing/invalid: {row_id or '<unknown>'}"
                )
            if order in seen_orders:
                raise CurriculumDataError(
                    f"duplicate {label} source_order {order}: {row_id or '<unknown>'}"
                )
            seen_orders.add(order)
            decorated.append((order, row_id, row))
        decorated.sort(key=lambda value: (value[0], value[1]))
        return [row for _, _, row in decorated]

    def load_standard_skills(
        self,
        route: RouteContext,
    ) -> tuple[StandardSkill, ...]:
        profile_id = route.profile_id
        cached = self._skills_cache.get(profile_id)
        if cached is not None:
            return cached

        rows = self._ordered_rows(
            self._rows(
                "curriculum_skills",
                filters={"release_id": self.release_id, "profile_id": profile_id},
            ),
            label="skill",
            id_field="skill_id",
        )
        result = tuple(
            StandardSkill(
                str(r.get("skill_id") or ""),
                str(r.get("official_code_raw") or ""),
                str(r.get("main_unit") or ""),
                str(r.get("subunit") or ""),
                str(r.get("skill_name") or ""),
                str(r.get("focus") or ""),
                self._int(r.get("difficulty")),
            )
            for r in rows
        )
        self._skills_cache[profile_id] = result
        return result

    def load_micro_skills(
        self,
        route: RouteContext,
    ) -> tuple[MicroSkill, ...]:
        profile_id = route.profile_id
        cached = self._micro_skills_cache.get(profile_id)
        if cached is not None:
            return cached

        rows = self._ordered_rows(
            self._rows(
                "curriculum_micro_skills",
                filters={"release_id": self.release_id, "profile_id": profile_id},
            ),
            label="micro skill",
            id_field="micro_skill_id",
        )
        parents = {
            skill.skill_id: skill for skill in self.load_standard_skills(route)
        }
        result: list[MicroSkill] = []
        for r in rows:
            parent_id = str(r.get("parent_skill_id") or "")
            parent = parents.get(parent_id)
            if parent is None:
                raise CurriculumDataError(
                    f"micro skill parent not found in route {profile_id}: {parent_id}"
                )
            result.append(
                MicroSkill(
                    str(r.get("micro_skill_id") or ""),
                    parent_id,
                    str(r.get("official_code_raw") or ""),
                    parent.main_unit,
                    parent.subunit,
                    str(r.get("skill_name") or ""),
                    str(r.get("question_type") or ""),
                    str(r.get("focus") or ""),
                    str(r.get("item_pattern") or ""),
                    str(r.get("common_error") or ""),
                    self._int(r.get("difficulty")),
                )
            )
        cached_result = tuple(result)
        self._micro_skills_cache[profile_id] = cached_result
        return cached_result

    def load_scope_rules(self, route: RouteContext) -> str:
        return str(self._profile(route.profile_id).get("scope_rules") or "")

    def list_main_units(self, route: RouteContext) -> list[str]:
        return list(
            dict.fromkeys(
                x.main_unit
                for x in self.load_standard_skills(route)
                if x.main_unit
            )
        )

    def list_subunits(
        self,
        route: RouteContext,
        main_units: Iterable[str] | None = None,
    ) -> list[str]:
        allowed = set(main_units or ())
        return list(
            dict.fromkeys(
                x.subunit
                for x in self.load_standard_skills(route)
                if x.subunit and (not allowed or x.main_unit in allowed)
            )
        )

    def skills_for_selection(
        self,
        route: RouteContext,
        *,
        main_units: Iterable[str] | None = None,
        subunits: Iterable[str] | None = None,
        max_difficulty: int | None = None,
    ) -> tuple[StandardSkill, ...]:
        mus, sus = set(main_units or ()), set(subunits or ())
        return tuple(
            x
            for x in self.load_standard_skills(route)
            if (not mus or x.main_unit in mus)
            and (not sus or x.subunit in sus)
            and (max_difficulty is None or x.difficulty <= max_difficulty)
        )

    def load_skill_edges(
        self,
        route: RouteContext,
    ) -> tuple[tuple[str, str, str], ...]:
        profile_id = route.profile_id
        cached = self._skill_edges_cache.get(profile_id)
        if cached is not None:
            return cached

        skill_ids = {x.skill_id for x in self.load_standard_skills(route)}
        if not skill_ids:
            self._skill_edges_cache[profile_id] = ()
            return ()

        query = (
            self.client.table("curriculum_skill_edges")
            .select("*")
            .eq("release_id", self.release_id)
        )
        in_filter = getattr(query, "in_", None)
        if callable(in_filter):
            response = in_filter("skill_id", sorted(skill_ids)).execute()
            rows = [
                dict(row)
                for row in (getattr(response, "data", None) or [])
            ]
        else:
            rows = self._rows(
                "curriculum_skill_edges",
                filters={"release_id": self.release_id},
            )
        result = tuple(
            sorted(
                {
                    (
                        str(r.get("skill_id") or ""),
                        str(r.get("related_skill_id") or ""),
                        str(r.get("edge_type") or ""),
                    )
                    for r in rows
                    if str(r.get("skill_id") or "") in skill_ids
                }
            )
        )
        self._skill_edges_cache[profile_id] = result
        return result

    def get_skill_context(
        self,
        route: RouteContext,
        skill_id: str,
    ) -> SkillContext:
        cache_key = (route.profile_id, str(skill_id))
        cached = self._skill_context_cache.get(cache_key)
        if cached is not None:
            return cached

        skill = next(
            (
                x
                for x in self.load_standard_skills(route)
                if x.skill_id == skill_id
            ),
            None,
        )
        if skill is None:
            raise KeyError(skill_id)
        micro = tuple(
            x
            for x in self.load_micro_skills(route)
            if x.parent_skill_id == skill_id
        )
        edges = self.load_skill_edges(route)
        prerequisites = tuple(
            sorted(
                {
                    related
                    for source, related, kind in edges
                    if source == skill_id and kind == "prerequisite"
                }
            )
        )
        successors = tuple(
            sorted(
                {
                    related
                    for source, related, kind in edges
                    if source == skill_id and kind == "successor"
                }
            )
        )
        result = SkillContext(
            route,
            skill,
            micro,
            prerequisites,
            successors,
            self.load_scope_rules(route),
        )
        self._skill_context_cache[cache_key] = result
        return result

    def build_prompt_context(
        self,
        route: RouteContext,
        skill_ids: Iterable[str],
    ) -> str:
        lines = [
            f"教育路徑：{route.education_system}",
            f"年級：{route.grade}",
            f"Track：{route.track or 'COMMON'}",
            "以下 canonical Skill 為唯一課程依據：",
        ]
        for sid in skill_ids:
            ctx = self.get_skill_context(route, sid)
            lines.append(
                f"- {sid}｜{ctx.skill.skill_name}｜{ctx.skill.focus}｜"
                f"難度{ctx.skill.difficulty}"
            )
            for micro in ctx.micro_skills:
                lines.append(
                    f"  - {micro.micro_skill_id}｜{micro.question_type}｜"
                    f"{micro.focus}｜常見錯因：{micro.common_error}"
                )
        lines.append("\n【不可超出以下範圍】\n" + self.load_scope_rules(route))
        return "\n".join(lines)

    def validate(self) -> Mapping[str, Any]:
        release = self._release()
        return {
            "release_gate": "PASS",
            "release_id": self.release_id,
            "release_status": str(release.get("status") or ""),
            "is_active": bool(release.get("is_active")),
            "source": "supabase",
        }
