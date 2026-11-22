#!/usr/bin/env python3
"""Q217: caches for the left-forearm work (all under build/q217_cache, git-ignored, re-made by this script):
  photo_l.npy   his photographed tissue classes of the left arm on a 1 mm atlas grid (q217_photo.Photos)
  zan_zone.pkl  the Z male fitted page's left forearm / arm muscles + bones (Q211 page)
  own_zone.pkl  the own male page's left arm structures (Q214 page, continuation pieces kept as separate ids)
    python3 scripts/transfer/q217_prep.py [photo|zan|own ...]"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
CACHE = REPO / "build" / "q217_cache"


def photo():
    from scripts.transfer.q217_photo import Photos
    P = Photos("l")
    np.save(CACHE / "photo_l.npy", P.cls)


def zan():
    from scripts.transfer import q217_common as C
    S = C.zan_left("zan_m")
    keep = {i: dict(v=s["v"], f=s["f"], sys=s["sys"], rec=s.get("rec")) for i, s in S.items()
            if i in C.side_ids(C.FOREARM) or i in C.side_ids(C.ARM) or (s["sys"] == "bone" and s["v"][:, 0].max() < -60 and s["v"][:, 1].min() < 345)}
    pickle.dump(keep, open(CACHE / "zan_zone.pkl", "wb"))


def own():
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(REPO / "build/viewer_m_hr_q214")
    out = {}
    for it in B.items:
        e = it["e"]
        v, f = B.mesh(it)
        if len(v) and v[:, 0].min() < -80 and v[:, 1].max() > 60 and v[:, 1].min() < 420 and v[:, 0].max() < -40:
            out[e["id"]] = dict(v=v, f=f, cat=e["cat"], sys=e["cat"], side=e["side"], subject=e["subject"], hidden=bool(e.get("hidden_default")), rec=e.get("rec"))
    pickle.dump(out, open(CACHE / "own_zone.pkl", "wb"))


if __name__ == "__main__":
    CACHE.mkdir(parents=True, exist_ok=True)
    for w in (sys.argv[1:] or ["photo", "zan", "own"]):
        globals()[w]()
        print("done", w, flush=True)
