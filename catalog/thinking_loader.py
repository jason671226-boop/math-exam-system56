from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .knowledge_loader import CatalogValidationError, SCHEMA_VERSION


THINKING_ID_RE = re.compile(r"^TS-[A-Z0-9][A-Z0-9_-]*$")
DEFAULT_THINKING_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "thinking_skills_v1.json"
)


@dataclass(frozen=True)
class ThinkingSkill:
    id: str
    name: str
    category: str
    description: str
    min_grade: int
    max_grade: int
    active: bool
    sort_order: int

    @property
    def grade_band(self) -> str:
        """Human-readable compatibility label; storage remains structured."""
        return f"G{self.min_grade}-G{self.max_grade}"


@dataclass(frozen=True)
class ThinkingCatalog:
    schema_version: str
    display_name: str
    skills: tuple[ThinkingSkill, ...]

    def by_id(self) -> dict[str, ThinkingSkill]:
        return {item.id: item for item in self.skills}


def _text(value: Any, field: str, skill_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{skill_id}: {field} must be a non-empty string")
    return value.strip()


def _grade(value: Any, field: str, skill_id: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 12:
        raise CatalogValidationError(f"{skill_id}: {field} must be an integer from 1 to 12")
    return value


def validate_thinking_catalog(data: Any) -> ThinkingCatalog:
    if not isinstance(data, dict):
        raise CatalogValidationError("thinking catalog root must be an object")

    schema_version = _text(data.get("schema_version"), "schema_version", "root")
    if schema_version != SCHEMA_VERSION:
        raise CatalogValidationError(f"root: schema_version must be {SCHEMA_VERSION!r}")
    display_name = _text(data.get("display_name"), "display_name", "root")
    raw_skills = data.get("skills")
    if not isinstance(raw_skills, list) or not raw_skills:
        raise CatalogValidationError("root: skills must be a non-empty list")

    seen: set[str] = set()
    skills: list[ThinkingSkill] = []
    for index, raw in enumerate(raw_skills, start=1):
        if not isinstance(raw, dict):
            raise CatalogValidationError(f"skills[{index}] must be an object")
        skill_id = _text(raw.get("id"), "id", f"skills[{index}]")
        if not THINKING_ID_RE.fullmatch(skill_id):
            raise CatalogValidationError(f"{skill_id}: invalid Thinking Skill id")
        if skill_id in seen:
            raise CatalogValidationError(f"duplicate Thinking Skill id: {skill_id}")
        seen.add(skill_id)

        active = raw.get("active", True)
        if not isinstance(active, bool):
            raise CatalogValidationError(f"{skill_id}: active must be boolean")
        sort_order = raw.get("sort_order")
        if not isinstance(sort_order, int) or isinstance(sort_order, bool) or sort_order < 0:
            raise CatalogValidationError(f"{skill_id}: sort_order must be a non-negative integer")

        min_grade = _grade(raw.get("min_grade"), "min_grade", skill_id)
        max_grade = _grade(raw.get("max_grade"), "max_grade", skill_id)
        if min_grade > max_grade:
            raise CatalogValidationError(f"{skill_id}: min_grade cannot exceed max_grade")

        skills.append(
            ThinkingSkill(
                id=skill_id,
                name=_text(raw.get("name"), "name", skill_id),
                category=_text(raw.get("category"), "category", skill_id),
                description=_text(raw.get("description"), "description", skill_id),
                min_grade=min_grade,
                max_grade=max_grade,
                active=active,
                sort_order=sort_order,
            )
        )

    return ThinkingCatalog(
        schema_version=schema_version,
        display_name=display_name,
        skills=tuple(sorted(skills, key=lambda s: s.sort_order)),
    )


def load_thinking_catalog(path: str | Path | None = None) -> ThinkingCatalog:
    catalog_path = Path(path) if path is not None else DEFAULT_THINKING_PATH
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogValidationError(f"thinking catalog not found: {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogValidationError(
            f"invalid JSON in thinking catalog {catalog_path}: line {exc.lineno} column {exc.colno}"
        ) from exc
    return validate_thinking_catalog(raw)
