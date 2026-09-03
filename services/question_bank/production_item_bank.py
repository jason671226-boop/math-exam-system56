"""Read-only Production item_bank adapter for G5 custom-exam selection."""
from __future__ import annotations
from typing import Any, Mapping, Sequence

PRODUCTION_PROJECT_ID = "igttuijrtwbtefhyeokp"
TABLE = "item_bank"

_DIFFICULTY_MAP = {"基本": "BASIC", "標準": "STANDARD", "進階": "ADVANCED", "挑戰": "CHALLENGE"}
_TYPE_MAP = {"選擇題": "CHOICE", "填空題": "FILL", "計算題": "CALCULATION"}


def load_g5_pool(client: Any, *, unit: str | None = None, knowledge_tag: str | None = None,
                 difficulty: str | None = None, question_type: str | None = None,
                 limit: int = 100) -> tuple[dict[str, Any], ...]:
    """Fetch a bounded G5 pool from Production; never writes or invokes AI."""
    if client is None:
        return ()
    q = client.table(TABLE).select("id,index_code,grade,unit,knowledge_tag,new_question,correct_answer,difficulty,question_type,solution").eq("grade", "5")
    if unit:
        q = q.ilike("unit", f"%{unit}%")
    if knowledge_tag:
        q = q.eq("knowledge_tag", knowledge_tag)
    if difficulty:
        q = q.eq("difficulty", _DIFFICULTY_MAP.get(difficulty, difficulty))
    if question_type:
        q = q.eq("question_type", _TYPE_MAP.get(question_type, question_type))
    result = q.limit(limit).execute()
    rows = result.data or []
    return tuple({
        "question_id": row.get("index_code") or str(row.get("id")),
        "source": "PRODUCTION_ITEM_BANK",
        "knowledge_tag": row.get("knowledge_tag"),
        "question_text": row.get("new_question") or row.get("original_question") or "",
        "answer": row.get("correct_answer") or "",
        "solution": row.get("solution") or "",
        "difficulty": row.get("difficulty") or "",
        "question_type": row.get("question_type") or "",
        "grade": "G5",
        "unit": row.get("unit") or "",
    } for row in rows)

def select_g5_questions(client: Any, *, count: int, units: tuple[str, ...] = (),
                        knowledge_tag: str | None = None, knowledge_tags: Sequence[str] = (),
                        difficulty: str | None = None, question_type: str | None = None,
                        question_type_counts: Mapping[str, int] | None = None) -> tuple[dict[str, Any], ...]:
    """Select from Production only, preferring requested units and never falling back to AI/local data."""
    pool: list[dict[str, Any]] = []
    tags = tuple(knowledge_tags) or ((knowledge_tag,) if knowledge_tag else (None,))
    type_counts = question_type_counts or ({question_type: count} if question_type else {None: count})
    for requested_type, requested_count in type_counts.items():
        if not requested_count:
            continue
        typed: list[dict[str, Any]] = []
        for tag in tags:
            for unit in units or (None,):
                typed.extend(load_g5_pool(client, unit=unit, knowledge_tag=tag,
                                          difficulty=difficulty, question_type=requested_type,
                                          limit=max(requested_count * 3, requested_count)))
                if len({x["question_id"] for x in typed}) >= requested_count:
                    break
            if len({x["question_id"] for x in typed}) >= requested_count:
                break
        pool.extend(typed[:requested_count])
        if len({x["question_id"] for x in pool}) >= count:
            break
    seen: set[str] = set(); unique = []
    for row in pool:
        if row["question_id"] not in seen:
            seen.add(row["question_id"]); unique.append(row)
    return tuple(unique[:count])
