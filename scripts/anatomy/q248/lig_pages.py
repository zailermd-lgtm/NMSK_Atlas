"""Q248: the six current pages as {id: entry} (atlas frame, mm; +X right, +Y sup, +Z ant) + a lazy signed-distance field to their bones.
Source dirs: Q248_SRC_<key> or <Q248_ROOT or build/q244>/<page dir> (the Q244 page dirs = the Q243 pages + the Q241 pose rigs)."""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
for p in (REPO, REPO / "scripts" / "anatomy"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
DIRS = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
STEM = {"own_m": "atlas_viewer_male", "own_f": "atlas_viewer_female", "base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female", "comb_m": "atlas_viewer_zan_male_fitted", "comb_f": "atlas_viewer_zan_female"}
FEMALE = ("own_f", "comb_f", "base_f")
ROOT = os.environ.get("Q248_ROOT", "build/q244")


def page_dir(key, root=None):
    return os.environ.get("Q248_SRC_" + key) or f"{root or ROOT}/{DIRS[key]}"


def load(key, root=None):
    """-> dict id -> {id,name,sys,side,v,f,src,rec}"""
    for k in DIRS:
        os.environ["Q233_SRC_" + k] = page_dir(k, root)
    import q233_load as Q
    return {s["id"]: s for s in Q.load(key)}


def mesh(e):
    return trimesh.Trimesh(e["v"], e["f"], process=False)


def outward_normals(m):
    """face normals pointing OUT of the solid: the winding of some page meshes is inverted (38 of 443 muscles / organs of the Imaging-based F page have negative signed volume), the sign of the volume decides"""
    n = np.asarray(m.face_normals, np.float32)
    try:
        if m.volume < 0:
            n = -n
    except Exception:  # noqa: BLE001
        pass
    return n


class BoneField:
    """signed distance (negative inside) to bone entries; surface sample ~1 point / 0.05 mm^2 (cap 300k) per bone, sign from the sampled face normal"""
    def __init__(self, entries):
        self.items = {}
        self.entries = entries

    def _get(self, bid):
        if bid not in self.items:
            m = mesh(self.entries[bid])
            n = int(min(300000, max(20000, m.area / 0.05)))
            np.random.seed(0)
            pts, fi = trimesh.sample.sample_surface(m, n, seed=0)
            self.items[bid] = (cKDTree(pts), outward_normals(m)[fi], m)
        return self.items[bid]

    def near(self, V, ids, margin=12.0):
        """the ids whose bounding box lies within margin of the points"""
        lo, hi = np.min(V, 0) - margin, np.max(V, 0) + margin
        out = []
        for i in ids:
            e = self.entries[i]
            if (e["v"].min(0) <= hi).all() and (e["v"].max(0) >= lo).all():
                out.append(i)
        return out

    def signed(self, V, ids):
        """-> (signed distance (n,), index into ids of the nearest bone (n,), outward normal (n,3), nearest surface point (n,3))"""
        V = np.asarray(V, float)
        best = np.full(len(V), np.inf); arg = np.zeros(len(V), int); nrm = np.zeros((len(V), 3)); pt = np.zeros((len(V), 3))
        for k, bid in enumerate(ids):
            kd, nn, m = self._get(bid)
            d, i = kd.query(V)
            p = kd.data[i]; n = nn[i]
            s = np.sign(((V - p) * n).sum(1)); s[s == 0] = 1
            upd = d < np.abs(best)
            best = np.where(upd, d * s, best); arg = np.where(upd, k, arg); nrm[upd] = n[upd]; pt[upd] = p[upd]
        return best, arg, nrm, pt
