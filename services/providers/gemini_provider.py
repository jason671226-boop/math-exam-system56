from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Sequence

from services.ai_provider import ProviderResponse, load_minimal_secret, normalize_provider_exception, parse_json_object


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, *, secret_paths: Sequence[Path], client: Any = None) -> None:
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self._secret_paths = tuple(secret_paths)
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = load_minimal_secret(("GEMINI_API_KEY", "GEMINI_KEY", "GOOGLE_API_KEY"), self._secret_paths)
        if not key:
            raise RuntimeError("SECURE_GEMINI_KEY_NOT_FOUND")
        from google import genai
        self._client = genai.Client(api_key=key)
        return self._client

    def generate_json(self, prompt: str) -> ProviderResponse:
        started = time.perf_counter()
        try:
            response = self._get_client().models.generate_content(model=self.model_name, contents=prompt)
            raw = str(response.text or "")
            usage = getattr(response, "usage_metadata", None)
            return ProviderResponse(
                provider=self.provider_name, model=self.model_name, parsed_json=parse_json_object(raw), raw_text=raw,
                latency_ms=(time.perf_counter() - started) * 1000,
                input_tokens=getattr(usage, "prompt_token_count", None),
                output_tokens=getattr(usage, "candidates_token_count", None),
                total_tokens=getattr(usage, "total_token_count", None),
            )
        except Exception as exc:
            if isinstance(exc, RuntimeError) and str(exc) == "SECURE_GEMINI_KEY_NOT_FOUND": raise
            raise normalize_provider_exception(exc) from None

    def health_check(self) -> str:
        self.generate_json("Return exactly {}.")
        return "GEMINI_AVAILABLE"
