# Stage 5 Generic Engine Release Candidate Audit

## Architecture

The release candidate uses target-aware configuration, automatic curriculum discovery, local inventory and fingerprinting, zero-safe coverage matrices, curriculum-only candidate selection, resilient JSON parsing, expected-versus-predicted validation, quality gates, human-review queues, and sanitized handoff generation. It supports checkpoint resume and bounded quota handling with `Retry-After` or 60/120/300-second backoff.

## Supported targets

G1 through G9, G10_GENERAL (with G10 alias), G11_A, G11_B, G12_A, and G12_B. Profile targets use isolated catalogs, statuses, and local output namespaces. Aggregate G11 and G12 mapping is forbidden.

## Foundation state

- Completed and SAFE TO PAUSE: G1, G2, G3, G4, G5, G6, G7, G8, G9, G10_GENERAL, G11_A, G11_B, G12_A, G12_B.
- Pending Foundation targets: none.
- G11 and G12 A/B profile-isolation audits PASS; aggregate profile mapping remains forbidden.
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

Foundation validation is complete. Validated real coverage remains zero until safe local sources are mapped and human-reviewed; synthetic HOLDOUTs never count as real coverage.
