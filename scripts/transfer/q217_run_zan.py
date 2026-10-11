#!/usr/bin/env python3
"""Q217 stages on the Z male fitted page's left forearm (caches in build/q217_cache):
    python3 scripts/transfer/q217_run_zan.py tile|fit|eval [--regrow 1.0]"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C, q217_domain as D, q217_tile as T, q217_fit as FT  # noqa: E402

CACHE = REPO / "build" / "q217_cache"


def setup():
    Z = pickle.load(open(CACHE / "zan_zone.pkl", "rb"))
    cls = np.load(CACHE / "photo_l.npy")
    g = D.new_grid()
    bone = np.zeros(g.shape, bool)
    for i, s in Z.items():
        if s["sys"] == "bone" and s["v"][:, 0].max() < -100 and s["v"][:, 1].max() > 90 and s["v"][:, 1].min() < 345:
            bone |= D.bone_solid(g, s["v"], s["f"])
    fixed = np.zeros(g.shape, bool)
    for i in C.side_ids(C.ARM):
        if i in Z:
            r = T.local_solid(g, Z[i]["v"], Z[i]["f"])
            if r:
                fixed[r[0]] |= r[1]
    pc = D.photo_on_grid(cls, np.array([-300.0, 90.0, -130.0]), g)
    cont = D.container(pc, bone, fixed)
    return Z, g, bone, fixed, pc, cont


def stage_tile(regrow=1.0):
    Z, g, bone, fixed, pc, cont = setup()
    priors = {i: (Z[i]["v"], Z[i]["f"]) for i in C.side_ids(C.FOREARM) if i in Z}
    lab, ids, rep = T.tile(g, priors, cont, bone | fixed, log=lambda *a: print(*a, flush=True), regrow_max=regrow)
    np.savez_compressed(CACHE / "zan_tile.npz", lab=lab.astype(np.int8), ids=np.array(ids))
    pickle.dump(rep, open(CACHE / "zan_tile_rep.pkl", "wb"))


def stage_fit():
    Z, g, *_ = setup()
    z = np.load(CACHE / "zan_tile.npz")
    lab, ids = z["lab"].astype(np.int16), list(z["ids"])
    X, rep = {}, {}
    t = time.time()
    for k, i in enumerate(ids):
        v0, f = Z[i]["v"], Z[i]["f"]
        r = T.local_solid(g, v0, f)
        prior = np.zeros(g.shape, bool)
        prior[r[0]] = r[1]
        terr = FT.Territory(g, lab == k + 1, prior)
        x, rp = FT.fit_mesh(v0, f, terr, rounds=16)
        X[i], rep[i] = x, rp
        print(i[:34].ljust(34), rp, round(time.time() - t), flush=True)
    pickle.dump(X, open(CACHE / "zan_fit.pkl", "wb"))


def stage_eval(name="zan_fit.pkl"):
    Z = pickle.load(open(CACHE / "zan_zone.pkl", "rb"))
    X = pickle.load(open(CACHE / name, "rb")) if name else {}
    fm = [i for i in C.side_ids(C.FOREARM) if i in Z]
    fx = [i for i in C.side_ids(C.ARM) if i in Z]
    for tag, co in (("before", {}), ("after", X)):
        M = {i: (co.get(i, Z[i]["v"]), Z[i]["f"]) for i in fm + fx}
        rows, tot = C.overlap_voxels(M, lo=tuple(D.BOX_LO), hi=tuple(D.BOX_HI))
        print(tag, "total shared cm3", tot, "mean shared %", round(np.mean([rows[i]["shared_pct"] for i in fm]), 1), flush=True)
        for i in fm:
            print("  ", i[:34].ljust(34), rows[i]["vol_cm3"], rows[i]["shared_pct"], "mesh", round(C.mesh_volume(Z[i]["v"], Z[i]["f"]), 1), "->", round(C.mesh_volume(co.get(i, Z[i]["v"]), Z[i]["f"]), 1), flush=True)


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "tile":
        stage_tile(float(sys.argv[3]) if len(sys.argv) > 3 else 1.0)
    elif st == "warp":
        stage_warp()
    elif st == "fit":
        stage_fit()
    else:
        stage_eval(*(sys.argv[2:3]))


def stage_warp():
    from scripts.transfer import q217_warp as W
    Z, g, *_ = setup()
    z = np.load(CACHE / "zan_tile.npz")
    lab, ids = z["lab"].astype(np.int16), list(z["ids"])
    X = {}
    t = time.time()
    for k, i in enumerate(ids):
        v0, f = Z[i]["v"], Z[i]["f"]
        r = T.local_solid(g, v0, f)
        prior = np.zeros(g.shape, bool)
        prior[r[0]] = r[1]
        wp = W.Warp(g, prior, lab == k + 1).run()
        X[i] = W.carry_mesh(v0, wp)
        print(i[:34].ljust(34), "prior", round(wp.vol_prior, 1), "terr", round(wp.vol_terr, 1), "resid", round(wp.last_resid, 3), "max move", round(float(np.linalg.norm(X[i] - v0, axis=1).max()), 1), round(time.time() - t), flush=True)
    pickle.dump(X, open(CACHE / "zan_warp.pkl", "wb"))
