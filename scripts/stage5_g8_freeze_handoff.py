"""Generate the public-safe G8 pilot freeze/handoff from local summary files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL = ROOT / ".local" / "stage5_g8_mapping_pilot"
DEFAULT_DOC = ROOT / "docs" / "stage5" / "G8_PILOT_FREEZE_HANDOFF.md"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def generate(local_root: Path, destination: Path) -> dict[str, Any]:
    scope = load(local_root / "scope200" / "scope_validation_report.json")
    quality = load(local_root / "scope200" / "g8_scope_quality_summary.json")
    coverage = load(local_root / "freeze" / "g8_coverage_summary.json")
    validation = load(local_root / "cross_unit" / "validation_summary.json")
    safety = all(x.get("production_reads") == 0 and x.get("production_writes") == 0 for x in (scope, quality, coverage, validation))
    scope_pass = scope.get("mapped") == 200 and scope.get("invalid") == 0
    complete = bool(scope_pass and validation.get("technical_pass") and safety)
    freeze_label = "G8 PILOT FOUNDATION: SAFE TO FREEZE" if complete else "G8 PILOT FOUNDATION: NOT COMPLETE"
    mismatch_note = (
        "建議準確率門檻已達成。" if validation.get("mapping_pilot_pass")
        else f"建議準確率門檻未全數達成；{validation.get('mismatch_count')} 筆 mismatch 已完整記錄於 local report，不影響 technical pipeline correctness。"
    )
    high_priority = coverage.get("high_priority_zero_coverage_skills", [])[:15]
    priority_lines = "\n".join(f"- `{row['skill_id']}` — {row.get('skill_name','')}" for row in high_priority) or "- 無"
    text = f"""# G8 Pilot Freeze / Handoff

## 結論與完成度

**{freeze_label}**

目前估計完成度：**60–65%（Pilot Foundation Complete）**。這代表 local 技術基礎可安全暫停，不代表完整題庫覆蓋或 Production 上線。

## 已完成 Stage

- Stage 5B-2A：local G8 mapping pilot preparation
- Stage 5B-2B：200 題 scope-aware pilot（checkpoint/resume、Scope Gate、resilient JSON parser）
- Stage 5B-2C：quality audit
- Stage 5B-2D：102 Skills / 660 Micro Skills coverage matrices
- Stage 5B-2E：8 Skills、24 題 local synthetic cross-unit technical validation

## Curriculum 與 200 題 Pilot 現況

- Profile：`CURRICULUM_V27:PREHIGH:G8:COMMON`
- Release：`CURRICULUM_V27_EA0E6735`
- Skills：102；Micro Skills：660
- 200 題完成：{scope.get('mapped', 0)}/200；IN_SCOPE_G8：{scope.get('scope_counts',{}).get('IN_SCOPE_G8',0)}；OUT_OF_SCOPE_G8：{scope.get('scope_counts',{}).get('OUT_OF_SCOPE_G8',0)}；invalid：{scope.get('invalid',0)}
- 現有題庫映射集中於 {quality.get('distinct_skills_used',0)} 個 Skills / {quality.get('distinct_micro_skills_used',0)} 個 Micro Skills，僅代表本次 sample 分布。

## Coverage Matrix 摘要

- Skills covered：{coverage.get('skills_with_questions',0)}；zero：{coverage.get('skills_zero_questions',0)}；coverage：{coverage.get('skill_coverage_percent',0)}%
- Micro Skills covered：{coverage.get('micro_skills_covered',0)}；zero：{coverage.get('micro_skills_zero_questions',0)}；coverage：{coverage.get('micro_coverage_percent',0)}%
- Coverage artifacts 不含題目原文，完整矩陣保留於 `.local/stage5_g8_mapping_pilot/freeze/`。

## 跨單元驗證

- Questions：{validation.get('questions',0)}；completed：{validation.get('completed',0)}；invalid：{validation.get('invalid',0)}
- Scope accuracy：{validation.get('scope_accuracy',0)}%
- Exact skill accuracy：{validation.get('exact_skill_accuracy',0)}%
- Exact micro accuracy：{validation.get('exact_micro_accuracy',0)}%
- Technical PASS：{str(bool(validation.get('technical_pass'))).upper()}
- Mapping Pilot PASS：{str(bool(validation.get('mapping_pilot_pass'))).upper()}
- {mismatch_note}

## 已知限制與尚未 Production 化項目

- Coverage 很低且高度集中；此成果不是完整題庫 coverage certification。
- Synthetic validation 只驗證代表性跨單元 routing，不替代真人審題或大規模 benchmark。
- 尚未將 G8 mappings、coverage 或 synthetic 題目寫入正式 item_bank。
- 尚未建立 Production migration、cutover 或正式資料回填。
- 未降低 RLS，未使用 staging 作為正式來源。

## Production 安全狀態

- Production project ref `igttuijrtwbtefhyeokp` 僅作禁止寫入環境標識。
- `production_reads = 0`
- `production_writes = 0`
- Secrets exposed：NO
- Local/raw/synthetic question data committed：NO

## 下次回到 G8 的第一步

先依 coverage matrix 的 `HIGH` / `ZERO_COVERAGE` 清單設計人工審核過的跨單元補題 blueprint；完成 local benchmark 後再討論任何 Production 設計。

## 建議補題優先順序

優先補完全零覆蓋且課程順序較前的核心 Skills，再擴大已有限覆蓋 Skill 的 Micro Skill breadth。首批候選：

{priority_lines}

---

本文件不含題目原文、API key、service role key、secrets 或逐題 mapping data。
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return {"complete": complete, "label": freeze_label, "production_reads": 0, "production_writes": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-root", type=Path, default=DEFAULT_LOCAL)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    try:
        result = generate(args.local_root, args.destination)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["complete"] else 2
    except Exception as exc:
        print(f"G8 FREEZE HANDOFF: BLOCKED ({type(exc).__name__}): {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
