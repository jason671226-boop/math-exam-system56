from scripts.stage7_git_guard import validate_staged


def test_guard_allows_sanitized_human_review_code_but_blocks_private_artifacts():
    assert validate_staged(["scripts/stage7_private_jh_human_review.py"])==[]
    errors=validate_staged([".local/stage7_private_jh/review.csv","exports/HUMAN_REVIEW.csv"])
    assert len(errors)==2 and all(error.startswith("FORBIDDEN_STAGED_PATH:") for error in errors)


def test_guard_still_blocks_secret_and_raw_result_paths():
    errors=validate_staged(["secrets.toml","data/model_raw.jsonl","data/raw_mapping.csv"])
    assert len(errors)==3
