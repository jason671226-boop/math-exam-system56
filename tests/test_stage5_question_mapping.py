from services.stage5_question_mapping import (
    build_candidate_packet,
    deduplicate_questions,
    mapping_review_status,
    normalize_question_text,
    question_fingerprint,
    stratified_sample,
    validate_mapping,
)


def test_normalize_and_fingerprint_are_stable():
    assert normalize_question_text("  x²＋  3x = 4  ") == "x2+ 3x = 4"
    assert question_fingerprint("A  B") == question_fingerprint("A B")


def test_deduplicate_collapses_rows_and_flags_conflict():
    rows = [
        {"id": 2, "index_code": "B", "new_question": "x + 1 = 2", "correct_answer": "1", "unit": "一次式", "knowledge_tag": "方程式"},
        {"id": 1, "index_code": "A", "new_question": "x + 1 = 2 ", "correct_answer": "1", "unit": "一次式", "knowledge_tag": "方程式"},
    ]
    unique = deduplicate_questions(rows)
    assert len(unique) == 1
    assert unique[0]["representative_id"] == 1
    assert unique[0]["duplicate_count"] == 2
    assert unique[0]["has_metadata_conflict"] is False


def test_stratified_sample_is_deterministic_and_covers_strata():
    rows = []
    for unit, tag, count in [("A", "a", 6), ("B", "b", 5), ("C", "c", 4)]:
        for i in range(count):
            rows.append({"fingerprint": f"{unit}{i}", "unit": unit, "knowledge_tag": tag})
    first = stratified_sample(rows, sample_size=8, seed="X")
    second = stratified_sample(rows, sample_size=8, seed="X")
    assert [row["fingerprint"] for row in first] == [row["fingerprint"] for row in second]
    assert {row["unit"] for row in first} == {"A", "B", "C"}


def test_candidate_packet_and_mapping_validation():
    question = {"fingerprint": "f", "question_text": "利用平方差公式分解 x^2-9", "answer_text": "(x-3)(x+3)", "unit": "乘法公式與多項式", "knowledge_tag": "平方差公式應用"}
    skills = [
        {"skill_id": "S1", "main_unit": "乘法公式與多項式", "subunit": "乘法公式", "skill_name": "平方差公式", "focus": "運用平方差公式", "difficulty": 2},
        {"skill_id": "S2", "main_unit": "根式的運算", "subunit": "根式", "skill_name": "化簡根式", "focus": "根式化簡", "difficulty": 2},
    ]
    micros = [
        {"micro_skill_id": "M1", "parent_skill_id": "S1", "skill_name": "平方差公式", "focus": "a²-b²", "question_type": "計算", "item_pattern": "因式分解", "common_error": "符號", "difficulty": 2},
        {"micro_skill_id": "M2", "parent_skill_id": "S2", "skill_name": "根式", "focus": "化簡", "question_type": "計算", "item_pattern": "根式", "common_error": "根號", "difficulty": 2},
    ]
    packet = build_candidate_packet(question, skills, micros, skill_limit=2, micro_limit=2)
    assert packet["skill_candidates"][0]["skill_id"] == "S1"
    assert validate_mapping({"skill_id": "S1", "micro_skill_id": "M1", "confidence": 0.91}, {"S1": skills[0]}, {"M1": micros[0]}) == []
    assert "MICRO_PARENT_MISMATCH" in validate_mapping({"skill_id": "S1", "micro_skill_id": "M2", "confidence": 0.91}, {"S1": skills[0]}, {"M2": micros[1]})
    assert mapping_review_status(0.85) == "AUTO_CANDIDATE"
    assert mapping_review_status(0.7) == "REVIEW"
    assert mapping_review_status(0.3) == "REJECT"
