"""Read-only adapter for the imported MathAI Master Curriculum grade packs.

The master CSV files remain the source of truth.  This module only builds an
in-memory publisher-to-canonical crosswalk; it never writes back to the pack.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
import re
from typing import Iterable


MASTER_ROOT = Path(__file__).resolve().parents[1] / "data" / "master_curriculum_v2_7"
ROOT = MASTER_ROOT / "grade_packs" / "G8"
SEMESTER_ALIASES = {"上學期": "八上", "下學期": "八下", "八上": "八上", "八下": "八下"}


@dataclass(frozen=True)
class MasterMicroSkill:
    micro_skill_id: str
    parent_skill_id: str
    question_type: str
    focus: str
    difficulty: str


@dataclass(frozen=True)
class MasterSkill:
    skill_id: str
    official_code: str
    main_unit: str
    subunit: str
    skill_name: str
    focus: str
    difficulty: str
    micro_skills: tuple[MasterMicroSkill, ...]


@dataclass(frozen=True)
class PublisherSkillMapping:
    grade: int
    publisher: str
    semester: str
    official_main_unit_id: str
    official_main_unit_name: str
    official_subunit_id: str
    official_subunit_name: str
    skill_id: str
    mapping_confidence: str
    mapping_status: str


@dataclass(frozen=True)
class MasterCatalog:
    publisher_units: tuple[dict[str, str], ...]
    skills: tuple[MasterSkill, ...]
    mappings: tuple[PublisherSkillMapping, ...]

    def mappings_for(self, publisher: str, semester: str, subunit_id: str) -> tuple[PublisherSkillMapping, ...]:
        master_semester = SEMESTER_ALIASES.get(semester, semester)
        return tuple(
            item for item in self.mappings
            if item.publisher == publisher and item.semester == master_semester
            and item.official_subunit_id == subunit_id
            and item.mapping_status in {"VERIFIED", "HIGH_CONFIDENCE", "CROSS_SHARED", "NEEDS_REVIEW"}
        )

    def skill_map(self) -> dict[str, MasterSkill]:
        return {item.skill_id: item for item in self.skills}


def _rows(name: str, root: Path = ROOT) -> list[dict[str, str]]:
    with (root / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _compact_tokens(value: str) -> set[str]:
    text = str(value or "").lower()
    # Keep meaningful CJK bigrams and ASCII words; this is deliberately
    # conservative so generic single characters do not create false matches.
    tokens = set(re.findall(r"[a-z0-9]+", text))
    chars = re.findall(r"[\u4e00-\u9fff]", text)
    tokens.update("".join(chars[i:i + 2]) for i in range(len(chars) - 1))
    return tokens


def _family_candidates(title: str, skills: Iterable[MasterSkill]) -> list[MasterSkill]:
    text = title
    keywords = (
        ("乘法公式", ("MULFORM", "FACTOR")),
        ("多項式", ("POLY",)),
        ("根式", ("SQRT", "RAD")),
        ("平方根", ("SQRT", "RAD")),
        ("因式分解", ("FACTOR",)),
        ("方程式", ("QUAD",)),
        ("函數", ("FUNC",)),
        ("數列", ("SEQ", "ARITH", "GEO")),
        ("等差", ("ARITH",)),
        ("等比", ("GEO",)),
        ("統計", ("D-",)),
        ("資料", ("D-",)),
        ("三角形", ("PYTH", "TRI", "ISO", "ANGLE")),
        ("畢氏", ("PYTH",)),
        ("平行", ("PARA", "PARALLEL", "TRANSVERSAL")),
        ("四邊形", ("PARA", "RECT", "RHOM", "KITE", "TRAP")),
        ("尺規", ("COMPASS",)),
        ("作圖", ("COMPASS",)),
    )
    canonical_keywords = (
        ("\u4e58\u6cd5\u516c\u5f0f", ("MULFORM", "FACTOR")),
        ("\u591a\u9805\u5f0f", ("POLY",)),
        ("\u5e73\u65b9\u6839", ("SQRT", "RAD")),
        ("\u6839\u5f0f", ("SQRT", "RAD")),
        ("\u56e0\u5f0f\u5206\u89e3", ("FACTOR",)),
        ("\u65b9\u7a0b\u5f0f", ("QUAD",)),
        ("\u51fd\u6578", ("FUNC",)),
        ("\u6578\u5217", ("SEQ", "ARITH", "GEO")),
        ("\u7b49\u5dee", ("ARITH",)),
        ("\u7b49\u6bd4", ("GEO",)),
        ("\u7d71\u8a08", ("D-",)),
        ("\u8cc7\u6599", ("D-",)),
        ("\u7562\u6c0f", ("PYTH", "DIST")),
        ("\u8ddd\u96e2", ("PYTH", "DIST")),
        ("\u4e09\u89d2\u5f62", ("PYTH", "TRI", "ISO", "ANGLE", "CONG")),
        ("\u5168\u7b49", ("CONG", "TRI")),
        ("\u5e73\u884c", ("PARA", "PARALLEL", "TRANSVERSAL")),
        ("\u56db\u908a\u5f62", ("PARA", "RECT", "RHOM", "KITE", "TRAP")),
        ("\u5c3a\u898f", ("COMPASS", "PROOF")),
        ("\u4f5c\u5716", ("COMPASS", "PROOF")),
    )
    families = tuple(f for marker, f in keywords + canonical_keywords if marker in text for f in f)
    # Canonical family prefixes are explicit in standard_skills.skill_id and
    # avoid losing valid skills when a publisher uses a broader unit title.
    prefix_rules = (
        ("\u51fd\u6578", ("G08-F-",)),
        ("\u591a\u908a\u5f62", ("G08-S-",)),
        ("\u5168\u7b49", ("G08-S-",)),
        ("\u9762\u7a4d", ("G08-S-",)),
        ("\u5e73\u884c", ("G08-S-",)),
        ("\u7562\u6c0f", ("G08-S-", "G08-G-")),
        ("\u8ddd\u96e2", ("G08-G-",)),
        ("\u591a\u9805\u5f0f", ("G08-A-POLY-",)),
        ("\u56e0\u5f0f\u5206\u89e3", ("G08-A-FACTOR-",)),
    )
    families += tuple(prefix for marker, prefixes in prefix_rules if marker in text for prefix in prefixes)
    if not families:
        return []
    return [skill for skill in skills if any(f in skill.skill_id for f in families)]


def _semantic_candidates(title: str, skills: Iterable[MasterSkill]) -> list[MasterSkill]:
    """Rank candidates using Master names/descriptions, not publisher guesses."""
    source = _compact_tokens(title)
    scored = []
    for skill in skills:
        target = _compact_tokens(skill.main_unit + skill.subunit + skill.skill_name + skill.focus)
        score = len(source & target)
        if score >= 2:
            scored.append((score, skill))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    return [skill for score, skill in sorted(scored, key=lambda item: (-item[0], item[1].skill_id))
            if score >= max(2, best - 2)]


SHARED_ROUTE_RULES = {
    "G08-A-FACTOR-CHECK-01": ("\u56e0\u5f0f\u5206\u89e3", "\u4e58\u6cd5\u516c\u5f0f"),
    "G08-A-POLY-ORDER-01": ("\u591a\u9805\u5f0f",),
    "G08-S-CONGRUENT-01": ("\u5168\u7b49", "\u4e09\u89d2\u5f62\u5168\u7b49"),
    "G08-S-CONG-PROOF-01": ("\u5168\u7b49", "\u4e09\u89d2\u5f62\u5168\u7b49"),
    "G08-S-PARALLEL-REV-01": ("\u5e73\u884c",),
    "G08-S-PYTH-APP-01": ("\u7562\u6c0f", "\u61c9\u7528\u554f\u984c"),
    "G08-S-PYTH-LEN-01": ("\u7562\u6c0f", "\u76f4\u89d2\u4e09\u89d2\u5f62"),
    "G08-S-TRI-SSS-01": ("\u5168\u7b49", "\u4e09\u89d2\u5f62"),
    "G08-S-TRI-SAS-01": ("\u5168\u7b49", "\u4e09\u89d2\u5f62"),
    "G08-S-TRI-RHS-01": ("\u5168\u7b49", "\u76f4\u89d2\u4e09\u89d2\u5f62"),
    "G08-S-TRI-ASA-01": ("\u5168\u7b49", "\u4e09\u89d2\u5f62"),
    "G08-S-POLY-INNER-01": ("\u591a\u908a\u5f62", "\u5167\u89d2"),
}


def _build_mappings(units: list[dict[str, str]], skills: tuple[MasterSkill, ...]) -> tuple[PublisherSkillMapping, ...]:
    result: list[PublisherSkillMapping] = []
    for unit in units:
        title = unit["subunit_title"]
        full_title = unit["unit_title"] + title
        exact = [s for s in skills if s.subunit == title]
        family = _family_candidates(full_title, skills)
        subunit_matches = [s for s in skills if s.subunit and (s.subunit in full_title or s.subunit in title)]
        ranked = _semantic_candidates(full_title, tuple(dict.fromkeys(subunit_matches + family)))
        candidates = exact or ranked or subunit_matches or family or _semantic_candidates(full_title, skills)
        shared_candidates = [skill for skill in skills
                             if skill.skill_id in SHARED_ROUTE_RULES
                             and any(marker in full_title for marker in SHARED_ROUTE_RULES[skill.skill_id])]
        candidates = list(dict.fromkeys(candidates + shared_candidates))
        if not candidates:
            shared_ids = [skill for skill in skills
                          if skill.skill_id in SHARED_ROUTE_RULES
                          and any(marker in full_title for marker in SHARED_ROUTE_RULES[skill.skill_id])]
            candidates = shared_ids
            if not candidates:
                continue
        # Keep a bounded, domain-relevant set.  Never attach the entire pool.
        ordered_candidates = list(dict.fromkeys(shared_candidates + candidates))
        for skill in ordered_candidates[:12]:
            status = "VERIFIED" if exact else "HIGH_CONFIDENCE"
            confidence = "VERIFIED" if exact else "HIGH"
            if (not exact and skill.skill_id in SHARED_ROUTE_RULES
                    and any(marker in full_title for marker in SHARED_ROUTE_RULES[skill.skill_id])):
                status, confidence = "CROSS_SHARED", "SHARED"
            result.append(PublisherSkillMapping(
                grade=8,
                publisher=unit["publisher"],
                semester=unit["semester"],
                official_main_unit_id=f"G08-{unit['unit_no']}",
                official_main_unit_name=unit["unit_title"],
                official_subunit_id=f"G08-{unit['unit_no']}-{unit['sub_no']}",
                official_subunit_name=title,
                skill_id=skill.skill_id,
                mapping_confidence=confidence,
                mapping_status=status,
            ))
    return tuple(result)


def load_g8_master_catalog() -> MasterCatalog:
    units = _rows("publisher_units.csv")
    skill_rows = _rows("standard_skills.csv")
    micro_rows = _rows("layer2_micro_skills.csv")
    micro_by_skill: dict[str, list[MasterMicroSkill]] = {}
    for row in micro_rows:
        micro_by_skill.setdefault(row["parent_skill_id"], []).append(MasterMicroSkill(
            micro_skill_id=row["micro_skill_id"],
            parent_skill_id=row["parent_skill_id"],
            question_type=row["question_type"],
            focus=row["focus"],
            difficulty=row["difficulty"],
        ))
    skills = tuple(MasterSkill(
        skill_id=row["skill_id"], official_code=row["official_code"],
        main_unit=row.get("main_unit", row.get("mathai_main_unit", "")),
        subunit=row.get("subunit", row.get("mathai_subunit", "")),
        skill_name=row["skill_name"], focus=row["focus"],
        difficulty=row["difficulty"],
        micro_skills=tuple(micro_by_skill.get(row["skill_id"], ())),
    ) for row in skill_rows)
    return MasterCatalog(tuple(units), skills, _build_mappings(units, skills))


GRADE_PACK_ROUTES = {
    **{(grade, publisher): MASTER_ROOT / "grade_packs" / f"G{grade}"
       for grade in range(1, 10) for publisher in ("康軒", "翰林", "南一")},
    (10, "普通高中"): MASTER_ROOT / "grade_packs" / "G10_GENERAL",
    (10, "數學 A"): MASTER_ROOT / "high_school_tracks" / "TECHNICAL" / "TECH_A" / "G10",
    (10, "數學 B"): MASTER_ROOT / "high_school_tracks" / "TECHNICAL" / "TECH_B" / "G10",
    (10, "數學 C"): MASTER_ROOT / "high_school_tracks" / "TECHNICAL" / "TECH_C" / "G10",
    (11, "數學 A"): MASTER_ROOT / "grade_packs" / "G11_A",
    (11, "數學 B"): MASTER_ROOT / "grade_packs" / "G11_B",
    (12, "數學甲"): MASTER_ROOT / "grade_packs" / "G12_A",
    (12, "數學乙"): MASTER_ROOT / "grade_packs" / "G12_B",
}


def curriculum_versions(grade: int) -> tuple[str, ...]:
    """Only expose routes backed by an existing released Master pack."""
    versions = tuple(version for (route_grade, version), path in GRADE_PACK_ROUTES.items()
                     if route_grade == grade and path.is_dir())
    if grade == 6:
        return versions + ("報考私中", "參加數學競賽")
    return versions


def load_master_catalog(grade: int, version: str) -> MasterCatalog:
    """Load exactly one selected pack, following the Master load policy."""
    root = GRADE_PACK_ROUTES.get((grade, version))
    if root is None or not root.is_dir():
        raise ValueError(f"unsupported Master Curriculum route: G{grade} {version}")
    units_path = root / "publisher_units.csv"
    units = _rows("publisher_units.csv", root) if units_path.exists() else []
    skill_rows = _rows("standard_skills.csv", root)
    micro_rows = _rows("layer2_micro_skills.csv", root)
    micro_by_skill: dict[str, list[MasterMicroSkill]] = {}
    for row in micro_rows:
        micro_by_skill.setdefault(row["parent_skill_id"], []).append(MasterMicroSkill(
            micro_skill_id=row["micro_skill_id"],
            parent_skill_id=row["parent_skill_id"],
            question_type=row["question_type"],
            focus=row["focus"],
            difficulty=row["difficulty"],
        ))
    skills = tuple(MasterSkill(
        skill_id=row["skill_id"], official_code=row["official_code"],
        main_unit=row.get("main_unit", row.get("mathai_main_unit", "")),
        subunit=row.get("subunit", row.get("mathai_subunit", "")),
        skill_name=row["skill_name"], focus=row["focus"],
        difficulty=row["difficulty"],
        micro_skills=tuple(micro_by_skill.get(row["skill_id"], ())),
    ) for row in skill_rows)
    return MasterCatalog(tuple(units), skills, ())


__all__ = ["MasterCatalog", "MasterMicroSkill", "MasterSkill", "PublisherSkillMapping",
           "ROOT", "curriculum_versions", "load_g8_master_catalog", "load_master_catalog"]
