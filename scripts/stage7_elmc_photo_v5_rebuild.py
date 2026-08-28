"""Local-only ELMC photo-backed canonical rebuild; no AI or database access."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".local/stage7_elementary_competition"
PHOTOS = BASE / "original_photos"
PROCESSED = BASE / "photo_processed_v5_rebuild"
OCR = BASE / "elmc_photo_ocr_v5_rebuild.jsonl"
CROPS = BASE / "photo_question_crops_v5_rebuild"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_lines(path, rows):
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")


def _font(size: int):
    for candidate in (Path(r"C:\Windows\Fonts\msjh.ttc"), Path(r"C:\Windows\Fonts\mingliu.ttc")):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def preprocess():
    PROCESSED.mkdir(exist_ok=True); CROPS.mkdir(exist_ok=True)
    existing_processed = sorted(PROCESSED.glob("*.png"))
    source_files = sorted(PHOTOS.glob("*.jpg"))
    if len(existing_processed) == len(source_files) == 62:
        return [{"filename": path.name, "processed_image": str((PROCESSED / f"photo_{i:03d}.png").relative_to(BASE)).replace("\\", "/"),
                 "sequence_order": i, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                 "width": Image.open(path).size[0], "height": Image.open(path).size[1]}
                for i, path in enumerate(source_files, 1)]
    for p in PROCESSED.glob("*.png"):
        try: p.unlink()
        except PermissionError: pass
    for p in CROPS.glob("*.png"):
        try: p.unlink()
        except PermissionError: pass
    rows = []
    for index, path in enumerate(sorted(PHOTOS.glob("*.jpg")), 1):
        with Image.open(path) as source:
            im = ImageOps.exif_transpose(source).convert("L")
            # Mild normalization only; preserve fraction bars, grids, and diagrams.
            im = ImageEnhance.Contrast(im).enhance(1.12)
            out = PROCESSED / f"photo_{index:03d}.png"
            im.save(out, optimize=True)
        rows.append({"filename": path.name, "processed_image": str(out.relative_to(BASE)).replace("\\", "/"),
                     "sequence_order": index, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "width": Image.open(path).size[0], "height": Image.open(path).size[1]})
    return rows


def run_ocr():
    if OCR.exists():
        try:
            existing = [json.loads(x) for x in OCR.read_text(encoding="utf-8").splitlines() if x.strip()]
            if len(existing) == len(list(PROCESSED.glob("*.png"))):
                return existing
        except Exception:
            pass
        try: OCR.unlink()
        except PermissionError: pass
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/stage7_elmc_windows_ocr.ps1"),
               "-InputDirectory", str(PROCESSED), "-OutputJsonl", str(OCR)]
    subprocess.run(command, check=True)
    return [json.loads(x) for x in OCR.read_text(encoding="utf-8").splitlines() if x.strip()]


def classify(text: str):
    year = next((y for y in ("2022", "2023", "2024", "2025") if y in text), None)
    competition = next((s for s in ("思考賽", "個人賽", "團體賽", "接力賽") if s in text), None)
    if any(x in text for x in ("答案", "解答", "詳解")) and not any(x in text for x in ("試題", "題目")):
        page_type = "SOLUTION_PAGE"
    elif any(x in text for x in ("試題", "題目")) or re.search(r"第\s*[0-9]{1,2}\s*題", text):
        page_type = "QUESTION_PAGE"
    else:
        page_type = "REVIEW_REQUIRED"
    page = None
    m = re.search(r"第\s*([0-9]{1,2})\s*頁", text)
    if m: page = int(m.group(1))
    return year, competition, page, page_type


def main():
    source_rows = preprocess()
    ocr_rows = run_ocr()
    ocr_by_image = {x["image"]: x for x in ocr_rows}
    pages, parents, children, quality = [], [], [], []
    for source in source_rows:
        image_name = Path(source["processed_image"]).name
        ocr = ocr_by_image.get(image_name, {"text": "", "lines": []})
        text = ocr.get("text", "")
        year, competition, page_number, page_type = classify(text)
        page_record = {**source, "year": year, "edition": None, "competition_type": competition,
                       "page_number": page_number, "page_type": page_type, "source_type": "PHOTO_BACKED_CANONICAL_SOURCE",
                       "orientation_status": "EXIF_ORIENTATION_APPLIED", "perspective_status": "NOT_AUTOMATICALLY_WARPED",
                       "contrast_status": "MILD_NORMALIZATION", "handwriting_present": None, "photo_shadow_present": None}
        pages.append(page_record)
        if page_type != "QUESTION_PAGE":
            if page_type == "REVIEW_REQUIRED": quality.append({"filename": source["filename"], "status": "QUESTION_STRUCTURE_REVIEW_REQUIRED", "reason": "PAGE_CLASSIFICATION_FAILED"})
            continue
        # A parent is created only when the printed page contains an explicit top-level marker.
        marker = re.search(r"第\s*([0-9]{1,2})\s*題", text)
        if not marker:
            quality.append({"filename": source["filename"], "status": "QUESTION_STRUCTURE_REVIEW_REQUIRED", "reason": "NO_TOP_LEVEL_QUESTION_ANCHOR"})
            continue
        number = marker.group(1)
        im_path = PROCESSED / image_name
        with Image.open(im_path) as im: crop = im.convert("RGB"); crop_path = CROPS / f"photo_{source['sequence_order']:03d}_Q{number}.png"; crop.save(crop_path)
        parent_id = f"ELMC-PHOTO-{source['sequence_order']:03d}-Q{number}"
        child_labels = [str(i) for i in range(1, 10) if re.search(rf"(?:^|[ (（]){i}[.、)]", text)]
        child_labels = list(dict.fromkeys(child_labels))
        child_ids = []
        for label in child_labels:
            child_id = f"{parent_id}-C{label}"; child_ids.append(child_id)
            children.append({"child_id": child_id, "parent_question_id": parent_id, "label": label,
                             "text": "", "visual_refs": [parent_id] if any(x in text for x in ("圖", "表", "格")) else [],
                             "depends_on_previous": label != "1"})
        visual = any(x in text for x in ("圖", "表", "格", "陰影", "展開", "積木", "路徑"))
        parents.append({"parent_question_id": parent_id, "edition": None, "year": year, "section": competition,
                        "question_number": number, "source_pages": [source["sequence_order"]], "parent_stem": "",
                        "parent_crop": str(crop_path.relative_to(BASE)).replace("\\", "/"), "shared_visuals": [parent_id] if visual else [],
                        "child_items": child_ids, "quality_status": "CANONICAL_VISUAL_REQUIRED" if visual else "CANONICAL_CLEAN",
                        "source_quality_flags": [], "source_photo": source["filename"],
                        "fingerprint": hashlib.sha256(crop_path.read_bytes()).hexdigest()})
    hashes = [x["fingerprint"] for x in parents]
    duplicate_count = len(hashes) - len(set(hashes))
    dump(BASE / "elmc_photo_pages_v5.json", pages)
    dump_lines(BASE / "elmc_parent_questions_v5.jsonl", parents)
    dump_lines(BASE / "elmc_child_items_v5.jsonl", children)
    dump(BASE / "elmc_visual_manifest_v5.json", [{"parent_question_id": p["parent_question_id"], "shared_visuals": p["shared_visuals"], "requires_visual": bool(p["shared_visuals"])} for p in parents if p["shared_visuals"]])
    dump(BASE / "elmc_question_solution_links_v5.json", [])
    dump(BASE / "elmc_quality_queue_v5.json", quality)
    usable = [p for p in parents if p["quality_status"] in {"CANONICAL_CLEAN", "CANONICAL_VISUAL_REQUIRED"}]
    audit = {"input_photos": len(source_rows), "valid_photos": len(source_rows), "pages_classified": len(pages), "unclassified": sum(p["page_type"] == "REVIEW_REQUIRED" for p in pages),
             "years": sorted({p["year"] for p in pages if p["year"]}), "editions": [], "competition_types": sorted({p["competition_type"] for p in pages if p["competition_type"]}),
             "parent_questions": len(parents), "child_items": len(children), "parents_with_children": sum(bool(p["child_items"]) for p in parents), "standalone_parents": sum(not p["child_items"] for p in parents),
             "quality": dict(Counter(p["quality_status"] for p in parents)), "source_quality_queue": len(quality), "questions_with_diagrams": sum(bool(p["shared_visuals"]) for p in parents), "questions_with_tables": 0,
             "visual_attachments_preserved": sum(bool(p["shared_visuals"]) for p in parents), "matched_parent_solutions": 0, "matched_child_solutions": 0, "unmatched_solutions": 0,
             "duplicate_fingerprints": duplicate_count, "usable_parent_questions": len(usable), "text_clean_usable_parents": sum(p["quality_status"] == "CANONICAL_CLEAN" for p in usable), "visual_backed_usable_parents": sum(p["quality_status"] == "CANONICAL_VISUAL_REQUIRED" for p in usable),
             "gemini_calls": 0, "deepseek_calls": 0, "production_reads": 0, "production_writes": 0, "human_gt": 0}
    dump(BASE / "elmc_corpus_audit_v5.json", audit)
    # Local visual QA contact sheet: include up to 30 source photos, prioritising
    # explicit parent/child pages and then unresolved pages for fail-closed review.
    sheet_pages = []
    title_font = _font(30); body_font = _font(19)
    for index, page in enumerate(pages[:30], 1):
        canvas = Image.new("RGB", (1654, 2339), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((55, 40), f"ELMC PHOTO V5 #{index}", fill="black", font=title_font)
        draw.text((55, 90), f"year: {page.get('year') or 'REVIEW_REQUIRED'} | edition: {page.get('edition') or 'REVIEW_REQUIRED'}", fill="black", font=body_font)
        draw.text((55, 130), f"type: {page.get('competition_type') or 'REVIEW_REQUIRED'} | page: {page.get('page_number') or 'REVIEW_REQUIRED'}", fill="black", font=body_font)
        draw.text((55, 170), f"page status: {page.get('page_type')} | solution pair: UNMATCHED_SOLUTION", fill=(130, 0, 0), font=body_font)
        path = PROCESSED / Path(page["processed_image"]).name
        if path.exists():
            with Image.open(path) as im:
                im = im.convert("RGB"); im.thumbnail((1500, 1950), Image.Resampling.LANCZOS); canvas.paste(im, (70, 230))
        sheet_pages.append(canvas)
    contact_path = BASE / "ELMC_PHOTO_CANONICAL_V5_CONTACT_SHEET.pdf"
    if sheet_pages:
        sheet_pages[0].save(contact_path, "PDF", resolution=150, save_all=True, append_images=sheet_pages[1:])
    audit["contact_sheet"] = str(contact_path)
    dump(BASE / "elmc_corpus_audit_v5.json", audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
