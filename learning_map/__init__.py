from __future__ import annotations

"""Feature-flagged learning-map entrypoint.

This package intentionally shadows the legacy top-level ``learning_map.py``.
All legacy helpers are loaded from that file and re-exported unchanged.  Only
``render_learning_map`` is switched when Curriculum Master v2.7 is enabled.

Keeping the legacy file untouched makes rollback deterministic:
CURRICULUM_MASTER_V27_ENABLED=0 -> legacy behaviour.
"""

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


_ROOT = Path(__file__).resolve().parents[1]
_LEGACY_FILE = _ROOT / "learning_map.py"
_spec = importlib.util.spec_from_file_location("_mathai_legacy_learning_map", _LEGACY_FILE)
if _spec is None or _spec.loader is None:  # pragma: no cover - packaging failure
    raise ImportError(f"Unable to load legacy learning map: {_LEGACY_FILE}")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)

# Public helpers used by app.py remain the legacy implementation.
get_classic_question_type_names_for_units = _legacy.get_classic_question_type_names_for_units
get_subunit_names_for_units = _legacy.get_subunit_names_for_units
get_topic_names_for_subunits = _legacy.get_topic_names_for_subunits
get_unit_names_for_profile = _legacy.get_unit_names_for_profile

MASTERY_LABELS = _legacy.MASTERY_LABELS
LearningRuntime = _legacy.LearningRuntime
SessionStateMasteryRepository = _legacy.SessionStateMasteryRepository
ensure_local_student_id = _legacy.ensure_local_student_id


def _developer_warning(message: str) -> None:
    if st.session_state.get("developer_mode", False):
        st.warning(message)


def _render_v27_model(result: Any, runtime: Any, learning_runtime: Any = None) -> None:
    model = result.model
    route = result.route
    rows = list(model.get("rows", ()))
    priorities = list(model.get("priorities", ()))

    st.subheader(f"🌳 {route.grade} 個人學習地圖")
    st.caption(
        "Curriculum Master v2.7｜"
        f"{route.education_system}｜{route.track or 'COMMON'}｜"
        "依 canonical Skill mastery 與 prerequisite graph 產生。"
    )
    if learning_runtime is not None and getattr(learning_runtime, "persistence_enabled", False):
        st.caption("目前學習紀錄已連接持久化儲存。")

    status_counts = {key: 0 for key in MASTERY_LABELS}
    for row in rows:
        status = row.get("mastery_status", "unassessed")
        status_counts[status] = status_counts.get(status, 0) + 1
    columns = st.columns(5)
    for column, (status, label) in zip(columns, MASTERY_LABELS.items()):
        with column:
            st.metric(label, status_counts.get(status, 0))

    units: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        units.setdefault(str(row.get("main_unit") or "未分類"), []).append(row)
    for unit, unit_rows in units.items():
        with st.expander(f"📘 {unit}", expanded=False):
            for row in unit_rows:
                status = str(row.get("mastery_status") or "unassessed")
                label = MASTERY_LABELS.get(status, status)
                st.markdown(f"**{row.get('sub_unit') or row.get('skill_id')}**　`{label}`")
                metadata = (
                    f"分數 {float(row.get('mastery_score', 0.0)):.1f}｜"
                    f"信心 {float(row.get('confidence', 0.0)):.2f}｜"
                    f"證據 {int(row.get('evidence_count', 0))}"
                )
                if st.session_state.get("developer_mode", False):
                    metadata = f"{row.get('skill_id')}｜{metadata}"
                st.caption(metadata)
                if row.get("learning_focus"):
                    st.write(row["learning_focus"])

    st.markdown("### 下一步優先補強")
    if not priorities:
        st.info("目前沒有足夠證據可排序；完成診斷或練習後會更新建議。")
        return

    skill_by_id = {skill.skill_id: skill for skill in runtime.load_standard_skills(route)}
    for index, priority in enumerate(priorities, start=1):
        skill = skill_by_id.get(priority.skill_id)
        name = skill.skill_name if skill is not None else priority.skill_id
        blockers = []
        for prereq_id in priority.blocking_prerequisites:
            hit = runtime.find_skill(prereq_id)
            row = hit.get("row") if hit else None
            blockers.append((row or {}).get("skill_name") or prereq_id)
        blocker_text = f"｜先備缺口：{'、'.join(blockers)}" if blockers else ""
        st.markdown(
            f"{index}. **{name}** — {priority.reason}"
            f"｜掌握度 {priority.mastery_score:.1f}{blocker_text}"
        )


def render_learning_map(
    user_profile: Dict[str, Any],
    is_trial: bool = False,
    learning_runtime: LearningRuntime | None = None,
) -> None:
    """Render v2.7 map when enabled; otherwise preserve legacy behaviour."""

    try:
        try:
            from services.curriculum_master_feature import (
                curriculum_master_v27,
                curriculum_master_v27_enabled,
            )
            from services.learning_map_provider_v27 import try_resolve_learning_map_v27
        except ModuleNotFoundError:
            from app.services.curriculum_master_feature import (
                curriculum_master_v27,
                curriculum_master_v27_enabled,
            )
            from app.services.learning_map_provider_v27 import try_resolve_learning_map_v27

        if not curriculum_master_v27_enabled():
            return _legacy.render_learning_map(user_profile, is_trial, learning_runtime)

        runtime = curriculum_master_v27()
        student_id = (
            learning_runtime.student_id
            if learning_runtime is not None
            else ensure_local_student_id(st.session_state)
        )
        repository = (
            learning_runtime.repository
            if learning_runtime is not None
            else SessionStateMasteryRepository(st.session_state)
        )
        result = try_resolve_learning_map_v27(
            runtime,
            user_profile=user_profile,
            repository=repository,
            student_id=student_id,
        )
        if result is None:
            _developer_warning("Curriculum Master v2.7 路由未能安全解析，已回退舊學習地圖。")
            return _legacy.render_learning_map(user_profile, is_trial, learning_runtime)
        _render_v27_model(result, runtime, learning_runtime)
    except Exception as exc:
        # The feature is additive. Any v2.7 data/runtime failure must not take
        # down the production learning map.
        _developer_warning(f"Curriculum Master v2.7 fallback: {type(exc).__name__}: {exc}")
        return _legacy.render_learning_map(user_profile, is_trial, learning_runtime)


def __getattr__(name: str) -> Any:
    """Forward any unlisted legacy symbol for compatibility."""
    return getattr(_legacy, name)
