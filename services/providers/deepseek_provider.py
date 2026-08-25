from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Sequence

from services.ai_provider import ProviderResponse, load_minimal_secret, normalize_provider_exception, parse_json_object


class DeepSeekProvider:
    provider_name = "deepseek"

    def __init__(self, *, secret_paths: Sequence[Path], client: Any = None) -> None:
        self.model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self._secret_paths = tuple(secret_paths)
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = load_minimal_secret(("DEEPSEEK_API_KEY",), self._secret_paths)
        if not key:
            raise RuntimeError("DEEPSEEK_NOT_CONFIGURED")
        from openai import OpenAI
        self._client = OpenAI(api_key=key, base_url=self.base_url)
        return self._client

    def generate_json(self, prompt: str) -> ProviderResponse:
        started = time.perf_counter()
        try:
            response = self._get_client().chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = str(response.choices[0].message.content or "")
            usage = getattr(response, "usage", None)
            return ProviderResponse(
                provider=self.provider_name, model=self.model_name, parsed_json=parse_json_object(raw), raw_text=raw,
                latency_ms=(time.perf_counter() - started) * 1000,
                input_tokens=getattr(usage, "prompt_tokens", None), output_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )
        except Exception as exc:
            if isinstance(exc, RuntimeError) and str(exc) == "DEEPSEEK_NOT_CONFIGURED": raise
            raise normalize_provider_exception(exc) from None

    def diagnose(self) -> dict[str, Any]:
        """One models request and, only when available, one minimal chat request."""
        try:
            models = self._get_client().models.list()
        except Exception as exc:
            if isinstance(exc, RuntimeError) and str(exc) == "DEEPSEEK_NOT_CONFIGURED":
                return {"models_http": None, "authentication": "NOT_CONFIGURED", "balance": "UNKNOWN",
                        "model_available": False, "chat_completion": "NOT_RUN", "normalized_error": "AUTH"}
            error = normalize_provider_exception(exc)
            return {"models_http": error.code, "authentication": "FAIL" if error.error_type == "AUTH" else "UNKNOWN",
                    "balance": "FAIL" if error.error_type == "BALANCE" else "UNKNOWN", "model_available": False,
                    "chat_completion": "NOT_RUN", "normalized_error": error.error_type}
        model_ids = {str(getattr(item, "id", "")) for item in getattr(models, "data", models)}
        if self.model_name not in model_ids:
            return {"models_http": 200, "authentication": "PASS", "balance": "UNKNOWN",
                    "model_available": False, "chat_completion": "NOT_RUN", "normalized_error": "MODEL_UNAVAILABLE"}
        try:
            self._get_client().chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": "Return a JSON object."},
                          {"role": "user", "content": "Return {\"ok\":true}."}],
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
                max_tokens=8,
                stream=False,
            )
            return {"models_http": 200, "authentication": "PASS", "balance": "PASS",
                    "model_available": True, "chat_completion": "PASS", "normalized_error": "NONE"}
        except Exception as exc:
            error = normalize_provider_exception(exc)
            return {"models_http": 200, "authentication": "PASS",
                    "balance": "FAIL" if error.error_type == "BALANCE" else "UNKNOWN",
                    "model_available": True, "chat_completion": "FAIL", "normalized_error": error.error_type}

    def health_check(self) -> str:
        result = self.diagnose()
        if result["chat_completion"] != "PASS":
            raise ProviderCallError(str(result["normalized_error"]))
        return "DEEPSEEK_AVAILABLE"
