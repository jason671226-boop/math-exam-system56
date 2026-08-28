"""Normalized G1-G12 curriculum adapter for the self-built exam flow.

Publisher and semester are explicit catalog dimensions so UI state and
generation context cannot leak across selections.  G1-G4 and G7 use official
publisher catalogs (``publisher_catalog_g1_g4`` / ``learning_map_g7.json``);
G5-G6 and G8-G9 still use the reviewed MathAI grade knowledge maps until
publisher-specific source data is added for those grades.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, MutableMapping

try:  # Prefer the data/service package; never resolve through the Streamlit app.py.
    from services.publisher_catalog_g1_g4 import get_catalog as _get_publisher_catalog
    from services.publisher_catalog_g8_g9 import get_catalog as _get_g8_g9_catalog
    from services.master_curriculum_loader import curriculum_versions, load_g8_master_catalog, load_master_catalog
except ImportError:  # pragma: no cover - package import fallback
    from .publisher_catalog_g1_g4 import get_catalog as _get_publisher_catalog
    from .publisher_catalog_g8_g9 import get_catalog as _get_g8_g9_catalog
    from .master_curriculum_loader import curriculum_versions, load_g8_master_catalog, load_master_catalog


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
APP_DIR = DATA_DIR.parent
SUPPORTED_GRADES = tuple(range(1, 13))
PUBLISHERS = ("康軒", "翰林", "南一")
SEMESTERS = ("上學期", "下學期")
DIFFICULTIES = ("基礎", "標準", "進階", "挑戰")
VARIATION_BY_DIFFICULTY: Mapping[str, tuple[int, ...]] = {
    "基礎": (1,),
    "標準": (1, 2),
    "進階": (2, 3),
    "挑戰": (3, 4),
}


__all__ = (
    "BANK_SEARCH_TIERS", "DIFFICULTIES", "PUBLISHERS", "SEMESTERS",
    "SUPPORTED_GRADES", "SelectedExamSpec", "build_generation_context",
    "curriculum_versions", "exam_output_has_question_count", "get_curriculum_path", "knowledge_point_ids", "knowledge_point_labels",
    "main_unit_names", "micro_skill_ids", "question_bank_search_plan",
    "question_type_labels", "reset_dependent_selections", "skill_ids",
    "standard_knowledge_ids", "subunit_labels",
)


@dataclass(frozen=True)
class CurriculumKnowledgePoint:
    """Finest-grained curriculum node (L3), shared across exam / learning-map /
    diagnosis features.  ``knowledge_point_id`` is the stable cross-feature key.
    """

    name: str
    knowledge_point_id: str
    standard_knowledge_id: str
    question_types: tuple[str, ...]
    difficulty: tuple[str, ...]
    variation_levels: tuple[int, ...]
    skill_id: str = ""
    micro_skill_id: str = ""
    micro_skill: str = ""
    micro_skill_ids: tuple[str, ...] = ()
    micro_skill_question_types: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CurriculumSubunit:
    name: str
    question_types: tuple[str, ...]
    knowledge_points: tuple[CurriculumKnowledgePoint, ...] = ()
    subunit_id: str = ""


@dataclass(frozen=True)
class CurriculumUnit:
    name: str
    subunits: tuple[CurriculumSubunit, ...]
    main_unit_id: str = ""


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
    knowledge_points: tuple[str, ...] = ()
    standard_knowledge_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    micro_skill_ids: tuple[str, ...] = ()
    variation_level: int = 1

    def __post_init__(self) -> None:
        if self.grade not in SUPPORTED_GRADES:
            raise ValueError("unsupported grade")
        if self.publisher not in curriculum_versions(self.grade):
            raise ValueError("unsupported curriculum version")
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
        raise ValueError("grade must be G1-G12")
    return grade


def normalize_publisher(value: Any) -> str:
    return str(value or "").strip().removesuffix("版")


def _load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _question_types(grade: int, main_unit: str, subunit: str) -> tuple[str, ...]:
    text = main_unit + subunit
    if grade <= 2:
        return _lower_primary_question_types(text)
    if grade <= 4:
        return _middle_primary_question_types(text)
    return _upper_primary_question_types(text)


def _lower_primary_question_types(text: str) -> tuple[str, ...]:
    """G1-G2 題型：以辨識、比較、情境與填空為主，不含會考題型。"""
    result = ["基本觀念", "基本計算"]
    if any(word in text for word in ("圖形", "形狀", "立體", "拼", "分類", "規律")):
        result.extend(("圖形辨識", "規律與分類"))
    elif any(word in text for word in ("時間", "鐘", "月曆", "日期", "星期")):
        result.extend(("情境題", "生活應用"))
    elif any(word in text for word in ("錢幣", "長度", "容量", "重量")):
        result.extend(("比較大小", "情境題"))
    else:
        result.extend(("數數與數量", "比較大小", "填空題", "生活應用", "簡單文字題"))
    result.extend(("進階變形", "挑戰思考"))
    return tuple(dict.fromkeys(result))


def _middle_primary_question_types(text: str) -> tuple[str, ...]:
    """G3-G4 題型：加入圖表、換算、多步驟，仍不含會考題型。"""
    result = ["基本觀念", "計算題", "填空題", "應用題"]
    if any(word in text for word in ("統計", "資料", "圖表", "長條", "折線")):
        result.extend(("圖表判讀", "生活素養"))
    elif any(word in text for word in ("圖形", "幾何", "面積", "周長", "角", "對稱", "三角形", "四邊形")):
        result.extend(("圖形題", "幾何推理"))
    elif any(word in text for word in ("分數", "小數", "概數", "估算")):
        result.extend(("估算", "單位換算", "數量關係"))
    elif any(word in text for word in ("長度", "容量", "重量", "公升", "公斤", "公分", "公尺")):
        result.extend(("單位換算", "生活素養"))
    elif any(word in text for word in ("乘", "除", "四則")):
        result.extend(("多步驟應用", "數量關係"))
    else:
        result.extend(("生活素養", "數量關係"))
    result.extend(("進階變形", "跨次單元", "挑戰題"))
    return tuple(dict.fromkeys(result))


def _upper_primary_question_types(text: str) -> tuple[str, ...]:
    """G5-G12 題型：沿用既有高年級分類。"""
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
                    CurriculumSubunit(sub, _question_types(grade, main, sub))
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
                types.extend(_question_types(7, unit.get("name", ""), subunit.get("name", "")))
            subunits.append(
                CurriculumSubunit(
                    str(subunit.get("name") or "").strip(),
                    tuple(dict.fromkeys(str(item).strip() for item in types if str(item).strip())),
                )
            )
        units.append(CurriculumUnit(str(unit.get("name") or "").strip(), tuple(subunits)))
    return tuple(item for item in units if item.name and item.subunits)


def _g1_g4_publisher_path(grade: int, publisher: str, semester: str) -> tuple[CurriculumUnit, ...]:
    """Official G1-G4 publisher catalog: publisher unit names + MathAI subunits."""
    catalog = _get_publisher_catalog(grade, publisher, semester)
    if not catalog or not catalog.get("units"):
        raise ValueError(f"publisher catalog missing for G{grade} {publisher} {semester}")
    units = []
    for unit in catalog["units"]:
        subunits = tuple(
            CurriculumSubunit(
                str(subunit.get("standard_name") or "").strip(),
                tuple(
                    str(item).strip()
                    for item in subunit.get("question_types", ())
                    if str(item).strip()
                ),
            )
            for subunit in unit.get("subunits", ())
        )
        units.append(
            CurriculumUnit(str(unit.get("official_unit_name") or "").strip(), subunits)
        )
    return tuple(item for item in units if item.name and item.subunits)


def _g8_g9_publisher_path(grade: int, publisher: str, semester: str) -> tuple[CurriculumUnit, ...]:
    """Official G8-G9 publisher catalog with fine-grained knowledge points (L3)."""
    if grade == 8:
        return _g8_master_publisher_path(publisher, semester)
    catalog = _get_g8_g9_catalog(grade, publisher, semester)
    if not catalog or not catalog.get("units"):
        raise ValueError(f"publisher catalog missing for G{grade} {publisher} {semester}")
    units = []
    for unit in catalog["units"]:
        subunits = []
        for subunit in unit.get("subunits", ()):
            knowledge_points = tuple(
                CurriculumKnowledgePoint(
                    name=str(kp.get("knowledge_point") or "").strip(),
                    knowledge_point_id=str(kp.get("knowledge_point_id") or "").strip(),
                    standard_knowledge_id=str(kp.get("standard_knowledge_id") or "").strip(),
                    question_types=tuple(
                        str(item).strip()
                        for item in kp.get("question_types", ())
                        if str(item).strip()
                    ),
                    difficulty=tuple(
                        str(item).strip()
                        for item in kp.get("difficulty", ())
                        if str(item).strip()
                    ),
                    variation_levels=tuple(
                        int(item) for item in kp.get("variation_levels", ())
                    ),
                    skill_id=str(kp.get("skill_id") or "").strip(),
                    micro_skill_id=str(kp.get("micro_skill_id") or "").strip(),
                    micro_skill=str(kp.get("micro_skill") or "").strip(),
                )
                for kp in subunit.get("knowledge_points", ())
                if kp.get("knowledge_point_id")
            )
            # Aggregate question types across the subunit so the pre-KP surface
            # stays available where knowledge points are not selected.
            qtypes = tuple(dict.fromkeys(
                qt for kp in knowledge_points for qt in kp.question_types
            ))
            subunits.append(
                CurriculumSubunit(
                    str(subunit.get("official_subunit") or "").strip(),
                    qtypes,
                    knowledge_points,
                )
            )
        units.append(
            CurriculumUnit(str(unit.get("official_main_unit") or "").strip(), tuple(subunits))
        )
    return tuple(item for item in units if item.name and item.subunits)


def _g8_master_publisher_path(publisher: str, semester: str) -> tuple[CurriculumUnit, ...]:
    """Adapt the read-only Master Curriculum pack to the shared UI model."""
    catalog = load_g8_master_catalog()
    skills = catalog.skill_map()
    master_semester = {"上學期": "八上", "下學期": "八下"}.get(semester, semester)
    selected = [u for u in catalog.publisher_units
                if u["publisher"] == publisher and u["semester"] == master_semester]
    units: list[CurriculumUnit] = []
    for unit_no in dict.fromkeys(u["unit_no"] for u in selected):
        rows = [u for u in selected if u["unit_no"] == unit_no]
        subunits: list[CurriculumSubunit] = []
        for row in rows:
            sub_id = f"G08-{row['unit_no']}-{row['sub_no']}"
            mappings = catalog.mappings_for(publisher, semester, sub_id)
            points: list[CurriculumKnowledgePoint] = []
            for mapping in mappings:
                skill = skills[mapping.skill_id]
                micros = skill.micro_skills
                if not micros:
                    continue
                points.append(CurriculumKnowledgePoint(
                    name=skill.skill_name,
                    # A canonical skill may legitimately map to more than one
                    # publisher subunit.  Keep the UI knowledge-point key
                    # route-unique while ``skill_id`` remains canonical.
                    knowledge_point_id=f"{sub_id}:{skill.skill_id}",
                    standard_knowledge_id=skill.official_code,
                    question_types=tuple(dict.fromkeys(m.question_type for m in micros if m.question_type)),
                    # Master ``difficulty`` describes the native complexity of
                    # each micro skill, not which exam levels may select it.
                    # The G8 runtime owns four age-fit blueprints for every
                    # mapped micro skill, so all four UI levels are valid.
                    difficulty=DIFFICULTIES,
                    variation_levels=(1, 2, 3, 4),
                    skill_id=skill.skill_id,
                    micro_skill_id=micros[0].micro_skill_id,
                    micro_skill=micros[0].focus,
                    micro_skill_ids=tuple(m.micro_skill_id for m in micros),
                    micro_skill_question_types=tuple((m.question_type, m.micro_skill_id) for m in micros if m.question_type),
                ))
            if points:
                subunits.append(CurriculumSubunit(
                    row["subunit_title"],
                    tuple(dict.fromkeys(q for p in points for q in p.question_types)),
                    tuple(points),
                    sub_id,
                ))
        if subunits:
            units.append(CurriculumUnit(rows[0]["unit_title"], tuple(subunits), f"G08-{unit_no}"))
    if not units:
        raise ValueError(f"master curriculum path missing for G8 {publisher} {semester}")
    return tuple(units)


def get_curriculum_path(grade: Any, publisher: Any, semester: str) -> CurriculumPath:
    grade_number = normalize_grade(grade)
    publisher_name = normalize_publisher(publisher)
    if semester not in SEMESTERS:
        raise ValueError("semester must be 上學期 or 下學期")
    if publisher_name not in curriculum_versions(grade_number):
        raise ValueError(f"unsupported curriculum version for G{grade_number}")
    if grade_number == 6 and publisher_name == "報考私中":
        units = _g6_private_school_path(semester)
        return CurriculumPath(grade_number, publisher_name, semester, units,
                              "learning_map_g6_pilot.json private-school route")
    if grade_number == 6 and publisher_name == "參加數學競賽":
        units = _g6_competition_path()
        return CurriculumPath(grade_number, publisher_name, semester, units,
                              "ELEMENTARY_COMPETITION_HIERARCHY")
    catalog = load_master_catalog(grade_number, publisher_name)
    units = (_g8_master_publisher_path(publisher_name, semester)
             if grade_number == 8 else
             _master_skill_path(catalog, grade_number, semester))
    source = f"master_curriculum_v2_7 G{grade_number} {publisher_name}"
    if not units or any(not unit.subunits for unit in units):
        raise ValueError("curriculum path is incomplete")
    return CurriculumPath(grade_number, publisher_name, semester, units, source)


def _g6_private_school_path(semester: str) -> tuple[CurriculumUnit, ...]:
    raw = _load_json(DATA_DIR / "learning_map_g6_pilot.json")
    points = list(raw.get("knowledge_points", ()))
    midpoint = max(1, (len(points) + 1) // 2)
    selected = points[:midpoint] if semester == "上學期" else points[midpoint:]
    grouped: dict[str, dict[str, list[CurriculumKnowledgePoint]]] = {}
    for row in selected:
        main = str(row.get("main_unit") or "").strip()
        sub = str(row.get("sub_unit") or "").strip()
        if not main or not sub:
            continue
        question_types = tuple(str(item).strip() for item in row.get("question_types", ()) if str(item).strip())
        grouped.setdefault(main, {}).setdefault(sub, []).append(CurriculumKnowledgePoint(
            name=str(row.get("learning_focus") or sub).strip(),
            knowledge_point_id=str(row.get("id") or "").strip(),
            standard_knowledge_id="",
            question_types=question_types,
            difficulty=DIFFICULTIES,
            variation_levels=(1, 2, 3, 4),
            skill_id=str(row.get("id") or "").strip(),
            micro_skill_id=f"{row.get('id', '')}-PRIVATE",
            micro_skill=str(row.get("learning_focus") or "").strip(),
            micro_skill_ids=(f"{row.get('id', '')}-PRIVATE",),
            micro_skill_question_types=tuple((item, f"{row.get('id', '')}-PRIVATE-{index}")
                                             for index, item in enumerate(question_types, 1)),
        ))
    return tuple(CurriculumUnit(main, tuple(
        CurriculumSubunit(sub, tuple(dict.fromkeys(q for point in items for q in point.question_types)), tuple(items))
        for sub, items in subunits.items())) for main, subunits in grouped.items())


def _g6_competition_path() -> tuple[CurriculumUnit, ...]:
    from curriculum.elementary_competition_hierarchy import (
        ELEMENTARY_COMPETITION_HIERARCHY,
    )
    units: list[CurriculumUnit] = []
    for contest_index, (contest, categories) in enumerate(ELEMENTARY_COMPETITION_HIERARCHY.items(), 1):
        subunits: list[CurriculumSubunit] = []
        for category_index, (category, details) in enumerate(categories.items(), 1):
            qtypes = tuple(str(item).strip() for item in details.get("question_types", ()) if str(item).strip())
            points = tuple(CurriculumKnowledgePoint(
                name=str(topic).strip(),
                knowledge_point_id=f"G6-COMP-{contest_index:02d}-{category_index:02d}-{topic_index:02d}",
                standard_knowledge_id="",
                question_types=qtypes,
                difficulty=DIFFICULTIES,
                variation_levels=(1, 2, 3, 4),
                skill_id=f"G6-COMP-{contest_index:02d}-{category_index:02d}",
                micro_skill_id=f"G6-COMP-{contest_index:02d}-{category_index:02d}-{topic_index:02d}",
                micro_skill=str(topic).strip(),
                micro_skill_ids=(f"G6-COMP-{contest_index:02d}-{category_index:02d}-{topic_index:02d}",),
                micro_skill_question_types=tuple((item, f"G6-COMP-{contest_index:02d}-{category_index:02d}-Q{q_index:02d}")
                                                 for q_index, item in enumerate(qtypes, 1)),
            ) for topic_index, topic in enumerate(details.get("topics", ()), 1))
            if points:
                subunits.append(CurriculumSubunit(category, qtypes, points))
        if subunits:
            units.append(CurriculumUnit(contest, tuple(subunits)))
    return tuple(units)


def _master_skill_path(catalog: Any, grade: int, semester: str) -> tuple[CurriculumUnit, ...]:
    """Build the complete selectable hierarchy from one canonical Master pack."""
    grouped: dict[str, dict[str, list[CurriculumKnowledgePoint]]] = {}
    for skill in catalog.skills:
        micros = skill.micro_skills
        if not micros:
            continue
        point = CurriculumKnowledgePoint(
            name=skill.skill_name,
            knowledge_point_id=skill.skill_id,
            standard_knowledge_id=skill.official_code,
            question_types=tuple(dict.fromkeys(m.question_type for m in micros if m.question_type)),
            difficulty=DIFFICULTIES,
            variation_levels=(1, 2, 3, 4),
            skill_id=skill.skill_id,
            micro_skill_id=micros[0].micro_skill_id,
            micro_skill=micros[0].focus,
            micro_skill_ids=tuple(m.micro_skill_id for m in micros),
            micro_skill_question_types=tuple((m.question_type, m.micro_skill_id) for m in micros if m.question_type),
        )
        grouped.setdefault(skill.main_unit, {}).setdefault(skill.subunit, []).append(point)
    all_units = [CurriculumUnit(main, tuple(
        CurriculumSubunit(sub, tuple(dict.fromkeys(q for p in points for q in p.question_types)), tuple(points))
        for sub, points in subunits.items())) for main, subunits in grouped.items()]
    midpoint = max(1, (len(all_units) + 1) // 2)
    return tuple(all_units[:midpoint] if semester == "上學期" else all_units[midpoint:])


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


def knowledge_point_labels(path: CurriculumPath, selected_subunits: Iterable[str]) -> list[str]:
    selected = set(selected_subunits)
    return [
        f"{unit.name} ＞ {subunit.name} ＞ {kp.name}"
        for unit in path.units
        for subunit in unit.subunits
        if f"{unit.name} ＞ {subunit.name}" in selected
        for kp in subunit.knowledge_points
    ]


def _selected_knowledge_points(path: CurriculumPath, selected: set[str]):
    for unit in path.units:
        for subunit in unit.subunits:
            prefix = f"{unit.name} ＞ {subunit.name}"
            for kp in subunit.knowledge_points:
                if f"{prefix} ＞ {kp.name}" in selected:
                    yield kp


def knowledge_point_ids(path: CurriculumPath, selected_knowledge_points: Iterable[str]) -> tuple[str, ...]:
    """Stable knowledge-point IDs for the selected labels (bank-search primary key)."""
    selected = set(selected_knowledge_points)
    return tuple(dict.fromkeys(
        kp.knowledge_point_id for kp in _selected_knowledge_points(path, selected)
    ))


def standard_knowledge_ids(path: CurriculumPath, selected_knowledge_points: Iterable[str]) -> tuple[str, ...]:
    """108-curriculum standard codes for the selected knowledge points."""
    selected = set(selected_knowledge_points)
    return tuple(dict.fromkeys(
        kp.standard_knowledge_id
        for kp in _selected_knowledge_points(path, selected)
        if kp.standard_knowledge_id
    ))


def skill_ids(path: CurriculumPath, selected_knowledge_points: Iterable[str]) -> tuple[str, ...]:
    """Return canonical MathAI skill IDs for selected knowledge-point labels."""
    selected = set(selected_knowledge_points)
    return tuple(dict.fromkeys(
        kp.skill_id for kp in _selected_knowledge_points(path, selected) if kp.skill_id
    ))


def micro_skill_ids(path: CurriculumPath, selected_knowledge_points: Iterable[str]) -> tuple[str, ...]:
    """Return canonical MathAI micro-skill IDs for selected labels."""
    selected = set(selected_knowledge_points)
    return tuple(dict.fromkeys(
        micro_id
        for kp in _selected_knowledge_points(path, selected)
        for micro_id in (kp.micro_skill_ids or ((kp.micro_skill_id,) if kp.micro_skill_id else ()))
    ))


def question_type_labels(
    path: CurriculumPath,
    selected_subunits: Iterable[str],
    selected_knowledge_points: Iterable[str] = (),
) -> list[str]:
    selected = set(selected_subunits)
    kp_selected = set(selected_knowledge_points)
    result: list[str] = []
    for unit in path.units:
        for subunit in unit.subunits:
            prefix = f"{unit.name} ＞ {subunit.name}"
            if prefix not in selected:
                continue
            if subunit.knowledge_points:
                # G8-G9: question types are derived from the selected knowledge points.
                source_types: Iterable[str] = (
                    qt
                    for kp in subunit.knowledge_points
                    if (not kp_selected or f"{prefix} ＞ {kp.name}" in kp_selected)
                    for qt in kp.question_types
                )
            else:
                source_types = subunit.question_types
            for question_type in source_types:
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
        "custom_exam_knowledge_points",
        "custom_exam_question_types",
    ):
        state.pop(state_key, None)
    state[key] = signature


def _grade_band(grade: int) -> str:
    if grade <= 2:
        return "低年級"
    if grade <= 4:
        return "中年級"
    if grade <= 6:
        return "高年級"
    if grade <= 9:
        return "國中"
    return "高中"


def _variation_labels(difficulties: Iterable[str]) -> str:
    levels = sorted({level for d in difficulties for level in VARIATION_BY_DIFFICULTY.get(d, (1,))})
    return "、".join(f"Level {level}" for level in levels)


def build_generation_context(spec: SelectedExamSpec) -> str:
    """Produce the complete, testable context passed to bank search and AI fallback."""
    lines = [
        f"年級：{spec.grade_label}",
        f"出版社：{spec.publisher}",
        f"學期：{spec.semester}",
        f"年段：{_grade_band(spec.grade)}",
        f"主單元：{'、'.join(spec.main_units)}",
        f"次單元：{'、'.join(spec.subunits)}",
    ]
    if spec.knowledge_points:
        lines.append(f"細分知識點：{'、'.join(spec.knowledge_points)}")
    if spec.standard_knowledge_ids:
        lines.append(f"課綱編碼：{'、'.join(spec.standard_knowledge_ids)}")
    if spec.skill_ids:
        lines.append(f"skill_id: {', '.join(spec.skill_ids)}")
    if spec.micro_skill_ids:
        lines.append(f"micro_skill_id: {', '.join(spec.micro_skill_ids)}")
    lines.extend(
        (
            f"題型：{'、'.join(spec.question_types) if spec.question_types else '混合題型'}",
            f"難度：{'、'.join(spec.difficulty)}",
            f"變化層級：{_variation_labels(spec.difficulty)}",
            f"題數：{spec.question_count}",
        )
    )
    return "\n".join(lines)


def exam_output_has_question_count(text: str, expected_count: int) -> bool:
    """Reject partial, code-like, or placeholder AI output before UI delivery."""
    value = str(text or "").strip()
    if not value or "```python" in value.lower() or "UNIT_PLACEHOLDER" in value:
        return False
    numbers = {
        int(match.group(1))
        for match in re.finditer(r"(?m)^\s*(?:第\s*)?(\d+)\s*(?:題|[.、．)])", value)
    }
    return all(number in numbers for number in range(1, expected_count + 1))


# ---------------------------------------------------------------------------
# Question-bank retrieval order (shared across exam / diagnosis / variation)
# ---------------------------------------------------------------------------

BANK_SEARCH_TIERS = (
    "micro_skill_id",         # 1. exact micro-skill match
    "skill_id",               # 2. canonical skill match
    "knowledge_point_id",     # 1. exact stable-ID match
    "standard_knowledge_id",  # compatibility / standards crosswalk
    "related_micro_skill_id", # 3. nearby micro-skill in same skill
    "subunit",                # 4. same official subunit
    "main_unit",              # compatibility only; never queried first
    "ai_fallback",            # 5. validated AI generation
)


def question_bank_search_plan(
    path: CurriculumPath, spec: SelectedExamSpec
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return the ordered bank-search tiers for ``spec``.

    Each tier is ``(tier_name, terms)`` where ``terms`` are the keys to try in
    that order before falling back to the next tier.  The final tier is always
    ``ai_fallback`` with empty terms (AI generates fresh content).
    """
    kp_ids = knowledge_point_ids(path, spec.knowledge_points)
    std_ids = standard_knowledge_ids(path, spec.knowledge_points)
    selected_micro = tuple(spec.micro_skill_ids) or micro_skill_ids(path, spec.knowledge_points)
    selected_skills = tuple(spec.skill_ids) or skill_ids(path, spec.knowledge_points)
    related_micro = tuple(dict.fromkeys(
        micro_id
        for unit in path.units for subunit in unit.subunits
        for kp in subunit.knowledge_points
        if kp.skill_id in selected_skills
        for micro_id in (kp.micro_skill_ids or ((kp.micro_skill_id,) if kp.micro_skill_id else ()))
        if micro_id not in selected_micro
    ))
    subunits = tuple(part.split(" ＞ ")[-1] for part in spec.subunits)
    return (
        ("micro_skill_id", selected_micro),
        ("skill_id", selected_skills),
        ("knowledge_point_id", kp_ids),
        ("standard_knowledge_id", std_ids),
        ("related_micro_skill_id", related_micro),
        ("subunit", subunits),
        ("main_unit", tuple(spec.main_units)),
        ("ai_fallback", ()),
    )
