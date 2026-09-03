"""Read-only Production item_bank adapter for G5 custom-exam selection."""
from __future__ import annotations
from typing import Any, Mapping

PRODUCTION_PROJECT_ID = "igttuijrtwbtefhyeokp"
TABLE = "item_bank"

def load_g5_pool(client: Any, *, unit: str | None = None, knowledge_tag: str | None = None, limit: int = 100) -> tuple[dict[str, Any], ...]:
    """Fetch a bounded G5 pool from Production; never writes or invokes AI."""
    if client is None:
        return ()
    q = client.table(TABLE).select("id,index_code,grade,unit,knowledge_tag,new_question,correct_answer,difficulty,question_type,solution").eq("grade", "5")
    if unit:
        q = q.ilike("unit", f"%{unit}%")
    if knowledge_tag:
        q = q.eq("knowledge_tag", knowledge_tag)
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

def select_g5_questions(client: Any, *, count: int, units: tuple[str, ...] = (), knowledge_tag: str | None = None) -> tuple[dict[str, Any], ...]:
    """Select from Production only, preferring requested units and never falling back to AI/local data."""
    pool: list[dict[str, Any]] = []
    for unit in units or (None,):
        pool.extend(load_g5_pool(client, unit=unit, knowledge_tag=knowledge_tag, limit=max(count * 3, count)))
        if len({x["question_id"] for x in pool}) >= count:
            break
    seen: set[str] = set(); unique = []
    for row in pool:
        if row["question_id"] not in seen:
            seen.add(row["question_id"]); unique.append(row)
    return tuple(unique[:count])
