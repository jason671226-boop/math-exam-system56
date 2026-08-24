from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class DiagnosisV27:
    skill_id: str
    micro_skill_id: str|None
    error_type: str
    confidence: float
    evidence: tuple[str,...]=()
    prerequisite_gap_candidates: tuple[str,...]=()
    remediation_focus: str=""
    next_action: str="verify"
    def __post_init__(self):
        if not self.skill_id: raise ValueError("skill_id is required")
        if not 0<=self.confidence<=1: raise ValueError("confidence must be between 0 and 1")
        if self.next_action not in {"reteach","variant_practice","prerequisite_review","verify"}: raise ValueError("unsupported next_action")

@dataclass(frozen=True)
class GeneratedItemV27:
    prompt: str
    answer: str
    solution: str
    skill_id: str
    micro_skill_id: str|None
    difficulty: int
    validation: Mapping[str,Any]
