from __future__ import annotations

from typing import Any, Mapping

try:
    from catalog.diagnostic_loader import load_profile_knowledge_catalog
    from catalog.thinking_loader import load_thinking_catalog
    from services.learning_runtime import current_auth_user_id
    from services.evidence_parent_report_service import ParentReport, build_parent_report
    from services.teacher_feedback_service import (
        SupabaseTeacherFeedbackRepository,
        TeacherFeedbackError,
        create_teacher_feedback,
    )
except ModuleNotFoundError:
    from app.catalog.diagnostic_loader import load_profile_knowledge_catalog
    from app.catalog.thinking_loader import load_thinking_catalog
    from app.services.learning_runtime import current_auth_user_id
    from app.services.evidence_parent_report_service import ParentReport, build_parent_report
    from app.services.teacher_feedback_service import (
        SupabaseTeacherFeedbackRepository,
        TeacherFeedbackError,
        create_teacher_feedback,
    )


SCOPE_LABELS = {
    "整體觀察": "overall",
    "Knowledge Point": "knowledge",
    "Thinking Skill": "thinking_skill",
}


def _catalogs(profile: str) -> tuple[dict[str, str], dict[str, str]]:
    knowledge = {
        item.id: item.sub_unit
        for item in load_profile_knowledge_catalog(profile=profile).knowledge_points
    }
    thinking = {item.id: item.name for item in load_thinking_catalog().skills}
    return knowledge, thinking


def _feedback_repository(auth_client: Any | None) -> SupabaseTeacherFeedbackRepository | None:
    if auth_client is None:
        return None
    try:
        return SupabaseTeacherFeedbackRepository(auth_client)
    except TeacherFeedbackError:
        return None


def _render_teacher_feedback(
    st: Any,
    *,
    student_id: str,
    profile: str,
    auth_client: Any | None,
    knowledge_names: Mapping[str, str],
    thinking_names: Mapping[str, str],
) -> None:
    repository = _feedback_repository(auth_client)
    if repository is None:
        st.info("教師回饋需要已授權的 Supabase Auth session；目前不會建立本機假紀錄。")
        return

    scope_label = st.selectbox("回饋範圍", tuple(SCOPE_LABELS))
    scope = SCOPE_LABELS[scope_label]
    knowledge_id = None
    thinking_id = None
    if scope == "knowledge":
        knowledge_id = st.selectbox(
            "對應 Knowledge Point",
            tuple(knowledge_names),
            format_func=lambda value: f"{knowledge_names[value]}（{value}）",
        )
    elif scope == "thinking_skill":
        thinking_id = st.selectbox(
            "對應 Thinking Skill",
            tuple(thinking_names),
            format_func=lambda value: f"{thinking_names[value]}（{value}）",
        )

    with st.form("teacher_feedback_v1_form"):
        feedback_text = st.text_area("老師觀察", max_chars=2000)
        recommendation = st.text_area("建議（選填）", max_chars=1000)
        submitted = st.form_submit_button("儲存教師回饋", type="primary")
    if submitted:
        try:
            recorded_by = current_auth_user_id(auth_client)
            create_teacher_feedback(
                repository,
                student_id=student_id,
                recorded_by=recorded_by,
                profile_id=profile,
                scope_type=scope,
                feedback_text=feedback_text,
                recommendation=recommendation,
                knowledge_point_id=knowledge_id,
                thinking_skill_id=thinking_id,
                knowledge_ids=set(knowledge_names),
                thinking_ids=set(thinking_names),
            )
        except TeacherFeedbackError:
            st.error("回饋未儲存。請確認內容與教師授權；系統不會自行放寬存取權限。")
        else:
            st.success("教師回饋已儲存；AI mastery 與 Thinking evidence 均未被修改。")


def _load_report(
    *,
    student_id: str,
    profile: str,
    learning_runtime: Any,
    auth_client: Any | None,
    knowledge_names: Mapping[str, str],
    thinking_names: Mapping[str, str],
) -> ParentReport:
    repository = learning_runtime.repository
    attempts = repository.load_diagnostic_history(student_id, profile)
    knowledge = repository.load_latest_knowledge_mastery(student_id, profile)
    thinking = repository.load_latest_thinking_skill_summary(student_id, profile)
    feedback_repository = _feedback_repository(auth_client)
    feedback = feedback_repository.list_for_student(student_id) if feedback_repository else ()
    return build_parent_report(
        student_id=student_id,
        profile=profile,
        diagnostic_attempts=attempts,
        knowledge=knowledge,
        thinking=thinking,
        teacher_feedback=feedback,
        knowledge_names=knowledge_names,
        thinking_names=thinking_names,
    )


def _render_parent_report(st: Any, report: ParentReport) -> None:
    summary = report.diagnostic_summary
    st.markdown("#### 本次診斷摘要")
    if summary["available"]:
        c1, c2, c3 = st.columns(3)
        c1.metric("作答題數", summary["question_count"])
        c2.metric("完整得分", summary["full_credit"])
        average = summary["average_credit"]
        c3.metric("平均 evidence credit", f"{average}%" if average is not None else "資料不足")
    else:
        st.info("目前沒有最近診斷資料。")

    st.markdown("#### 目前優勢")
    if report.strengths:
        for item in report.strengths:
            st.success(f"{item['name']}｜{item['reason']}")
    else:
        st.info("目前尚未累積足夠證據辨識穩定優勢，並不代表學生沒有優勢。")

    st.markdown("#### 優先補強 Knowledge Top 3")
    if report.knowledge_priorities:
        for index, item in enumerate(report.knowledge_priorities, 1):
            st.write(f"{index}. **{item['name']}** — {item['reason']}")
    else:
        st.info("目前沒有足夠的 Knowledge evidence 可排序。")

    st.markdown("#### Thinking Skill Top 3")
    if report.thinking_priorities:
        for index, item in enumerate(report.thinking_priorities, 1):
            st.write(f"{index}. **{item['name']}** — {item['reason']}")
    else:
        st.info("目前累積的解題策略證據還不足，完成更多練習後再更新判斷。")

    st.markdown("#### 老師觀察")
    labels = {"overall": "Overall", "knowledge": "Knowledge", "thinking_skill": "Thinking Skill"}
    if any(report.teacher_observations.values()):
        for scope, rows in report.teacher_observations.items():
            if rows:
                with st.expander(labels[scope], expanded=scope == "overall"):
                    for row in rows:
                        st.write(row.feedback_text)
                        if row.recommendation:
                            st.caption("老師建議：" + row.recommendation)
    else:
        st.info("目前尚無老師觀察紀錄。")

    st.markdown("#### 下一步建議")
    if report.recommendations:
        for item in report.recommendations:
            with st.expander(f"P{item.priority}｜{item.title}", expanded=item.priority == 1):
                st.write(item.reason)
                st.caption("證據摘要：" + item.evidence_summary)
                st.info(item.next_action)
    else:
        st.info("先累積一份診斷或練習證據，再提供個人化建議。")

    st.markdown("#### 家長可以做什麼")
    for action in report.parent_actions:
        st.write("- " + action)
    for message in report.messages:
        st.caption(message)


def render_private_beta_feedback_and_parent_report(
    *,
    user_profile: Mapping[str, Any],
    learning_runtime: Any | None,
    auth_client: Any | None,
    profile: str = "",
) -> None:
    import streamlit as st

    st.markdown("### 🧪 Private Beta｜教師回饋 + 家長報告")
    if learning_runtime is None:
        st.info("學習資料尚未初始化。")
        return
    if not profile:
        profile = str(st.session_state.get("diag_pilot_active_route") or "")
    if not profile or profile.endswith("unavailable"):
        st.info("完成或選擇一份診斷後，即可建立教師回饋與家長報告。")
        return
    try:
        knowledge_names, thinking_names = _catalogs(profile)
    except (OSError, ValueError):
        st.error("課程資料目前無法載入。")
        return

    teacher_tab, parent_tab = st.tabs(("👩‍🏫 教師回饋", "👨‍👩‍👧 家長報告"))
    with teacher_tab:
        _render_teacher_feedback(
            st,
            student_id=learning_runtime.student_id,
            profile=profile,
            auth_client=auth_client,
            knowledge_names=knowledge_names,
            thinking_names=thinking_names,
        )
    with parent_tab:
        try:
            report = _load_report(
                student_id=learning_runtime.student_id,
                profile=profile,
                learning_runtime=learning_runtime,
                auth_client=auth_client,
                knowledge_names=knowledge_names,
                thinking_names=thinking_names,
            )
        except Exception:
            st.error("家長報告資料暫時無法載入；既有學習紀錄不會被修改。")
            return
        _render_parent_report(st, report)
