#!/usr/bin/env python3
"""Q217 Z male fitted page: the left forearm muscles = the Z BASE muscles carried onto HIS forearm by one twisted-tube map (q217_twist), joined to the page's own hand-side tendon part (q217_carry).
    python3 scripts/transfer/q217_carry_zan.py carry|eval"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C, q217_domain as D, q217_twist as TW, q217_carry as CA  # noqa: E402

CACHE = REPO / "build" / "q217_cache"
Y_SEAM = 105.0
CARPALS = ("capitate", "hamate", "lunate", "pisiform", "scaphoid", "trapezium", "trapezoid", "triquetrum")


def load_pages():
    from scripts.zanatomy import q217_paths  # noqa: F401
    from scripts.zanatomy import q198_load as L
    B = {s["id"]: s for s in L.load("z_male")}
    P = {s["id"]: s for s in L.load("zan_m")}
    return B, P


def twist_map(B, P):
    carp = [k for k in B if k.endswith("_bone_l") and any(t in k for t in CARPALS) and k in P]
    hb, hp = B["humerus_l"]["v"], P["humerus_l"]["v"]
    m = hb[:, 1] < hb[:, 1].min() + 70
    blocks = [(hb[m], hp[m]), (np.concatenate([B[k]["v"] for k in carp]), np.concatenate([P[k]["v"] for k in carp]))]
    return TW.TwistMap({k: B[k]["v"] for k in ("radius_l", "ulna_l")}, {k: P[k]["v"] for k in ("radius_l", "ulna_l")}, blocks=blocks)


def carry():
    B, P = load_pages()
    tm = twist_map(B, P)
    out, info = {}, {}
    for i in C.side_ids(C.FOREARM):
        if i not in B or i not in P:
            continue
        a_v = tm(B[i]["v"])
        v, f, inf = CA.join_closed(a_v, B[i]["f"], P[i]["v"], P[i]["f"], Y_SEAM)
        out[i] = (v, f)
        info[i] = inf
        print(i[:40].ljust(40), len(v), len(f), inf, flush=True)
    pickle.dump(dict(meshes=out, info=info), open(CACHE / "zan_carry.pkl", "wb"))


def evaluate(name="zan_carry.pkl"):
    B, P = load_pages()
    d = pickle.load(open(CACHE / name, "rb"))
    d = d["meshes"] if "meshes" in d else d
    fm = list(d)
    fx = [i for i in C.side_ids(C.ARM) if i in P]
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    for tag, mm in (("page", {i: (P[i]["v"], P[i]["f"]) for i in fm}), ("carried", d)):
        M = dict(mm)
        M.update({i: (P[i]["v"], P[i]["f"]) for i in fx})
        rows, tot = C.overlap_voxels(M, lo=tuple(D.BOX_LO), hi=tuple(D.BOX_HI))
        print(tag, "total shared cm3", tot, "mean shared %", round(np.mean([rows[i]["shared_pct"] for i in fm]), 1), flush=True)
        for i in fm:
            v = mm[i][0]
            win = (v[:, 1] > 125) & (v[:, 1] < 320)
            sg = G.signed(v[win]) if win.any() else np.zeros(1)
            print("  ", i[:34].ljust(34), "vol", rows[i]["vol_cm3"], "shared", rows[i]["shared_pct"], "outside skin (window) %", round(100 * float((sg > 0).mean()), 1), "depth min", round(float(-sg.max()), 1), flush=True)


def polish(src="zan_carry.pkl", dst="zan_polish.pkl", rounds=12):
    import time
    from scripts.transfer import q217_slide as SL
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    d = d["meshes"] if "meshes" in d else d
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    fixed = {i: (P[i]["v"], P[i]["f"]) for i in C.side_ids(C.ARM) if i in P}
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    sp = SL.Separator({i: d[i] for i in d}, fixed, bones, G)
    lams = [3.0, 1.5, 0.75, 0.75, 0.4, 0.4, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
    for k, lam in enumerate(lams[:rounds]):
        t = time.time()
        tot = sp.step(lam)
        mv = np.mean([np.linalg.norm(sp.x[i] - sp.x0[i], axis=1).mean() for i in sp.ids])
        print(k, lam, {n: (v[0], round(v[1]), round(v[2], 1)) for n, v in tot.items()}, "mean move", round(mv, 2), round(time.time() - t), flush=True)
        pickle.dump({i: (sp.x[i], sp.f[i]) for i in sp.ids}, open(CACHE / dst, "wb"))


if __name__ == "__main__":
    {"carry": carry, "eval": lambda: evaluate(*sys.argv[2:3]), "polish": polish}[sys.argv[1]]()
