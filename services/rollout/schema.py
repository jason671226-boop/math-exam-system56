"""G1-G9 Rollout Engine — shared, grade-agnostic schema (Phase 1).

This module holds the canonical data shapes every grade (G1-G9) must conform
to.  It intentionally contains **no G7-specific knowledge**: the grade-specific
content lives in the Grade Registry and the per-grade data files.

The grade-agnostic constants (five-level difficulty, variation methods, the
eight-category error taxonomy, evidence source types, mastery statuses) are
re-imported from the existing Gold Template modules so there is a single source
of truth, but nothing here hardcodes ``G7``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from services.g7_gold_template import (
    DIFFICULTY_LEVELS,
    ERROR_TAXONOMY,
    VARIATION_METHODS,
)
from services.evidence_mastery_gold import MASTERY_STATUSES, SOURCE_TYPES

# ---------------------------------------------------------------------------
# Curriculum / domain vocabulary (shared across G1-G9)
# ---------------------------------------------------------------------------

# Canonical 108-curriculum domains and their curriculum-code letter prefix.
DOMAIN_CODES: Mapping[str, str] = {
    "數與量": "N",
    "代數": "A",
    "空間與形狀": "S",
    "資料與不確定性": "D",
}

SEMESTERS: tuple[str, ...] = ("上學期", "下學期")
PUBLISHERS: tuple[str, ...] = ("康軒", "翰林", "南一")

# Curriculum code format: <DOMAIN_LETTER>-<GRADE>-<SEQUENCE>, e.g. "A-7-1".
# A range such as "S-7-1~S-7-5" (one core covering several codes) is also valid.
_CURRICULUM_SINGLE = r"[A-Z]+-\d+-\d+"
CURRICULUM_CODE_RE = re.compile(rf"^{_CURRICULUM_SINGLE}(~{_CURRICULUM_SINGLE})?$")

GRADE_STATUS_FORMAL = "formal"
GRADE_STATUS_SKELETON = "skeleton"


# ---------------------------------------------------------------------------
# Shared record shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KnowledgePoint:
    id: str
    grade: int
    semester: str
    domain: str
    core_topic: str
    subunit: str
    curriculum_codes: tuple[str, ...]
    prerequisite_ids: tuple[str, ...]
    follow_up_ids: tuple[str, ...]


@dataclass(frozen=True)
class QuestionTypeRecord:
    type_id: str
    knowledge_id: str
    name: str
    category: str
    difficulty: str
    solving_strategy: str
    key_steps: tuple[str, ...]
    common_error_diagnosis: Mapping[str, str]
    underlying_principle: str
    prerequisite_knowledge_ids: tuple[str, ...]
    follow_up_knowledge_ids: tuple[str, ...]
    variation_methods: tuple[Mapping[str, Any], ...]
    recommended_difficulty_range: Mapping[str, int]
    thinking_skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class GradeRecord:
    grade_id: int
    semesters: tuple[str, ...]
    domains: tuple[str, ...]
    status: str
    knowledge_points: tuple[KnowledgePoint, ...]
    question_types: tuple[QuestionTypeRecord, ...]
    publisher_mapping: Mapping[str, Any]
    prerequisite_graph: Mapping[str, tuple[str, ...]]
    follow_up_graph: Mapping[str, tuple[str, ...]]

    @property
    def knowledge_ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.knowledge_points)

    @property
    def question_type_ids(self) -> tuple[str, ...]:
        return tuple(q.type_id for q in self.question_types)


# ---------------------------------------------------------------------------
# Cross-grade graph — anchor vocabulary
# ---------------------------------------------------------------------------

def domain_anchor(grade: int, domain: str) -> str:
    """Return a stable cross-grade anchor key for a (grade, domain) pair."""
    return f"G{grade}:{domain}"


def knowledge_anchor(knowledge_id: str) -> str:
    """Return a concrete knowledge anchor key (used for G7's real IDs)."""
    return knowledge_id
