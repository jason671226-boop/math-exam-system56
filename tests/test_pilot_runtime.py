from services.question_bank.pilot_runtime import runtime_pilot_status

def test_local_pilot_flag_and_pool():
    s=runtime_pilot_status(); assert s['enabled'] is True; assert s['count'] >= 30
