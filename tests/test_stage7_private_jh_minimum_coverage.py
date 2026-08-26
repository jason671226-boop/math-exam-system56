import csv

from scripts import stage7_private_jh_minimum_coverage as cover


def test_set_cover_is_deterministic_and_fingerprint_unique():
    items=cover._items();a=cover.select_plan(items,*cover.PLAN_TARGETS["PLAN_B_BALANCED"]);b=cover.select_plan(items,*cover.PLAN_TARGETS["PLAN_B_BALANCED"])
    assert a==b and len(a)==len(set(a))


def test_all_plans_include_mandatory_p3_new_skills_and_styles():
    items=cover._items();universe=cover._universes(items)
    for name,target in cover.PLAN_TARGETS.items():
        selected=cover.select_plan(items,*target);cov=cover._coverage(selected,items,universe)
        assert all(x["fingerprint"] in selected for x in items if x["priority"]=="P3")
        assert cov["new_skills"]==universe["new_skills"] and cov["styles"]==universe["styles"]


def test_plan_thresholds_and_balanced_recommendation():
    status=cover.build();a,b,c=(status["plans"][x] for x in ("PLAN_A_STRICT","PLAN_B_BALANCED","PLAN_C_MINIMUM"))
    assert a["micro_coverage"]>=80
    assert b["micro_coverage"]>=70 and b["topic_coverage"]>=80 and b["assessment_coverage"]==100
    assert c["micro_coverage"]>=60 and c["topic_coverage"]>=70
    assert status["recommendation"]["selected_plan"]=="PLAN_B_BALANCED"


def test_deferred_traceability_and_no_fake_validation():
    status=cover.build()
    with cover.DEFERRED.open(encoding="utf-8-sig",newline="") as handle:rows=list(csv.DictReader(handle))
    assert all(r["status"]=="DEFERRED_AUDIT" and r["covered_by_teacher_question"] for r in rows)
    assert all(r["shared_skill"] or (r["shared_topic"] and r["shared_assessment_style"]) for r in rows)
    assert status["deferred_human_validated"]==0


def test_teacher_and_deferred_are_bom_disjoint_and_complete():
    status=cover.build();assert cover.TEACHER_SET.read_bytes().startswith(b"\xef\xbb\xbf") and cover.DEFERRED.read_bytes().startswith(b"\xef\xbb\xbf")
    with cover.TEACHER_SET.open(encoding="utf-8-sig",newline="") as h:teacher=list(csv.DictReader(h))
    with cover.DEFERRED.open(encoding="utf-8-sig",newline="") as h:deferred=list(csv.DictReader(h))
    assert len(teacher)+len(deferred)==57
    assert len(teacher)==status["recommendation"]["teacher_questions"] and len(deferred)==status["recommendation"]["deferred_questions"]
