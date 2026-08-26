"""Fail closed when private Stage 7 artifacts or secrets are staged."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_ALWAYS = (".local/", ".env", "secrets.toml")
PRIVATE_ARTIFACT_NAMES = ("human_review", "raw_question", "raw_mapping", "model_raw")
SANITIZED_SOURCE_SUFFIXES = {".py", ".md"}
SECRET_MARKERS = tuple(prefix + "KEY=" for prefix in ("DEEPSEEK_API_", "GEMINI_API_", "GOOGLE_API_")) + ("service_" + "role_key",)


def staged_paths() -> list[str]:
    result = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], cwd=ROOT,
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def validate_staged(paths: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    for relative in paths if paths is not None else staged_paths():
        lowered = relative.lower()
        suffix = Path(lowered).suffix
        if any(marker in lowered for marker in FORBIDDEN_ALWAYS) or (
            suffix not in SANITIZED_SOURCE_SUFFIXES and any(marker in lowered for marker in PRIVATE_ARTIFACT_NAMES)
        ):
            errors.append(f"FORBIDDEN_STAGED_PATH:{relative}")
            continue
        path = ROOT / relative
        if path.is_file() and path.stat().st_size <= 2_000_000:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(marker.lower() in text.lower() for marker in SECRET_MARKERS):
                errors.append(f"POSSIBLE_SECRET:{relative}")
    return errors


if __name__ == "__main__":
    failures = validate_staged()
    if failures:
        print("\n".join(failures))
        raise SystemExit(1)
    print("STAGE7_GIT_GUARD_PASS")
