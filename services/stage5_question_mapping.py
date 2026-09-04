from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable, Sequence


def normalize_question_text(text: str) -> str:
    """Normalize formatting without changing mathematical meaning."""
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("\u00a0", " ").replace("\u3000", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def question_fingerprint(text: str) -> str:
    normalized = normalize_question_text(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _clean_values(values: Iterable[Any]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value or "").strip()})


def deduplicate_questions(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate item_bank rows by normalized question text."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        text = normalize_question_text(row.get("new_question") or "")
        if not text:
            continue
        grouped[question_fingerprint(text)].append(dict(row))

    unique_rows: list[dict[str, Any]] = []
    for fingerprint, members in grouped.items():
        members.sort(key=lambda row: (int(row.get("id") or 0), str(row.get("index_code") or "")))
        representative = members[0]
        answers = _clean_values(row.get("correct_answer") for row in members)
        units = _clean_values(row.get("unit") for row in members)
        tags = _clean_values(row.get("knowledge_tag") for row in members)
        unique_rows.append({
            "fingerprint": fingerprint,
            "representative_id": int(representative.get("id") or 0),
            "representative_index_code": str(representative.get("index_code") or ""),
            "question_text": normalize_question_text(representative.get("new_question") or ""),
            "answer_text": str(representative.get("correct_answer") or ""),
            "unit": str(representative.get("unit") or ""),
            "knowledge_tag": str(representative.get("knowledge_tag") or ""),
            "duplicate_count": len(members),
            "source_row_ids": [int(row.get("id") or 0) for row in members],
            "source_index_codes": _clean_values(row.get("index_code") for row in members),
            "unit_variants": units,
            "knowledge_tag_variants": tags,
            "answer_variants": answers,
            "has_metadata_conflict": len(units) > 1 or len(tags) > 1 or len(answers) > 1,
        })
    return sorted(unique_rows, key=lambda row: row["fingerprint"])


def _stable_rank(seed: str, fingerprint: str) -> str:
    return hashlib.sha256(f"{seed}:{fingerprint}".encode("utf-8")).hexdigest()


def stratified_sample(
    unique_rows: Sequence[dict[str, Any]],
    sample_size: int = 200,
    seed: str = "MATHAI_STAGE5_G8_V1",
) -> list[dict[str, Any]]:
    """Deterministic proportional sample with at least one item per stratum when possible."""
    if sample_size <= 0:
        return []
    if len(unique_rows) <= sample_size:
        return list(unique_rows)

    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in unique_rows:
        key = (str(row.get("unit") or ""), str(row.get("knowledge_tag") or ""))
        strata[key].append(row)
    for members in strata.values():
        members.sort(key=lambda row: _stable_rank(seed, str(row["fingerprint"])))

    keys = sorted(strata)
    allocation = {key: 0 for key in keys}
    remaining = sample_size

    if len(keys) <= sample_size:
        for key in keys:
            allocation[key] = 1
            remaining -= 1
    else:
        ranked_keys = sorted(
            keys,
            key=lambda key: hashlib.sha256(f"{seed}:{key[0]}:{key[1]}".encode()).hexdigest(),
        )
        for key in ranked_keys[:sample_size]:
            allocation[key] = 1
        remaining = 0

    total_capacity = sum(len(strata[key]) - allocation[key] for key in keys)
    while remaining > 0 and total_capacity > 0:
        capacities = {key: len(strata[key]) - allocation[key] for key in keys}
        weights_total = sum(max(0, value) for value in capacities.values())
        if weights_total <= 0:
            break
        raw = {
            key: remaining * max(0, capacities[key]) / weights_total
            for key in keys
        }
        additions = {
            key: min(capacities[key], int(math.floor(raw[key])))
            for key in keys
        }
        added = sum(additions.values())
        for key, count in additions.items():
            allocation[key] += count
        remaining -= added
        if remaining <= 0:
            break
        remainder_order = sorted(
            keys,
            key=lambda key: (
                -(raw[key] - math.floor(raw[key])),
                hashlib.sha256(f"{seed}:{key[0]}:{key[1]}".encode()).hexdigest(),
            ),
        )
        progressed = False
        for key in remainder_order:
            if remaining <= 0:
                break
            if allocation[key] < len(strata[key]):
                allocation[key] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
        total_capacity = sum(len(strata[key]) - allocation[key] for key in keys)

    selected: list[dict[str, Any]] = []
    for key in keys:
        selected.extend(strata[key][: allocation[key]])
    selected.sort(key=lambda row: _stable_rank(seed, str(row["fingerprint"])))
    return selected[:sample_size]


def _bigrams(text: str) -> set[str]:
    value = re.sub(r"\s+", "", normalize_question_text(text).lower())
    if not value:
        return set()
    if len(value) == 1:
        return {value}
    return {value[index : index + 2] for index in range(len(value) - 1)}


def text_similarity(left: str, right: str) -> float:
    a, b = _bigrams(left), _bigrams(right)
    if not a or not b:
        return 0.0
    jaccard = len(a & b) / len(a | b)
    left_norm = normalize_question_text(left).lower()
    right_norm = normalize_question_text(right).lower()
    containment = 1.0 if left_norm and left_norm in right_norm else 0.0
    containment = max(containment, 1.0 if right_norm and right_norm in left_norm else 0.0)
    return max(jaccard, containment)


def skill_candidate_score(question: dict[str, Any], skill: dict[str, Any]) -> float:
    metadata = " ".join([
        str(question.get("unit") or ""),
        str(question.get("knowledge_tag") or ""),
    ]).strip()
    skill_core = " ".join([
        str(skill.get("main_unit") or ""),
        str(skill.get("subunit") or ""),
        str(skill.get("skill_name") or ""),
        str(skill.get("focus") or ""),
    ]).strip()
    question_text = str(question.get("question_text") or "")
    return round(0.75 * text_similarity(metadata, skill_core) + 0.25 * text_similarity(question_text, skill_core), 6)


def micro_candidate_score(question: dict[str, Any], micro: dict[str, Any]) -> float:
    metadata = " ".join([
        str(question.get("unit") or ""),
        str(question.get("knowledge_tag") or ""),
    ]).strip()
    micro_core = " ".join([
        str(micro.get("skill_name") or ""),
        str(micro.get("focus") or ""),
        str(micro.get("question_type") or ""),
        str(micro.get("item_pattern") or ""),
        str(micro.get("common_error") or ""),
    ]).strip()
    question_text = str(question.get("question_text") or "")
    return round(0.65 * text_similarity(metadata, micro_core) + 0.35 * text_similarity(question_text, micro_core), 6)


def build_candidate_packet(
    question: dict[str, Any],
    skills: Sequence[dict[str, Any]],
    micros: Sequence[dict[str, Any]],
    skill_limit: int = 10,
    micro_limit: int = 20,
) -> dict[str, Any]:
    ranked_skills = sorted(
        ((skill_candidate_score(question, skill), skill) for skill in skills),
        key=lambda pair: (-pair[0], str(pair[1].get("skill_id") or "")),
    )[:skill_limit]
    allowed_skill_ids = {str(skill.get("skill_id") or "") for _, skill in ranked_skills}
    eligible_micros = [
        micro for micro in micros
        if str(micro.get("parent_skill_id") or "") in allowed_skill_ids
    ]
    ranked_micros = sorted(
        ((micro_candidate_score(question, micro), micro) for micro in eligible_micros),
        key=lambda pair: (-pair[0], str(pair[1].get("micro_skill_id") or "")),
    )[:micro_limit]
    return {
        "fingerprint": question["fingerprint"],
        "question_text": question["question_text"],
        "answer_text": question.get("answer_text", ""),
        "unit": question.get("unit", ""),
        "knowledge_tag": question.get("knowledge_tag", ""),
        "skill_candidates": [
            {
                "score": score,
                "skill_id": skill.get("skill_id"),
                "main_unit": skill.get("main_unit"),
                "subunit": skill.get("subunit"),
                "skill_name": skill.get("skill_name"),
                "focus": skill.get("focus"),
                "difficulty": skill.get("difficulty"),
            }
            for score, skill in ranked_skills
        ],
        "micro_candidates": [
            {
                "score": score,
                "micro_skill_id": micro.get("micro_skill_id"),
                "parent_skill_id": micro.get("parent_skill_id"),
                "skill_name": micro.get("skill_name"),
                "focus": micro.get("focus"),
                "question_type": micro.get("question_type"),
                "item_pattern": micro.get("item_pattern"),
                "common_error": micro.get("common_error"),
                "difficulty": micro.get("difficulty"),
            }
            for score, micro in ranked_micros
        ],
    }


def mapping_review_status(confidence: float) -> str:
    value = float(confidence)
    if value >= 0.85:
        return "AUTO_CANDIDATE"
    if value >= 0.60:
        return "REVIEW"
    return "REJECT"


def validate_mapping(
    mapping: dict[str, Any],
    skills_by_id: dict[str, dict[str, Any]],
    micros_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    skill_id = str(mapping.get("skill_id") or "")
    micro_id = str(mapping.get("micro_skill_id") or "")
    if skill_id not in skills_by_id:
        errors.append("UNKNOWN_SKILL_ID")
    if micro_id:
        micro = micros_by_id.get(micro_id)
        if micro is None:
            errors.append("UNKNOWN_MICRO_SKILL_ID")
        elif skill_id and str(micro.get("parent_skill_id") or "") != skill_id:
            errors.append("MICRO_PARENT_MISMATCH")
    try:
        confidence = float(mapping.get("confidence"))
        if not 0.0 <= confidence <= 1.0:
            errors.append("CONFIDENCE_OUT_OF_RANGE")
    except (TypeError, ValueError):
        errors.append("INVALID_CONFIDENCE")
    return errors
