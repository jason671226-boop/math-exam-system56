"""MathAI AI service with automatic Gemini model discovery and safe fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import streamlit as st

try:
    from google import genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GOOGLE_GENAI_AVAILABLE = False


@dataclass
class AIServiceError(RuntimeError):
    code: str
    user_message: str
    original_message: str = ""

    def __str__(self) -> str:
        return self.user_message


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def _clean_api_key(value: str) -> str:
    value = str(value or "").strip()
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"'", '"'}
    ):
        value = value[1:-1].strip()
    return value


def _get_gemini_key() -> str:
    # 同時支援 Google 官方常用名稱與 MathAI 舊名稱。
    api_key = (
        _secret("GEMINI_API_KEY")
        or _secret("GOOGLE_API_KEY")
        or _secret("GEMINI_KEY")
        or _secret("GOOGLE_GENAI_API_KEY")
    )
    api_key = _clean_api_key(api_key)
    if not api_key:
        raise AIServiceError(
            code="MISSING_API_KEY",
            user_message=(
                "系統尚未設定 Gemini API Key。"
                "管理員請在 Streamlit Secrets 設定 "
                "GEMINI_API_KEY 或 GOOGLE_API_KEY。"
            ),
        )
    return api_key


def _classify_google_error(exc: Exception) -> AIServiceError:
    original = str(exc)
    lowered = original.lower()

    if any(x in lowered for x in (
        "401", "unauthenticated", "access_token_type_unsupported",
        "invalid authentication credentials",
    )):
        return AIServiceError(
            code="AUTHENTICATION_FAILED",
            user_message=(
                "Gemini 服務目前無法通過身分驗證。"
                "請改用人工輸入模式，並由管理員檢查 API Key。"
            ),
            original_message=original,
        )

    if any(x in lowered for x in (
        "429", "resource_exhausted", "quota", "rate limit",
    )):
        return AIServiceError(
            code="QUOTA_EXCEEDED",
            user_message="Gemini API 額度或請求頻率已達上限，請稍後再試或改用人工輸入。",
            original_message=original,
        )

    if any(x in lowered for x in (
        "403", "permission_denied", "permission denied",
    )):
        return AIServiceError(
            code="PERMISSION_DENIED",
            user_message="Gemini API Key 已被辨識，但目前沒有足夠的 API 權限。",
            original_message=original,
        )

    if any(x in lowered for x in (
        "404", "not found", "model_not_found", "is not found for api version",
    )):
        return AIServiceError(
            code="MODEL_NOT_FOUND",
            user_message="目前設定的 Gemini 模型不存在或不支援此呼叫方式。",
            original_message=original,
        )

    if any(x in lowered for x in (
        "timeout", "timed out", "deadline exceeded",
    )):
        return AIServiceError(
            code="TIMEOUT",
            user_message="AI 服務等待時間過長，請稍後再試或改用人工輸入。",
            original_message=original,
        )

    return AIServiceError(
        code="UNKNOWN_AI_ERROR",
        user_message="AI 服務暫時無法完成請求，請改用人工輸入模式。",
        original_message=original,
    )


@st.cache_resource
def _get_gemini_client(api_key: str):
    if not GOOGLE_GENAI_AVAILABLE or genai is None:
        raise AIServiceError(
            code="SDK_NOT_INSTALLED",
            user_message="系統沒有安裝 google-genai 套件，請先執行更新套件。",
        )
    return genai.Client(api_key=api_key)


def _normalize_model_name(name: str) -> str:
    name = str(name or "").strip()
    if name.startswith("models/"):
        return name[len("models/"):]
    return name


def _supports_generate_content(model: Any) -> bool:
    actions = getattr(model, "supported_actions", None)
    if actions is None:
        actions = getattr(model, "supported_generation_methods", None)
    if actions is None:
        # Some SDK releases omit this metadata. Keep plausible Gemini models.
        return "gemini" in str(getattr(model, "name", "")).lower()
    action_text = " ".join(str(x) for x in actions).lower()
    return "generatecontent" in action_text.replace("_", "")


def _model_score(name: str) -> tuple[int, str]:
    n = name.lower()
    # Exclude models that are clearly not general multimodal generation models.
    excluded = (
        "embedding", "imagen", "veo", "tts", "live", "aqa",
        "computer-use", "robotics", "nano-banana",
    )
    if any(x in n for x in excluded):
        return (999, n)

    # Prefer lower-cost Flash families, then stable versions, then previews.
    if "flash-lite" in n:
        rank = 0
    elif "flash" in n:
        rank = 1
    elif "pro" in n:
        rank = 3
    else:
        rank = 5

    if "preview" in n or "experimental" in n or "exp" in n:
        rank += 2
    if "latest" in n:
        rank += 1
    return (rank, n)


def list_generate_content_models() -> list[str]:
    """Return models visible to the configured key that support generateContent."""
    api_key = _get_gemini_key()
    client = _get_gemini_client(api_key)
    try:
        names: list[str] = []
        for model in client.models.list():
            raw_name = getattr(model, "name", "")
            name = _normalize_model_name(raw_name)
            if name and _supports_generate_content(model):
                names.append(name)
        return sorted(set(names), key=_model_score)
    except Exception as exc:
        raise _classify_google_error(exc) from exc


def _candidate_models(requested_model: str | None = None) -> list[str]:
    configured = _secret("GEMINI_MODEL")
    candidates: list[str] = []

    for item in (requested_model, configured):
        normalized = _normalize_model_name(item or "")
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    # Discover models from the account/key. Failure here is non-fatal; direct
    # candidates below may still work.
    try:
        for name in list_generate_content_models():
            if name not in candidates:
                candidates.append(name)
    except AIServiceError as exc:
        if exc.code in {"AUTHENTICATION_FAILED", "PERMISSION_DENIED", "QUOTA_EXCEEDED"}:
            raise

    # Last-resort aliases. They are tried only when discovery yields nothing or
    # the configured alias is unavailable.
    for name in (
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ):
        if name not in candidates:
            candidates.append(name)

    return candidates


def call_gemini_api(
    contents: Sequence[Any],
    *,
    model: str | None = None,
) -> str:
    """Call Gemini, automatically trying models available to the current key."""
    api_key = _get_gemini_key()
    client = _get_gemini_client(api_key)
    errors: list[str] = []

    for candidate in _candidate_models(model):
        try:
            response = client.models.generate_content(
                model=candidate,
                contents=list(contents),
            )
            response_text = getattr(response, "text", None)
            if response_text and str(response_text).strip():
                st.session_state["working_gemini_model"] = candidate
                return str(response_text).strip()
            errors.append(f"{candidate}: empty response")
        except Exception as exc:
            classified = _classify_google_error(exc)
            errors.append(f"{candidate}: {classified.original_message or classified.user_message}")

            # A missing model can be retried with another candidate. Authentication,
            # permissions, quota and other request failures should not be hidden by
            # trying every model.
            if classified.code == "MODEL_NOT_FOUND":
                continue
            raise classified from exc

    detail = "\n\n".join(errors[-8:])
    raise AIServiceError(
        code="NO_WORKING_MODEL",
        user_message=(
            "目前帳號沒有找到可用的 Gemini 內容生成模型。"
            "請先使用人工輸入模式。"
        ),
        original_message=detail,
    )


def get_ai_error_message(exc: Exception) -> str:
    if isinstance(exc, AIServiceError):
        return exc.user_message
    return _classify_google_error(exc).user_message


def get_ai_error_code(exc: Exception) -> str:
    if isinstance(exc, AIServiceError):
        return exc.code
    return _classify_google_error(exc).code


def get_ai_debug_message(exc: Exception) -> str:
    if isinstance(exc, AIServiceError):
        return exc.original_message or exc.user_message
    return str(exc)
