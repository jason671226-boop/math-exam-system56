from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64
import csv
import io
import json
import re
import zipfile
from typing import Any, Iterable, Mapping

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_ARCHIVE = DATA_DIR / "MathAI_Master_Curriculum_Skill_v2.7_G1-G12_RUNTIME_READY.zip"
DEFAULT_DIRECTORY = DATA_DIR / "master_curriculum_v2_7"
DEFAULT_B64_GLOB = "MathAI_Master_Curriculum_Skill_v2.7.zip.b64.*"


class CurriculumRouteError(ValueError):
    pass


class CurriculumDataError(ValueError):
    pass


@dataclass(frozen=True)
class RouteContext:
    education_system: str
    grade: str
    track: str | None
    pack_relpath: str

    @property
    def profile_id(self) -> str:
        return f"CURRICULUM_V27:{self.education_system}:{self.grade}:{self.track or 'COMMON'}"


@dataclass(frozen=True)
class StandardSkill:
    skill_id: str
    official_code: str
    main_unit: str
    subunit: str
    skill_name: str
    focus: str
    difficulty: int


@dataclass(frozen=True)
class MicroSkill:
    micro_skill_id: str
    parent_skill_id: str
    official_code: str
    main_unit: str
    subunit: str
    skill_name: str
    question_type: str
    focus: str
    item_pattern: str
    common_error: str
    difficulty: int


@dataclass(frozen=True)
class SkillContext:
    route: RouteContext
    skill: StandardSkill
    micro_skills: tuple[MicroSkill, ...]
    prerequisite_ids: tuple[str, ...]
    successor_ids: tuple[str, ...]
    scope_rules: str


class CurriculumMasterRuntime:
    """Read-only Curriculum Master v2.7 runtime.

    Source priority is deterministic: explicit/runtime ZIP first, then the
    repository's committed ``data/master_curriculum_v2_7`` directory, then the
    legacy base64 chunks. The public runtime API is identical for every source.
    """

    def __init__(self, archive: str | Path | None = None) -> None:
        self.archive = Path(archive) if archive is not None else DEFAULT_ARCHIVE
        self._archive_bytes: bytes | None = None
        self._directory_root: Path | None = None

        if not self.archive.exists():
            qa_file = DEFAULT_DIRECTORY / "G1-G12_GLOBAL_QA_SUMMARY.csv"
            if DEFAULT_DIRECTORY.is_dir() and qa_file.is_file():
                self._directory_root = DEFAULT_DIRECTORY
            else:
                chunks = sorted(DATA_DIR.glob(DEFAULT_B64_GLOB))
                if not chunks:
                    raise CurriculumDataError(
                        "curriculum source not found: "
                        f"archive={self.archive}, directory={DEFAULT_DIRECTORY}"
                    )
                encoded = "".join(
                    path.read_text(encoding="ascii").strip() for path in chunks
                )
                self._archive_bytes = base64.b64decode(encoded)
        self._index: dict[str, tuple[str, dict[str, str]]] | None = None

    @staticmethod
    def normalize_grade(value: Any) -> str:
        match = re.search(r"(\d+)", str(value or ""))
        if not match or int(match.group(1)) not in range(1, 13):
            raise CurriculumRouteError("grade must be G1-G12")
        return f"G{int(match.group(1))}"

    @staticmethod
    def normalize_system(value: Any, grade: str) -> str:
        if grade in {f"G{i}" for i in range(1, 10)}:
            return "PREHIGH"
        raw = str(value or "GENERAL").strip()
        aliases = {
            "GENERAL": "GENERAL",
            "普通高中": "GENERAL",
            "普通型高中": "GENERAL",
            "TECHNICAL": "TECHNICAL",
            "技高": "TECHNICAL",
            "技術型高中": "TECHNICAL",
        }
        return aliases.get(raw, raw.upper())

    @staticmethod
    def normalize_track(track: Any, *, grade: str, system: str) -> str | None:
        raw = str(track or "").strip().replace("數學", "").replace("版", "")
        if system == "PREHIGH" or (system == "GENERAL" and grade == "G10"):
            return None
        if system == "GENERAL" and grade == "G11":
            normalized = raw.upper()
            if normalized in {"A", "B"}:
                return normalized
            raise CurriculumRouteError("GENERAL G11 requires Math A or Math B")
        if system == "GENERAL" and grade == "G12":
            aliases = {"A": "甲", "甲": "甲", "B": "乙", "乙": "乙"}
            if raw.upper() in aliases:
                return aliases[raw.upper()]
            if raw in aliases:
                return aliases[raw]
            raise CurriculumRouteError("GENERAL G12 requires Math 甲 or Math 乙")
        if system == "TECHNICAL" and grade == "G10":
            normalized = raw.upper().replace("TECH_", "")
            if normalized in {"A", "B", "C"}:
                return normalized
            raise CurriculumRouteError("TECHNICAL G10 requires A/B/C")
        raise CurriculumRouteError(f"unsupported route: {system} {grade} {track}")

    def resolve_route(
        self,
        grade: Any,
        *,
        education_system: Any = None,
        track: Any = None,
    ) -> RouteContext:
        normalized_grade = self.normalize_grade(grade)
        system = self.normalize_system(education_system, normalized_grade)
        normalized_track = self.normalize_track(
            track, grade=normalized_grade, system=system
        )
        if normalized_grade in {f"G{i}" for i in range(1, 10)}:
            rel = f"grade_packs/{normalized_grade}"
        elif system == "GENERAL" and normalized_grade == "G10":
            rel = "grade_packs/G10_GENERAL"
        elif system == "GENERAL" and normalized_grade == "G11":
            rel = f"grade_packs/G11_{normalized_track}"
        elif system == "GENERAL" and normalized_grade == "G12":
            rel = f"grade_packs/G12_{'A' if normalized_track == '甲' else 'B'}"
        elif system == "TECHNICAL" and normalized_grade == "G10":
            rel = f"high_school_tracks/TECHNICAL/TECH_{normalized_track}/G10"
        else:
            raise CurriculumRouteError(
                f"unsupported route: {system} {normalized_grade} {normalized_track}"
            )
        if not self._exists(rel + "/standard_skills.csv"):
            raise CurriculumDataError(f"resolved pack missing: {rel}")
        return RouteContext(system, normalized_grade, normalized_track, rel)

    def _zip(self) -> zipfile.ZipFile:
        if self._directory_root is not None:
            raise CurriculumDataError(
                "ZIP access is unavailable in directory-backed curriculum mode"
            )
        if self._archive_bytes is not None:
            return zipfile.ZipFile(io.BytesIO(self._archive_bytes))
        return zipfile.ZipFile(self.archive)

    def _read_bytes(self, name: str) -> bytes:
        if self._directory_root is not None:
            path = self._directory_root / name
            if not path.is_file():
                raise CurriculumDataError(f"missing curriculum member: {name}")
            return path.read_bytes()
        try:
            with self._zip() as archive:
                return archive.read(name)
        except KeyError as exc:
            raise CurriculumDataError(f"missing curriculum member: {name}") from exc

    def _read_text(self, name: str) -> str:
        return self._read_bytes(name).decode("utf-8-sig")

    def _read_csv(self, name: str) -> list[dict[str, str]]:
        return list(csv.DictReader(io.StringIO(self._read_text(name))))

    def _exists(self, name: str) -> bool:
        if self._directory_root is not None:
            return (self._directory_root / name).is_file()
        with self._zip() as archive:
            return name in set(archive.namelist())

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def load_standard_skills(
        self, route: RouteContext
    ) -> tuple[StandardSkill, ...]:
        rows = self._read_csv(route.pack_relpath + "/standard_skills.csv")
        return tuple(
            StandardSkill(
                row["skill_id"],
                row.get("official_code", ""),
                row.get("main_unit") or row.get("mathai_main_unit", ""),
                row.get("subunit") or row.get("mathai_subunit", ""),
                row.get("skill_name", ""),
                row.get("focus", ""),
                self._int(row.get("difficulty")),
            )
            for row in rows
        )

    def load_micro_skills(self, route: RouteContext) -> tuple[MicroSkill, ...]:
        rows = self._read_csv(route.pack_relpath + "/layer2_micro_skills.csv")
        return tuple(
            MicroSkill(
                row["micro_skill_id"],
                row["parent_skill_id"],
                row.get("official_code", ""),
                row.get("main_unit") or row.get("mathai_main_unit", ""),
                row.get("subunit") or row.get("mathai_subunit", ""),
                row.get("skill_name", ""),
                row.get("question_type", ""),
                row.get("focus", ""),
                row.get("item_pattern", ""),
                row.get("common_error", ""),
                self._int(row.get("difficulty")),
            )
            for row in rows
        )

    def load_scope_rules(self, route: RouteContext) -> str:
        return self._read_text(route.pack_relpath + "/OUT_OF_SCOPE_RULES.md")

    def list_main_units(self, route: RouteContext) -> list[str]:
        return list(
            dict.fromkeys(
                skill.main_unit
                for skill in self.load_standard_skills(route)
                if skill.main_unit
            )
        )

    def list_subunits(
        self, route: RouteContext, main_units: Iterable[str] | None = None
    ) -> list[str]:
        allowed = set(main_units or ())
        return list(
            dict.fromkeys(
                skill.subunit
                for skill in self.load_standard_skills(route)
                if skill.subunit and (not allowed or skill.main_unit in allowed)
            )
        )

    def skills_for_selection(
        self,
        route: RouteContext,
        *,
        main_units: Iterable[str] | None = None,
        subunits: Iterable[str] | None = None,
        max_difficulty: int | None = None,
    ) -> tuple[StandardSkill, ...]:
        selected_main = set(main_units or ())
        selected_sub = set(subunits or ())
        return tuple(
            skill
            for skill in self.load_standard_skills(route)
            if (not selected_main or skill.main_unit in selected_main)
            and (not selected_sub or skill.subunit in selected_sub)
            and (max_difficulty is None or skill.difficulty <= max_difficulty)
        )

    def _refs(self, row: Mapping[str, str], *fields: str) -> tuple[str, ...]:
        output: list[str] = []
        for field in fields:
            for value in row.get(field, "").split(";"):
                value = value.strip()
                if value and value not in output:
                    output.append(value)
        return tuple(output)

    def get_skill_context(self, route: RouteContext, skill_id: str) -> SkillContext:
        skill = next(
            (
                candidate
                for candidate in self.load_standard_skills(route)
                if candidate.skill_id == skill_id
            ),
            None,
        )
        if skill is None:
            raise KeyError(skill_id)
        micro = tuple(
            item
            for item in self.load_micro_skills(route)
            if item.parent_skill_id == skill_id
        )
        rows = self._read_csv(route.pack_relpath + "/prerequisite_graph.csv")
        node = next((row for row in rows if row.get("skill_id") == skill_id), {})
        return SkillContext(
            route,
            skill,
            micro,
            self._refs(node, "prerequisites", "prerequisite"),
            self._refs(node, "next_skill", "successor", "successors"),
            self.load_scope_rules(route),
        )

    def build_prompt_context(
        self, route: RouteContext, skill_ids: Iterable[str]
    ) -> str:
        lines = [
            f"教育路徑：{route.education_system}",
            f"年級：{route.grade}",
            f"Track：{route.track or 'COMMON'}",
            "以下 canonical Skill 為唯一課程依據：",
        ]
        for skill_id in skill_ids:
            context = self.get_skill_context(route, skill_id)
            lines.append(
                f"- {skill_id}｜{context.skill.skill_name}｜"
                f"{context.skill.focus}｜難度{context.skill.difficulty}"
            )
            for micro in context.micro_skills:
                lines.append(
                    f"  - {micro.micro_skill_id}｜{micro.question_type}｜"
                    f"{micro.focus}｜常見錯因：{micro.common_error}"
                )
        lines.append("\n【不可超出以下範圍】\n" + self.load_scope_rules(route))
        return "\n".join(lines)

    def validate(self) -> Mapping[str, Any]:
        qa = self._read_csv("G1-G12_GLOBAL_QA_SUMMARY.csv")
        gate = next((row for row in qa if row.get("Metric") == "Release gate"), {})
        return {"release_gate": gate.get("Result"), "qa": qa}
