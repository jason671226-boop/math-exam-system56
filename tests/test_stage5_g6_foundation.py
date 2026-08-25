from scripts.stage5_g6_foundation import (
    IN_SCOPE, OUT_SCOPE, choose_skills, gemini_api_key, map_set, pilot_status, response_json_resilient, validate_result,
)


def test_coverage_thresholds_and_skill_selection():
    assert pilot_status(0, 0, 5) == "ZERO_COVERAGE"
    assert pilot_status(1, 1, 5) == "LIMITED_COVERAGE"
    assert pilot_status(3, 2, 5) == "PILOT_COVERED"
    skills = [{"skill_id": str(i), "main_unit": unit} for i, unit in enumerate(
        ["因數與倍數進階", "分數除法", "小數除法", "比與比例", "速率", "數量關係", "比例幾何", "圓與扇形", "柱體", "資料"]
    )]
    chosen = choose_skills(skills)
    assert len(chosen) == 10
    assert len({r["main_unit"] for r in chosen}) == 10


def test_resilient_json_parser():
    assert response_json_resilient("```json\n{\"scope_status\":\"IN_SCOPE_G6\",}\n```")["scope_status"] == IN_SCOPE
    assert response_json_resilient("prefix {\"x\": 1} suffix") == {"x": 1}


def test_mapping_validation_fail_closed():
    skills = {"S": {"skill_id": "S"}}
    micros = {"M": {"micro_skill_id": "M", "parent_skill_id": "S"}}
    valid = {"scope_status": IN_SCOPE, "predicted_skill_id": "S", "predicted_micro_skill_id": "M", "confidence": .8}
    assert validate_result(valid, skills, micros) == []
    invalid = {"scope_status": OUT_SCOPE, "predicted_skill_id": "S", "predicted_micro_skill_id": "M", "confidence": 2}
    assert set(validate_result(invalid, skills, micros)) == {"OUT_OF_SCOPE_MAPPED", "INVALID_CONFIDENCE"}


def test_mapper_checkpoint_resume(tmp_path, monkeypatch):
    import scripts.stage5_g6_foundation as module
    monkeypatch.setattr(module, "LOCAL", tmp_path)
    base = tmp_path / "synthetic/holdout"
    base.mkdir(parents=True)
    rows = [{"fingerprint": "a", "question_text": "x"}, {"fingerprint": "b", "question_text": "y"}]
    base.joinpath("questions.jsonl").write_text("".join(__import__("json").dumps(r) + "\n" for r in rows), encoding="utf-8")
    calls = []
    def fake(prompt, model):
        calls.append(prompt)
        return '{"scope_status":"OUT_OF_SCOPE_G6","predicted_skill_id":"","predicted_micro_skill_id":"","confidence":0.9}'
    first = map_set("holdout", generate=fake)
    second = map_set("holdout", generate=fake)
    assert first["completed"] == second["completed"] == 2
    assert second["resumed"] == 2
    assert len(calls) == 2


def test_gemini_secret_loader_never_prints_or_persists(tmp_path, monkeypatch, capsys):
    import scripts.stage5_g6_foundation as module
    secret = "unit-test-secret-value"
    source = tmp_path / "secrets.toml"
    source.write_text(f'GEMINI_API_KEY = "{secret}"\nSUPABASE_SERVICE_ROLE_KEY = "must-not-read"\n', encoding="utf-8")
    monkeypatch.setattr(module, "GEMINI_SECRET_PATHS", (source,))
    for name in ("G6_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert gemini_api_key() == secret
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert list(tmp_path.iterdir()) == [source]
