import csv
from pathlib import Path
import unittest

from scripts.build_g8_import_package import OUTPUT, QUESTION_FIELDS, build


def read_rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class G8ImportPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = build()

    def test_coverage_contains_all_master_micros_and_exactly_100_processed(self):
        rows = read_rows("g8_coverage_matrix.csv")
        self.assertEqual(len(rows), 660)
        self.assertEqual(len({row["micro_skill_id"] for row in rows}), 660)
        self.assertEqual(sum(row["processed"] == "true" for row in rows), 100)
        self.assertTrue(all(
            row["staging_count_status"] == "UNAVAILABLE_NO_STAGING_READ"
            for row in rows
        ))

    def test_import_ready_schema_and_quality_gate(self):
        rows = read_rows("g8_import_ready.csv")
        self.assertEqual(tuple(rows[0]), QUESTION_FIELDS)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({row["question_key"] for row in rows}), 5)
        self.assertEqual(len({row["content_hash"] for row in rows}), 5)
        for row in rows:
            self.assertEqual(row["grade"], "8")
            self.assertEqual(row["rights_status"], "CLEARED_OPEN_LICENSE")
            self.assertEqual(row["quality_status"], "VALIDATED")
            self.assertEqual(row["is_active"], "true")
            for field in QUESTION_FIELDS:
                self.assertTrue(row[field], f"empty import-ready field: {field}")

    def test_noncommercial_source_is_review_only(self):
        ready = read_rows("g8_import_ready.csv")
        review = read_rows("g8_needs_review.csv")
        self.assertEqual(len(review), 6)
        self.assertFalse(any("SIYAVULA" in row["source_key"] for row in ready))
        self.assertTrue(all(
            row["rights_status"] == "NEEDS_RIGHTS_REVIEW_NONCOMMERCIAL"
            and row["quality_status"] == "NEEDS_REVIEW"
            and row["is_active"] == "false"
            for row in review
        ))

    def test_candidates_and_source_manifest_reconcile(self):
        candidates = read_rows("g8_question_candidates.csv")
        sources = read_rows("g8_source_manifest.csv")
        self.assertEqual(len(candidates), 11)
        self.assertEqual(len(sources), 2)
        source_keys = {row["source_key"] for row in sources}
        self.assertEqual({row["source_key"] for row in candidates}, source_keys)


if __name__ == "__main__":
    unittest.main()
