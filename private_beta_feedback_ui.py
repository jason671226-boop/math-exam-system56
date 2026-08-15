from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

try:
    from catalog.diagnostic_loader import load_diagnostic_questions, load_error_types
    from services.parent_report_service import (
        build_detail_rows,
        build_diagnostic_summary,
        build_parent_report_payload,
        parent_report_markdown,
        to_plain_data,
    )
except ModuleNotFoundError:
    from app.catalog.diagnostic_loader import load_diagnostic_questions, load_error_types
    from app.services.parent_report_service import (
        build_detail_rows,
        build_diagnostic_summary,
        build_parent_report_payload,
        parent_report_markdown,
        to_plain_data,
    )


ISSUE_OPTIONS = [
    "知識點判斷錯誤",
    "錯因判斷錯誤",
    "解答不適合學生",
    "題目辨識錯誤",
    "後續練習方向不適合",
]
VERDICT_OPTIONS = ["正確", "部分正確", "錯誤"]
RESPONSE_OPTIONS = ["已理解", "部分理解", "仍需補強", "尚未觀察"]


def _email(profile: Mapping[str, Any]) -> str:
    return str(profile.get("email") or "").strip().lower()


def _student_id(learning_runtime: Any | None) -> str:
    if learning_runtime is None:
        return ""
    return str(getattr(learning_runtime, "student_id", "") or "")


def _catalog_context(state: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    profile = str(state.get("diag_pilot_active_route") or "").strip()
    if not profile or profile.endswith("unavailable"):
        return {}, {}
    try:
        catalog = load_diagnostic_questions(profile=profile)
        errors = load_error_types()
    except (OSError, ValueError):
        return {}, {}
    question_meta = {
        q.question_id: {
            "sequence": q.sequence,
            "prompt": q.prompt,
        }
        for q in catalog.questions
    }
    error_labels = {key: item.name for key, item in errors.by_id().items()}
    return question_meta, error_labels


def _db_ready(auth_client: Any | None) -> bool:
    return auth_client is not None and hasattr(auth_client, "table")


def _save_snapshot(
    auth_client: Any | None,
    *,
    user_email: str,
    student_id: str,
    attempt_key: str,
    profile_id: str,
    summary: Mapping[str, Any],
    details: list[Mapping[str, Any]],
) -> bool:
    if not _db_ready(auth_client) or not user_email or not attempt_key:
        return False
    try:
        auth_client.table("beta_diagnostic_snapshots").upsert(
            {
                "user_email": user_email,
                "student_id": student_id,
                "attempt_key": attempt_key,
                "profile_id": profile_id,
                "summary": to_plain_data(summary),
                "details": to_plain_data(details),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_email,attempt_key",
        ).execute()
        return True
    except Exception:
        return False


def _save_feedback_row(auth_client: Any | None, row: Mapping[str, Any]) -> bool:
    if not _db_ready(auth_client):
        return False
    try:
        auth_client.table("beta_learning_feedback").insert(to_plain_data(row)).execute()
        return True
    except Exception:
        return False


def _load_feedback_rows(auth_client: Any | None, user_email: str, attempt_key: str) -> list[dict[str, Any]]:
    if not _db_ready(auth_client) or not user_email:
        return []
    try:
        query = (
            auth_client.table("beta_learning_feedback")
            .select("*")
            .eq("user_email", user_email)
            .order("created_at")
        )
        if attempt_key:
            query = query.eq("attempt_key", attempt_key)
        response = query.execute()
        return [dict(row) for row in (getattr(response, "data", None) or [])]
    except Exception:
        return []


def _save_report_snapshot(auth_client: Any | None, *, user_email: str, student_id: str, attempt_key: str, payload: Mapping[str, Any]) -> bool:
    if not _db_ready(auth_client) or not user_email:
        return False
    try:
        auth_client.table("beta_parent_report_snapshots").insert(
            {
                "user_email": user_email,
                "student_id": student_id,
                "source_attempt_key": attempt_key,
                "report_payload": to_plain_data(payload),
            }
        ).execute()
        return True
    except Exception:
        return False


def _session_feedback(state: Any, attempt_key: str) -> list[dict[str, Any]]:
    store = state.setdefault("private_beta_feedback_rows", [])
    return [dict(row) for row in store if str(row.get("attempt_key") or "") == attempt_key]


def _append_session_feedback(state: Any, row: Mapping[str, Any]) -> None:
    state.setdefault("private_beta_feedback_rows", []).append(dict(row))


def _render_teacher_feedback(
    st: Any,
    *,
    profile: Mapping[str, Any],
    learning_runtime: Any | None,
    auth_client: Any | None,
    question_meta: Mapping[str, Mapping[str, Any]],
    error_labels: Mapping[str, str],
) -> None:
    results = st.session_state.get("diag_pilot_results", {}) or {}
    attempt_key = str(st.session_state.get("diag_pilot_attempt_key") or "")
    if not results or not attempt_key:
        st.info("完成一次學習診斷後，這裡會自動出現教師校正與教學回饋表。")
        return

    user_email = _email(profile)
    student_id = _student_id(learning_runtime)
    profile_id = str(st.session_state.get("diag_pilot_active_route") or "")
    summary = build_diagnostic_summary(results)
    details = build_detail_rows(results, question_meta, error_labels)
    persisted = _save_snapshot(
        auth_client,
        user_email=user_email,
        student_id=student_id,
        attempt_key=attempt_key,
        profile_id=profile_id,
        summary=summary,
        details=details,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("完全答對", f"{summary['full_correct']} / {summary['question_count']}")
    c2.metric("部分答對", summary["partial"])
    c3.metric("需要補強", summary["needs_work"])
    st.caption(
        "老師只要校正 AI 判斷，不需要重新輸入整份答案。"
        + (" 回饋可寫入 Private Beta 雲端紀錄。" if persisted else " 目前先保留在本次瀏覽器工作階段。")
    )

    weak_first = sorted(details, key=lambda row: (row["status"] == "答對", str(row.get("sequence") or "999")))
    for row in weak_first:
        qid = row["question_id"]
        seq = row.get("sequence") or qid
        with st.expander(f"第 {seq} 題｜AI：{row['status']}", expanded=row["status"] != "答對"):
            prompt = str(row.get("prompt") or "").strip()
            if prompt:
                st.caption(prompt)
            if row.get("error_labels"):
                st.write("AI 可能錯因：" + "、".join(row["error_labels"]))
            verdict = st.radio(
                "AI 判斷正確嗎？",
                VERDICT_OPTIONS,
                horizontal=True,
                key=f"beta_teacher_verdict_{attempt_key}_{qid}",
            )
            issues = st.multiselect(
                "需要修正的地方（可複選）",
                ISSUE_OPTIONS,
                key=f"beta_teacher_issues_{attempt_key}_{qid}",
            )
            note = st.text_input(
                "補充說明（選填）",
                key=f"beta_teacher_note_{attempt_key}_{qid}",
            )
            if st.button("儲存這題回饋", key=f"beta_teacher_save_{attempt_key}_{qid}"):
                feedback_row = {
                    "user_email": user_email,
                    "student_id": student_id,
                    "attempt_key": attempt_key,
                    "feedback_scope": "question",
                    "question_id": qid,
                    "ai_status": row["status"],
                    "teacher_verdict": verdict,
                    "issue_types": issues,
                    "teacher_note": note,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                saved = _save_feedback_row(auth_client, feedback_row)
                _append_session_feedback(st.session_state, feedback_row)
                st.success("已儲存教師回饋。" + ("（雲端）" if saved else "（本次工作階段）"))

    st.markdown("#### 本次教學整體回饋")
    with st.form(f"beta_session_feedback_{attempt_key}"):
        taught = st.text_area("本次老師已教／已複習的內容", height=80)
        response = st.selectbox("學生課後反應", RESPONSE_OPTIONS)
        next_focus = st.text_area("下一步最應優先處理什麼？", height=80)
        teacher_note = st.text_area("老師備註（選填）", height=80)
        submitted = st.form_submit_button("儲存本次教學回饋", type="primary", use_container_width=True)
    if submitted:
        row = {
            "user_email": user_email,
            "student_id": student_id,
            "attempt_key": attempt_key,
            "feedback_scope": "session",
            "question_id": "",
            "ai_status": "",
            "teacher_verdict": "",
            "issue_types": [],
            "taught_content": taught.strip(),
            "student_response": response,
            "next_focus": next_focus.strip(),
            "teacher_note": teacher_note.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = _save_feedback_row(auth_client, row)
        _append_session_feedback(st.session_state, row)
        st.success("本次教學回饋已儲存。" + ("（雲端）" if saved else "（本次工作階段）"))


def _render_parent_report(
    st: Any,
    *,
    profile: Mapping[str, Any],
    learning_runtime: Any | None,
    auth_client: Any | None,
    question_meta: Mapping[str, Mapping[str, Any]],
    error_labels: Mapping[str, str],
) -> None:
    results = st.session_state.get("diag_pilot_results", {}) or {}
    attempt_key = str(st.session_state.get("diag_pilot_attempt_key") or "")
    if not results:
        st.info("完成一次學習診斷後即可產生家長報告。")
        return

    user_email = _email(profile)
    student_id = _student_id(learning_runtime)
    cloud_feedback = _load_feedback_rows(auth_client, user_email, attempt_key)
    local_feedback = _session_feedback(st.session_state, attempt_key)
    feedback = cloud_feedback or local_feedback

    payload = build_parent_report_payload(
        user_profile=profile,
        diagnostic_results=results,
        question_meta=question_meta,
        error_labels=error_labels,
        teacher_feedback=feedback,
    )
    summary = payload["summary"]
    student = payload["student"]

    st.markdown(f"### 👨‍👩‍👧 {student.get('display_name', '學生')} 的學習診斷")
    st.caption(f"{student.get('grade', '')}｜{student.get('version', '')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("綜合表現", f"{summary['average_credit']}%")
    c2.metric("完全答對", summary["full_correct"])
    c3.metric("部分答對", summary["partial"])
    c4.metric("需補強", summary["needs_work"])

    if payload.get("top_errors"):
        st.warning("目前最常見的問題：" + "、".join(payload["top_errors"]))

    teacher = payload.get("teacher_session", {})
    if any(str(teacher.get(key) or "").strip() for key in teacher):
        st.markdown("#### 👩‍🏫 教師觀察")
        if teacher.get("taught_content"):
            st.write("**已教內容：** " + teacher["taught_content"])
        if teacher.get("student_response"):
            st.write("**學生反應：** " + teacher["student_response"])
        if teacher.get("next_focus"):
            st.write("**下一步重點：** " + teacher["next_focus"])
        if teacher.get("teacher_note"):
            st.write("**老師備註：** " + teacher["teacher_note"])

    st.markdown("#### 🎯 MathAI 建議下一步")
    st.info(payload["recommendation"])

    markdown = parent_report_markdown(payload)
    st.download_button(
        "⬇️ 下載家長報告（Markdown）",
        data=markdown.encode("utf-8"),
        file_name="MathAI_家長學習診斷報告.md",
        mime="text/markdown",
        use_container_width=True,
    )
    if st.button("💾 保存本次家長報告快照", use_container_width=True, key=f"beta_parent_save_{attempt_key}"):
        saved = _save_report_snapshot(
            auth_client,
            user_email=user_email,
            student_id=student_id,
            attempt_key=attempt_key,
            payload=payload,
        )
        st.session_state["private_beta_last_parent_report"] = payload
        st.success("家長報告已保存。" + ("（雲端）" if saved else "（本次工作階段）"))


def render_private_beta_feedback_and_parent_report(
    *,
    user_profile: Mapping[str, Any],
    learning_runtime: Any | None = None,
    auth_client: Any | None = None,
) -> None:
    import streamlit as st

    st.markdown("### 🧪 Private Beta｜教師回饋 + 家長報告")
    st.caption("先用真實診斷資料驗證：老師是否覺得判斷合理、家長是否一看就懂。")
    question_meta, error_labels = _catalog_context(st.session_state)
    teacher_tab, parent_tab = st.tabs(["👩‍🏫 教師回饋", "👨‍👩‍👧 家長報告"])
    with teacher_tab:
        _render_teacher_feedback(
            st,
            profile=user_profile,
            learning_runtime=learning_runtime,
            auth_client=auth_client,
            question_meta=question_meta,
            error_labels=error_labels,
        )
    with parent_tab:
        _render_parent_report(
            st,
            profile=user_profile,
            learning_runtime=learning_runtime,
            auth_client=auth_client,
            question_meta=question_meta,
            error_labels=error_labels,
        )
