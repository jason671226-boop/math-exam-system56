"""Research-only approved pilot adapter; never writes production data."""
from __future__ import annotations
from dataclasses import dataclass
from random import Random
from typing import Any, Mapping

REQUIRED=('question_id','source_id','knowledge_id','micro_skill_id','question_type_id','question_text','answer')
def validate_export(item: Mapping[str,Any]) -> tuple[bool,list[str]]:
    missing=[k for k in REQUIRED if item.get(k) in (None,'')]
    # Technical-high-school assessment assets may legitimately span grades;
    # accept a verified scope while retaining the legacy single-grade field.
    if item.get('grade') in (None,'') and item.get('grade_scope') in (None,'') and item.get('verified_grade_scope') in (None,''):
        missing.append('grade_or_grade_scope')
    for flag in ('source_verified','question_verified','taxonomy_mapping_verified','duplicate_resolved'):
        if item.get(flag) is not True: missing.append(flag)
    if item.get('rights_status') in (None,'UNKNOWN','NEEDS_RIGHTS_REVIEW_NONCOMMERCIAL'): missing.append('rights_status')
    return (not missing,missing)

class ApprovedPilotLoader:
    def __init__(self, items): self.items=tuple(items)
    def valid_items(self): return tuple(x for x in self.items if validate_export(x)[0])
    def load(self, *, grade=None, grade_scope=None, curriculum_track=None, semester=None, knowledge_id=None, micro_skill_id=None, question_type_id=None, difficulty=None):
        xs=self.valid_items()
        filters={'grade':grade,'grade_scope':grade_scope,'curriculum_track':curriculum_track,'semester':semester,'knowledge_id':knowledge_id,'micro_skill_id':micro_skill_id,'question_type_id':question_type_id,'difficulty':difficulty}
        return tuple(x for x in xs if all(v is None or x.get(k)==v for k,v in filters.items()))

class QuestionBankAdapter:
    def __init__(self, loader, seed=0): self.loader=loader; self.rng=Random(seed)
    def draw(self, count=5, **filters):
        xs=list(self.loader.load(**filters)); self.rng.shuffle(xs); return tuple(xs[:count])
    def answer(self,item): return {'question_id':item['question_id'],'answer':item['answer'],'solution':item['solution']}
    def evidence(self, item, student_id, correct, attempts=1, hints=0, source_type='autonomous_test'):
        return {'student_id':student_id,'question_id':item['question_id'],'knowledge_id':item['knowledge_id'],'micro_skill_id':item['micro_skill_id'],'question_type_id':item['question_type_id'],'thinking_skill_ids':item.get('thinking_skill_ids',[]),'difficulty':item.get('difficulty','standard'),'correct':bool(correct),'attempts':attempts,'hints':hints,'source_type':source_type}
    def recommendation(self, knowledge_id, reason='targeted_practice', question_type='default'):
        return {'next_action':'PRACTICE','recommendation_reason':reason,'target_knowledge_id':knowledge_id,'target_question_type':question_type,'suggested_pack':5}
