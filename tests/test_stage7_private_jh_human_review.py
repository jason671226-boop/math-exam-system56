import csv
import json

from scripts import stage7_private_jh_human_review as review


def test_teacher_review_preparation_is_private_unique_and_offline():
    before={path.name:review.file_hash(path) for path in (review.DEEPSEEK,review.GEMINI,review.QUEUE)}
    status=review.prepare()
    after={path.name:review.file_hash(path) for path in (review.DEEPSEEK,review.GEMINI,review.QUEUE)}
    assert before==after and status["source_files_unchanged"]
    assert status["total_unique_review"]==status["remaining"]==79
    assert status["human_validated"]==status["duplicate_fingerprints"]==0
    assert status["api_calls"]==status["production_reads"]==status["production_writes"]==0
    assert review.PILOT in review.TEACHER.parents and review.PILOT in review.SIMPLE.parents


def test_teacher_csv_bom_names_parent_validation_and_unique_fingerprints():
    review.prepare()
    assert review.TEACHER.read_bytes().startswith(b"\xef\xbb\xbf")
    with review.TEACHER.open(encoding="utf-8-sig",newline="") as handle:
        rows=list(csv.DictReader(handle))
    with review.QUEUE.open(encoding="utf-8-sig",newline="") as handle:
        queue=list(csv.DictReader(handle))
    assert len(rows)==len(queue)==79
    assert all(row["DeepSeek Skill 中文名稱"] not in ("", "INVALID_ID") for row in rows if row["DeepSeek Skill ID"])
    assert all(row["DeepSeek Micro 中文名稱"] not in ("", "INVALID_ID") for row in rows if row["DeepSeek Micro ID"])
    assert all("MICRO_PARENT_MISMATCH" not in row["Validation Error"] for row in rows)
    assert all(row["structural_group_id"].startswith("SG-") and int(row["group_size"])>=1 for row in rows)


def test_simple_csv_is_utf8_bom_and_status_is_unvalidated():
    status=review.prepare()
    assert review.SIMPLE.read_bytes().startswith(b"\xef\xbb\xbf")
    stored=json.loads(review.STATUS.read_text(encoding="utf-8"))
    assert stored==status and stored["human_validated"]==0
