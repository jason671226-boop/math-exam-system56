import csv

from scripts import stage7_private_jh_coverage_batch1 as batch


def test_coverage_batch_locator_is_number_fingerprint_text_unique():
    resolved,_=batch._locate();assert set(resolved)==set(range(8,14))
    assert len({x["fingerprint"] for x in resolved.values()})==6
    assert all(x["coverage"]["題目"]==x["question"]["question_text"] for x in resolved.values())


def test_teacher_batch_adds_three_gt_three_source_invalid_with_valid_parents():
    status=batch.ingest();assert status["human_validated"]==3 and status["source_reextraction"]==3 and status["parent_failures"]==0
    resolved,_=batch._locate();gt={r["fingerprint"]:r for r in batch._jsonl(batch.GT)}
    assert sum(gt[x["fingerprint"]]["source_status"]=="HUMAN_VALIDATED" for x in resolved.values())==3
    assert sum(gt[x["fingerprint"]]["source_status"]=="SOURCE_NEEDS_REEXTRACTION" for x in resolved.values())==3


def test_next_teacher_csv_is_bom_dedup_and_v1_preserved():
    before=batch.TEACHER_SET.read_bytes();status=batch.ingest();assert batch.TEACHER_SET.read_bytes()==before
    assert batch.NEXT_TEACHER.read_bytes().startswith(b"\xef\xbb\xbf")
    with batch.NEXT_TEACHER.open(encoding="utf-8-sig",newline="") as handle:rows=list(csv.DictReader(handle))
    assert len(rows)==status["teacher_questions_remaining"] and len({r["題目"] for r in rows})==len(rows)


def test_no_api_or_production_access():
    status=batch.ingest();assert status["api_calls"]==status["production_reads"]==status["production_writes"]==0
