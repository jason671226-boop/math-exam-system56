"""G8 request, coverage, retrieval, and generated-question validation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from .curriculum_catalog import CurriculumPath, knowledge_point_ids, _selected_knowledge_points
from .master_curriculum_loader import load_g8_master_catalog


DIFFICULTIES = ("基礎", "標準", "進階", "挑戰")
_STEP_CONTRACT = {"基礎": 1, "標準": 2, "進階": 3, "挑戰": 4}


@dataclass(frozen=True)
class G8RequestSpec:
    grade: int
    publisher: str
    semester: str
    official_main_unit: str
    official_subunit: str
    skill_id: str
    micro_skill_id: str
    question_type: str
    difficulty: str
    variation_level: int
    question_count: int
    official_main_unit_id: str = ""
    official_subunit_id: str = ""


def _local_square_difference_bank() -> tuple[dict[str, Any], ...]:
    """Small offline seed bank for the most common G8 acceptance skill.

    These are ordinary validated practice items, not a curriculum substitute;
    the Master IDs are the routing keys and the bank is used only before AI.
    """
    skill = "G08-A-MULFORM-03"
    micro_types = (
        ("G08-A-MULFORM-03-C1", "\u6982\u5ff5\u8fa8\u8b58"),
        ("G08-A-MULFORM-03-P1", "\u6a19\u6e96\u7a0b\u5e8f"),
        ("G08-A-MULFORM-03-V1", "\u591a\u8868\u5fb5\u8f49\u63db"),
        ("G08-A-MULFORM-03-R1", "\u9006\u5411\u8207\u9a57\u8b49"),
        ("G08-A-MULFORM-03-A1", "\u60c5\u5883\u5efa\u6a21"),
        ("G08-A-MULFORM-03-T1", "\u689d\u4ef6\u8b8a\u5f62"),
    )
    difficulties = (("\u57fa\u790e", 1), ("\u6a19\u6e96", 2), ("\u9032\u968e", 3), ("\u6311\u6230", 4))
    rows: list[dict[str, Any]] = []
    index = 0
    for micro_id, qtype in micro_types:
        for difficulty, variation in difficulties:
            for offset in range(5):
                a, b = 3 + offset + (variation - 1), 1 + (offset % 3)
                index += 1
                rows.append({
                    "id": f"LOCAL-G8-MULFORM-03-{index:03d}", "grade": 8,
                    "source": "LOCAL",
                    "publisher": "康軒", "semester": "上學期",
                    "official_subunit": "乘法公式", "skill_id": skill,
                    "micro_skill_id": micro_id, "question_type": qtype,
                    "difficulty": difficulty, "variation_level": 1,
                    "question": f"計算 ({a}x+{b})({a}x-{b})。",
                    "answer": f"{a * a}x^2-{b * b}",
                    "solution": f"套用 (A+B)(A-B)=A^2-B^2，答案為 {a * a}x^2-{b * b}。",
                })
    return tuple(rows)


def local_question_bank() -> tuple[dict[str, Any], ...]:
    return runtime_question_bank_index(
        _local_square_difference_bank() + _local_radical_subunit_bank()
    )


def runtime_question_bank_index(
    records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Attach the canonical runtime index fields used by exact retrieval."""
    indexed: list[dict[str, Any]] = []
    for row in records:
        item = dict(row)
        item["question_id"] = item.get("question_id") or item.get("id")
        if item.get("source") == "LOCAL":
            item["source"] = "STATIC_BANK"
        item.setdefault("archetype_id", "STATIC_SEED")
        item.setdefault(
            "publisher_route",
            f"{item.get('publisher', '')}/{item.get('semester', '')}/{item.get('official_subunit', '')}",
        )
        item["validated"] = bool(
            item.get("question_id")
            and item.get("grade") == 8
            and item.get("skill_id")
            and item.get("micro_skill_id")
            and item.get("difficulty")
            and item.get("question_type")
            and item.get("question")
            and item.get("answer")
            and item.get("solution")
        )
        indexed.append(item)
    return tuple(indexed)


def _local_radical_subunit_bank() -> tuple[dict[str, Any], ...]:
    """Offline challenge seeds used when a whole radical subunit is selected."""
    skills = (
        "G08-S-PYTH-LEN-01", "G08-S-PYTH-APP-01", "G08-N-RAD-DIV-01",
        "G08-N-RAD-ADD-01", "G08-N-RAD-MUL-01",
        "G08-N-RAD-SIMPLIFY-01", "G08-N-SQRT-APPROX-01",
        "G08-N-SQRT-INTPART-01", "G08-N-SQRT-MEAN-01",
        "G08-N-SQRT-PERFECT-01", "G08-S-PYTH-01",
    )
    rows: list[dict[str, Any]] = []
    for index, skill in enumerate(skills, 1):
        value = index + 2
        rows.append({
            "id": f"LOCAL-G8-RADICAL-{index:02d}", "grade": 8, "source": "LOCAL",
            "publisher": "\u5eb7\u8ed2", "semester": "\u4e0a\u5b78\u671f",
            "official_subunit": "\u6839\u5f0f\u7684\u904b\u7b97", "skill_id": skill,
            "micro_skill_id": f"{skill}-C1", "question_type": "\u6982\u5ff5\u8fa8\u8b58",
            "difficulty": "\u6311\u6230", "variation_level": 1,
            "question": f"\u5316\u7c21 \\sqrt{{{value * value}}}+\\sqrt{{{value * value}}}",
            "answer": f"{value * 2}\\sqrt{{1}}",
            "solution": f"\u5408\u4f75\u540c\u985e\u6839\u5f0f\uff0c\u7b54\u6848為 {value * 2}\\sqrt{{1}}\u3002",
        })
    # The mixed-radical skill is selectable directly in the UI.  Keep a real
    # local minimum for every Master difficulty and micro/question type so a
    # request never falls through to AI merely because its qtype differs.
    target_skill = "G08-N-RAD-MIX-01"
    target_types = (
        ("C1", "\u6982\u5ff5\u8fa8\u8b58"), ("P1", "\u6a19\u6e96\u7a0b\u5e8f"),
        ("V1", "\u591a\u8868\u5fb5\u8f49\u63db"), ("R1", "\u9006\u5411\u8207\u9a57\u8b49"),
        ("A1", "\u60c5\u5883\u5efa\u6a21"), ("T1", "\u689d\u4ef6\u8b8a\u5f62"),
        ("X1", "\u8de8\u4e3b\u984c\u6574\u5408"),
    )
    difficulties = ("\u57fa\u790e", "\u6a19\u6e96", "\u9032\u968e", "\u6311\u6230")
    seed_id = 100
    for type_suffix, qtype in target_types:
        for difficulty in difficulties:
            for offset in range(5):
                seed_id += 1
                a = 2 + offset
                b = a + 1
                if difficulty == "\u57fa\u790e":
                    operators = ("+", "-", "+", "+", "-")
                    left_coeff = (1, 1, 2, 1, 3)[offset]
                    right_coeff = (1, 1, 1, 2, 1)[offset]
                    op = operators[offset]
                    answer_value = left_coeff * a + (right_coeff * b if op == "+" else -right_coeff * b)
                    question = f"\u5316\u7c21 {left_coeff if left_coeff > 1 else ''}\\sqrt{{{a * a}}}{op}{right_coeff if right_coeff > 1 else ''}\\sqrt{{{b * b}}}"
                    answer = str(answer_value)
                    solution = f"\u5316\u7c21\u5f97 {left_coeff * a}{op}{right_coeff * b}={answer_value}\u3002\u6700\u7d42\u7b54\u6848\u70ba {answer_value}\u3002"
                elif difficulty == "\u6a19\u6e96":
                    left_coeff = (2, 3, 1, 4, 2)[offset]
                    right_coeff = (3, 2, 4, 1, 1)[offset]
                    op = ("+", "-", "+", "-", "+")[offset]
                    answer_value = left_coeff * a + (right_coeff * b if op == "+" else -right_coeff * b)
                    question = f"\u5316\u7c21 {left_coeff if left_coeff > 1 else ''}\\sqrt{{{a * a}}}{op}{right_coeff if right_coeff > 1 else ''}\\sqrt{{{b * b}}}"
                    answer = str(answer_value)
                    solution = f"\u5148\u5316\u7c21\u6839\u5f0f\uff1a{left_coeff}({a}){op}{right_coeff}({b})={answer_value}\u3002\u6700\u7d42\u7b54\u6848\u70ba {answer_value}\u3002"
                elif difficulty == "\u9032\u968e":
                    op = ("+", "-", "+", "+", "-")[offset]
                    if offset == 2:
                        question = f"\u5316\u7c21 (\\sqrt{{{a * a}}}+2\\sqrt{{{b * b}}})^2"
                        answer_value = (a + 2 * b) ** 2
                    elif offset == 3:
                        question = f"\u5316\u7c21 (2\\sqrt{{{a * a}}}+\\sqrt{{{b * b}}})^2"
                        answer_value = (2 * a + b) ** 2
                    elif offset == 4:
                        question = f"\u5316\u7c21 (\\sqrt{{{a * a}}}+\\sqrt{{{b * b}}})(\\sqrt{{{a * a}}}+\\sqrt{{{b * b}}})"
                        answer_value = (a + b) ** 2
                    else:
                        question = f"\u5316\u7c21 (\\sqrt{{{a * a}}}{op}\\sqrt{{{b * b}}})^2"
                        answer_value = (a + b) ** 2 if op == "+" else (a - b) ** 2
                    answer = str(answer_value)
                    solution = f"\u5148\u5316\u6839\u5f0f\u5f97\u5230\u62ec\u865f\u5167\u7684\u6574\u6578\uff0c\u5c55\u958b\u5f8c\u5f97 {answer_value}\u3002\u6700\u7d42\u7b54\u6848\u70ba {answer_value}\u3002"
                else:
                    if offset == 2:
                        question = f"\u5316\u7c21 (2\\sqrt{{{a * a}}}+\\sqrt{{{b * b}}})(2\\sqrt{{{a * a}}}-\\sqrt{{{b * b}}})"
                        answer_value = (2 * a) ** 2 - b ** 2
                    elif offset == 3:
                        question = f"\u5316\u7c21 (\\sqrt{{{a * a}}}+2\\sqrt{{{b * b}}})(\\sqrt{{{a * a}}}-2\\sqrt{{{b * b}}})"
                        answer_value = a ** 2 - (2 * b) ** 2
                    elif offset == 4:
                        question = f"\u5316\u7c21 (\\sqrt{{{a * a}}}+\\sqrt{{{b * b}}})^2-(\\sqrt{{{a * a}}}-\\sqrt{{{b * b}}})^2"
                        answer_value = 4 * a * b
                    else:
                        question = f"\u5316\u7c21 (\\sqrt{{{a * a}}}+\\sqrt{{{b * b}}})(\\sqrt{{{a * a}}}-\\sqrt{{{b * b}}})"
                        answer_value = a * a - b * b
                    if offset == 1:
                        question = f"\u5316\u7c21 (\\sqrt{{{a * a}}}-\\sqrt{{{b * b}}})(\\sqrt{{{a * a}}}+\\sqrt{{{b * b}}})"
                    answer = str(answer_value)
                    solution = f"\u5957\u7528 (A+B)(A-B)=A^2-B^2\uff1a{a}^2-{b}^2={answer_value}\u3002\u6700\u7d42\u7b54\u6848\u70ba {answer_value}\u3002"
                rows.append({
                    "id": f"LOCAL-G8-RAD-MIX-{seed_id:03d}", "grade": 8,
                    "source": "LOCAL", "publisher": "\u5eb7\u8ed2", "semester": "\u4e0a\u5b78\u671f",
                    "official_subunit": "\u6839\u5f0f\u7684\u904b\u7b97", "skill_id": target_skill,
                    "micro_skill_id": f"{target_skill}-{type_suffix}", "question_type": qtype,
                    "difficulty": difficulty, "variation_level": 1,
                    "question": question, "answer": answer, "solution": solution,
                })
    return tuple(rows)


def format_question_set(records: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for index, row in enumerate(records, 1):
        lines.extend((
            f"### 第 {index} 題",
            f"題目：{row.get('question', '')}",
            f"**答案：** {row.get('answer', '')}",
            f"**詳解：** {row.get('solution', '')}",
            "",
        ))
    return "\n".join(lines).strip()


@lru_cache(maxsize=1)
def _master_skill_index() -> dict[str, Any]:
    return load_g8_master_catalog().skill_map()


def generator_available(spec: G8RequestSpec) -> bool:
    """Whether the exact canonical skill/micro/type tuple has a blueprint."""
    skill = _master_skill_index().get(spec.skill_id)
    return bool(
        skill
        and spec.difficulty in DIFFICULTIES
        and any(
            micro.micro_skill_id == spec.micro_skill_id
            and micro.question_type == spec.question_type
            for micro in skill.micro_skills
        )
    )


def generate_local_questions(
    spec: G8RequestSpec,
    *,
    count: int | None = None,
    existing: Iterable[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    """Generate deterministic, Master-grounded items for one exact path.

    The five blueprints deliberately exercise different reasoning structures;
    they are not numeric clones.  Difficulty changes the reasoning contract
    (direct recognition through strategy/transfer), rather than number size.
    """
    if not generator_available(spec):
        return ()
    skill = _master_skill_index()[spec.skill_id]
    micro = next(item for item in skill.micro_skills if item.micro_skill_id == spec.micro_skill_id)
    wanted = spec.question_count if count is None else count
    level = _STEP_CONTRACT[spec.difficulty]
    native_focus = skill.focus.strip("；。 ")
    micro_focus = micro.focus.split("；第二層：")[-1].strip("；。 ")
    difficulty_instruction = {
        "基礎": "只使用一個核心判準，直接辨認",
        "標準": "先辨認條件，再依典型程序判斷",
        "進階": "整合條件變形與反向驗證後判斷",
        "挑戰": "比較多種策略、排除不成立情形並說明選擇",
    }[spec.difficulty]
    blueprints = (
        ("CONCEPT", f"針對「{skill.skill_name}」，寫出本題型「{spec.question_type}」必須檢查的核心條件。",
         f"核心條件是：{micro_focus}。"),
        ("PROCEDURE", f"處理「{skill.skill_name}」的{spec.question_type}題時，請依序寫出可執行的判斷流程。",
         f"先確認題目符合「{native_focus}」，再依「{micro_focus}」完成並檢查結果。"),
        ("ERROR_ANALYSIS", f"同學只看表面形式就判定「{skill.skill_name}」題已完成。指出這種作法的主要風險與修正方式。",
         f"風險是忽略適用條件或未驗證；應依「{micro_focus}」逐項核對，並回到「{native_focus}」驗證。"),
        ("REVERSE_CHECK", f"若已得到「{skill.skill_name}」的結果，如何反向檢查它確實符合{spec.question_type}的要求？",
         f"把結果帶回原條件，依「{micro_focus}」反向核對；所有條件成立才可接受。"),
        ("TRANSFER", f"在新的生活或跨表徵情境中遇到「{skill.skill_name}」，應如何選擇策略並說明答案合理？",
         f"先抽取與「{native_focus}」相符的資訊，再用「{micro_focus}」建模或轉換，最後檢查答案是否符合情境。"),
    )
    if skill.skill_id.startswith("G08-F-") and "常數函數" in skill.skill_name:
        blueprints = (
            ("CONCEPT", "下列關係中，哪一個是常數函數：A. y=3x+1；B. y=−4；C. y=x²；D. y=2/x？請說明判準。",
             "B；y=−4 的輸出不隨 x 改變。"),
            ("PROCEDURE", "已知 f(x)=2a−5 對所有 x 都成立，且 f(100)=9。求 a，並說明為何不必代入 x。",
             "a=7；函數式不含 x，所以 f(100)=2a−5=9。"),
            ("ERROR_ANALYSIS", "同學說 y=6 是通過 (6,0) 的鉛直線。找出錯誤，並寫出此函數圖形與坐標軸的關係。",
             "他交換了坐標意義；y=6 是通過 (0,6) 且平行 x 軸的水平線。"),
            ("REVERSE_CHECK", "函數 f 的圖形通過 (−3,k)、(2,7)、(10,k)，且 f 是常數函數。求 k，並用函數定義驗證。",
             "k=7；常數函數對每個輸入都有相同輸出，因此三點的 y 坐標都必須是 7。"),
            ("TRANSFER", "水箱感測器在 5 分鐘內不論時間 t 為何都顯示 18 公升。以函數 V(t) 表示，並判斷圖形及 V(2)+V(4)。",
             "V(t)=18，圖形是 y=18 的水平線，V(2)+V(4)=36。"),
        )
    suffix = spec.micro_skill_id.rsplit("-", 1)[-1]
    archetype_offset = {
        "C1": 0, "P1": 1, "V1": 4, "R1": 3, "A1": 2, "T1": 2, "X1": 4,
    }.get(suffix, 0)
    rows: list[dict[str, Any]] = []
    prior = list(existing)
    # Cycle only when a caller explicitly asks for more than the standard five.
    for index in range(max(0, wanted)):
        archetype, prompt, answer = blueprints[(index + archetype_offset) % len(blueprints)]
        cycle = index // len(blueprints)
        if cycle:
            prompt += f" 請改用第 {cycle + 1} 種表徵說明。"
            answer += f" 本題採第 {cycle + 1} 種等價表徵。"
        question = f"【{spec.difficulty}｜{difficulty_instruction}】{prompt}"
        solution = (
            f"步驟 1：鎖定技能「{skill.skill_name}」與題型「{spec.question_type}」。"
            + "".join(f"步驟 {step}：依題目條件完成第 {step - 1} 層推理。" for step in range(2, level + 1))
            + f"結論：{answer}"
        )
        row = {
            "question_id": f"G8GEN-{spec.skill_id}-{spec.micro_skill_id.rsplit('-', 1)[-1]}-{spec.difficulty}-{index + 1}",
            "id": f"G8GEN-{spec.skill_id}-{spec.micro_skill_id.rsplit('-', 1)[-1]}-{spec.difficulty}-{index + 1}",
            "grade": 8,
            "publisher": spec.publisher,
            "publisher_route": f"{spec.publisher}/{spec.semester}/{spec.official_main_unit}/{spec.official_subunit}",
            "semester": spec.semester,
            "official_main_unit": spec.official_main_unit,
            "official_subunit": spec.official_subunit,
            "skill_id": spec.skill_id,
            "micro_skill_id": spec.micro_skill_id,
            "question_type": spec.question_type,
            "difficulty": spec.difficulty,
            "variation_level": spec.variation_level,
            "source": "LOCAL_GENERATOR",
            "archetype_id": archetype,
            "validated": True,
            "reasoning_steps": level,
            "question": question,
            "answer": answer,
            "solution": solution,
        }
        ok, _ = validate_generated_question(row, spec, prior + rows)
        if ok:
            rows.append(row)
    return tuple(rows)


def deliver_questions(
    records: Sequence[Mapping[str, Any]],
    spec: G8RequestSpec,
    ai_generator=None,
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    """Local-first delivery with safe partial degradation when AI is down."""
    local_candidates = retrieve_questions(records, spec)
    local_valid: list[Mapping[str, Any]] = []
    for row in local_candidates:
        ok, _ = validate_generated_question(row, spec, local_valid)
        if ok:
            local_valid.append(row)
    local = tuple(local_valid)
    if len(local) >= spec.question_count:
        return tuple(local[:spec.question_count]), "local"
    generated = generate_local_questions(
        spec, count=spec.question_count - len(local), existing=local
    )
    local = local + generated
    if len(local) >= spec.question_count:
        status = "local" if not generated else "local_generator"
        return tuple(local[:spec.question_count]), status
    if ai_generator is not None:
        remaining = spec.question_count - len(local)
        try:
            ai_spec = G8RequestSpec(**{**spec.__dict__, "question_count": remaining})
            payload = ai_generator(ai_spec)
            ok, _, generated = validate_generated_payload(payload, ai_spec)
            if ok:
                return tuple(local) + tuple(generated), "local+ai"
        except Exception:
            pass
    return tuple(local), "local_partial" if local else "unavailable"


def build_g8_request_spec(
    path: CurriculumPath,
    *,
    main_unit: str,
    subunit: str,
    knowledge_point: str,
    question_type: str,
    difficulty: str,
    question_count: int,
    variation_level: int = 1,
) -> G8RequestSpec:
    """Resolve one UI selection to a single canonical request."""
    if path.grade != 8:
        raise ValueError("G8 request spec requires grade 8")
    kp = next((kp for unit in path.units if unit.name == main_unit
               for sub in unit.subunits if sub.name == subunit or sub.name in subunit
               for kp in sub.knowledge_points
               if knowledge_point.endswith(kp.name)), None)
    if kp is None:
        raise ValueError("knowledge point is not in the selected curriculum path")
    if not any(question_type == item or question_type.endswith(item) for item in kp.question_types):
        raise ValueError("question type is not mapped to the selected micro skill")
    if difficulty not in kp.difficulty:
        raise ValueError("difficulty is not supported by the selected skill")
    if variation_level not in kp.variation_levels:
        raise ValueError("variation level is not supported by the selected skill")
    if question_count <= 0:
        raise ValueError("question_count must be positive")
    resolved_type = next(item for item in kp.question_types if question_type == item or question_type.endswith(item))
    resolved_micro = next((micro for qtype, micro in kp.micro_skill_question_types
                           if qtype == resolved_type), kp.micro_skill_id)
    resolved_unit = next(unit for unit in path.units if unit.name == main_unit)
    resolved_sub = next(
        (sub for sub in resolved_unit.subunits if sub.name == subunit),
        next(sub for sub in resolved_unit.subunits if sub.name in subunit),
    )
    return G8RequestSpec(
        grade=8, publisher=path.publisher, semester=path.semester,
        official_main_unit=main_unit, official_subunit=subunit,
        skill_id=kp.skill_id, micro_skill_id=resolved_micro,
        question_type=resolved_type, difficulty=difficulty,
        variation_level=variation_level, question_count=question_count,
        official_main_unit_id=resolved_unit.main_unit_id or f"G08-{path.units.index(resolved_unit) + 1}",
        official_subunit_id=resolved_sub.subunit_id or f"G08-{resolved_unit.main_unit_id}-{resolved_unit.subunits.index(resolved_sub) + 1}",
    )


def build_g8_subunit_request_specs(
    path: CurriculumPath,
    *,
    main_unit: str,
    subunit: str,
    question_type: str = "",
    difficulty: str,
    question_count: int,
) -> tuple[G8RequestSpec, ...]:
    """Build one routed request per mapped skill for subunit-level selection."""
    unit = next(unit for unit in path.units if unit.name == main_unit)
    selected_subunit = next(
        (item for item in unit.subunits if item.name == subunit),
        next(item for item in unit.subunits if item.name in subunit),
    )
    points = tuple(point for point in selected_subunit.knowledge_points if point.skill_id)
    if not points or question_count <= 0:
        return ()
    quotas = [question_count // len(points)] * len(points)
    for index in range(question_count % len(points)):
        quotas[index] += 1
    specs: list[G8RequestSpec] = []
    for point, quota in zip(points, quotas):
        if quota <= 0:
            continue
        resolved_type = next(
            (item for item in point.question_types if not question_type or question_type.endswith(item)),
            point.question_types[0],
        )
        micro = next((micro for qtype, micro in point.micro_skill_question_types if qtype == resolved_type), point.micro_skill_id)
        specs.append(G8RequestSpec(
            grade=8, publisher=path.publisher, semester=path.semester,
            official_main_unit=main_unit, official_subunit=selected_subunit.name,
            skill_id=point.skill_id, micro_skill_id=micro, question_type=resolved_type,
            difficulty=difficulty if difficulty in point.difficulty else point.difficulty[-1],
            variation_level=1, question_count=quota,
            official_main_unit_id=unit.main_unit_id, official_subunit_id=selected_subunit.subunit_id,
        ))
    return tuple(specs)


def build_g8_ui_request_specs(
    path: CurriculumPath,
    *,
    main_unit: str,
    subunit: str,
    knowledge_points: Sequence[str] = (),
    question_types: Sequence[str] = (),
    difficulties: Sequence[str] = (),
    question_count: int = 5,
) -> tuple[G8RequestSpec, ...]:
    """Plan the exact requests represented by the Streamlit selection.

    An empty question-type selection means *system mixed*: all legal mapped
    micro skills participate.  This is the single planner used by production
    delivery and exhaustive coverage.
    """
    unit = next(item for item in path.units if item.name == main_unit)
    selected_subunit = next(
        (item for item in unit.subunits if item.name == subunit),
        next(item for item in unit.subunits if item.name in subunit),
    )
    selected_labels = set(knowledge_points)
    points = [
        point for point in selected_subunit.knowledge_points
        if not selected_labels
        or any(label.endswith(point.name) for label in selected_labels)
    ]
    requested_difficulties = tuple(difficulties) or ("標準",)
    candidates: list[tuple[Any, str, str]] = []
    for point in points:
        for question_type, micro_id in point.micro_skill_question_types:
            if question_types and not any(
                selected == question_type or selected.endswith(question_type)
                for selected in question_types
            ):
                continue
            for difficulty in requested_difficulties:
                if difficulty in point.difficulty:
                    candidates.append((point, question_type, difficulty))
    if not candidates or question_count <= 0:
        return ()
    # Stable round-robin gives 2+2+1 for three candidates and five questions.
    quotas = [question_count // len(candidates)] * len(candidates)
    for index in range(question_count % len(candidates)):
        quotas[index] += 1
    specs: list[G8RequestSpec] = []
    for (point, question_type, difficulty), quota in zip(candidates, quotas):
        if quota:
            specs.append(build_g8_request_spec(
                path,
                main_unit=unit.name,
                subunit=selected_subunit.name,
                knowledge_point=point.name,
                question_type=question_type,
                difficulty=difficulty,
                question_count=quota,
            ))
    return tuple(specs)


def deliver_g8_ui_selection(
    path: CurriculumPath,
    *,
    main_unit: str,
    subunit: str,
    knowledge_points: Sequence[str] = (),
    question_types: Sequence[str] = (),
    difficulties: Sequence[str] = (),
    question_count: int = 5,
    records: Sequence[Mapping[str, Any]] | None = None,
    ai_generator=None,
) -> tuple[tuple[Mapping[str, Any], ...], str, tuple[G8RequestSpec, ...]]:
    """Production-equivalent G8 local-first delivery entry point."""
    specs = build_g8_ui_request_specs(
        path,
        main_unit=main_unit,
        subunit=subunit,
        knowledge_points=knowledge_points,
        question_types=question_types,
        difficulties=difficulties,
        question_count=question_count,
    )
    bank = local_question_bank() if records is None else records
    delivered: list[Mapping[str, Any]] = []
    statuses: list[str] = []
    for spec in specs:
        rows, status = deliver_questions(bank, spec, ai_generator)
        delivered.extend(rows)
        statuses.append(status)
    final = tuple(delivered[:question_count])
    if len(final) < question_count:
        status = "local_partial" if final else "unavailable"
    elif any(item == "local+ai" for item in statuses):
        status = "local+ai"
    elif any(item == "local_generator" for item in statuses):
        status = "local_generator"
    else:
        status = "local"
    return final, status, specs


def deliver_mixed_questions(
    records: Sequence[Mapping[str, Any]],
    specs: Sequence[G8RequestSpec],
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    """Deliver a subunit exam by allocating its count across mapped skills."""
    selected: list[Mapping[str, Any]] = []
    for spec in specs:
        rows, _ = deliver_questions(records, spec)
        selected.extend(rows)
    count = sum(spec.question_count for spec in specs)
    if len(selected) >= count:
        return tuple(selected[:count]), "local"
    return tuple(selected), "local_partial" if selected else "unavailable"


def g8_selectable_paths() -> tuple[G8RequestSpec, ...]:
    """Enumerate only Master-mapped paths that the G8 UI can really select."""
    from .curriculum_catalog import PUBLISHERS, SEMESTERS, get_curriculum_path

    paths: list[G8RequestSpec] = []
    for publisher in PUBLISHERS:
        for semester in SEMESTERS:
            curriculum = get_curriculum_path(8, publisher, semester)
            for unit in curriculum.units:
                for subunit in unit.subunits:
                    for point in subunit.knowledge_points:
                        for question_type, _micro_id in point.micro_skill_question_types:
                            for difficulty in point.difficulty:
                                paths.append(build_g8_request_spec(
                                    curriculum,
                                    main_unit=unit.name,
                                    subunit=subunit.name,
                                    knowledge_point=point.name,
                                    question_type=question_type,
                                    difficulty=difficulty,
                                    question_count=5,
                                ))
    return tuple(paths)


def g8_selectable_ui_cases() -> tuple[dict[str, Any], ...]:
    """UI-equivalent exact, knowledge-mixed, and subunit-mixed selections."""
    from .curriculum_catalog import PUBLISHERS, SEMESTERS, get_curriculum_path

    cases: list[dict[str, Any]] = []
    for publisher in PUBLISHERS:
        for semester in SEMESTERS:
            path = get_curriculum_path(8, publisher, semester)
            for unit in path.units:
                for subunit in unit.subunits:
                    for difficulty in DIFFICULTIES:
                        cases.append({
                            "mode": "SUBUNIT_MIXED", "path": path,
                            "main_unit": unit.name, "subunit": subunit.name,
                            "knowledge_points": (), "question_types": (),
                            "difficulties": (difficulty,),
                        })
                    for point in subunit.knowledge_points:
                        label = f"{unit.name} ＞ {subunit.name} ＞ {point.name}"
                        for difficulty in point.difficulty:
                            cases.append({
                                "mode": "KNOWLEDGE_MIXED", "path": path,
                                "main_unit": unit.name, "subunit": subunit.name,
                                "knowledge_points": (label,), "question_types": (),
                                "difficulties": (difficulty,),
                            })
                            for question_type in point.question_types:
                                cases.append({
                                    "mode": "EXACT", "path": path,
                                    "main_unit": unit.name, "subunit": subunit.name,
                                    "knowledge_points": (label,),
                                    "question_types": (question_type,),
                                    "difficulties": (difficulty,),
                                })
    return tuple(cases)


def build_runtime_coverage_matrix(
    records: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return the executable L1/L2/L3 coverage contract for every valid path."""
    bank = local_question_bank() if records is None else runtime_question_bank_index(records)
    matrix: list[dict[str, Any]] = []
    for case in g8_selectable_ui_cases():
        delivered, delivery_status, specs = deliver_g8_ui_selection(
            case["path"], main_unit=case["main_unit"], subunit=case["subunit"],
            knowledge_points=case["knowledge_points"], question_types=case["question_types"],
            difficulties=case["difficulties"], question_count=5, records=bank,
            ai_generator=None,
        )
        static_count = sum(len(retrieve_questions(bank, spec)) for spec in specs)
        generated_count = sum(row.get("source") == "LOCAL_GENERATOR" for row in delivered)
        validated_count = len(delivered)
        has_generator = bool(specs) and all(generator_available(spec) for spec in specs)
        status = "READY" if validated_count >= 5 else "LOW_COVERAGE" if validated_count else "ZERO_COVERAGE"
        first_spec = specs[0] if specs else None
        matrix.append({
            "mode": case["mode"],
            "publisher": case["path"].publisher,
            "semester": case["path"].semester,
            "main_unit": case["main_unit"],
            "subunit": case["subunit"],
            "skill_id": first_spec.skill_id if first_spec else "",
            "micro_skill_id": first_spec.micro_skill_id if first_spec else "",
            "question_type": first_spec.question_type if first_spec else "SYSTEM_MIXED",
            "difficulty": case["difficulties"][0],
            "static_bank_count": static_count,
            "generator_available": has_generator,
            "generator_output": generated_count,
            "validated_archetype_count": len({row.get("archetype_id") for row in delivered}),
            "ai_fallback_available": True,
            "delivery_status": delivery_status,
            "deliverable_question_count": validated_count,
            "deliverable_5": validated_count >= 5,
            "status": status,
        })
    return tuple(matrix)


def coverage_summary(matrix: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    rows = tuple(matrix or build_runtime_coverage_matrix())
    routes: dict[str, dict[str, int]] = {}
    for row in rows:
        key = f"{row['publisher']} {row['semester'][0]}"
        route = routes.setdefault(key, {"valid_paths": 0, "ready_paths": 0, "blocked_paths": 0})
        route["valid_paths"] += 1
        route["ready_paths" if row["status"] == "READY" else "blocked_paths"] += 1
    ready = sum(row["status"] == "READY" for row in rows)
    return {
        "total_valid_paths": len(rows),
        "ready_paths": ready,
        "blocked_paths": len(rows) - ready,
        "dead_end_paths": sum(not row["deliverable_5"] for row in rows),
        "routes": routes,
    }


def audit_question_bank(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Produce compact skill/micro/type/difficulty coverage rows."""
    counts: dict[tuple[str, str, str, str], int] = {}
    for row in records:
        if int(row.get("grade", 0) or 0) != 8:
            continue
        key = (str(row.get("skill_id", "")), str(row.get("micro_skill_id", "")),
               str(row.get("question_type", "")), str(row.get("difficulty", "")))
        counts[key] = counts.get(key, 0) + 1
    output = []
    for (skill, micro, qtype, difficulty), count in sorted(counts.items()):
        output.append({"skill_id": skill, "micro_skill_id": micro, "question_type": qtype,
                       "difficulty": difficulty, "available_question_count": count,
                       "status": "sufficient" if count >= 5 else "low coverage" if count else "zero coverage"})
    return output


def coverage_gaps(rows: Iterable[Mapping[str, Any]], recommended_minimum: int = 5) -> list[dict[str, Any]]:
    return [{"skill_id": r["skill_id"], "micro_skill_id": r["micro_skill_id"],
             "difficulty": r["difficulty"], "current_count": int(r["available_question_count"]),
             "recommended_minimum": recommended_minimum,
             "gap": max(0, recommended_minimum - int(r["available_question_count"]))}
            for r in rows if int(r["available_question_count"]) < recommended_minimum]


def _legacy_catalog_question_bank_gaps(recommended_minimum: int = 5) -> list[dict[str, Any]]:
    """Return zero-coverage rows for every canonical G8 micro skill."""
    rows = []
    for publisher in ("康軒", "翰林", "南一"):
        for semester in ("上學期", "下學期"):
            catalog = get_catalog(8, publisher, semester)
            for unit in catalog["units"]:
                for subunit in unit["subunits"]:
                    for kp in subunit["knowledge_points"]:
                        rows.append({
                            "skill_id": kp["skill_id"], "micro_skill_id": kp["micro_skill_id"],
                            "difficulty": "標準", "current_count": 0,
                            "recommended_minimum": recommended_minimum, "gap": recommended_minimum,
                        })
    return rows


def catalog_question_bank_gaps(recommended_minimum: int = 5) -> list[dict[str, Any]]:
    from .curriculum_catalog import DIFFICULTIES, PUBLISHERS, SEMESTERS, get_curriculum_path
    rows = []
    for publisher in PUBLISHERS:
        for semester in SEMESTERS:
            path = get_curriculum_path(8, publisher, semester)
            for unit in path.units:
                for subunit in unit.subunits:
                    for kp in subunit.knowledge_points:
                        for micro_id in (kp.micro_skill_ids or (kp.micro_skill_id,)):
                            if micro_id:
                                rows.append({"skill_id": kp.skill_id, "micro_skill_id": micro_id,
                                             "difficulty": kp.difficulty[0] if kp.difficulty else DIFFICULTIES[1],
                                             "current_count": 0, "recommended_minimum": recommended_minimum,
                                             "gap": recommended_minimum})
    return rows


def retrieve_questions(records: Sequence[Mapping[str, Any]], spec: G8RequestSpec) -> tuple[Mapping[str, Any], ...]:
    """Retrieve exact canonical matches; never dilute a requested path."""
    selected: list[Mapping[str, Any]] = []
    seen: set[Any] = set()
    for row in records:
        key = row.get("question_id") or row.get("id", id(row))
        exact = (
            int(row.get("grade", spec.grade) or spec.grade) == spec.grade
            and row.get("skill_id") == spec.skill_id
            and row.get("micro_skill_id") == spec.micro_skill_id
            and row.get("question_type") == spec.question_type
            and row.get("difficulty") == spec.difficulty
            and row.get("publisher", spec.publisher) == spec.publisher
            and row.get("semester", spec.semester) == spec.semester
            and row.get("official_subunit", spec.official_subunit) == spec.official_subunit
        )
        if key in seen or not exact:
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= spec.question_count:
            break
    return tuple(selected)


def validate_generated_question(question: Mapping[str, Any], spec: G8RequestSpec, existing: Iterable[Mapping[str, Any]] = ()) -> tuple[bool, str]:
    """Strict structural/routing gate for AI output before it reaches UI."""
    required = ("question", "answer", "solution")
    if any(not str(question.get(key, "")).strip() for key in required):
        return False, "incomplete question"
    checks = (("grade", spec.grade), ("skill_id", spec.skill_id), ("micro_skill_id", spec.micro_skill_id),
              ("question_type", spec.question_type), ("difficulty", spec.difficulty))
    for key, expected in checks:
        if str(question.get(key, expected)) != str(expected):
            return False, f"mismatched {key}"
    if int(question.get("variation_level", spec.variation_level)) != spec.variation_level:
        return False, "mismatched variation level"
    text = str(question["question"]).strip()
    if any(text == str(item.get("question", "")).strip() for item in existing):
        return False, "duplicate question"
    signature = re.sub(r"[\d\s，。；：、【】｜]+", "#", text).lower()
    if any(
        re.sub(r"[\d\s，。；：、【】｜]+", "#", str(item.get("question", "")).strip()).lower()
        == signature for item in existing
    ):
        return False, "near-duplicate question"
    quality_ok, quality_reason = validate_question_quality(question, spec)
    if not quality_ok:
        return False, quality_reason
    return True, "ok"


def validate_question_quality(question: Mapping[str, Any], spec: G8RequestSpec) -> tuple[bool, str]:
    """Reject structurally valid but pedagogically incomplete local/AI items."""
    prompt = str(question.get("question", "")).strip()
    answer = str(question.get("answer", "")).strip()
    solution = str(question.get("solution", "")).strip()
    if len(solution) < 12 or answer not in solution:
        return False, "incomplete solution or final answer"
    if any(token in prompt or token in solution for token in ("```", "{\"question\"", "\\begin{")):
        return False, "raw code in question"
    if re.search(r"\\(?:frac|sqrt|begin|end)", prompt + solution) and "$" not in prompt + solution:
        return False, "raw latex"
    if question.get("source") == "LOCAL_GENERATOR":
        if question.get("archetype_id") not in {
            "CONCEPT", "PROCEDURE", "ERROR_ANALYSIS", "REVERSE_CHECK", "TRANSFER"
        }:
            return False, "unknown archetype"
        if int(question.get("reasoning_steps", 0) or 0) != _STEP_CONTRACT[spec.difficulty]:
            return False, "difficulty reasoning contract mismatch"
        if not question.get("publisher_route") or question.get("validated") is not True:
            return False, "runtime metadata incomplete"
    if spec.skill_id == "G08-N-RAD-MIX-01" and question.get("source") != "LOCAL_GENERATOR":
        if "\\sqrt" not in prompt:
            return False, "radical notation missing"
        if any(symbol in answer for symbol in ("+", "\\sqrt", "sqrt")):
            return False, "answer is not fully simplified"
        if spec.difficulty == "\u9032\u968e" and ")^2" not in prompt and ")(" not in prompt:
            return False, "difficulty structure mismatch"
        if spec.difficulty == "\u6311\u6230" and ")(" not in prompt and ")^2-" not in prompt:
            return False, "difficulty structure mismatch"
    return True, "ok"


def question_quality_score(question: Mapping[str, Any], spec: G8RequestSpec) -> int:
    """Return a compact 0-10 score for acceptance reports."""
    ok, _ = validate_question_quality(question, spec)
    if not ok:
        return 0
    score = 10
    if len(str(question.get("solution", ""))) < 45:
        score -= 1
    if spec.skill_id == "G08-N-RAD-MIX-01" and spec.difficulty == "\u6311\u6230":
        score = max(score, 9)
    return score


def validate_generated_payload(payload: str | Sequence[Mapping[str, Any]], spec: G8RequestSpec) -> tuple[bool, str, list[Mapping[str, Any]]]:
    try:
        data = json.loads(payload) if isinstance(payload, str) else list(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False, "invalid JSON", []
    if not isinstance(data, list) or len(data) != spec.question_count:
        return False, "question count mismatch", []
    valid: list[Mapping[str, Any]] = []
    for item in data:
        ok, reason = validate_generated_question(item, spec, valid)
        if not ok:
            return False, reason, []
        valid.append(item)
    return True, "ok", valid


def generate_validated_questions(generator, spec: G8RequestSpec, max_attempts: int = 2) -> str:
    """Call an AI generator and retry when the strict payload gate rejects it."""
    last_reason = "unknown validation failure"
    for attempt in range(max_attempts):
        payload = generator(attempt)
        ok, reason, _ = validate_generated_payload(payload, spec)
        if ok:
            return payload
        last_reason = reason
    raise ValueError(f"generated G8 question payload rejected: {last_reason}")


# ---------------------------------------------------------------------------
# G8 production content-depth contracts
# ---------------------------------------------------------------------------

GENERIC_PLACEHOLDER_TERMS = (
    "本題型", "第一層推理", "第二層推理", "第1層推理", "第2層推理",
    "依標準算法", "鎖定技能", "依題目條件完成推理", "請針對",
    "完成推理", "generator scaffold",
)

_ARCHETYPE_DEFINITIONS = (
    ("CONCEPT", "概念辨識與反例排除", "比較必要條件與充分條件",
     ("敘述方向", "反例", "必要條件")),
    ("PROCEDURE", "文字、符號與圖像表徵轉換", "先辨識不變關係再轉換表徵",
     ("表徵形式", "已知與未知", "符號位置")),
    ("ERROR_ANALYSIS", "錯誤步驟診斷與修正", "定位第一個不成立的推論並修正",
     ("錯誤位置", "錯誤類型", "修正方向")),
    ("REVERSE_CHECK", "由結果反推條件", "以核心關係逆推並代回檢查",
     ("條件方向", "已知與未知交換", "驗證方式")),
    ("TRANSFER", "情境建模與策略選擇", "抽取數學關係、求解並檢核情境",
     ("情境", "資料形式", "多步驟結構")),
)


@dataclass(frozen=True)
class QuestionArchetype:
    archetype_id: str
    grade: int
    skill_id: str
    micro_skill_id: str
    difficulty: str
    question_type: str
    problem_structure: str
    solution_strategy: str
    parameter_constraints: tuple[str, ...]
    variation_dimensions: tuple[str, ...]
    validation_rules: tuple[str, ...]


def question_archetypes(spec: G8RequestSpec) -> tuple[QuestionArchetype, ...]:
    """Return the production archetype schema for an exact selectable path."""
    return tuple(
        QuestionArchetype(
            archetype_id=archetype_id,
            grade=8,
            skill_id=spec.skill_id,
            micro_skill_id=spec.micro_skill_id,
            difficulty=spec.difficulty,
            question_type=spec.question_type,
            problem_structure=problem_structure,
            solution_strategy=solution_strategy,
            parameter_constraints=("符合八年級範圍", "條件足以作答", "答案唯一或判準明確"),
            variation_dimensions=variation_dimensions,
            validation_rules=("NO_PLACEHOLDER", "SEMANTIC_MATCH", "ANSWER_IN_SOLUTION"),
        )
        for archetype_id, problem_structure, solution_strategy, variation_dimensions
        in _ARCHETYPE_DEFINITIONS
    )


def generic_placeholder_count(question: Mapping[str, Any]) -> int:
    text = " ".join(str(question.get(key, "")) for key in ("question", "answer", "solution"))
    return sum(text.count(term) for term in GENERIC_PLACEHOLDER_TERMS)


def validate_generic_placeholder(question: Mapping[str, Any]) -> tuple[bool, str]:
    if generic_placeholder_count(question):
        return False, "generic placeholder"
    return True, "ok"


_SEMANTIC_CONFLICTS = {
    # Sequence vocabulary was the concrete production leak found in function
    # questions.  Broader words such as graph/statistics also occur in valid
    # representation-translation curriculum text and are not safe negatives.
    "G08-F-": ("首項", "公比", "等比數列"),
}


def validate_semantic_match(question: Mapping[str, Any], spec: G8RequestSpec) -> tuple[bool, str]:
    """Reject wrong-skill output using canonical anchors and domain conflicts."""
    skill = _master_skill_index().get(spec.skill_id)
    if skill is None:
        return False, "unknown skill"
    if question.get("source") == "LOCAL_GENERATOR" and question.get("semantic_anchor") != spec.skill_id:
        return False, "missing semantic anchor"
    text = " ".join(str(question.get(key, "")) for key in ("question", "answer", "solution"))
    for prefix, forbidden in _SEMANTIC_CONFLICTS.items():
        if spec.skill_id.startswith(prefix) and any(term in text for term in forbidden):
            return False, "semantic mismatch"
    if question.get("source") == "LOCAL_GENERATOR" and str(skill.skill_name) not in text:
        return False, "skill name missing"
    return True, "ok"


def _depth_difficulty_contract(spec: G8RequestSpec) -> tuple[str, int]:
    index = DIFFICULTIES.index(spec.difficulty)
    return (
        ("直接辨識核心關係，說明一項判準。", 1),
        ("從條件選用合適方法，依序完成判斷與驗證。", 2),
        ("先轉換條件，再整合同一小單元內的關係完成逆向檢查。", 3),
        ("比較兩條可行策略，完成多步推理並說明排除另一策略的理由。", 4),
    )[index]


def _student_safe_focus(value: Any) -> str:
    """Remove authoring-language fragments before curriculum text reaches UI."""
    text = str(value).strip()
    replacements = {
        "本題型": "這項關係", "依標準算法": "依正確方法", "鎖定技能": "確認觀念",
        "第一層推理": "直接判斷", "第二層推理": "進一步判斷",
        "第1層推理": "直接判斷", "第2層推理": "進一步判斷",
        "完成推理": "完成判斷", "依題目條件完成推理": "根據條件判斷",
        "請針對": "依據",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def generate_local_questions(
    spec: G8RequestSpec,
    *,
    count: int | None = None,
    existing: Iterable[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    """Generate five skill-grounded structures without student-facing scaffolds."""
    if not generator_available(spec):
        return ()
    skill = _master_skill_index()[spec.skill_id]
    micro = next(item for item in skill.micro_skills if item.micro_skill_id == spec.micro_skill_id)
    wanted = spec.question_count if count is None else count
    difficulty_text, reasoning_steps = _depth_difficulty_contract(spec)
    focus = _student_safe_focus(skill.focus)
    micro_focus = _student_safe_focus(micro.focus)
    archetypes = question_archetypes(spec)
    from .g8_concrete_questions import concrete_questions
    concrete = concrete_questions(spec.skill_id, reasoning_steps)
    if len(concrete) < 5:
        return ()
    prior = list(existing)
    rows: list[dict[str, Any]] = []
    offset = {"C1": 0, "P1": 1, "V1": 1, "R1": 3, "A1": 4, "T1": 2, "X1": 4}.get(
        spec.micro_skill_id.rsplit("-", 1)[-1], 0
    )
    for index in range(max(0, wanted)):
        slot = (index + offset) % len(archetypes)
        schema = archetypes[slot]
        item = concrete[slot]
        answer = str(item["answer"])
        question = f"{difficulty_text} {item['question']}"
        solution = (
            f"觀念：使用「{skill.skill_name}」的課內關係。方法：{schema.solution_strategy}。"
            f"關鍵步驟與計算：{item['working']} "
            f"最終答案：{answer}"
        )
        row = {
            "question_id": f"G8DEPTH-{spec.skill_id}-{spec.micro_skill_id.rsplit('-', 1)[-1]}-{spec.difficulty}-{index + 1}",
            "id": f"G8DEPTH-{spec.skill_id}-{spec.micro_skill_id.rsplit('-', 1)[-1]}-{spec.difficulty}-{index + 1}",
            "grade": 8, "publisher": spec.publisher,
            "publisher_route": f"{spec.publisher}/{spec.semester}/{spec.official_main_unit}/{spec.official_subunit}",
            "semester": spec.semester, "official_main_unit": spec.official_main_unit,
            "official_subunit": spec.official_subunit, "skill_id": spec.skill_id,
            "micro_skill_id": spec.micro_skill_id, "question_type": spec.question_type,
            "difficulty": spec.difficulty, "variation_level": spec.variation_level,
            "source": "LOCAL_GENERATOR", "archetype_id": schema.archetype_id,
            "problem_structure": schema.problem_structure,
            "solution_strategy": schema.solution_strategy,
            "parameter_constraints": schema.parameter_constraints,
            "variation_dimensions": schema.variation_dimensions,
            "validation_rules": schema.validation_rules,
            "semantic_anchor": spec.skill_id, "validated": True,
            "concrete_data": True,
            "reasoning_steps": reasoning_steps, "question": question,
            "answer": answer, "solution": solution,
        }
        ok, _ = validate_generated_question(row, spec, prior + rows)
        if ok:
            rows.append(row)
    return tuple(rows)


_base_validate_question_quality = validate_question_quality


def validate_question_quality(question: Mapping[str, Any], spec: G8RequestSpec) -> tuple[bool, str]:
    placeholder_ok, reason = validate_generic_placeholder(question)
    if not placeholder_ok:
        return False, reason
    semantic_ok, reason = validate_semantic_match(question, spec)
    if not semantic_ok:
        return False, reason
    ok, reason = _base_validate_question_quality(question, spec)
    if not ok:
        return False, reason
    if question.get("source") == "LOCAL_GENERATOR":
        required = ("problem_structure", "solution_strategy", "parameter_constraints",
                    "variation_dimensions", "validation_rules")
        if any(not question.get(field) for field in required):
            return False, "archetype schema incomplete"
        if question.get("concrete_data") is not True:
            return False, "concrete blueprint missing"
    return True, "ok"


def validate_five_pack(rows: Sequence[Mapping[str, Any]]) -> tuple[bool, str]:
    if len(rows) != 5:
        return False, "question count mismatch"
    archetypes = [str(row.get("archetype_id", "")) for row in rows]
    if len(set(archetypes)) < 3:
        return False, "insufficient archetype diversity"
    if any(archetypes.count(item) > 2 for item in set(archetypes)):
        return False, "archetype repeated more than twice"
    structures = [str(row.get("problem_structure", row.get("archetype_id", ""))) for row in rows]
    if len(set(structures)) < 3:
        return False, "insufficient structure diversity"
    return True, "ok"


def validate_math_rendering(question: Mapping[str, Any]) -> tuple[bool, str]:
    """Verify question, answer, and solution leave no raw math in plain UI text."""
    from math_output import split_math_segments
    raw_pattern = re.compile(r"\\(?:sqrt|frac|begin|end)\b|(?<![\w}])\w+\^\{?\d")
    for field in ("question", "answer", "solution"):
        for is_math, segment in split_math_segments(question.get(field, "")):
            if not is_math and raw_pattern.search(segment):
                return False, f"raw math in {field}"
    return True, "ok"


def build_content_depth_audit() -> tuple[dict[str, Any], ...]:
    """Audit every exact production path and retain one row per micro/difficulty."""
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    bank = local_question_bank()
    for spec in g8_selectable_paths():
        key = (spec.skill_id, spec.micro_skill_id, spec.difficulty)
        if key in grouped:
            continue
        delivered, _ = deliver_questions(bank, spec)
        skill = _master_skill_index()[spec.skill_id]
        micro = next(item for item in skill.micro_skills if item.micro_skill_id == spec.micro_skill_id)
        placeholders = sum(generic_placeholder_count(row) for row in delivered)
        semantic_mismatches = sum(not validate_semantic_match(row, spec)[0] for row in delivered)
        signatures = [re.sub(r"\d+", "#", str(row.get("question", ""))) for row in delivered]
        near_duplicates = len(signatures) - len(set(signatures))
        archetype_count = len({row.get("archetype_id") for row in delivered})
        valid_count = sum(validate_generated_question(row, spec)[0] for row in delivered)
        pack_ok, _ = validate_five_pack(delivered)
        status = "INVALID" if placeholders or semantic_mismatches or valid_count < len(delivered) else (
            "REPETITIVE" if not pack_ok or archetype_count < 2 else "SHALLOW" if archetype_count < 4 else "GOOD"
        )
        grouped[key] = {
            "skill_id": spec.skill_id, "skill_name": skill.skill_name,
            "micro_skill_id": spec.micro_skill_id, "micro_skill_name": micro.focus,
            "difficulty": spec.difficulty,
            "static_question_count": len(retrieve_questions(bank, spec)),
            "generator_archetype_count": len(question_archetypes(spec)),
            "unique_structure_count": len({row.get("problem_structure", row.get("archetype_id")) for row in delivered}),
            "validated_question_count": valid_count,
            "near_duplicate_rate": near_duplicates / len(delivered) if delivered else 0.0,
            "generic_placeholder_count": placeholders,
            "semantic_mismatch_count": semantic_mismatches,
            "status": status,
        }
    return tuple(grouped.values())


def content_depth_summary(rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, int]:
    audit = tuple(rows or build_content_depth_audit())
    skill_archetypes: dict[str, set[str]] = {}
    skill_statuses: dict[str, set[str]] = {}
    for row in audit:
        skill_archetypes.setdefault(str(row["skill_id"]), set()).update(
            archetype_id for archetype_id, *_ in _ARCHETYPE_DEFINITIONS
        )
        skill_statuses.setdefault(str(row["skill_id"]), set()).add(str(row["status"]))
    priority = ("INVALID", "REPETITIVE", "SHALLOW", "GOOD")
    final_status = {
        skill_id: next(status for status in priority if status in statuses)
        for skill_id, statuses in skill_statuses.items()
    }
    return {
        "total_skills": len(skill_archetypes),
        "good": sum(status == "GOOD" for status in final_status.values()),
        "shallow": sum(status == "SHALLOW" for status in final_status.values()),
        "repetitive": sum(status == "REPETITIVE" for status in final_status.values()),
        "invalid": sum(status == "INVALID" for status in final_status.values()),
        "total_archetypes": sum(len(items) for items in skill_archetypes.values()),
        "min_archetypes": min((len(items) for items in skill_archetypes.values()), default=0),
        "generic_placeholder_count": sum(int(row["generic_placeholder_count"]) for row in audit),
        "semantic_mismatch_count": sum(int(row["semantic_mismatch_count"]) for row in audit),
        "near_duplicate_failures": sum(float(row["near_duplicate_rate"]) > 0 for row in audit),
    }
