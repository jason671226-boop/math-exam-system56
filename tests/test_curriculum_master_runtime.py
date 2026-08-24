import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from services.curriculum_master_runtime import CurriculumMasterRuntime, CurriculumRouteError


def make_fixture() -> str:
    handle=tempfile.NamedTemporaryFile(suffix='.zip',delete=False)
    handle.close()
    path=Path(handle.name)
    def csv_text(headers, rows):
        s=io.StringIO(); w=csv.writer(s); w.writerow(headers); w.writerows(rows); return s.getvalue()
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('G1-G12_GLOBAL_QA_SUMMARY.csv',csv_text(['Metric','Result','Status'],[['Release gate','PASS','PASS']]))
        packs=['grade_packs/G5','grade_packs/G9','grade_packs/G10_GENERAL','grade_packs/G11_A','grade_packs/G11_B','grade_packs/G12_A','grade_packs/G12_B','high_school_tracks/TECHNICAL/TECH_C/G10']
        ids={'grade_packs/G9':'G09-S-INSCRIBED-01'}
        for i,p in enumerate(packs,1):
            sid=ids.get(p,f'TEST-{i}')
            z.writestr(p+'/standard_skills.csv',csv_text(['skill_id','official_code','main_unit','subunit','skill_name','focus','difficulty'],[[sid,'X','主單元','次單元','測試Skill','測試重點',3]]))
            z.writestr(p+'/layer2_micro_skills.csv',csv_text(['micro_skill_id','parent_skill_id','official_code','main_unit','subunit','skill_name','question_type','focus','item_pattern','common_error','difficulty'],[[sid+'-C1',sid,'X','主單元','次單元','測試Skill','概念','辨識','pattern','error',1]]))
            z.writestr(p+'/prerequisite_graph.csv',csv_text(['skill_id','prerequisites','graph_status','missing_refs'],[[sid,'','ready','']]))
            z.writestr(p+'/OUT_OF_SCOPE_RULES.md','# scope\nfixture rules\n')
    return str(path)

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=make_fixture(); self.runtime=CurriculumMasterRuntime(self.fixture)
    def tearDown(self): Path(self.fixture).unlink(missing_ok=True)
    def test_release_gate(self): self.assertEqual(self.runtime.validate()['release_gate'],'PASS')
    def test_routes(self):
        cases=[('G5',None,None,'grade_packs/G5'),('G10','GENERAL',None,'grade_packs/G10_GENERAL'),('G11','GENERAL','A','grade_packs/G11_A'),('G11','GENERAL','B','grade_packs/G11_B'),('G12','GENERAL','甲','grade_packs/G12_A'),('G12','GENERAL','乙','grade_packs/G12_B'),('G10','TECHNICAL','C','high_school_tracks/TECHNICAL/TECH_C/G10')]
        for grade,system,track,expected in cases:
            with self.subTest(grade=grade,system=system,track=track): self.assertEqual(self.runtime.resolve_route(grade,education_system=system,track=track).pack_relpath,expected)
    def test_ambiguous_high_school_rejected(self):
        with self.assertRaises(CurriculumRouteError): self.runtime.resolve_route('G11',education_system='GENERAL')
        with self.assertRaises(CurriculumRouteError): self.runtime.resolve_route('G12',education_system='GENERAL')
    def test_context(self):
        route=self.runtime.resolve_route('G9'); ctx=self.runtime.get_skill_context(route,'G09-S-INSCRIBED-01')
        self.assertGreater(len(ctx.micro_skills),0); self.assertTrue(ctx.scope_rules)
if __name__=='__main__': unittest.main()
