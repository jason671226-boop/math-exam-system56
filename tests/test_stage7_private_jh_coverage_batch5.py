import csv
import json

from scripts import stage7_private_jh_coverage_batch5 as batch


def test_locator_is_number_fingerprint_and_question_text_bound():
    located = batch._locate()
    assert set(located) == set(range(1, 7))
    assert len({entry["fingerprint"] for entry in located.values()}) == 6
    for entry in located.values():
        fields = list(entry["coverage"])
        assert entry["coverage"][fields[3]] == entry["question"]["question_text"]


def test_ingest_four_gt_two_diagram_cases_with_valid_parents():
    status = batch.ingest(force=True)
    assert status["teacher_batch"] == {"reviewed": 6, "human_validated": 4,
        "image_reextraction": 2, "id_validation_failures": 0, "parent_failures": 0}
    gt = {row["fingerprint"]: row for row in batch._jsonl(batch.GT)}
    located = batch._locate()
    expected = {1: ("G05-R-LAW-01", "G05-R-LAW-01-T1"),
        2: ("G05-R-MULTISTEP-01", "G05-R-MULTISTEP-01-A1"),
        3: ("G06-R-COUNT-01", "G06-R-COUNT-01-P1"),
        6: ("G06-N-SPEED-APP-01", "G06-N-SPEED-APP-01-T1")}
    for number, pair in expected.items():
        record = gt[located[number]["fingerprint"]]
        assert (record["human_primary_skill_id"], record["human_primary_micro_id"]) == pair
    assert all(gt[located[n]["fingerprint"]]["human_primary_skill_id"] is None for n in (4, 5))


def test_source_cleaning_v6_bom_review_dedup_and_exclusion():
    status = batch.ingest()
    items = json.loads(batch.CLEANING.read_text(encoding="utf-8-sig"))["items"]
    assert len(items) == status["source_quality"]["source_cleaning_queue_total"]
    assert len({item["fingerprint"] for item in items}) == len(items)
    assert batch.TEACHER_V6.read_bytes().startswith(b"\xef\xbb\xbf")
    with batch.TEACHER_V6.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == status["teacher_review"]["remaining_questions"]
    assert len({row[list(row)[3]] for row in rows}) == len(rows)


def test_no_fake_human_validation_or_external_calls():
    status = batch.ingest()
    assert status["api_calls"] == status["production_reads"] == status["production_writes"] == 0
    assert all(value == "READY" for value in status["disambiguation"].values())
