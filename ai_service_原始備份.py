"""
MathAI AI 服務模組

目前功能：
1. 集中管理 Gemini API 呼叫。
2. 將 Google API 的技術錯誤轉換成容易理解的訊息。
3. 發生認證、額度或模型錯誤時，由呼叫端決定是否切換人工輸入。

安全原則：
- API Key 只從 Streamlit Secrets 讀取。
- 不在本檔案寫死任何 API Key。
- 不輸出完整 API Key。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import streamlit as st

try:
    from google import genai

    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GOOGLE_GENAI_AVAILABLE = False


@dataclass
class AIServiceError(RuntimeError):
    """統一的 AI 服務錯誤。"""

    code: str
    user_message: str
    original_message: str = ""

    def __str__(self) -> str:
        return self.user_message


def _get_gemini_key() -> str:
    """
    從 Streamlit Secrets 讀取 Gemini Key。

    支援目前專案使用的 GEMINI_KEY，
    也相容 GEMINI_API_KEY 名稱。
    """
    api_key = str(
        st.secrets.get(
            "GEMINI_KEY",
            st.secrets.get("GEMINI_API_KEY", ""),
        )
    ).strip()

    if not api_key:
        raise AIServiceError(
            code="MISSING_API_KEY",
            user_message="系統尚未設定 Gemini API Key。",
        )

    return api_key


def _classify_google_error(exc: Exception) -> AIServiceError:
    """將 Google API 錯誤分類成系統可處理的錯誤。"""
    original = str(exc)
    lowered = original.lower()

    if (
        "401" in lowered
        or "unauthenticated" in lowered
        or "access_token_type_unsupported" in lowered
        or "invalid authentication credentials" in lowered
    ):
        return AIServiceError(
            code="AUTHENTICATION_FAILED",
            user_message=(
                "Gemini 圖片辨識服務目前無法通過身分驗證。"
                "這不是圖片格式問題，也不是額度不足；"
                "請先改用人工輸入錯題文字。"
            ),
            original_message=original,
        )

    if (
        "429" in lowered
        or "resource_exhausted" in lowered
        or "quota" in lowered
        or "rate limit" in lowered
    ):
        return AIServiceError(
            code="QUOTA_EXCEEDED",
            user_message=(
                "Gemini API 的使用額度或請求頻率已達上限，"
                "請稍後再試，或先使用人工輸入模式。"
            ),
            original_message=original,
        )

    if (
        "403" in lowered
        or "permission_denied" in lowered
        or "permission denied" in lowered
    ):
        return AIServiceError(
            code="PERMISSION_DENIED",
            user_message=(
                "Gemini API Key 已被辨識，但目前沒有足夠的 API 使用權限。"
            ),
            original_message=original,
        )

    if (
        "404" in lowered
        or "not found" in lowered
        or "model_not_found" in lowered
    ):
        return AIServiceError(
            code="MODEL_NOT_FOUND",
            user_message=(
                "目前設定的 Gemini 模型不存在或暫時無法使用。"
            ),
            original_message=original,
        )

    if (
        "timeout" in lowered
        or "timed out" in lowered
        or "deadline exceeded" in lowered
    ):
        return AIServiceError(
            code="TIMEOUT",
            user_message=(
                "AI 圖片辨識等待時間過長，請稍後重試，"
                "或先使用人工輸入模式。"
            ),
            original_message=original,
        )

    return AIServiceError(
        code="UNKNOWN_AI_ERROR",
        user_message="AI 服務暫時無法完成請求，請改用人工輸入模式。",
        original_message=original,
    )


@st.cache_resource
def _get_gemini_client(api_key: str):
    """建立並快取 Gemini Client。"""
    if not GOOGLE_GENAI_AVAILABLE or genai is None:
        raise AIServiceError(
            code="SDK_NOT_INSTALLED",
            user_message=(
                "系統沒有安裝 google-genai 套件，"
                "請先執行更新套件。"
            ),
        )

    return genai.Client(api_key=api_key)


def call_gemini_api(
    contents: Sequence[Any],
    *,
    model: str = "gemini-2.5-flash",
) -> str:
    """
    呼叫 Gemini API。

    Args:
        contents:
            傳給 Gemini 的文字與圖片內容。
        model:
            Gemini 模型名稱。

    Returns:
        Gemini 回傳的文字。

    Raises:
        AIServiceError:
            認證、額度、權限、模型或其他 API 錯誤。
    """
    api_key = _get_gemini_key()

    try:
        client = _get_gemini_client(api_key)

        response = client.models.generate_content(
            model=model,
            contents=list(contents),
        )

        response_text = getattr(response, "text", None)

        if not response_text or not str(response_text).strip():
            raise AIServiceError(
                code="EMPTY_RESPONSE",
                user_message="AI 沒有回傳有效內容，請重新嘗試。",
            )

        return str(response_text).strip()

    except AIServiceError:
        raise

    except Exception as exc:
        raise _classify_google_error(exc) from exc


def get_ai_error_message(exc: Exception) -> str:
    """取得適合顯示給使用者看的錯誤訊息。"""
    if isinstance(exc, AIServiceError):
        return exc.user_message

    return _classify_google_error(exc).user_message


def get_ai_error_code(exc: Exception) -> str:
    """取得系統可判斷的錯誤代碼。"""
    if isinstance(exc, AIServiceError):
        return exc.code

    return _classify_google_error(exc).code


def get_ai_debug_message(exc: Exception) -> str:
    """
    取得管理員除錯資訊。

    正式環境不要直接顯示給一般學生。
    """
    if isinstance(exc, AIServiceError):
        return exc.original_message or exc.user_message

    return str(exc)