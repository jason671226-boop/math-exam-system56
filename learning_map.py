import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


DATA_FILE = Path(__file__).with_name("curriculum_map.json")
G7_DATA_FILE = Path(__file__).with_name("learning_map_g7.json")


def _load_data() -> Dict[str, Any]:
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_g7_data() -> Dict[str, Any]:
    try:
        with G7_DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize_publisher(version_text: str) -> str:
    version = str(version_text or "").strip()
    aliases = {
        "康軒版": "康軒",
        "康軒": "康軒",
        "翰林版": "翰林",
        "翰林": "翰林",
        "南一版": "南一",
        "南一": "南一",
    }
    return aliases.get(version, version.replace("版", "").strip())


def _g7_profile_data(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    if _grade_number(user_profile) != "7":
        return {}
    data = _load_g7_data()
    publisher = _normalize_publisher(user_profile.get("version", ""))
    if not data or publisher not in data.get("publishers", {}):
        return {}
    return {
        "data": data,
        "publisher": publisher,
        "semesters": data["publishers"][publisher],
    }


def _g7_all_units(profile_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for semester_name, semester_data in profile_data.get("semesters", {}).items():
        for unit in semester_data.get("units", []):
            item = dict(unit)
            item["semester"] = semester_name
            result.append(item)
    return result


def _g7_find_subunit(
    profile_data: Dict[str, Any],
    unit_name: str,
    subunit_name: str,
) -> Dict[str, Any]:
    for unit in _g7_all_units(profile_data):
        if str(unit.get("name", "")).strip() != unit_name:
            continue
        for subunit in unit.get("subunits", []):
            if str(subunit.get("name", "")).strip() == subunit_name:
                return subunit
    return {}


def _normalize_grade(grade_text: str) -> str:
    if not grade_text:
        return ""
    return grade_text.split("年級", 1)[0].strip()


DEFAULT_UNIT_OPTIONS = {
    "康軒版": [
        "數與量", "計算與代數", "分數與小數", "比與比例",
        "幾何與測量", "統計與機率", "生活應用與跨單元",
    ],
    "翰林版": [
        "數與量", "計算與代數", "分數與小數", "比與比例",
        "幾何與測量", "統計與機率", "生活應用與跨單元",
    ],
    "南一版": [
        "數與量", "計算與代數", "分數與小數", "比與比例",
        "幾何與測量", "統計與機率", "生活應用與跨單元",
    ],
    "報考私中": [
        "數與計算", "應用問題", "幾何與測量",
        "規律與推理", "跨單元綜合", "私中入學題型",
    ],
    "參加數學競賽": [
        "數論", "計數與組合", "幾何",
        "代數與規律", "邏輯推理", "綜合挑戰",
    ],
}

HIGH_SCHOOL_UNIT_OPTIONS = {
    "A級 (數學A)": [
        "數與式",
        "指數與對數",
        "多項式與多項式函數",
        "直線與圓",
        "數列與級數",
        "排列組合",
        "機率與統計",
        "三角比與三角函數",
        "平面向量",
        "空間概念",
    ],
    "B級 (數學B)": [
        "數與式",
        "指數與對數",
        "多項式函數",
        "直線與圓",
        "數列與級數",
        "排列組合與機率",
        "數據分析",
        "三角比",
        "平面向量",
        "生活情境應用",
    ],
    "C級 (數學C)": [
        "數與式",
        "指數與對數",
        "多項式函數",
        "直線與圓",
        "數列與級數",
        "排列組合與機率",
        "三角函數",
        "平面向量",
        "空間向量",
        "進階綜合題",
    ],
}

JUNIOR_HIGH_UNIT_OPTIONS = [
    "數與數線",
    "因數與倍數",
    "分數與小數運算",
    "一元一次方程式",
    "二元一次聯立方程式",
    "比例與函數",
    "幾何與測量",
    "統計與機率",
    "生活應用與跨單元",
]

ELEMENTARY_UNIT_OPTIONS = [
    "數與量",
    "四則運算",
    "分數與小數",
    "比與比例",
    "幾何與測量",
    "時間、重量與容量",
    "統計與資料整理",
    "生活應用與跨單元",
]


ELEMENTARY_COMPETITION_HIERARCHY = {
    "奧林匹克數學": {
        "算術與巧算": {
            "topics": [
                "四則運算與運算律",
                "湊整與拆補",
                "數列與規律巧算",
                "估算與逆向思考",
            ],
            "question_types": [
                "巧算與速算",
                "找規律計算",
                "逆運算",
                "多步驟算式",
            ],
        },
        "數論與整除": {
            "topics": [
                "奇偶性",
                "因數與倍數",
                "質數與合數",
                "整除與餘數",
            ],
            "question_types": [
                "奇偶判斷",
                "因倍數推理",
                "餘數問題",
                "整除性綜合題",
            ],
        },
        "計數與組合": {
            "topics": [
                "有系統列舉",
                "加法原理與乘法原理",
                "排列與組合初步",
                "重複與不重複計數",
            ],
            "question_types": [
                "列舉法",
                "樹狀圖計數",
                "排列方式",
                "組合選取",
            ],
        },
        "幾何與圖形": {
            "topics": [
                "角度與多邊形",
                "面積與周長",
                "圖形分割與拼補",
                "立體與空間想像",
            ],
            "question_types": [
                "角度追蹤",
                "割補面積",
                "圖形計數",
                "空間展開與摺疊",
            ],
        },
        "邏輯與策略": {
            "topics": [
                "真假與條件推理",
                "分類討論",
                "不變量與極端思考",
                "逆推與假設法",
            ],
            "question_types": [
                "邏輯判斷",
                "條件推理",
                "逆推問題",
                "策略型綜合題",
            ],
        },
        "應用問題": {
            "topics": [
                "和差倍問題",
                "年齡問題",
                "行程問題",
                "雞兔與分配問題",
            ],
            "question_types": [
                "和差倍應用",
                "年齡推理",
                "行程與速率",
                "雞兔同籠與分配",
            ],
        },
    },

    "AMC": {
        "數與運算": {
            "topics": [
                "整數與四則運算",
                "分數、小數與百分率",
                "因數倍數與數論初步",
                "估算與數感",
            ],
            "question_types": [
                "運算推理",
                "分數小數轉換",
                "整除與餘數",
                "數感估算",
            ],
        },
        "比率與應用": {
            "topics": [
                "比與比例",
                "百分率",
                "平均數",
                "單位率與速率",
            ],
            "question_types": [
                "比例推理",
                "百分率應用",
                "平均數問題",
                "速率與單位率",
            ],
        },
        "幾何與測量": {
            "topics": [
                "角度",
                "三角形與四邊形",
                "周長與面積",
                "體積與空間概念",
            ],
            "question_types": [
                "角度計算",
                "圖形性質",
                "面積組合",
                "立體幾何初步",
            ],
        },
        "計數與機率": {
            "topics": [
                "系統列舉",
                "排列組合初步",
                "簡單機率",
                "表格與樹狀圖",
            ],
            "question_types": [
                "列舉計數",
                "排列組合",
                "機率判斷",
                "樹狀圖與表格",
            ],
        },
        "代數與規律": {
            "topics": [
                "數列與圖形規律",
                "未知數與簡單方程",
                "代數式表示",
                "函數關係初步",
            ],
            "question_types": [
                "找規律",
                "代數表示",
                "簡易方程",
                "表格關係題",
            ],
        },
        "綜合挑戰": {
            "topics": [
                "多步驟應用",
                "跨單元整合",
                "邏輯推理",
                "競賽策略與時間控制",
            ],
            "question_types": [
                "AMC 風格短題",
                "多概念整合",
                "陷阱辨識",
                "選項反推",
            ],
        },
    },

    "ELNC": {
        "數感與基礎運算": {
            "topics": [
                "整數與四則運算",
                "心算與估算",
                "分數與小數",
                "數量關係",
            ],
            "question_types": [
                "快速計算",
                "數感比較",
                "分數小數應用",
                "數量關係判讀",
            ],
        },
        "規律與推理": {
            "topics": [
                "數字規律",
                "圖形規律",
                "條件推理",
                "排序與分類",
            ],
            "question_types": [
                "找下一項",
                "缺項填補",
                "邏輯排序",
                "分類判斷",
            ],
        },
        "圖形與空間": {
            "topics": [
                "平面圖形",
                "對稱與拼圖",
                "方向與位置",
                "立體空間",
            ],
            "question_types": [
                "圖形辨識",
                "拼圖與分割",
                "方向判讀",
                "立體展開",
            ],
        },
        "生活情境應用": {
            "topics": [
                "時間與日曆",
                "金錢與購物",
                "長度重量容量",
                "表格與圖表",
            ],
            "question_types": [
                "生活應用題",
                "時間推理",
                "單位換算",
                "圖表判讀",
            ],
        },
        "計數與資料": {
            "topics": [
                "簡單列舉",
                "分類計數",
                "資料整理",
                "可能性初步",
            ],
            "question_types": [
                "有序列舉",
                "分類統計",
                "表格整理",
                "可能性判斷",
            ],
        },
        "綜合挑戰": {
            "topics": [
                "跨單元推理",
                "多步驟解題",
                "觀察與策略",
                "競賽型綜合題",
            ],
            "question_types": [
                "多步驟綜合",
                "觀察推理",
                "策略選擇",
                "競賽綜合題",
            ],
        },
    },

    "跨競賽綜合": {
        "奧數 × AMC 綜合": {
            "topics": [
                "數論與數感",
                "幾何與計數",
                "代數規律",
                "邏輯與應用",
            ],
            "question_types": [
                "奧數思維題",
                "AMC 風格選擇題",
                "跨單元綜合",
                "限時挑戰題",
            ],
        },
        "AMC × ELNC 綜合": {
            "topics": [
                "運算與比例",
                "圖形與測量",
                "規律與資料",
                "生活情境推理",
            ],
            "question_types": [
                "短題快速判斷",
                "圖表與資料題",
                "生活情境題",
                "綜合推理題",
            ],
        },
    },
}


JUNIOR_HIGH_HIERARCHY = {
    "數與數線": {
        "正負數與數線": {
            "topics": ["正負數概念", "數線定位與大小比較", "相反數與絕對值"],
            "question_types": ["數線判讀", "正負數大小比較", "絕對值與距離"],
        },
        "科學記號與近似值": {
            "topics": ["科學記號表示", "有效數字", "誤差與近似值"],
            "question_types": ["科學記號互換", "近似值判讀", "誤差範圍"],
        },
    },
    "因數與倍數": {
        "質因數分解": {
            "topics": ["質數與合數", "短除法", "標準分解式"],
            "question_types": ["質因數分解", "指數形式判讀", "整除判斷"],
        },
        "最大公因數": {
            "topics": ["公因數", "最大公因數", "分組與分配應用"],
            "question_types": ["列舉法", "短除法", "最大公因數應用題"],
        },
        "最小公倍數": {
            "topics": ["公倍數", "最小公倍數", "週期與同時發生問題"],
            "question_types": ["列舉法", "短除法", "最小公倍數應用題"],
        },
    },
    "分數與小數運算": {
        "分數四則運算": {
            "topics": ["約分與通分", "分數加減", "分數乘除"],
            "question_types": ["異分母加減", "連乘連除", "混合運算"],
        },
        "小數與分數互換": {
            "topics": ["有限小數", "循環小數", "分數小數互換"],
            "question_types": ["小數化分數", "分數化小數", "循環小數判讀"],
        },
    },
    "一元一次方程式": {
        "代數式與同類項": {
            "topics": ["文字符號", "代數式化簡", "同類項合併"],
            "question_types": ["代數式表示", "去括號", "同類項化簡"],
        },
        "一元一次方程式": {
            "topics": ["等量公理", "移項法則", "方程式求解"],
            "question_types": ["基本方程式", "含括號方程式", "分數係數方程式"],
        },
        "應用問題": {
            "topics": ["年齡問題", "行程問題", "分配問題"],
            "question_types": ["列一元一次方程式", "文字題轉換", "答案合理性檢查"],
        },
    },
    "二元一次聯立方程式": {
        "二元一次方程式": {
            "topics": ["二元一次方程式", "解的意義", "圖形表示"],
            "question_types": ["判斷解", "代入驗證", "直線交點"],
        },
        "聯立方程式解法": {
            "topics": ["代入消去法", "加減消去法", "特殊解情形"],
            "question_types": ["代入法", "加減法", "無解與無限多解"],
        },
        "聯立方程式應用": {
            "topics": ["雞兔問題", "價格數量問題", "行程問題"],
            "question_types": ["列聯立方程式", "生活情境題", "表格整理題"],
        },
    },
    "比例與函數": {
        "比與比例式": {
            "topics": ["比值", "比例式", "正比與反比"],
            "question_types": ["比例式求值", "正比應用", "反比應用"],
        },
        "一次函數": {
            "topics": ["函數概念", "一次函數圖形", "斜率與截距"],
            "question_types": ["函數值", "畫一次函數圖形", "由圖形求關係式"],
        },
    },
    "幾何與測量": {
        "平面幾何": {
            "topics": ["角與平行線", "三角形性質", "多邊形"],
            "question_types": ["角度計算", "三角形內外角", "多邊形內角和"],
        },
        "尺規作圖與全等": {
            "topics": ["基本作圖", "三角形全等", "垂直平分線"],
            "question_types": ["尺規作圖步驟", "全等判定", "幾何證明"],
        },
        "圓與相似形": {
            "topics": ["圓的性質", "相似三角形", "比例線段"],
            "question_types": ["圓周角", "相似判定", "比例線段計算"],
        },
    },
    "統計與機率": {
        "統計資料整理": {
            "topics": ["次數分配表", "平均數中位數眾數", "盒狀圖"],
            "question_types": ["統計表判讀", "代表值計算", "資料比較"],
        },
        "機率": {
            "topics": ["樣本空間", "理論機率", "實驗機率"],
            "question_types": ["列舉樣本空間", "單一步驟機率", "樹狀圖"],
        },
    },
    "生活應用與跨單元": {
        "跨單元綜合": {
            "topics": ["代數與幾何整合", "比例與統計整合", "生活情境建模"],
            "question_types": ["多步驟應用題", "圖表整合題", "素養題"],
        },
    },
}


CURRICULUM_HIERARCHY = {
    ("10", "A級 (數學A)"): {
        "數與式": {
            "實數與數線": {
                "topics": [
                    "有理數與無理數的判別",
                    "實數的稠密性與大小比較",
                    "數線上的區間與距離",
                ],
                "question_types": [
                    "有限小數、循環小數與有理數判別",
                    "根號數是否為有理數的判別",
                    "實數大小比較與數線定位",
                ],
            },
            "根式與雙重根式": {
                "topics": [
                    "根式的化簡與四則運算",
                    "雙重根式的拆解",
                    "共軛根式與有理化",
                ],
                "question_types": [
                    "可直接寫成平方和的雙重根式",
                    "缺少中間項時的配方判別",
                    "係數條件較大時的拆項與試配",
                    "共軛根式乘積與分母有理化",
                ],
            },
            "絕對值": {
                "topics": [
                    "絕對值的幾何意義",
                    "分段討論",
                    "絕對值方程式與不等式",
                ],
                "question_types": [
                    "單一絕對值方程式",
                    "多個臨界點的分段討論",
                    "絕對值不等式與區間表示",
                    "絕對值函數圖形判讀",
                ],
            },
            "不等式": {
                "topics": [
                    "算術平均與幾何平均不等式",
                    "平方恆非負與配方法",
                    "基本不等式的等號成立條件",
                ],
                "question_types": [
                    "兩正數的算幾不等式",
                    "固定和求乘積最大值",
                    "固定積求和最小值",
                    "含參數不等式與等號條件",
                ],
            },
        },
    },
}


def _grade_number(user_profile: Dict[str, Any]) -> str:
    import re
    match = re.search(r"(\d+)", str(user_profile.get("grade", "")))
    return match.group(1) if match else ""


def _catalog_for_profile(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    grade_number = _grade_number(user_profile)
    version = str(user_profile.get("version", ""))

    exact_catalog = CURRICULUM_HIERARCHY.get(
        (grade_number, version),
        {},
    )
    if exact_catalog:
        return exact_catalog

    if grade_number in {"1", "2", "3", "4", "5", "6"} and version == "參加數學競賽":
        return ELEMENTARY_COMPETITION_HIERARCHY

    if grade_number in {"7", "8", "9"}:
        return JUNIOR_HIGH_HIERARCHY

    return {}


def _matching_demo(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_data()
    demo = data.get("demo", {})
    current_grade = _normalize_grade(user_profile.get("grade", ""))
    current_version = user_profile.get("version", "康軒版")

    if (
        demo
        and current_grade == str(demo.get("grade", ""))
        and current_version == demo.get("version", "")
    ):
        return demo
    return {}


def _all_demo_units(demo: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for semester_data in demo.get("semesters", {}).values():
        result.extend(semester_data.get("units", []))
    return result


def get_unit_names_for_profile(user_profile: Dict[str, Any]) -> List[str]:
    """依年級與版本取得主單元，避免沿用前一個年級的選項。"""
    g7_profile = _g7_profile_data(user_profile)
    if g7_profile:
        result: List[str] = []
        for unit in _g7_all_units(g7_profile):
            unit_name = str(unit.get("name", "")).strip()
            if unit_name and unit_name not in result:
                result.append(unit_name)
        if result:
            return result

    demo = _matching_demo(user_profile)
    if demo:
        result: List[str] = []
        for unit in _all_demo_units(demo):
            unit_name = str(unit.get("name", "")).strip()
            if unit_name and unit_name not in result:
                result.append(unit_name)
        if result:
            return result

    current_grade_text = str(user_profile.get("grade", ""))
    current_version = str(user_profile.get("version", "康軒版"))
    grade_match = __import__("re").search(r"(\d+)", current_grade_text)
    grade_number = int(grade_match.group(1)) if grade_match else 0

    if current_version in HIGH_SCHOOL_UNIT_OPTIONS:
        return HIGH_SCHOOL_UNIT_OPTIONS[current_version]

    if grade_number >= 10:
        return HIGH_SCHOOL_UNIT_OPTIONS["A級 (數學A)"]

    if 7 <= grade_number <= 9:
        return JUNIOR_HIGH_UNIT_OPTIONS

    if 1 <= grade_number <= 6:
        if current_version == "參加數學競賽":
            return list(ELEMENTARY_COMPETITION_HIERARCHY.keys())
        return ELEMENTARY_UNIT_OPTIONS

    return DEFAULT_UNIT_OPTIONS.get(
        current_version,
        DEFAULT_UNIT_OPTIONS["康軒版"],
    )


def get_subunit_names_for_units(
    user_profile: Dict[str, Any],
    selected_unit_names: List[str],
) -> List[str]:
    """依主單元回傳真正的次單元；沒有校對資料時回傳空清單。"""
    g7_profile = _g7_profile_data(user_profile)
    if g7_profile and selected_unit_names:
        results: List[str] = []
        selected_set = set(selected_unit_names)
        for unit in _g7_all_units(g7_profile):
            unit_name = str(unit.get("name", "")).strip()
            if unit_name not in selected_set:
                continue
            for subunit in unit.get("subunits", []):
                subunit_name = str(subunit.get("name", "")).strip()
                if subunit_name:
                    label = f"{unit_name} ＞ {subunit_name}"
                    if label not in results:
                        results.append(label)
        return results

    demo = _matching_demo(user_profile)
    if demo and selected_unit_names:
        results: List[str] = []
        for unit in _all_demo_units(demo):
            unit_name = str(unit.get("name", "")).strip()
            if unit_name not in selected_unit_names:
                continue
            for subunit in unit.get("subunits", []):
                subunit_name = str(subunit.get("name", "")).strip()
                if subunit_name:
                    label = f"{unit_name} ＞ {subunit_name}"
                    if label not in results:
                        results.append(label)
        if results:
            return results

    catalog = _catalog_for_profile(user_profile)
    results: List[str] = []
    for unit_name in selected_unit_names:
        for subunit_name in catalog.get(unit_name, {}).keys():
            label = f"{unit_name} ＞ {subunit_name}"
            if label not in results:
                results.append(label)
    return results


def get_topic_names_for_subunits(
    user_profile: Dict[str, Any],
    selected_subunit_labels: List[str],
) -> List[str]:
    """依次單元回傳學習重點；不使用通用假選項。"""
    g7_profile = _g7_profile_data(user_profile)
    results: List[str] = []

    if g7_profile:
        core_map = g7_profile["data"].get("core", {})
        for selected_label in selected_subunit_labels:
            parts = [part.strip() for part in selected_label.split("＞")]
            if len(parts) != 2:
                continue
            unit_name, subunit_name = parts
            subunit = _g7_find_subunit(g7_profile, unit_name, subunit_name)
            for core_id in subunit.get("core_ids", []):
                core = core_map.get(core_id, {})
                for concept in core.get("concepts", []):
                    label = f"{unit_name} ＞ {subunit_name} ＞ {concept}"
                    if label not in results:
                        results.append(label)
        return results

    demo = _matching_demo(user_profile)

    if demo:
        selected_set = set(selected_subunit_labels)
        for unit in _all_demo_units(demo):
            unit_name = str(unit.get("name", "")).strip()
            for subunit in unit.get("subunits", []):
                subunit_name = str(subunit.get("name", "")).strip()
                label = f"{unit_name} ＞ {subunit_name}"
                if label not in selected_set:
                    continue
                for topic in subunit.get("topics", []):
                    topic_name = str(topic.get("name", "")).strip()
                    full_label = f"{label} ＞ {topic_name}"
                    if topic_name and full_label not in results:
                        results.append(full_label)
        if results:
            return results

    catalog = _catalog_for_profile(user_profile)
    for selected_label in selected_subunit_labels:
        parts = [part.strip() for part in selected_label.split("＞")]
        if len(parts) != 2:
            continue
        unit_name, subunit_name = parts
        subunit_data = catalog.get(unit_name, {}).get(subunit_name, {})
        for topic_name in subunit_data.get("topics", []):
            label = f"{unit_name} ＞ {subunit_name} ＞ {topic_name}"
            if label not in results:
                results.append(label)
    return results


def get_classic_question_type_names_for_units(
    user_profile: Dict[str, Any],
    selected_subunit_labels: List[str],
) -> List[str]:
    """依次單元回傳細部題型；沒有可靠資料時回傳空清單。"""
    g7_profile = _g7_profile_data(user_profile)
    results: List[str] = []

    if g7_profile:
        core_map = g7_profile["data"].get("core", {})
        for selected_label in selected_subunit_labels:
            parts = [part.strip() for part in selected_label.split("＞")]
            if len(parts) != 2:
                continue
            unit_name, subunit_name = parts
            subunit = _g7_find_subunit(g7_profile, unit_name, subunit_name)
            for core_id in subunit.get("core_ids", []):
                core = core_map.get(core_id, {})
                for type_name in core.get("question_types", []):
                    label = f"{unit_name} ＞ {subunit_name} ＞ {type_name}"
                    if label not in results:
                        results.append(label)
        return results

    catalog = _catalog_for_profile(user_profile)
    for selected_label in selected_subunit_labels:
        parts = [part.strip() for part in selected_label.split("＞")]
        if len(parts) != 2:
            continue
        unit_name, subunit_name = parts
        subunit_data = catalog.get(unit_name, {}).get(subunit_name, {})
        for type_name in subunit_data.get("question_types", []):
            label = f"{unit_name} ＞ {subunit_name} ＞ {type_name}"
            if label not in results:
                results.append(label)
    return results


def _render_pack_group(unit_id: str, pack_group: Dict[str, Any]) -> None:
    title = pack_group.get("title", "題組")
    description = pack_group.get("description", "")
    packs: List[Dict[str, Any]] = pack_group.get("packs", [])

    st.markdown(f"#### {title}")
    if description:
        st.caption(description)

    columns = st.columns(3)
    for idx, pack in enumerate(packs):
        with columns[idx % 3]:
            pack_name = pack.get("name", f"題組 {idx + 1}")
            status = pack.get("status", "準備中")
            st.markdown(f"**{pack_name}**  \n5 題｜{status}")
            st.button(
                "準備中",
                key=f"learning_pack_{unit_id}_{title}_{idx}",
                disabled=True,
                use_container_width=True,
            )


def _render_topic_detail(topic: Dict[str, Any]) -> None:
    tips = topic.get("tips", [])
    example = topic.get("example", "")
    answer = topic.get("answer", "")
    solution = topic.get("solution", "")

    if tips:
        st.markdown("**📌 單元重點提示**")
        for tip in tips:
            st.markdown(f"- {tip}")

    if example:
        st.markdown("**🧪 例題**")
        st.info(example)

    if answer or solution:
        with st.expander("查看答案與解法", expanded=False):
            if answer:
                st.markdown(f"**答案：** {answer}")
            if solution:
                st.markdown(f"**解法：** {solution}")


def _render_classic_type(item: Dict[str, Any], key: str) -> None:
    name = item.get("name", "經典題型")
    description = item.get("description", "")
    example = item.get("example", "")
    answer = item.get("answer", "")
    solution = item.get("solution", "")

    with st.expander(f"🧩 {name}", expanded=False):
        if description:
            st.write(description)
        if example:
            st.markdown("**例題**")
            st.info(example)
        if answer or solution:
            st.markdown("**解答**")
            if answer:
                st.markdown(f"- **答案：** {answer}")
            if solution:
                st.markdown(f"- **解析：** {solution}")


def _render_g7_learning_map(user_profile: Dict[str, Any]) -> bool:
    profile_data = _g7_profile_data(user_profile)
    if not profile_data:
        return False

    data = profile_data["data"]
    publisher = profile_data["publisher"]
    semesters = profile_data["semesters"]
    core_map = data.get("core", {})

    st.subheader("🌳 國一數學學習地圖")
    st.info(
        "目前已接入國一三版本正式母表：主單元 → 次單元 → 核心概念 → 常見考法題型。"
        "本版已加入 164 個題型，並顯示 106～115 會考的保守實證次數、出現年度與歷屆證據。"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("目前年級", user_profile.get("grade", "7年級"))
    with c2:
        st.metric("教材版本", f"{publisher}版")
    with c3:
        st.metric("核心知識點", len(core_map))

    semester_options = [s for s in ("七上", "七下") if s in semesters]
    if not semester_options:
        st.warning("這個版本尚未建立國一學期資料。")
        return True

    semester = st.radio(
        "選擇學期",
        semester_options,
        horizontal=True,
        key="g7_learning_map_semester",
    )
    units = semesters.get(semester, {}).get("units", [])
    if not units:
        st.warning("這個學期的主單元資料正在整理中。")
        return True

    unit_names = [u.get("name", "未命名主單元") for u in units]
    selected_unit_name = st.selectbox(
        "選擇主單元",
        unit_names,
        key="g7_learning_map_unit",
    )
    unit = next(
        (u for u in units if u.get("name") == selected_unit_name),
        units[0],
    )

    st.markdown(f"## {selected_unit_name}")
    st.caption(
        f"{data.get('stage', '國一學習地圖第一階段')}｜"
        "學習紀錄未來會以核心 ID 儲存，不受出版社名稱變動影響。"
    )

    subunits = unit.get("subunits", [])
    for index, subunit in enumerate(subunits):
        section = str(subunit.get("section", "")).strip()
        sub_name = str(subunit.get("name", "次單元")).strip()
        title = f"📘 {section} {sub_name}".strip()

        with st.expander(title, expanded=(index == 0)):
            for core_id in subunit.get("core_ids", []):
                core = core_map.get(core_id, {})
                st.markdown(f"**核心 ID：** `{core_id}`")
                if core.get("core_subunit"):
                    st.markdown(f"**核心概念：** {core['core_subunit']}")
                if core.get("curriculum_codes"):
                    st.markdown(
                        "**108 課綱碼：** "
                        + "、".join(core.get("curriculum_codes", []))
                    )
                concepts = core.get("concepts", [])
                if concepts:
                    st.markdown("**本次單元涵蓋：**")
                    for concept in concepts:
                        st.markdown(f"- {concept}")

                question_catalog = core.get("question_type_catalog", [])
                if question_catalog:
                    st.markdown("**常見考法題型：**")
                    for q in question_catalog:
                        q_name = str(q.get("name", "")).strip()
                        q_type_id = str(q.get("type_id", "")).strip()
                        q_category = str(q.get("category", "")).strip()
                        q_difficulty = str(q.get("difficulty", "")).strip()
                        q_feature = str(q.get("feature", "")).strip()
                        q_error = str(q.get("common_error", "")).strip()

                        heading = f"- **{q_name}**"
                        meta = "｜".join(
                            x for x in [q_category, q_difficulty] if x
                        )
                        if meta:
                            heading += f"　`{meta}`"
                        st.markdown(heading)

                        q_diagnostic = str(q.get("diagnostic_clue", "")).strip()
                        q_skill = str(q.get("skill", "")).strip()
                        q_principle = str(q.get("principle", "")).strip()
                        q_frequency = q.get("frequency", {}) or {}
                        q_evidence = q.get("exam_evidence", []) or []

                        if q_feature:
                            st.caption(f"出題特徵：{q_feature}")
                        if q_error:
                            st.caption(f"常見錯誤：{q_error}")
                        if q_diagnostic:
                            st.markdown(f"**🔎 錯誤診斷：** {q_diagnostic}")
                        if q_skill:
                            st.markdown(f"**🧭 解題技巧：** {q_skill}")
                        if q_principle:
                            st.markdown(f"**🧠 原理原則：** {q_principle}")

                        evidence_count = int(q_frequency.get("evidence_count", 0) or 0)
                        year_count = int(q_frequency.get("year_count", 0) or 0)
                        signal = str(q_frequency.get("signal", "")).strip()
                        years = q_frequency.get("years", []) or []

                        if evidence_count > 0:
                            year_text = "、".join(str(y) for y in years)
                            st.markdown(
                                f"**📊 106～115 會考實證：** "
                                f"至少 {evidence_count} 題／{year_count} 個年度"
                                + (f"｜**{signal}**" if signal else "")
                            )
                            if year_text:
                                st.caption(f"明確掛標年度：{year_text}")

                            if q_evidence:
                                with st.expander("查看歷屆試題證據", expanded=False):
                                    for ev in q_evidence:
                                        ev_year = ev.get("year", "")
                                        ev_q = ev.get("question", "")
                                        ev_summary = ev.get("summary", "")
                                        ev_conf = ev.get("confidence", "")
                                        st.markdown(
                                            f"- **{ev_year} {ev_q}**"
                                            + (f"　`掛標信心：{ev_conf}`" if ev_conf else "")
                                        )
                                        if ev_summary:
                                            st.caption(ev_summary)
                        else:
                            st.caption(
                                "📊 十年實證：目前尚無明確掛標；"
                                "不代表未考過，可能屬跨單元或尚未完成精確掛標。"
                            )

                        if q_type_id:
                            st.caption(f"題型 ID：{q_type_id}")
                elif core.get("question_types"):
                    st.markdown(
                        "**常見考法題型：** "
                        + "、".join(core.get("question_types", []))
                    )
                else:
                    st.caption("常見考法題型：資料整理中")

                # 題型資料已逐題顯示解題技巧與原理原則時，
                # 不再把整個次單元的所有技巧／原理於底部重複串成一大段。
                # 舊資料沒有題型明細時，才保留核心層摘要。
                if not question_catalog:
                    if core.get("skills"):
                        st.markdown(
                            "**解題技巧：** "
                            + "、".join(core.get("skills", []))
                        )
                    if core.get("principles"):
                        st.markdown(
                            "**原理原則：** "
                            + "、".join(core.get("principles", []))
                        )

    st.success(
        "✅ 目前這張國一地圖已直接使用 Excel 母表轉出的 learning_map_g7.json。"
    )
    return True


def render_learning_map(user_profile: Dict[str, Any], is_trial: bool = False) -> None:
    """依學生年級與版本顯示學習地圖。"""
    if _render_g7_learning_map(user_profile):
        return

    st.subheader("🌳 學習地圖")
    st.info(
        "依照學生的年級與版本顯示主單元、次單元、重點提示、例題與經典題型。"
        "目前先提供『五年級・康軒版・上學期』前三個單元；題組按鈕仍為準備中，不會扣點。"
    )

    data = _load_data()
    if not data:
        st.error("找不到 curriculum_map.json，請確認它與 app.py 放在同一個資料夾。")
        return

    current_grade = user_profile.get("grade", "")
    current_version = user_profile.get("version", "")
    normalized_grade = _normalize_grade(current_grade)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("目前年級", current_grade or "未設定")
    with c2:
        st.metric("目前版本", current_version or "未設定")
    with c3:
        st.metric("題組單位", "每組 5 題")

    demo = data.get("demo", {})
    demo_grade = str(demo.get("grade", "5"))
    demo_version = demo.get("version", "康軒版")

    if normalized_grade != demo_grade or current_version != demo_version:
        st.warning(
            f"目前示範資料為：{demo.get('display_name', '五年級・康軒版・上學期')}。"
            "你的個人資料尚未有對應課程地圖，因此先顯示示範內容供測試。"
        )

    st.markdown(f"### {demo.get('display_name', '五年級・康軒版・上學期')}")
    st.caption(demo.get("note", "示範資料，後續會由老師校對並持續擴充。"))

    semester_options = list(demo.get("semesters", {}).keys())
    if not semester_options:
        st.warning("課程地圖尚未建立學期資料。")
        return

    semester = st.radio(
        "選擇學期",
        semester_options,
        horizontal=True,
        key="learning_map_semester",
    )
    semester_data = demo["semesters"].get(semester, {})
    units = semester_data.get("units", [])

    if not units:
        st.warning("這個學期的單元資料正在整理中。")
        return

    unit_names = [u.get("name", "未命名單元") for u in units]
    selected_name = st.selectbox(
        "選擇主單元",
        unit_names,
        key="learning_map_unit",
    )
    unit = next((u for u in units if u.get("name") == selected_name), units[0])

    st.markdown(f"## {unit.get('name', '')}")
    if unit.get("summary"):
        st.write(unit["summary"])

    subunits = unit.get("subunits", [])
    if subunits:
        st.markdown("### 次單元與學習重點")
        st.caption("先展開次單元，再選擇其中一個重點，即可查看提示、例題與解法。")

        for sub_idx, subunit in enumerate(subunits):
            sub_name = subunit.get("name", "次單元")
            description = subunit.get("description", "")
            topics = subunit.get("topics", [])

            with st.expander(f"📘 {sub_name}", expanded=(sub_idx == 0)):
                if description:
                    st.write(description)

                if topics:
                    topic_names = [t.get("name", "學習重點") for t in topics]
                    selected_topic_name = st.selectbox(
                        "選擇學習重點",
                        topic_names,
                        key=f"learning_topic_{unit.get('id', 'unit')}_{sub_idx}",
                    )
                    selected_topic = next(
                        (t for t in topics if t.get("name") == selected_topic_name),
                        topics[0],
                    )
                    _render_topic_detail(selected_topic)
                else:
                    old_points = subunit.get("key_points", [])
                    for point in old_points:
                        st.markdown(f"- {point}")

    classic_types = unit.get("classic_question_types", [])
    if classic_types:
        st.markdown("### 經典題型、例題與解答")
        if classic_types and isinstance(classic_types[0], str):
            st.write("、".join(classic_types))
        else:
            for idx, item in enumerate(classic_types):
                _render_classic_type(
                    item,
                    key=f"classic_{unit.get('id', 'unit')}_{idx}",
                )

    st.markdown("---")
    st.markdown("### 五題題組")
    st.caption("題組內容完成審核後再開放，避免誤扣點數。")

    for group in unit.get("pack_groups", []):
        _render_pack_group(unit.get("id", "unit"), group)
        st.markdown("")

    st.success(
        "目前學習地圖只提供學習說明與題組入口，不會呼叫 Gemini，也不會扣除點數。"
    )
