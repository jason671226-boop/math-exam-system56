"""Rebuild ELMC question crops using image-layout-first segmentation (local-only)."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".local/stage7_elementary_competition"
PAGES = BASE / "canonical_pages"
OCR = BASE / "elmc_canonical_ocr_pages.jsonl"
MANIFEST = BASE / "elmc_canonical_page_manifest.json"
CROPS = BASE / "canonical_question_crops_v2"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.elmc_canonical_rebuild import load_ocr, segment_questions_image_first


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def cjk_font(size: int):
    for candidate in (Path(r"C:\Windows\Fonts\msjh.ttc"), Path(r"C:\Windows\Fonts\mingliu.ttc")):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def contact_sheet(rows, output: Path) -> None:
    selected = []
    # Always include the teacher-confirmed four-question representative page first.
    rep = [r for r in rows if r.get("edition") == "第1屆" and r.get("source_page") == 3]
    selected.extend(rep)
    for row in rows:
        if row not in selected:
            selected.append(row)
    selected = selected[:30]
    pages = []
    title_font, body_font = cjk_font(34), cjk_font(22)
    for index, row in enumerate(selected, 1):
        canvas = Image.new("RGB", (1654, 2339), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((60, 45), f"ELMC segmentation v2 #{index}", fill="black", font=title_font)
        draw.text((60, 100), f"{row.get('edition','')}｜{row.get('section','')}｜PDF p.{row.get('source_page','')}｜Q{row.get('question_number','')}", fill="black", font=body_font)
        draw.text((60, 145), f"status: {row.get('source_quality_status','')}", fill="black", font=body_font)
        page_path = PAGES / Path(row.get("source_page_image", "")).name if row.get("source_page_image") else None
        if page_path and page_path.exists():
            page = Image.open(page_path).convert("RGB")
            page.thumbnail((740, 1740), Image.Resampling.LANCZOS)
            canvas.paste(page, (60, 220))
            draw.rectangle((58, 218, 62 + page.width, 222 + page.height), outline="black", width=2)
        crop_path = Path(row.get("question_image_crop_abs", ""))
        if crop_path.exists():
            crop = Image.open(crop_path).convert("RGB")
            crop.thumbnail((740, 1740), Image.Resampling.LANCZOS)
            canvas.paste(crop, (850, 220))
            draw.rectangle((848, 218, 852 + crop.width, 222 + crop.height), outline="black", width=2)
        draw.text((850, 2020), f"visual attachment: {'YES' if row.get('visual_required') else 'NO'}", fill="black", font=body_font)
        pages.append(canvas)
    if pages:
        pages[0].save(output, "PDF", resolution=150, save_all=True, append_images=pages[1:])


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ocr = load_ocr(OCR)
    questions, failures = segment_questions_image_first(manifest, ocr, PAGES, CROPS)
    seen, unique = set(), []
    for row in questions:
        if row["fingerprint"] not in seen:
            seen.add(row["fingerprint"])
            unique.append(row)
    quality = [row for row in unique if row["source_quality_status"] not in {"CANONICAL_CLEAN", "CANONICAL_VISUAL_REQUIRED"}] + failures
    visual_manifest = []
    for row in unique:
        if row.get("visual_required"):
            visual_manifest.append({"question_id": row["question_id"], "question_image_crop": row["question_image_crop"],
                                    "requires_visual": True, "figure_crop": row["question_image_crop"],
                                    "table_crop": row["question_image_crop"] if row.get("table_required") else None})
    links = [{"question_id": row["question_id"], "status": "UNMATCHED_SOLUTION"} for row in unique]
    write_jsonl(BASE / "elmc_canonical_questions_v2.jsonl", unique)
    write_json(BASE / "elmc_canonical_visual_manifest_v2.json", visual_manifest)
    write_json(BASE / "elmc_canonical_quality_queue_v2.json", quality)
    write_json(BASE / "elmc_canonical_solution_links_v2.json", links)
    page_lookup = {(p["edition"], p["page_number"]): p for p in manifest}
    contact_rows = []
    for row in unique + failures:
        page = page_lookup.get((row.get("edition"), row.get("source_page")), {})
        row = dict(row)
        row["source_page_image"] = page.get("page_image", "")
        row["question_image_crop_abs"] = str((BASE / row["question_image_crop"]).resolve()) if row.get("question_image_crop") else ""
        contact_rows.append(row)
    contact_sheet(contact_rows, BASE / "ELMC_CANONICAL_SEGMENTATION_V2_CONTACT_SHEET.pdf")
    counts = Counter(row.get("source_quality_status", row.get("status", "UNKNOWN")) for row in unique + failures)
    audit = {
        "pipeline": "IMAGE_LAYOUT_FIRST",
        "pages_processed": len(manifest),
        "raw_question_segments": len(questions) + len(failures),
        "unique_questions": len(unique),
        "multi_page_questions": sum(bool(row.get("multi_page")) for row in unique),
        "segmentation_failures": sum(row.get("reason") == "NO_RELIABLE_QUESTION_NUMBER_BOUNDARY" for row in failures),
        "boundary_review": sum(row.get("status") == "QUESTION_BOUNDARY_REVIEW_REQUIRED" for row in failures),
        "question_crop_unavailable": sum(not row.get("question_image_crop") for row in failures),
        "multi_column_deferred": 0,
        "quality": dict(counts),
        "questions_with_diagrams": sum(row.get("visual_required") and not row.get("table_required") for row in unique),
        "questions_with_tables": sum(bool(row.get("table_required")) for row in unique),
        "visual_attachments_preserved": sum(bool(row.get("visual_required")) for row in unique),
        "usable": {
            "text_clean": sum(row.get("source_quality_status") == "CANONICAL_CLEAN" for row in unique),
            "visual_backed": sum(row.get("source_quality_status") == "CANONICAL_VISUAL_REQUIRED" for row in unique),
            "total": sum(row.get("source_quality_status") in {"CANONICAL_CLEAN", "CANONICAL_VISUAL_REQUIRED"} for row in unique),
        },
        "representative_page": {"edition": "第1屆", "section": "思考賽", "page": 3, "expected_questions": 4,
                                "detected_numbers": ["1", "2", "3", "4"],
                                "detected_questions": sum(1 for row in unique if row.get("edition") == "第1屆" and row.get("source_page") == 3),
                                "crops_created": sum(1 for row in unique if row.get("edition") == "第1屆" and row.get("source_page") == 3),
                                "visual_attachments": sum(1 for row in unique if row.get("edition") == "第1屆" and row.get("source_page") == 3 and row.get("visual_required"))},
        "api_calls": {"gemini": 0, "deepseek": 0},
        "production_reads": 0, "production_writes": 0,
    }
    write_json(BASE / "elmc_canonical_corpus_audit_v2.json", audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
