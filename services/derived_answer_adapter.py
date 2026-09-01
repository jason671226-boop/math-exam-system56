"""Confirmed-question to structured derived-answer adapter (private beta)."""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

class ContractValidationError(ValueError): pass

@dataclass(frozen=True)
class ConfirmedQuestion:
    question_text: str
    answer_request: str
    question_id: str|None = None
    request_id: str|None = None
    formula_representation: str|None = None
    choice_options: Mapping[str,str]|None = None
    source_type: str|None = None
    source_asset_ref: str|None = None
    crop_ref: str|None = None
    image_ref: str|None = None
    extraction_confidence: float|None = None
    human_confirmed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    def validate(self):
        if not self.question_text.strip(): raise ContractValidationError('question_text must be non-empty')
        if not self.answer_request.strip(): raise ContractValidationError('answer_request must be non-empty')
        if self.choice_options:
            keys={str(k).upper() for k in self.choice_options}
            if keys != {'A','B','C','D'}: raise ContractValidationError('multiple-choice options must contain A/B/C/D')
            if any(not str(v).strip() for v in self.choice_options.values()): raise ContractValidationError('choice options must be non-empty')
        return self
    def solver_payload(self):
        self.validate(); return asdict(self)

@dataclass(frozen=True)
class DerivedAnswerResult:
    status: str
    derived_answer: str|None=None
    derived_answer_normalized: str|None=None
    derived_option: str|None=None
    confidence: float|None=None
    reasoning_summary: str|None=None
    verification_summary: str|None=None
    review_required: bool=False
    warnings: tuple[str,...]=()
    provider: str='gemini'
    fallback_used: bool=False
    error_code: str|None=None
    def to_public_dict(self): return asdict(self)

def build_solver_prompt(q: ConfirmedQuestion)->str:
    q.validate(); opts=q.choice_options or {}
    option_text='\n'.join(f'{k}: {opts[k]}' for k in ('A','B','C','D') if k in opts)
    return ('Solve the confirmed mathematics question. First derive the mathematical result, then map to an option, and independently verify. Return JSON only with keys: answer, normalized_answer, option, confidence, reasoning_summary, verification_summary, review_required. Keep summaries concise.\n\nQuestion:\n'+q.question_text.strip()+'\nFormula:\n'+(q.formula_representation or '')+'\nAnswer request:\n'+q.answer_request.strip()+'\nOptions:\n'+option_text)

def parse_derived_response(raw: str, *, provider='gemini')->DerivedAnswerResult:
    try:
        text=(raw or '').strip()
        if text.startswith('```'): text=text.strip('`').split('\n',1)[-1]
        obj=json.loads(text)
        if not isinstance(obj,dict): raise ValueError('not object')
        answer=obj.get('answer',obj.get('derived_answer')); norm=obj.get('normalized_answer',obj.get('derived_answer_normalized'))
        conf=obj.get('confidence'); conf=float(conf) if conf is not None else None
        if conf is not None and not 0<=conf<=1: raise ValueError('bad confidence')
        if not answer or not norm: raise ValueError('missing answer')
        return DerivedAnswerResult('SUCCESS',str(answer),str(norm),obj.get('option'),conf,str(obj.get('reasoning_summary','')),str(obj.get('verification_summary','')),bool(obj.get('review_required',False)),tuple(map(str,obj.get('warnings',[]) or [])),provider,False,None)
    except Exception:
        return DerivedAnswerResult('REVIEW_REQUIRED',review_required=True,warnings=('Structured solver response could not be parsed.',),provider=provider,error_code='INVALID_STRUCTURED_RESPONSE')

def derive_answer(q: ConfirmedQuestion, provider: Callable[[list[Any]],str], *, provider_name='gemini')->DerivedAnswerResult:
    try: return parse_derived_response(provider([build_solver_prompt(q)]),provider=provider_name)
    except Exception: return DerivedAnswerResult('ERROR',review_required=True,warnings=('Solver provider unavailable; confirm the question and try again.',),provider=provider_name,error_code='PROVIDER_ERROR')

def history_payload(q: ConfirmedQuestion, r: DerivedAnswerResult):
    q.validate(); return {'original_mistake':q.question_text.strip(),'derived_answer':r.derived_answer_normalized,'review_required':r.review_required,'provider':r.provider}
