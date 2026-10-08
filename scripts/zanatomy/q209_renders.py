#!/usr/bin/env python3
"""Q209 renders (READ-ONLY, git-ignored output build/q209_renders/): the worst structure of each page (data/derived/Q209_anatomy_audit.json worst10[0]) in its surroundings:
structure magenta, neighbouring bones cream, neighbouring soft tissue grey-blue; 3 views (front, side, oblique) -> one PNG per page.   python3 scripts/zanatomy/q209_renders.py [MODEL ...]"""
import json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q209_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OUT = REPO / "build" / "q209_renders"


PICKS = {"own_m": None, "own_f": None, "z_male": None, "z_base_f": "zan_middle_genicular_artery_l", "z_male_fit": None, "z_female_fit": None}  # worst10[0] of the Q209 JSON (first not already in the unfitted base for the fits); the generic female differs from the male base by a named structure


def finding(A, k, sid):
    P = A["pages"][k]
    if sid is None:
        w = next((x for x in P["worst10"] if not x["in_unfitted_base"]), P["worst10"][0]) if k.endswith("_fit") else P["worst10"][0]
        return w
    w = next((x for x in P["worst10"] if x["id"] == sid), None)
    if w:
        return w
    from scripts.zanatomy.q204_regions import structure_defects
    raw = json.loads((REPO / "build" / ("q209_raw_merged" if k.startswith("own") else "q209_raw") / f"Q204_regions_{k}.json").read_text())
    r = next(x for x in raw["rows"] if x["id"] == sid)
    ds = sorted(structure_defects(r), key=lambda d: -d["severity"])
    return {"id": sid, "region": r["region"], "side": r["side"], "max_severity": ds[0]["severity"] if ds else 0, "centroid_mm": r["centroid"], "findings": [f"[{d['severity']}] {d['check']}: {d['detail'][:110]}" for d in ds[:3]]}


def main(keys):
    A = json.loads((REPO / "data/derived/Q209_anatomy_audit.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    for k in keys:
        w = finding(A, k, PICKS.get(k))
        S = load(k)
        tgt = next(s for s in S if s["id"] == w["id"])
        c = np.asarray(w["centroid_mm"]); ext = float(np.ptp(tgt["v"], axis=0).max())
        half = float(np.clip(0.62 * ext + 40, 70, 260))
        sc = []
        for s in S:
            if s["sys"] in ("skin",) or s["id"] == "skin" or len(s["f"]) == 0:
                continue
            if s["id"] == tgt["id"]:
                sc.append({"v": s["v"], "f": s["f"], "color": (0.95, 0.05, 0.75)})
                continue
            if s["sys"] not in ("bone", "muscle", "tendon", "ligament", "joint", "cartilage", "fascia", "insertion"):
                continue
            cen = s["v"][s["f"]].mean(1)
            keep = np.linalg.norm(cen - c, axis=1) < half * 1.15
            if keep.sum() < 2:
                continue
            col = (0.93, 0.91, 0.80) if s["sys"] == "bone" else (0.52, 0.60, 0.72)
            sc.append({"v": s["v"], "f": s["f"][keep], "color": col})
        views = [dict(name="front", az=0, el=0, target=c, half=half), dict(name="side", az=90, el=0, target=c, half=half), dict(name="oblique", az=40, el=20, target=c, half=half)]
        d = OUT / k
        R.render(sc, views, d, size=(560, 560))
        ims = [Image.open(d / f"{n}.png").convert("RGB") for n in ("front", "side", "oblique")]
        W = Image.new("RGB", (560 * 3, 560 + 64), (255, 255, 255))
        for i, im in enumerate(ims):
            W.paste(im, (560 * i, 64))
        dr = ImageDraw.Draw(W)
        dr.text((8, 6), f"{A['pages'][k]['label']}  |  {w['id']} ({w['region']}, {w['side']})  max severity {w['max_severity']}  |  magenta = the structure, cream = bones, blue-grey = neighbouring soft tissue", fill=(0, 0, 0))
        for i, t in enumerate(w["findings"][:3]):
            dr.text((8, 22 + 13 * i), t[:230], fill=(120, 0, 0))
        W.save(OUT / f"worst_{k}.png")
        print(k, w["id"], "rendered", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["own_m", "own_f", "z_male", "z_base_f", "z_male_fit", "z_female_fit"])
