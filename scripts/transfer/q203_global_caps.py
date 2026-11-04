#!/usr/bin/env python3
"""Q203: whole-body flat-cap census of the own-model bundles (continuations merged into the structure they continue, as in the audits).
    python3 scripts/transfer/q203_global_caps.py  ->  data/derived/Q203_global_caps.json
A flat cap = axis-aligned planar end face >= 40 mm2 at an extreme of a structure (Q198 definition via q200_continue.find_caps), skin / organs excluded."""
import json
import re
import sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle
from scripts.transfer.q200_continue import find_caps
from scripts.transfer.q200_merge import merge_structure

SUF = re.compile(r"_zfill(203s?)?$")


def census(bdir, body, seams_files):
    B = Bundle(REPO / bdir)
    seams = {}
    for f in seams_files:
        p = REPO / "data/derived" / f.format(body=body)
        if p.exists():
            seams.update(json.loads(p.read_text()))
    ents = {}
    for it in B.items:
        v, f = B.mesh(it)
        ents.setdefault(it["e"]["id"], []).append((it, v, f))
    rows = []
    for i, lst in ents.items():
        it, v, f = lst[0]
        e = it["e"]
        if SUF.search(i) or e["cat"] in ("organ",) or i == "skin" or e["cat"] in ("vessel", "nerve"):
            continue
        for it2, v2, f2 in lst:
            vv, ff = v2, f2
            for nid in (i + "_zfill", i + "_zfill203", i + "_zfill203s"):
                if nid in ents and len(lst) == 1:
                    pv, pf = ents[nid][0][1], ents[nid][0][2]
                    vv, ff, _ = merge_structure(vv, ff, pv, pf, seams.get(nid, []), weld=True)
            for c in find_caps(vv, ff, minarea=40.0, at_end=2.0):
                rows.append(dict(id=i, cat=e["cat"], axis=c["axis"], pos=round(c["pos"], 1), area=round(c["area"], 1)))
    area = sum(r["area"] for r in rows)
    out = {}
    for cat in ("muscle", "tendon", "bone", "other"):
        sel = [r for r in rows if (r["cat"] == cat or (cat == "other" and r["cat"] not in ("muscle", "tendon", "bone")))]
        out[cat] = dict(caps=len(sel), structures=len({r["id"] for r in sel}), area_mm2=round(sum(r["area"] for r in sel)))
    return dict(caps=len(rows), structures=len({r["id"] for r in rows}), area_mm2=round(area), by_cat=out, top=sorted(rows, key=lambda r: -r["area"])[:15])


res = {}
for body, q200, q203 in (("vhm", "build/viewer_m_hr_q200", "build/viewer_m_hr_q203"), ("vhf", "build/viewer_f_hr_q200", "build/viewer_f_hr_q203")):
    res[body] = dict(before_q200=census(q200, body, ["Q200_seams_{body}.json"]), after_q203=census(q203, body, ["Q200_seams_{body}.json", "Q203_seams_{body}.json"]))
    b, a = res[body]["before_q200"], res[body]["after_q203"]
    print(body, "flat caps", b["caps"], "->", a["caps"], "| structures", b["structures"], "->", a["structures"], "| area mm2", b["area_mm2"], "->", a["area_mm2"])
(REPO / "data/derived/Q203_global_caps.json").write_text(json.dumps(res, indent=1))
