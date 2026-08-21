"""Normalized curriculum adapter for the self-built exam flow.

Legacy G5-G9 catalog behavior remains the default.  When Curriculum Master
v2.7 is explicitly enabled, generation context is augmented with canonical
Skill / micro-skill metadata without changing the current Streamlit UI.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, MutableMapping


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
APP_DIR = DATA_DIR.parent
SUPPORTED_GRADES = (5, 6, 7, 8, 9)
PUBLISHERS = ("康軒", "翰林", "南一")
SEMESTERS = ("上學期", "下學期")
DIFFICULTIES = ("基礎", "標準", "進階", "挑戰")


@dataclass(frozen=True)
class CurriculumSubunit:
    name: str
    question_types: tuple[str, ...]


@dataclass(frozen=True)
class CurriculumUnit:
    name: str
    subunits: tuple[CurriculumSubunit, ...]


@dataclass(frozen=True)
class CurriculumPath:
    grade: int
    publisher: str
    semester: str
    units: tuple[CurriculumUnit, ...]
    source: str


@dataclass(frozen=True)
class SelectedExamSpec:
    grade: int
    publisher: str
    semester: str
    main_units: tuple[str, ...]
    subunits: tuple[str, ...]
    question_types: tuple[str, ...]
    difficulty: tuple[str, ...]
    question_count: int

    def __post_init__(self) -> None:
        if self.grade not in SUPPORTED_GRADES:
            raise ValueError("unsupported grade")
        if self.publisher not in PUBLISHERS:
            raise ValueError("unsupported publisher")
        if self.semester not in SEMESTERS:
            raise ValueError("unsupported semester")
        if not self.main_units or not self.subunits:
            raise ValueError("main_units and subunits are required")
        if not self.difficulty or any(item not in DIFFICULTIES for item in self.difficulty):
            raise ValueError("invalid difficulty")
        if self.question_count <= 0:
            raise ValueError("question_count must be positive")

    @property
    def grade_label(self) -> str:
        return f"G{self.grade}"


def normalize_grade(value: Any) -> int:
    match = re.search(r"(\d+)", str(value or ""))
    grade = int(match.group(1)) if match else 0
    if grade not in SUPPORTED_GRADES:
        raise ValueError("grade must be G5-G9")
    return grade


def normalize_publisher(value: Any) -> str:
    publisher = str(value or "").strip().replace("版", "")
    if publisher not in PUBLISHERS:
        raise ValueError("publisher must be 康軒、翰林或南一")
    return publisher


def _load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _question_types(main_unit: str, subunit: str) -> tuple[str, ...]:
    text = main_unit + subunit
    result = ["基本觀念", "計算", "應用問題"]
    if any(word in text for word in ("統計", "資料", "機率", "圖表")):
        result.extend(("圖表／資料判讀", "素養題"))
    elif any(word in text for word in ("幾何", "圖形", "三角", "圓", "相似", "測量")):
        result.extend(("幾何推理", "素養題"))
    elif any(word in text for word in ("方程", "函數", "代數", "不等式")):
        result.extend(("變形題", "跨單元"))
    else:
        result.extend(("變形題", "素養題"))
    return tuple(dict.fromkeys(result))


def _standard_grade_paths(grade: int) -> dict[str, tuple[CurriculumUnit, ...]]:
    filename = "learning_map_g6_pilot.json" if grade == 6 else f"learning_map_g{grade}_baseline.json"
    raw = _load_json(DATA_DIR / filename)
    points = list(raw.get("knowledge_points", []))
    midpoint = max(1, (len(points) + 1) // 2)
    output: dict[str, tuple[CurriculumUnit, ...]] = {}
    for semester, semester_points in zip(SEMESTERS, (points[:midpoint], points[midpoint:])):
        grouped: dict[str, list[CurriculumSubunit]] = {}
        for point in semester_points:
            main = str(point.get("main_unit") or "").strip()
            sub = str(point.get("sub_unit") or "").strip()
            if main and sub:
                grouped.setdefault(main, []).append(
                    CurriculumSubunit(sub, _question_types(main, sub))
                )
        output[semester] = tuple(
            CurriculumUnit(name, tuple(dict.fromkeys(items)))
            for name, items in grouped.items()
        )
    return output


def _g7_path(publisher: str, semester: str) -> tuple[CurriculumUnit, ...]:
    raw = _load_json(APP_DIR / "learning_map_g7.json")
    semester_key = "七上" if semester == "上學期" else "七下"
    raw_units = (
        raw.get("publishers", {})
        .get(publisher, {})
        .get(semester_key, {})
        .get("units", [])
    )
    core = raw.get("core", {})
    units = []
    for unit in raw_units:
        subunits = []
        for subunit in unit.get("subunits", []):
            types: list[str] = []
            for core_id in subunit.get("core_ids", []):
                types.extend(core.get(core_id, {}).get("question_types", []))
            if not types:
                types.extend(_question_types(unit.get("name", ""), subunit.get("name", "")))
            subunits.append(
                CurriculumSubunit(
                    str(subunit.get("name") or "").strip(),
                    tuple(dict.fromkeys(str(item).strip() for item in types if str(item).strip())),
                )
            )
        units.append(CurriculumUnit(str(unit.get("name") or "").strip(), tuple(subunits)))
    return tuple(item for item in units if item.name and item.subunits)


def get_curriculum_path(grade: Any, publisher: Any, semester: str) -> CurriculumPath:
    grade_number = normalize_grade(grade)
    publisher_name = normalize_publisher(publisher)
    if semester not in SEMESTERS:
        raise ValueError("semester must be 上學期 or 下學期")
    if grade_number == 7:
        units = _g7_path(publisher_name, semester)
        source = "learning_map_g7.json publisher catalog"
    else:
        units = _standard_grade_paths(grade_number)[semester]
        source = f"learning_map_g{grade_number} MathAI knowledge catalog"
    if not units or any(not unit.subunits for unit in units):
        raise ValueError("curriculum path is incomplete")
    return CurriculumPath(grade_number, publisher_name, semester, units, source)


def main_unit_names(path: CurriculumPath) -> list[str]:
    return [unit.name for unit in path.units]


def subunit_labels(path: CurriculumPath, selected_units: Iterable[str]) -> list[str]:
    selected = set(selected_units)
    return [
        f"{unit.name} ＞ {subunit.name}"
        for unit in path.units
        if unit.name in selected
        for subunit in unit.subunits
    ]


def question_type_labels(path: CurriculumPath, selected_subunits: Iterable[str]) -> list[str]:
    selected = set(selected_subunits)
    result: list[str] = []
    for unit in path.units:
        for subunit in unit.subunits:
            prefix = f"{unit.name} ＞ {subunit.name}"
            if prefix not in selected:
                continue
            for question_type in subunit.question_types:
                label = f"{prefix} ＞ {question_type}"
                if label not in result:
                    result.append(label)
    return result


def retain_valid(values: Iterable[str], options: Iterable[str]) -> list[str]:
    allowed = set(options)
    return [value for value in values if value in allowed]


def reset_dependent_selections(state: MutableMapping[str, Any], signature: str) -> None:
    """Clear dependent values before their widgets are instantiated."""
    key = "custom_exam_catalog_signature"
    if state.get(key) == signature:
        return
    for state_key in (
        "custom_exam_main_units",
        "custom_exam_subunits",
        "custom_exam_question_types",
    ):
        state.pop(state_key, None)
    state[key] = signature


def _legacy_generation_context(spec: SelectedExamSpec) -> str:
    return "\n".join(
        (
            f"年級：{spec.grade_label}",
            f"出版社：{spec.publisher}",
            f"學期：{spec.semester}",
            f"主單元：{'、'.join(spec.main_units)}",
            f"次單元：{'、'.join(spec.subunits)}",
            f"題型：{'、'.join(spec.question_types) if spec.question_types else '混合題型'}",
            f"難度：{'、'.join(spec.difficulty)}",
            f"題數：{spec.question_count}",
        )
    )


def _selected_subunit_names(labels: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for label in labels:
        text = str(label).strip()
        if "＞" in text:
            text = text.rsplit("＞", 1)[-1].strip()
        if text:
            result.add(text)
    return result


def _canonical_generation_context(spec: SelectedExamSpec) -> str:
    """Best-effort canonical augmentation for the current G5-G9 UI.

    The current UI is publisher/semester driven, while v2.7 canonical skills are
    publisher-independent.  We therefore only attach skills that match the
    selected MathAI main/subunit labels.  If no safe match exists, legacy context
    is returned unchanged rather than broadening the requested scope.
    """
    try:
        from .curriculum_master_feature import (
            curriculum_master_v27,
            curriculum_master_v27_enabled,
        )
    except (ImportError, ModuleNotFoundError):
        return ""
    if not curriculum_master_v27_enabled():
        return ""
    try:
        runtime = curriculum_master_v27()
        route = runtime.resolve_route(spec.grade_label)
        selected_main = {str(x).strip() for x in spec.main_units if str(x).strip()}
        selected_sub = _selected_subunit_names(spec.subunits)
        candidates = [
            skill for skill in runtime.load_standard_skills(route)
            if skill.main_unit in selected_main or skill.subunit in selected_sub
        ]
        if not candidates:
            return ""
        # Keep prompt size bounded while preserving selected canonical scope.
        candidates = candidates[:24]
        return "\n".join((
            "",
            "【MathAI Curriculum Master v2.7 canonical context】",
            runtime.build_prompt_context(route, [skill.skill_id for skill in candidates]),
            "每題必須回傳 canonical skill_id；若可判定，另回傳 micro_skill_id。",
        ))
    except Exception:
        # Feature-flagged rollout must never break the legacy self-built exam.
        return ""


def build_generation_context(spec: SelectedExamSpec) -> str:
    """Produce the complete context passed to bank search and AI fallback.

    Flag OFF: byte-for-byte equivalent legacy structure.
    Flag ON + valid v2.7 archive: append canonical Skill context.
    Any v2.7 load/match failure: fall back to legacy context.
    """
    legacy = _legacy_generation_context(spec)
    canonical = _canonical_generation_context(spec)
    return legacy + canonical
