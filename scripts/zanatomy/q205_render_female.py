#!/usr/bin/env python3
"""Q205 female renders (build/q205_renders): 3-D close-ups of both wrists / hands (bones + muscles, vessels + nerves) and of the forearm bones, Q202 page | Q205 page.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q205_render_female.py [--out build/q205_renders]"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P  # noqa: E402

STEM = "atlas_viewer_zan_female"
HAND = re.compile(r"metacarpal|finger_of_hand|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "build" / "q205_renders"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from scripts.zanatomy import q201_renders as RR
    from scripts.zanatomy import q190_render as R
    old, new = {}, {}
    for S, d in ((old, REPO / "build" / "q202" / "viewer_zan_female"), (new, REPO / "build" / "q205" / "viewer_zan_female")):
        man, blob = P.load_page(d, STEM)
        for i, e in P.decode(man, blob).items():
            S[i] = {"v": e["v"], "f": e["f"], "sys": e["m"]["sys"]}

    def closeups(Mb, Ma, side, tag, centre, layers, half):
        rows = []
        for t, M in (("Q202 page", Mb), ("Q205 page", Ma)):
            views = [{"name": n, "az": az, "el": 0, "target": centre, "half": half} for n, az in (("anterior", 0), ("lateral", 270 if side == "l" else 90), ("posterior", 180), ("medial", 90 if side == "l" else 270))]
            tmp = out / f"_tmp_{side}_{tag}_{t.replace(' ', '_')}"
            R.render(RR.scene(M, side, layers, centre), views, tmp, size=(480, 480))
            rows.append([str(tmp / f"{v['name']}.png") for v in views])
        RR.montage(rows, out / f"{tag}_{'left' if side == 'l' else 'right'}_f.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("Q202 page", "Q205 page")])

    for side in "rl":
        s = "_" + side
        hb = np.vstack([e["v"] for i, e in new.items() if i.endswith(s) and e["sys"] == "bone" and HAND.search(i) and "foot" not in i])
        rb = np.vstack([new["radius" + s]["v"][new["radius" + s]["v"][:, 1] < new["radius" + s]["v"][:, 1].min() + 60]])
        hc = hb.mean(0)
        wc = rb.mean(0)
        closeups(old, new, side, "wrist_bones_muscles", wc, ("bone", "muscle", "tendon"), 110)
        closeups(old, new, side, "wrist_vessels_nerves", wc, ("bone", "vessel", "nerve", "ligament"), 110)
        closeups(old, new, side, "hand_bones", hc, ("bone",), 110)
        closeups(old, new, side, "forearm_bones", (wc + new["radius" + s]["v"].mean(0)) / 2, ("bone",), 170)
    import shutil
    for d in out.glob("_tmp_*"):
        shutil.rmtree(d)
    print("renders ->", out)


if __name__ == "__main__":
    main()
