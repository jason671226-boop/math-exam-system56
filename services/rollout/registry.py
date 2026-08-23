"""G1-G9 Rollout Engine — Grade Registry, cross-grade graph, publisher framework.

Phase 2 (grade registry), Phase 3 (cross-grade prerequisite graph), and
Phase 4 (publisher mapping framework).

* ``get_grade`` returns a :class:`GradeRecord` for any grade 1-9.  G7 is
  backed by the existing formal data; every other grade is a backward-compatible
  skeleton (structure only, no formal content).
* :class:`CrossGradeGraph` models the G1 -> G2 -> ... -> G9 prerequisite /
  follow-up chains across domains, supports one-to-many / many-to-one edges,
  and detects broken links and cycles.
* The publisher mapping framework keeps the "shared core tree + publisher path
  mapping" principle: one schema reused for every grade and publisher.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from services.g7_gold_template import get_gold_template

from .schema import (
    DOMAIN_CODES,
    PUBLISHERS,
    SEMESTERS,
    GRADE_STATUS_FORMAL,
    GRADE_STATUS_SKELETON,
    GradeRecord,
    KnowledgePoint,
    QuestionTypeRecord,
    domain_anchor,
)

_REGISTRY_FILE = Path(__file__).resolve().parents[2] / "data" / "rollout" / "grade_registry.json"

# G7 fine-grained domain labels -> canonical domain (for registry consistency).
_DOMAIN_NORMALIZE = {
    "坐標幾何": "空間與形狀",
    "代數／坐標": "代數",
    "空間與形狀": "空間與形狀",
    "資料與不確定性": "資料與不確定性",
}

# Publisher-mapping semester keys in the G7 source ("七上"/"七下") -> canonical.
_SEMESTER_KEY_NORMALIZE = {"七上": "上學期", "七下": "下學期"}


def _normalize_domain(domain: str) -> str:
    return _DOMAIN_NORMALIZE.get(domain, domain)


def _normalize_publisher_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize publisher-mapping semester keys to the shared schema."""
    return {
        publisher: {
            _SEMESTER_KEY_NORMALIZE.get(semester, semester): payload
            for semester, payload in semesters.items()
        }
        for publisher, semesters in mapping.items()
    }


def _load_registry() -> Mapping[str, Any]:
    return json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))


def list_grades() -> tuple[int, ...]:
    raw = _load_registry()
    return tuple(int(g) for g in raw["grades"].keys())


def grade_status(grade: int) -> str:
    raw = _load_registry()
    entry = raw["grades"].get(str(grade))
    if entry is None:
        raise ValueError(f"unknown grade {grade}")
    return entry["status"]


# ---------------------------------------------------------------------------
# Phase 4 — publisher mapping framework
# ---------------------------------------------------------------------------

def empty_publisher_mapping(grade: int) -> dict[str, Any]:
    """Return a schema-compatible, empty publisher mapping for a grade."""
    return {
        publisher: {
            "上學期": {"units": []},
            "下學期": {"units": []},
        }
        for publisher in PUBLISHERS
    }


def publisher_mapping_semesters(publisher_mapping: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(publisher_mapping.keys())


# ---------------------------------------------------------------------------
# Grade records
# ---------------------------------------------------------------------------

def _g7_record() -> GradeRecord:
    template = get_gold_template()
    points: list[KnowledgePoint] = []
    question_types: list[QuestionTypeRecord] = []
    for cid, node in template["core"].items():
        points.append(
            KnowledgePoint(
                id=cid,
                grade=7,
                semester=str(node.get("semester", "")),
                domain=_normalize_domain(str(node.get("domain", ""))),
                core_topic=str(node.get("core_topic", "")),
                subunit=str(node.get("core_subunit", "")),
                curriculum_codes=tuple(node.get("curriculum_codes", ())),
                prerequisite_ids=tuple(node.get("prerequisite_knowledge_ids", ())),
                follow_up_ids=tuple(node.get("follow_up_knowledge_ids", ())),
            )
        )
        for q in node["question_type_catalog"]:
            question_types.append(
                QuestionTypeRecord(
                    type_id=str(q["type_id"]),
                    knowledge_id=cid,
                    name=str(q["name"]),
                    category=str(q["category"]),
                    difficulty=str(q["difficulty"]),
                    solving_strategy=str(q["solving_strategy"]),
                    key_steps=tuple(q["key_steps"]),
                    common_error_diagnosis=dict(q["common_error_diagnosis"]),
                    underlying_principle=str(q["underlying_principle"]),
                    prerequisite_knowledge_ids=tuple(q["prerequisite_knowledge_ids"]),
                    follow_up_knowledge_ids=tuple(q["follow_up_knowledge_ids"]),
                    variation_methods=tuple(q["variation_methods"]),
                    recommended_difficulty_range=dict(q["recommended_difficulty_range"]),
                    thinking_skill_ids=tuple(q["thinking_skill_ids"]),
                )
            )

    raw = _load_registry()
    g7_entry = raw["grades"]["7"]
    return GradeRecord(
        grade_id=7,
        semesters=tuple(g7_entry["semesters"]),
        domains=tuple(g7_entry["domains"]),
        status=GRADE_STATUS_FORMAL,
        knowledge_points=tuple(points),
        question_types=tuple(question_types),
        publisher_mapping=_normalize_publisher_mapping(template["publishers"]),
        prerequisite_graph=dict(template["prerequisite_graph"]),
        follow_up_graph=dict(template["follow_up_graph"]),
    )


def _skeleton_record(grade: int) -> GradeRecord:
    raw = _load_registry()
    entry = raw["grades"].get(str(grade))
    if entry is None:
        raise ValueError(f"unknown grade {grade}")
    return GradeRecord(
        grade_id=grade,
        semesters=tuple(entry["semesters"]),
        domains=tuple(entry["domains"]),
        status=GRADE_STATUS_SKELETON,
        knowledge_points=(),
        question_types=(),
        publisher_mapping=empty_publisher_mapping(grade),
        prerequisite_graph={},
        follow_up_graph={},
    )


def get_grade(grade: int) -> GradeRecord:
    if grade == 7:
        return _g7_record()
    if grade in (5, 6):
        from services.g5_g6_gold_template import get_grade_record as _g5_g6_record

        return _g5_g6_record(grade)
    if grade in (8, 9):
        from services.g8_g9_gold_template import get_grade_record as _g8_g9_record

        return _g8_g9_record(grade)
    return _skeleton_record(grade)


# ---------------------------------------------------------------------------
# Phase 3 — cross-grade prerequisite graph
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CrossGradeGraph:
    edges: tuple[tuple[str, str], ...]

    @property
    def nodes(self) -> tuple[str, ...]:
        seen: list[str] = []
        for edge in self.edges:
            for node in edge:
                if node not in seen:
                    seen.append(node)
        return tuple(seen)

    def predecessors(self, node: str) -> tuple[str, ...]:
        return tuple(src for src, dst in self.edges if dst == node)

    def successors(self, node: str) -> tuple[str, ...]:
        return tuple(dst for src, dst in self.edges if src == node)

    def transitive_prerequisites(self, node: str) -> tuple[str, ...]:
        """All upstream ancestors of ``node`` (topological, cycle-safe)."""
        result: list[str] = []
        seen: set[str] = set()
        stack = [node]
        while stack:
            current = stack.pop()
            for pred in self.predecessors(current):
                if pred not in seen:
                    seen.add(pred)
                    result.append(pred)
                    stack.append(pred)
        return tuple(dict.fromkeys(result))

    def transitive_follow_ups(self, node: str) -> tuple[str, ...]:
        """All downstream descendants of ``node`` (topological, cycle-safe)."""
        result: list[str] = []
        seen: set[str] = set()
        stack = [node]
        while stack:
            current = stack.pop()
            for succ in self.successors(current):
                if succ not in seen:
                    seen.add(succ)
                    result.append(succ)
                    stack.append(succ)
        return tuple(dict.fromkeys(result))

    def broken_links(self, known_nodes: Iterable[str]) -> tuple[tuple[str, str], ...]:
        """Edges whose endpoints are not in ``known_nodes`` (undefined anchor)."""
        valid = set(known_nodes)
        return tuple(e for e in self.edges if e[0] not in valid or e[1] not in valid)

    def cycles(self) -> tuple[tuple[str, ...], ...]:
        """Return every simple directed cycle (empty tuple if acyclic)."""
        adj: dict[str, list[str]] = {}
        for src, dst in self.edges:
            adj.setdefault(src, []).append(dst)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in self.nodes}
        cycles: list[tuple[str, ...]] = []

        def dfs(node: str, stack: list[str]) -> None:
            color[node] = GRAY
            stack.append(node)
            for nxt in adj.get(node, ()):
                if color[nxt] == GRAY:
                    idx = stack.index(nxt)
                    cycles.append(tuple(stack[idx:] + [nxt]))
                elif color[nxt] == WHITE:
                    dfs(nxt, stack)
            stack.pop()
            color[node] = BLACK

        for node in self.nodes:
            if color[node] == WHITE:
                dfs(node, [])
        return tuple(cycles)

    def is_acyclic(self) -> bool:
        return not self.cycles()


def cross_grade_graph() -> CrossGradeGraph:
    raw = _load_registry()
    edges = tuple((e["from"], e["to"]) for e in raw["cross_grade_edges"])
    return CrossGradeGraph(edges)


def domain_anchors() -> tuple[str, ...]:
    """Every (grade, domain) anchor implied by the registry."""
    raw = _load_registry()
    anchors: list[str] = []
    for grade_str, entry in raw["grades"].items():
        grade = int(grade_str)
        for domain in entry["domains"]:
            anchors.append(domain_anchor(grade, domain))
    return tuple(anchors)


def all_formal_knowledge_ids() -> tuple[str, ...]:
    """Concrete knowledge IDs of every formal grade (G5-G9)."""
    ids: list[str] = []
    for grade in (5, 6, 7, 8, 9):
        ids.extend(get_grade(grade).knowledge_ids)
    return tuple(ids)


HIGH_SCHOOL_ANCHORS = ("HS:數與量", "HS:代數", "HS:空間與形狀", "HS:資料與不確定性")


def high_school_anchors() -> tuple[str, ...]:
    """Terminal anchors marking the high-school follow-up entry points."""
    return HIGH_SCHOOL_ANCHORS
