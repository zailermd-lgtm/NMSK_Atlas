#!/usr/bin/env python3
"""Q224 renders: the 3 worst places before / after -> build/q224_renders/ (git-ignored) + small copies data/derived/Q224_render_<n>_*.png.
1 own male right femoral vein (62 mm break -> one tube), 2 own female longissimus l (flat sawn end 1308 mm2 -> domed), 3 own female tarsals (grouped male-carried mesh on top of her single tarsals -> removed).
   python3 scripts/transfer/q224_renders.py [1 2 3]"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.transfer.q224_common import BODIES  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OUT = REPO / "build" / "q224_renders"
DER = REPO / "data" / "derived"
MAG, CREAM, BLUE, ORANGE, GREEN = (0.95, 0.05, 0.75), (0.93, 0.91, 0.80), (0.52, 0.60, 0.72), (0.95, 0.55, 0.10), (0.20, 0.65, 0.30)


def window(v, f, c, half):
    cen = v[f].mean(1)
    keep = np.linalg.norm(cen - c, axis=1) < half
    return f[keep] if keep.sum() > 1 else None


def context(B, c, half, systems, skip=()):
    sc = []
    for it in B.items:
        e = it["e"]
        if e["id"] in skip or e["cat"] not in systems or e.get("hidden_default"):
            continue
        v, f = B.mesh(it)
        ff = window(v, f, c, half)
        if ff is not None:
            sc.append({"v": v, "f": ff, "color": CREAM if e["cat"] == "bone" else BLUE})
    return sc


def montage(name, title, lines, before, after, views, size=520):
    d = OUT / name
    ims = []
    for tag, sc in (("before", before), ("after", after)):
        R.render(sc, views, d, size=(size, size), prefix=tag + "_")
        ims.append([Image.open(d / f"{tag}_{v['name']}.png").convert("RGB") for v in views])
    W = Image.new("RGB", (size * len(views), size * 2 + 80), (255, 255, 255))
    for r, row in enumerate(ims):
        for i, im in enumerate(row):
            W.paste(im, (size * i, 80 + size * r))
    dr = ImageDraw.Draw(W)
    dr.text((8, 6), title, fill=(0, 0, 0))
    for i, t in enumerate(lines):
        dr.text((8, 24 + 14 * i), t, fill=(120, 0, 0))
    dr.text((8, 80 + 4), "BEFORE", fill=(200, 0, 0))
    dr.text((8, 80 + size + 4), "AFTER", fill=(0, 120, 0))
    W.save(OUT / f"{name}.png")
    W.resize((W.width * 2 // 3, W.height * 2 // 3), Image.LANCZOS).save(DER / f"Q224_render_{name}.png", optimize=True)
    print(name, "done", flush=True)


def get(B, sid):
    g = B.get(sid)
    return g["v"], g["f"]


def r1():
    b, a = Bundle(BODIES["m"]["src_bundle"]), Bundle(BODIES["m"]["out_bundle"])
    vb, fb = get(b, "femoral_v_r")
    va, fa = get(a, "femoral_v_r")
    c = 0.5 * (vb.min(0) + vb.max(0))
    half = 190
    sb = context(b, c, half, ("bone", "vessel", "nerve"), skip=("femoral_v_r",)) + [{"v": vb, "f": fb, "color": MAG}]
    sa = context(a, c, half, ("bone", "vessel", "nerve"), skip=("femoral_v_r",)) + [{"v": va, "f": fa, "color": MAG}]
    views = [dict(name="front", az=0, el=0, target=c, half=half), dict(name="side", az=90, el=0, target=c, half=half), dict(name="oblique", az=40, el=15, target=c, half=half)]
    montage("1_own_male_femoral_vein_r", "Own male | femoral_v_r (magenta): two pieces 62.0 mm apart -> one tube (rule-based bridge 70 mm between the two measured stumps)",
            ["cream = bones, blue-grey = other vessels and nerves. The bridge is rule-based (Hermite centreline + morphing elliptical section), NOT measured; checked on his 1 mm photographs (data/derived/Q224_photo_check_femoral_v_r.png)."], sb, sa, views)


def r2():
    b, a = Bundle(BODIES["f"]["src_bundle"]), Bundle(BODIES["f"]["out_bundle"])
    vb, fb = get(b, "longissimus_l")
    va, fa = get(a, "longissimus_l")
    end = vb[vb[:, 2] < vb[:, 2].min() + 1.0]
    c = end.mean(0) + np.array([0, 25, 25])
    half = 80
    sb = context(b, c, half * 1.6, ("bone",)) + [{"v": vb, "f": fb, "color": MAG}]
    sa = context(a, c, half * 1.6, ("bone",)) + [{"v": va, "f": fa, "color": MAG}]
    views = [dict(name="below", az=0, el=-55, target=c, half=half), dict(name="side", az=-90, el=-10, target=c, half=half), dict(name="back", az=180, el=-25, target=c, half=half)]
    montage("2_own_female_longissimus_l_flat_cut", "Own female | longissimus_l (magenta): flat face in the z=-110.2 plane (1308 mm2, the dorsal table-side plane of the CT block) -> domed",
            ["cream = bones. The dome only removes the planar face; where no bone is within reach the true continuation through the missing block is not known and not invented (z is the antero-posterior axis: -110 = the back)."], sb, sa, views)


def r3():
    b, a = Bundle(BODIES["f"]["src_bundle"]), Bundle(BODIES["f"]["out_bundle"])
    vb, fb = get(b, "tarsals_r")
    c = vb.mean(0)
    half = 150
    sb = context(b, c, half, ("bone",), skip=("tarsals_r",)) + [{"v": vb, "f": fb, "color": MAG}]
    sa = context(a, c, half, ("bone",))
    views = [dict(name="medial", az=-90, el=0, target=c, half=110), dict(name="top", az=0, el=70, target=c, half=110), dict(name="oblique", az=40, el=25, target=c, half=110)]
    montage("3_own_female_tarsals_group_mesh", "Own female | tarsals_r (magenta, the male-carried composite) on top of her seven single tarsal bones (cream) -> composite removed",
            ["IoU with her CT tarsal label: composite 0.405, her individual bones 0.888 (union). calcaneus 14.9 mm / talus 13.4 / cuboid 10.2 mm deep inside the composite before."], sb, sa, views)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for w in sys.argv[1:] or ["1", "2", "3"]:
        {"1": r1, "2": r2, "3": r3}[w]()
