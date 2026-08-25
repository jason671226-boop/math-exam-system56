from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

ERROR_TYPES = {
    "AUTH", "AUTH_ERROR", "BALANCE", "BAD_REQUEST", "PARAMETER", "RATE_LIMIT",
    "QUOTA_EXHAUSTED", "SERVER", "OVERLOADED", "NETWORK_ERROR", "TIMEOUT",
    "INVALID_JSON", "MODEL_UNAVAILABLE", "CONFIGURATION_ERROR", "UNKNOWN_PROVIDER_ERROR",
}


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    parsed_json: dict[str, Any] | None
    raw_text: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    retry_count: int = 0
    request_status: str = "OK"
    error_type: str | None = None


class ProviderCallError(RuntimeError):
    def __init__(self, error_type: str, *, retry_after: float | None = None) -> None:
        if error_type not in ERROR_TYPES:
            error_type = "UNKNOWN_PROVIDER_ERROR"
        super().__init__(error_type)
        self.error_type = error_type
        self.retry_after = retry_after
        self.code = {"AUTH": 401, "AUTH_ERROR": 401, "BALANCE": 402, "BAD_REQUEST": 400,
                     "PARAMETER": 422, "RATE_LIMIT": 429, "QUOTA_EXHAUSTED": 429,
                     "SERVER": 500, "OVERLOADED": 503}.get(error_type)
        self.status = "RESOURCE_EXHAUSTED" if error_type == "QUOTA_EXHAUSTED" else None


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_json(self, prompt: str) -> ProviderResponse: ...
    def health_check(self) -> str: ...


def parse_json_object(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S).strip()
    attempts = [value]
    start, end = value.find("{"), value.rfind("}")
    if start >= 0 and end > start:
        attempts.append(value[start:end + 1])
    attempts += [re.sub(r",\s*([}\]])", r"\1", item) for item in list(attempts)]
    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise ProviderCallError("INVALID_JSON")


def load_minimal_secret(names: Sequence[str], paths: Sequence[Path]) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    allowed_names = "|".join(re.escape(name) for name in names)
    allowed = re.compile(rf'^\s*(?:{allowed_names})\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$')
    for path in paths:
        if path.is_file():
            with path.open(encoding="utf-8-sig") as handle:
                for line in handle:
                    match = allowed.match(line)
                    if match:
                        return match.group(1).strip()
    return ""


def retry_after_from_exception(exc: Exception) -> float | None:
    direct = getattr(exc, "retry_after", None)
    if direct is not None:
        try:
            return max(0.0, float(direct))
        except (TypeError, ValueError):
            pass
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    value = headers.get("Retry-After") if headers is not None and hasattr(headers, "get") else None
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalize_provider_exception(exc: Exception) -> ProviderCallError:
    if isinstance(exc, ProviderCallError):
        return exc
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    text = f"{type(exc).__name__} {exc}".lower()
    if isinstance(exc, (ImportError, ModuleNotFoundError)): kind = "CONFIGURATION_ERROR"
    elif code in (401, 403): kind = "AUTH"
    elif code == 402: kind = "BALANCE"
    elif code == 400: kind = "BAD_REQUEST"
    elif code == 422: kind = "PARAMETER"
    elif code == 429 and any(word in text for word in ("quota", "exhausted", "insufficient")): kind = "QUOTA_EXHAUSTED"
    elif code == 429: kind = "RATE_LIMIT"
    elif code == 404 and "model" in text: kind = "MODEL_UNAVAILABLE"
    elif code == 500: kind = "SERVER"
    elif code == 503: kind = "OVERLOADED"
    elif isinstance(exc, TimeoutError) or "timeout" in text: kind = "TIMEOUT"
    elif any(word in text for word in ("connection", "network", "dns")): kind = "NETWORK_ERROR"
    else: kind = "UNKNOWN_PROVIDER_ERROR"
    return ProviderCallError(kind, retry_after=retry_after_from_exception(exc))


def _default_secret_paths() -> tuple[Path, ...]:
    return (
        Path.cwd() / ".streamlit/secrets.toml",
        Path(r"C:\MathAI_G5_Pilot\.streamlit\secrets.toml"),
        Path(r"C:\MathAI_G6_Pilot\.streamlit\secrets.toml"),
        Path(r"C:\MathAI_G8_Pilot\.streamlit\secrets.toml"),
        Path(r"C:\MathAI\app\.streamlit\secrets.toml"),
    )


def get_ai_provider(*, secret_paths: Sequence[Path] | None = None, client: Any = None) -> AIProvider:
    provider = os.getenv("AI_PROVIDER", "gemini").strip().lower() or "gemini"
    paths = tuple(secret_paths or _default_secret_paths())
    if provider == "gemini":
        from services.providers.gemini_provider import GeminiProvider
        return GeminiProvider(secret_paths=paths, client=client)
    if provider == "deepseek":
        from services.providers.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(secret_paths=paths, client=client)
    raise RuntimeError("UNSUPPORTED_AI_PROVIDER")
