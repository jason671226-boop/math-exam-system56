from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.ai_provider import (
    ProviderCallError, get_ai_provider, load_minimal_secret, normalize_provider_exception,
)
from services.providers.deepseek_provider import DeepSeekProvider
from services.providers.gemini_provider import GeminiProvider


class MockCompletions:
    def __init__(self, content='{"ok": true}', error=None):
        self.content = content; self.error = error; self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error: raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        )


def deepseek(content='{"ok": true}', error=None):
    completions = MockCompletions(content, error)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return DeepSeekProvider(secret_paths=(), client=client), completions


class MockModels:
    def __init__(self, ids=("deepseek-v4-flash",), error=None):
        self.ids = ids; self.error = error; self.calls = 0
    def list(self):
        self.calls += 1
        if self.error: raise self.error
        return SimpleNamespace(data=[SimpleNamespace(id=value) for value in self.ids])


def test_deepseek_valid_json_and_metadata(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    provider, calls = deepseek()
    response = provider.generate_json("x")
    assert response.parsed_json == {"ok": True}
    assert (response.provider, response.model) == ("deepseek", "deepseek-v4-flash")
    assert (response.input_tokens, response.output_tokens, response.total_tokens) == (3, 2, 5)
    assert calls.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert calls.calls[0]["response_format"] == {"type": "json_object"}


def test_deepseek_markdown_fence_json():
    provider, _ = deepseek("```json\n{\"ok\": true}\n```")
    assert provider.generate_json("x").parsed_json["ok"] is True


def test_deepseek_malformed_json():
    provider, _ = deepseek("not-json")
    with pytest.raises(ProviderCallError, match="INVALID_JSON"):
        provider.generate_json("x")


@pytest.mark.parametrize("exc,kind", [
    (TimeoutError("timed out"), "TIMEOUT"),
    (type("Auth", (Exception,), {"status_code": 401})("denied"), "AUTH"),
    (type("Rate", (Exception,), {"status_code": 429})("rate limit"), "RATE_LIMIT"),
    (type("Quota", (Exception,), {"status_code": 429})("quota exhausted"), "QUOTA_EXHAUSTED"),
])
def test_deepseek_error_normalization(exc, kind):
    provider, _ = deepseek(error=exc)
    with pytest.raises(ProviderCallError) as caught:
        provider.generate_json("x")
    assert caught.value.error_type == kind


def test_retry_after_normalized():
    exc = type("Rate", (Exception,), {"status_code": 429})("rate limit")
    exc.response = SimpleNamespace(headers={"Retry-After": "7"})
    assert normalize_provider_exception(exc).retry_after == 7


@pytest.mark.parametrize("status,kind", [(400, "BAD_REQUEST"), (402, "BALANCE"), (422, "PARAMETER"),
                                          (500, "SERVER"), (503, "OVERLOADED")])
def test_deepseek_http_error_normalization(status, kind):
    exc = type("HttpError", (Exception,), {"status_code": status})("safe")
    assert normalize_provider_exception(exc).error_type == kind


def test_missing_provider_dependency_is_configuration_error():
    assert normalize_provider_exception(ModuleNotFoundError("missing sdk")).error_type == "CONFIGURATION_ERROR"


def test_deepseek_diagnostic_models_then_one_minimal_chat():
    provider, completions = deepseek()
    models = MockModels()
    provider._client.models = models
    result = provider.diagnose()
    assert result == {"models_http": 200, "authentication": "PASS", "balance": "PASS",
                      "model_available": True, "chat_completion": "PASS", "normalized_error": "NONE"}
    assert models.calls == 1 and len(completions.calls) == 1
    call = completions.calls[0]
    assert call["model"] == "deepseek-v4-flash" and call["max_tokens"] == 8 and call["stream"] is False


def test_deepseek_diagnostic_stops_when_model_missing():
    provider, completions = deepseek()
    provider._client.models = MockModels(ids=("deepseek-chat",))
    result = provider.diagnose()
    assert result["normalized_error"] == "MODEL_UNAVAILABLE"
    assert not completions.calls


def test_provider_selection_default_and_explicit(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    assert isinstance(get_ai_provider(secret_paths=(), client=object()), GeminiProvider)
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    assert isinstance(get_ai_provider(secret_paths=(), client=object()), DeepSeekProvider)


def test_unknown_provider_fails_closed(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "abc")
    with pytest.raises(RuntimeError, match="UNSUPPORTED_AI_PROVIDER"):
        get_ai_provider(secret_paths=())


def test_no_automatic_fallback(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    provider, _ = deepseek(error=TimeoutError("timeout"))
    with pytest.raises(ProviderCallError, match="TIMEOUT"):
        provider.generate_json("x")
    assert provider.provider_name == "deepseek"


@pytest.mark.parametrize("name", ["DEEPSEEK_API_KEY", "GEMINI_API_KEY"])
def test_secret_loader_never_logs_or_persists(name, tmp_path, capsys, monkeypatch):
    secret = "unit-test-secret-never-output"
    source = tmp_path / "secrets.toml"
    source.write_text(f'{name} = "{secret}"\nIGNORED = "private"\n', encoding="utf-8")
    monkeypatch.delenv(name, raising=False)
    assert load_minimal_secret((name,), (source,)) == secret
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert list(tmp_path.iterdir()) == [source]


def test_deepseek_missing_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider = DeepSeekProvider(secret_paths=())
    with pytest.raises(RuntimeError, match="DEEPSEEK_NOT_CONFIGURED"):
        provider.generate_json("x")


def test_checkpoint_resume_and_duplicate_provider_call(tmp_path, monkeypatch):
    import scripts.stage5_grade_foundation as engine
    from dataclasses import replace
    from services.stage5_grade_config import load_grade_config
    config = replace(load_grade_config("G5"), local_output_dir=tmp_path)
    base = tmp_path / "synthetic" / "holdout"; base.mkdir(parents=True)
    question = {"fingerprint": "fp1", "question_text": "mock", "expected_scope_status": config.out_scope_status,
                "expected_skill_id": "", "expected_micro_skill_id": "", "synthetic_validation": True}
    (base / "questions.jsonl").write_text(json.dumps(question) + "\n", encoding="utf-8")
    calls = []
    def generate(prompt, model):
        calls.append(prompt)
        return json.dumps({"scope_status": config.out_scope_status, "predicted_skill_id": "",
                           "predicted_micro_skill_id": "", "confidence": .9})
    engine.map_set(config, "holdout", generate=generate)
    engine.map_set(config, "holdout", generate=generate)
    assert len(calls) == 1


def test_duplicate_checkpoint_fails_closed(tmp_path):
    import scripts.stage5_grade_foundation as engine
    from dataclasses import replace
    from services.stage5_grade_config import load_grade_config
    config = replace(load_grade_config("G5"), local_output_dir=tmp_path)
    base = tmp_path / "synthetic" / "holdout"; base.mkdir(parents=True)
    q = {"fingerprint": "fp1", "question_text": "mock"}
    (base / "questions.jsonl").write_text(json.dumps(q) + "\n", encoding="utf-8")
    row = json.dumps({"fingerprint": "fp1"}) + "\n"
    (base / "mapping_checkpoint.jsonl").write_text(row + row, encoding="utf-8")
    with pytest.raises(RuntimeError, match="INVALID_CHECKPOINT_FINGERPRINT"):
        engine.map_set(config, "holdout", generate=lambda *_: "{}")


def test_tools_are_local_only_and_probe_does_not_retry():
    probe = Path("Stage6_AI_Provider_Probe.bat").read_text(encoding="utf-8")
    compare = Path("Stage6_Provider_AB_Compare.bat").read_text(encoding="utf-8")
    script = Path("scripts/stage6_provider_tools.py").read_text(encoding="utf-8")
    assert "stage6_provider_ab" in script and ".local" in script
    assert "health_check()" in script and "retry" not in probe.lower()
    assert "stage6_provider_tools.py compare" in compare
