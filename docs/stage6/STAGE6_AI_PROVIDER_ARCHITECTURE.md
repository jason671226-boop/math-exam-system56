# Stage 6 AI Provider Architecture

Stage 6 adds a small provider boundary without redesigning the frozen Stage 5 Foundation engine. `AI_PROVIDER` accepts `gemini` or `deepseek`; an unset value remains `gemini`. Unknown values fail closed with `UNSUPPORTED_AI_PROVIDER`. Automatic fallback is disabled: a selected provider failure is never silently routed to another provider.

## Interface and implementations

The shared interface exposes `provider_name`, `model_name`, `generate_json(...)`, and `health_check()`. It returns normalized metadata: provider, model, parsed JSON, runtime-only raw text, latency, input/output/total tokens, retry count, request status, and normalized error type. The mapping engine calls this interface and does not import either vendor SDK directly.

- Gemini remains the default and uses `gemini-3.6-flash`, preserving existing behavior.
- DeepSeek uses the OpenAI-compatible Chat Completions endpoint at `https://api.deepseek.com`, defaults to `deepseek-v4-flash`, requests a JSON object, and sends `thinking.type=disabled` for mapping workloads.

DeepSeek settings are `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, and `DEEPSEEK_BASE_URL`. Prices are deliberately absent from mapping correctness logic; only token usage is recorded.

## Secret handling

The minimal loader reads only the selected provider's allowed names from process environment or configured known local secret files. Gemini allows `GEMINI_API_KEY`, `GEMINI_KEY`, and `GOOGLE_API_KEY`; DeepSeek allows only `DEEPSEEK_API_KEY`. It does not dump TOML, search disks, read database credentials, log values, or persist secrets.

## Reliability and errors

Provider exceptions normalize to `AUTH_ERROR`, `RATE_LIMIT`, `QUOTA_EXHAUSTED`, `NETWORK_ERROR`, `TIMEOUT`, `INVALID_JSON`, `MODEL_UNAVAILABLE`, or `UNKNOWN_PROVIDER_ERROR`. Stage 5 fingerprint checkpoint/resume and bounded retry remain authoritative. `Retry-After` is honored, completed fingerprints are skipped, invalid checkpoints fail closed, and there is no implicit fallback.

## Safe switching

1. Leave `AI_PROVIDER` unset for the backward-compatible Gemini default.
2. Configure only the intended provider's key in an approved local source.
3. Set `AI_PROVIDER=deepseek` explicitly for a DeepSeek run; optionally override its model or base URL.
4. Run `Stage6_AI_Provider_Probe.bat deepseek` for one small, non-retrying health check.
5. Run `Stage6_Provider_AB_Compare.bat <target>` only when both providers are explicitly authorized.
6. Review `.local/stage6_provider_ab/` results; never commit checkpoints, raw text, questions, or mappings.

## A/B validation plan

The local A/B tool uses the same prepared HOLDOUT and separate per-provider checkpoints. It compares invalid/mismatch counts, JSON parse failures, latency, token totals, and provider errors. Accuracy remains evaluated against the same expected scope/Skill/Micro labels. This Stage 6A change only builds and mock-tests the tool; no DeepSeek request has been made.
