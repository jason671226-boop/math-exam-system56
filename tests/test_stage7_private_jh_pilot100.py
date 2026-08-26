import json

import pytest

from scripts import stage7_private_jh_pilot100 as pilot


def test_checkpoint_key_has_profile_fingerprint_provider():
    assert pilot.checkpoint_key("deepseek","abc")=="PRIVATE_JH:abc:deepseek"
    assert pilot.checkpoint_key("gemini","abc")!="PRIVATE_JH:abc:deepseek"


def test_prepare_real_official_unique_sample():
    manifest=pilot.prepare()
    rows=manifest["questions"]
    assert len(rows)==len({r["fingerprint"] for r in rows})==100
    assert manifest["integrity"]=={"sample":100,"unique_fingerprints":100,"official":True,"real_questions":True,
        "synthetic":False,"source_urls_traceable":True,"question_text_complete":True}
    assert len(manifest["holdout_fingerprints"])==70
    assert len(manifest["distribution"]["schools"])>=2


def test_sample_is_not_first_100_and_is_balanced():
    corpus=pilot.read_jsonl(pilot.CORPUS);manifest=pilot.prepare();rows=manifest["questions"]
    assert {r["fingerprint"] for r in rows}!={r["fingerprint"] for r in corpus[:100]}
    school_counts=manifest["distribution"]["schools"]
    assert max(school_counts.values())<=60
    assert len(manifest["distribution"]["topics"])>=12


def test_prompt_disables_thinking_and_requires_parent_constraint():
    row=pilot.prepare()["questions"][0];text=pilot.mapping_prompt(row)
    assert "Thinking skills are disabled" in text
    assert "MUST have parent_skill_id equal to primary_skill_id" in text
    assert "OUT_OF_SCOPE_PROFILE" in text and "PRIVATE_JH" in text


def test_invalid_checkpoint_fails_closed(tmp_path):
    path=tmp_path/"checkpoint.jsonl";path.write_text(json.dumps({"fingerprint":"bad","checkpoint_key":"wrong"})+"\n")
    with pytest.raises(RuntimeError,match="INVALID_PROFILE_PROVIDER_CHECKPOINT"):
        pilot._load_checkpoint(path,"deepseek",{"good"})


def test_metrics_do_not_claim_accuracy_or_validation():
    value=pilot.metrics([],100)
    assert value["completed"]==0 and value["remaining"]==100
    assert "accuracy" not in value


def test_private_artifacts_are_under_ignored_root():
    for path in (pilot.MANIFEST,pilot.DEEPSEEK_CHECKPOINT,pilot.DEEPSEEK_CORRECTIONS,pilot.DEEPSEEK_CORRECTIONS2,pilot.DEEPSEEK_INVALID_ATTEMPTS,pilot.GEMINI_RESULTS,pilot.COMPARISON,pilot.REVIEW,pilot.COVERAGE,pilot.REPORT):
        assert pilot.PILOT in path.parents


def test_correction_artifacts_are_independently_countable(tmp_path):
    first=tmp_path/"corrections1.jsonl";second=tmp_path/"corrections2.jsonl"
    first.write_text("".join(json.dumps({"attempt":1})+"\n" for _ in range(4)),encoding="utf-8")
    second.write_text("".join(json.dumps({"attempt":2})+"\n" for _ in range(2)),encoding="utf-8")
    assert len(pilot.read_jsonl(first))+len(pilot.read_jsonl(second))==6
