"""Acquire and inventory allowlisted official PRIVATE_JH public exam PDFs.

Raw PDFs and extracted question text are written only below .local/.  The
script performs no model or database calls and never follows arbitrary links.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local/stage7_private_jh"
PDF_DIR = LOCAL / "source_pdfs"
RAW_DIR = LOCAL / "raw_extracted"
REGISTRY = LOCAL / "public_source_registry.json"
CORPUS = RAW_DIR / "public_private_jh_questions.jsonl"

OFFICIAL_DOMAINS = {"www.ynhs.ylc.edu.tw", "www.lmsh.tn.edu.tw", "www.shinmin.tc.edu.tw"}
SOURCES = (
    {"school":"永年高級中學","year":"110","exam_name":"永年盃國小學藝競試數學科",
     "page":"https://www.ynhs.ylc.edu.tw/news/2/96",
     "url":"https://www.ynhs.ylc.edu.tw/archive/news/item/110%E5%AD%B8%E8%97%9D%E7%AB%B6%E8%A9%A6%E6%95%B8%E5%AD%B8%E7%A7%91%E8%80%83%E9%A1%8C.pdf","answer":False,"expected":30},
    {"school":"永年高級中學","year":"111","exam_name":"永年盃國小學藝競試數學科",
     "page":"https://www.ynhs.ylc.edu.tw/news/2/96",
     "url":"https://www.ynhs.ylc.edu.tw/archive/news/item/111%E5%B9%B4%E5%AD%B8%E8%97%9D%E7%AB%B6%E8%A9%A6--%E6%95%B8%E5%AD%B8.pdf","answer":True,"expected":30},
    {"school":"永年高級中學","year":"112","exam_name":"永年盃國小學藝競試數學科",
     "page":"https://www.ynhs.ylc.edu.tw/news/2/96",
     "url":"https://www.ynhs.ylc.edu.tw/archive/news/item/%E6%95%99%E5%8B%99%E8%99%95/%E5%AD%B8%E8%97%9D%E7%AB%B6%E8%A9%A6/112%E6%B0%B8%E5%B9%B4%E7%9B%83%E5%AD%B8%E8%97%9D%E7%AB%B6%E8%A9%A6%E6%95%B8%E5%AD%B8%E7%A7%91-%E5%90%AB%E8%A7%A3%E7%AD%94-.pdf","answer":True,"expected":30},
    {"school":"永年高級中學","year":"113","exam_name":"永年盃國小學藝競試數學科",
     "page":"https://www.ynhs.ylc.edu.tw/news/2/96",
     "url":"https://www.ynhs.ylc.edu.tw/archive/news/item/%E6%95%99%E5%8B%99%E8%99%95/%E6%95%99%E5%8B%99%E4%B8%BB%E4%BB%BB/113%E5%B9%B4%E6%B0%B8%E5%B9%B4%E7%9B%83%E5%AD%B8%E8%97%9D%E7%AB%B6%E8%A9%A6%E6%95%B8%E5%AD%B8%E7%A7%91-%E5%90%AB%E8%A7%A3%E7%AD%94-.pdf","answer":True,"expected":30},
    {"school":"明達高級中學","year":"112","exam_name":"小六學力檢測數學科",
     "page":"https://www.lmsh.tn.edu.tw/ischool/publish_page/53/?cid=660",
     "url":"https://www.lmsh.tn.edu.tw/resource/openfid.php?id=15701","answer":False,"expected":25},
    {"school":"明達高級中學","year":"113","exam_name":"小六學藝競賽邏輯運算思維",
     "page":"https://www.lmsh.tn.edu.tw/ischool/publish_page/53/?cid=660",
     "url":"https://www.lmsh.tn.edu.tw/resource/openfid.php?id=17762","answer":False,"expected":25},
    {"school":"明達高級中學","year":"114A","exam_name":"小六學藝競賽邏輯運算思維甲卷",
     "page":"https://www.lmsh.tn.edu.tw/ischool/publish_page/53/?cid=660",
     "url":"https://www.lmsh.tn.edu.tw/ischool/rfile/ef0f20001d5b6004acd2b1a9dac15fa9","answer":False,"expected":25},
    {"school":"明達高級中學","year":"114B","exam_name":"小六學藝競賽邏輯運算思維乙卷",
     "page":"https://www.lmsh.tn.edu.tw/ischool/publish_page/53/?cid=660",
     "url":"https://www.lmsh.tn.edu.tw/ischool/rfile/067295a3bb07570d8c0155a69383c573","answer":False,"expected":25},
)

TOPICS = {
    "整數": ("整數", "質數", "偶數", "奇數", "餘數"), "因數倍數": ("因數", "倍數", "公因數", "公倍數", "互質"),
    "分數": ("分數", "分子", "分母", "約分"), "小數": ("小數", "0."), "百分率": ("百分", "%", "％"),
    "比與比例": ("比例", "比值", "比為"), "速率": ("速率", "速度", "公里／", "公里/"), "時間": ("分鐘", "小時", "時刻"),
    "平均": ("平均",), "單位換算": ("公尺", "公分", "公里", "毫升", "公升"), "面積": ("面積", "平方"),
    "體積": ("體積", "立方"), "幾何": ("角度", "對稱", "圓形", "三角形", "長方形", "正方形"),
    "規律": ("規律", "按照順序", "數列"), "邏輯": ("邏輯", "必定", "可能", "最多", "最少"),
    "多步驟應用": ("共要", "相差", "剩餘", "合起來", "至少", "經過"),
}
QUESTION_START = re.compile(r"(?m)^\s*(?:[（(]\s*[）)]\s*)?(\d{1,2})\s*[.、．]\s*")


def _filename(source: dict) -> str:
    school = "YONGNIAN" if source["school"].startswith("永年") else "MINGDA"
    return f"{school}_{source['year']}_EXAM_MATH.pdf"


def _official(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in OFFICIAL_DOMAINS


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_normalize(text).lower().encode("utf-8")).hexdigest()


def _download(source: dict, target: Path) -> None:
    if not (_official(source["page"]) and _official(source["url"])):
        raise ValueError("NON_OFFICIAL_SOURCE")
    request = urllib.request.Request(source["url"], headers={"User-Agent":"MathAI-Stage7-Public-Corpus/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read()
    if not content.startswith(b"%PDF"):
        raise ValueError("NOT_A_PDF")
    target.write_bytes(content)


def _answer_key(last_page_text: str) -> dict[int, str]:
    lines = [line.strip() for line in last_page_text.splitlines() if line.strip()]
    answers: dict[int, str] = {}
    for index, line in enumerate(lines):
        numbers = [int(value) for value in re.findall(r"\b(?:[1-9]|[12]\d|30)\b", line)]
        if len(numbers) < 5:
            continue
        for following in lines[index + 1:index + 4]:
            letters = re.findall(r"\b[ABCD]\b", following.upper())
            if len(letters) >= len(numbers):
                answers.update(zip(numbers, letters))
                break
    return answers


def _extract(pdf: Path) -> tuple[list[tuple[int, str]], int, dict[int, str]]:
    reader = PdfReader(str(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    matches = list(QUESTION_START.finditer(text))
    questions: list[tuple[int, str]] = []
    seen_numbers: set[int] = set()
    for index, match in enumerate(matches):
        number = int(match.group(1))
        if number in seen_numbers or number < 1 or number > 60:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = _normalize(text[match.end():end])
        if len(body) < 12 or not re.search(r"[?？]|[（(]?[ABCD][）)]", body):
            continue
        seen_numbers.add(number)
        questions.append((number, body))
    return questions, len(reader.pages), _answer_key(reader.pages[-1].extract_text() or "")


def run() -> dict:
    PDF_DIR.mkdir(parents=True, exist_ok=True); RAW_DIR.mkdir(parents=True, exist_ok=True)
    registry: list[dict] = []; all_questions: list[dict] = []
    for source in SOURCES:
        pdf = PDF_DIR / _filename(source)
        row = {"school":source["school"], "year":source["year"], "exam_name":source["exam_name"],
               "official_url":source["page"], "document_url":source["url"], "source_type":"OFFICIAL_PUBLIC_SCHOOL_EXAM",
               "grade_scope":"G6_TO_G7", "math_question_estimate":0, "answer_available":source["answer"],
               "official_domain":_official(source["page"]) and _official(source["url"]),
               "download_status":"PENDING", "parse_status":"PENDING", "usable_status":"PENDING", "reason":""}
        try:
            if not pdf.exists(): _download(source, pdf)
            row["download_status"] = "DOWNLOADED"
            extracted, pages, answers = _extract(pdf); row["math_question_estimate"] = len(extracted); row["pdf_pages"] = pages
            if not source["answer"]:
                answers = {}
            expected = source.get("expected", 0); complete = bool(extracted) and (not expected or len(extracted) >= expected)
            row["expected_questions"] = expected; row["answer_count"] = len(answers)
            row["parse_status"] = "PARSED" if complete else ("PARTIAL" if extracted else "FAILED")
            row["usable_status"] = "USABLE" if complete else ("USABLE_PARTIAL" if extracted else "REJECTED")
            row["reason"] = ("Official public elementary academic exam with traceable page and document URL."
                             if complete else ("Only individually complete parsed questions retained; incomplete questions excluded."
                                               if extracted else "No complete math questions parsed."))
            for number, text in extracted:
                all_questions.append({"source_school":source["school"], "source_year":source["year"],
                    "source_exam":source["exam_name"], "question_number":number, "question_text":text,
                    "answer_if_available":answers.get(number), "source_url":source["url"], "fingerprint":_fingerprint(text),
                    "topic_groups":[topic for topic, words in TOPICS.items() if any(word in text for word in words)]})
        except Exception as exc:
            row.update(download_status="FAILED", parse_status="FAILED", usable_status="REJECTED", reason=type(exc).__name__)
        registry.append(row)
    unique: dict[str, dict] = {}
    for question in all_questions: unique.setdefault(question["fingerprint"], question)
    CORPUS.write_text("".join(json.dumps(row, ensure_ascii=False)+"\n" for row in unique.values()), encoding="utf-8")
    topic_counts = Counter(topic for row in unique.values() for topic in row["topic_groups"])
    summary = {"schema_version":"1.0", "sources":registry, "raw_math_questions":len(all_questions),
               "unique_usable_questions":len(unique), "duplicates_removed":len(all_questions)-len(unique),
               "invalid_incomplete_removed":sum(max(0, row.get("expected_questions",0)-row["math_question_estimate"]) for row in registry),
               "schools_represented":len({q["source_school"] for q in unique.values()}),
               "years_represented":len({q["source_year"] for q in unique.values()}), "topic_counts":dict(sorted(topic_counts.items())),
               "status":"CORPUS_READY" if len(unique)>=100 else ("CORPUS_PARTIAL" if len(unique)>=50 else "CORPUS_INSUFFICIENT"),
               "api_calls":{"gemini":0,"deepseek":0}, "production_reads":0, "production_writes":0}
    REGISTRY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = run()
    print(json.dumps({key:value for key,value in result.items() if key not in {"sources","topic_counts"}}, ensure_ascii=False))
