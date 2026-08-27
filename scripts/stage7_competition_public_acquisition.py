"""Acquire/extract an official elementary competition corpus into .local only.

Network downloading is deliberately separate from this script.  The source PDF
manifest is fixed and auditable; this program only reads already-downloaded PDFs.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.competition_public_corpus import (eligible, extraction_risks, infer_topic,
    normalized_fingerprint, official_source, select_pilot)

LOCAL = ROOT / ".local" / "stage7_elementary_competition"
RAW_DIR = LOCAL / "raw_sources" / "IMC"
CROP_DIR = LOCAL / "question_crops"
MANIFEST = LOCAL / "competition_public_source_manifest.json"
RAW_OUT = LOCAL / "competition_raw_questions.jsonl"
QUALITY_OUT = LOCAL / "competition_quality_queue.json"
UNIQUE_OUT = LOCAL / "competition_unique_questions.jsonl"
PILOT_OUT = LOCAL / "competition_pilot100.jsonl"
PILOT_MANIFEST = LOCAL / "competition_pilot100_manifest.json"
AUDIT_OUT = LOCAL / "competition_public_corpus_audit.json"

IMC_PAGE_2024 = "https://imcct.net/cms2-47-lang1.html"
IMC_PAGE_2025 = "https://imcct.net/news1-575-lang1.html"
IMC_SECOND_2024 = "https://imcct.net/cms2-45-lang1.html"
PAPERS = (
    ("IMC_2024_PRELIM_G4.pdf", 2025, "PRELIMINARY", "G4", IMC_PAGE_2024, "https://imcct.net/UserFiles/files/20241216112118_3.pdf"),
    ("IMC_2024_PRELIM_G5.pdf", 2025, "PRELIMINARY", "G5", IMC_PAGE_2024, "https://imcct.net/UserFiles/files/20241220083511_0.pdf"),
    ("IMC_2024_PRELIM_G6.pdf", 2025, "PRELIMINARY", "G6", IMC_PAGE_2024, "https://imcct.net/UserFiles/files/20241220083511_1.pdf"),
    ("IMC_2025_PRELIM_G4.pdf", 2025, "PRELIMINARY", "G4", IMC_PAGE_2025, "https://imcct.net/UserFiles/news/575/20251201103125_3.pdf"),
    ("IMC_2025_PRELIM_G5.pdf", 2025, "PRELIMINARY", "G5", IMC_PAGE_2025, "https://imcct.net/UserFiles/news/575/20251201103125_4.pdf"),
    ("IMC_2025_PRELIM_G6.pdf", 2025, "PRELIMINARY", "G6", IMC_PAGE_2025, "https://imcct.net/UserFiles/news/575/20251201103305_0.pdf"),
    ("IMC_2024_SECOND_G4.pdf", 2024, "SECOND_ROUND", "G4", IMC_SECOND_2024, "https://imcct.net/UserFiles/files/20240327155628_0.pdf"),
    ("IMC_2024_SECOND_G5.pdf", 2024, "SECOND_ROUND", "G5", IMC_SECOND_2024, "https://imcct.net/UserFiles/files/20240401110303_0.pdf"),
    ("IMC_2024_SECOND_G6.pdf", 2024, "SECOND_ROUND", "G6", IMC_SECOND_2024, "https://imcct.net/UserFiles/files/20240401110303_1.pdf"),
    ("IMC_2024_OFFICIAL_PRELIM_G4.pdf", 2024, "PRELIMINARY", "G4", "https://imcct.net/cms2-44-lang1.html", "https://imcct.net/UserFiles/files/2024%E5%88%9D%E8%B3%BD%E8%A9%A6%E5%8D%B74%E5%B9%B4%E7%B4%9A(%E8%A7%A3%E6%9E%90%E7%89%88).pdf"),
    ("IMC_2024_OFFICIAL_PRELIM_G5.pdf", 2024, "PRELIMINARY", "G5", "https://imcct.net/cms2-44-lang1.html", "https://imcct.net/UserFiles/files/2024%E5%88%9D%E8%B3%BD%E8%A9%A6%E5%8D%B75%E5%B9%B4%E7%B4%9A(%E8%A7%A3%E6%9E%90%E7%89%88).pdf"),
    ("IMC_2024_OFFICIAL_PRELIM_G6.pdf", 2024, "PRELIMINARY", "G6", "https://imcct.net/cms2-44-lang1.html", "https://imcct.net/UserFiles/files/2024%E5%88%9D%E8%B3%BD%E8%A9%A6%E5%8D%B76%E5%B9%B4%E7%B4%9A(%E8%A7%A3%E6%9E%90%E7%89%88).pdf"),
)


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _ocr_page(page: Any, engine: Any) -> tuple[list[dict[str, Any]], Any]:
    import cv2
    import numpy as np
    pix = page.get_pixmap(matrix=__import__("pymupdf").Matrix(2.0, 2.0), alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    result, _ = engine(image)
    lines = []
    for box, text, confidence in result or []:
        lines.append({"box": box, "text": str(text).strip(), "confidence": float(confidence)})
    lines.sort(key=lambda item: (min(p[1] for p in item["box"]), min(p[0] for p in item["box"])))
    return lines, image


def _extract_paper(path: Path, year: int, round_name: str, grade: str, source_page: str, document_url: str,
                   engine: Any) -> list[dict[str, Any]]:
    import cv2
    import pymupdf
    records: list[dict[str, Any]] = []
    document = pymupdf.open(path)
    CROP_DIR.mkdir(parents=True, exist_ok=True)
    local_number = 0
    for page_index in range(1, len(document)):
        lines, image = _ocr_page(document[page_index], engine)
        starts = [i for i, line in enumerate(lines) if re.match(r"^\s*(?:[1-9]|1\d|2[0-5])[\.．、]\s*", line["text"])]
        for pos, start in enumerate(starts):
            end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
            segment = lines[start:end]
            analysis_at = next((i for i, line in enumerate(segment)
                                if re.search(r"\u89e3\u6790|\u89e3\u7b54|solution", line["text"], re.IGNORECASE)), len(segment))
            question_lines = segment[:analysis_at]
            if not question_lines:
                continue
            question_text = " ".join(line["text"] for line in question_lines).strip()
            if len(question_text) < 12:
                continue
            local_number += 1
            top = max(0, int(min(p[1] for p in question_lines[0]["box"])) - 12)
            bottom = min(image.shape[0], int(max(p[1] for line in question_lines for p in line["box"])) + 12)
            crop_name = f"{path.stem}_P{page_index + 1}_Q{local_number:02d}.png"
            crop_path = CROP_DIR / crop_name
            cv2.imwrite(str(crop_path), image[top:bottom, :])
            confidence = sum(line["confidence"] for line in question_lines) / len(question_lines)
            record = {
                "competition": "IMC", "country_or_region": "Taiwan", "year": year,
                "round": round_name, "grade": grade, "question_number": local_number,
                "question_text": question_text, "answer_choice": None, "answer": None,
                "source_file": path.name, "source_page": source_page, "document_url": document_url,
                "page_number": page_index + 1, "page_crop": str(crop_path.relative_to(LOCAL)),
                "has_required_image": bool(re.search(r"\u5716|figure|shown", question_text, re.IGNORECASE)),
                "ocr_confidence": round(confidence, 5), "official_source": True,
                "extraction_status": "COMPLETE", "competition_topic": infer_topic(question_text),
            }
            record["fingerprint"] = normalized_fingerprint(question_text)
            record["quality_risks"] = extraction_risks(record)
            if record["quality_risks"]:
                record["extraction_status"] = "SOURCE_NEEDS_REEXTRACTION"
            records.append(record)
    return records


def _extract_saved_crops(path: Path, year: int, round_name: str, grade: str, source_page: str,
                         document_url: str, engine: Any) -> list[dict[str, Any]]:
    """Resume from durable question crops created by a previous interrupted pass."""
    import cv2

    crops = sorted(CROP_DIR.glob(f"{path.stem}_P*_Q*.png"))
    records: list[dict[str, Any]] = []
    for crop in crops:
        match = re.search(r"_P(\d+)_Q(\d+)\.png$", crop.name)
        if not match:
            continue
        image = cv2.imread(str(crop))
        result, _ = engine(image)
        lines = [(str(text).strip(), float(confidence)) for _, text, confidence in result or []]
        question_text = " ".join(text for text, _ in lines).strip()
        confidence = sum(score for _, score in lines) / len(lines) if lines else 0.0
        record = {"competition": "IMC", "country_or_region": "Taiwan", "year": year,
            "round": round_name, "grade": grade, "question_number": int(match.group(2)),
            "question_text": question_text, "answer_choice": None, "answer": None,
            "source_file": path.name, "source_page": source_page, "document_url": document_url,
            "page_number": int(match.group(1)), "page_crop": str(crop.relative_to(LOCAL)),
            "has_required_image": bool(re.search(r"\u5716|figure|shown", question_text, re.IGNORECASE)),
            "ocr_confidence": round(confidence, 5), "official_source": True,
            "extraction_status": "COMPLETE", "competition_topic": infer_topic(question_text)}
        record["fingerprint"] = normalized_fingerprint(question_text)
        record["quality_risks"] = extraction_risks(record)
        if record["quality_risks"]:
            record["extraction_status"] = "SOURCE_NEEDS_REEXTRACTION"
        records.append(record)
    return records


def build() -> dict[str, Any]:
    from rapidocr_onnxruntime import RapidOCR

    missing = [name for name, *_ in PAPERS if not (RAW_DIR / name).is_file()]
    if missing:
        raise RuntimeError(f"DOWNLOAD_FAIL_CLOSED:{','.join(missing)}")
    if not all(official_source(page) and official_source(doc) for _, _, _, _, page, doc in PAPERS):
        raise RuntimeError("NON_OFFICIAL_SOURCE")

    source_rows = []
    raw: list[dict[str, Any]] = []
    prior_by_source: dict[str, list[dict[str, Any]]] = {}
    if RAW_OUT.is_file():
        for line in RAW_OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                prior = json.loads(line)
                prior_by_source.setdefault(str(prior.get("source_file")), []).append(prior)
    engine = RapidOCR()
    for name, year, round_name, grade, page, document in PAPERS:
        saved = list(CROP_DIR.glob(f"{Path(name).stem}_P*_Q*.png"))
        rows = prior_by_source.get(name) or (
            _extract_saved_crops(RAW_DIR / name, year, round_name, grade, page, document, engine)
            if saved else _extract_paper(RAW_DIR / name, year, round_name, grade, page, document, engine))
        for row in rows:
            row.update({"year": year, "round": round_name, "grade": grade,
                        "source_page": page, "document_url": document})
            row["competition_topic"] = infer_topic(str(row.get("question_text") or ""))
        source_rows.append({"competition": "IMC", "country_or_region": "Taiwan", "year": year,
            "round": round_name, "grade": grade, "source_domain": "imcct.net",
            "source_page": page, "source_file": name, "document_url": document,
            "official_source": True, "download_status": "DOWNLOADED", "question_count": len(rows),
            "answer_available": True})
        raw.extend(rows)
    source_rows.append({"competition": "Math Kangaroo", "year": 2020, "round": "OFFICIAL_PRACTICE",
        "grade": "G3-G4", "source_domain": "mathkangaroo.org",
        "source_page": "https://mathkangaroo.org/mks/practice/pdf-exams/", "source_file": None,
        "official_source": True, "download_status": "SKIPPED_LOGIN_OR_PLATFORM_RESTRICTION",
        "question_count": 0, "answer_available": False})
    source_rows.append({"competition": "Math Kangaroo", "year": 2020, "round": "OFFICIAL_PRACTICE",
        "grade": "G5-G6", "source_domain": "mathkangaroo.org",
        "source_page": "https://mathkangaroo.org/mks/practice/pdf-exams/", "source_file": None,
        "official_source": True, "download_status": "SKIPPED_LOGIN_OR_PLATFORM_RESTRICTION",
        "question_count": 0, "answer_available": False})

    unique_map: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in raw:
        if row["fingerprint"] in unique_map:
            duplicates += 1
        else:
            unique_map[row["fingerprint"]] = row
    unique = list(unique_map.values())
    quality = [{"fingerprint": r["fingerprint"], "source_file": r["source_file"],
                "question_number": r["question_number"], "risks": extraction_risks(r),
                "status": "SOURCE_NEEDS_REEXTRACTION"}
               for r in unique if extraction_risks(r)]
    usable = [r for r in unique if eligible(r)]
    diversity_error = None
    selected: list[dict[str, Any]] = []
    if len(usable) >= 100:
        try:
            selected = select_pilot(usable, 100)
        except RuntimeError as exc:
            diversity_error = str(exc)
    topics = Counter(r["competition_topic"] for r in selected)
    papers = Counter(r["source_file"] for r in selected)
    grades = Counter(r["grade"] for r in usable)
    risks = Counter(x for row in quality for x in row["risks"])
    audit = {
        "official_source_pages_checked": 4, "imc_papers_downloaded": 12,
        "math_kangaroo_papers_downloaded": 0, "paid_login_sources_skipped": 2,
        "failed_downloads": 0, "raw_questions": len(raw), "unique_questions": len(unique),
        "duplicates_removed": duplicates, "quality_rejected": len(quality), "usable_questions": len(usable),
        "grades": {g: grades[g] for g in ("G3", "G4", "G5", "G6")}, "out_of_scope": 0,
        "sources_represented": {"IMC": len(usable), "Math Kangaroo": 0},
        "years": sorted({r["year"] for r in usable}), "rounds": sorted({r["round"] for r in usable}),
        "quality": dict(risks), "pilot_target": 100, "pilot_selected": len(selected),
        "pilot_imc": len(selected), "pilot_math_kangaroo": 0,
        "largest_single_source_share": round(max(papers.values()) / len(selected), 4) if selected else 0,
        "largest_topic_like_cluster_share": round(max(topics.values()) / len(selected), 4) if selected else 0,
        "additional_needed": max(0, 100 - len(selected)),
        "topic_counts_usable": dict(Counter(r["competition_topic"] for r in usable)),
        "diversity_error": diversity_error,
        "status": "CORPUS_READY" if len(selected) == 100 else "CORPUS_INSUFFICIENT",
        "api_calls": 0, "gemini_calls": 0, "deepseek_calls": 0,
        "production_reads": 0, "production_writes": 0,
    }
    LOCAL.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"sources": source_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _jsonl(RAW_OUT, raw); _jsonl(UNIQUE_OUT, unique); _jsonl(PILOT_OUT, selected)
    QUALITY_OUT.write_text(json.dumps({"items": quality}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PILOT_MANIFEST.write_text(json.dumps({"target": 100, "selected": len(selected),
        "fingerprints": [r["fingerprint"] for r in selected]}, indent=2) + "\n", encoding="utf-8")
    AUDIT_OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
