# Stage 5 Generic Engine Release Candidate Audit

## Architecture

The release candidate uses target-aware configuration, automatic curriculum discovery, local inventory and fingerprinting, zero-safe coverage matrices, curriculum-only candidate selection, resilient JSON parsing, expected-versus-predicted validation, quality gates, human-review queues, and sanitized handoff generation. It supports checkpoint resume and bounded quota handling with `Retry-After` or 60/120/300-second backoff.

## Supported targets

G1 through G9, G10_GENERAL (with G10 alias), G11_A, G11_B, G12_A, and G12_B. Profile targets use isolated catalogs, statuses, and local output namespaces. Aggregate G11 and G12 mapping is forbidden.

## Foundation state

- Completed: G5, G6, G8.
- Pending: G1, G2, G3, G4, G7, G9, G10_GENERAL, G11_A, G11_B, G12_A, G12_B.
- G7 is technically ready and externally API-blocked; its 34-item HOLDOUT and checkpoints are preserved.
- Foundation completion is not validated real coverage. Current validated real coverage remains 0% in generic summaries.

## API and checkpoint strategy

New targets use HOLDOUT-first validation. Passing HOLDOUTs skip tuning. Failed HOLDOUTs require tuning plus a distinct HOLDOUT2. Resume is single-target, fingerprint-skipping, and fail-closed on quota exhaustion. The probe makes at most one minimal request and never retries.

## Safety and tests

- Offline regression: 61/61 PASS (including the frozen 59-test baseline).
- Production reads: 0; production writes: 0.
- No database client is used by the generic engine.
- Secrets stay in process memory and are never included in outputs.
- Local questions, synthetic sets, checkpoints, and mappings remain ignored by Git.

## Known limitations and recovery

Foundation validation for pending targets requires external API availability. Real local sources are absent for most pending targets, so validated real coverage will remain zero until safe sources are available and human-reviewed. Follow `STAGE5_QUOTA_RESUME_RUNBOOK.md`, beginning with G7, and process one target at a time.
