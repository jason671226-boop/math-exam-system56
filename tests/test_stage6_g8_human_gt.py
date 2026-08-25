import csv

import scripts.stage6_g8_human_gt as gt


def test_structural_gate_accepts_only_exact_skeleton_and_difference_two():
    skeleton, _ = gt._signature("Compute 100 times 102 exactly")
    assert gt.exact_difference_of_squares_match("Compute 200 times 202 exactly", skeleton)
    assert not gt.exact_difference_of_squares_match("Compute 200 times 203 exactly", skeleton)
    assert not gt.exact_difference_of_squares_match("Add 200 and 202 exactly", skeleton)
    assert not gt.exact_difference_of_squares_match("Compute 200 times 202 approximately", skeleton)


def test_human_gt_and_v2_are_private_and_statuses_are_distinct():
    result = gt.run()
    rows = gt._jsonl(gt.PRIVATE / "human_ground_truth.jsonl")
    assert len(rows) == 5
    assert all(row["validated_by"] == "HUMAN" and row["validation_status"] == "VALIDATED" for row in rows)
    with (gt.PRIVATE / "G8_HUMAN_REVIEW_SIMPLE_V2.csv").open(encoding="utf-8-sig", newline="") as handle:
        v2 = list(csv.DictReader(handle))
    assert len(v2) == 56
    assert {row["review_status"] for row in v2} <= {"HUMAN_VALIDATED", "STRUCTURALLY_INFERRED", "REQUIRES_HUMAN_REVIEW"}
    assert result["audit"]["exact_structural_matches"] == 145
    assert result["audit"]["unsafe_matches_rejected"] == 55
