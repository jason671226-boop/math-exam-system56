"""Deterministic Phase 3H lock/schema regression; never calls an AI provider."""
import json
from pathlib import Path
LOCK=Path(r"C:\MathAI\data\question_research\phase_3h8i\phase3h8i_final_locked_summary.json")
SOLVER=Path(r"C:\MathAI\data\question_research\phase_3h8h\phase3h8h_frozen_derived_results.json")
if not LOCK.exists() or not SOLVER.exists(): raise SystemExit("Phase 3H locked artifacts missing")
obj=json.loads(LOCK.read_text(encoding="utf-8")); rows=json.loads(SOLVER.read_text(encoding="utf-8"))
assert obj["FINAL_30_CALIBRATION_LOCK"] == "PASS"
assert obj["TOTAL_CASES"] == 30 and obj["GOLD_COMPARABLE"] == 30
assert obj["TOTAL_MATCHES"] == 30 and obj["MISMATCHES"] == 0
for row in rows:
    assert not any(k in row for k in ("official_answer","official_answer_value","correct_option","answer_key","gold"))
print(json.dumps({"locked":True,"cases":30,"schema_compatible":True,"gold_in_solver_schema":False,"external_ai_calls":0}))
