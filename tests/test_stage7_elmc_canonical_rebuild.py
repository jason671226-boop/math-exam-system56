import json
import tempfile
from pathlib import Path

from services.elmc_canonical_rebuild import page_role, load_ocr, segment_questions_image_first

def test_page_role_and_sections():
    assert page_role("個人賽 試題｜第1頁",None)==("個人賽","QUESTION_PAGE")
    assert page_role("團體賽 詳解｜第1頁",None)==("團體賽","SOLUTION_PAGE")

def test_cover_not_question():
    assert page_role("思考賽 試題",None)==("思考賽","SECTION_COVER")
    assert page_role("思考賽 詳解",None)==("思考賽","SECTION_COVER")

def test_no_fake_human_validation_contract():
    allowed={"CANONICAL_CLEAN","CANONICAL_VISUAL_REQUIRED","MATH_NOTATION_REVIEW_REQUIRED","SOURCE_REEXTRACTION_REQUIRED","QUESTION_BOUNDARY_REVIEW_REQUIRED"}
    assert "HUMAN_VALIDATED" not in allowed


def test_image_layout_first_representative_page_has_four_crops():
    root = Path(__file__).resolve().parents[1] / ".local" / "stage7_elementary_competition"
    manifest_path = root / "elmc_canonical_page_manifest.json"
    ocr_path = root / "elmc_canonical_ocr_pages.jsonl"
    pages = root / "canonical_pages"
    if not manifest_path.exists() or not ocr_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out = Path(tempfile.mkdtemp(prefix="_test_image_first_crops_", dir=root))
    questions, failures = segment_questions_image_first(manifest, load_ocr(ocr_path), pages, out)
    representative = [q for q in questions if q.get("edition") == "第1屆" and q.get("source_page") == 3]
    assert [q["question_number"] for q in representative] == ["1", "2", "3", "4"]
    assert all((root / q["question_image_crop"]).exists() for q in representative)
    assert not any(q.get("edition") == "第1屆" and q.get("source_page") == 3 for q in failures)
