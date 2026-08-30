import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/question_research/mvp_integration'
def load(n): return json.loads((OUT/n).read_text(encoding='utf8'))
def test_all_18_assets_verified():
 r=load('tcte_official_asset_registry.json'); assert r['count']==18 and r['integrity']
 assert all(x['source_verified'] and x['sha256_verified'] for x in r['assets'])
def test_candidates_are_official_pairs():
 d=load('tcte_basic_algebra_candidates.json'); assert d['count']>=0
 for x in d['items']: assert x['source_id'].startswith('TCTE_') and x['answer_linkage_verified']
def test_approved_pool_is_gate_safe(): assert load('approved_pilot_pool.json')['count']>=20
def test_no_production_mutation():
    q=load('tcte_mvp_qa_report.json'); assert q['integrity']=='PASS'; assert q['production_mutations']==0 and q['staging_mutations']==0
