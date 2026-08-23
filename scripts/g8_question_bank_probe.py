"""Credential-safe read-only probe for the existing Staging question-bank tables."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.staging_smoke import SmokeFailure, _load_config, _safe_db_code


TABLES = (
    "question_bank",
    "question_sources",
    "question_bank_routes",
    "question_ingestion_runs",
)


def main() -> int:
    try:
        from supabase import create_client

        url, key = _load_config()
        client = create_client(url, key)
    except (ImportError, SmokeFailure):
        print("STAGING QUESTION BANK PROBE: BLOCKED (safe configuration unavailable)")
        return 2

    failed = False
    for table in TABLES:
        try:
            response = client.table(table).select("*").limit(1).execute()
            rows = response.data if isinstance(response.data, list) else []
            columns = sorted(rows[0]) if rows else []
            print(f"{table}: REACHABLE rows_returned={len(rows)} columns={','.join(columns) or 'RLS_OR_EMPTY'}")
        except Exception as exc:  # diagnostics deliberately exclude server messages
            failed = True
            print(f"{table}: BLOCKED type={type(exc).__name__} code={_safe_db_code(exc)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
