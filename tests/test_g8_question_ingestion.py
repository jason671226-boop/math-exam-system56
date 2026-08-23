from pathlib import Path
import unittest

from scripts.g8_question_bank_audit import build_report
from scripts.g8_question_batch_validator import validate_batch


class G8QuestionIngestionTests(unittest.TestCase):
    BATCH = Path("data/question_ingestion/g8/our_g8_linear_model_batch_001.json")

    def test_open_batch_matches_master_and_validates_answers(self):
        payload, errors = validate_batch(self.BATCH)

        self.assertEqual(errors, [])
        self.assertEqual(len(payload["questions"]), 5)
        self.assertEqual(payload["source"]["license"], "CC BY 4.0")
        self.assertTrue(all(row["validated"] for row in payload["questions"]))
        self.assertEqual(
            {row["micro_skill_id"] for row in payload["questions"]},
            {"G08-F-MODEL-01-A1"},
        )
        self.assertEqual(
            len({row["content_hash"] for row in payload["questions"]}), 5
        )
        self.assertEqual(
            len({row["archetype_key"] for row in payload["questions"]}), 5
        )

    def test_empty_staging_bank_reports_every_master_micro_as_zero(self):
        report = build_report([])

        self.assertEqual(report["total_standard_skills"], 102)
        self.assertEqual(report["total_micro_skills"], 660)
        self.assertEqual(
            report["coverage_status_counts"],
            {"ZERO": 660, "LOW": 0, "READY": 0, "STRONG": 0},
        )
        self.assertEqual(len(report["largest_20_gaps"]), 20)


if __name__ == "__main__":
    unittest.main()
