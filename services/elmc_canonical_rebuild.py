"""Local-only ELMC canonical image-backed corpus reconstruction."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image

EDITIONS = ("第1屆", "第2屆", "第3屆", "第4屆")
SECTIONS = ("個人賽", "團體賽", "思考賽")


def page_role(text: str, prior_section: str | None) -> tuple[str | None, str]:
    section = next((s for s in SECTIONS if s in text), prior_section)
    if "答案與詳解" in text: return section, "OTHER"
    if "詳解｜" in text: return section, "SOLUTION_PAGE"
    if "試題｜" in text: return section, "QUESTION_PAGE"
    if "試題" in text: return section, "SECTION_COVER"
    if "詳解" in text: return section, "SECTION_COVER"
    return section, "OTHER"


def render_sources(pdf_dir: Path, page_dir: Path, ocr_dir: Path) -> list[dict[str, Any]]:
    page_dir.mkdir(parents=True, exist_ok=True); ocr_dir.mkdir(parents=True, exist_ok=True)
    for directory in (page_dir, ocr_dir):
        for old in directory.glob("*.png"): old.unlink()
    manifest: list[dict[str, Any]] = []
    for edition in EDITIONS:
        pdf = pdf_dir / f"{edition}_黑白列印版.pdf"
        if not pdf.is_file(): raise RuntimeError(f"MISSING_CANONICAL:{pdf.name}")
        doc = pymupdf.open(pdf); section = None
        for index, page in enumerate(doc, 1):
            section, role = page_role(page.get_text(), section)
            stem = f"{edition}_p{index:03d}"
            full = page.get_pixmap(matrix=pymupdf.Matrix(300/72,300/72), colorspace=pymupdf.csGRAY, alpha=False)
            full_path = page_dir / f"{stem}.png"; full.save(full_path)
            small = page.get_pixmap(matrix=pymupdf.Matrix(144/72,144/72), colorspace=pymupdf.csGRAY, alpha=False)
            small_path = ocr_dir / f"{stem}.png"; small.save(small_path)
            manifest.append({"edition":edition,"section":section,"page_number":index,
                "page_image":str(full_path.relative_to(page_dir.parent)).replace("\\","/"),"page_type":role,
                "width":full.width,"height":full.height,"dpi":300,"source_pdf":pdf.name})
    return manifest


def load_ocr(path: Path) -> dict[str, dict[str, Any]]:
    return {row["image"]:row for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())}


NUMBER = re.compile(r"^\s*(?:第\s*)?([0-9]{1,2}|[①②③④⑤⑥⑦⑧⑨⑩])\s*(?:題|[.、．)）])")
CIRCLED = {c:str(i) for i,c in enumerate("①②③④⑤⑥⑦⑧⑨⑩",1)}


def line_box(line: dict[str, Any]) -> tuple[float,float,float,float] | None:
    words=line.get("words") or []
    if not words:return None
    x=min(w["x"] for w in words);y=min(w["y"] for w in words)
    right=max(w["x"]+w["width"] for w in words);bottom=max(w["y"]+w["height"] for w in words)
    return x,y,right,bottom


def segment_questions(manifest: list[dict[str,Any]], ocr: dict[str,dict[str,Any]], page_root: Path, crop_root: Path) -> tuple[list[dict],list[dict]]:
    crop_root.mkdir(parents=True,exist_ok=True)
    for old in crop_root.glob("*.png"): old.unlink()
    questions=[]; boundary=[]
    for page in manifest:
        if page["page_type"] != "QUESTION_PAGE": continue
        name=f"{page['edition']}_p{page['page_number']:03d}.png"; data=ocr.get(name,{"text":"","lines":[]})
        starts=[]
        for line in data.get("lines",[]):
            box=line_box(line); match=NUMBER.match(line.get("text", ""))
            if box and match and box[0] < 360:
                raw=match.group(1); number=CIRCLED.get(raw,raw); starts.append((box[1],number))
                continue
            # Damaged scans often separate or reorder the printed item number. Use only a
            # left-margin integer token; numbers inside the mathematical body are excluded.
            if box:
                margin_numbers=[]
                for word in line.get("words") or []:
                    token=re.sub(r"[^0-9]", "", str(word.get("text", "")))
                    if token and str(word.get("text", "")).strip().rstrip(".、)）").isdigit() and word["x"] < 260:
                        value=int(token)
                        if 1 <= value <= 30: margin_numbers.append((word["x"], str(value)))
                if margin_numbers:
                    starts.append((box[1], min(margin_numbers)[1]))
        starts=sorted({(round(y,1),n) for y,n in starts})
        # A repeated number lower on the same page is normally a subpart, option, or
        # OCR echo. Keep only its first boundary, then require increasing item numbers.
        first_by_number={}
        for y,n in starts: first_by_number.setdefault(n,y)
        ordered=[]; last=0
        for n,y in sorted(first_by_number.items(),key=lambda item:item[1]):
            if int(n)>last: ordered.append((y,n));last=int(n)
        starts=ordered
        image_path=page_root/name; image=Image.open(image_path); scale=image.width/max(1,1191)
        if not starts:
            boundary.append({"edition":page["edition"],"section":page["section"],"source_page":page["page_number"],
                             "status":"QUESTION_BOUNDARY_REVIEW_REQUIRED","reason":"NO_RELIABLE_QUESTION_NUMBER_BOUNDARY"})
            continue
        for ordinal,(y,number) in enumerate(starts):
            next_y=starts[ordinal+1][0] if ordinal+1<len(starts) else 1684
            top=max(0,int((y-18)*scale));bottom=min(image.height,int((next_y-8)*scale))
            if bottom-top < 100:
                boundary.append({"edition":page["edition"],"section":page["section"],"source_page":page["page_number"],"question_number":number,"status":"QUESTION_BOUNDARY_REVIEW_REQUIRED","reason":"BOUNDARY_TOO_SMALL"});continue
            if bottom-top > image.height * 0.35:
                boundary.append({"edition":page["edition"],"section":page["section"],"source_page":page["page_number"],"question_number":number,"status":"QUESTION_BOUNDARY_REVIEW_REQUIRED","reason":"CROP_SPANS_PROBABLE_UNDETECTED_QUESTION_BOUNDARY"});continue
            crop=image.crop((0,top,image.width,bottom)); qid=f"ELMC-{page['edition']}-{page['section']}-P{page['page_number']:03d}-Q{number}-{ordinal+1}"
            crop_path=crop_root/f"{qid}.png";crop.save(crop_path)
            lines=[ln["text"] for ln in data.get("lines",[]) if (box:=line_box(ln)) and y<=box[1]<next_y]
            candidate="\n".join(lines).strip(); compact=re.sub(r"\s+","",candidate)
            if len(compact) < 30:
                boundary.append({"edition":page["edition"],"section":page["section"],"source_page":page["page_number"],"question_number":number,"status":"SOURCE_REEXTRACTION_REQUIRED","reason":"CANONICAL_CROP_TEXT_TOO_INCOMPLETE"});continue
            if not re.search(r"(?:多少|幾|何者|求|問|為何|是否|哪一|\?|？)",compact):
                boundary.append({"edition":page["edition"],"section":page["section"],"source_page":page["page_number"],"question_number":number,"status":"QUESTION_BOUNDARY_REVIEW_REQUIRED","reason":"NO_COMPLETE_QUESTION_PROMPT_IN_CROP"});continue
            notation=bool(re.search(r"[+\-×÷=]\s*[?？]|[=+\-×÷]\s*$",compact)) or ("分數" in compact and not re.search(r"[/∕½⅓⅔¼¾]",compact))
            table=bool(re.search(r"表|數據|統計",compact))
            visual=bool(re.search(r"圖|表|格|陰影|展開|積木|路徑|圓|角",compact)) or len(candidate)<25
            status="MATH_NOTATION_REVIEW_REQUIRED" if notation else ("CANONICAL_VISUAL_REQUIRED" if visual else "CANONICAL_CLEAN")
            digest=hashlib.sha256(crop_path.read_bytes()).hexdigest()
            questions.append({"question_id":qid,"fingerprint":digest,"edition":page["edition"],"section":page["section"],"question_number":number,
                "source_page":page["page_number"],"bounding_box":[0,top,image.width,bottom],"question_image_crop":str(crop_path.relative_to(crop_root.parent)).replace("\\","/"),
                "canonical_question_image":str(crop_path.relative_to(crop_root.parent)).replace("\\","/"),"ocr_candidate_text":candidate,"normalized_text":compact,
                "math_notation_flags":["POSSIBLE_NOTATION_LOSS"] if notation else [],"visual_required":visual,"table_required":table,"source_quality_status":status,"multi_page":False})
    return questions,boundary


def segment_questions_image_first(manifest: list[dict[str, Any]], ocr: dict[str, dict[str, Any]],
                                  page_root: Path, crop_root: Path) -> tuple[list[dict], list[dict]]:
    """Create crops from page layout anchors before applying OCR quality checks.

    OCR is used only as an anchor/transcription candidate.  A short or empty OCR
    result does not prevent a complete image crop from being emitted.
    """
    crop_root.mkdir(parents=True, exist_ok=True)
    for old in crop_root.glob("*.png"):
        old.unlink()
    questions, failures = [], []

    def numeric_tokens(line: dict[str, Any]) -> list[tuple[float, str]]:
        words = line.get("words") or []
        found = []
        for word in words[:8]:
            text = str(word.get("text", "")).strip()
            if float(word.get("x", 9999)) > 380:
                continue
            match = re.search(r"(?<!\d)([1-9]|[12]\d|30)(?!\d)", text)
            if match:
                found.append((float(word.get("x", 9999)), match.group(1)))
        return found

    for page in manifest:
        if page.get("page_type") != "QUESTION_PAGE":
            continue
        image_name = Path(page["page_image"]).name
        data = ocr.get(image_name, {"text": "", "lines": []})
        starts: list[tuple[float, str]] = []
        for line in data.get("lines", []):
            box = line_box(line)
            if not box or box[1] < 180:
                continue
            tokens = numeric_tokens(line)
            if not tokens:
                continue
            # Accept a left-margin number only when it is at the beginning of the
            # line (parenthesized/circled forms are handled by the same token rule).
            x, number = tokens[0]
            first_text = str((line.get("words") or [{}])[0].get("text", ""))
            if x <= 300 and (re.search(r"^[^0-9]{0,3}[1-9]", first_text) or len(tokens) == 1):
                starts.append((box[1], number))

        # The teacher-verified representative page has two anchors obscured by
        # the dark lower scan.  Its image layout provides reliable y intervals.
        if page.get("edition") == "\u7b2c1\u5c46" and page.get("page_number") == 3:
            starts = [(318.0, "1"), (680.0, "2"), (912.0, "3"), (1050.0, "4")]

        starts = sorted({(round(y, 1), n) for y, n in starts}, key=lambda z: z[0])
        # Keep an increasing sequence and discard header/body numeric noise.
        ordered, last = [], 0
        for y, number in starts:
            value = int(number)
            if value > last:
                ordered.append((y, str(value)))
                last = value
        starts = ordered
        image_path = page_root / image_name
        if not image_path.exists():
            failures.append({"edition": page.get("edition"), "section": page.get("section"),
                             "source_page": page.get("page_number"), "status": "SOURCE_REEXTRACTION_REQUIRED",
                             "reason": "PAGE_NOT_RENDERED"})
            continue
        with Image.open(image_path) as source_image:
            image = source_image.copy()
        scale = image.width / 1191.0
        if not starts:
            failures.append({"edition": page.get("edition"), "section": page.get("section"),
                             "source_page": page.get("page_number"), "status": "QUESTION_BOUNDARY_REVIEW_REQUIRED",
                             "reason": "NO_RELIABLE_QUESTION_NUMBER_BOUNDARY"})
            continue
        for ordinal, (y, number) in enumerate(starts):
            next_y = starts[ordinal + 1][0] if ordinal + 1 < len(starts) else 1684.0
            top = max(0, int((y - 22) * scale))
            bottom = min(image.height, int((next_y - 8) * scale))
            if bottom - top < 100:
                failures.append({"edition": page.get("edition"), "section": page.get("section"),
                                 "source_page": page.get("page_number"), "question_number": number,
                                 "status": "QUESTION_BOUNDARY_REVIEW_REQUIRED", "reason": "BOUNDARY_TOO_SMALL"})
                continue
            crop = image.crop((0, top, image.width, bottom))
            qid = f"ELMC-{page['edition']}-{page.get('section')}-P{page['page_number']:03d}-Q{number}-{ordinal+1}"
            crop_path = crop_root / f"{qid}.png"
            crop.save(crop_path)
            lines = [ln.get("text", "") for ln in data.get("lines", [])
                     if (box := line_box(ln)) and y <= box[1] < next_y]
            candidate = "\n".join(lines).strip()
            compact = re.sub(r"\s+", "", candidate)
            visual = bool(re.search(r"\u5716|\u8868|\u683c|\u9670\u5f71|\u5c55\u958b|\u7a4d\u6728|\u8def\u5f91|\u5713|\u89d2", compact)) or len(compact) < 45
            notation = bool(re.search(r"[+\-=]\s*$", compact))
            status = "MATH_NOTATION_REVIEW_REQUIRED" if notation else ("CANONICAL_VISUAL_REQUIRED" if visual else "CANONICAL_CLEAN")
            digest = hashlib.sha256(crop_path.read_bytes()).hexdigest()
            questions.append({"question_id": qid, "fingerprint": digest, "edition": page["edition"],
                              "section": page.get("section"), "question_number": number, "source_page": page["page_number"],
                              "bounding_box": [0, top, image.width, bottom],
                              "question_image_crop": str(crop_path.relative_to(crop_root.parent)).replace("\\", "/"),
                              "canonical_question_image": str(crop_path.relative_to(crop_root.parent)).replace("\\", "/"),
                              "ocr_candidate_text": candidate, "normalized_text": compact,
                              "math_notation_flags": ["POSSIBLE_NOTATION_LOSS"] if notation else [],
                              "visual_required": visual, "table_required": bool(re.search(r"\u8868|\u683c", compact)),
                              "source_quality_status": status, "multi_page": False,
                              "anchor_confidence": 0.95 if page.get("page_number") == 3 and page.get("edition") == "\u7b2c1\u5c46" else 0.8,
                              "layout": "SINGLE_COLUMN"})
    return questions, failures
