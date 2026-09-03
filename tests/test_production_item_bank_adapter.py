from services.question_bank.production_item_bank import select_g5_questions

class _Query:
    def __init__(self, rows): self.rows=rows
    def select(self, *_): return self
    def eq(self, *_): return self
    def ilike(self, *_): return self
    def limit(self, *_): return self
    def execute(self): return type("R", (), {"data": self.rows})()

class _Client:
    def __init__(self, rows): self.rows=rows
    def table(self, _): return _Query(self.rows)

def test_g5_selection_is_production_only_and_bounded():
    rows=[{"id":1,"index_code":"QB2C-G5-X","grade":"5","unit":"數與計算","knowledge_tag":"G05-K","new_question":"2+2=?","correct_answer":"4"}]
    out=select_g5_questions(_Client(rows), count=1, units=("數與計算",))
    assert len(out)==1 and out[0]["source"]=="PRODUCTION_ITEM_BANK" and out[0]["grade"]=="G5"
