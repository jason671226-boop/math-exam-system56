"""Focused Staging testing-auth E2E for the three allowlisted accounts.

Read-only except for the testing-challenge writes (prepare / reveal / consume).
Never prints URLs, keys, OTPs, or session tokens.
"""

from __future__ import annotations

import hashlib
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from supabase import create_client  # noqa: E402

from services.learning_runtime import resolve_authenticated_student  # noqa: E402
from services.testing_auth_service import (  # noqa: E402
    TESTING_NONCE_KEY,
    complete_testing_login,
    issue_testing_code,
)

EMAILS = (
    "jason601226@gmail.com",
    "jason621226@gmail.com",
    "jason671226@gmail.com",
)


def _load_config() -> tuple[str, str]:
    path = REPO / "app" / ".streamlit" / "secrets.toml"
    with path.open("rb") as handle:
        values = tomllib.load(handle)
    return values["SUPABASE_URL"], values["SUPABASE_KEY"]


def main() -> int:
    url, key = _load_config()
    results: dict[str, dict] = {}
    for email in EMAILS:
        client = create_client(url, key)
        state: dict = {}
        try:
            code = issue_testing_code(client, state, email=email)
            nonce = str(state.get(TESTING_NONCE_KEY, ""))
            challenge_hash = hashlib.sha256(nonce.encode("utf-8")).hexdigest()

            response, _ = complete_testing_login(
                client, state, email=email, token=code
            )
            auth_user_id = getattr(getattr(response, "user", None), "id", None)

            identity = resolve_authenticated_student(client)

            profile_rows = (client.rpc("mathai_private_profile_get").execute().data) or []
            wallet_rows = (client.rpc("mathai_private_wallet_lookup").execute().data) or []

            second_consume_blocked = False
            try:
                client.rpc(
                    "mathai_testing_auth_consume",
                    {"p_email": email, "p_challenge_hash": challenge_hash},
                ).execute()
            except Exception:
                second_consume_blocked = True

            results[email] = {
                "session": bool(auth_user_id),
                "student_id": identity.student_id,
                "profile": bool(profile_rows),
                "wallet": bool(wallet_rows),
                "second_consume_blocked": second_consume_blocked,
            }
        except Exception as exc:  # never print raw SDK text
            results[email] = {
                "error": type(exc).__name__,
                "code": getattr(exc, "code", None),
            }
        finally:
            try:
                client.auth.sign_out()
            except Exception:
                pass

    ok = True
    for email in EMAILS:
        result = results[email]
        if "error" in result:
            ok = False
            print(f"{email}: FAIL {result['error']} code={result['code']}")
            continue
        student_id = result["student_id"]
        print(
            f"{email}: session={result['session']} "
            f"student_id={student_id[:8]}... profile={result['profile']} "
            f"wallet={result['wallet']} "
            f"second_consume_blocked={result['second_consume_blocked']}"
        )
        if not all(
            (
                result["session"],
                result["profile"],
                result["wallet"],
                result["second_consume_blocked"],
            )
        ):
            ok = False
    print("STAGING AUTH E2E:", "PASS" if ok else "BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
