from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .curriculum_master_runtime import CurriculumMasterRuntime, RouteContext
from .curriculum_supabase_runtime import DEFAULT_RELEASE_ID, SupabaseCurriculumRuntime


@dataclass(frozen=True)
class CurriculumShadowReportV27:
    profile_id: str
    matched: bool
    zip_skill_count: int
    db_skill_count: int
    zip_micro_count: int
    db_micro_count: int
    zip_edge_count: int
    db_edge_count: int
    scope_rules_match: bool
    differences: tuple[str, ...]


def _object_map(items: Iterable[Any], id_field: str) -> dict[str, Mapping[str, Any]]:
    return {str(getattr(item, id_field)): asdict(item) for item in items}


def _diff_maps(
    label: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    limit: int,
) -> list[str]:
    out: list[str] = []
    for key in sorted(set(left) | set(right)):
        if key not in left:
            out.append(f"{label}: DB-only {key}")
        elif key not in right:
            out.append(f"{label}: ZIP-only {key}")
        elif left[key] != right[key]:
            fields = sorted(
                field
                for field in set(left[key]) | set(right[key])
                if left[key].get(field) != right[key].get(field)
            )
            out.append(f"{label}: field mismatch {key}: {','.join(fields)}")
        if len(out) >= limit:
            break
    return out


def _zip_edges(
    runtime: CurriculumMasterRuntime, route: RouteContext
) -> set[tuple[str, str, str]]:
    edges: set[tuple[str, str, str]] = set()
    for skill in runtime.load_standard_skills(route):
        ctx = runtime.get_skill_context(route, skill.skill_id)
        edges.update(
            (skill.skill_id, related, "prerequisite")
            for related in ctx.prerequisite_ids
        )
        edges.update(
            (skill.skill_id, related, "successor")
            for related in ctx.successor_ids
        )
    return edges


def compare_curriculum_route_v27(
    zip_runtime: CurriculumMasterRuntime,
    db_runtime: SupabaseCurriculumRuntime,
    grade: Any,
    *,
    education_system: Any = None,
    track: Any = None,
    difference_limit: int = 40,
) -> CurriculumShadowReportV27:
    zip_route = zip_runtime.resolve_route(
        grade, education_system=education_system, track=track
    )
    db_route = db_runtime.resolve_route(
        grade, education_system=education_system, track=track
    )
    differences: list[str] = []
    if zip_route.profile_id != db_route.profile_id:
        differences.append(
            f"profile mismatch ZIP={zip_route.profile_id} DB={db_route.profile_id}"
        )

    zip_skills = _object_map(zip_runtime.load_standard_skills(zip_route), "skill_id")
    db_skills = _object_map(db_runtime.load_standard_skills(db_route), "skill_id")
    differences.extend(
        _diff_maps(
            "skill",
            zip_skills,
            db_skills,
            limit=max(0, difference_limit - len(differences)),
        )
    )

    zip_micros = _object_map(
        zip_runtime.load_micro_skills(zip_route), "micro_skill_id"
    )
    db_micros = _object_map(db_runtime.load_micro_skills(db_route), "micro_skill_id")
    differences.extend(
        _diff_maps(
            "micro",
            zip_micros,
            db_micros,
            limit=max(0, difference_limit - len(differences)),
        )
    )

    zip_edges = _zip_edges(zip_runtime, zip_route)
    db_edges = set(db_runtime.load_skill_edges(db_route))
    for edge in sorted(zip_edges - db_edges):
        if len(differences) >= difference_limit:
            break
        differences.append(f"edge: ZIP-only {edge}")
    for edge in sorted(db_edges - zip_edges):
        if len(differences) >= difference_limit:
            break
        differences.append(f"edge: DB-only {edge}")

    scope_match = (
        zip_runtime.load_scope_rules(zip_route).strip()
        == db_runtime.load_scope_rules(db_route).strip()
    )
    if not scope_match and len(differences) < difference_limit:
        differences.append("scope_rules mismatch")

    return CurriculumShadowReportV27(
        profile_id=zip_route.profile_id,
        matched=not differences,
        zip_skill_count=len(zip_skills),
        db_skill_count=len(db_skills),
        zip_micro_count=len(zip_micros),
        db_micro_count=len(db_micros),
        zip_edge_count=len(zip_edges),
        db_edge_count=len(db_edges),
        scope_rules_match=scope_match,
        differences=tuple(differences),
    )


def compare_curriculum_shadow_v27(
    zip_runtime: CurriculumMasterRuntime,
    supabase_client: Any,
    grade: Any,
    *,
    education_system: Any = None,
    track: Any = None,
    release_id: str = DEFAULT_RELEASE_ID,
) -> CurriculumShadowReportV27:
    db_runtime = SupabaseCurriculumRuntime(
        supabase_client,
        release_id=release_id,
        allowed_statuses=("staged", "verified", "active"),
    )
    return compare_curriculum_route_v27(
        zip_runtime,
        db_runtime,
        grade,
        education_system=education_system,
        track=track,
    )
