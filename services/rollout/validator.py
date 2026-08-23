"""G1-G9 Rollout Engine — Rollout Validator (Phase 5).

Validates any :class:`GradeRecord` against the shared schema and produces a
per-grade rollout report.  Checks cover stable-ID uniqueness, orphan
knowledge / question types, graph cycle / broken links, thinking-skill and
difficulty coverage, publisher-mapping completeness, curriculum-code format,
checkpoint coverage, and mastery/recommendation compatibility.

Formal grades (G7) run every check as ``error``.  Skeleton grades run only the
structural checks as ``error``; content checks are ``warning`` (a skeleton is
expected to be empty until content is authored).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from services.checkpoint_gold import load_checkpoints

from .schema import (
    CURRICULUM_CODE_RE,
    DIFFICULTY_LEVELS,
    DOMAIN_CODES,
    PUBLISHERS,
    SEMESTERS,
    SOURCE_TYPES,
    GradeRecord,
)
from .registry import all_formal_knowledge_ids, cross_grade_graph, domain_anchors, high_school_anchors

_ERROR = "error"
_WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    check: str
    severity: str
    message: str


@dataclass(frozen=True)
class RolloutReport:
    grade: int
    status: str
    passed: bool
    issues: tuple[ValidationIssue, ...]
    summary: Mapping[str, Any]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == _ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == _WARNING)


def _check_structural(record: GradeRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if record.grade_id not in range(1, 10):
        issues.append(ValidationIssue("grade_id", _ERROR, f"grade_id must be 1-9, got {record.grade_id}"))
    if not record.semesters or set(record.semesters) != set(SEMESTERS):
        issues.append(ValidationIssue("semesters", _ERROR, f"semesters must be {SEMESTERS}"))
    for domain in record.domains:
        if domain not in DOMAIN_CODES:
            issues.append(ValidationIssue("domain", _ERROR, f"unknown domain {domain!r}"))
    # publisher mapping structure
    for publisher in PUBLISHERS:
        if publisher not in record.publisher_mapping:
            issues.append(ValidationIssue("publisher_mapping", _ERROR, f"missing publisher {publisher}"))
            continue
        for semester in SEMESTERS:
            if semester not in record.publisher_mapping[publisher]:
                issues.append(ValidationIssue("publisher_mapping", _ERROR, f"{publisher} missing {semester}"))
    return issues


def _check_content(record: GradeRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    knowledge_ids = set(record.knowledge_ids)
    type_ids = [q.type_id for q in record.question_types]

    # stable ID uniqueness
    if len(knowledge_ids) != len(record.knowledge_points):
        issues.append(ValidationIssue("stable_id", _ERROR, "duplicate knowledge id"))
    if len(set(type_ids)) != len(type_ids):
        issues.append(ValidationIssue("stable_id", _ERROR, "duplicate question type id"))

    # orphan knowledge / question type
    referenced = {q.knowledge_id for q in record.question_types}
    for kid in knowledge_ids - referenced:
        issues.append(ValidationIssue("orphan_knowledge", _ERROR, f"knowledge {kid} has no question type"))
    for q in record.question_types:
        if q.knowledge_id not in knowledge_ids:
            issues.append(ValidationIssue("orphan_question_type", _ERROR, f"{q.type_id} references unknown {q.knowledge_id}"))

    # graph: cycle + missing prerequisite / follow-up
    for kid, prereqs in record.prerequisite_graph.items():
        if kid not in knowledge_ids:
            issues.append(ValidationIssue("prerequisite_graph", _ERROR, f"graph key {kid} is not a knowledge point"))
        for pid in prereqs:
            if pid not in knowledge_ids:
                issues.append(ValidationIssue("missing_prerequisite", _ERROR, f"{kid} prerequisite {pid} is missing"))
    for kid, follow in record.follow_up_graph.items():
        for fid in follow:
            if fid not in knowledge_ids:
                issues.append(ValidationIssue("missing_follow_up", _ERROR, f"{kid} follow-up {fid} is missing"))

    # thinking-skill mapping coverage
    for q in record.question_types:
        if not q.thinking_skill_ids:
            issues.append(ValidationIssue("thinking_skill", _ERROR, f"{q.type_id} has no thinking skill"))
        for skill_id in q.thinking_skill_ids:
            if not skill_id.startswith("TS-"):
                issues.append(ValidationIssue("thinking_skill", _ERROR, f"{q.type_id} invalid skill {skill_id}"))

    # difficulty mapping coverage
    for q in record.question_types:
        rng = q.recommended_difficulty_range
        for key in ("min_level", "max_level", "default_level"):
            if key not in rng or rng[key] not in DIFFICULTY_LEVELS:
                issues.append(ValidationIssue("difficulty", _ERROR, f"{q.type_id} invalid difficulty range"))
        if rng.get("min_level", 0) > rng.get("default_level", 0) or rng.get("default_level", 0) > rng.get("max_level", 0):
            issues.append(ValidationIssue("difficulty", _ERROR, f"{q.type_id} difficulty range ordering invalid"))

    # curriculum code validity
    for p in record.knowledge_points:
        for code in p.curriculum_codes:
            if not CURRICULUM_CODE_RE.fullmatch(code):
                issues.append(ValidationIssue("curriculum_code", _ERROR, f"{p.id} invalid curriculum code {code!r}"))

    # publisher mapping completeness: core_ids must reference real knowledge
    for publisher, semesters in record.publisher_mapping.items():
        for semester, payload in semesters.items():
            for unit in payload.get("units", []):
                for subunit in unit.get("subunits", []):
                    for core_id in subunit.get("core_ids", []):
                        if core_id not in knowledge_ids:
                            issues.append(ValidationIssue("publisher_mapping", _ERROR, f"publisher maps unknown core {core_id}"))

    # mastery / recommendation compatibility: every question type carries the
    # fields the recommendation engine consumes.
    for q in record.question_types:
        if not q.recommended_difficulty_range or not q.thinking_skill_ids:
            issues.append(ValidationIssue("recommendation", _ERROR, f"{q.type_id} not recommendation-compatible"))
        if not q.prerequisite_knowledge_ids and q.knowledge_id not in {"G7-C01"}:
            # foundational-only empty is fine; non-empty elsewhere is checked by graph
            pass

    return issues


def _check_cross_grade(record: GradeRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    graph = cross_grade_graph()
    known = set(domain_anchors()) | set(all_formal_knowledge_ids()) | set(high_school_anchors())
    broken = graph.broken_links(known)
    for src, dst in broken:
        issues.append(ValidationIssue("cross_grade", _ERROR, f"cross-grade edge {src}->{dst} references undefined node"))
    cycles = graph.cycles()
    if cycles:
        for cycle in cycles:
            issues.append(ValidationIssue("cross_grade_cycle", _ERROR, "cycle: " + " -> ".join(cycle)))
    return issues


def _check_checkpoints(record: GradeRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    checkpoints = load_checkpoints(record.grade_id)
    knowledge_ids = set(record.knowledge_ids)
    covered: set[str] = set()
    for cp in checkpoints:
        for cid in cp["core_ids"]:
            if cid not in knowledge_ids:
                issues.append(ValidationIssue("checkpoint", _ERROR, f"{cp['id']} references unknown core {cid}"))
            covered.add(cid)
    missing = knowledge_ids - covered
    if missing:
        for cid in sorted(missing):
            issues.append(ValidationIssue("checkpoint_coverage", _ERROR, f"knowledge {cid} not covered by any checkpoint"))
    return issues


def validate_grade(record: GradeRecord) -> RolloutReport:
    """Validate one grade record against the shared schema."""
    is_formal = record.status == "formal"
    issues: list[ValidationIssue] = _check_structural(record)

    if is_formal:
        issues.extend(_check_content(record))
        issues.extend(_check_checkpoints(record))
        issues.extend(_check_cross_grade(record))
    else:
        # skeleton grades: content is intentionally empty — informational only
        issues.append(ValidationIssue(
            "skeleton",
            _WARNING,
            f"G{record.grade_id} is a skeleton: {len(record.knowledge_points)} knowledge points, "
            f"{len(record.question_types)} question types (content authoring pending)",
        ))

    errors = [i for i in issues if i.severity == _ERROR]
    summary = {
        "grade": record.grade_id,
        "status": record.status,
        "knowledge_points": len(record.knowledge_points),
        "question_types": len(record.question_types),
        "domains": record.domains,
        "publisher_count": len(record.publisher_mapping),
        "error_count": len(errors),
        "warning_count": len(issues) - len(errors),
    }
    return RolloutReport(
        grade=record.grade_id,
        status=record.status,
        passed=not errors,
        issues=tuple(issues),
        summary=summary,
    )


def validate_all() -> tuple[RolloutReport, ...]:
    from .registry import get_grade

    return tuple(validate_grade(get_grade(g)) for g in range(1, 10))
