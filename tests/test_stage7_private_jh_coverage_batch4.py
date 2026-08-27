import csv
import json

from scripts import stage7_private_jh_coverage_batch4 as batch


def test_locator_uses_number_fingerprint_and_exact_question_text():
    located = batch._locate()
    assert set(located) == {7, 8, 9, 10}
    assert len({entry["fingerprint"] for entry in located.values()}) == 4
    for entry in located.values():
        fields = list(entry["coverage"])
        assert entry["coverage"][fields[3]] == entry["question"]["question_text"]


def test_ingest_two_gt_two_source_cases_and_validate_parents():
    status = batch.ingest(force=True)
    assert status["teacher_batch"] == {"reviewed": 4, "human_validated": 2,
        "source_reextraction": 2, "id_validation_failures": 0, "parent_failures": 0}
    gt = {row["fingerprint"]: row for row in batch._jsonl(batch.GT)}
    located = batch._locate()
    assert gt[located[9]["fingerprint"]]["human_primary_micro_id"] == "G04-N-DEC2-ADD-01-R1"
    assert gt[located[10]["fingerprint"]]["human_primary_micro_id"] == "G05-N-MULTIPLE-01-R1"
    assert gt[located[10]["fingerprint"]]["human_secondary_skill_ids"] == ["G06-R-COUNT-01"]
    assert all(gt[located[n]["fingerprint"]]["human_primary_skill_id"] is None for n in (7, 8))


def test_cleaning_exclusion_v5_bom_and_dedup():
    status = batch.ingest()
    items = json.loads(batch.CLEANING.read_text(encoding="utf-8-sig"))["items"]
    assert len(items) == status["source_quality"]["source_cleaning_queue_total"]
    assert len({item["fingerprint"] for item in items}) == len(items)
    assert batch.TEACHER_V5.read_bytes().startswith(b"\xef\xbb\xbf")
    with batch.TEACHER_V5.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == status["teacher_review"]["remaining_questions"]
    assert len({row[list(row)[3]] for row in rows}) == len(rows)


def test_no_rule_match_becomes_human_validation_or_external_call():
    status = batch.ingest()
    assert status["api_calls"] == status["production_reads"] == status["production_writes"] == 0
    assert status["private_jh_extension"]["divisibility_by_3_rule"] == "CANDIDATE_GUIDANCE_READY"
