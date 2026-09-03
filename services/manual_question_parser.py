import re

def parse_manual_question(raw: str) -> dict:
    text = (raw or "").strip()
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    choices = {}
    kept = []
    for line in lines:
        m = re.match(r"^\(?([ABCD])\)?[\s:：、.-]+(.+)$", line, re.I)
        if m: choices[m.group(1).upper()] = m.group(2).strip()
        else: kept.append(line)
    body = "\n".join(kept)
    formula = None
    for m in re.finditer(r"(?<![A-Za-z0-9])([0-9A-Za-zα-ωΑ-Ω]+(?:\s*[+\-*/=]\s*[0-9A-Za-zα-ωΑ-Ω]+)+)", body):
        formula = m.group(1).strip(); break
    request = None
    m = re.search(r"求\s*([A-Za-z][A-Za-z0-9_]*)", body)
    if m: request = "求 " + m.group(1)
    return {"question_text": body, "formula_representation": formula, "choice_options": choices or None, "answer_request": request or "Solve this question"}
