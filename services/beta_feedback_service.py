from __future__ import annotations

from dataclasses import dataclass
from typing import Any


APP_VERSION = "v0.8.7.3"
CATEGORIES = frozenset(
    {
        "GENERAL",
        "LOGIN",
        "QUESTION_OUTPUT",
        "MATH_OUTPUT",
        "DIAGNOSTIC",
        "CAMERA_UPLOAD",
        "PERSISTENCE",
        "TEACHER_FEEDBACK",
        "PARENT_REPORT",
        "CREDITS",
        "OTHER",
    }
)


class BetaFeedbackError(ValueError):
    pass


@dataclass(frozen=True)
class BetaFeedback:
    context: str
    category: str
    rating: int
    message: str
    app_version: str = APP_VERSION


def validate_feedback(feedback: BetaFeedback) -> BetaFeedback:
    context = feedback.context.strip()
    category = feedback.category.strip().upper()
    message = feedback.message.strip()
    if not context or len(context) > 100:
        raise BetaFeedbackError("invalid feedback context")
    if category not in CATEGORIES:
        raise BetaFeedbackError("invalid feedback category")
    if not 1 <= int(feedback.rating) <= 5:
        raise BetaFeedbackError("invalid feedback rating")
    if not message or len(message) > 2000:
        raise BetaFeedbackError("invalid feedback message")
    if not feedback.app_version.strip() or len(feedback.app_version.strip()) > 32:
        raise BetaFeedbackError("invalid app version")
    return BetaFeedback(
        context=context,
        category=category,
        rating=int(feedback.rating),
        message=message,
        app_version=feedback.app_version.strip(),
    )


def submit_feedback(client: Any, feedback: BetaFeedback) -> str:
    if client is None or not hasattr(client, "rpc"):
        raise BetaFeedbackError("authenticated feedback is unavailable")
    clean = validate_feedback(feedback)
    try:
        response = client.rpc(
            "mathai_private_beta_feedback_submit",
            {
                "p_context": clean.context,
                "p_category": clean.category,
                "p_rating": clean.rating,
                "p_message": clean.message,
                "p_app_version": clean.app_version,
            },
        ).execute()
    except Exception as exc:
        raise BetaFeedbackError("feedback could not be saved") from exc
    value = getattr(response, "data", None)
    feedback_id = str(value or "").strip().strip('"')
    if not feedback_id:
        raise BetaFeedbackError("feedback could not be saved")
    return feedback_id


def classify_issue(*, category: str, safe_error_code: str = "") -> str:
    category = str(category or "").strip().upper()
    code = str(safe_error_code or "").strip().upper()
    if code in {"CROSS_STUDENT_ACCESS", "SECRET_EXPOSURE", "DATA_CORRUPTION"}:
        return "P0_SECURITY" if code != "DATA_CORRUPTION" else "P0_DATA_LOSS"
    if category == "LOGIN":
        return "P1_LOGIN"
    if category == "CREDITS":
        return "P1_PAYMENT_CREDITS"
    if category == "CAMERA_UPLOAD":
        return "P1_CAMERA"
    if category == "DIAGNOSTIC":
        return "P1_DIAGNOSTIC"
    if category == "PERSISTENCE":
        return "P1_PERSISTENCE"
    if category == "MATH_OUTPUT":
        return "P2_MATH_OUTPUT"
    if category == "PARENT_REPORT":
        return "P2_REPORT"
    if category in {"QUESTION_OUTPUT", "TEACHER_FEEDBACK"}:
        return "P2_UI"
    return "P3_COSMETIC" if category == "GENERAL" else "P2_UI"
