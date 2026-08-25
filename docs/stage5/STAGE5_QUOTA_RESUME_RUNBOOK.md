# Stage 5 Quota Resume Runbook

Foundation completion and validated real-question coverage remain separate. Never count synthetic HOLDOUT items as real coverage.

1. Run `Stage5_Gemini_Quota_Probe.bat`. It makes at most one minimal request.
2. If the result is `GEMINI_QUOTA_BLOCKED`, do not run mapping.
3. If the result is `GEMINI_AVAILABLE`, run `Stage5_Quota_Resume_Controller.bat G7`.
4. After G7 passes, resume G9 next.
5. Continue one target at a time in `STAGE5_API_RESUME_QUEUE.md` order.
6. When the first HOLDOUT passes, do not run tuning.
7. When it returns `HOLDOUT_NEEDS_TUNING`, run the same target with `--fallback`; this uses tuning and a new HOLDOUT2.
8. If any resume returns quota blocked, stop. Checkpoints and local artifacts remain available for the next resume.

Use `--full` only when the explicitly requested workflow requires tuning followed by the original independent HOLDOUT.
