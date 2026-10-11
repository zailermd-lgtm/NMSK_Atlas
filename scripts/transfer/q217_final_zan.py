#!/usr/bin/env python3
"""Q217 Z male fitted page, final stage: hard guards on the polished carried muscles, arm-end pulls, metrics before / after, pack into build/q217/viewer_zan_vhm, ship-diff.
    python3 scripts/transfer/q217_final_zan.py clamp|ends|metrics|pack"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C, q217_ends as E, q217_slide as SL  # noqa: E402
from scripts.transfer.q217_carry_zan import load_pages, CACHE  # noqa: E402
from scripts.transfer.q213_inbone import laplacian  # noqa: E402

SRC = REPO / "build/q211/viewer_zan_vhm"
OUT = REPO / "build/q217/viewer_zan_vhm"
STEM = "atlas_viewer_zan_male_fitted"
SKIN_MIN_MM = 1.0


def clamp(src="zan_polish.pkl", dst="zan_clamp.pkl", rounds=6):
    """vertices outside the skin / closer than SKIN_MIN_MM to it go inward, vertices > 0.5 mm inside a bone go out (displacement field smoothed over the mesh, so no spikes); held vertices (y outside the window) stay"""
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    bv = C.BoneVox(bones)
    out = {}
    for i, (v, f) in d.items():
        x = v.copy()
        Lap = laplacian(len(x), f)
        anch = 60.0 * np.maximum(SL.smooth_ramp(x[:, 1], 100.0, 20.0), 1.0 - SL.smooth_ramp(x[:, 1], 300.0, 20.0))
        for _ in range(rounds):
            t = np.zeros_like(x)
            sg = G.signed(x)
            need = np.maximum(sg + SKIN_MIN_MM, 0.0)
            sel = need > 0
            if sel.any():
                dd, ii = G.tree.query(x[sel])
                near = G.tree.data[ii]
                inside = sg[sel] <= 0
                dirn = np.where(inside[:, None], x[sel] - near, near - x[sel])
                t[sel] += need[sel, None] * dirn / np.maximum(np.linalg.norm(dirn, axis=1, keepdims=True), 1e-6)
            dep = bv.depth(x)
            sel2 = dep > 0.5
            if sel2.any():
                g = np.zeros((sel2.sum(), 3))
                for k in range(3):
                    e = np.zeros(3)
                    e[k] = 1.0
                    g[:, k] = (bv.depth(x[sel2] + e) - bv.depth(x[sel2] - e)) / 2.0
                n = np.linalg.norm(g, axis=1, keepdims=True)
                t[sel2] += (dep[sel2, None] + 0.3) * (-g / np.maximum(n, 1e-6))
            w = ((np.linalg.norm(t, axis=1) > 0)).astype(float) * 30.0
            if not w.any():
                break
            dsp = SL.solve_disp(Lap, w, t, 1.0, anch)
            x = x + dsp
        out[i] = (x, f)
    pickle.dump(out, open(CACHE / dst, "wb"))


if __name__ == "__main__":
    {"clamp": clamp}[sys.argv[1]]()
