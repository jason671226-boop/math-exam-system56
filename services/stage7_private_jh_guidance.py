"""Deterministic PRIVATE_JH candidate guidance; never Human Ground Truth."""
from __future__ import annotations

from typing import Any


def divisibility_extension_guidance(evidence: dict[str, Any]) -> dict[str, Any] | None:
    """Route evidenced advanced divisibility tasks to existing foundation IDs.

    Difficulty alone is intentionally ignored.  Callers must supply explicit
    divisibility evidence and PRIVATE_JH profile evidence.
    """
    if evidence.get("profile_type") != "PRIVATE_JH" or not evidence.get("divisibility_condition"):
        return None
    secondary = ["G06-R-COUNT-01"] if evidence.get("systematic_enumeration") else []
    return {
        "profile_type": "PRIVATE_JH",
        "foundation_skill_id": "G05-N-MULTIPLE-01",
        "assessment_style": "PRIVATE_JH_ADVANCED",
        "secondary_skill_ids": secondary,
        "guidance_status": "CANDIDATE_ONLY",
        "human_validated": False,
    }
