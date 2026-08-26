from services.math_extraction_quality import assess_fraction_structure_loss,assess_math_extraction,assess_missing_required_image


def test_math_notation_gate_detects_broken_fraction_radical_exponent_and_geometry():
    assert "BROKEN_FRACTION" in assess_math_extraction("計算 3 / ").risks
    assert "MISSING_RADICAL" in assess_math_extraction("求 √ 的值").risks
    assert "BROKEN_EXPONENT" in assess_math_extraction("計算 2^ + 3").risks
    assert "BROKEN_GEOMETRY_SYMBOL" in assess_math_extraction("已知 ∠，求角度").risks


def test_expected_notation_loss_and_difficulty_independence():
    assert "MISSING_FRACTION_NOTATION" in assess_math_extraction("求兩個數的差",expected_notation=("fraction",)).risks
    assert assess_math_extraction("這是一道非常困難但符號完整的多步驟題").status=="PASS"


def test_fraction_loss_requires_multiple_signals_and_does_not_flag_large_integer_arithmetic():
    broken="計算 12+14+16+18+112？ (A) 2524 (B) 2924 (C) 98 (D) 118"
    meta={"official_pdf":True,"question_number":2,"fraction_expected":True}
    assert assess_fraction_structure_loss(broken,source_metadata=meta).status=="SOURCE_NEEDS_REEXTRACTION"
    intact="計算 299998+29998+2998+298+28？ (A) 333320 (B) 333310 (C) 333210 (D) 333120"
    assert assess_fraction_structure_loss(intact,source_metadata={"official_pdf":True,"question_number":9,"fraction_expected":False}).status=="PASS"


def test_missing_image_gate_and_false_positive_reference():
    assert assess_missing_required_image("如下圖所示，求角度。",extracted_record={}).status=="SOURCE_IMAGE_REQUIRED"
    assert assess_missing_required_image("如下圖所示，求角度。",extracted_record={"page_crop":"crop.png"}).status=="PASS"
    assert assess_missing_required_image("請到右圖書館借書。",extracted_record={}).status=="PASS"
