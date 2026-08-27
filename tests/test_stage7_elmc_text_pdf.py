from pathlib import Path

from services.elmc_text_pdf import fingerprint, quality_risks, validate_mapping
from services.elementary_competition import COMPETITION_THINKING_SKILLS, COMPETITION_TOPICS


def test_fingerprint_ignores_layout_but_not_numbers():
    assert fingerprint("第 1 題：3＋5") == fingerprint("第1題: 3＋5")
    assert fingerprint("3＋5") != fingerprint("3＋6")


def test_ocr_quality_gates_fail_closed():
    assert "MISSING_REQUIRED_DIAGRAM" in quality_risks("依右圖求陰影部分面積")
    assert "MISSING_REQUIRED_CHART" in quality_risks("依下列折線圖回答")
    assert quality_risks("小明有 13 顆球，送出 3 顆") == []


def test_mapping_parent_and_taxonomies():
    skills={"S":{"skill_id":"S"}}; micros={"M":{"micro_skill_id":"M","parent_skill_id":"S"}}
    row={"scope":"ELEMENTARY_COMPETITION","foundation_grade":"G5","foundation_skill_id":"S","foundation_micro_skill_id":"M","secondary_skill_ids":[],"competition_topic":"LOGIC","thinking_skills":["CASE_SPLIT"]}
    assert validate_mapping(row,skills,micros,set(COMPETITION_TOPICS),set(COMPETITION_THINKING_SKILLS)) == []
    row["foundation_skill_id"]="BAD"
    assert {"INVALID_SKILL","MICRO_PARENT_MISMATCH"}.issubset(validate_mapping(row,skills,micros,set(COMPETITION_TOPICS),set(COMPETITION_THINKING_SKILLS)))


def test_out_of_elementary_grade_rejected():
    row={"scope":"ELEMENTARY_COMPETITION","foundation_grade":"G7","foundation_skill_id":"S","foundation_micro_skill_id":"M","secondary_skill_ids":[],"competition_topic":"LOGIC","thinking_skills":[]}
    assert "OUT_OF_SCOPE_GRADE" in validate_mapping(row,{"S":{}},{"M":{"parent_skill_id":"S"}},set(COMPETITION_TOPICS),set(COMPETITION_THINKING_SKILLS))


def test_local_artifacts_are_ignored():
    root=Path(__file__).resolve().parents[1]
    assert ".local" in (root/".gitignore").read_text(encoding="utf-8-sig")
