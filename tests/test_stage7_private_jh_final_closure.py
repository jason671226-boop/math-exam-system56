import csv
import json

from scripts import stage7_private_jh_final_closure as closure


def test_final_locator_binds_all_twelve_by_number_fingerprint_and_text():
    located = closure._locate()
    assert set(located) == set(range(1, 13))
    assert len({item["fingerprint"] for item in located.values()}) == 12
    for item in located.values():
        fields = list(item["coverage"])
        assert item["coverage"][fields[3]] == item["question"]["question_text"]


def test_final_batch_has_seven_teacher_gt_and_five_cleaning_cases():
    status = closure.close(force=True)
    assert status["final_teacher_batch"] == {"reviewed": 12, "human_validated": 7,
        "source_cleaning": 5, "id_validation_failures": 0, "parent_failures": 0}
    gt = {row["fingerprint"]: row for row in closure._jsonl(closure.GT)}
    cleaning = {row["fingerprint"]: row for row in json.loads(
        closure.CLEANING.read_text(encoding="utf-8-sig"))["items"]}
    located = closure._locate()
    for number in closure.VALIDATED_NUMBERS:
        record = gt[located[number]["fingerprint"]]
        assert record["source_status"] == "HUMAN_VALIDATED"
        assert record["validation_source"] == "TEACHER_APPROVED"
        assert record["question_reference"]["question_number"] is not None
    for number in closure.SOURCE_NUMBERS:
        assert located[number]["fingerprint"] in cleaning


def test_catalog_ids_parents_and_pattern_style_are_valid():
    _, micros = closure._validate_ids()
    for number in closure.VALIDATED_NUMBERS:
        spec = closure.BATCH[number]
        assert micros[spec["micro"]]["parent_skill_id"] == spec["skill"]
    assert closure.BATCH[1]["assessment"] == "PATTERN_REASONING"


def test_v7_is_header_only_bom_and_final_audits_reproduce_partition():
    status = closure.close()
    assert closure.TEACHER_V7.read_bytes().startswith(b"\xef\xbb\xbf")
    with closure.TEACHER_V7.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == []
    audit = status["audit"]
    assert audit["total_pilot_questions"] == 100
    assert sum(audit[key] for key in ("direct_human_gt", "structurally_accepted",
        "deferred_audit", "source_invalid")) == 100
    assert audit == json.loads(closure.FINAL_AUDIT_JSON.read_text(encoding="utf-8-sig"))
    with closure.FINAL_AUDIT_CSV.open(encoding="utf-8-sig", newline="") as handle:
        csv_metrics = {row["metric"]: row["value"] for row in csv.DictReader(handle)}
    assert int(csv_metrics["remaining_human_review"]) == 0


def test_completion_gate_has_no_invalid_duplicate_unresolved_or_fake_gt():
    audit = closure.close()["audit"]
    assert audit["remaining_human_review"] == 0
    assert all(audit[key] == 0 for key in ("invalid_skill_ids", "invalid_micro_ids",
        "micro_parent_mismatches", "duplicate_fingerprints", "unresolved_fingerprints",
        "fake_human_validation"))
    assert audit["pilot_status"] == "PRIVATE_JH HUMAN-VALIDATED PILOT PASS"
    assert audit["api_calls"] == audit["production_reads"] == audit["production_writes"] == 0


def test_source_quality_records_are_excluded_from_direct_gt():
    audit = closure.close()["audit"]
    assert audit["missing_diagram"] > 0 and audit["missing_chart"] > 0
    assert audit["fraction_notation_loss"] > 0
    assert audit["multi_document_contamination"] > 0
    assert audit["expression_incomplete"] > 0
