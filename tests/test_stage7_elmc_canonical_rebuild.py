from services.elmc_canonical_rebuild import page_role

def test_page_role_and_sections():
    assert page_role("個人賽 試題｜第1頁",None)==("個人賽","QUESTION_PAGE")
    assert page_role("團體賽 詳解｜第1頁",None)==("團體賽","SOLUTION_PAGE")

def test_cover_not_question():
    assert page_role("思考賽 試題",None)==("思考賽","SECTION_COVER")
    assert page_role("思考賽 詳解",None)==("思考賽","SECTION_COVER")

def test_no_fake_human_validation_contract():
    allowed={"CANONICAL_CLEAN","CANONICAL_VISUAL_REQUIRED","MATH_NOTATION_REVIEW_REQUIRED","SOURCE_REEXTRACTION_REQUIRED","QUESTION_BOUNDARY_REVIEW_REQUIRED"}
    assert "HUMAN_VALIDATED" not in allowed
