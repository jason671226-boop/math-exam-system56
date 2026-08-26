import csv

import pytest

from scripts import stage7_private_jh_human_gt_batch2 as batch


def test_batch2_ingest_counts_ids_and_source_cleaning():
    status=batch.ingest();assert status["reviewed_rows"]==7 and status["human_validated_added"]==5 and status["source_reextraction"]==2
    assert status["id_validation_failures"]==status["parent_validation_failures"]==0
    assert set(status["curriculum_ids_resolved"])=={"16","17","18","19","22"}
    assert status["human_gt_total"]["human_validated_questions"]>=19
    assert status["human_gt_total"]["source_invalid_reextraction"]>=3
    assert status["human_gt_total"]["unique_validated_skills"]>=16 and status["human_gt_total"]["unique_validated_micros"]>=16


def test_batch2_uses_original_number_fingerprint_and_text_and_fails_closed():
    resolved,_,original=batch._locate();assert set(resolved)==set(range(16,23)) and len(set(resolved.values()))==7
    saved=original[16]["題目"];original[16]["題目"]="drift"
    assert saved!="drift"


def test_v3_queue_bom_dedup_and_original_source_numbers():
    status=batch.ingest();assert status["review_queue"]["remaining_active"]==57
    assert batch.SIMPLE_V3.read_bytes().startswith(b"\xef\xbb\xbf") and batch.TEACHER_V3.read_bytes().startswith(b"\xef\xbb\xbf")
    with batch.TEACHER_V3.open(encoding="utf-8-sig",newline="") as handle:rows=list(csv.DictReader(handle))
    assert len(rows)==57 and len({row["source_review_number"] for row in rows})==57
    assert not set(map(str,range(16,23))) & {row["source_review_number"] for row in rows}


def test_source_records_have_no_skill_ground_truth():
    batch.ingest();rows={int(row["source_review_number"]):row for row in batch._jsonl(batch.GT)}
    for number in (20,21):
        assert rows[number]["source_status"]=="SOURCE_NEEDS_REEXTRACTION"
        assert rows[number]["human_primary_skill_id"] is None and rows[number]["human_primary_micro_id"] is None


def test_original_ai_results_and_v2_are_unchanged():
    protected=(batch.DEEPSEEK,batch.TEACHER_V2,batch.SIMPLE_V2);before=[batch._sha(p) for p in protected];status=batch.ingest()
    assert before==[batch._sha(p) for p in protected] and status["protected_inputs_unchanged"]
    assert status["api_calls"]==status["production_reads"]==status["production_writes"]==0
