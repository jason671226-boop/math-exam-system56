from services.math_extraction_quality import (
    assess_fraction_structure_loss,
    assess_expression_completeness,
    assess_missing_required_chart,
    assess_multi_document_contamination,
)


META = {"source_document": "official.pdf", "question_number": 12}


def test_multi_document_gate_requires_cross_document_evidence():
    contaminated = "某校112學年度入學測驗試題\n題幹。\n另一校113學年度獎學金測驗試題\n作答說明\n第1頁\n第2頁"
    assert assess_multi_document_contamination(
        contaminated, source_metadata={**META, "multiple_exam_headers": True}
    ).risks == ("MULTI_DOCUMENT_CONTAMINATION",)


def test_long_question_choices_school_context_and_subparts_are_not_contamination():
    valid = "幸福學校辦活動，請閱讀長表格後回答：(1)求總數 (2)求平均 (3)說明理由。 (A)1 (B)2 (C)3 (D)4"
    assert assess_multi_document_contamination(valid, source_metadata=META).status == "PASS"


def test_expression_gate_is_source_evidence_bound():
    broken = "已知若干條件，最後要求計算 ab+?"
    assert assess_expression_completeness(
        broken, source_metadata={**META, "expression_expected": True}, pdf_text_discrepancy=True
    ).risks == ("MATH_EXPRESSION_INCOMPLETE",)
    assert assess_expression_completeness(broken, source_metadata=META).status == "PASS"


def test_chart_gate_requires_visual_and_avoids_plain_table_false_positive():
    text = "根據下列5至9月薪資折線圖，回答超過指定薪資的月份數。"
    assert assess_missing_required_chart(text, extracted_record={}).risks == ("MISSING_REQUIRED_CHART",)
    assert assess_missing_required_chart(text, extracted_record={"page_crop": "q15.png"}).status == "PASS"
    assert assess_missing_required_chart("根據文字表格計算總數。", extracted_record={}).status == "PASS"


def test_contextual_fraction_loss_requires_all_independent_evidence():
    metadata = {**META, "fraction_expected": True, "ratio_context": True,
        "literal_interpretation_implausible": True, "concatenated_fraction_options": True}
    result = assess_fraction_structure_loss("比例文字及數字選項的抽取結果", source_metadata=metadata,
        pdf_text_discrepancy=True)
    assert result.risks == ("MATH_FRACTION_NOTATION_LOST",)


def test_common_two_digit_numbers_alone_are_not_fraction_loss():
    for value in ("13", "21", "35", "51", "53"):
        assert assess_fraction_structure_loss(value, source_metadata=META).status == "PASS"
