#!/usr/bin/env python3
"""Q338: screenshots of one hand of a Base page (test copy with hook_q338.js; the page dir is not touched).

    python3 scripts/anatomy/q338/render_hand_q338.py <page_dir> <out_dir> [--side r|l] [--pose JSON] [--views palmar,dorsal,...] [--layers all,noskin,vn,tendon]

--pose: {"joint_id": {"dof": value}, ...} applied with window.__poseApi.set (raw rig values, clamped to the rig's range)."""
from __future__ import annotations
import argparse, json, math, os, sys, tempfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pagehook_q338 as PH  # noqa: E402

LAYERS = {
    "all": None,
    "noskin": {"skin": 0, "fat": 0},
    "vn": {k: (1 if k in ("bone", "vessel", "nerve") else 0) for k in ["bone", "cartilage", "joint", "insertion", "muscle", "fascia", "bursa", "nerve", "cns", "vessel", "lymph", "viscera", "fat", "skin"]},
    "tendon": {k: (1 if k in ("bone", "muscle", "insertion") else 0) for k in ["bone", "cartilage", "joint", "insertion", "muscle", "fascia", "bursa", "nerve", "cns", "vessel", "lymph", "viscera", "fat", "skin"]},
    "skin": {k: (1 if k in ("bone", "skin") else 0) for k in ["bone", "cartilage", "joint", "insertion", "muscle", "fascia", "bursa", "nerve", "cns", "vessel", "lymph", "viscera", "fat", "skin"]},
    "sheath": {k: (1 if k in ("bone", "bursa", "joint") else 0) for k in ["bone", "cartilage", "joint", "insertion", "muscle", "fascia", "bursa", "nerve", "cns", "vessel", "lymph", "viscera", "fat", "skin"]},
}


def hand_frame(page_dir, side):
    key = "base_f" if "female" in Path(page_dir).name else "base_m"
    os.environ["Q241_SRC_" + key] = str(Path(page_dir).resolve())
    import hand_frame as HF
    M = HF.MD.Model(key)
    from rig_io_q338 import page_rig
    rig = page_rig(page_dir)
    H = HF.Hand(M, rig, side)
    s3 = H.fingers[3][0]
    B = M.bones()
    c = np.vstack([B["mc_3_" + side]["v"], B["ph_hand_3_prox_" + side]["v"]]).mean(0)
    u = s3["u"]; p = s3["p"]; r = s3["r"]
    return c, u, p, r


def az_el(n):
    n = n / np.linalg.norm(n)
    return math.atan2(n[0], n[2]), math.asin(max(-1, min(1, n[1])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page_dir"); ap.add_argument("out_dir")
    ap.add_argument("--side", default="r"); ap.add_argument("--pose", default=None)
    ap.add_argument("--views", default="palmar,dorsal,radial,ulnar,endon")
    ap.add_argument("--layers", default="all,noskin,vn,tendon")
    ap.add_argument("--dist", type=float, default=200.0); ap.add_argument("--ahead", type=float, default=25.0); ap.add_argument("--tag", default="")
    a = ap.parse_args()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    c, u, p, r = hand_frame(a.page_dir, a.side)
    tgt = (c + a.ahead * u).tolist()
    views = {"palmar": p, "dorsal": -p, "radial": r, "ulnar": -r, "endon": u + 0.25 * p}
    from playwright.sync_api import sync_playwright
    tmp = Path(tempfile.mkdtemp(prefix="q338_", dir="/dev/shm"))
    d = PH.test_copy(Path(a.page_dir), tmp / Path(a.page_dir).name)
    errs = []
    with sync_playwright() as pl:
        srv, b, pg = PH.open_page(pl, d, errs=errs)
        try:
            pg.evaluate("() => { const b = document.getElementById('btn-pose'); if (b) b.click(); }")
            pg.wait_for_timeout(800)
            if a.pose:
                spec = json.loads(a.pose)
                res = pg.evaluate("""async (spec) => { const P = window.__poseApi; const out = {};
                    for (const j in spec) for (const k in spec[j]) out[j + '.' + k] = P.set(j, k, spec[j][k]);
                    await new Promise(r => setTimeout(r, 1500)); return out; }""", spec)
                print("pose", res)
            pg.add_style_tag(content="#pose-panel,#topright,.q301-bar,#pose-banner{visibility:hidden !important}")
            for lk in a.layers.split(","):
                pg.evaluate("() => window.__q338.defaults()")
                L = LAYERS[lk]
                if L:
                    for k, v in L.items():
                        pg.evaluate("([k, v]) => window.__q338.layer(k, v)", [k, v])
                for vn in a.views.split(","):
                    az, el = az_el(views[vn])
                    pg.evaluate("(c) => window.__q338.cam(c)", {"az": az, "el": el, "dist": a.dist, "tgt": tgt})
                    pg.wait_for_timeout(600)
                    f = out / ("%s%s_%s_%s.png" % (a.tag, a.side, lk, vn))
                    pg.screenshot(path=str(f))
                    print(f)
        finally:
            b.close(); srv.terminate()
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
    print("page errors:", errs)


if __name__ == "__main__":
    main()
