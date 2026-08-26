from services.math_extraction_quality import assess_math_extraction


def test_math_notation_gate_detects_broken_fraction_radical_exponent_and_geometry():
    assert "BROKEN_FRACTION" in assess_math_extraction("計算 3 / ").risks
    assert "MISSING_RADICAL" in assess_math_extraction("求 √ 的值").risks
    assert "BROKEN_EXPONENT" in assess_math_extraction("計算 2^ + 3").risks
    assert "BROKEN_GEOMETRY_SYMBOL" in assess_math_extraction("已知 ∠，求角度").risks


def test_expected_notation_loss_and_difficulty_independence():
    assert "MISSING_FRACTION_NOTATION" in assess_math_extraction("求兩個數的差",expected_notation=("fraction",)).risks
    assert assess_math_extraction("這是一道非常困難但符號完整的多步驟題").status=="PASS"
