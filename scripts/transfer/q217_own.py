#!/usr/bin/env python3
"""Q217 own male page (bundle build/viewer_m_hr_q214): the left forearm muscles = the Q217 carried set of the Z male fitted page (build q217_final_zan: zan_ends.pkl) pushed inside HIS OWN skin and out of HIS OWN
bones, separated from his measured arm muscles; replaces his 13 Z-carried forearm muscles (+ their continuation pieces), adds the 8 left forearm muscles his page did not carry.
    python3 scripts/transfer/q217_own.py polish|clamp|metrics|bundle"""
from __future__ import annotations

import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C, q217_slide as SL  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

CACHE = REPO / "build" / "q217_cache"
SRC_BUNDLE = REPO / "build/viewer_m_hr_q214"
OWN_BONES = ["humerus_l", "humerus_l_zfill", "radius_l", "radius_l_zfill", "radius_l_distal_q212", "ulna_l", "ulna_l_distal_q212", "carpals_l_q212", "metacarpals_l"]
ARM_OWN = ["biceps_brachii_l", "brachialis_l", "coracobrachialis_l", "triceps_brachii_l"]
_ZF = re.compile(r"_zfill\w*$")


def merged(B, sid):
    """base mesh + its Z-fill continuation pieces (ids sid_zfill*) as one (v, f); hidden base included (the audit merges them the same way)"""
    parts = [it for it in B.items if it["e"]["id"] == sid or re.fullmatch(re.escape(sid) + r"_zfill\w*", it["e"]["id"])]
    vs, fs, off = [], [], 0
    for it in parts:
        v, f = B.mesh(it)
        vs.append(v)
        fs.append(f + off)
        off += len(v)
    return (np.concatenate(vs), np.concatenate(fs)) if vs else None, [it["e"]["id"] for it in parts]


def own_context(B):
    fixed = {}
    for i in ARM_OWN:
        m, _ids = merged(B, i)
        if m is not None:
            fixed[i] = m
    bones = {}
    for i in OWN_BONES:
        g = B.get(i)
        if g is not None:
            bones[i] = (g["v"], g["f"])
    sk = B.get("skin")
    skin = C.SkinGuard([dict(v=sk["v"], f=sk["f"], sys="skin", id="skin")], zone_lo=(-330.0, 40.0, -160.0), zone_hi=(-60.0, 360.0, 200.0), close=1)
    return fixed, bones, skin


def polish(src="zan_ends.pkl", dst="own_polish.pkl", rounds=12):
    B = Bundle(SRC_BUNDLE)
    fixed, bones, skin = own_context(B)
    d = pickle.load(open(CACHE / src, "rb"))
    zone = pickle.load(open(CACHE / "zan_zone.pkl", "rb"))
    mov = {i: d[i] for i in d if i in zone and zone[i]["sys"] == "muscle" and i in C.side_ids(C.FOREARM)}
    sp = SL.Separator(mov, fixed, bones, skin)
    lams = [3.0, 1.5, 0.75, 0.75, 0.4, 0.4, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
    for k, lam in enumerate(lams[:rounds]):
        t = time.time()
        tot = sp.step(lam)
        mv = np.mean([np.linalg.norm(sp.x[i] - sp.x0[i], axis=1).mean() for i in sp.ids])
        print(k, lam, {n: (v[0], round(v[1]), round(v[2], 1)) for n, v in tot.items()}, "mean move", round(mv, 2), round(time.time() - t), flush=True)
        pickle.dump({i: (sp.x[i], sp.f[i]) for i in sp.ids}, open(CACHE / dst, "wb"))


if __name__ == "__main__":
    st = sys.argv[1]
    {"polish": polish}[st]()
