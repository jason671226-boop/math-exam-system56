import os, unittest
from services.curriculum_master_feature import curriculum_master_v27_enabled
class FeatureTests(unittest.TestCase):
    def test_flag_off_default(self):
        old=os.environ.pop('CURRICULUM_MASTER_V27_ENABLED',None)
        try: self.assertFalse(curriculum_master_v27_enabled())
        finally:
            if old is not None: os.environ['CURRICULUM_MASTER_V27_ENABLED']=old
if __name__=='__main__': unittest.main()
