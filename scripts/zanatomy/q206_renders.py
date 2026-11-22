#!/usr/bin/env python3
"""Q206 renders (build/q206_renders, git-ignored): 3-D close-ups of both wrists / hands, Q205 page | Q206 page: vessels + nerves + bones, sheaths / ligaments / retinacula + bones, and the
worst-fixed structure of each page.   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q206_renders.py male|female [--out build/q206_renders]"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P  # noqa: E402
from scripts.zanatomy import q206_state as ST  # noqa: E402

HAND = re.compile(r"metacarpal|finger_of_hand|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate")


def load(d, stem):
    man, blob = P.load_page(d, stem)
    return {i: {"v": e["v"], "f": e["f"], "sys": e["m"]["sys"]} for i, e in P.decode(man, blob).items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["male", "female"])
    ap.add_argument("--out", default=str(REPO / "build" / "q206_renders"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from scripts.zanatomy import q201_renders as RR
    from scripts.zanatomy import q190_render as R
    cfg = ST.CFG[a.which]
    old, new = load(cfg["page"], cfg["stem"]), load(cfg["out"], cfg["stem"])

    def closeups(side, tag, centre, layers, half, sel=None):
        rows = []
        for t, M in (("Q205 page", old), ("Q206 page", new)):
            if sel:
                M = {i: m for i, m in M.items() if i in sel or m["sys"] == "bone"}
            views = [{"name": n, "az": az, "el": 0, "target": centre, "half": half} for n, az in (("anterior", 0), ("lateral", 270 if side == "l" else 90), ("posterior", 180), ("medial", 90 if side == "l" else 270))]
            tmp = out / f"_tmp_{a.which}_{side}_{tag}_{t.replace(' ', '_')}"
            R.render(RR.scene(M, side, layers, centre), views, tmp, size=(480, 480))
            rows.append([str(tmp / f"{v['name']}.png") for v in views])
        RR.montage(rows, out / f"{a.which}_{tag}_{'left' if side == 'l' else 'right'}.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("Q205 page", "Q206 page")])

    for side in "rl":
        s = "_" + side
        hb = np.vstack([e["v"] for i, e in new.items() if i.endswith(s) and e["sys"] == "bone" and HAND.search(i) and "foot" not in i])
        rb = new["radius" + s]["v"]
        wc = rb[rb[:, 1] < rb[:, 1].min() + 60].mean(0)
        hc = hb.mean(0)
        closeups(side, "wrist_vessels_nerves", wc, ("bone", "vessel", "nerve"), 100)
        closeups(side, "hand_vessels_nerves", hc, ("bone", "vessel", "nerve"), 110)
        closeups(side, "wrist_sheaths_ligaments", wc, ("bone", "ligament", "tendon", "joint", "bursa"), 100)
    for d in out.glob("_tmp_*"):
        shutil.rmtree(d)
    print("renders ->", out)


if __name__ == "__main__":
    main()
