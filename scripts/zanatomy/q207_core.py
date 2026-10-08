"""Q207 core: page loading, hand / wrist zone, fine skin clearance of the DISPLAYED outer skin sheet (Q198 SkinSurf) and the bone-anchored skin inflation field.
Everything works on the DECODED shipped geometry of a page (skin patches are not decimated, so skin edits are exact up to the page's 16-bit quantisation)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_pages as P2  # noqa: E402

PAGES = {
    "male": dict(src=REPO / "build/q206/viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted", out=REPO / "build/q207/viewer_zan_vhm", raw="base_m", own="own_m", sealers="z_male_fit"),
    "female": dict(src=REPO / "build/q206/viewer_zan_female", stem="atlas_viewer_zan_female", out=REPO / "build/q207/viewer_zan_female", raw="base_f", own="own_f", sealers="z_female_fit"),
}
REGIONS = None
ARM_REGIONS = ("upper_limb", "forearm_hand")
HAND_RE = re.compile(r"metacarpal|finger_of_hand|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate")
ZONE_HAND_MM, ZONE_WRIST_MM = 35.0, 110.0
LIMB_SKIN_RE = re.compile(r"forearm|wrist|hand|palm|nail_plate|perionyx|foveola|cubital|elbow|arm_region|region_of_arm|deltoid|posterior_region_of_arm|anterior_region_of_arm|lateral_region_of_arm|medial_region_of_arm")


def regions():
    global REGIONS
    if REGIONS is None:
        REGIONS = json.loads((REPO / "data/derived/Q168_zan_to_vhf.json").read_text())["region_of_structure"]
    return REGIONS


class Page:
    def __init__(self, which, src=None, stem=None):
        self.which = which
        self.cfg = PAGES[which]
        self.dir = Path(src or self.cfg["src"])
        self.man, self.blob = P2.load_page(self.dir, stem or self.cfg["stem"])
        self.S = P2.decode(self.man, self.blob)
        self.ids = list(self.S)
        self.skin_ids = [i for i, e in self.S.items() if e["m"]["sys"] == "skin"]

    def v(self, i):
        return self.S[i]["v"]

    def f(self, i):
        return self.S[i]["f"]

    def sys(self, i):
        return self.S[i]["m"]["sys"]

    def wrist(self):
        """wrist joint centres {side: xyz} (Q198 find_joints on the decoded page)"""
        from scripts.zanatomy.q198_joints import find_joints
        L = [dict(id=i, name=e["m"]["name"], sys=e["m"]["sys"], side=e["m"]["side"], v=e["v"], f=e["f"], src="zan", rec=e["m"].get("rec") or {}) for i, e in self.S.items()]
        # unique bone ids as the q198 loader does
        cnt = {}
        for s in L:
            if s["sys"] == "bone":
                cnt[s["id"]] = cnt.get(s["id"], 0) + 1
        seen = {}
        for s in L:
            if s["sys"] == "bone" and cnt[s["id"]] > 1:
                seen[s["id"]] = seen.get(s["id"], 0) + 1
                s["id"] = f"{s['id']}#{seen[s['id']]}"
        J, B, lev = find_joints(L)
        return {j["side"]: np.asarray(j["centre"], float) for j in J if j["name"] == "wrist"}

    def zone_structs(self, side, wrist, vertex_zone=True):
        """-> {id: boolean vertex mask} of the non-skin structures of the arm regions of `side` whose vertices lie in the hand / wrist zone"""
        s = "_" + side
        reg = regions()
        hand = np.vstack([self.v(i) for i in self.ids if self.sys(i) == "bone" and i.endswith(s) and HAND_RE.search(i)])
        ht = cKDTree(hand)
        out = {}
        for i in self.ids:
            if self.sys(i) == "skin" or not (i.endswith(s) or s + "_" in i) or reg.get(i) not in ARM_REGIONS:
                continue
            v = self.v(i)
            m = (np.linalg.norm(v - wrist, axis=1) < ZONE_WRIST_MM) | (ht.query(v)[0] < ZONE_HAND_MM)
            if m.any():
                out[i] = m
        return out


def slab_sheets(v, f):
    """thin-slab skin patch -> (split index s, outer vertex mask, outer face mask, inner face mask).  The builder writes the two sheets as index halves [0:s) and [s:n); the rim wall faces mix the halves.
    The outer sheet = the half farther from the other half's... decided by the caller with bone points; here both candidate halves are returned as masks over vertices."""
    n = len(v)
    best, bs = -1, n // 2
    lo, hi = int(0.30 * n), int(0.70 * n)
    mx, mn = f.max(1), f.min(1)
    for s in range(lo, hi):
        c = int((mx < s).sum() + (mn >= s).sum())
        if c > best:
            best, bs = c, s
    return bs


def tri_area(V, F):
    return 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)


class Outer:
    """the OUTER sheet of the displayed skin near a wrist: faces of the closed, outward-wound slabs whose normal points away from the nearest bone (the inner sheet and the rim wall face the other way);
    dense surface samples with normals -> signed clearance (mm, + = outside the outer sheet) of any point by the nearest sample."""

    def __init__(self, page, centre, radius, bone_pts, spacing=1.0, V=None, side=None, outer_cos=0.4):
        Vs, Fs, off = [], [], 0
        self.patch_of_face = []
        self.ids = []
        for k, i in enumerate(page.skin_ids):
            v = page.v(i) if V is None else V[i]
            if side is not None and not (i.endswith("_" + side) and LIMB_SKIN_RE.search(i)):
                continue
            if np.linalg.norm(v - centre, axis=1).min() > radius:
                continue
            Vs.append(v)
            Fs.append(page.f(i) + off)
            off += len(v)
            self.patch_of_face += [len(self.ids)] * len(page.f(i))
            self.ids.append(i)
        self.V = np.vstack(Vs)
        self.F = np.vstack(Fs)
        self.patch_of_face = np.asarray(self.patch_of_face)
        t = self.V[self.F]
        nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        ar = 0.5 * np.linalg.norm(nrm, axis=1)
        nrm /= np.maximum(2 * ar[:, None], 1e-12)
        cen = t.mean(1)
        bt = cKDTree(bone_pts)
        d, k = bt.query(cen)
        dirv = cen - bone_pts[k]
        dirv /= np.maximum(np.linalg.norm(dirv, axis=1, keepdims=True), 1e-9)
        self.outer = (nrm * dirv).sum(1) > outer_cos        # rim wall faces (normal along the surface) are not outer sheet
        Fo = self.F[self.outer]
        self.Fo, self.No = Fo, nrm[self.outer]
        a = ar[self.outer]
        kk = int(min(2_000_000, max(len(Fo), a.sum() / spacing ** 2)))
        rng = np.random.default_rng(1)
        idx = rng.choice(len(Fo), kk, p=a / a.sum())
        u = rng.random((kk, 2))
        m = u.sum(1) > 1
        u[m] = 1 - u[m]
        tt = self.V[Fo[idx]]
        self.P = tt[:, 0] + u[:, :1] * (tt[:, 1] - tt[:, 0]) + u[:, 1:] * (tt[:, 2] - tt[:, 0])
        self.N = self.No[idx]
        self.tree = cKDTree(self.P)

    def signed(self, p):
        p = np.asarray(p, float)
        d, i = self.tree.query(p)
        s = ((p - self.P[i]) * self.N[i]).sum(1)
        return np.where(s > 0, d, -d).astype(np.float32)


class Fine:
    """FINE local skin envelope of a box (h ~ 1 mm): all skin patches rasterised + closed by one voxel, the OUTSIDE = the connected empty space that touches a seed (voxels the sealed Q198 coarse field
    (h = 3 mm, closing 2) calls clearly outside: > `seed_mm`, plus the box faces where the coarse field is outside); everything else is inside the skin.  Unlike the sealed coarse field the web between
    fingers stays outside.  sd = signed distance to the envelope surface (+ outside), trilinear."""

    def __init__(self, page, V, coarse, lo, hi, h=1.0, seed_mm=1.5, close=2, patches=None, deep_mm=5.0):
        from scipy import ndimage as ndi
        from scripts.zanatomy.q198_core import Grid
        self.h, self.lo = float(h), np.asarray(lo, float)
        g = Grid(lo, hi, h)
        self.shape = g.shape
        surf = np.zeros(g.shape, bool)
        for i in (patches or page.skin_ids):
            v = V[i]
            if ((v > lo - 5) & (v < hi + 5)).all(1).any():
                surf |= g.raster(v, page.f(i))
        cl = ndi.binary_dilation(surf, iterations=close) if close else surf
        ix = np.stack(np.meshgrid(*[np.arange(s) for s in g.shape], indexing="ij"), -1)
        P = self.lo + ix.reshape(-1, 3) * h
        csd = coarse.value(P, outside=50.0).reshape(g.shape)
        seeds = (csd > seed_mm) & ~cl
        lab, nl = ndi.label(~cl)
        keep = np.unique(lab[seeds])
        keep = keep[keep > 0]
        outside = np.isin(lab, keep) & ~(csd < -deep_mm)          # the deep interior of the sealed coarse envelope can never be reached through a seam gap
        self.inside = ~outside
        d_in = ndi.distance_transform_edt(self.inside, sampling=h).astype(np.float32)
        d_out = ndi.distance_transform_edt(outside, sampling=h).astype(np.float32)
        self.sd = np.where(self.inside, -(d_in - 0.5 * h), d_out - 0.5 * h).astype(np.float32)
        self.coarse_sd = csd

    def value(self, p, outside=50.0):
        from scipy import ndimage as ndi
        c = ((np.asarray(p, float) - self.lo) / self.h).T
        inb = ((c >= 0) & (c <= np.array(self.shape)[:, None] - 1)).all(0)
        r = np.full(len(p), outside, np.float32)
        if inb.any():
            r[inb] = ndi.map_coordinates(self.sd, c[:, inb], order=1, mode="nearest")
        return r
