from services.question_bank.adapter import ApprovedPilotLoader,QuestionBankAdapter
def item(): return {'question_id':'q1','source_id':'s1','grade':'G5','knowledge_id':'G5-K001','micro_skill_id':'G5-K001-M1','question_type_id':'G5-K001-Q01','question_text':'x+1=2','answer':'1','solution':'x=1','source_verified':True,'question_verified':True,'taxonomy_mapping_verified':True,'duplicate_resolved':True,'rights_status':'PUBLIC_OFFICIAL_RESEARCH_ONLY'}
def test_filter_draw_answer():
 a=QuestionBankAdapter(ApprovedPilotLoader([item()]),seed=1); xs=a.draw(1,grade='G5'); assert len(xs)==1; assert a.answer(xs[0])['answer']=='1'
def test_invalid_rejected():
 bad=item(); bad['taxonomy_mapping_verified']=False; assert ApprovedPilotLoader([bad]).valid_items()==()
def test_evidence_mastery_recommendation():
 a=QuestionBankAdapter(ApprovedPilotLoader([item()])); x=item(); assert a.evidence(x,'LOCAL',True)['question_id']=='q1'; assert a.recommendation('G5-K001')['next_action']=='PRACTICE'
