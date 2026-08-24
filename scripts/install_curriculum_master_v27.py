from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

EXPECTED_SHA256 = "ea0e673506f20635987db9933fe4532bfe2b0592a073fddefab3a3fe0dff745d"
TARGET_NAME = "MathAI_Master_Curriculum_Skill_v2.7_G1-G12_RUNTIME_READY.zip"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/install_curriculum_master_v27.py <validated-v2.7-zip>")
        return 2
    source = Path(sys.argv[1]).resolve()
    if not source.is_file():
        print(f"source not found: {source}")
        return 2
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        print(f"SHA256 mismatch: {digest}")
        return 3
    repo = Path(__file__).resolve().parents[1]
    target = repo / "data" / TARGET_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"installed: {target}")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
