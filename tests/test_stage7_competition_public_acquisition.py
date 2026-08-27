from __future__ import annotations

import pytest

from services.competition_public_corpus import (eligible, extraction_risks, infer_topic,
    normalized_fingerprint, official_source, select_pilot)


def record(index: int, **updates):
    row = {"fingerprint": f"fp-{index}", "official_source": True,
        "source_page": "https://imcct.net/cms2-47-lang1.html", "grade": "G5",
        "extraction_status": "COMPLETE", "page_crop": f"q{index}.png", "ocr_confidence": .95,
        "question_text": f"complete official competition question number {index}", "quality_risks": [],
        "competition_topic": ["COUNTING", "GEOMETRY", "WORD_PROBLEM", "DIVISIBILITY"][index % 4],
        "source_file": f"paper-{index % 6}.pdf", "year": 2024 + index % 2}
    row.update(updates)
    return row


def test_official_source_validation_and_paywall_fail_closed():
    assert official_source("https://imcct.net/example.pdf")
    assert official_source("https://mathkangaroo.org/mks/practice/pdf-exams/")
    assert not official_source("https://example.com/imc.pdf")
    assert not official_source("http://imcct.net/example.pdf")


def test_grade_and_download_quality_fail_closed():
    assert eligible(record(1))
    assert not eligible(record(1, grade="G7"))
    assert not eligible(record(1, extraction_status="DOWNLOAD_FAILED"))
    assert not eligible(record(1, page_crop=None, question_text="如下圖，求面積"))


def test_math_notation_and_image_preservation():
    assert "SPECIAL_SYMBOL_LOST" in extraction_risks(record(1, question_text="value of 3�5 please"))
    assert "MISSING_REQUIRED_DIAGRAM" in extraction_risks(
        record(2, question_text="shown in figure find area", page_crop=None))
    assert not extraction_risks(record(3, question_text="shown in figure find area", page_crop="crop.png"))


def test_fingerprint_normalizes_format_not_numbers():
    assert normalized_fingerprint("第 1 題：3 ＋ 4？") == normalized_fingerprint("第1題:3+4?")
    assert normalized_fingerprint("3+4") != normalized_fingerprint("3+5")


def test_topic_metadata_does_not_create_curriculum_mapping():
    assert infer_topic("how many ways can be arranged") == "COUNTING"
    assert infer_topic("find triangle area") == "GEOMETRY"


def test_pilot100_is_deterministic_diverse_and_no_fake_corpus():
    rows = [record(i) for i in range(120)]
    one = select_pilot(rows, 100); two = select_pilot(list(reversed(rows)), 100)
    assert [r["fingerprint"] for r in one] == [r["fingerprint"] for r in two]
    assert len(one) == len({r["fingerprint"] for r in one}) == 100
    assert max(sum(r["competition_topic"] == topic for r in one) for topic in
               {r["competition_topic"] for r in one}) <= 25
    with pytest.raises(RuntimeError, match="CORPUS_INSUFFICIENT"):
        select_pilot(rows[:99], 100)
