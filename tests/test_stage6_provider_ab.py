from pathlib import Path

import scripts.stage6_provider_ab as ab


def test_select_six_is_diverse_and_ground_truth_complete():
    rows = ab.select_six("G11_A")
    assert len(rows) == 6
    assert len({r.get("expected_skill_id") for r in rows if r.get("expected_skill_id")}) >= 4
    assert all(r.get("expected_scope_status") for r in rows)


def test_checkpoint_key_includes_provider_and_fingerprint(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text('{"provider":"gemini","fingerprint":"abc"}\n', encoding="utf-8")
    rows = ab._load_checkpoint(checkpoint, {("gemini", "abc"), ("deepseek", "abc")})
    assert ("gemini", "abc") in rows
    assert ("deepseek", "abc") not in rows


def test_safe_secret_paths_stay_in_workspace():
    assert all(ab.ROOT in path.parents for path in ab.SAFE_SECRET_PATHS)
