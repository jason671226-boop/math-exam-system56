from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


KNOWLEDGE_ID_RE = re.compile(r"^G[5-9]-K\d{3}$")
SCHEMA_VERSION = "1.0"
DEFAULT_KNOWLEDGE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "learning_map_g6_pilot.json"
)


class CatalogValidationError(ValueError):
    """Raised when a catalog file is readable JSON but violates the MathAI schema."""


@dataclass(frozen=True)
class KnowledgePoint:
    id: str
    grade: int
    domain: str
    ability_tags: tuple[str, ...]
    main_unit: str
    sub_unit: str
    learning_focus: str
    question_types: tuple[str, ...]
    curriculum_codes: tuple[str, ...]
    description: str
    sort_order: int
    official_mapping_status: str
    learning_scope: str
    private_school_weight_status: str
    prerequisite_ids: tuple[str, ...]
    active: bool


@dataclass(frozen=True)
class KnowledgeCatalog:
    schema_version: str
    grade: int
    display_name: str
    pilot_status: str
    knowledge_points: tuple[KnowledgePoint, ...]

    def by_id(self) -> dict[str, KnowledgePoint]:
        return {item.id: item for item in self.knowledge_points}


def _require_non_empty_text(value: Any, field: str, point_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{point_id}: {field} must be a non-empty string")
    return value.strip()


def _require_text_list(value: Any, field: str, point_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise CatalogValidationError(f"{point_id}: {field} must be a list of strings")
    return tuple(v.strip() for v in value if v.strip())


def validate_knowledge_catalog(data: Any) -> KnowledgeCatalog:
    if not isinstance(data, dict):
        raise CatalogValidationError("knowledge catalog root must be an object")

    schema_version = _require_non_empty_text(data.get("schema_version"), "schema_version", "root")
    if schema_version != SCHEMA_VERSION:
        raise CatalogValidationError(f"root: schema_version must be {SCHEMA_VERSION!r}")
    display_name = _require_non_empty_text(data.get("display_name"), "display_name", "root")
    pilot_status = _require_non_empty_text(data.get("pilot_status"), "pilot_status", "root")

    grade = data.get("grade")
    if grade not in range(5, 10):
        raise CatalogValidationError("root: grade must be from 5 to 9")

    raw_points = data.get("knowledge_points")
    if not isinstance(raw_points, list) or not raw_points:
        raise CatalogValidationError("root: knowledge_points must be a non-empty list")

    seen: set[str] = set()
    points: list[KnowledgePoint] = []
    allowed_mapping = {"pending_verification", "verified"}
    allowed_learning_scopes = {"general_foundation", "enrichment", "extension"}
    allowed_weight = {"not_assigned", "draft", "verified"}

    for index, raw in enumerate(raw_points, start=1):
        if not isinstance(raw, dict):
            raise CatalogValidationError(f"knowledge_points[{index}] must be an object")

        point_id = _require_non_empty_text(raw.get("id"), "id", f"knowledge_points[{index}]")
        if not KNOWLEDGE_ID_RE.fullmatch(point_id):
            raise CatalogValidationError(
                f"{point_id}: id must match G5-K### through G9-K###"
            )
        if not point_id.startswith(f"G{grade}-K"):
            raise CatalogValidationError(
                f"{point_id}: id grade must match catalog grade {grade}"
            )
        if point_id in seen:
            raise CatalogValidationError(f"duplicate knowledge point id: {point_id}")
        seen.add(point_id)

        point_grade = raw.get("grade")
        if point_grade != grade:
            raise CatalogValidationError(
                f"{point_id}: grade {point_grade!r} must match catalog grade {grade}"
            )

        official_mapping_status = _require_non_empty_text(
            raw.get("official_mapping_status"), "official_mapping_status", point_id
        )
        if official_mapping_status not in allowed_mapping:
            raise CatalogValidationError(
                f"{point_id}: unsupported official_mapping_status {official_mapping_status!r}"
            )

        learning_scope = _require_non_empty_text(
            raw.get("learning_scope", "general_foundation"),
            "learning_scope",
            point_id,
        )
        if learning_scope not in allowed_learning_scopes:
            raise CatalogValidationError(
                f"{point_id}: unsupported learning_scope {learning_scope!r}"
            )

        private_school_weight_status = _require_non_empty_text(
            raw.get("private_school_weight_status"),
            "private_school_weight_status",
            point_id,
        )
        if private_school_weight_status not in allowed_weight:
            raise CatalogValidationError(
                f"{point_id}: unsupported private_school_weight_status {private_school_weight_status!r}"
            )

        sort_order = raw.get("sort_order")
        if not isinstance(sort_order, int) or sort_order < 0:
            raise CatalogValidationError(f"{point_id}: sort_order must be a non-negative integer")

        active = raw.get("active", True)
        if not isinstance(active, bool):
            raise CatalogValidationError(f"{point_id}: active must be boolean")

        points.append(
            KnowledgePoint(
                id=point_id,
                grade=point_grade,
                domain=_require_non_empty_text(raw.get("domain"), "domain", point_id),
                ability_tags=_require_text_list(raw.get("ability_tags", []), "ability_tags", point_id),
                main_unit=_require_non_empty_text(raw.get("main_unit"), "main_unit", point_id),
                sub_unit=_require_non_empty_text(raw.get("sub_unit"), "sub_unit", point_id),
                learning_focus=_require_non_empty_text(
                    raw.get("learning_focus"), "learning_focus", point_id
                ),
                question_types=_require_text_list(raw.get("question_types"), "question_types", point_id),
                curriculum_codes=_require_text_list(
                    raw.get("curriculum_codes", []), "curriculum_codes", point_id
                ),
                description=str(raw.get("description", "")).strip(),
                sort_order=sort_order,
                official_mapping_status=official_mapping_status,
                learning_scope=learning_scope,
                private_school_weight_status=private_school_weight_status,
                prerequisite_ids=_require_text_list(
                    raw.get("prerequisite_ids", []), "prerequisite_ids", point_id
                ),
                active=active,
            )
        )

    point_ids = {point.id for point in points}
    for point in points:
        missing_prerequisites = set(point.prerequisite_ids) - point_ids
        invalid_missing = {
            prerequisite_id
            for prerequisite_id in missing_prerequisites
            if int(prerequisite_id[1]) >= grade
        }
        if invalid_missing:
            raise CatalogValidationError(
                f"{point.id}: unknown or future-grade prerequisite ids {sorted(invalid_missing)}"
            )
        if point.id in point.prerequisite_ids:
            raise CatalogValidationError(
                f"{point.id}: a knowledge point cannot require itself"
            )

    return KnowledgeCatalog(
        schema_version=schema_version,
        grade=grade,
        display_name=display_name,
        pilot_status=pilot_status,
        knowledge_points=tuple(sorted(points, key=lambda p: p.sort_order)),
    )


def load_knowledge_catalog(path: str | Path | None = None) -> KnowledgeCatalog:
    catalog_path = Path(path) if path is not None else DEFAULT_KNOWLEDGE_PATH
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogValidationError(f"knowledge catalog not found: {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogValidationError(
            f"invalid JSON in knowledge catalog {catalog_path}: line {exc.lineno} column {exc.colno}"
        ) from exc
    return validate_knowledge_catalog(raw)


def iter_knowledge_ids(catalog: KnowledgeCatalog) -> Iterable[str]:
    return (item.id for item in catalog.knowledge_points)
