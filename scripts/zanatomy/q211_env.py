"""Q211 environment of a Z-fitted page: the DISPLAYED skin (Q198 SkinField, > 3 mm outside counts) as one whole-body signed field, and the DISPLAYED bones as local signed fields per ZONE (Q198 bone fill: voxel solids,
h = 1.5 mm, closing 1; depth > 1.5 mm counts).  Both with trilinear values and gradients (q206_env.Fields).  `zone` is the `side` argument of the q206_carry guards (push_out / clamp_skin / metrics)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q211_core as K  # noqa: E402
from scripts.zanatomy.q206_env import Fields  # noqa: E402
from scripts.zanatomy.q198_core import Grid, SkinField  # noqa: E402


def q198_list(pg, V=None):
    """decoded page -> the q198_load structure list (unique bone ids as the loader does); V = {id: vertices} overrides"""
    V = V or {}
    L = [dict(id=i, name=e["m"]["name"], sys=e["m"]["sys"], side=e["m"]["side"], v=np.asarray(V.get(i, e["v"]), float), f=e["f"], src="zan", rec=e["m"].get("rec") or {}) for i, e in pg.S.items()]
    cnt = {}
    for s in L:
        if s["sys"] == "bone":
            cnt[s["id"]] = cnt.get(s["id"], 0) + 1
    seen = {}
    for s in L:
        if s["sys"] == "bone" and cnt[s["id"]] > 1:
            seen[s["id"]] = seen.get(s["id"], 0) + 1
            s["id"] = f"{s['id']}#{seen[s['id']]}"
    return L


class Env:
    def __init__(self, which, pg, V=None, log=print, h_bone=1.5, skin_cache=None):
        self.which, self.pg = which, pg
        self.V = dict(V or {})
        self.S = q198_list(pg, V)
        self.by = {s["id"]: s for s in self.S}
        cache = Path(skin_cache) if skin_cache else REPO / "build" / "q211" / f"skinfield_{K.PAGES[which]['key0']}.npz"
        if cache.exists():
            z = np.load(cache)
            self.skin = Fields(z["sd"], z["lo"], float(z["h"]))
        else:
            from scripts.zanatomy.q198_audit import female_sealers
            skin = [s for s in self.S if s["sys"] == "skin" or s["id"] == "skin"]
            key = K.PAGES[which]["fit_key"]
            sk = SkinField(skin + female_sealers(key, self.S), 3.0, close=2)
            self.skin = Fields(sk.sd, sk.g.lo, sk.g.h)
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez(cache, sd=sk.sd, lo=sk.g.lo, h=sk.g.h, vol=sk.vol_L)
        self.bone, self.box, self.bone_ids = {}, {}, {}
        self.h_bone = h_bone
        self.log = log

    def add_zone(self, name, lo, hi):
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        g = Grid(lo, hi, self.h_bone)
        uni = np.zeros(g.shape, bool)
        ids = []
        for s in self.S:
            if s["sys"] != "bone":
                continue
            v = s["v"]
            if ((v > lo) & (v < hi)).all(1).any():
                uni |= g.solid(v, s["f"], close=1)
                ids.append(s["id"])
        h = self.h_bone
        din = ndi.distance_transform_edt(uni, sampling=h).astype(np.float32)
        dout = ndi.distance_transform_edt(~uni, sampling=h).astype(np.float32)
        self.bone[name] = Fields(dout - din, g.lo, h)
        self.box[name], self.bone_ids[name] = (lo, hi), ids
        self.log(f"  env zone {name}: grid {g.shape}, {len(ids)} bones")

    def zone_of(self, P, pad=0.0):
        """the zone whose box holds all of P (first match), else None"""
        P = np.asarray(P)
        for n, (lo, hi) in self.box.items():
            if (P.min(0) >= lo + pad).all() and (P.max(0) <= hi - pad).all():
                return n
        return None

    def depth(self, P, zone):
        return np.maximum(-self.bone[zone].value(P, outside=1.0), 0.0)

    def skin_sd(self, P):
        return self.skin.value(P)

    def measure(self, v, zone):
        d = self.depth(v, zone)
        s = self.skin_sd(v)
        return {"outside_skin_pct": round(100 * float((s > 3).mean()), 2), "outside_skin_max_mm": round(float(max(s.max(), 0)), 1),
                "inside_bone_pct": round(100 * float((d > 1.5).mean()), 2), "inside_bone_max_mm": round(float(d.max()), 1)}
