"""Build a deterministic diversified 20-question G8 smoke set from the local 200-row pilot.

Selection policy:
- 8 questions: 平方差公式應用
- 6 questions: 化簡根式
- 6 questions: other strata, round-robin across distinct (unit, knowledge_tag)

Safety:
- Reads local Stage 5B pilot artifacts only.
- Writes only under .local/stage5_g8_mapping_pilot/<target-name>.
- No Supabase/network/database access.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".local" / "stage5_g8_mapping_pilot"


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required local pilot artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Missing required local pilot artifact: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _stable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: str(row.get("fingerprint") or ""))


def _pick_other_diverse(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (str(row.get("unit") or ""), str(row.get("knowledge_tag") or ""))
        strata[key].append(row)
    for key in strata:
        strata[key] = _stable(strata[key])

    selected: list[dict[str, Any]] = []
    keys = sorted(strata)
    offset = 0
    while len(selected) < count:
        progressed = False
        for key in keys:
            members = strata[key]
            if offset < len(members):
                selected.append(members[offset])
                progressed = True
                if len(selected) == count:
                    break
        if not progressed:
            break
        offset += 1
    return selected


def build(target_name: str) -> dict[str, Any]:
    target = SOURCE / target_name
    packets = _read_jsonl(SOURCE / "g8_mapping_input.jsonl")
    sample = _read_json(SOURCE / "g8_pilot_sample.json")
    if len(packets) != 200 or len(sample) != 200:
        raise RuntimeError(f"Expected prepared 200-row G8 pilot; packets={len(packets)} sample={len(sample)}")

    square = _stable([row for row in packets if str(row.get("knowledge_tag") or "") == "平方差公式應用"])
    radical = _stable([row for row in packets if str(row.get("knowledge_tag") or "") == "化簡根式"])
    other = _stable([
        row for row in packets
        if str(row.get("knowledge_tag") or "") not in {"平方差公式應用", "化簡根式"}
    ])

    if len(square) < 8:
        raise RuntimeError(f"Need at least 8 平方差公式應用 rows; got {len(square)}")
    if len(radical) < 6:
        raise RuntimeError(f"Need at least 6 化簡根式 rows; got {len(radical)}")

    selected_square = square[:8]
    selected_radical = radical[:6]
    selected_other = _pick_other_diverse(other, 6)
    if len(selected_other) != 6:
        raise RuntimeError(f"Need 6 diversified other rows; got {len(selected_other)}")

    selected = selected_square + selected_radical + selected_other
    fingerprints = [str(row.get("fingerprint") or "") for row in selected]
    if len(fingerprints) != 20 or len(set(fingerprints)) != 20:
        raise RuntimeError("Diversified smoke selection must contain exactly 20 unique fingerprints")

    sample_by_fp = {str(row.get("fingerprint") or ""): row for row in sample}
    selected_sample = [sample_by_fp[fp] for fp in fingerprints]

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    for name in ("g8_curriculum_skills.json", "g8_curriculum_micro_skills.json"):
        src = SOURCE / name
        if not src.exists():
            raise RuntimeError(f"Missing required local pilot artifact: {src}")
        shutil.copy2(src, target / name)

    _write_json(target / "g8_pilot_sample.json", selected_sample)
    _write_jsonl(target / "g8_mapping_input.jsonl", selected)

    other_strata = [
        {
            "unit": str(row.get("unit") or ""),
            "knowledge_tag": str(row.get("knowledge_tag") or ""),
            "fingerprint": str(row.get("fingerprint") or ""),
        }
        for row in selected_other
    ]
    manifest = {
        "stage": "5B-2A-diverse20",
        "target_name": target_name,
        "selection": {
            "平方差公式應用": len(selected_square),
            "化簡根式": len(selected_radical),
            "其他": len(selected_other),
        },
        "other_strata": other_strata,
        "total": len(selected),
        "production_reads": 0,
        "production_writes": 0,
    }
    _write_json(target / "diverse_smoke_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build diversified local-only G8 smoke set")
    parser.add_argument("--target-name", default="diverse20")
    args = parser.parse_args()
    manifest = build(args.target_name)
    target = SOURCE / args.target_name
    print("DIVERSE20:", json.dumps(manifest, ensure_ascii=False))
    print(f"Output: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
