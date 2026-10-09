#!/usr/bin/env python3
"""Q203: shoulder close-ups of an own-model bundle (anterior / posterior / lateral / superior views, bones visible), Z-filled continuations
(Q203 subjects) in blue, Q200 continuations in cyan.   python3 scripts/transfer/q203_render.py BUNDLE_DIR OUT_DIR own_m|own_f [--sides lr] [--tag T] [--muscles-only]"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402
import zlib  # noqa: E402

FOCUS = False
SKIP = re.compile(r"intercostal|skin|fascia|bursa|capsule|lung|heart|liver")


def col(e):
    i, c, sub = e["id"], e["cat"], e.get("subject", "")
    if sub.endswith("_q203"):
        return (0.10, 0.40, 0.95)
    if sub.endswith("_q200"):
        return (0.30, 0.80, 0.85)
    h = (zlib.crc32(i.encode()) % 1000) / 1000.0
    if c == "muscle" and FOCUS:
        return (0.85, 0.55, 0.50)
    if c == "bone":
        return (0.93, 0.91, 0.80)
    if c == "muscle":
        return (0.62 + 0.25 * h, 0.16 + 0.12 * h, 0.14 + 0.10 * h)
    if c == "vessel":
        return (0.92, 0.10, 0.10)
    if c == "nerve":
        return (0.97, 0.85, 0.10)
    return (0.90, 0.78, 0.55)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle"); ap.add_argument("out"); ap.add_argument("model")
    ap.add_argument("--sides", default="lr"); ap.add_argument("--tag", default=""); ap.add_argument("--r", type=float, default=150.0)
    ap.add_argument("--muscles-only", action="store_true"); ap.add_argument("--focus", action="store_true"); ap.add_argument("--focus-from", default=None); ap.add_argument("--half", type=float, default=120.0)
    a = ap.parse_args()
    global FOCUS
    FOCUS = a.focus
    B = Bundle(a.bundle)
    FB = Bundle(a.focus_from) if a.focus_from else B
    filled = {it["e"]["id"].rsplit("_zfill", 1)[0] for it in FB.items if "_zfill" in it["e"]["id"] and it["e"].get("subject", "").endswith("_q203")}
    r_ = json.loads((REPO / f"data/derived/Q198_model_{a.model}.json").read_text())
    cen = {j["side"]: np.asarray(j["centre_mm"], float) for j in r_["junctions"] if j["name"] == "shoulder"}
    for sd in a.sides:
        c = cen[sd]
        scene = []
        for it in B.items:
            e = it["e"]
            if e["id"] == "skin" or e["cat"] not in ("bone", "muscle", "tendon", "ligament") or SKIP.search(e["id"]):
                continue
            if e.get("side") not in (sd, None, "middle") and not re.sub(r"_zfill\d*$", "", e["id"]).endswith("_" + sd):
                continue
            if e["cat"] == "bone" and a.muscles_only:
                continue
            if e["cat"] != "bone" and not e.get("subject", "").endswith("_q203") and e["id"] not in filled and a.focus:
                continue
            v, f = B.mesh(it)
            if len(f) == 0 or np.linalg.norm(v - c, axis=1).min() > a.r:
                continue
            cf = v[f].mean(1)
            keep = np.linalg.norm(cf - c, axis=1) < a.r
            if keep.sum() < 2:
                continue
            scene.append({"v": v, "f": f[keep], "color": col(e)})
        lat = 270 if sd == "l" else 90
        views = [dict(name=f"shoulder_{sd}_anterior{a.tag}", az=0, el=0, target=c, half=a.half),
                 dict(name=f"shoulder_{sd}_posterior{a.tag}", az=180, el=0, target=c, half=a.half),
                 dict(name=f"shoulder_{sd}_lateral{a.tag}", az=lat, el=0, target=c, half=a.half),
                 dict(name=f"shoulder_{sd}_superior{a.tag}", az=0, el=70, target=c, half=a.half)]
        R.render(scene, views, Path(a.out) / a.model, size=(520, 520))
    print("rendered", a.out)


if __name__ == "__main__":
    main()
