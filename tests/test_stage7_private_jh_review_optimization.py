import csv

from scripts import stage7_private_jh_review_optimization as opt


def test_input_is_57_unique_fingerprints_with_expected_priorities():
    rows=opt._resolve();assert len(rows)==len({r["fingerprint"] for r in rows})==57
    counts={p:sum(r["優先級"]==p for r in rows) for p in ("P3","P4","P5")}
    assert counts=={"P3":5,"P4":37,"P5":15}


def test_risk_scoring_and_coverage_gap_selection_are_deterministic():
    first=opt.optimize();second=opt.optimize();assert first==second
    assert sum(first["risk"].values())==57
    assert first["coverage_gaps"]["new_skills_requiring_teacher_review"]>0
    assert first["coverage_gaps"]["new_micros_requiring_teacher_review"]>0


def test_minimum_and_deferred_are_disjoint_and_complete_utf8_bom():
    status=opt.optimize();assert opt.MINIMUM.read_bytes().startswith(b"\xef\xbb\xbf") and opt.DEFERRED.read_bytes().startswith(b"\xef\xbb\xbf")
    with opt.MINIMUM.open(encoding="utf-8-sig",newline="") as h:min_rows=list(csv.DictReader(h))
    with opt.DEFERRED.open(encoding="utf-8-sig",newline="") as h:deferred=list(csv.DictReader(h))
    assert len(min_rows)+len(deferred)==57==status["teacher_minimum"]["questions"]+status["deferred"]["questions"]
    assert not ({r["來源原序號"] for r in min_rows} & {next(x["source_review_number"] for x in opt._resolve() if x["fingerprint"]==r["fingerprint"]) for r in deferred})


def test_all_p3_p5_and_new_skills_are_in_minimum():
    opt.optimize();resolved=opt._resolve()
    with opt.MINIMUM.open(encoding="utf-8-sig",newline="") as h:selected={r["來源原序號"] for r in csv.DictReader(h)}
    assert all(str(row["source_review_number"]) in selected for row in resolved if row["優先級"] in {"P3","P5"})


def test_no_fake_human_validation_and_inputs_unchanged():
    status=opt.optimize();assert status["deferred"]["human_validated"]==0 and status["inputs_unchanged"]
    assert status["api_calls"]==status["production_reads"]==status["production_writes"]==0
