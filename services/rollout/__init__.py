"""G1-G9 Learning Map Rollout Engine.

Shared, grade-agnostic infrastructure built on top of the G7 Gold Template:
schema (Phase 1), grade registry + cross-grade graph + publisher framework
(Phases 2-4), rollout validator (Phase 5), and grade template generator
(Phase 6).
"""

from .schema import (
    CURRICULUM_CODE_RE,
    DIFFICULTY_LEVELS,
    DOMAIN_CODES,
    ERROR_TAXONOMY,
    PUBLISHERS,
    SEMESTERS,
    GradeRecord,
    KnowledgePoint,
    QuestionTypeRecord,
)
from .registry import (
    CrossGradeGraph,
    all_formal_knowledge_ids,
    cross_grade_graph,
    domain_anchors,
    get_grade,
    high_school_anchors,
    list_grades,
)
from .validator import RolloutReport, validate_all, validate_grade
from .generator import generate_grade_template, scaffold_grade
from .recommendation import RecommendationStep, recommend_for_record

__all__ = [
    "CURRICULUM_CODE_RE",
    "DIFFICULTY_LEVELS",
    "DOMAIN_CODES",
    "ERROR_TAXONOMY",
    "PUBLISHERS",
    "SEMESTERS",
    "GradeRecord",
    "KnowledgePoint",
    "QuestionTypeRecord",
    "CrossGradeGraph",
    "all_formal_knowledge_ids",
    "cross_grade_graph",
    "domain_anchors",
    "get_grade",
    "high_school_anchors",
    "list_grades",
    "RolloutReport",
    "validate_all",
    "validate_grade",
    "generate_grade_template",
    "scaffold_grade",
    "RecommendationStep",
    "recommend_for_record",
]
