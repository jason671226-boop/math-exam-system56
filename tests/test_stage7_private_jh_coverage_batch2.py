import csv
import json

from scripts import stage7_private_jh_coverage_batch2 as batch


def test_locator_uses_coverage_number_fingerprint_and_exact_text():
    rows=batch._locate();assert set(rows)==set(range(8,13)) and len({r["fingerprint"] for r in rows.values()})==5
    assert all(r["coverage"]["題目"]==r["question"]["question_text"] for r in rows.values())


def test_batch_ingest_four_gt_one_image_source_and_parent_valid():
    status=batch.ingest();assert status["human_validated"]==4 and status["image_reextraction"]==1
    assert status["id_validation_failures"]==status["parent_failures"]==0
    gt={r["fingerprint"]:r for r in batch._jsonl(batch.GT)};located=batch._locate()
    assert sum(gt[r["fingerprint"]]["source_status"]=="HUMAN_VALIDATED" for r in located.values())==4
    image=gt[located[9]["fingerprint"]];assert image["source_status"]=="SOURCE_IMAGE_REQUIRED" and image["human_primary_skill_id"] is None


def test_source_cleaning_and_v3_are_private_bom_deduplicated():
    status=batch.ingest();clean=json.loads(batch.CLEANING.read_text(encoding="utf-8-sig"))["items"]
    assert sum(r.get("status")=="NEEDS_IMAGE_REEXTRACTION" for r in clean)==status["human_coverage"]["missing_image_queue"]
    assert batch.TEACHER_V3.read_bytes().startswith(b"\xef\xbb\xbf")
    with batch.TEACHER_V3.open(encoding="utf-8-sig",newline="") as h:rows=list(csv.DictReader(h))
    assert len(rows)==status["teacher_review"]["remaining_questions"] and len({r["題目"] for r in rows})==len(rows)


def test_no_fake_validation_or_external_calls():
    status=batch.ingest();assert status["api_calls"]==status["production_reads"]==status["production_writes"]==0
