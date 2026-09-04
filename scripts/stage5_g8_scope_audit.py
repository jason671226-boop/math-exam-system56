"""Local-only quality audit for Stage 5B-2B G8 scope-aware mapping.

Reads the completed 200-row human review CSV and produces compact summary artifacts.
No network, Supabase, or database access.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".local" / "stage5_g8_mapping_pilot" / "scope200"
INPUT = SOURCE / "g8_scope_human_review_queue.csv"
SUMMARY_JSON = SOURCE / "g8_scope_quality_summary.json"
SKILL_CSV = SOURCE / "g8_scope_skill_distribution.csv"
MICRO_CSV = SOURCE / "g8_scope_micro_distribution.csv"
OUT_CSV = SOURCE / "g8_scope_out_of_scope_10.csv"
FLAGS_CSV = SOURCE / "g8_scope_quality_flags.csv"


def read_rows() -> list[dict[str, str]]:
    if not INPUT.exists():
        raise RuntimeError(f"Missing completed review CSV: {INPUT}")
    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 200:
        raise RuntimeError(f"Expected 200 rows, got {len(rows)}")
    return rows


def write_counter(path: Path, name: str, counter: Counter[str]) -> None:
    total = sum(counter.values())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([name, "count", "percent"])
        for key, count in counter.most_common():
            w.writerow([key, count, round(count * 100.0 / total, 2) if total else 0])


def main() -> int:
    rows = read_rows()
    scope = Counter(r.get("scope_status", "") for r in rows)
    review = Counter(r.get("review_status", "") for r in rows)
    skills = Counter(r.get("skill_id", "") for r in rows if r.get("scope_status") == "IN_SCOPE_G8")
    micros = Counter(r.get("micro_skill_id", "") for r in rows if r.get("scope_status") == "IN_SCOPE_G8")

    invalid_rows = [r for r in rows if (r.get("validation_errors") or "").strip()]
    low_conf = []
    flags = []
    for r in rows:
        try:
            conf = float(r.get("confidence") or 0)
        except ValueError:
            conf = 0
        if conf < 0.85:
            low_conf.append(r)
            flags.append({"flag": "LOW_CONFIDENCE", **r})
        if r.get("scope_status") == "IN_SCOPE_G8" and not r.get("skill_id"):
            flags.append({"flag": "IN_SCOPE_WITHOUT_SKILL", **r})
        if r.get("scope_status") == "OUT_OF_SCOPE_G8" and (r.get("skill_id") or r.get("micro_skill_id")):
            flags.append({"flag": "OUT_SCOPE_HAS_MAPPING", **r})
        if (r.get("validation_errors") or "").strip():
            flags.append({"flag": "VALIDATION_ERROR", **r})

    out_rows = [r for r in rows if r.get("scope_status") == "OUT_OF_SCOPE_G8"]

    write_counter(SKILL_CSV, "skill_id", skills)
    write_counter(MICRO_CSV, "micro_skill_id", micros)

    fields = list(rows[0].keys()) if rows else []
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(out_rows)

    flag_fields = ["flag"] + fields
    with FLAGS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flag_fields, extrasaction="ignore")
        w.writeheader(); w.writerows(flags)

    top_skill = skills.most_common(1)[0] if skills else ("", 0)
    top_micro = micros.most_common(1)[0] if micros else ("", 0)
    summary = {
        "stage": "5B-2C",
        "sample_size": len(rows),
        "scope_counts": dict(scope),
        "review_counts": dict(review),
        "distinct_skills_used": len(skills),
        "distinct_micro_skills_used": len(micros),
        "top_skill": {"skill_id": top_skill[0], "count": top_skill[1]},
        "top_micro_skill": {"micro_skill_id": top_micro[0], "count": top_micro[1]},
        "low_confidence_count": len(low_conf),
        "validation_error_count": len(invalid_rows),
        "quality_flag_count": len(flags),
        "out_of_scope_count": len(out_rows),
        "production_reads": 0,
        "production_writes": 0,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("G8 SCOPE QUALITY AUDIT")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Summary : {SUMMARY_JSON}")
    print(f"Skills  : {SKILL_CSV}")
    print(f"Micros  : {MICRO_CSV}")
    print(f"OutScope: {OUT_CSV}")
    print(f"Flags   : {FLAGS_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
