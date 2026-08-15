from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence


def to_plain_data(value: Any) -> Any:
    """Convert dataclasses/session objects into JSON-safe plain Python values."""
    if is_dataclass(value):
        return to_plain_data(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): to_plain_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain_data(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _credit_of(result: Any) -> float:
    if isinstance(result, Mapping):
        value = result.get("credit", 0)
    else:
        value = getattr(result, "credit", 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_correct(result: Any) -> bool:
    if isinstance(result, Mapping):
        return bool(result.get("is_correct", False))
    return bool(getattr(result, "is_correct", False))


def _error_candidates(result: Any) -> list[str]:
    if isinstance(result, Mapping):
        raw = result.get("error_candidates", []) or []
    else:
        raw = getattr(result, "error_candidates", ()) or ()
    output: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            value = item.get("error_type_id") or item.get("name") or ""
        else:
            value = getattr(item, "error_type_id", "") or str(item)
        if value:
            output.append(str(value))
    return output


def build_diagnostic_summary(results: Mapping[str, Any]) -> dict[str, Any]:
    total = len(results)
    full_correct = sum(1 for result in results.values() if _is_correct(result))
    partial = sum(
        1 for result in results.values() if (not _is_correct(result) and 0 < _credit_of(result) < 1)
    )
    needs_work = total - full_correct - partial
    average_credit = (
        round(sum(_credit_of(result) for result in results.values()) / total * 100, 1)
        if total
        else 0.0
    )
    return {
        "question_count": total,
        "full_correct": full_correct,
        "partial": partial,
        "needs_work": needs_work,
        "average_credit": average_credit,
    }


def build_detail_rows(
    results: Mapping[str, Any],
    question_meta: Mapping[str, Mapping[str, Any]] | None = None,
    error_labels: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    question_meta = question_meta or {}
    error_labels = error_labels or {}
    rows: list[dict[str, Any]] = []
    for qid, result in results.items():
        credit = _credit_of(result)
        if _is_correct(result):
            status = "答對"
        elif 0 < credit < 1:
            status = "部分答對"
        else:
            status = "需要補強"
        meta = question_meta.get(str(qid), {})
        ids = _error_candidates(result)
        rows.append(
            {
                "question_id": str(qid),
                "sequence": meta.get("sequence", ""),
                "prompt": str(meta.get("prompt", "")),
                "status": status,
                "credit": credit,
                "error_ids": ids,
                "error_labels": [error_labels.get(item, item) for item in ids],
            }
        )
    rows.sort(key=lambda row: (str(row.get("sequence") or "999"), row["question_id"]))
    return rows


def build_parent_report_payload(
    *,
    user_profile: Mapping[str, Any],
    diagnostic_results: Mapping[str, Any],
    question_meta: Mapping[str, Mapping[str, Any]] | None = None,
    error_labels: Mapping[str, str] | None = None,
    teacher_feedback: Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    summary = build_diagnostic_summary(diagnostic_results)
    details = build_detail_rows(diagnostic_results, question_meta, error_labels)
    feedback = [dict(item) for item in (teacher_feedback or [])]
    session_feedback = [item for item in feedback if item.get("feedback_scope") == "session"]
    question_feedback = [item for item in feedback if item.get("feedback_scope") == "question"]

    weak_rows = [row for row in details if row["status"] != "答對"]
    error_counts: dict[str, int] = {}
    for row in weak_rows:
        for label in row.get("error_labels", []):
            error_counts[label] = error_counts.get(label, 0) + 1
    top_errors = [
        label for label, _ in sorted(error_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    ]

    latest_session = session_feedback[-1] if session_feedback else {}
    next_focus = str(latest_session.get("next_focus") or "").strip()
    taught_content = str(latest_session.get("taught_content") or "").strip()
    student_response = str(latest_session.get("student_response") or "").strip()

    if next_focus:
        recommendation = next_focus
    elif weak_rows:
        recommendation = "先針對本次需要補強／部分答對的題目做 1 組基本題，再做 1 組變形題。"
    else:
        recommendation = "目前基礎診斷表現穩定，可進入下一個主題並保留少量複習題。"

    display_name = (
        str(user_profile.get("first_name") or "").strip()
        or str(user_profile.get("last_name") or "").strip()
        or "學生"
    )
    return {
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "student": {
            "display_name": display_name,
            "grade": str(user_profile.get("grade") or ""),
            "version": str(user_profile.get("version") or ""),
            "school": str(user_profile.get("school") or ""),
        },
        "summary": summary,
        "details": details,
        "top_errors": top_errors,
        "teacher_feedback_count": len(question_feedback),
        "teacher_session": {
            "taught_content": taught_content,
            "student_response": student_response,
            "next_focus": next_focus,
            "teacher_note": str(latest_session.get("teacher_note") or "").strip(),
        },
        "recommendation": recommendation,
    }


def parent_report_markdown(payload: Mapping[str, Any]) -> str:
    student = payload.get("student", {}) or {}
    summary = payload.get("summary", {}) or {}
    details = payload.get("details", []) or []
    top_errors = payload.get("top_errors", []) or []
    teacher = payload.get("teacher_session", {}) or {}

    lines = [
        "# MathAI 家長學習診斷報告",
        "",
        f"- 學生：{student.get('display_name', '學生')}",
        f"- 年級：{student.get('grade', '')}",
        f"- 教材／學習目標：{student.get('version', '')}",
        f"- 產生時間：{payload.get('generated_at', '')}",
        "",
        "## 本次診斷摘要",
        "",
        f"- 題數：{summary.get('question_count', 0)}",
        f"- 完全答對：{summary.get('full_correct', 0)}",
        f"- 部分答對：{summary.get('partial', 0)}",
        f"- 需要補強：{summary.get('needs_work', 0)}",
        f"- 綜合表現：{summary.get('average_credit', 0)}%",
        "",
    ]

    if top_errors:
        lines.extend(["## 主要觀察", "", "常見錯因／需要確認：" + "、".join(top_errors), ""])

    weak = [row for row in details if row.get("status") != "答對"]
    if weak:
        lines.extend(["## 需要優先處理的題目", ""])
        for row in weak[:5]:
            seq = row.get("sequence") or row.get("question_id")
            label = "、".join(row.get("error_labels", [])) or "待老師進一步確認"
            lines.append(f"- 第 {seq} 題：{row.get('status')}；{label}")
        lines.append("")

    if any(str(teacher.get(key) or "").strip() for key in teacher):
        lines.extend(["## 教師回饋", ""])
        if teacher.get("taught_content"):
            lines.append(f"- 本次已教內容：{teacher['taught_content']}")
        if teacher.get("student_response"):
            lines.append(f"- 學生反應：{teacher['student_response']}")
        if teacher.get("next_focus"):
            lines.append(f"- 下一步重點：{teacher['next_focus']}")
        if teacher.get("teacher_note"):
            lines.append(f"- 老師備註：{teacher['teacher_note']}")
        lines.append("")

    lines.extend([
        "## MathAI 建議下一步",
        "",
        str(payload.get("recommendation") or "繼續累積作答資料，再調整下一階段學習內容。"),
        "",
        "> 本報告為 Private Beta 學習追蹤用途，應搭配老師實際觀察與學生作答情況一起判讀。",
        "",
    ])
    return "\n".join(lines)
