from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def resolve_pack(grade: str, education_system: str="PREHIGH", track: str|None=None) -> str:
    grade = grade.upper()
    education_system = education_system.upper()
    if grade in {f"G{i}" for i in range(1,10)}:
        return f"grade_packs/{grade}"
    if education_system == "GENERAL":
        if grade == "G10":
            return "grade_packs/G10_GENERAL"
        if grade == "G11":
            if track not in {"A","B"}:
                raise ValueError("GENERAL G11 requires track A or B")
            return f"grade_packs/G11_{track}"
        if grade == "G12":
            aliases={"A":"A","甲":"A","B":"B","乙":"B"}
            if track not in aliases:
                raise ValueError("GENERAL G12 requires track 甲/乙 (A/B accepted as aliases)")
            return f"grade_packs/G12_{aliases[track]}"
    if education_system == "TECHNICAL" and grade == "G10":
        aliases={"A":"A","B":"B","C":"C","TECH_A":"A","TECH_B":"B","TECH_C":"C"}
        if track not in aliases:
            raise ValueError("TECHNICAL G10 requires track A/B/C")
        return f"high_school_tracks/TECHNICAL/TECH_{aliases[track]}/G10"
    raise ValueError(f"Unsupported route: {education_system=} {grade=} {track=}")

def _read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def load_pack(grade: str, education_system: str="PREHIGH", track: str|None=None):
    rel=resolve_pack(grade,education_system,track)
    p=ROOT/rel
    data={
        "route":{"grade":grade,"education_system":education_system,"track":track,"pack":rel},
        "standard_skills":_read_csv(p/"standard_skills.csv"),
        "micro_skills":_read_csv(p/"layer2_micro_skills.csv"),
        "graph":_read_csv(p/"prerequisite_graph.csv"),
        "scope_rules":(p/"OUT_OF_SCOPE_RULES.md").read_text(encoding="utf-8"),
    }
    return data

def find_skill(skill_id: str):
    # Compact index-free deterministic lookup across released packs.
    candidates=[*(ROOT/"grade_packs").glob("*/standard_skills.csv"),
                *(ROOT/"high_school_tracks/TECHNICAL").glob("TECH_*/G10/standard_skills.csv")]
    for f in candidates:
        for r in _read_csv(f):
            if r.get("skill_id")==skill_id:
                return {"pack":str(f.parent.relative_to(ROOT)),"skill":r}
    return None

def build_context(skill_id: str):
    found=find_skill(skill_id)
    if not found:
        raise KeyError(skill_id)
    p=ROOT/found["pack"]
    micro=[r for r in _read_csv(p/"layer2_micro_skills.csv") if r.get("parent_skill_id")==skill_id]
    graph_rows=_read_csv(p/"prerequisite_graph.csv")
    node=next((r for r in graph_rows if r.get("skill_id")==skill_id),{})
    prereq_raw=node.get("prerequisites",node.get("prerequisite",""))
    prereqs=[x for x in prereq_raw.split(";") if x]
    return {
        **found,
        "micro_skills":micro,
        "prerequisite_ids":prereqs,
        "scope_rules":(p/"OUT_OF_SCOPE_RULES.md").read_text(encoding="utf-8"),
    }
