#!/usr/bin/env python3
"""Q212: whole-body flat-cap census of the own-model bundles, Q203 (before) vs Q212 (after): same definition as q203_global_caps.py (axis-aligned planar end face >= 40 mm2 at an
extreme of a structure, continuations merged into the structure they continue; skin / organs / vessels / nerves excluded). Wrist re-segmentation (his): the cap of his radius / ulna at
the old label end is covered by the `*_distal_q212` piece (not a free face any more), the superseded grouped carpal mesh is hidden and not counted, `carpals_?_q212` is counted.
    python3 scripts/transfer/q212_global_caps.py  ->  data/derived/Q212_global_caps.json"""
import json, re, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle
from scripts.transfer.q200_continue import find_caps
from scripts.transfer.q200_merge import merge_structure

SUF = re.compile(r"_zfill(203s?|212)?$")
WRIST = re.compile(r"_(distal_)?q212$")


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
        if SUF.search(i) or e["cat"] in ("organ", "vessel", "nerve") or i == "skin" or e.get("hidden_default") or i.endswith("_distal_q212"):
            continue
        for it2, v2, f2 in lst:
            vv, ff = v2, f2
            for suf in ("_zfill", "_zfill203", "_zfill203s", "_zfill212"):
                nid = i + suf
                if nid in ents and len(lst) == 1:
                    vv, ff, _ = merge_structure(vv, ff, ents[nid][0][1], ents[nid][0][2], seams.get(nid, []), weld=True)
            dist = ents.get(i.replace("_", "_", 1) + "_distal_q212") if False else ents.get(f"{i}_distal_q212")
            for c in find_caps(vv, ff, minarea=40.0, at_end=2.0):
                if dist:                                    # cap covered by the CT-resegmented distal piece (same plane region)
                    dv = dist[0][1]; k = "xyz".index(c["axis"])
                    if dv[:, k].min() - 3.0 <= c["pos"] <= dv[:, k].max() + 3.0 and np.linalg.norm(dv.mean(0) - vv[np.unique(ff[c["faces"]])].mean(0)) < 60:
                        continue
                rows.append(dict(id=i, cat=e["cat"], axis=c["axis"], pos=round(c["pos"], 1), area=round(c["area"], 1)))
    out = {}
    for cat in ("muscle", "tendon", "bone", "other"):
        sel = [r for r in rows if (r["cat"] == cat or (cat == "other" and r["cat"] not in ("muscle", "tendon", "bone")))]
        out[cat] = dict(caps=len(sel), structures=len({r["id"] for r in sel}), area_mm2=round(sum(r["area"] for r in sel)))
    return dict(caps=len(rows), structures=len({r["id"] for r in rows}), area_mm2=round(sum(r["area"] for r in rows)), by_cat=out, top=sorted(rows, key=lambda r: -r["area"])[:20], rows=rows)


res = {}
S3 = ["Q200_seams_{body}.json", "Q203_seams_{body}.json"]
for body, q203, q212 in (("vhm", "build/viewer_m_hr_q203", "build/viewer_m_hr_q212"), ("vhf", "build/viewer_f_hr_q203", "build/viewer_f_hr_q212")):
    res[body] = dict(before_q203=census(q203, body, S3), after_q212=census(q212, body, S3 + ["Q212_seams_{body}.json"]))
    b, a = res[body]["before_q203"], res[body]["after_q212"]
    print(body, "flat caps", b["caps"], "->", a["caps"], "| structures", b["structures"], "->", a["structures"], "| area mm2", b["area_mm2"], "->", a["area_mm2"],
          "| muscle", b["by_cat"]["muscle"], "->", a["by_cat"]["muscle"], "| bone", b["by_cat"]["bone"], "->", a["by_cat"]["bone"])
(REPO / "data/derived/Q212_global_caps.json").write_text(json.dumps(res, indent=1))
