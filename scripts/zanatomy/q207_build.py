#!/usr/bin/env python3
"""Q207 build of the two Z-fitted pages (in-process patch of the published Q206 pages, no Z build):
   stage wrap   : skin cleared outward around the hand / wrist / distal forearm structures of both sides          (q207_wrap)
   stage uro    : male urogenital patches refit to their Z source volume                                          (q207_uro)
   stage seams  : skin contacts whose true gap is > 1.5 mm closed by one sparse least-squares solve                (q207_seams)
   stage pack   : changed skin patches re-packed with before -> after badges, all other structures byte for byte  (q207_pack)
    python3 scripts/zanatomy/q207_build.py male|female wrap|uro|seams|report|pack|all"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C  # noqa: E402
from scripts.zanatomy import q207_wrap as WR  # noqa: E402
from scripts.zanatomy import q207_uro as URO  # noqa: E402
from scripts.zanatomy import q207_seams as SM  # noqa: E402

BUILD = REPO / "build" / "q207"
RAW = {"male": ("build/q197/viewer_zan_atlas", "atlas_viewer_zan_atlas"), "female": ("build/q197/viewer_base_female", "atlas_viewer_base_female")}
KEY = {"male": "q206_m", "female": "q206_f"}


def load_ctx(which):
    pg = C.Page(which)
    raw = C.Page(which, src=REPO / RAW[which][0], stem=RAW[which][1])
    return pg, raw


def coarse_fields(which):
    from scripts.zanatomy.q206_env import Fields
    z = np.load(REPO / "build" / "q206" / f"skinfield_{KEY[which]}.npz")
    return Fields(z["sd"], z["lo"], float(z["h"]))


def state_path(which, stage):
    BUILD.mkdir(parents=True, exist_ok=True)
    return BUILD / f"{which}_{stage}.pkl"


def stage_wrap(which, log=print):
    from scripts.zanatomy.q207_inflate import OwnSkin
    pg, raw = load_ctx(which)
    W = pg.wrist()
    coarse = coarse_fields(which)
    own = OwnSkin(which)
    V = {i: pg.v(i) for i in pg.skin_ids}
    rep = {}
    for side in "lr":
        t = time.time()
        log(f"[{which}] wrap side {side}")
        V, h = WR.wrap(pg, V, side, W[side], coarse, own, iters=8, log=log)
        rep[side] = h
        log(f"   {time.time()-t:.0f}s")
    pickle.dump((V, rep), open(state_path(which, "wrap"), "wb"))
    return V, rep


def stage_nails(which, log=print):
    """overlay patches whose edges the earlier fits collapsed (degenerate share > 1 %) are re-seated on the dorsal digit sheet (q207_nails)"""
    from scripts.zanatomy import q207_nails as N
    pg, raw = load_ctx(which)
    V, rep = pickle.load(open(state_path(which, "wrap"), "rb"))
    V = dict(V)
    done = {}
    bad = {side: any(f"zan_skin_{ov}_{side}" in V and N.degenerate_share(V[f"zan_skin_{ov}_{side}"], pg.f(f"zan_skin_{ov}_{side}"), raw.v(f"zan_skin_{ov}_{side}")) > 0.01 for ov in ("nail_plate", "perionyx")) for side in "lr"}
    for side in "lr":
        base = f"zan_skin_dorsal_surfaces_of_digits_of_hand_{side}"
        for ov in ("nail_plate", "perionyx"):
            i = f"zan_skin_{ov}_{side}"
            if i not in V:
                continue
            f = pg.f(i)
            before = N.degenerate_share(V[i], f, raw.v(i))
            if bad[side]:           # both overlays of a hand are re-seated together so that they keep their source relation to each other
                V[i] = N.transfer(raw.v(i), raw.v(base), pg.f(base), V[base])
                after = N.degenerate_share(V[i], f, raw.v(i))
                done[i] = {"degenerate_edge_share": [round(before, 4), round(after, 4)]}
                log(f"   {i}: collapsed edges {before:.3f} -> {after:.3f}")
    pickle.dump((V, {"wrap": rep, "nails": done}), open(state_path(which, "nails"), "wb"))
    return V, done


def stage_uro(which, log=print):
    pg, raw = load_ctx(which)
    V, rep = pickle.load(open(state_path(which, "nails"), "rb"))
    if which != "male":
        pickle.dump((V, {}), open(state_path(which, "uro"), "wb"))
        return V, {}
    ids = list(URO.IDS)
    oth = [i for i in pg.skin_ids if i not in ids and i in raw.S]
    out, r = URO.refit_split({i: raw.v(i) for i in ids}, {i: pg.v(i) for i in ids}, {i: pg.f(i) for i in ids}, {i: raw.v(i) for i in oth}, {i: V[i] for i in oth}, others_faces={i: pg.f(i) for i in oth}, log=log)
    V = dict(V)
    V.update(out)
    pickle.dump((V, r), open(state_path(which, "uro"), "wb"))
    return V, r


def stage_seams(which, log=print, min_move=0.5):
    pg, raw = load_ctx(which)
    V, _ = pickle.load(open(state_path(which, "uro"), "rb"))
    ids = sorted(i for i in pg.skin_ids if i in raw.S)
    faces = {i: pg.f(i) for i in ids}
    rv = {i: raw.v(i) for i in ids}
    from scripts.zanatomy import q207_uro as U
    V2, rep = SM.weld_true_gaps(ids, {i: V[i] for i in ids}, faces, rv, skip=tuple(U.IDS) if which == 'male' else (), log=log)
    V2b, rep2 = SM.weld_pass2(ids, V2, faces, rv, log=log)
    V2 = V2b
    rep["pass2"] = rep2
    out = dict(V)
    moved = {}
    for i in ids:
        d = np.linalg.norm(V2[i] - V[i], axis=1)
        if d.max() >= min_move:
            out[i] = V2[i]
            moved[i] = {"max_mm": round(float(d.max()), 2), "mean_mm": round(float(d.mean()), 2)}
    log(f"   seam solve: {len(moved)} patches moved >= {min_move} mm (smaller moves reverted)")
    rep = {k: v for k, v in rep.items() if k != "items"}
    rep["moved"] = moved
    pickle.dump((out, rep), open(state_path(which, "seams"), "wb"))
    return out, rep


if __name__ == "__main__":
    which, stage = sys.argv[1], sys.argv[2]
    stages = ["wrap", "nails", "uro", "seams"] if stage == "all" else [stage]
    for s in stages:
        globals()["stage_" + s](which)
