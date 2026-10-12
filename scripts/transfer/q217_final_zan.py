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


def ends(src="zan_clamp.pkl", dst="zan_ends.pkl"):
    """pull every muscle end that lies > END_GATE_MM from the bone its card names onto that bone (<= CAP_MM), the other end held: forearm origins + the arm muscles' distal ends (biceps -> radius ...)"""
    from scripts.transfer.q216_fix import pull_anchored
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    bt = E.bone_trees(bones)
    items = dict(d)
    for i in C.side_ids(C.ARM):
        if i in P:
            items[i] = (P[i]["v"], P[i]["f"])
    out, rep = dict(d), {}
    for i, (v, f) in items.items():
        rec = P[i].get("rec")
        zs, u, t = E.zones(v)
        pulls, anchors, info = [], [], []
        for nm, z, bid, p5, mn in E.plan(v, rec, bt):
            other = zs["hi" if nm == "lo" else "lo"]
            info.append(dict(end=nm, bone=bid, p5_before=round(p5, 1)))
            if p5 > E.END_GATE_MM and p5 <= E.CAP_MM:
                pulls.append((z, bt[bid][1], 0.0))
                anchors.append(other)
        if not pulls:
            rep[i] = dict(ends=info, pulled=False)
            continue
        nv, pinfo = pull_anchored(v, f, pulls, anchors)
        if nv is None:
            rep[i] = dict(ends=info, pulled=False, refused=pinfo)
            continue
        out[i] = (nv, f)
        after = [round(E.zone_dist(nv, z, bt[bid][0])[0], 1) for (nm, z, bid, p5, mn) in E.plan(v, rec, bt) if p5 > E.END_GATE_MM and p5 <= E.CAP_MM]
        rep[i] = dict(ends=info, pulled=True, applied_mm=[round(x.get("applied_mm", 0), 1) for x in pinfo], p5_after=after, max_move_mm=round(float(np.linalg.norm(nv - v, axis=1).max()), 1))
        print(i[:40].ljust(40), rep[i], flush=True)
    pickle.dump(out, open(CACHE / dst, "wb"))
    pickle.dump(rep, open(CACHE / "zan_ends_rep.pkl", "wb"))


def metrics(src="zan_ends.pkl"):
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    fm = [i for i in C.side_ids(C.FOREARM) if i in d]
    fx = [i for i in C.side_ids(C.ARM) if i in P]
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    bv = C.BoneVox(bones)
    res = {}
    for tag, mm, fixed in (("before", {i: (P[i]["v"], P[i]["f"]) for i in fm}, {i: (P[i]["v"], P[i]["f"]) for i in fx}),
                           ("after", {i: d[i] for i in fm}, {i: d.get(i, (P[i]["v"], P[i]["f"])) for i in fx})):
        out, tot = C.muscle_metrics(mm, fixed, G, bv, ids=fm)
        res[tag] = dict(per_muscle=out, total_shared_cm3=tot, mean_shared_pct=round(float(np.mean([o["shared_pct"] for o in out.values()])), 1))
        print(tag, "total shared", tot, "mean", res[tag]["mean_shared_pct"], flush=True)
    (REPO / "data/derived/Q217_zan_metrics.json").write_text(json.dumps(res, indent=1, default=str))
    for i in fm:
        a, b = res["before"]["per_muscle"][i], res["after"]["per_muscle"][i]
        print(i[:34].ljust(34), "vol", a["vol_cm3"], "->", b["vol_cm3"], "shared", a["shared_pct"], "->", b["shared_pct"], "outside skin", a["outside_skin_pct"], "->", b["outside_skin_pct"],
              "in bone", a["in_bone_pct"], "->", b["in_bone_pct"], "depth", a["bone_depth_max_mm"], "->", b["bone_depth_max_mm"], flush=True)


if __name__ == "__main__":
    {"clamp": clamp, "ends": ends, "metrics": metrics}[sys.argv[1]]()
