from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.catalog.knowledge_loader import (
    CatalogValidationError,
    KnowledgeCatalog,
    load_knowledge_catalog,
)


SCHEMA_VERSION = "1.0"
IMPORTANCE_LEVELS = ("high", "medium", "low")
DEFAULT_COMPETITION_WEIGHTS_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "competition_knowledge_weights_v1.json"
)
DEFAULT_KNOWLEDGE_PATHS = (
    Path(__file__).resolve().parents[1] / "data" / "learning_map_g5_baseline.json",
    Path(__file__).resolve().parents[1] / "data" / "learning_map_g6_pilot.json",
)


@dataclass(frozen=True)
class CompetitionGradeWeights:
    grade: int
    weights: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class CompetitionTrack:
    track_id: str
    display_name: str
    status: str
    grade_weights: tuple[CompetitionGradeWeights, ...]


@dataclass(frozen=True)
class CompetitionWeightingCatalog:
    schema_version: str
    status: str
    validation_status: str
    weight_basis: str
    tracks: tuple[CompetitionTrack, ...]


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{field} must be a non-empty string")
    return value.strip()


def validate_competition_weighting(
    data: Any,
    *,
    knowledge_catalogs: tuple[KnowledgeCatalog, ...],
) -> CompetitionWeightingCatalog:
    if not isinstance(data, dict):
        raise CatalogValidationError("competition weighting root must be an object")
    schema_version = _text(data.get("schema_version"), "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise CatalogValidationError(f"schema_version must be {SCHEMA_VERSION!r}")
    status = _text(data.get("status"), "status")
    validation_status = _text(data.get("validation_status"), "validation_status")
    weight_basis = _text(data.get("weight_basis"), "weight_basis")
    if status != "draft" or validation_status != "pending_validation":
        raise CatalogValidationError(
            "competition weighting must remain draft and pending_validation"
        )
    if weight_basis != "repository_asset_alignment_not_official_statistics":
        raise CatalogValidationError(
            "competition weighting must state that it is not official statistics"
        )

    knowledge_by_id = {
        point.id: point
        for catalog in knowledge_catalogs
        for point in catalog.knowledge_points
    }
    raw_tracks = data.get("tracks")
    if not isinstance(raw_tracks, list) or not raw_tracks:
        raise CatalogValidationError("tracks must be a non-empty list")

    seen_tracks: set[str] = set()
    tracks: list[CompetitionTrack] = []
    for raw_track in raw_tracks:
        if not isinstance(raw_track, dict):
            raise CatalogValidationError("each competition track must be an object")
        track_id = _text(raw_track.get("track_id"), "track_id")
        if track_id in seen_tracks:
            raise CatalogValidationError(f"duplicate competition track: {track_id}")
        seen_tracks.add(track_id)
        if raw_track.get("status") != "draft":
            raise CatalogValidationError(f"{track_id}: status must be draft")

        raw_grade_weights = raw_track.get("grade_weights")
        if not isinstance(raw_grade_weights, list) or not raw_grade_weights:
            raise CatalogValidationError(f"{track_id}: grade_weights must be non-empty")
        seen_grades: set[int] = set()
        grade_weights: list[CompetitionGradeWeights] = []
        for raw_grade in raw_grade_weights:
            grade = raw_grade.get("grade") if isinstance(raw_grade, dict) else None
            if grade not in (5, 6) or grade in seen_grades:
                raise CatalogValidationError(
                    f"{track_id}: grades must be unique and limited to 5 or 6"
                )
            seen_grades.add(grade)
            raw_weights = raw_grade.get("weights")
            if not isinstance(raw_weights, dict) or set(raw_weights) != set(IMPORTANCE_LEVELS):
                raise CatalogValidationError(
                    f"{track_id}/G{grade}: weights must contain high, medium, and low"
                )
            normalized: dict[str, tuple[str, ...]] = {}
            used_ids: set[str] = set()
            for importance in IMPORTANCE_LEVELS:
                ids = raw_weights[importance]
                if not isinstance(ids, list) or not ids or any(
                    not isinstance(item, str) for item in ids
                ):
                    raise CatalogValidationError(
                        f"{track_id}/G{grade}/{importance}: expected knowledge ID list"
                    )
                duplicate_ids = used_ids.intersection(ids)
                if duplicate_ids:
                    raise CatalogValidationError(
                        f"{track_id}/G{grade}: duplicate weighted IDs {sorted(duplicate_ids)}"
                    )
                for knowledge_id in ids:
                    point = knowledge_by_id.get(knowledge_id)
                    if point is None:
                        raise CatalogValidationError(
                            f"{track_id}/G{grade}: unknown knowledge ID {knowledge_id}"
                        )
                    if point.grade > grade:
                        raise CatalogValidationError(
                            f"{track_id}/G{grade}: cannot use future-grade point {knowledge_id}"
                        )
                used_ids.update(ids)
                normalized[importance] = tuple(ids)
            grade_weights.append(
                CompetitionGradeWeights(grade=grade, weights=normalized)
            )
        tracks.append(
            CompetitionTrack(
                track_id=track_id,
                display_name=_text(raw_track.get("display_name"), "display_name"),
                status="draft",
                grade_weights=tuple(grade_weights),
            )
        )

    return CompetitionWeightingCatalog(
        schema_version=schema_version,
        status=status,
        validation_status=validation_status,
        weight_basis=weight_basis,
        tracks=tuple(tracks),
    )


def load_competition_weighting(
    path: str | Path | None = None,
    *,
    knowledge_paths: tuple[str | Path, ...] = DEFAULT_KNOWLEDGE_PATHS,
) -> CompetitionWeightingCatalog:
    catalog_path = Path(path) if path is not None else DEFAULT_COMPETITION_WEIGHTS_PATH
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogValidationError(
            f"competition weighting catalog not found: {catalog_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CatalogValidationError(
            f"invalid JSON in competition weighting catalog: line {exc.lineno} column {exc.colno}"
        ) from exc
    catalogs = tuple(load_knowledge_catalog(item) for item in knowledge_paths)
    return validate_competition_weighting(data, knowledge_catalogs=catalogs)
