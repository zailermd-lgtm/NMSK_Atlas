#!/usr/bin/env python3
"""Q217 Z male fitted page: everything else that touches the carried forearm muscles in the Z BASE at the left elbow (the distal arm muscles, bursae, cartilage, ligaments, septa, lymph nodes, vessels, nerves: 44 + 5
structures) is carried by the SAME twisted-tube map, so that the arm | forearm adjacency of the base (brachialis | brachioradialis ...) survives.  A structure that leaves the chain's range is cut at the wrist plane y = Y_WRIST and / or
the upper-arm plane y = Y_ARM and joined to the page's own mesh beyond (q217_carry.join_closed, B warped onto A over 45 mm).
    python3 scripts/transfer/q217_carry_extra.py list|carry|clamp"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C, q217_carry as CA  # noqa: E402
from scripts.transfer.q217_carry_zan import load_pages, twist_map, CACHE  # noqa: E402

Y_WRIST = 105.0
Y_ARM = 350.0
ELBOW = np.array([-240.0, 284.0, -42.0])
ARM_MUSCLES = ["biceps_brachii_l", "brachialis_l", "zan_lateral_head_of_triceps_brachii_l", "zan_long_head_of_triceps_brachii_l", "zan_medial_head_of_triceps_brachii_l"]


def list_ids():
    from scipy.spatial import cKDTree
    from scripts.transfer.q217_slide import surface_samples
    B, P = load_pages()
    tm = twist_map(B, P)
    mus = [i for i in C.side_ids(C.FOREARM + C.ARM) if i in B]
    mt = {i: cKDTree(surface_samples(B[i]["v"], B[i]["f"], 1.0)) for i in mus}
    ids = []
    for i, s in B.items():
        if s["sys"] in ("muscle", "bone", "skin") or not i.endswith("_l") or i not in P:
            continue
        img = tm(s["v"])
        if np.linalg.norm(img.mean(0) - ELBOW) > 140:
            continue
        pts = surface_samples(s["v"], s["f"], 1.5)
        if any(mt[m].query(pts)[0].min() <= 2.0 for m in mus):
            ids.append(i)
    (CACHE / "zan_extra_ids.json").write_text(json.dumps(ids))
    print(len(ids), "structures")


def carry():
    B, P = load_pages()
    tm = twist_map(B, P)
    ids = json.loads((CACHE / "zan_extra_ids.json").read_text()) + [i for i in ARM_MUSCLES if i in B]
    out, info = {}, {}
    for i in ids:
        a = tm(B[i]["v"])
        fb = B[i]["f"]
        ymin, ymax = float(a[:, 1].min()), float(a[:, 1].max())
        v, f, inf = a, fb, {"whole": True}
        ok = True
        if ymin < Y_WRIST:
            v, f, inf1 = CA.join_closed(v, f, P[i]["v"], P[i]["f"], Y_WRIST, a_above=True)
            inf = {"wrist": inf1}
            ok &= "note" not in inf1
        if ymax > Y_ARM and ok:
            v, f, inf2 = CA.join_closed(v, f, P[i]["v"], P[i]["f"], Y_ARM, a_above=False)
            inf["arm"] = inf2
            ok &= "note" not in inf2
        if not ok:
            info[i] = dict(skipped="the page has no section at a seam plane", **inf)
            print(i[:46].ljust(46), "SKIP", inf, flush=True)
            continue
        out[i] = (v, f)
        info[i] = dict(y_range_carried=[round(ymin), round(ymax)], **inf)
        print(i[:46].ljust(46), len(v), info[i], flush=True)
    pickle.dump(dict(meshes=out, info=info), open(CACHE / "zan_extra.pkl", "wb"))


def clamp():
    from scripts.transfer import q217_final_zan as FZ
    B, P = load_pages()
    d = pickle.load(open(CACHE / "zan_extra.pkl", "rb"))["meshes"]
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    muscles = {i: d[i] for i in d if P[i]["sys"] == "muscle"}
    others = {i: d[i] for i in d if P[i]["sys"] != "muscle"}
    bv = C.BoneVox(bones)
    out = dict(FZ.clamp_meshes(muscles, G, bv, win=(100.0, 380.0)))
    # vessels / nerves / ligaments / bursae: out of the bones only (they run inside the skin by construction; a vessel may touch its bone)
    for i, (v, f) in others.items():
        out.update(FZ.clamp_meshes({i: (v, f)}, G, bv, win=(100.0, 380.0)))
    pickle.dump(out, open(CACHE / "zan_extra_clamp.pkl", "wb"))


if __name__ == "__main__":
    {"list": list_ids, "carry": carry, "clamp": clamp}[sys.argv[1]]()
