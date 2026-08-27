"""Local-only Stage 7 assessment profiles and fail-closed mapping validation."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "data/master_curriculum_v2_7/grade_packs"
THINKING_PATH = ROOT / "data/stage7/thinking_skills_v1.csv"
PRIVATE_JH_TARGET_GRADES = ("G5", "G6")
PRIVATE_JH_FOUNDATION_GRADES = ("G1", "G2", "G3", "G4")
PRIVATE_JH_CATALOG_GRADES = PRIVATE_JH_FOUNDATION_GRADES + PRIVATE_JH_TARGET_GRADES


class ProfileType(str, Enum):
    STANDARD = "STANDARD"
    PRIVATE_JH = "PRIVATE_JH"
    COMPETITION = "COMPETITION"
    ELEMENTARY_COMPETITION = "ELEMENTARY_COMPETITION"


PRIVATE_JH_STYLES = frozenset({
    "STANDARD_REINFORCEMENT", "MULTI_STEP", "REVERSE_REASONING", "CROSS_UNIT",
    "HIGH_DIFFICULTY", "TIME_PRESSURE", "PRIVATE_JH_CLASSIC", "PRIVATE_JH_ADVANCED",
    "PATTERN_REASONING",
})
STANDARD_STYLES = frozenset({"STANDARD"})
COMPETITION_LEVELS = frozenset({"FOUNDATION", "INTERMEDIATE", "ADVANCED"})


@dataclass(frozen=True)
class AssessmentProfile:
    profile_id: str
    profile_type: ProfileType
    grade_band: str
    curriculum_grade: tuple[str, ...]
    curriculum_target_grade: tuple[str, ...]
    curriculum_foundation_grade: tuple[str, ...]
    difficulty_band: tuple[str, ...]
    assessment_style: tuple[str, ...]
    allowed_skill_ids: tuple[str, ...]
    allowed_micro_ids: tuple[str, ...]
    thinking_skill_enabled: bool
    cross_unit_enabled: bool
    time_pressure_enabled: bool
    source_type: str
    status: str


def normalize_profile_type(value: str | ProfileType | None = None) -> ProfileType:
    """Omitted profile preserves the pre-Stage-7 STANDARD behavior."""
    if value is None or value == "":
        return ProfileType.STANDARD
    try:
        return ProfileType(value)
    except ValueError as exc:
        raise ValueError(f"UNKNOWN_PROFILE:{value}") from exc


def load_curriculum_catalog(grades: Iterable[str]) -> tuple[dict[str, dict], dict[str, dict]]:
    skills: dict[str, dict] = {}
    micros: dict[str, dict] = {}
    for grade in grades:
        pack = PACK_ROOT / grade
        if not pack.is_dir():
            raise ValueError(f"UNKNOWN_CURRICULUM_GRADE:{grade}")
        with (pack / "standard_skills.csv").open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                skill_id = (row.get("skill_id") or "").strip()
                if not skill_id or skill_id in skills:
                    raise ValueError(f"INVALID_OR_DUPLICATE_SKILL_ID:{skill_id}")
                skills[skill_id] = row
        with (pack / "layer2_micro_skills.csv").open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                micro_id = (row.get("micro_skill_id") or "").strip()
                if not micro_id or micro_id in micros:
                    raise ValueError(f"INVALID_OR_DUPLICATE_MICRO_ID:{micro_id}")
                micros[micro_id] = row
    return skills, micros


def load_thinking_taxonomy(path: Path = THINKING_PATH) -> dict[str, dict]:
    required = {"thinking_skill_id", "category", "name_zh", "name_en", "definition",
                "recognition_rule", "common_mistake", "recommended_grade_band", "status"}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError("INVALID_THINKING_TAXONOMY_SCHEMA")
        rows = list(reader)
    result = {row["thinking_skill_id"].strip(): row for row in rows}
    if len(result) != len(rows) or "" in result:
        raise ValueError("DUPLICATE_OR_BLANK_THINKING_SKILL_ID")
    return result


def build_profile(profile_type: str | ProfileType | None = None) -> AssessmentProfile:
    kind = normalize_profile_type(profile_type)
    competition_kind = kind in {ProfileType.COMPETITION, ProfileType.ELEMENTARY_COMPETITION}
    target_grades = (PRIVATE_JH_TARGET_GRADES if kind is ProfileType.PRIVATE_JH else
                     (("G3", "G4", "G5", "G6") if kind is ProfileType.ELEMENTARY_COMPETITION else
                      (("G4", "G5", "G6") if kind is ProfileType.COMPETITION else tuple())))
    foundation_grades = PRIVATE_JH_FOUNDATION_GRADES if kind is ProfileType.PRIVATE_JH else tuple()
    catalog_grades = foundation_grades + target_grades
    skills, micros = load_curriculum_catalog(catalog_grades) if catalog_grades else ({}, {})
    styles = tuple(sorted(PRIVATE_JH_STYLES)) if kind is ProfileType.PRIVATE_JH else (("COMPETITION_STRATEGY",) if competition_kind else ("STANDARD",))
    return AssessmentProfile(
        profile_id=f"{kind.value}_V1", profile_type=kind,
        grade_band=("G5-G6" if kind is ProfileType.PRIVATE_JH else
                    ("G3-G6" if kind is ProfileType.ELEMENTARY_COMPETITION else
                     ("G4-G6" if kind is ProfileType.COMPETITION else "CONFIGURED_GRADE"))),
        curriculum_grade=target_grades, curriculum_target_grade=target_grades,
        curriculum_foundation_grade=foundation_grades, difficulty_band=("FOUNDATION", "STANDARD", "ADVANCED"),
        assessment_style=styles, allowed_skill_ids=tuple(sorted(skills)),
        allowed_micro_ids=tuple(sorted(micros)), thinking_skill_enabled=competition_kind,
        cross_unit_enabled=kind is not ProfileType.STANDARD,
        time_pressure_enabled=kind is ProfileType.PRIVATE_JH, source_type="LOCAL_PRIVATE", status="ACTIVE",
    )


def checkpoint_key(fingerprint: str, profile_type: str | ProfileType | None = None) -> str:
    if not str(fingerprint or "").strip():
        raise ValueError("MISSING_FINGERPRINT")
    return f"{normalize_profile_type(profile_type).value}:{fingerprint}"


def profile_scope_status(curriculum_in_scope: bool, profile_type: str | ProfileType | None = None) -> str:
    kind = normalize_profile_type(profile_type)
    return kind.value if curriculum_in_scope else "OUT_OF_SCOPE_PROFILE"


def validate_mapping_result(result: dict[str, Any], *, grades: Iterable[str]) -> list[str]:
    """Validate IDs and separation rules. Any error makes the mapping invalid."""
    errors: list[str] = []
    try:
        profile = normalize_profile_type(result.get("profile_type"))
    except ValueError:
        return ["UNKNOWN_PROFILE"]
    catalog_grades = (PRIVATE_JH_CATALOG_GRADES if profile is ProfileType.PRIVATE_JH else
                      (("G3", "G4", "G5", "G6") if profile is ProfileType.ELEMENTARY_COMPETITION else
                       (("G4", "G5", "G6") if profile is ProfileType.COMPETITION else tuple(grades))))
    skills, micros = load_curriculum_catalog(catalog_grades)
    thinking = load_thinking_taxonomy()
    skill_id = str(result.get("primary_skill_id") or "")
    micro_id = str(result.get("primary_micro_skill_id") or "")
    out_of_scope = result.get("scope_status") == "OUT_OF_SCOPE_PROFILE"
    if result.get("scope_status") not in {profile.value, "OUT_OF_SCOPE_PROFILE"}:
        errors.append("INVALID_SCOPE_STATUS")
    if out_of_scope:
        if skill_id or micro_id or result.get("secondary_skill_ids"):
            errors.append("OUT_OF_SCOPE_MAPPED")
    else:
        if skill_id not in skills:
            errors.append("UNKNOWN_SKILL_ID")
        micro = micros.get(micro_id)
        if micro is None:
            errors.append("UNKNOWN_MICRO_SKILL_ID")
        elif skill_id and micro.get("parent_skill_id") != skill_id:
            errors.append("MICRO_PARENT_MISMATCH")
    for item in result.get("secondary_skill_ids") or []:
        if item not in skills:
            errors.append("UNKNOWN_SECONDARY_SKILL_ID")
    thinking_ids = result.get("thinking_skill_ids") or []
    primary_thinking = result.get("primary_thinking_skill_id") or ""
    for item in thinking_ids:
        if item not in thinking:
            errors.append("UNKNOWN_THINKING_SKILL_ID")
        if item in skills or item in micros:
            errors.append("THINKING_SKILL_CURRICULUM_POLLUTION")
    if primary_thinking and primary_thinking not in thinking_ids:
        errors.append("PRIMARY_THINKING_NOT_IN_THINKING_SKILLS")
    competition_profile = profile in {ProfileType.COMPETITION, ProfileType.ELEMENTARY_COMPETITION}
    if not competition_profile and (thinking_ids or result.get("competition_level") or result.get("strategy_depth")):
        errors.append("COMPETITION_METADATA_NOT_ALLOWED")
    if competition_profile:
        if result.get("competition_level") not in COMPETITION_LEVELS:
            errors.append("INVALID_COMPETITION_LEVEL")
        if primary_thinking and primary_thinking not in thinking:
            errors.append("UNKNOWN_PRIMARY_THINKING_SKILL_ID")
        if not isinstance(result.get("strategy_depth"), int) or not 1 <= result["strategy_depth"] <= 5:
            errors.append("INVALID_STRATEGY_DEPTH")
    style = result.get("assessment_style")
    if profile is ProfileType.PRIVATE_JH and not out_of_scope and style not in PRIVATE_JH_STYLES:
        errors.append("INVALID_PRIVATE_JH_STYLE")
    if profile is ProfileType.PRIVATE_JH and not out_of_scope:
        for secondary_style in result.get("secondary_assessment_styles") or []:
            if secondary_style not in PRIVATE_JH_STYLES:
                errors.append("INVALID_PRIVATE_JH_SECONDARY_STYLE")
    return sorted(set(errors))


def mapping_output_schema() -> dict[str, Any]:
    return json.loads((ROOT / "schemas/stage7_mapping_result.schema.json").read_text(encoding="utf-8"))
