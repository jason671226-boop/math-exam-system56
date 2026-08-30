"""Small, backward-compatible bridge from approved research pool to runtime.

The bridge is opt-in for production and enabled by default only for local or
staging execution. It does not write a database or alter the legacy bank.
"""
from __future__ import annotations
import json, os
from pathlib import Path
from .adapter import ApprovedPilotLoader

ROOT = Path(__file__).resolve().parents[2]
POOL_PATH = ROOT / "data/question_research/mvp_integration/approved_pilot_pool.json"

def pilot_enabled() -> bool:
    raw = os.getenv("QUESTION_BANK_PILOT_ENABLED")
    if raw is not None:
        return raw.lower() in {"1", "true", "yes", "on"}
    return os.getenv("APP_ENV", "local").lower() in {"local", "staging", "test"}

def load_pilot_pool() -> ApprovedPilotLoader:
    if not pilot_enabled() or not POOL_PATH.exists():
        return ApprovedPilotLoader(())
    data = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    return ApprovedPilotLoader(data.get("items", ()))

def runtime_pilot_status() -> dict:
    loader = load_pilot_pool()
    return {"enabled": pilot_enabled(), "count": len(loader.valid_items()), "research_only": True}
