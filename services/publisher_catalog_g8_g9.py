"""Publisher-specific G8/G9 curriculum and canonical skill mapping."""

from __future__ import annotations

from typing import Any

PUBLISHERS = ("康軒", "翰林", "南一")
SEMESTERS = ("上學期", "下學期")
JUNIOR_TYPES = (
    "標準程序", "逆向與驗證", "進階拆解", "符號檢查",
    "情境建模", "資料判讀", "證明推理", "策略判斷",
)
_PUBLISHER_CODES = {"康軒": "KX", "翰林": "HL", "南一": "NY"}
_SEMESTER_CODES = {"上學期": "A", "下學期": "B"}

# One local source of truth for G8 publisher paths and MathAI skill IDs.
def _g8_path(publisher: str, semester: str):
    common = {
        "康軒": {
            "上學期": ("乘法公式與多項式", "因式分解", "二次方根與畢氏定理"),
            "下學期": ("幾何與尺規作圖", "統計與機率", "函數與生活應用"),
        },
        "翰林": {
            "上學期": ("乘法公式與多項式", "二次方根", "因式分解與一元二次式"),
            "下學期": ("幾何與證明", "統計資料分析", "數學建模與探究"),
        },
        "南一": {
            "上學期": ("代數運算與乘法公式", "因式分解", "平方根與幾何"),
            "下學期": ("幾何圖形與證明", "統計與機率", "函數與綜合應用"),
        },
    }[publisher][semester]
    suffixes = {
        "乘法公式與多項式": (("1-1 乘法公式", (("MULFORM-01", "和平方公式", "標準程序"), ("MULFORM-02", "平方差公式", "逆向與驗證"))), ("1-2 多項式運算", (("POLY-01", "多項式加減", "標準程序"), ("POLY-02", "多項式乘法", "符號檢查")))),
        "因式分解": (("2-1 十字交乘法", (("FACTOR-01", "十字交乘法", "進階拆解"), ("FACTOR-02", "因式分解驗算", "逆向與驗證"))), ("2-2 提公因式與公式", (("FACTOR-03", "提公因式", "標準程序"), ("FACTOR-04", "公式分解選擇", "策略判斷")))),
        "二次方根與畢氏定理": (("3-1 二次方根", (("RADICAL-01", "二次方根化簡", "標準程序"), ("RADICAL-02", "根式運算", "符號檢查"))), ("3-2 畢氏定理", (("PYTH-01", "畢氏定理應用", "情境建模"), ("PYTH-02", "距離與斜邊", "逆向與驗證")))),
        "二次方根": (("2-1 根式的意義", (("RADICAL-01", "二次方根", "標準程序"), ("RADICAL-02", "根式大小比較", "策略判斷"))), ("2-2 根式運算", (("RADICAL-03", "根式乘除", "標準程序"), ("RADICAL-04", "根式應用", "情境建模")))),
        "幾何圖形與證明": (("4-1 幾何性質", (("GEOM-01", "幾何性質", "標準程序"), ("GEOM-02", "幾何證明", "證明推理"))), ("4-2 尺規作圖", (("GEOM-03", "尺規作圖", "標準程序"), ("GEOM-04", "作圖驗證", "逆向與驗證")))),
    }
    result = []
    for unit_index, main in enumerate(common, 1):
        subs = suffixes.get(main)
        if subs is None:
            subs = tuple(
                (f"{unit_index}-{sub_index} {main}基礎", ((f"GEN{_PUBLISHER_CODES[publisher]}-{unit_index:02d}-{sub_index:02d}A", f"{main}核心概念", "標準程序"), (f"GEN{_PUBLISHER_CODES[publisher]}-{unit_index:02d}-{sub_index:02d}B", f"{main}情境應用", "情境建模")))
                for sub_index in (1, 2)
            )
        result.append((main, subs))
    return tuple(result)


def _legacy_path(publisher: str, semester: str):
    names = {"康軒": ("代數與數線", "幾何與統計", "函數與應用"), "翰林": ("數與式", "幾何推理", "資料分析"), "南一": ("代數運算", "圖形與測量", "機率與統計")}[publisher]
    return tuple((main, tuple((f"{main}－{suffix}", ((f"LEGACY-{i:02d}", f"{main}{suffix}{i}", "標準程序"), (f"LEGACY-{i+2:02d}", f"{main}{suffix}{i+2}", "情境建模"))) for i, suffix in enumerate(("核心概念", "解題應用"), 1))) for main in names)


def _catalog(grade: int, publisher: str, semester: str) -> dict[str, Any]:
    code, sem = _PUBLISHER_CODES[publisher], _SEMESTER_CODES[semester]
    specs = _g8_path(publisher, semester) if grade == 8 else _legacy_path(publisher, semester)
    units = []
    for u, (main, sub_specs) in enumerate(specs, 1):
        subunits = []
        for s, (sub, skill_specs) in enumerate(sub_specs, 1):
            points = []
            for k, (suffix, label, micro) in enumerate(skill_specs, 1):
                skill_id = f"G{grade:02d}-{sem}-{suffix}"
                points.append({
                    "knowledge_point_id": f"G{grade}-{code}-{sem}-U{u}-S{s}-KP{k:02d}",
                    "skill_id": skill_id, "micro_skill_id": f"{skill_id}-MS{k:02d}", "micro_skill": micro,
                    "grade": grade, "publisher": publisher, "semester": semester,
                    "official_main_unit": main, "official_subunit": sub, "knowledge_point": label,
                    "standard_knowledge_id": f"N-{grade}-{u * 10 + s}", "question_types": [micro],
                    "difficulty": ["基礎", "標準", "進階"], "variation_levels": [1, 2, 3],
                })
            subunits.append({
                "subunit_id": f"G{grade}-{code}-{sem}-U{u}-S{s}", "official_subunit": sub,
                "standard_name": sub, "publisher_original_unit": main,
                "learning_focus": skill_specs[0][1], "prerequisite": [],
                "common_errors": ["概念混淆", "步驟遺漏"],
                "question_types": [item[2] for item in skill_specs], "difficulty_range": ["基礎", "進階"],
                "variation_levels": [1, 2, 3], "knowledge_points": points,
            })
        units.append({"official_main_unit": main, "unit_order": u, "subunits": subunits})
    return {"grade": grade, "publisher": publisher, "semester": semester, "volume": 1 if semester == "上學期" else 2,
            "verification_status": "partial", "source_url": "https://www.wincenter.com.tw/" if publisher != "南一" else "https://www.naer.edu.tw/",
            "source_type": "publisher-aligned local curriculum mapping", "units": units}


def get_catalog(grade: int, publisher: str, semester: str) -> dict[str, Any]:
    if grade not in (8, 9) or publisher not in PUBLISHERS or semester not in SEMESTERS:
        raise ValueError("unsupported G8/G9 publisher catalog selection")
    return _catalog(grade, publisher, semester)


def all_catalogs() -> list[dict[str, Any]]:
    return [get_catalog(g, p, s) for g in (8, 9) for p in PUBLISHERS for s in SEMESTERS]
