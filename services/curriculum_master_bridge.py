from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping
from .curriculum_master_runtime import CurriculumMasterRuntime, RouteContext

@dataclass(frozen=True)
class ExamSelectionV27:
    route: RouteContext
    main_units: tuple[str,...]
    subunits: tuple[str,...]
    skill_ids: tuple[str,...]
    difficulty: tuple[str,...]
    question_count: int

DIFFICULTY_MAP={"基礎":2,"標準":3,"進階":4,"挑戰":5}

def route_from_user_profile(runtime: CurriculumMasterRuntime,user_profile: Mapping[str,Any]) -> RouteContext:
    grade=str(user_profile.get("grade") or "")
    version=str(user_profile.get("version") or "")
    system=user_profile.get("education_system") or user_profile.get("school_type") or ("TECHNICAL" if ("技高" in version or "技術型" in version) else None)
    track=user_profile.get("math_track") or user_profile.get("track")
    if not track:
        if "數甲" in version or "數學甲" in version: track="甲"
        elif "數乙" in version or "數學乙" in version: track="乙"
        elif re.search(r"數學\s*A|數A",version,re.I): track="A"
        elif re.search(r"數學\s*B|數B",version,re.I): track="B"
        elif system=="TECHNICAL":
            m=re.search(r"(?:數學|TECH)[ _-]*([ABC])",version,re.I)
            track=m.group(1).upper() if m else None
    return runtime.resolve_route(grade,education_system=system,track=track)

def build_exam_selection(runtime: CurriculumMasterRuntime,route: RouteContext,*,main_units: Iterable[str],subunits: Iterable[str],difficulty: Iterable[str],question_count: int) -> ExamSelectionV27:
    levels=[DIFFICULTY_MAP.get(x,3) for x in difficulty]
    skills=runtime.skills_for_selection(route,main_units=tuple(main_units),subunits=tuple(subunits),max_difficulty=max(levels,default=3))
    if not skills: raise ValueError("No canonical skills match the exam selection")
    return ExamSelectionV27(route,tuple(main_units),tuple(subunits),tuple(s.skill_id for s in skills),tuple(difficulty),int(question_count))

def build_generation_context_v27(runtime: CurriculumMasterRuntime,selection: ExamSelectionV27) -> str:
    return "\n".join(["【MathAI Curriculum Master v2.7】",f"教育路徑：{selection.route.education_system}",f"年級：{selection.route.grade}",f"Track：{selection.route.track or 'COMMON'}",f"主單元：{'、'.join(selection.main_units)}",f"次單元：{'、'.join(selection.subunits)}",f"難度：{'、'.join(selection.difficulty)}",f"題數：{selection.question_count}","",runtime.build_prompt_context(selection.route,selection.skill_ids),"","每題必須回傳 canonical skill_id；可判定時另回 micro_skill_id。"])

def canonical_profile_id(route: RouteContext) -> str:
    return route.profile_id
