import csv
import json

import pytest

from scripts import stage7_private_jh_human_gt as gt
from services.stage7_profiles import build_profile, load_curriculum_catalog, validate_mapping_result


def test_teacher_gt_ingest_is_unique_valid_and_excludes_source_invalid():
    status=gt.ingest();all_rows=gt._jsonl(gt.GT);rows=[row for row in all_rows if int(row["source_review_number"])<=15]
    assert len(rows)==len({row["fingerprint"] for row in rows})==15
    assert sum(row["source_status"]=="HUMAN_VALIDATED" for row in rows)==14
    invalid=[row for row in rows if row["source_status"]=="SOURCE_INVALID"]
    assert len(invalid)==1 and invalid[0]["human_primary_skill_id"] is None and invalid[0]["human_primary_micro_id"] is None
    assert status["human_coverage"]=={"questions":14,"unique_primary_skills":12,"unique_micros":12,"secondary_skills":4,"source_invalid_excluded":True}


def test_all_teacher_ids_and_parents_are_catalog_valid():
    skills,micros=load_curriculum_catalog(("G1","G2","G3","G4","G5","G6"))
    for row in gt._jsonl(gt.GT):
        if row["source_status"]!="HUMAN_VALIDATED":continue
        assert row["human_primary_skill_id"] in skills
        assert row["human_primary_micro_id"] in micros
        assert micros[row["human_primary_micro_id"]]["parent_skill_id"]==row["human_primary_skill_id"]
        assert all(sid in skills for sid in row["human_secondary_skill_ids"])


def test_review_v2_is_bom_unique_and_does_not_overwrite_v1():
    before=(gt._sha(gt.SIMPLE_V1),gt._sha(gt.TEACHER_V1),gt._sha(gt.QUEUE));status=gt.ingest()
    assert before==(gt._sha(gt.SIMPLE_V1),gt._sha(gt.TEACHER_V1),gt._sha(gt.QUEUE))
    assert gt.SIMPLE_V2.read_bytes().startswith(b"\xef\xbb\xbf") and gt.TEACHER_V2.read_bytes().startswith(b"\xef\xbb\xbf")
    with gt.TEACHER_V2.open(encoding="utf-8-sig",newline="") as handle:rows=list(csv.DictReader(handle))
    assert len(rows)==64 and len({row["題目"] for row in rows})==64 and status["review_queue"]["remaining"]==64


def test_sequence_resolution_fails_closed_on_text_drift():
    simple=gt._csv(gt.SIMPLE_V1);teacher=gt._csv(gt.TEACHER_V1);manifest=json.loads(gt.MANIFEST.read_text(encoding="utf-8-sig"))
    simple[0]["題目"]+=" altered"
    with pytest.raises(RuntimeError,match="REVIEW_TEXT_MISMATCH"):
        gt._resolve(simple,teacher,manifest["questions"],{row["fingerprint"] for row in gt._csv(gt.QUEUE)})


def test_private_jh_scope_gate_accepts_g4_foundation_and_high_difficulty():
    profile=build_profile("PRIVATE_JH")
    assert profile.curriculum_target_grade==("G5","G6") and "G4" in profile.curriculum_foundation_grade
    row={"profile_type":"PRIVATE_JH","scope_status":"PRIVATE_JH","primary_skill_id":"G04-S-ANGLECALC-01","primary_micro_skill_id":"G04-S-ANGLECALC-01-T1",
      "secondary_skill_ids":["G04-N-TIMEAPP-01"],"thinking_skill_ids":[],"primary_thinking_skill_id":"","competition_level":None,"strategy_depth":None,"assessment_style":"HIGH_DIFFICULTY","difficulty":"HIGH"}
    assert validate_mapping_result(row,grades=("G5","G6"))==[]


def test_scope_requires_profile_evidence_and_true_out_scope_is_unmapped():
    out={"profile_type":"PRIVATE_JH","scope_status":"OUT_OF_SCOPE_PROFILE","primary_skill_id":"","primary_micro_skill_id":"","secondary_skill_ids":[],"thinking_skill_ids":[],"primary_thinking_skill_id":"","competition_level":None,"strategy_depth":None,"assessment_style":None}
    assert validate_mapping_result(out,grades=("G5","G6"))==[]
    competition_only={**out,"profile_type":"PRIVATE_JH","scope_status":"PRIVATE_JH","competition_level":"ADVANCED","strategy_depth":4}
    errors=validate_mapping_result(competition_only,grades=("G5","G6"))
    assert "COMPETITION_METADATA_NOT_ALLOWED" in errors


def test_candidate_guidance_never_claims_human_validation():
    guidance=json.loads((gt.ROOT/"data/stage7/private_jh_topic_guidance_v1.json").read_text(encoding="utf-8"))
    assert guidance["status"]=="CANDIDATE_GUIDANCE_ONLY" and guidance["human_validation_implied"] is False
    assert len(guidance["rules"])==5
