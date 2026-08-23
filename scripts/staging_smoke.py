"""One-click authenticated RLS smoke test for the isolated MathAI Staging project."""

from __future__ import annotations

import base64
import getpass
import json
from pathlib import Path
import sys
import tomllib
from typing import Any, Callable
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


PROFILE = "STAGING_SMOKE"
STUDENT_A_EMAIL = "student-a-staging@example.com"
STUDENT_B_EMAIL = "student-b-staging@example.com"
STUDENT_A_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
STUDENT_B_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
SECRETS_PATH = Path(__file__).resolve().parents[1] / "app" / ".streamlit" / "secrets.toml"

CHECK_ORDER = (
    "Secrets safety",
    "Staging passwords",
    "Connection",
    "Student A login",
    "Student B login",
    "Student ownership",
    "Profile ownership",
    "Credits ownership",
    "Anon privileged RPC denied",
    "Beta feedback intake",
    "Diagnostic persistence",
    "Knowledge mastery",
    "Thinking evidence",
    "Teacher feedback persistence",
    "Teacher feedback reload",
    "Parent Report integration",
    "Learning Map reload",
    "Cross-session reload",
    "A/B isolation",
    "Cleanup",
)

PASS_REQUIRED = tuple(name for name in CHECK_ORDER if name != "Staging passwords")


class SmokeFailure(RuntimeError):
    """Safe control-flow error whose details are never printed."""


def _load_config(path: Path = SECRETS_PATH) -> tuple[str, str]:
    if not path.is_file():
        raise SmokeFailure("missing configuration")
    with path.open("rb") as handle:
        values = tomllib.load(handle)
    url = values.get("SUPABASE_URL")
    key = values.get("SUPABASE_KEY")
    if not isinstance(url, str) or not url.strip():
        raise SmokeFailure("missing configuration")
    if not isinstance(key, str) or not key.strip():
        raise SmokeFailure("missing configuration")
    _require_public_client_key(key.strip())
    return url.strip(), key.strip()


def _load_staging_passwords(path: Path = SECRETS_PATH) -> tuple[str | None, str | None]:
    """Read optional synthetic-user passwords without exposing their values."""
    if not path.is_file():
        return None, None
    with path.open("rb") as handle:
        values = tomllib.load(handle)

    def present(name: str) -> str | None:
        value = values.get(name)
        return value if isinstance(value, str) and value else None

    return (
        present("STAGING_STUDENT_A_PASSWORD"),
        present("STAGING_STUDENT_B_PASSWORD"),
    )


def _load_or_prompt_passwords(
    password_reader: Callable[[str], str],
    path: Path = SECRETS_PATH,
) -> tuple[str, str, str]:
    password_a, password_b = _load_staging_passwords(path)
    status = "PRESENT" if password_a and password_b else "MISSING"
    if not password_a:
        password_a = password_reader("Student A password: ")
    if not password_b:
        password_b = password_reader("Student B password: ")
    return password_a, password_b, status


def _require_public_client_key(key: str) -> None:
    """Reject known secret/service-role key formats without logging the key."""
    if key.startswith("sb_publishable_"):
        return
    if key.startswith("sb_secret_"):
        raise SmokeFailure("unsafe client key")
    parts = key.split(".")
    if len(parts) != 3:
        raise SmokeFailure("unrecognized client key")
    try:
        payload_part = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_part).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmokeFailure("unrecognized client key") from exc
    if payload.get("role") != "anon":
        raise SmokeFailure("unsafe client key")


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _safe_db_code(exc: Exception) -> str:
    for name in ("code", "status", "status_code"):
        value = getattr(exc, name, None)
        if isinstance(value, (int, str)):
            clean = str(value)
            if clean.replace("_", "").replace("-", "").isalnum():
                return clean
    return "unavailable"


def _execute(query: Any, *, table: str, operation: str) -> Any:
    """Execute a PostgREST operation with credential-safe diagnostics."""
    try:
        return query.execute()
    except Exception as exc:
        print(
            "DB diagnostic: "
            f"type={type(exc).__name__}, code={_safe_db_code(exc)}, "
            f"table={table}, operation={operation}"
        )
        raise SmokeFailure(f"{table} {operation} failed") from None


def _login(client: Any, email: str, password: str) -> str:
    try:
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as exc:
        status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
        safe_status = status if isinstance(status, int) else "unavailable"
        print(f"Auth diagnostic: {type(exc).__name__}, status={safe_status}")
        raise SmokeFailure(_safe_auth_reason(exc)) from None
    user = getattr(response, "user", None)
    user_id = getattr(user, "id", None)
    if not user_id:
        raise SmokeFailure("session not established")
    return str(user_id)


def _safe_auth_reason(exc: Exception) -> str:
    """Return a credential-safe summary; never return raw SDK exception text."""
    message = str(exc).lower()
    if "invalid login credentials" in message or "invalid credentials" in message:
        return "invalid credentials"
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if status in (400, 401):
        return "authentication rejected"
    if status == 429:
        return "authentication rate limited"
    return "authentication unavailable"


def _owned_student_id(client: Any, user_id: str, expected_student_id: str) -> str:
    response = (
        client.table("student_access")
        .select("student_id,role")
        .eq("user_id", user_id)
        .eq("role", "owner")
        .execute()
    )
    rows = _rows(response)
    if len(rows) != 1 or rows[0].get("student_id") != expected_student_id:
        raise SmokeFailure("bootstrap required")
    return expected_student_id


def _cannot_read_other_student(client: Any, other_student_id: str) -> bool:
    response = (
        client.table("student_access")
        .select("student_id")
        .eq("student_id", other_student_id)
        .execute()
    )
    return _rows(response) == []


def _cannot_read_other_student_evidence(client: Any, other_student_id: str) -> bool:
    for table in (
        "diagnostic_attempts",
        "knowledge_mastery",
        "thinking_skill_evidence",
        "teacher_feedback",
    ):
        if not _query_is_denied(
            client.table(table).select("*").eq("student_id", other_student_id)
        ):
            return False
    return True


def _query_is_denied(query: Any) -> bool:
    try:
        return _rows(query.execute()) == []
    except Exception:
        return True


def _rpc_is_denied(client: Any, name: str, payload: dict[str, Any] | None = None) -> bool:
    try:
        client.rpc(name, payload or {}).execute()
    except Exception:
        return True
    return False


def _profile_ownership_round_trip(
    client_a: Any,
    client_b: Any,
    student_a_id: str,
    student_b_id: str,
) -> bool:
    payload = {
        "p_identity_locked": False,
        "p_locked_last_name": "S",
        "p_locked_first_name": "Student A",
        "p_city": "",
        "p_district": "",
        "p_school": "MathAI Staging",
        "p_grade": "5年級(小五)",
        "p_version": "康軒版",
        "p_traits": [],
        "p_interests": [],
        "p_discovery_source": "",
        "p_source_detail": "",
        "p_source_reward_status": "none",
        "p_referral_eligible_override": False,
        "p_change_year": 2026,
        "p_change_count": 0,
    }
    if not bool(client_a.rpc("mathai_private_profile_save", payload).execute().data):
        return False
    own_rows = _rows(client_a.rpc("mathai_private_profile_get").execute())
    if len(own_rows) != 1 or own_rows[0].get("locked_first_name") != "Student A":
        return False
    return all(
        (
            _query_is_denied(
                client_a.table("student_profile_controls")
                .select("student_id")
                .eq("student_id", student_b_id)
            ),
            _query_is_denied(
                client_b.table("student_profile_controls")
                .select("student_id")
                .eq("student_id", student_a_id)
            ),
        )
    )


def _credits_ownership_round_trip(
    client_a: Any,
    client_b: Any,
    student_a_id: str,
    student_b_id: str,
) -> bool:
    first = _rows(client_a.rpc("mathai_private_wallet_bootstrap").execute())
    second = _rows(client_a.rpc("mathai_private_wallet_bootstrap").execute())
    b_wallet = _rows(client_b.rpc("mathai_private_wallet_bootstrap").execute())
    if len(first) != 1 or len(second) != 1 or len(b_wallet) != 1:
        return False
    if int(first[0]["credits"]) != int(second[0]["credits"]):
        return False
    debit_payload = {
        "p_amount": 1,
        "p_reason": "diagnostic_practice",
        "p_reference_id": "STAGING_SMOKE_SECURITY_DEBIT_V1",
    }
    debit_first = _rows(client_a.rpc("mathai_private_wallet_debit", debit_payload).execute())
    debit_second = _rows(client_a.rpc("mathai_private_wallet_debit", debit_payload).execute())
    if len(debit_first) != 1 or len(debit_second) != 1:
        return False
    if debit_first[0].get("new_balance") != debit_second[0].get("new_balance"):
        return False
    return all(
        (
            _query_is_denied(
                client_a.table("member_wallets")
                .select("student_id,credits")
                .eq("student_id", student_b_id)
            ),
            _query_is_denied(
                client_b.table("member_wallets")
                .select("student_id,credits")
                .eq("student_id", student_a_id)
            ),
            _rpc_is_denied(
                client_a,
                "mathai_private_wallet_debit",
                {"p_amount": -100, "p_reason": "diagnostic_practice", "p_reference_id": "FORGED"},
            ),
        )
    )


def _anon_attack_surface_is_denied(anon_client: Any) -> bool:
    sensitive_tables = (
        "student_access",
        "diagnostic_attempts",
        "knowledge_mastery",
        "thinking_skill_evidence",
        "teacher_feedback",
        "student_profile_controls",
        "member_wallets",
    )
    tables_denied = all(
        _query_is_denied(anon_client.table(table).select("*"))
        for table in sensitive_tables
    )
    rpcs_denied = all(
        _rpc_is_denied(anon_client, name)
        for name in (
            "mathai_private_profile_get",
            "mathai_private_wallet_lookup",
            "mathai_private_wallet_bootstrap",
        )
    )
    feedback_denied = _rpc_is_denied(
        anon_client,
        "mathai_private_beta_feedback_submit",
        {
            "p_context": "STAGING_SMOKE_ANON",
            "p_category": "GENERAL",
            "p_rating": 1,
            "p_message": "denied",
            "p_app_version": "v0.8.7.1",
        },
    )
    return tables_denied and rpcs_denied and feedback_denied


def _beta_feedback_round_trip(client_a: Any, client_b: Any) -> bool:
    payload = {
        "p_category": "GENERAL",
        "p_rating": 5,
        "p_message": "Automated safe feedback validation",
        "p_app_version": "v0.8.7.1",
    }
    a = client_a.rpc(
        "mathai_private_beta_feedback_submit",
        {**payload, "p_context": "STAGING_SMOKE_A"},
    ).execute()
    b = client_b.rpc(
        "mathai_private_beta_feedback_submit",
        {**payload, "p_context": "STAGING_SMOKE_B"},
    ).execute()
    return bool(getattr(a, "data", None) and getattr(b, "data", None)) and all(
        (
            _query_is_denied(client_a.table("beta_feedback").select("*")),
            _query_is_denied(client_b.table("beta_feedback").select("*")),
        )
    )


def _upsert_knowledge(client: Any, student_id: str, score: int) -> None:
    client.table("knowledge_mastery").upsert(
        {
            "student_id": student_id,
            "profile_id": PROFILE,
            "knowledge_id": "STAGING-SMOKE-KNOWLEDGE",
            "mastery_status": "learning",
            "mastery_score": score,
            "confidence": 0.5,
            "evidence_count": 2,
            "weighted_credit": 1,
            "metadata": {
                "smoke": True,
                "state": {
                    "status": "learning",
                    "score_numeric": score,
                    "confidence": 0.5,
                    "evidence_count": 2,
                    "weighted_points": 1,
                    "total_weight": 2,
                },
            },
        },
        on_conflict="student_id,profile_id,knowledge_id",
    ).execute()


def _knowledge_score(client: Any, student_id: str) -> float:
    response = (
        client.table("knowledge_mastery")
        .select("mastery_score")
        .eq("student_id", student_id)
        .eq("profile_id", PROFILE)
        .eq("knowledge_id", "STAGING-SMOKE-KNOWLEDGE")
        .execute()
    )
    rows = _rows(response)
    if len(rows) != 1:
        raise SmokeFailure("mastery round trip failed")
    return float(rows[0]["mastery_score"])


def _cross_write_is_denied(
    actor_client: Any,
    owner_client: Any,
    other_student_id: str,
    expected_score: int,
) -> bool:
    insert_denied = False
    try:
        actor_client.table("knowledge_mastery").insert(
            {
                "student_id": other_student_id,
                "profile_id": PROFILE,
                "knowledge_id": "STAGING-SMOKE-UNAUTHORIZED",
                "mastery_status": "learning",
                "mastery_score": 99,
                "confidence": 0.5,
                "evidence_count": 1,
                "weighted_credit": 1,
                "metadata": {"smoke": True, "answers": {}},
            }
        ).execute()
    except Exception:  # Supabase/PostgREST exception details are deliberately hidden.
        insert_denied = True

    try:
        actor_client.table("knowledge_mastery").update({"mastery_score": 99}).eq(
            "student_id", other_student_id
        ).eq("profile_id", PROFILE).eq(
            "knowledge_id", "STAGING-SMOKE-KNOWLEDGE"
        ).execute()
    except Exception:
        pass

    unauthorized = (
        owner_client.table("knowledge_mastery")
        .select("knowledge_id")
        .eq("student_id", other_student_id)
        .eq("profile_id", PROFILE)
        .eq("knowledge_id", "STAGING-SMOKE-UNAUTHORIZED")
        .execute()
    )
    return (
        insert_denied
        and _rows(unauthorized) == []
        and _knowledge_score(owner_client, other_student_id) == float(expected_score)
    )


def _diagnostic_round_trip(client: Any, student_id: str) -> tuple[str, str]:
    attempt_key = str(uuid4())
    response = _execute(
        client.table("diagnostic_attempts").upsert(
            {
                "student_id": student_id,
                "attempt_key": attempt_key,
                "profile_id": PROFILE,
                "source_type": "diagnostic",
                "completed_at": "2026-01-01T00:00:00+00:00",
                "metadata": {"smoke": True},
            },
            on_conflict="student_id,attempt_key",
        ),
        table="diagnostic_attempts",
        operation="upsert",
    )
    rows = _rows(response)
    if not rows or not rows[0].get("id"):
        rows = _rows(
            _execute(
                client.table("diagnostic_attempts")
                .select("id,attempt_key")
                .eq("student_id", student_id)
                .eq("attempt_key", attempt_key),
                table="diagnostic_attempts",
                operation="select",
            )
        )
    if len(rows) != 1 or rows[0].get("attempt_key") not in (None, attempt_key):
        raise SmokeFailure("diagnostic round trip failed")
    attempt_id = str(rows[0]["id"])

    _execute(
        client.table("diagnostic_item_results").upsert(
            {
                "attempt_id": attempt_id,
                "question_id": "STAGING-SMOKE-ITEM",
                "credit": 0.5,
                "source_type": "diagnostic",
                "answer_payload": {"answer": "synthetic"},
                "evidence_payload": [{"smoke": True}],
            },
            on_conflict="attempt_id,question_id",
        ),
        table="diagnostic_item_results",
        operation="upsert",
    )
    item_rows = _rows(
        _execute(
            client.table("diagnostic_item_results")
            .select("question_id,credit")
            .eq("attempt_id", attempt_id)
            .eq("question_id", "STAGING-SMOKE-ITEM"),
            table="diagnostic_item_results",
            operation="select",
        )
    )
    if len(item_rows) != 1 or float(item_rows[0]["credit"]) != 0.5:
        raise SmokeFailure("item round trip failed")
    return attempt_id, attempt_key


def _thinking_round_trip(client: Any, student_id: str) -> None:
    client.table("thinking_skill_evidence").upsert(
        {
            "student_id": student_id,
            "profile_id": PROFILE,
            "thinking_skill_id": "STAGING-SMOKE-THINKING",
            "score": 60,
            "confidence": 0.5,
            "evidence_count": 2,
            "metadata": {
                "smoke": True,
                "state": {
                    "status": "learning",
                    "score_numeric": 60,
                    "confidence": 0.5,
                    "evidence_count": 2,
                },
            },
        },
        on_conflict="student_id,profile_id,thinking_skill_id",
    ).execute()
    rows = _rows(
        client.table("thinking_skill_evidence")
        .select("score")
        .eq("student_id", student_id)
        .eq("profile_id", PROFILE)
        .eq("thinking_skill_id", "STAGING-SMOKE-THINKING")
        .execute()
    )
    if len(rows) != 1 or float(rows[0]["score"]) != 60:
        raise SmokeFailure("thinking round trip failed")


def _teacher_feedback_round_trip(
    client: Any,
    student_id: str,
    user_id: str,
) -> str:
    response = _execute(
        client.table("teacher_feedback").insert(
            {
                "student_id": student_id,
                "recorded_by": user_id,
                "profile_id": PROFILE,
                "scope_type": "overall",
                "feedback_text": "Staging smoke teacher observation",
                "recommendation": "Staging smoke next action",
            }
        ),
        table="teacher_feedback",
        operation="insert",
    )
    rows = _rows(response)
    if len(rows) != 1 or not rows[0].get("id"):
        raise SmokeFailure("teacher feedback write was not confirmed")
    feedback_id = str(rows[0]["id"])
    reloaded = _rows(
        _execute(
            client.table("teacher_feedback")
            .select("id,student_id,recorded_by,profile_id,scope_type,feedback_text")
            .eq("id", feedback_id)
            .eq("student_id", student_id)
            .eq("profile_id", PROFILE),
            table="teacher_feedback",
            operation="select",
        )
    )
    if len(reloaded) != 1 or reloaded[0].get("recorded_by") != user_id:
        raise SmokeFailure("teacher feedback round trip failed")
    return feedback_id


def _teacher_feedback_reloads(client: Any, student_id: str, feedback_id: str) -> bool:
    rows = _rows(
        _execute(
            client.table("teacher_feedback")
            .select("id")
            .eq("id", feedback_id)
            .eq("student_id", student_id)
            .eq("profile_id", PROFILE),
            table="teacher_feedback",
            operation="reload select",
        )
    )
    return len(rows) == 1


def _teacher_feedback_cross_write_denied(
    actor_client: Any,
    owner_client: Any,
    actor_user_id: str,
    other_student_id: str,
) -> bool:
    marker = f"STAGING-SMOKE-UNAUTHORIZED-{uuid4()}"
    denied = False
    try:
        actor_client.table("teacher_feedback").insert(
            {
                "student_id": other_student_id,
                "recorded_by": actor_user_id,
                "profile_id": PROFILE,
                "scope_type": "overall",
                "feedback_text": marker,
            }
        ).execute()
    except Exception:
        denied = True
    visible = _rows(
        owner_client.table("teacher_feedback")
        .select("id")
        .eq("student_id", other_student_id)
        .eq("profile_id", PROFILE)
        .eq("feedback_text", marker)
        .execute()
    )
    return denied and visible == []


def _parent_report_reads_feedback(client: Any, student_id: str) -> bool:
    from app.services.evidence_parent_report_service import build_parent_report
    from app.services.mastery_repository import SupabaseMasteryRepository
    from app.services.teacher_feedback_service import SupabaseTeacherFeedbackRepository

    try:
        learning = SupabaseMasteryRepository(client)
        attempts = learning.load_diagnostic_history(student_id, PROFILE)
        knowledge = learning.load_latest_knowledge_mastery(student_id, PROFILE)
        thinking = learning.load_latest_thinking_skill_summary(student_id, PROFILE)
        feedback = SupabaseTeacherFeedbackRepository(client).list_for_student(
            student_id,
            profile_id=PROFILE,
        )
        report = build_parent_report(
            student_id=student_id,
            profile=PROFILE,
            diagnostic_attempts=attempts,
            knowledge=knowledge,
            thinking=thinking,
            teacher_feedback=feedback,
        )
        observed = report.teacher_observations["overall"]
        ok = all(
            (
                report.diagnostic_summary["available"],
                report.diagnostic_summary["question_count"] == 1,
                len(report.knowledge_priorities) == 1,
                len(report.thinking_priorities) == 1,
                len(feedback) == 1,
                len(observed) == 1,
                bool(report.recommendations),
            )
        )
        if not ok:
            print(
                "Integration diagnostic: type=VerificationFailure, "
                f"component=parent_report, attempts={len(attempts)}, "
                f"knowledge={len(knowledge)}, thinking={len(thinking)}, "
                f"feedback={len(feedback)}, observed={len(observed)}"
            )
        return ok
    except Exception as exc:
        print(
            "Integration diagnostic: "
            f"type={type(exc).__name__}, component=parent_report, operation=build"
        )
        raise SmokeFailure("parent report integration failed") from None


def _learning_state_reloads(client: Any, student_id: str) -> bool:
    """Read the persisted inputs used by the Learning Map without bypassing RLS."""
    mastery = _rows(
        client.table("knowledge_mastery")
        .select("knowledge_id,mastery_score,evidence_count")
        .eq("student_id", student_id)
        .eq("profile_id", PROFILE)
        .execute()
    )
    thinking = _rows(
        client.table("thinking_skill_evidence")
        .select("thinking_skill_id,score,evidence_count")
        .eq("student_id", student_id)
        .eq("profile_id", PROFILE)
        .execute()
    )
    attempts = _rows(
        client.table("diagnostic_attempts")
        .select("id,attempt_key")
        .eq("student_id", student_id)
        .eq("profile_id", PROFILE)
        .execute()
    )
    return len(mastery) == 1 and len(thinking) == 1 and len(attempts) == 1


def _cleanup(client: Any, student_id: str) -> bool:
    _execute(
        client.table("teacher_feedback").delete().eq("student_id", student_id).eq(
            "profile_id", PROFILE
        ),
        table="teacher_feedback",
        operation="delete",
    )
    for table in (
        "diagnostic_attempts",
        "knowledge_mastery",
        "thinking_skill_evidence",
    ):
        _execute(
            client.table(table).delete().eq("student_id", student_id).eq(
                "profile_id", PROFILE
            ),
            table=table,
            operation="delete",
        )

    attempts = _rows(
        _execute(
            client.table("diagnostic_attempts").select("id").eq(
                "student_id", student_id
            ).eq("profile_id", PROFILE),
            table="diagnostic_attempts",
            operation="cleanup verify",
        )
    )
    knowledge = _rows(
        _execute(
            client.table("knowledge_mastery").select("knowledge_id").eq(
                "student_id", student_id
            ).eq("profile_id", PROFILE),
            table="knowledge_mastery",
            operation="cleanup verify",
        )
    )
    thinking = _rows(
        _execute(
            client.table("thinking_skill_evidence").select("thinking_skill_id").eq(
                "student_id", student_id
            ).eq("profile_id", PROFILE),
            table="thinking_skill_evidence",
            operation="cleanup verify",
        )
    )
    teacher = _rows(
        _execute(
            client.table("teacher_feedback").select("id").eq(
                "student_id", student_id
            ).eq("profile_id", PROFILE),
            table="teacher_feedback",
            operation="cleanup verify",
        )
    )
    remaining = (
        ("diagnostic_attempts", attempts),
        ("knowledge_mastery", knowledge),
        ("thinking_skill_evidence", thinking),
        ("teacher_feedback", teacher),
    )
    for table, rows in remaining:
        if rows:
            print(
                "DB diagnostic: type=VerificationFailure, code=unexpected_rows, "
                f"table={table}, operation=cleanup verify"
            )
            return False
    return True


def _print_report(checks: dict[str, bool | str], reasons: dict[str, str]) -> None:
    print("\nMathAI Staging Smoke")
    print("====================")
    for name in CHECK_ORDER:
        dots = "." * max(1, 28 - len(name))
        value = checks.get(name, False)
        status = value if isinstance(value, str) else "PASS" if value else "FAIL"
        print(f"{name} {dots} {status}")
        if status == "FAIL" and name in reasons:
            print(f"Reason: {reasons[name]}")
    passed = all(checks.get(name, False) is True for name in PASS_REQUIRED)
    print(f"\nRESULT: {'PASS' if passed else 'FAIL'}")


def run_smoke(
    client_factory: Callable[[str, str], Any],
    password_reader: Callable[[str], str] = getpass.getpass,
) -> bool:
    checks: dict[str, bool | str] = {}
    reasons: dict[str, str] = {}
    client_a = None
    client_b = None
    anon_client = None
    reload_client = None
    student_a_id = None
    student_b_id = None
    password_a = ""
    password_b = ""
    try:
        url, key = _load_config()
        checks["Secrets safety"] = True
        password_a, password_b, password_status = _load_or_prompt_passwords(
            password_reader
        )
        checks["Staging passwords"] = password_status
        client_a = client_factory(url, key)
        client_b = client_factory(url, key)
        anon_client = client_factory(url, key)
        checks["Connection"] = True
        try:
            user_a_id = _login(client_a, STUDENT_A_EMAIL, password_a)
            checks["Student A login"] = True
        except SmokeFailure as exc:
            reasons["Student A login"] = str(exc)
            raise
        try:
            user_b_id = _login(client_b, STUDENT_B_EMAIL, password_b)
            checks["Student B login"] = True
        except SmokeFailure as exc:
            reasons["Student B login"] = str(exc)
            raise

        try:
            student_a_id = _owned_student_id(client_a, user_a_id, STUDENT_A_ID)
            student_b_id = _owned_student_id(client_b, user_b_id, STUDENT_B_ID)
            checks["Student ownership"] = True
        except SmokeFailure as exc:
            reasons["Student ownership"] = str(exc)
            raise
        a_cannot_read_b = _cannot_read_other_student(client_a, student_b_id)
        b_cannot_read_a = _cannot_read_other_student(client_b, student_a_id)
        checks["Profile ownership"] = _profile_ownership_round_trip(
            client_a, client_b, student_a_id, student_b_id
        )
        checks["Credits ownership"] = _credits_ownership_round_trip(
            client_a, client_b, student_a_id, student_b_id
        )
        checks["Anon privileged RPC denied"] = _anon_attack_surface_is_denied(
            anon_client
        )
        checks["Beta feedback intake"] = _beta_feedback_round_trip(client_a, client_b)

        # Remove prior interrupted smoke rows before writing a deterministic new set.
        if not _cleanup(client_a, student_a_id) or not _cleanup(client_b, student_b_id):
            reasons["Diagnostic persistence"] = "pre-cleanup failed"
            raise SmokeFailure("pre-cleanup failed")

        try:
            attempt_id, _ = _diagnostic_round_trip(client_a, student_a_id)
            attempt_b_id, _ = _diagnostic_round_trip(client_b, student_b_id)
            checks["Diagnostic persistence"] = bool(attempt_id and attempt_b_id)
        except SmokeFailure as exc:
            reasons["Diagnostic persistence"] = str(exc)
            raise

        _upsert_knowledge(client_a, student_a_id, 61)
        _upsert_knowledge(client_b, student_b_id, 62)
        checks["Knowledge mastery"] = _knowledge_score(client_a, student_a_id) == 61.0
        a_cannot_write_b = _cross_write_is_denied(
            client_a, client_b, student_b_id, 62
        )
        b_cannot_write_a = _cross_write_is_denied(
            client_b, client_a, student_a_id, 61
        )
        checks["A/B isolation"] = all(
            (a_cannot_read_b, b_cannot_read_a, a_cannot_write_b, b_cannot_write_a)
        )

        _thinking_round_trip(client_a, student_a_id)
        _thinking_round_trip(client_b, student_b_id)
        checks["Thinking evidence"] = True
        feedback_a_id = _teacher_feedback_round_trip(
            client_a, student_a_id, user_a_id
        )
        feedback_b_id = _teacher_feedback_round_trip(
            client_b, student_b_id, user_b_id
        )
        checks["Teacher feedback persistence"] = True
        try:
            a_cannot_read_b_feedback = not _teacher_feedback_reloads(
                client_a, student_b_id, feedback_b_id
            )
            b_cannot_read_a_feedback = not _teacher_feedback_reloads(
                client_b, student_a_id, feedback_a_id
            )
            a_cannot_write_b_feedback = _teacher_feedback_cross_write_denied(
                client_a, client_b, user_a_id, student_b_id
            )
            b_cannot_write_a_feedback = _teacher_feedback_cross_write_denied(
                client_b, client_a, user_b_id, student_a_id
            )
            checks["Parent Report integration"] = _parent_report_reads_feedback(
                client_a, student_a_id
            )
        except SmokeFailure:
            raise
        except Exception as exc:
            print(
                "Integration diagnostic: "
                f"type={type(exc).__name__}, component=teacher_isolation, operation=verify"
            )
            raise SmokeFailure("teacher isolation verification failed") from None
        checks["Learning Map reload"] = _learning_state_reloads(client_a, student_a_id)

        # A fresh SDK client proves that persisted learning state survives an
        # application/session restart and remains protected by authenticated RLS.
        reload_client = client_factory(url, key)
        reload_user_id = _login(reload_client, STUDENT_A_EMAIL, password_a)
        reload_student_id = _owned_student_id(
            reload_client, reload_user_id, STUDENT_A_ID
        )
        checks["Cross-session reload"] = _learning_state_reloads(
            reload_client, reload_student_id
        )
        checks["Teacher feedback reload"] = _teacher_feedback_reloads(
            reload_client, reload_student_id, feedback_a_id
        )
        checks["A/B isolation"] = checks["A/B isolation"] and all(
            (
                _cannot_read_other_student_evidence(client_a, student_b_id),
                _cannot_read_other_student_evidence(client_b, student_a_id),
                a_cannot_read_b_feedback,
                b_cannot_read_a_feedback,
                a_cannot_write_b_feedback,
                b_cannot_write_a_feedback,
            )
        )
    except SmokeFailure:
        pass
    except Exception:
        # Never print exception text: SDK/network errors can embed request metadata.
        pass
    finally:
        password_a = ""
        password_b = ""
        cleanup_ok = True
        for client, student_id in ((client_a, student_a_id), (client_b, student_b_id)):
            if client is not None and student_id:
                try:
                    cleanup_ok = _cleanup(client, student_id) and cleanup_ok
                except Exception:
                    cleanup_ok = False
        for client in (client_a, client_b):
            if client is not None:
                try:
                    client.rpc("mathai_staging_cleanup_beta_feedback").execute()
                except Exception:
                    cleanup_ok = False
        checks["Cleanup"] = cleanup_ok and bool(student_a_id) and bool(student_b_id)
        for client in (client_a, client_b, reload_client, anon_client):
            if client is not None:
                try:
                    client.auth.sign_out()
                except Exception:
                    pass

    _print_report(checks, reasons)
    return all(checks.get(name, False) is True for name in PASS_REQUIRED)


def main() -> int:
    if len(sys.argv) != 1:
        print("Passwords and options are not accepted on the command line.")
        return 2
    try:
        from supabase import create_client
    except ImportError:
        print("Supabase client dependency is unavailable.")
        return 2
    return 0 if run_smoke(create_client) else 1


if __name__ == "__main__":
    raise SystemExit(main())
