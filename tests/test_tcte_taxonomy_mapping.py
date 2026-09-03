import json
from pathlib import Path
from services.question_bank.adapter import ApprovedPilotLoader

OUT=Path('data/question_research/mvp_integration')

def test_tcte_mapping_pool_is_research_only_and_scoped():
    d=json.loads((OUT/'approved_pilot_pool.json').read_text(encoding='utf-8'))
    assert d['count'] == len(d['items'])
    assert d['count'] >= 20
    assert all(x['source_verified'] and x['answer_linkage_verified'] for x in d['items'])
    assert all(x['curriculum_track']=='TECH-A' for x in d['items'])
    assert all(x['taxonomy_mapping_verified'] and x['knowledge_id'] and x['micro_skill_id'] for x in d['items'])
    assert all(x.get('grade_scope') and x.get('assessment_stage')=='TECH_HIGH_SCHOOL_EXIT_EXAM' for x in d['items'])

def test_scope_accepted_without_single_grade():
    d=json.loads((OUT/'approved_pilot_pool.json').read_text(encoding='utf-8'))
    assert len(ApprovedPilotLoader(d['items']).valid_items()) == d['count']
