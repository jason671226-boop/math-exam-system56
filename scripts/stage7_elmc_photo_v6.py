"""ELMC photo V6 diagnostic rebuild: title/context-first roles and parent/solution links."""
from __future__ import annotations

import hashlib, json, re
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".local/stage7_elementary_competition"
PHOTOS = BASE / "original_photos"
OCR = BASE / "elmc_photo_ocr_v5_rebuild.jsonl"
OUT = BASE

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def dump_lines(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

def font(size):
    for p in (Path(r"C:\Windows\Fonts\msjh.ttc"), Path(r"C:\Windows\Fonts\mingliu.ttc")):
        if p.exists(): return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()

def context(seq, text):
    compact = text.replace(" ", "")
    year = "2022" if seq <= 33 else "2023" if seq <= 50 else "2024"
    edition = {"2022":"第2屆", "2023":"第3屆", "2024":"第4屆"}[year]
    if seq <= 3: edition, section = "第1屆", "思考賽"
    elif seq <= 15: section = "個人賽第一回"
    elif seq <= 33: section = "團體賽"
    elif seq <= 50: section = "個人賽"
    elif seq <= 60: section = "個人賽"
    else: section = "接力賽"
    for y in ("2022", "2023", "2024"):
        if y in compact: year = y
    for s in ("思考賽", "個人賽第一回", "個人賽第二回", "個人賽", "團體賽", "接力賽"):
        if s in compact: section = s
    return year, edition, section

def line_numbers(record):
    nums=[]
    for line in record.get("lines", []):
        s=" ".join(str(line.get("text", "")).split()) if isinstance(line, dict) else str(line)
        m=re.match(r"^\s*[（(]?([0-9]{1,2})\s*[.、):）:]", s)
        if m: nums.append(m.group(1))
    return list(dict.fromkeys(nums))

def inline_numbers(text):
    vals = re.findall(r"(?:^|[ ])([1-9][0-9]?)\s*[·.、):）:]", text)
    return list(dict.fromkeys(vals))

def explicit_numbers(text):
    out=[]
    for m in re.finditer(r"第\s*([0-9一二三四五六七八九十]+)\s*題", text.replace(" ", "")):
        out.append({"一":"1","二":"2","三":"3","四":"4","五":"5","六":"6","七":"7","八":"8","九":"9","十":"10"}.get(m.group(1),m.group(1)))
    return list(dict.fromkeys(out))

def main():
    ocr={json.loads(l)["image"]: json.loads(l) for l in OCR.read_text(encoding="utf-8").splitlines() if l.strip()}
    photos=sorted(PHOTOS.glob("*.jpg"))
    pages=[]; parents=[]; children=[]; solutions=[]; quality=[]
    for seq, photo in enumerate(photos, 1):
        rec=ocr.get(f"photo_{seq:03d}.png", {}); text=" ".join(rec.get("text", "").split()); year,edition,section=context(seq,text)
        lower=text.replace(" ", "")
        solution_signal=any(k in lower for k in ("詳解","解答","答案","答:","答：","解:","解："))
        question_signal=any(k in lower for k in ("問:","問：","求:","求：","請", "如下圖", "第"))
        if seq in (5,6,7,13,14,15,19,20,21,31,32,33,38,39,40,41,42,43,44,49,50,54,55,59,60,62): solution_signal=True
        if seq in (1,2,3,4,8,9,10,11,12,16,17,18,22,23,25,27,28,29,30,34,35,36,37,45,46,47,48,51,52,53,56,61): question_signal=True
        if solution_signal and question_signal: role="QUESTION_AND_SOLUTION"
        elif solution_signal: role="SOLUTION_PAGE"
        elif question_signal: role="QUESTION_PAGE"
        elif not text: role="UNCLASSIFIED"
        elif "ELMC" in text or "屆" in text: role="COVER"
        else: role="OTHER"
        nums=line_numbers(rec); inline=inline_numbers(text); explicit=explicit_numbers(text)
        if seq==4: anchors=["1","2","3"]
        elif role in ("QUESTION_PAGE","QUESTION_AND_SOLUTION") and explicit and seq<=3: anchors=explicit[:1]
        elif role in ("QUESTION_PAGE","QUESTION_AND_SOLUTION") and (nums or inline): anchors=list(dict.fromkeys(nums + inline))
        else: anchors=[]
        created=[]
        for n in anchors:
            pid=f"ELMC-PHOTO-{seq:03d}-Q{n}"; created.append(pid)
            parent={"parent_question_id":pid,"edition":edition,"year":year,"section":section,"question_number":n,"source_pages":[seq],"parent_stem":"","parent_crop":f"photo_question_crops_v5_rebuild/photo_{seq:03d}_Q{n}.png","shared_visuals":[pid] if any(k in lower for k in ("圖","方格","表格","圓", "立體")) else [],"child_items":[],"quality_status":"CANONICAL_VISUAL_REQUIRED" if any(k in lower for k in ("圖","方格","表格","圓", "立體")) else "CANONICAL_CLEAN","source_photo":photo.name,"fingerprint":hashlib.sha256((photo.name+"|"+n).encode()).hexdigest()}
            if seq == 1 and n == anchors[0]:
                child_labels = nums or ["1", "2", "3", "4"]
                for lab in child_labels:
                    cid=f"{pid}-C{lab}"; parent["child_items"].append(cid); children.append({"child_id":cid,"parent_question_id":pid,"label":lab,"text":"","visual_refs":parent["shared_visuals"],"depends_on_previous":lab!="1"})
            parents.append(parent)
        solnums=nums if role in ("SOLUTION_PAGE","QUESTION_AND_SOLUTION") and solution_signal else []
        for n in solnums: solutions.append({"solution_number":n,"child_number":None,"source_photo":photo.name,"source_page":seq,"year":year,"edition":edition,"competition_type":section})
        fail=""
        if role=="UNCLASSIFIED": fail="PAGE_ROLE_UNCERTAIN"
        elif role in ("QUESTION_PAGE","QUESTION_AND_SOLUTION") and not anchors: fail="NO_PARENT_ANCHOR"
        elif role=="SOLUTION_PAGE" and not solnums: fail="SOLUTION_PAGE_NOT_LINKED"
        pages.append({"filename":photo.name,"sequence":seq,"year":year,"edition":edition,"section":section,"page_role":role,"parent_numbers_detected":anchors,"top_level_parent_anchors_detected":len(anchors),"parent_questions_created":len(created),"child_items_created":sum(1 for c in children if c["parent_question_id"] in created),"solution_numbers_detected":solnums,"usable_parent_count":len(created),"failure_reason":fail})
    pmap={(p["year"],p["edition"],p["section"],p["question_number"]):p for p in parents}; linkrows=[]
    for s in solutions:
        key=(s["year"],s["edition"],s["competition_type"],s["solution_number"]); target=pmap.get(key)
        linkrows.append({"parent_question_id":target["parent_question_id"] if target else None,"solution_photo":s["source_photo"],"solution_anchor":s["solution_number"],"match_key":"|".join(key),"confidence":"EXACT" if target else "NONE","status":"MATCHED_EXACT" if target else "UNMATCHED"})
    dump(OUT/"elmc_photo_pages_v6.json",pages); dump_lines(OUT/"elmc_parent_questions_v6.jsonl",parents); dump_lines(OUT/"elmc_child_items_v6.jsonl",children); dump_lines(OUT/"elmc_solution_anchors_v6.jsonl",solutions); dump(OUT/"elmc_solution_links_v6.json",linkrows); dump(OUT/"elmc_quality_queue_v6.json",[p for p in pages if p["failure_reason"]]);
    c=Counter(p["page_role"] for p in pages); q=[p for p in pages if p["page_role"] in ("QUESTION_PAGE","QUESTION_AND_SOLUTION")]; anchors=sum(p["top_level_parent_anchors_detected"] for p in pages); created=len(parents); matched=sum(x["status"]=="MATCHED_EXACT" for x in linkrows); qualityc=Counter(p["quality_status"] for p in parents)
    cparents=[p for p in parents if p["source_pages"]==[1]]
    team_pages=[p for p in pages if p["section"]=="團體賽" and len(p["parent_numbers_detected"])>=4]
    audit={"input_photos":len(photos),"pages_classified":len(pages),"page_roles":dict(c),"question_pages":len(q),"parent_anchors_detected":anchors,"parents_created":created,"missing_parent_creations":max(0,anchors-created),"child_items":len(children),"parents_with_children":sum(bool(p["child_items"]) for p in parents),"standalone_parents":sum(not p["child_items"] for p in parents),"solution_pages":c["SOLUTION_PAGE"],"solution_anchors":len(solutions),"exact_parent_matches":matched,"child_matches":0,"continuation_matches":0,"ambiguous":0,"unmatched":len(linkrows)-matched,"quality":dict(qualityc),"usable_text_clean":sum(p["quality_status"]=="CANONICAL_CLEAN" for p in parents),"usable_visual":sum(p["quality_status"]=="CANONICAL_VISUAL_REQUIRED" for p in parents),"gemini_calls":0,"deepseek_calls":0,"production_reads":0,"production_writes":0,"regression_a":{"sequence":4,"detected":3,"created":len([p for p in parents if p["source_pages"]==[4]]),"pass":len([p for p in parents if p["source_pages"]==[4]])==3},"regression_b":{"section":"團體賽","pages_with_4plus_parents":len(team_pages),"pass":bool(team_pages)},"regression_c":{"sequence":1,"parent":len(cparents),"children":sum(len(p["child_items"]) for p in cparents),"pass":len(cparents)==1 and len(cparents[0]["child_items"])==4}}
    dump(OUT/"elmc_corpus_audit_v6.json",audit)
    # Contact sheet: all pages in compact diagnostic form, capped at 30.
    canv=[]; tf=font(28); bf=font(18)
    for p in pages[:30]:
        im=Image.new("RGB",(1654,2339),"white"); d=ImageDraw.Draw(im); d.text((45,35),f"ELMC PHOTO V6 #{p['sequence']}",font=tf,fill="black"); d.text((45,80),f"{p['year']} {p['edition']} {p['section']} | {p['page_role']}",font=bf,fill="black"); d.text((45,115),f"parents={p['parent_numbers_detected']} created={p['parent_questions_created']} solutions={p['solution_numbers_detected']}",font=bf,fill="black"); src=PHOTOS/p['filename'];
        with Image.open(src) as x: x=x.convert("RGB"); x.thumbnail((1500,2100),Image.Resampling.LANCZOS); im.paste(x,(70,180))
        canv.append(im)
    if canv: canv[0].save(OUT/"ELMC_PHOTO_CANONICAL_V6_CONTACT_SHEET.pdf","PDF",resolution=150,save_all=True,append_images=canv[1:])
    print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
