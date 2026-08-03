import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


DATA_FILE = Path(__file__).with_name("curriculum_map.json")


def _load_data() -> Dict[str, Any]:
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize_grade(grade_text: str) -> str:
    if not grade_text:
        return ""
    return grade_text.split("年級", 1)[0].strip()


DEFAULT_UNIT_OPTIONS = {
    "康軒版": [
        "數與量",
        "計算與代數",
        "分數與小數",
        "比與比例",
        "幾何與測量",
        "統計與機率",
        "生活應用與跨單元",
    ],
    "翰林版": [
        "數與量",
        "計算與代數",
        "分數與小數",
        "比與比例",
        "幾何與測量",
        "統計與機率",
        "生活應用與跨單元",
    ],
    "南一版": [
        "數與量",
        "計算與代數",
        "分數與小數",
        "比與比例",
        "幾何與測量",
        "統計與機率",
        "生活應用與跨單元",
    ],
    "報考私中": [
        "數與計算",
        "應用問題",
        "幾何與測量",
        "規律與推理",
        "跨單元綜合",
        "私中入學題型",
    ],
    "參加數學競賽": [
        "數論",
        "計數與組合",
        "幾何",
        "代數與規律",
        "邏輯推理",
        "綜合挑戰",
    ],
}


def _matching_demo(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_data()
    demo = data.get("demo", {})
    current_grade = _normalize_grade(user_profile.get("grade", ""))
    current_version = user_profile.get("version", "康軒版")

    if (
        demo
        and current_grade == str(demo.get("grade", ""))
        and current_version == demo.get("version", "")
    ):
        return demo
    return {}


def _all_demo_units(demo: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for semester_data in demo.get("semesters", {}).values():
        result.extend(semester_data.get("units", []))
    return result


def get_unit_names_for_profile(user_profile: Dict[str, Any]) -> List[str]:
    """取得自組考卷可用的主單元，並保證永遠回傳安全選項。"""
    demo = _matching_demo(user_profile)
    if demo:
        result: List[str] = []
        for unit in _all_demo_units(demo):
            unit_name = str(unit.get("name", "")).strip()
            if unit_name and unit_name not in result:
                result.append(unit_name)
        if result:
            return result

    current_version = user_profile.get("version", "康軒版")
    return DEFAULT_UNIT_OPTIONS.get(
        current_version,
        DEFAULT_UNIT_OPTIONS["康軒版"],
    )


def get_subunit_names_for_units(
    user_profile: Dict[str, Any],
    selected_unit_names: List[str],
) -> List[str]:
    """依已選主單元回傳次單元，尚未建檔時提供通用選項。"""
    demo = _matching_demo(user_profile)
    if demo and selected_unit_names:
        results: List[str] = []
        for unit in _all_demo_units(demo):
            unit_name = str(unit.get("name", "")).strip()
            if unit_name not in selected_unit_names:
                continue
            for subunit in unit.get("subunits", []):
                subunit_name = str(subunit.get("name", "")).strip()
                if subunit_name:
                    label = f"{unit_name} ＞ {subunit_name}"
                    if label not in results:
                        results.append(label)
        if results:
            return results

    return [
        "基本概念與定義",
        "基本計算與操作",
        "文字應用題",
        "圖形與測量",
        "易錯觀念辨析",
        "跨單元綜合",
    ]


def _render_pack_group(unit_id: str, pack_group: Dict[str, Any]) -> None:
    title = pack_group.get("title", "題組")
    description = pack_group.get("description", "")
    packs: List[Dict[str, Any]] = pack_group.get("packs", [])

    st.markdown(f"#### {title}")
    if description:
        st.caption(description)

    columns = st.columns(3)
    for idx, pack in enumerate(packs):
        with columns[idx % 3]:
            pack_name = pack.get("name", f"題組 {idx + 1}")
            status = pack.get("status", "準備中")
            st.markdown(f"**{pack_name}**  \n5 題｜{status}")
            st.button(
                "準備中",
                key=f"learning_pack_{unit_id}_{title}_{idx}",
                disabled=True,
                use_container_width=True,
            )


def _render_topic_detail(topic: Dict[str, Any]) -> None:
    tips = topic.get("tips", [])
    example = topic.get("example", "")
    answer = topic.get("answer", "")
    solution = topic.get("solution", "")

    if tips:
        st.markdown("**📌 單元重點提示**")
        for tip in tips:
            st.markdown(f"- {tip}")

    if example:
        st.markdown("**🧪 例題**")
        st.info(example)

    if answer or solution:
        with st.expander("查看答案與解法", expanded=False):
            if answer:
                st.markdown(f"**答案：** {answer}")
            if solution:
                st.markdown(f"**解法：** {solution}")


def _render_classic_type(item: Dict[str, Any], key: str) -> None:
    name = item.get("name", "經典題型")
    description = item.get("description", "")
    example = item.get("example", "")
    answer = item.get("answer", "")
    solution = item.get("solution", "")

    with st.expander(f"🧩 {name}", expanded=False):
        if description:
            st.write(description)
        if example:
            st.markdown("**例題**")
            st.info(example)
        if answer or solution:
            st.markdown("**解答**")
            if answer:
                st.markdown(f"- **答案：** {answer}")
            if solution:
                st.markdown(f"- **解析：** {solution}")


def render_learning_map(user_profile: Dict[str, Any], is_trial: bool = False) -> None:
    """顯示輕量版學習地圖、重點提示、例題與五題題組入口。"""
    st.subheader("🌳 學習地圖")
    st.info(
        "依照學生的年級與版本顯示主單元、次單元、重點提示、例題與經典題型。"
        "目前先提供『五年級・康軒版・上學期』前三個單元；題組按鈕仍為準備中，不會扣點。"
    )

    data = _load_data()
    if not data:
        st.error("找不到 curriculum_map.json，請確認它與 app.py 放在同一個資料夾。")
        return

    current_grade = user_profile.get("grade", "")
    current_version = user_profile.get("version", "")
    normalized_grade = _normalize_grade(current_grade)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("目前年級", current_grade or "未設定")
    with c2:
        st.metric("目前版本", current_version or "未設定")
    with c3:
        st.metric("題組單位", "每組 5 題")

    demo = data.get("demo", {})
    demo_grade = str(demo.get("grade", "5"))
    demo_version = demo.get("version", "康軒版")

    if normalized_grade != demo_grade or current_version != demo_version:
        st.warning(
            f"目前示範資料為：{demo.get('display_name', '五年級・康軒版・上學期')}。"
            "你的個人資料尚未有對應課程地圖，因此先顯示示範內容供測試。"
        )

    st.markdown(f"### {demo.get('display_name', '五年級・康軒版・上學期')}")
    st.caption(demo.get("note", "示範資料，後續會由老師校對並持續擴充。"))

    semester_options = list(demo.get("semesters", {}).keys())
    if not semester_options:
        st.warning("課程地圖尚未建立學期資料。")
        return

    semester = st.radio(
        "選擇學期",
        semester_options,
        horizontal=True,
        key="learning_map_semester",
    )
    semester_data = demo["semesters"].get(semester, {})
    units = semester_data.get("units", [])

    if not units:
        st.warning("這個學期的單元資料正在整理中。")
        return

    unit_names = [u.get("name", "未命名單元") for u in units]
    selected_name = st.selectbox(
        "選擇主單元",
        unit_names,
        key="learning_map_unit",
    )
    unit = next((u for u in units if u.get("name") == selected_name), units[0])

    st.markdown(f"## {unit.get('name', '')}")
    if unit.get("summary"):
        st.write(unit["summary"])

    subunits = unit.get("subunits", [])
    if subunits:
        st.markdown("### 次單元與學習重點")
        st.caption("先展開次單元，再選擇其中一個重點，即可查看提示、例題與解法。")

        for sub_idx, subunit in enumerate(subunits):
            sub_name = subunit.get("name", "次單元")
            description = subunit.get("description", "")
            topics = subunit.get("topics", [])

            with st.expander(f"📘 {sub_name}", expanded=(sub_idx == 0)):
                if description:
                    st.write(description)

                if topics:
                    topic_names = [t.get("name", "學習重點") for t in topics]
                    selected_topic_name = st.selectbox(
                        "選擇學習重點",
                        topic_names,
                        key=f"learning_topic_{unit.get('id', 'unit')}_{sub_idx}",
                    )
                    selected_topic = next(
                        (t for t in topics if t.get("name") == selected_topic_name),
                        topics[0],
                    )
                    _render_topic_detail(selected_topic)
                else:
                    old_points = subunit.get("key_points", [])
                    for point in old_points:
                        st.markdown(f"- {point}")

    classic_types = unit.get("classic_question_types", [])
    if classic_types:
        st.markdown("### 經典題型、例題與解答")
        if classic_types and isinstance(classic_types[0], str):
            st.write("、".join(classic_types))
        else:
            for idx, item in enumerate(classic_types):
                _render_classic_type(
                    item,
                    key=f"classic_{unit.get('id', 'unit')}_{idx}",
                )

    st.markdown("---")
    st.markdown("### 五題題組")
    st.caption("題組內容完成審核後再開放，避免誤扣點數。")

    for group in unit.get("pack_groups", []):
        _render_pack_group(unit.get("id", "unit"), group)
        st.markdown("")

    st.success(
        "目前學習地圖只提供學習說明與題組入口，不會呼叫 Gemini，也不會扣除點數。"
    )
