from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .knowledge_loader import (
    CatalogValidationError,
    KNOWLEDGE_ID_RE,
    SCHEMA_VERSION,
    load_knowledge_catalog,
)
from .thinking_loader import load_thinking_catalog


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DIAGNOSTIC_PATH = DATA_DIR / "diagnostic_questions_g6_pilot_v1.json"
DEFAULT_ERROR_TYPES_PATH = DATA_DIR / "error_types_v1.json"
DEFAULT_PROFILE = "G6_PRIVATE_SCHOOL_PILOT"
DEFAULT_PROFILES_BY_GRADE = {
    5: "G5_PREREQUISITE_BASELINE",
    6: "G6_PRIVATE_SCHOOL_PILOT",
    7: "G7_GENERAL_BASELINE",
    8: "G8_GENERAL_BASELINE",
    9: "G9_GENERAL_BASELINE",
}

ALLOWED_ANSWER_TYPES = {"numeric", "ordered_list", "ratio", "multipart"}
ALLOWED_MASTERY_BANDS = {"basic", "standard", "advanced"}
ALLOWED_ERROR_CATEGORIES = {
    "knowledge",
    "reading",
    "representation",
    "strategy",
    "execution",
    "verification",
}
ALLOWED_SEVERITIES = {"low", "medium", "high"}


@dataclass(frozen=True)
class DifficultySpec:
    level: int
    mastery_band: str


@dataclass(frozen=True)
class HintPolicy:
    allowed: bool
    max_hints: int


@dataclass(frozen=True)
class SolutionSpec:
    summary: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class DiagnosticQuestion:
    question_id: str
    schema_version: str
    active: bool
    target_profiles: tuple[str, ...]
    section: str
    sequence: int
    prompt: str
    answer_spec: dict[str, Any]
    knowledge_points: tuple[str, ...]
    primary_thinking_skills: tuple[str, ...]
    supporting_thinking_skills: tuple[str, ...]
    difficulty: DifficultySpec
    expected_time_seconds: int
    hint_policy: HintPolicy
    solution: SolutionSpec
    error_type_ids: tuple[str, ...]
    error_rules: tuple[dict[str, Any], ...]
    visualization: str | None


@dataclass(frozen=True)
class DiagnosticQuestionCatalog:
    schema_version: str
    display_name: str
    target_profile: str
    questions: tuple[DiagnosticQuestion, ...]

    def by_id(self) -> dict[str, DiagnosticQuestion]:
        return {item.question_id: item for item in self.questions}


@dataclass(frozen=True)
class ErrorType:
    id: str
    name: str
    category: str
    description: str
    related_knowledge_points: tuple[str, ...]
    related_thinking_skills: tuple[str, ...]
    severity: str
    remediation_type: str
    active: bool


@dataclass(frozen=True)
class ErrorTypeCatalog:
    schema_version: str
    display_name: str
    error_types: tuple[ErrorType, ...]

    def by_id(self) -> dict[str, ErrorType]:
        return {item.id: item for item in self.error_types}


@dataclass(frozen=True)
class DiagnosticCatalogProfile:
    grade: int
    knowledge_path: Path
    diagnostic_path: Path | None = None
    error_types_path: Path = DEFAULT_ERROR_TYPES_PATH
    additional_knowledge_paths: tuple[Path, ...] = ()


CATALOG_PROFILES: dict[str, DiagnosticCatalogProfile] = {
    DEFAULT_PROFILE: DiagnosticCatalogProfile(
        grade=6,
        knowledge_path=DATA_DIR / "learning_map_g6_pilot.json",
        diagnostic_path=DEFAULT_DIAGNOSTIC_PATH,
    ),
    "G5_PREREQUISITE_BASELINE": DiagnosticCatalogProfile(
        grade=5,
        knowledge_path=DATA_DIR / "learning_map_g5_baseline.json",
        diagnostic_path=DATA_DIR / "diagnostic_questions_g5_baseline_v1.json",
    ),
    "G5_COMPETITION_CORE": DiagnosticCatalogProfile(
        grade=5,
        knowledge_path=DATA_DIR / "learning_map_g5_baseline.json",
        diagnostic_path=DATA_DIR / "diagnostic_questions_g5_competition_core_v1.json",
    ),
    "G6_COMPETITION_CORE": DiagnosticCatalogProfile(
        grade=6,
        knowledge_path=DATA_DIR / "learning_map_g6_pilot.json",
        diagnostic_path=DATA_DIR / "diagnostic_questions_g6_competition_core_v1.json",
        additional_knowledge_paths=(DATA_DIR / "learning_map_g5_baseline.json",),
    ),
    "G7_GENERAL_BASELINE": DiagnosticCatalogProfile(
        grade=7, knowledge_path=DATA_DIR / "learning_map_g7_baseline.json",
        diagnostic_path=DATA_DIR / "diagnostic_questions_g7_baseline_v1.json",
        additional_knowledge_paths=(DATA_DIR / "learning_map_g6_pilot.json", DATA_DIR / "learning_map_g5_baseline.json"),
    ),
    "G8_GENERAL_BASELINE": DiagnosticCatalogProfile(
        grade=8, knowledge_path=DATA_DIR / "learning_map_g8_baseline.json",
        diagnostic_path=DATA_DIR / "diagnostic_questions_g8_baseline_v1.json",
        additional_knowledge_paths=(DATA_DIR / "learning_map_g7_baseline.json", DATA_DIR / "learning_map_g6_pilot.json", DATA_DIR / "learning_map_g5_baseline.json"),
    ),
    "G9_GENERAL_BASELINE": DiagnosticCatalogProfile(
        grade=9, knowledge_path=DATA_DIR / "learning_map_g9_baseline.json",
        diagnostic_path=DATA_DIR / "diagnostic_questions_g9_baseline_v1.json",
        additional_knowledge_paths=(DATA_DIR / "learning_map_g8_baseline.json", DATA_DIR / "learning_map_g7_baseline.json", DATA_DIR / "learning_map_g6_pilot.json", DATA_DIR / "learning_map_g5_baseline.json"),
    ),
}


def register_catalog_profile(
    profile: str,
    *,
    grade: int,
    knowledge_path: str | Path,
    diagnostic_path: str | Path | None = None,
    error_types_path: str | Path = DEFAULT_ERROR_TYPES_PATH,
) -> None:
    """Register catalog paths for a G5-G9 diagnostic profile."""

    profile_id = _text(profile, "profile", "profile")
    if grade not in range(5, 10):
        raise CatalogValidationError("profile: grade must be from 5 to 9")
    CATALOG_PROFILES[profile_id] = DiagnosticCatalogProfile(
        grade=grade,
        knowledge_path=Path(knowledge_path),
        diagnostic_path=Path(diagnostic_path) if diagnostic_path is not None else None,
        error_types_path=Path(error_types_path),
    )


def get_catalog_profile(
    *, profile: str | None = None, grade: int | None = None
) -> tuple[str, DiagnosticCatalogProfile]:
    """Resolve one unambiguous registered profile by id and/or grade."""

    if profile is not None:
        try:
            selected = CATALOG_PROFILES[profile]
        except KeyError as exc:
            raise CatalogValidationError(f"unknown diagnostic profile: {profile}") from exc
        if grade is not None and selected.grade != grade:
            raise CatalogValidationError(
                f"profile {profile} is grade {selected.grade}, not grade {grade}"
            )
        return profile, selected

    if grade is None:
        return DEFAULT_PROFILE, CATALOG_PROFILES[DEFAULT_PROFILE]
    default_for_grade = DEFAULT_PROFILES_BY_GRADE.get(grade)
    if default_for_grade is not None:
        return default_for_grade, CATALOG_PROFILES[default_for_grade]
    matches = [(key, item) for key, item in CATALOG_PROFILES.items() if item.grade == grade]
    if len(matches) != 1:
        raise CatalogValidationError(
            f"grade {grade} requires exactly one registered profile; found {len(matches)}"
        )
    return matches[0]


def load_profile_knowledge_catalog(
    *, profile: str | None = None, grade: int | None = None
):
    """Load the Knowledge catalog registered for one grade/profile."""

    _, config = get_catalog_profile(profile=profile, grade=grade)
    primary = load_knowledge_catalog(config.knowledge_path)
    if not config.additional_knowledge_paths:
        return primary
    additional = tuple(
        load_knowledge_catalog(path) for path in config.additional_knowledge_paths
    )
    points = (*primary.knowledge_points, *(point for catalog in additional for point in catalog.knowledge_points))
    if len({point.id for point in points}) != len(points):
        raise CatalogValidationError("profile knowledge catalogs contain duplicate IDs")
    point_ids = {point.id for point in points}
    for point in points:
        missing = set(point.prerequisite_ids) - point_ids
        if missing:
            raise CatalogValidationError(
                f"{point.id}: profile is missing prerequisite ids {sorted(missing)}"
            )
    return type(primary)(
        schema_version=primary.schema_version,
        grade=primary.grade,
        display_name=f"{primary.display_name} + prerequisite knowledge",
        pilot_status=primary.pilot_status,
        knowledge_points=points,
    )


def _text(value: Any, field: str, owner: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{owner}: {field} must be a non-empty string")
    return value.strip()


def _text_list(value: Any, field: str, owner: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise CatalogValidationError(f"{owner}: {field} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise CatalogValidationError(f"{owner}: {field} must not be empty")
    return tuple(v.strip() for v in value)


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogValidationError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogValidationError(
            f"invalid JSON in {label} {path}: line {exc.lineno} column {exc.colno}"
        ) from exc


def validate_error_types(
    data: Any,
    *,
    knowledge_catalog=None,
    thinking_catalog=None,
    require_local_knowledge: bool = True,
) -> ErrorTypeCatalog:
    if not isinstance(data, dict):
        raise CatalogValidationError("error type catalog root must be an object")

    schema_version = _text(data.get("schema_version"), "schema_version", "root")
    if schema_version != SCHEMA_VERSION:
        raise CatalogValidationError(f"root: schema_version must be {SCHEMA_VERSION!r}")
    display_name = _text(data.get("display_name"), "display_name", "root")
    raw_items = data.get("error_types")
    if not isinstance(raw_items, list) or not raw_items:
        raise CatalogValidationError("root: error_types must be a non-empty list")

    knowledge_catalog = knowledge_catalog or load_knowledge_catalog()
    thinking_catalog = thinking_catalog or load_thinking_catalog()
    knowledge_ids = set(knowledge_catalog.by_id())
    thinking_ids = set(thinking_catalog.by_id())

    seen: set[str] = set()
    items: list[ErrorType] = []
    for index, raw in enumerate(raw_items, start=1):
        owner = f"error_types[{index}]"
        if not isinstance(raw, dict):
            raise CatalogValidationError(f"{owner} must be an object")

        error_id = _text(raw.get("id"), "id", owner)
        if error_id in seen:
            raise CatalogValidationError(f"duplicate error type id: {error_id}")
        seen.add(error_id)

        category = _text(raw.get("category"), "category", error_id)
        if category not in ALLOWED_ERROR_CATEGORIES:
            raise CatalogValidationError(f"{error_id}: unsupported category {category!r}")

        severity = _text(raw.get("severity"), "severity", error_id)
        if severity not in ALLOWED_SEVERITIES:
            raise CatalogValidationError(f"{error_id}: unsupported severity {severity!r}")

        active = raw.get("active")
        if not isinstance(active, bool):
            raise CatalogValidationError(f"{error_id}: active must be boolean")

        related_knowledge = _text_list(
            raw.get("related_knowledge_points", []),
            "related_knowledge_points",
            error_id,
        )
        missing_knowledge = set(related_knowledge) - knowledge_ids
        invalid_knowledge = {
            item for item in related_knowledge if not KNOWLEDGE_ID_RE.fullmatch(item)
        }
        if invalid_knowledge:
            raise CatalogValidationError(
                f"{error_id}: invalid knowledge ids {sorted(invalid_knowledge)}"
            )
        if require_local_knowledge and missing_knowledge:
            raise CatalogValidationError(
                f"{error_id}: unknown knowledge ids {sorted(missing_knowledge)}"
            )

        related_thinking = _text_list(
            raw.get("related_thinking_skills", []),
            "related_thinking_skills",
            error_id,
        )
        missing_thinking = set(related_thinking) - thinking_ids
        if missing_thinking:
            raise CatalogValidationError(
                f"{error_id}: unknown thinking ids {sorted(missing_thinking)}"
            )

        items.append(
            ErrorType(
                id=error_id,
                name=_text(raw.get("name"), "name", error_id),
                category=category,
                description=_text(raw.get("description"), "description", error_id),
                related_knowledge_points=related_knowledge,
                related_thinking_skills=related_thinking,
                severity=severity,
                remediation_type=_text(
                    raw.get("remediation_type"), "remediation_type", error_id
                ),
                active=active,
            )
        )

    return ErrorTypeCatalog(
        schema_version=schema_version,
        display_name=display_name,
        error_types=tuple(items),
    )


def load_error_types(path: str | Path | None = None) -> ErrorTypeCatalog:
    catalog_path = Path(path) if path is not None else DEFAULT_ERROR_TYPES_PATH
    return validate_error_types(
        _read_json(catalog_path, "error type catalog"),
        require_local_knowledge=False,
    )


def _validate_answer_spec(
    spec: Any,
    question_id: str,
    *,
    knowledge_ids: set[str],
    thinking_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise CatalogValidationError(f"{question_id}: answer_spec must be an object")

    answer_type = _text(spec.get("type"), "answer_spec.type", question_id)
    if answer_type not in ALLOWED_ANSWER_TYPES:
        raise CatalogValidationError(
            f"{question_id}: unsupported answer_spec.type {answer_type!r}"
        )

    if answer_type == "multipart":
        raw_parts = spec.get("parts")
        if not isinstance(raw_parts, list) or len(raw_parts) < 2:
            raise CatalogValidationError(
                f"{question_id}: multipart answer_spec must contain at least 2 parts"
            )
        seen_parts: set[str] = set()
        clean_parts: list[dict[str, Any]] = []
        for index, raw_part in enumerate(raw_parts, start=1):
            if not isinstance(raw_part, dict):
                raise CatalogValidationError(
                    f"{question_id}: multipart part {index} must be an object"
                )
            part_id = _text(raw_part.get("part_id"), "part_id", question_id)
            if part_id in seen_parts:
                raise CatalogValidationError(
                    f"{question_id}: duplicate multipart part_id {part_id!r}"
                )
            seen_parts.add(part_id)
            part_type = _text(raw_part.get("answer_type"), "answer_type", question_id)
            if part_type not in {"numeric", "ratio"}:
                raise CatalogValidationError(
                    f"{question_id}: unsupported multipart answer_type {part_type!r}"
                )
            accepted = raw_part.get("accepted_answers")
            if not isinstance(accepted, list) or not accepted:
                raise CatalogValidationError(
                    f"{question_id}: multipart part {part_id} needs accepted_answers"
                )
            clean_part = dict(raw_part)
            for field in (
                "knowledge_points",
                "primary_thinking_skills",
                "supporting_thinking_skills",
            ):
                if field not in raw_part:
                    continue
                values = _text_list(raw_part[field], field, f"{question_id}.{part_id}")
                allowed_ids = knowledge_ids if field == "knowledge_points" else thinking_ids
                missing = set(values) - allowed_ids
                if missing:
                    raise CatalogValidationError(
                        f"{question_id}.{part_id}: unknown {field} ids {sorted(missing)}"
                    )
                clean_part[field] = list(values)
            clean_parts.append(clean_part)
        result = dict(spec)
        result["parts"] = clean_parts
        return result

    accepted = spec.get("accepted_answers")
    if not isinstance(accepted, list) or not accepted:
        raise CatalogValidationError(
            f"{question_id}: answer_spec.accepted_answers must be a non-empty list"
        )
    if answer_type in {"numeric", "ratio"} and any(
        not isinstance(value, (str, int, float)) or isinstance(value, bool)
        for value in accepted
    ):
        raise CatalogValidationError(
            f"{question_id}: accepted_answers must contain scalar answers"
        )
    if answer_type == "ordered_list":
        if any(
            not isinstance(order, list)
            or not order
            or any(not isinstance(value, str) or not value.strip() for value in order)
            for order in accepted
        ):
            raise CatalogValidationError(
                f"{question_id}: ordered_list accepted_answers must be lists of strings"
            )
    return dict(spec)


def validate_diagnostic_catalog(
    data: Any,
    *,
    error_catalog: ErrorTypeCatalog | None = None,
    knowledge_catalog=None,
    thinking_catalog=None,
) -> DiagnosticQuestionCatalog:
    if not isinstance(data, dict):
        raise CatalogValidationError("diagnostic catalog root must be an object")

    schema_version = _text(data.get("schema_version"), "schema_version", "root")
    if schema_version != SCHEMA_VERSION:
        raise CatalogValidationError(
            f"root: schema_version must be {SCHEMA_VERSION!r}"
        )
    display_name = _text(data.get("display_name"), "display_name", "root")
    target_profile = _text(data.get("target_profile"), "target_profile", "root")
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise CatalogValidationError("root: questions must be a non-empty list")

    knowledge_catalog = knowledge_catalog or load_knowledge_catalog()
    thinking_catalog = thinking_catalog or load_thinking_catalog()
    error_catalog = error_catalog or load_error_types()

    knowledge_ids = set(knowledge_catalog.by_id())
    thinking_ids = set(thinking_catalog.by_id())
    error_ids = set(error_catalog.by_id())

    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    questions: list[DiagnosticQuestion] = []

    for index, raw in enumerate(raw_questions, start=1):
        owner = f"questions[{index}]"
        if not isinstance(raw, dict):
            raise CatalogValidationError(f"{owner} must be an object")

        required_fields = {
            "question_id",
            "schema_version",
            "active",
            "target_profiles",
            "section",
            "sequence",
            "prompt",
            "answer_spec",
            "knowledge_points",
            "primary_thinking_skills",
            "supporting_thinking_skills",
            "difficulty",
            "expected_time_seconds",
            "hint_policy",
            "solution",
            "error_type_ids",
        }
        missing = sorted(required_fields - set(raw))
        if missing:
            raise CatalogValidationError(
                f"{owner}: missing required fields {missing}"
            )

        question_id = _text(raw.get("question_id"), "question_id", owner)
        if question_id in seen_ids:
            raise CatalogValidationError(f"duplicate question_id: {question_id}")
        seen_ids.add(question_id)
        question_schema_version = _text(
            raw.get("schema_version"), "schema_version", question_id
        )
        if question_schema_version != schema_version:
            raise CatalogValidationError(
                f"{question_id}: schema_version must match catalog schema_version"
            )

        active = raw.get("active")
        if not isinstance(active, bool):
            raise CatalogValidationError(f"{question_id}: active must be boolean")

        sequence = raw.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise CatalogValidationError(
                f"{question_id}: sequence must be a positive integer"
            )
        if sequence in seen_sequences:
            raise CatalogValidationError(f"duplicate sequence: {sequence}")
        seen_sequences.add(sequence)

        knowledge_points = _text_list(
            raw.get("knowledge_points"),
            "knowledge_points",
            question_id,
            allow_empty=False,
        )
        missing_knowledge = set(knowledge_points) - knowledge_ids
        if missing_knowledge:
            raise CatalogValidationError(
                f"{question_id}: unknown knowledge ids {sorted(missing_knowledge)}"
            )

        primary = _text_list(
            raw.get("primary_thinking_skills"),
            "primary_thinking_skills",
            question_id,
            allow_empty=False,
        )
        supporting = _text_list(
            raw.get("supporting_thinking_skills"),
            "supporting_thinking_skills",
            question_id,
        )
        missing_thinking = (set(primary) | set(supporting)) - thinking_ids
        if missing_thinking:
            raise CatalogValidationError(
                f"{question_id}: unknown thinking ids {sorted(missing_thinking)}"
            )

        error_type_ids = _text_list(
            raw.get("error_type_ids"),
            "error_type_ids",
            question_id,
        )
        missing_errors = set(error_type_ids) - error_ids
        if missing_errors:
            raise CatalogValidationError(
                f"{question_id}: unknown error ids {sorted(missing_errors)}"
            )

        raw_error_rules = raw.get("error_rules", [])
        if not isinstance(raw_error_rules, list):
            raise CatalogValidationError(f"{question_id}: error_rules must be a list")
        error_rules: list[dict[str, Any]] = []
        for rule_index, rule in enumerate(raw_error_rules, start=1):
            owner_rule = f"{question_id}.error_rules[{rule_index}]"
            if not isinstance(rule, dict):
                raise CatalogValidationError(f"{owner_rule} must be an object")
            rule_type = _text(rule.get("type"), "type", owner_rule)
            error_type_id = _text(rule.get("error_type_id"), "error_type_id", owner_rule)
            if error_type_id not in error_ids or error_type_id not in error_type_ids:
                raise CatalogValidationError(
                    f"{owner_rule}: error_type_id must be declared by the question"
                )
            confidence = rule.get("confidence")
            if (
                not isinstance(confidence, (int, float))
                or isinstance(confidence, bool)
                or not 0.0 <= confidence <= 1.0
            ):
                raise CatalogValidationError(f"{owner_rule}: confidence must be 0..1")
            if rule_type == "answer_equals" and "answer" not in rule:
                raise CatalogValidationError(f"{owner_rule}: answer is required")
            error_rules.append(dict(rule))

        raw_difficulty = raw.get("difficulty")
        if not isinstance(raw_difficulty, dict):
            raise CatalogValidationError(
                f"{question_id}: difficulty must be an object"
            )
        level = raw_difficulty.get("level")
        if (
            not isinstance(level, int)
            or isinstance(level, bool)
            or level < 1
            or level > 5
        ):
            raise CatalogValidationError(
                f"{question_id}: difficulty.level must be 1..5"
            )
        mastery_band = _text(
            raw_difficulty.get("mastery_band"),
            "difficulty.mastery_band",
            question_id,
        )
        if mastery_band not in ALLOWED_MASTERY_BANDS:
            raise CatalogValidationError(
                f"{question_id}: unsupported mastery_band {mastery_band!r}"
            )

        expected_time = raw.get("expected_time_seconds")
        if (
            not isinstance(expected_time, int)
            or isinstance(expected_time, bool)
            or expected_time <= 0
        ):
            raise CatalogValidationError(
                f"{question_id}: expected_time_seconds must be a positive integer"
            )

        raw_hint = raw.get("hint_policy")
        if not isinstance(raw_hint, dict):
            raise CatalogValidationError(
                f"{question_id}: hint_policy must be an object"
            )
        hint_allowed = raw_hint.get("allowed")
        max_hints = raw_hint.get("max_hints")
        if not isinstance(hint_allowed, bool):
            raise CatalogValidationError(
                f"{question_id}: hint_policy.allowed must be boolean"
            )
        if (
            not isinstance(max_hints, int)
            or isinstance(max_hints, bool)
            or max_hints < 0
        ):
            raise CatalogValidationError(
                f"{question_id}: hint_policy.max_hints must be non-negative integer"
            )
        if not hint_allowed and max_hints != 0:
            raise CatalogValidationError(
                f"{question_id}: max_hints must be 0 when hints are disabled"
            )

        raw_solution = raw.get("solution")
        if not isinstance(raw_solution, dict):
            raise CatalogValidationError(
                f"{question_id}: solution must be an object"
            )
        solution_steps = _text_list(
            raw_solution.get("steps"), "solution.steps", question_id, allow_empty=False
        )

        questions.append(
            DiagnosticQuestion(
                question_id=question_id,
                schema_version=question_schema_version,
                active=active,
                target_profiles=_text_list(
                    raw.get("target_profiles"),
                    "target_profiles",
                    question_id,
                    allow_empty=False,
                ),
                section=_text(raw.get("section"), "section", question_id),
                sequence=sequence,
                prompt=_text(raw.get("prompt"), "prompt", question_id),
                answer_spec=_validate_answer_spec(
                    raw.get("answer_spec"), question_id,
                    knowledge_ids=knowledge_ids,
                    thinking_ids=thinking_ids,
                ),
                knowledge_points=knowledge_points,
                primary_thinking_skills=primary,
                supporting_thinking_skills=supporting,
                difficulty=DifficultySpec(level=level, mastery_band=mastery_band),
                expected_time_seconds=expected_time,
                hint_policy=HintPolicy(
                    allowed=hint_allowed, max_hints=max_hints
                ),
                solution=SolutionSpec(
                    summary=_text(
                        raw_solution.get("summary"), "solution.summary", question_id
                    ),
                    steps=solution_steps,
                ),
                error_type_ids=error_type_ids,
                error_rules=tuple(error_rules),
                visualization=(
                    _text(raw["visualization"], "visualization", question_id)
                    if raw.get("visualization") is not None
                    else None
                ),
            )
        )

    return DiagnosticQuestionCatalog(
        schema_version=schema_version,
        display_name=display_name,
        target_profile=target_profile,
        questions=tuple(sorted(questions, key=lambda q: q.sequence)),
    )


def load_diagnostic_questions(
    path: str | Path | None = None,
    *,
    error_types_path: str | Path | None = None,
    knowledge_path: str | Path | None = None,
    profile: str | None = None,
    grade: int | None = None,
) -> DiagnosticQuestionCatalog:
    if path is None:
        profile_id, config = get_catalog_profile(profile=profile, grade=grade)
        if config.diagnostic_path is None:
            raise CatalogValidationError(
                f"diagnostic questions are not available for profile {profile_id}"
            )
        catalog_path = config.diagnostic_path
        knowledge_catalog_path = Path(knowledge_path) if knowledge_path else None
        errors_path = Path(error_types_path) if error_types_path else config.error_types_path
    else:
        profile_id = profile
        catalog_path = Path(path)
        knowledge_catalog_path = Path(knowledge_path) if knowledge_path else None
        errors_path = Path(error_types_path) if error_types_path else DEFAULT_ERROR_TYPES_PATH
    knowledge_catalog = (
        load_knowledge_catalog(knowledge_catalog_path)
        if knowledge_catalog_path is not None
        else load_profile_knowledge_catalog(profile=profile_id)
    )
    error_catalog = validate_error_types(
        _read_json(errors_path, "error type catalog"),
        knowledge_catalog=knowledge_catalog,
        require_local_knowledge=False,
    )
    catalog = validate_diagnostic_catalog(
        _read_json(catalog_path, "diagnostic question catalog"),
        error_catalog=error_catalog,
        knowledge_catalog=knowledge_catalog,
    )
    if profile_id is not None and catalog.target_profile != profile_id:
        raise CatalogValidationError(
            f"catalog target_profile {catalog.target_profile!r} does not match {profile_id!r}"
        )
    return catalog


def get_diagnostic_question(
    question_id: str,
    catalog: DiagnosticQuestionCatalog | None = None,
) -> DiagnosticQuestion:
    catalog = catalog or load_diagnostic_questions()
    try:
        return catalog.by_id()[question_id]
    except KeyError as exc:
        raise KeyError(f"unknown diagnostic question: {question_id}") from exc


def get_error_type(
    error_type_id: str,
    catalog: ErrorTypeCatalog | None = None,
) -> ErrorType:
    catalog = catalog or load_error_types()
    try:
        return catalog.by_id()[error_type_id]
    except KeyError as exc:
        raise KeyError(f"unknown error type: {error_type_id}") from exc
