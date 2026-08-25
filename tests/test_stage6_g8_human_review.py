import csv
from pathlib import Path

import scripts.stage6_g8_human_review as review


def test_priority_order_uses_highest_reason():
    assert review._priority({"INVALID", "PROVIDER_DISAGREEMENT"}) == "P0"
    assert review._priority({"OUT_OF_SCOPE", "AGREEMENT_AUDIT_SAMPLE"}) == "P2"


def test_invalid_id_name_is_explicit():
    assert review._id_name("missing", {}) == ("missing", "INVALID_ID")
    assert review._id_name(None, {}) == ("", "")


def test_prepared_csvs_are_bom_and_unique():
    status = review.prepare()
    teacher = review.PRIVATE / "G8_HUMAN_REVIEW_FOR_TEACHER.csv"
    simple = review.PRIVATE / "G8_HUMAN_REVIEW_SIMPLE.csv"
    assert teacher.read_bytes().startswith(b"\xef\xbb\xbf")
    assert simple.read_bytes().startswith(b"\xef\xbb\xbf")
    with teacher.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == status["total_review"] == 56
    assert len({row["fingerprint"] for row in rows}) == 56
    assert all(row["human_scope"] == row["human_skill_id"] == row["human_micro_id"] == "" for row in rows)
    assert status["production_reads"] == status["production_writes"] == 0


def test_micro_name_and_parent_lookup_are_catalog_backed():
    micros = review._json(review.PRIVATE / "g8_curriculum_micro_skills.json")
    skills = {row["skill_id"]: row for row in review._json(review.PRIVATE / "g8_curriculum_skills.json")}
    row = micros[0]
    assert row["parent_skill_id"] in skills
    assert review._id_name(row["micro_skill_id"], {row["micro_skill_id"]: row}, micro=True)[1] != "INVALID_ID"
