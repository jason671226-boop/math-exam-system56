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


def core_structure_guidance(evidence: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer mathematical structure over surface words or number formats."""
    if evidence.get("profile_type") != "PRIVATE_JH":
        return None
    skill = assessment = rule = None
    if evidence.get("common_factor_structure"):
        skill, assessment, rule = "G05-R-LAW-01", "PRIVATE_JH_ADVANCED", "COMMON_FACTOR_OVER_DECIMAL"
    elif (evidence.get("segmented_quantities") and evidence.get("asks_total")
          and not evidence.get("distance_time_relation")):
        skill, assessment, rule = "G05-R-MULTISTEP-01", "MULTI_STEP", "MULTISTEP_OVER_SPEED_WORD"
    elif evidence.get("distinct_combinations") and evidence.get("deduplicate_results"):
        skill, assessment, rule = "G06-R-COUNT-01", "PRIVATE_JH_ADVANCED", "COUNTING_OVER_ADDITION"
    elif evidence.get("round_trip") and evidence.get("average_speed"):
        skill, assessment, rule = "G06-N-SPEED-APP-01", "MULTI_STEP", "TOTAL_DISTANCE_OVER_TOTAL_TIME"
    if skill is None:
        return None
    return {"profile_type": "PRIVATE_JH", "foundation_skill_id": skill,
        "assessment_style": assessment, "rule_id": rule,
        "formula": "TOTAL_DISTANCE/TOTAL_TIME" if rule == "TOTAL_DISTANCE_OVER_TOTAL_TIME" else None,
        "guidance_status": "CANDIDATE_ONLY", "human_validated": False}
