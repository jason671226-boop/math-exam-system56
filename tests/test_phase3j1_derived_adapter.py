import json
import pytest
from services.derived_answer_adapter import ConfirmedQuestion, ContractValidationError, parse_derived_response, derive_answer, history_payload

def test_confirmed_question_contract():
    q=ConfirmedQuestion(question_text="2x+1=3", answer_request="solve x", choice_options={"A":"0","B":"1","C":"2","D":"3"})
    assert q.validate().solver_payload()["question_text"]=="2x+1=3"

def test_empty_question_rejected():
    with pytest.raises(ContractValidationError): ConfirmedQuestion(question_text="",answer_request="solve").validate()

def test_structured_parse_and_history():
    r=parse_derived_response(json.dumps({"answer":"1","normalized_answer":"1","option":"B","confidence":0.95,"reasoning_summary":"isolate x","verification_summary":"substitute","review_required":False}))
    assert r.status=="SUCCESS" and r.derived_option=="B"
    q=ConfirmedQuestion(question_text="2x+1=3",answer_request="solve x")
    assert history_payload(q,r)["derived_answer"]=="1"

def test_malformed_requires_review():
    assert parse_derived_response("not json").review_required

def test_provider_is_mocked_and_no_gold_in_prompt():
    seen=[]
    def provider(parts): seen.extend(parts); return json.dumps({"answer":"1","normalized_answer":"1","confidence":0.9,"reasoning_summary":"ok","verification_summary":"ok"})
    r=derive_answer(ConfirmedQuestion(question_text="2x+1=3",answer_request="solve"),provider)
    assert r.status=="SUCCESS" and "official_answer" not in seen[0] and "correct option" not in seen[0].lower()
