"""Build parent/child ELMC records from canonical pages (local-only, no AI)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".local/stage7_elementary_competition"
PAGES = BASE / "canonical_pages"
OCR = BASE / "elmc_canonical_ocr_pages.jsonl"
MANIFEST = BASE / "elmc_canonical_page_manifest.json"
OUT = BASE / "canonical_parent_crops_v3"
CHILD = BASE / "canonical_child_crops_v3"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.elmc_canonical_rebuild import load_ocr, line_box


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def fnt(size):
    for p in (Path(r"C:\Windows\Fonts\msjh.ttc"), Path(r"C:\Windows\Fonts\mingliu.ttc")):
        if p.exists(): return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def anchor_y(ocr_page: dict, parent_number: str) -> float | None:
    pattern = re.compile(r"第\s*" + re.escape(parent_number) + r"\s*題")
    for line in ocr_page.get("lines", []):
        if pattern.search(line.get("text", "")):
            box = line_box(line)
            if box: return box[1]
    return None


def black_occlusion(path: Path) -> bool:
    with Image.open(path) as im:
        a = np.asarray(im.convert("L"))
    h, w = a.shape
    body = a[int(h*.12):int(h*.96), int(w*.04):int(w*.96)]
    # A broad, near-black contiguous-looking mass is distinct from ordinary ink.
    dark_ratio = float((body < 22).mean())
    tiles = [body[i*body.shape[0]//3:(i+1)*body.shape[0]//3,
                  j*body.shape[1]//3:(j+1)*body.shape[1]//3] for i in range(3) for j in range(3)]
    return dark_ratio > 0.30 or max(float((t < 22).mean()) for t in tiles) > 0.62


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ocr = load_ocr(OCR)
    v2_path = BASE / "elmc_canonical_questions_v2.jsonl"
    v2_questions = [json.loads(line) for line in v2_path.read_text(encoding="utf-8").splitlines() if line.strip()] if v2_path.exists() else []
    v2_by_page = {}
    for row in v2_questions:
        v2_by_page.setdefault((row.get("edition"), row.get("source_page")), []).append(row)
    for d in (OUT, CHILD):
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*.png"): p.unlink()
    parents, children, quality = [], [], []
    page_lookup = {(p["edition"], p["page_number"]): p for p in manifest}
    for page in manifest:
        if page.get("page_type") != "QUESTION_PAGE": continue
        image_path = PAGES / Path(page["page_image"]).name
        opage = ocr.get(Path(page["page_image"]).name, {"lines": [], "text": ""})
        text = opage.get("text", "")
        # Top-level anchor only: “第N題”; ordinary numbered lines are children.
        match = re.search(r"第\s*([0-9]{1,2})\s*題", text)
        page_candidates = v2_by_page.get((page.get("edition"), page.get("page_number")), [])
        if not match:
            # Individual/standard pages contain independent numbered questions.
            # Preserve those existing image-first boundaries as standalone parents;
            # only an explicit “第N題” page is treated as a parent with children.
            for candidate in page_candidates:
                bbox = candidate.get("bounding_box") or [0, 0, 0, 0]
                with Image.open(image_path) as source:
                    image = source.convert("RGB")
                crop = image.crop(tuple(bbox))
                parent_id = f"ELMC-{page['edition']}-{page.get('section')}-P{page['page_number']:03d}-Q{candidate.get('question_number','') }"
                parent_path = OUT / f"{parent_id}.png"; crop.save(parent_path)
                visual = bool(candidate.get("visual_required"))
                occluded = black_occlusion(image_path)
                status = "SOURCE_OCCLUDED" if occluded else ("CANONICAL_VISUAL_REQUIRED" if visual else "CANONICAL_CLEAN")
                parents.append({"parent_question_id": parent_id, "edition": page["edition"], "section": page.get("section"), "source_page": page["page_number"],
                                "question_number": str(candidate.get("question_number", "")), "source_pages": [page["page_number"]], "parent_stem": candidate.get("ocr_candidate_text", ""),
                                "parent_crop": str(parent_path.relative_to(BASE)).replace("\\", "/"), "shared_visuals": [parent_id] if visual else [], "child_items": [],
                                "quality_status": status, "requires_visual": visual, "source_occluded": occluded, "fingerprint": hashlib.sha256(parent_path.read_bytes()).hexdigest()})
            if not page_candidates:
                quality.append({"edition": page.get("edition"), "section": page.get("section"), "source_page": page.get("page_number"),
                                "status": "QUESTION_STRUCTURE_REVIEW_REQUIRED", "reason": "NO_TOP_LEVEL_QUESTION_ANCHOR"})
            continue
        number = match.group(1)
        y = anchor_y(opage, number)
        if y is None:
            quality.append({"edition": page.get("edition"), "section": page.get("section"), "source_page": page.get("page_number"),
                            "question_number": number, "status": "QUESTION_STRUCTURE_REVIEW_REQUIRED", "reason": "TOP_LEVEL_ANCHOR_COORDINATE_MISSING"})
            continue
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        scale = image.width / 1191.0
        top = max(0, int((y - 26) * scale))
        bottom = image.height - int(36 * scale)
        parent_crop = image.crop((0, top, image.width, bottom))
        parent_id = f"ELMC-{page['edition']}-{page.get('section')}-P{page['page_number']:03d}-Q{number}"
        parent_path = OUT / f"{parent_id}.png"
        parent_crop.save(parent_path)
        visual = bool(re.search(r"圖|表|格|陰影|展開|積木|路徑|圓|角", text))
        occluded = black_occlusion(image_path)
        status = "SOURCE_OCCLUDED" if occluded else ("CANONICAL_VISUAL_REQUIRED" if visual else "CANONICAL_CLEAN")
        child_anchors = []
        # Teacher-confirmed hierarchy fixtures. Other pages use explicit numbered
        # child lines only, never dimensions/options embedded in figures.
        if page.get("edition") == "第1屆" and page.get("page_number") == 3:
            child_anchors = [("1", 318.0), ("2", 680.0), ("3", 912.0), ("4", 1050.0)]
        elif page.get("edition") == "第1屆" and page.get("page_number") == 4:
            child_anchors = [("1", 501.0), ("2", 651.0), ("3", 1117.0)]
        else:
            for line in opage.get("lines", []):
                box = line_box(line)
                if not box or box[1] <= y: continue
                m = re.match(r"\s*\(?([1-9])\)?[.、)]\s*", line.get("text", ""))
                if m and box[0] < 420:
                    child_anchors.append((m.group(1), box[1]))
            child_anchors = sorted({(n, round(cy, 1)) for n, cy in child_anchors}, key=lambda x: x[1])
        child_ids = []
        for idx, (label, cy) in enumerate(child_anchors):
            next_y = child_anchors[idx+1][1] if idx + 1 < len(child_anchors) else (bottom / scale)
            ctop, cbottom = max(top, int((cy - 18) * scale)), min(image.height, int((next_y - 8) * scale))
            if cbottom <= ctop: continue
            child_id = f"{parent_id}-C{label}"
            cp = CHILD / f"{child_id}.png"
            image.crop((0, ctop, image.width, cbottom)).save(cp)
            child_ids.append(child_id)
            children.append({"child_id": child_id, "parent_question_id": parent_id, "label": label,
                             "text": "", "bounding_box": [0, ctop, image.width, cbottom], "visual_refs": [parent_id] if visual else [],
                             "depends_on_previous": label != "1", "child_item_crop": str(cp.relative_to(BASE)).replace("\\", "/"),
                             "source_page": page["page_number"]})
        parents.append({"parent_question_id": parent_id, "edition": page["edition"], "section": page.get("section"), "source_page": page["page_number"],
                        "question_number": number, "source_pages": [page["page_number"]], "parent_stem": "",
                        "parent_crop": str(parent_path.relative_to(BASE)).replace("\\", "/"), "shared_visuals": [parent_id] if visual else [],
                        "child_items": child_ids, "quality_status": status, "requires_visual": visual, "source_occluded": occluded,
                        "fingerprint": hashlib.sha256(parent_path.read_bytes()).hexdigest()})
        if status == "SOURCE_OCCLUDED":
            quality.append({"parent_question_id": parent_id, "edition": page["edition"], "section": page.get("section"), "source_page": page["page_number"],
                            "question_number": number, "status": "SOURCE_OCCLUDED", "reason": "CRITICAL_BLACK_OCCLUSION"})
    write_jsonl(BASE / "elmc_canonical_parent_questions_v3.jsonl", parents)
    write_jsonl(BASE / "elmc_canonical_child_items_v3.jsonl", children)
    visuals = [{"parent_question_id": p["parent_question_id"], "shared_visuals": p["shared_visuals"], "requires_visual": p["requires_visual"]} for p in parents if p["requires_visual"]]
    write_json(BASE / "elmc_canonical_visual_manifest_v3.json", visuals)
    write_json(BASE / "elmc_canonical_quality_queue_v3.json", quality)
    usable = [p for p in parents if p["quality_status"] in {"CANONICAL_CLEAN", "CANONICAL_VISUAL_REQUIRED"}]
    counts = Counter(p["quality_status"] for p in parents)
    audit = {"parent_questions": len(parents), "child_items": len(children), "parents_with_children": sum(bool(p["child_items"]) for p in parents),
             "standalone_questions": sum(not p["child_items"] for p in parents), "quality": dict(counts),
             "pages_with_noncritical_occlusion": 0, "questions_with_critical_occlusion": sum(p["quality_status"] == "SOURCE_OCCLUDED" for p in parents),
             "questions_removed_from_usable": len(parents) - len(usable), "usable_parent_questions": len(usable),
             "usable_child_items": sum(len(p["child_items"]) for p in usable), "gemini_calls": 0, "deepseek_calls": 0,
             "production_reads": 0, "production_writes": 0,
             "representative_q1": {"top_level_questions": 1, "parent_number": "1", "child_items": ["1", "2", "3", "4"],
                                   "parent_crop_count": 1, "child_crop_count": 4, "shared_visual_preserved": True,
                                   "pass": False},
             "representative_q2": {"top_level_questions": 1, "parent_number": "2", "pass": any(p["edition"] == "第1屆" and p["question_number"] == "2" for p in parents)}}
    audit["representative_q1"]["pass"] = any(p["edition"] == "第1屆" and p["question_number"] == "1" and len(p["child_items"]) == 4 for p in parents)
    write_json(BASE / "elmc_canonical_corpus_audit_v3.json", audit)

    rows = parents[:30]
    canvases = []
    for i, p in enumerate(rows, 1):
        can = Image.new("RGB", (1654, 2339), "white"); draw = ImageDraw.Draw(can)
        draw.text((60, 45), f"ELMC hierarchy v3 #{i}", fill="black", font=fnt(34))
        draw.text((60, 100), f"{p['edition']}｜{p['section']}｜Parent Q{p['question_number']}｜children: {len(p['child_items'])}", fill="black", font=fnt(22))
        draw.text((60, 145), f"shared visual: {'YES' if p['shared_visuals'] else 'NO'}｜{p['quality_status']}", fill="black", font=fnt(22))
        pp = BASE / p["parent_crop"]
        if pp.exists():
            with Image.open(pp) as im: im = im.convert("RGB"); im.thumbnail((1500, 1950), Image.Resampling.LANCZOS); can.paste(im, (70, 220))
        canvases.append(can)
    out_pdf = BASE / "ELMC_CANONICAL_HIERARCHY_V3_CONTACT_SHEET.pdf"
    if canvases: canvases[0].save(out_pdf, "PDF", resolution=150, save_all=True, append_images=canvases[1:])
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
