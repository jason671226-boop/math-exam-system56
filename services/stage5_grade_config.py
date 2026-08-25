"""Grade-specific configuration for the local Stage 5 pilot engine."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "data/master_curriculum_v2_7/grade_packs"


@dataclass(frozen=True)
class GradeConfig:
    target_id: str
    grade: str
    profile: str | None
    grade_label: str
    curriculum_dir: Path
    local_output_dir: Path
    in_scope_status: str
    out_scope_status: str
    out_of_scope_rules_path: Path
    real_question_source_candidates: tuple[Path, ...]
    gemini_secret_paths: tuple[Path, ...]
    recommended_validation_skill_count: int = 10
    recommended_holdout_size: int = 34
    lower_scope_hint: str = "clearly below the configured grade curriculum"
    upper_scope_hint: str = "clearly above the configured grade curriculum"


TARGET_PATTERN = re.compile(r"G(?:[1-9]|10_GENERAL|11_[AB]|12_[AB])")


def load_grade_config(grade: str) -> GradeConfig:
    normalized = str(grade or "").strip().upper()
    if normalized == "G10":
        normalized = "G10_GENERAL"
    if normalized in {"G11", "G12"}:
        raise ValueError(f"PROFILE_REQUIRED:{normalized}")
    if not TARGET_PATTERN.fullmatch(normalized):
        raise ValueError(f"UNKNOWN_GRADE:{normalized or '<blank>'}")
    curriculum = PACK_ROOT / normalized
    if not curriculum.is_dir():
        raise FileNotFoundError(f"CURRICULUM_PACK_NOT_FOUND:{normalized}")
    grade_id, _, profile = normalized.partition("_")
    lower = normalized.lower()
    sources = tuple(sorted((ROOT / "data").glob(f"diagnostic_questions_{lower}_*.json")))
    secret_paths = (
        ROOT / ".streamlit/secrets.toml",
        Path(r"C:\MathAI_G5_Pilot\.streamlit\secrets.toml"),
        Path(r"C:\MathAI_G6_Pilot\.streamlit\secrets.toml"),
        Path(r"C:\MathAI_G8_Pilot\.streamlit\secrets.toml"),
        Path(r"C:\MathAI\app\.streamlit\secrets.toml"),
    )
    return GradeConfig(
        target_id=normalized,
        grade=grade_id,
        profile=profile or None,
        grade_label=f"Taiwan {normalized} mathematics",
        curriculum_dir=curriculum,
        local_output_dir=ROOT / f".local/stage5_{lower}_mapping_pilot",
        in_scope_status=f"IN_SCOPE_{normalized}",
        out_scope_status=f"OUT_OF_SCOPE_{normalized}",
        out_of_scope_rules_path=curriculum / "OUT_OF_SCOPE_RULES.md",
        real_question_source_candidates=sources,
        gemini_secret_paths=secret_paths,
    )
