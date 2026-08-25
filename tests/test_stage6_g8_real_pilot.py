from pathlib import Path

import scripts.stage6_g8_real_pilot as pilot


def test_mapping_prompt_has_scope_gate_and_no_provider_hint():
    prompt = pilot.mapping_prompt({"fingerprint": "f", "question_text": "q", "skill_candidates": [], "micro_candidates": []}, {})
    assert "IN_SCOPE_G8" in prompt and "OUT_OF_SCOPE_G8" in prompt
    assert "DeepSeek" not in prompt and "Gemini" not in prompt


def test_validate_out_of_scope_requires_null_ids():
    good = {"scope_status": "OUT_OF_SCOPE_G8", "skill_id": None, "micro_skill_id": None, "confidence": 0.9}
    bad = {**good, "skill_id": "G8-X"}
    assert pilot.validate(good, {}, {}) == []
    assert "OUT_OF_SCOPE_HAS_SKILL" in pilot.validate(bad, {}, {})


def test_parent_constraint_rejects_cross_skill_micro():
    micros = {"M1": {"parent_skill_id": "S1"}}
    pilot.enforce_micro_parent_constraint({"scope_status": "IN_SCOPE_G8", "skill_id": "S1", "micro_skill_id": "M1"}, micros)
    try:
        pilot.enforce_micro_parent_constraint({"scope_status": "IN_SCOPE_G8", "skill_id": "S2", "micro_skill_id": "M1"}, micros)
    except RuntimeError as exc:
        assert str(exc) == "MICRO_PARENT_CONSTRAINT_FAILED"
    else:
        raise AssertionError("cross-Skill Micro must fail closed")


def test_checkpoint_is_provider_scoped(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pilot, "PRIVATE", tmp_path)
    (tmp_path / "deepseek_checkpoint.jsonl").write_text(
        '{"provider":"deepseek","fingerprint":"f"}\n', encoding="utf-8")
    assert set(pilot.checkpoint_rows()) == {"f"}


def test_agreement_audit_sample_fills_to_twenty():
    rows = [{"fingerprint": str(i), "skill_id": "same", "micro_skill_id": "same", "question_type": "same"} for i in range(25)]
    packets = {str(i): {"unit": "same"} for i in range(25)}
    sample = pilot._agreement_audit_sample(rows, packets)
    assert len(sample) == 20
    assert len({row["fingerprint"] for row in sample}) == 20
