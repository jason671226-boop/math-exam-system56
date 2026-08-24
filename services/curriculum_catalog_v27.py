from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .curriculum_master_bridge import (
    ExamSelectionV27,
    build_exam_selection,
    build_generation_context_v27,
)
from .curriculum_master_runtime import CurriculumMasterRuntime, RouteContext

DIFFICULTIES = ("基礎", "標準", "進階", "挑戰")


@dataclass(frozen=True)
class CurriculumSubunitV27:
    name: str
    skill_ids: tuple[str, ...]
    question_types: tuple[str, ...]


@dataclass(frozen=True)
class CurriculumUnitV27:
    name: str
    subunits: tuple[CurriculumSubunitV27, ...]


@dataclass(frozen=True)
class CurriculumPathV27:
    route: RouteContext
    units: tuple[CurriculumUnitV27, ...]
    source: str = "MathAI Curriculum Master v2.7"


def get_curriculum_path_v27(
    runtime: CurriculumMasterRuntime,
    grade: Any,
    *,
    education_system: Any = None,
    track: Any = None,
) -> CurriculumPathV27:
    route = runtime.resolve_route(
        grade,
        education_system=education_system,
        track=track,
    )
    skills = runtime.load_standard_skills(route)
    micros = runtime.load_micro_skills(route)
    micros_by_parent: dict[str, list[Any]] = {}
    for micro in micros:
        micros_by_parent.setdefault(micro.parent_skill_id, []).append(micro)

    grouped: dict[str, dict[str, list[Any]]] = {}
    for skill in skills:
        grouped.setdefault(skill.main_unit, {}).setdefault(skill.subunit, []).append(skill)

    units = []
    for main_unit, subgroups in grouped.items():
        subunits = []
        for subunit, subskills in subgroups.items():
            ids = tuple(skill.skill_id for skill in subskills)
            qtypes = []
            for skill in subskills:
                for micro in micros_by_parent.get(skill.skill_id, ()):
                    if micro.question_type and micro.question_type not in qtypes:
                        qtypes.append(micro.question_type)
            subunits.append(CurriculumSubunitV27(subunit, ids, tuple(qtypes)))
        units.append(CurriculumUnitV27(main_unit, tuple(subunits)))
    return CurriculumPathV27(route, tuple(units))


def main_unit_names_v27(path: CurriculumPathV27) -> list[str]:
    return [unit.name for unit in path.units]


def subunit_labels_v27(path: CurriculumPathV27, selected_units: Iterable[str]) -> list[str]:
    allowed = set(selected_units)
    return [
        f"{unit.name} ＞ {subunit.name}"
        for unit in path.units
        if unit.name in allowed
        for subunit in unit.subunits
    ]


def question_type_labels_v27(path: CurriculumPathV27, selected_subunits: Iterable[str]) -> list[str]:
    allowed = set(selected_subunits)
    result = []
    for unit in path.units:
        for subunit in unit.subunits:
            prefix = f"{unit.name} ＞ {subunit.name}"
            if prefix not in allowed:
                continue
            for qtype in subunit.question_types:
                label = f"{prefix} ＞ {qtype}"
                if label not in result:
                    result.append(label)
    return result


def build_exam_generation_context_v27(
    runtime: CurriculumMasterRuntime,
    path: CurriculumPathV27,
    *,
    main_units: Iterable[str],
    subunit_labels: Iterable[str],
    difficulty: Iterable[str],
    question_count: int,
) -> tuple[ExamSelectionV27, str]:
    subunits = tuple(label.split("＞", 1)[-1].strip() for label in subunit_labels)
    selection = build_exam_selection(
        runtime,
        path.route,
        main_units=tuple(main_units),
        subunits=subunits,
        difficulty=tuple(difficulty),
        question_count=question_count,
    )
    return selection, build_generation_context_v27(runtime, selection)
