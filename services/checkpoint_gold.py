"""G7 Gold Template — Integrated Checkpoints (Phase 6).

Checkpoints group 3-5 core topics per 七上/七下 and integrate the
composite question-type composition (core / numeric-variation / medium
application / novel / cross-unit).  A checkpoint is evaluated against the
knowledge-mastery snapshots; falling below the (configurable) threshold does
NOT mean redoing a whole chapter — it returns the specific knowledge and
thinking-skill weaknesses to target.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .evidence_mastery_gold import MasteryResult, STRONG_STATUSES, WEAK_STATUSES

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_CHECKPOINTS_FILES = {
    5: _DATA_DIR / "g5_checkpoints.json",
    6: _DATA_DIR / "g6_checkpoints.json",
    7: _DATA_DIR / "g7_checkpoints.json",
    8: _DATA_DIR / "g8_checkpoints.json",
    9: _DATA_DIR / "g9_checkpoints.json",
}


@dataclass(frozen=True)
class CheckpointResult:
    checkpoint_id: str
    name: str
    semester: str
    threshold: float
    pass_rate: float
    passed: bool
    assessed: int
    total: int
    weak_knowledge_ids: tuple[str, ...]
    remediation_reason: str


def load_checkpoints(grade: int = 7) -> tuple[Mapping[str, Any], ...]:
    path = _CHECKPOINTS_FILES.get(grade, _CHECKPOINTS_FILES[7])
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(raw.get("checkpoints", ()))


def default_threshold(grade: int = 7) -> float:
    path = _CHECKPOINTS_FILES.get(grade, _CHECKPOINTS_FILES[7])
    raw = json.loads(path.read_text(encoding="utf-8"))
    return float(raw.get("default_threshold", 0.80))


def _mastery_for(knowledge_id: str, snapshots: Mapping[str, MasteryResult]) -> MasteryResult:
    return snapshots.get(knowledge_id)


def evaluate_checkpoint(
    checkpoint: Mapping[str, Any],
    knowledge_mastery: Mapping[str, MasteryResult],
    *,
    threshold: float | None = None,
) -> CheckpointResult:
    """Evaluate a checkpoint against knowledge mastery snapshots."""
    core_ids = tuple(checkpoint.get("core_ids", ()))
    threshold = float(threshold if threshold is not None else checkpoint.get("threshold", 0.80))

    assessed: list[str] = []
    passed: list[str] = []
    weak: list[str] = []
    for knowledge_id in core_ids:
        snapshot = _mastery_for(knowledge_id, knowledge_mastery)
        if snapshot is None or snapshot.status == "unassessed":
            weak.append(knowledge_id)
            continue
        assessed.append(knowledge_id)
        if snapshot.status in STRONG_STATUSES:
            passed.append(knowledge_id)
        else:
            weak.append(knowledge_id)

    total = len(core_ids)
    pass_rate = round(len(passed) / total, 4) if total else 0.0
    passed_checkpoint = pass_rate >= threshold

    if passed_checkpoint:
        reason = f"通過：達標 {pass_rate:.0%}（門檻 {threshold:.0%}）"
    else:
        reason = (
            f"未達標：{pass_rate:.0%} < {threshold:.0%}；"
            f"回到弱點補強 {('、'.join(weak) if weak else '無')}，"
            "不要求整章重做。"
        )

    return CheckpointResult(
        checkpoint_id=str(checkpoint.get("id", "")),
        name=str(checkpoint.get("name", "")),
        semester=str(checkpoint.get("semester", "")),
        threshold=threshold,
        pass_rate=pass_rate,
        passed=passed_checkpoint,
        assessed=len(assessed),
        total=total,
        weak_knowledge_ids=tuple(weak),
        remediation_reason=reason,
    )


def evaluate_all_checkpoints(
    knowledge_mastery: Mapping[str, MasteryResult],
    *,
    threshold: float | None = None,
) -> tuple[CheckpointResult, ...]:
    return tuple(
        evaluate_checkpoint(cp, knowledge_mastery, threshold=threshold)
        for cp in load_checkpoints()
    )


def composition_total(checkpoint: Mapping[str, Any]) -> int:
    return sum(int(n) for n in checkpoint.get("composition", {}).values())
