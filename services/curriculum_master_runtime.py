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
    def __init__(self, archive: str | Path | None = None) -> None:
        self.archive = Path(archive) if archive is not None else DEFAULT_ARCHIVE
        self._archive_bytes: bytes | None = None
        if not self.archive.exists():
            chunks = sorted(DATA_DIR.glob(DEFAULT_B64_GLOB))
            if not chunks:
                raise CurriculumDataError(f"curriculum archive not found: {self.archive}")
            encoded = "".join(p.read_text(encoding="ascii").strip() for p in chunks)
            self._archive_bytes = base64.b64decode(encoded)
        self._index: dict[str, tuple[str, dict[str,str]]] | None = None

    @staticmethod
    def normalize_grade(value: Any) -> str:
        m=re.search(r"(\d+)", str(value or ""))
        if not m or int(m.group(1)) not in range(1,13):
            raise CurriculumRouteError("grade must be G1-G12")
        return f"G{int(m.group(1))}"

    @staticmethod
    def normalize_system(value: Any, grade: str) -> str:
        if grade in {f"G{i}" for i in range(1,10)}:
            return "PREHIGH"
        raw=str(value or "GENERAL").strip()
        aliases={"GENERAL":"GENERAL","普通高中":"GENERAL","普通型高中":"GENERAL",
                 "TECHNICAL":"TECHNICAL","技高":"TECHNICAL","技術型高中":"TECHNICAL"}
        return aliases.get(raw, raw.upper())

    @staticmethod
    def normalize_track(track: Any, *, grade: str, system: str) -> str | None:
        raw=str(track or "").strip().replace("數學","").replace("版","")
        if system=="PREHIGH" or (system=="GENERAL" and grade=="G10"):
            return None
        if system=="GENERAL" and grade=="G11":
            r=raw.upper()
            if r in {"A","B"}: return r
            raise CurriculumRouteError("GENERAL G11 requires Math A or Math B")
        if system=="GENERAL" and grade=="G12":
            aliases={"A":"甲","甲":"甲","B":"乙","乙":"乙"}
            if raw.upper() in aliases: return aliases[raw.upper()]
            if raw in aliases: return aliases[raw]
            raise CurriculumRouteError("GENERAL G12 requires Math 甲 or Math 乙")
        if system=="TECHNICAL" and grade=="G10":
            r=raw.upper().replace("TECH_","")
            if r in {"A","B","C"}: return r
            raise CurriculumRouteError("TECHNICAL G10 requires A/B/C")
        raise CurriculumRouteError(f"unsupported route: {system} {grade} {track}")

    def resolve_route(self, grade: Any, *, education_system: Any=None, track: Any=None) -> RouteContext:
        g=self.normalize_grade(grade); system=self.normalize_system(education_system,g)
        t=self.normalize_track(track,grade=g,system=system)
        if g in {f"G{i}" for i in range(1,10)}: rel=f"grade_packs/{g}"
        elif system=="GENERAL" and g=="G10": rel="grade_packs/G10_GENERAL"
        elif system=="GENERAL" and g=="G11": rel=f"grade_packs/G11_{t}"
        elif system=="GENERAL" and g=="G12": rel=f"grade_packs/G12_{'A' if t=='甲' else 'B'}"
        elif system=="TECHNICAL" and g=="G10": rel=f"high_school_tracks/TECHNICAL/TECH_{t}/G10"
        else: raise CurriculumRouteError(f"unsupported route: {system} {g} {t}")
        if not self._exists(rel+"/standard_skills.csv"):
            raise CurriculumDataError(f"resolved pack missing: {rel}")
        return RouteContext(system,g,t,rel)

    def _zip(self) -> zipfile.ZipFile:
        if self._archive_bytes is not None:
            return zipfile.ZipFile(io.BytesIO(self._archive_bytes))
        return zipfile.ZipFile(self.archive)

    def _read_bytes(self, name: str) -> bytes:
        try:
            with self._zip() as z:
                return z.read(name)
        except KeyError as exc:
            raise CurriculumDataError(f"missing curriculum member: {name}") from exc

    def _read_text(self, name: str) -> str:
        return self._read_bytes(name).decode("utf-8-sig")

    def _read_csv(self, name: str) -> list[dict[str,str]]:
        return list(csv.DictReader(io.StringIO(self._read_text(name))))

    def _exists(self, name: str) -> bool:
        with self._zip() as z:
            return name in set(z.namelist())

    @staticmethod
    def _int(v: Any) -> int:
        try: return int(float(v))
        except (TypeError,ValueError): return 0

    def load_standard_skills(self, route: RouteContext) -> tuple[StandardSkill,...]:
        rows=self._read_csv(route.pack_relpath+"/standard_skills.csv")
        return tuple(StandardSkill(
            r["skill_id"],r.get("official_code",""),r.get("main_unit") or r.get("mathai_main_unit",""),
            r.get("subunit") or r.get("mathai_subunit",""),r.get("skill_name",""),r.get("focus",""),self._int(r.get("difficulty"))
        ) for r in rows)

    def load_micro_skills(self, route: RouteContext) -> tuple[MicroSkill,...]:
        rows=self._read_csv(route.pack_relpath+"/layer2_micro_skills.csv")
        return tuple(MicroSkill(
            r["micro_skill_id"],r["parent_skill_id"],r.get("official_code",""),r.get("main_unit") or r.get("mathai_main_unit",""),
            r.get("subunit") or r.get("mathai_subunit",""),r.get("skill_name",""),r.get("question_type",""),r.get("focus",""),
            r.get("item_pattern",""),r.get("common_error",""),self._int(r.get("difficulty"))
        ) for r in rows)

    def load_scope_rules(self, route: RouteContext) -> str:
        return self._read_text(route.pack_relpath+"/OUT_OF_SCOPE_RULES.md")

    def list_main_units(self, route: RouteContext) -> list[str]:
        return list(dict.fromkeys(x.main_unit for x in self.load_standard_skills(route) if x.main_unit))

    def list_subunits(self, route: RouteContext, main_units: Iterable[str]|None=None) -> list[str]:
        allowed=set(main_units or ())
        return list(dict.fromkeys(x.subunit for x in self.load_standard_skills(route) if x.subunit and (not allowed or x.main_unit in allowed)))

    def skills_for_selection(self, route: RouteContext, *, main_units: Iterable[str]|None=None, subunits: Iterable[str]|None=None, max_difficulty: int|None=None) -> tuple[StandardSkill,...]:
        mus,sus=set(main_units or ()),set(subunits or ())
        return tuple(x for x in self.load_standard_skills(route)
                     if (not mus or x.main_unit in mus) and (not sus or x.subunit in sus)
                     and (max_difficulty is None or x.difficulty<=max_difficulty))

    def _refs(self,row: Mapping[str,str],*fields:str) -> tuple[str,...]:
        out=[]
        for field in fields:
            for x in row.get(field,"").split(";"):
                x=x.strip()
                if x and x not in out: out.append(x)
        return tuple(out)

    def get_skill_context(self, route: RouteContext, skill_id: str) -> SkillContext:
        skill=next((x for x in self.load_standard_skills(route) if x.skill_id==skill_id),None)
        if skill is None: raise KeyError(skill_id)
        micro=tuple(x for x in self.load_micro_skills(route) if x.parent_skill_id==skill_id)
        rows=self._read_csv(route.pack_relpath+"/prerequisite_graph.csv")
        node=next((r for r in rows if r.get("skill_id")==skill_id),{})
        return SkillContext(route,skill,micro,self._refs(node,"prerequisites","prerequisite"),self._refs(node,"next_skill","successor","successors"),self.load_scope_rules(route))

    def build_prompt_context(self, route: RouteContext, skill_ids: Iterable[str]) -> str:
        lines=[f"教育路徑：{route.education_system}",f"年級：{route.grade}",f"Track：{route.track or 'COMMON'}","以下 canonical Skill 為唯一課程依據："]
        for sid in skill_ids:
            ctx=self.get_skill_context(route,sid)
            lines.append(f"- {sid}｜{ctx.skill.skill_name}｜{ctx.skill.focus}｜難度{ctx.skill.difficulty}")
            for m in ctx.micro_skills:
                lines.append(f"  - {m.micro_skill_id}｜{m.question_type}｜{m.focus}｜常見錯因：{m.common_error}")
        lines.append("\n【不可超出以下範圍】\n"+self.load_scope_rules(route))
        return "\n".join(lines)

    def validate(self) -> Mapping[str,Any]:
        qa=self._read_csv("G1-G12_GLOBAL_QA_SUMMARY.csv")
        gate=next((r for r in qa if r.get("Metric")=="Release gate"),{})
        return {"release_gate":gate.get("Result"),"qa":qa}
