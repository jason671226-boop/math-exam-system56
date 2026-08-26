import csv
import json

from scripts import stage7_private_jh_coverage_batch3 as batch


def test_locator_is_number_fingerprint_text_bound_and_unique():
    located = batch._locate()
    assert set(located) == {8, 9, 10, 11}
    assert len({entry["fingerprint"] for entry in located.values()}) == 4
    for entry in located.values():
        fields = list(entry["coverage"])
        assert entry["coverage"][fields[3]] == entry["question"]["question_text"]


def test_batch_ingests_one_gt_three_source_cases_with_parent_validation():
    status = batch.ingest(force=True)
    assert status["teacher_batch"] == {"reviewed": 4, "human_validated": 1,
        "source_reextraction": 2, "image_chart_reextraction": 1,
        "id_validation_failures": 0, "parent_failures": 0}
    gt = {row["fingerprint"]: row for row in batch._jsonl(batch.GT)}
    located = batch._locate()
    validated = gt[located[9]["fingerprint"]]
    assert validated["human_primary_skill_id"] == "G05-N-FACTOR-01"
    assert validated["human_primary_micro_id"] == "G05-N-FACTOR-01-C1"
    assert all(gt[located[n]["fingerprint"]]["human_primary_skill_id"] is None for n in (8, 10, 11))


def test_cleaning_queue_and_v4_are_private_deduplicated_and_bom():
    status = batch.ingest()
    items = json.loads(batch.CLEANING.read_text(encoding="utf-8-sig"))["items"]
    assert len(items) == status["source_quality"]["source_cleaning_queue_total"]
    assert len({item["fingerprint"] for item in items}) == len(items)
    reasons = {item.get("reason") for item in items}
    assert {"MULTI_DOCUMENT_CONTAMINATION", "MATH_EXPRESSION_INCOMPLETE", "MISSING_REQUIRED_CHART"} <= reasons
    assert batch.TEACHER_V4.read_bytes().startswith(b"\xef\xbb\xbf")
    with batch.TEACHER_V4.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == status["teacher_review"]["remaining_questions"]
    question_col = list(rows[0])[3] if rows else None
    assert not rows or len({row[question_col] for row in rows}) == len(rows)


def test_no_fake_human_validation_or_external_calls():
    status = batch.ingest()
    assert status["api_calls"] == status["production_reads"] == status["production_writes"] == 0
    assert status["teacher_review"]["removed_by_human_gt"] == 1
