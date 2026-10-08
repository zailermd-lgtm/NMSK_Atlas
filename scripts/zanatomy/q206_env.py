"""Q206 page environment: the DISPLAYED bones and the DISPLAYED skin of a page (what the unchanged Q198 audit judges soft tissue against), as fast fields for the per-structure guards.
inside-bone depth = the Q198 bone-fill measure (voxel solids of every displayed bone, h = 1.5 mm, depth > 1.5 mm counts); outside skin = the Q198 SkinField (h = 3 mm, 2 closing steps; > 3 mm counts).
Both are used as trilinear signed fields with gradients to push a structure out of a bone / back inside the skin."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q206_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.zanatomy.q198_core import Grid, SkinField  # noqa: E402
from scripts.zanatomy.q198_audit import female_sealers  # noqa: E402


class Fields:
    def __init__(self, sd, lo, h):
        self.sd, self.lo, self.h = sd.astype(np.float32), np.asarray(lo, float), float(h)
        sm = ndi.gaussian_filter(self.sd, 0.8)
        self.grad = [ndi.sobel(sm, axis=a, mode="nearest") / (8.0 * self.h) for a in range(3)]

    def _c(self, P):
        return ((np.asarray(P, float) - self.lo) / self.h).T

    def value(self, P, outside=50.0):
        c = self._c(P)
        inb = ((c >= 0) & (c <= np.array(self.sd.shape)[:, None] - 1)).all(0)
        r = np.full(len(P), outside, np.float32)
        if inb.any():
            r[inb] = ndi.map_coordinates(self.sd, c[:, inb], order=1, mode="nearest")
        return r

    def gradient(self, P):
        c = self._c(P)
        g = np.stack([ndi.map_coordinates(a, c, order=1, mode="nearest") for a in self.grad], 1)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(n, 1e-6)


class Env:
    """page_key: q198_load key of the page whose bones / skin are the reference.  box: (lo, hi) of the local bone grid (the wrist / hand region)"""

    def __init__(self, page_key, log=print, h_bone=1.5):
        self.S = load(page_key)
        self.by = {}
        for s in self.S:
            self.by.setdefault(s["id"], s)
        skin = [s for s in self.S if s["sys"] == "skin" or s["id"] == "skin"]
        log(f"  env {page_key}: {len(self.S)} structures, {len(skin)} skin patches")
        cache = REPO / "build" / "q206" / f"skinfield_{page_key}.npz"
        if cache.exists():
            z = np.load(cache)
            self.skin = Fields(z["sd"], z["lo"], float(z["h"]))
            self.skin_vol_L = float(z["vol"])
        else:
            sk = SkinField(skin + female_sealers("z_female_fit" if page_key.endswith("_f") else "z_male_fit", self.S), 3.0, close=2)
            self.skin = Fields(sk.sd, sk.g.lo, sk.g.h)
            self.skin_vol_L = sk.vol_L
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez(cache, sd=sk.sd, lo=sk.g.lo, h=sk.g.h, vol=sk.vol_L)
        from scripts.zanatomy.q198_joints import find_joints
        J, B, lev = find_joints(self.S)
        self.wrist = {j["side"]: j["centre"] for j in J if j["name"] == "wrist"}
        self.bone, self.bone_ids, self.box = {}, {}, {}
        for side, c in self.wrist.items():
            s_ = "_" + side
            pts = [s["v"] for s in self.S if s["sys"] == "bone" and s["id"].endswith(s_) and re.search(r"carpal|finger_of_hand|phalanges_hand|scaphoid|lunate|triquetrum|pisiform|trapezium|trapezoid|capitate|hamate", s["id"])]
            pts += [s["v"][np.linalg.norm(s["v"] - c, axis=1) < 170.0] for s in self.S if s["sys"] == "bone" and s["id"] in ("radius" + s_, "ulna" + s_)]
            V = np.vstack(pts)
            lo, hi = V.min(0) - 45.0, V.max(0) + 45.0
            g = Grid(lo, hi, h_bone)
            uni = np.zeros(g.shape, bool)
            ids = []
            for s in self.S:
                if s["sys"] != "bone":
                    continue
                v = s["v"]
                if ((v > lo) & (v < hi)).all(1).any():
                    uni |= g.solid(v, s["f"], close=1)
                    ids.append(s["id"])
            din = ndi.distance_transform_edt(uni, sampling=h_bone).astype(np.float32)
            dout = ndi.distance_transform_edt(~uni, sampling=h_bone).astype(np.float32)
            self.bone[side] = Fields(dout - din, g.lo, h_bone)         # < 0 inside (depth = -value)
            self.bone_ids[side], self.box[side] = ids, (lo, hi)
            log(f"  env bone grid {side}: {g.shape}, {len(ids)} bones")

    # ---- audit-aligned measures
    def depth(self, P, side):
        """mm below the bone surface (> 0 inside); points outside the local grid -> 0"""
        return np.maximum(-self.bone[side].value(P, outside=1.0), 0.0)

    def skin_sd(self, P):
        return self.skin.value(P)

    def measure(self, v, side):
        d = self.depth(v, side)
        s = self.skin_sd(v)
        return {"outside_skin_pct": round(100 * float((s > 3).mean()), 2), "outside_skin_max_mm": round(float(max(s.max(), 0)), 1),
                "inside_bone_pct": round(100 * float((d > 1.5).mean()), 2), "inside_bone_max_mm": round(float(d.max()), 1)}
