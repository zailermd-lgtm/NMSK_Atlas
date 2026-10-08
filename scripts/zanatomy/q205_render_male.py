#!/usr/bin/env python3
"""Q205 male renders (build/q205_renders): hand bones over HIS photographs (Q202 page | Q205 page), 3-D close-ups of both hands and shoulders before | after.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q205_render_male.py CROPS_NPZ [--out build/q205_renders]"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P  # noqa: E402
from scripts.zanatomy import q205_renders as R5  # noqa: E402

STEM = "atlas_viewer_zan_male_fitted"
HAND = re.compile(r"metacarpal|finger_of_hand|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate")


def page_models(d):
    man, blob = P.load_page(d, STEM)
    return P.decode(man, blob)


def photo_hands(crops, old, new, out):
    for side in "rl":
        s = "_" + side
        mods = {}
        for nm, S in (("Q202 page", old), ("Q205 page", new)):
            mods[nm] = {i: (e["v"], e["f"], "thumb" if "first" in i else "bone") for i, e in S.items() if i.endswith(s) and e["m"]["sys"] == "bone" and HAND.search(i) and "foot" not in i}
        for n, lv in enumerate(((16, 30, 44), (56, 66, 78))):
            R5.photo_sections(crops, side, mods, list(lv), out / f"photos_hand_{side}_{n}.png")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("crops")
    ap.add_argument("--out", default=str(REPO / "build" / "q205_renders"))
    ap.add_argument("--only", default="photos,3d")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    old = page_models(REPO / "build" / "q202" / "viewer_zan_vhm")
    new = page_models(REPO / "build" / "q205" / "viewer_zan_vhm")
    if "photos" in a.only:
        photo_hands(a.crops, old, new, out)
    if "3d" in a.only:
        from scripts.zanatomy import q201_renders as RR
        from scripts.zanatomy import q190_render as R

        def closeups(Mb, Ma, out, side, tag, centre, layers, half):
            rows = []
            for t, M in (("Q202 page", Mb), ("Q205 page", Ma)):
                views = [{"name": n, "az": az, "el": 0, "target": centre, "half": half}
                         for n, az in (("anterior", 0), ("lateral", 270 if side == "l" else 90), ("posterior", 180), ("medial", 90 if side == "l" else 270))]
                tmp = out / f"_tmp_{side}_{tag}_{t.replace(' ', '_')}"
                R.render(RR.scene(M, side, layers, centre), views, tmp, size=(480, 480))
                rows.append([str(tmp / f"{v['name']}.png") for v in views])
            RR.montage(rows, out / f"{tag}_{'left' if side == 'l' else 'right'}.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("Q202 page", "Q205 page")])
        Mb = {i: {"v": e["v"], "f": e["f"], "sys": e["m"]["sys"]} for i, e in old.items()}
        Ma = {i: {"v": e["v"], "f": e["f"], "sys": e["m"]["sys"]} for i, e in new.items()}
        for side, hc, sc in (("r", np.array([95.0, 55.0, 140.0]), np.array([186.0, 563.0, 3.0])), ("l", np.array([-120.0, 55.0, 140.0]), np.array([-171.0, 577.0, 4.0]))):
            closeups(Mb, Ma, out, side, "hand_bones_muscles", hc, ("bone", "muscle", "tendon"), 110)
            closeups(Mb, Ma, out, side, "hand_vessels_nerves", hc, ("bone", "vessel", "nerve", "ligament"), 110)
            closeups(Mb, Ma, out, side, "shoulder_muscles", sc, ("bone", "muscle"), 120)
            closeups(Mb, Ma, out, side, "shoulder_vessels_nerves", sc, ("bone", "vessel", "nerve"), 120)
        import shutil
        for d in out.glob("_tmp_*"):
            shutil.rmtree(d)
    print("renders ->", out)


if __name__ == "__main__":
    main()
