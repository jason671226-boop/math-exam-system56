import json

from scripts import stage5_g5_foundation as g5


def test_grade_configuration_and_model():
    assert g5.GRADE == "G5"
    assert g5.MODEL == "gemini-3.6-flash"
    assert g5.IN_SCOPE == "IN_SCOPE_G5"
    assert g5.OUT_SCOPE == "OUT_OF_SCOPE_G5"


def test_curriculum_integrity(tmp_path, monkeypatch):
    monkeypatch.setattr(g5, "LOCAL", tmp_path)
    result = g5.curriculum_audit()
    assert result["curriculum_integrity"] == "PASS"
    assert result["skills"] > 0 and result["micro_skills"] > 0
    assert result["production_reads"] == result["production_writes"] == 0


def test_selection_spans_ten_units():
    skills = g5.read_csv(g5.GRADE_DIR / "standard_skills.csv")
    selected = g5.choose_skills(skills)
    assert len(selected) == 10
    assert len({row["mathai_main_unit"] for row in selected}) == 10


def test_prepare_is_synthetic_and_local(tmp_path, monkeypatch):
    monkeypatch.setattr(g5, "LOCAL", tmp_path)
    result = g5.prepare_set("tuning")
    rows = g5.read_jsonl(tmp_path / "synthetic/tuning/questions.jsonl")
    assert result["questions"] == 34
    assert result["skills"] == result["main_units"] == 10
    assert all(row["synthetic_validation"] is True for row in rows)
    assert len({row["fingerprint"] for row in rows}) == len(rows)


def test_g5_mapping_validation():
    skills = {"S": {"skill_id": "S"}}
    micros = {"M": {"micro_skill_id": "M", "parent_skill_id": "S"}}
    row = {"scope_status": g5.IN_SCOPE, "predicted_skill_id": "S",
           "predicted_micro_skill_id": "M", "confidence": 0.8}
    assert g5.validate_result(row, skills, micros) == []


def test_resilient_parser_and_checkpoint_resume(tmp_path, monkeypatch):
    assert g5.response_json_resilient('```json\n{"scope_status":"IN_SCOPE_G5",}\n```')["scope_status"] == g5.IN_SCOPE
    monkeypatch.setattr(g5.core, "LOCAL", tmp_path)
    base = tmp_path / "synthetic/tuning"
    base.mkdir(parents=True)
    row = {"fingerprint": "fp", "question_text": ""}
    base.joinpath("questions.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    calls = []
    def fake(prompt, model):
        calls.append(model)
        return '{"scope_status":"OUT_OF_SCOPE_G5","predicted_skill_id":"","predicted_micro_skill_id":"","confidence":0.8}'
    first = g5.core.map_set("tuning", generate=fake)
    second = g5.core.map_set("tuning", generate=fake)
    assert first["completed"] == second["completed"] == 1
    assert second["resumed"] == 1
    assert calls == [g5.MODEL]


def test_no_supabase_or_forbidden_model_in_runner():
    source = g5.Path(g5.__file__).read_text(encoding="utf-8").lower()
    assert ".create_client(" not in source
    assert "service_role" not in source
    assert "gemini-2.5-flash" not in source
