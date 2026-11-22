"""Q388 nerve course audit -- shared measuring library (read-only on the page data).

Frame of the Base pages (checked on the data, not assumed): millimetres, +y superior, +z anterior, +x = body RIGHT
(ids ending _r have x > 0). Geometry is decoded from the page files in build/q309/<dir> (scripts/anatomy/q340 page I/O);
a pickle cache can be kept in a scratch directory (env Q388_CACHE) so repeated runs take seconds.
"""
from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q340"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
from conform_palm_q340 import read_page, dec, stem_of  # noqa: E402
from lm import centerline as _geo_centerline            # noqa: E402

PAGES = {"base_m": "viewer_zan_atlas", "base_f": "viewer_base_female"}
SG = {"r": 1.0, "l": -1.0}


def load(key, page_dir=None, cache=None):
    """-> {id: dict(name, side, sys, V, F, rec)}"""
    cache = cache or os.environ.get("Q388_CACHE")
    if not page_dir and key not in PAGES and cache and (Path(cache) / f"{key}.pkl").exists():
        return pickle.load(open(Path(cache) / f"{key}.pkl", "rb"))
    d = Path(page_dir) if page_dir else REPO / "build/q309" / PAGES[key]
    if cache:
        cp = Path(cache) / f"{key}.pkl"
        if cp.exists() and cp.stat().st_mtime >= max(p.stat().st_mtime for p in d.glob("*_geo_0*.txt")):
            return pickle.load(open(cp, "rb"))
    st = stem_of(d)
    man, blob, _ = read_page(d, st)
    out = {}
    for m in man["meshes"]:
        V, F = dec(m, blob)
        out[m["id"]] = dict(name=m["name"], side=m.get("side"), sys=m.get("sys"), V=V.astype(np.float32),
                            F=F.astype(np.int32), rec=m.get("rec", {}))
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        pickle.dump(out, open(Path(cache) / f"{key}.pkl", "wb"))
    return out


class LazyPage(dict):
    """{id: mesh dict} decoded on first access (the verifier touches ~150 of ~3300 meshes); .meta[id] has name/sys/side/rec
    and the manifest bbox (min, min + span) without decoding."""

    def __init__(self, page_dir):
        super().__init__()
        d = Path(page_dir)
        man, blob, _ = read_page(d, stem_of(d))
        self._blob = blob
        self._m = {m["id"]: m for m in man["meshes"]}
        self.meta = {k: dict(name=m["name"], side=m.get("side"), sys=m.get("sys"), rec=m.get("rec", {}),
                             lo=np.asarray(m["min"], float), hi=np.asarray(m["min"], float) + np.asarray(m["span"], float))
                     for k, m in self._m.items()}

    def __contains__(self, k):
        return k in self._m

    def __missing__(self, k):
        m = self._m[k]
        V, F = dec(m, self._blob)
        v = dict(name=m["name"], side=m.get("side"), sys=m.get("sys"), V=V.astype(np.float32), F=F.astype(np.int32),
                 rec=m.get("rec", {}))
        self[k] = v
        return v

    def get(self, k, default=None):
        return self[k] if k in self._m else default

    def keys(self):
        return self._m.keys()

    def items(self):
        return ((k, self[k]) for k in self._m)


def centreline(m, n=90, top_first=True):
    C = _geo_centerline(m["V"], m["F"], n=n)
    if C is None:
        return None
    if top_first and C[0, 1] < C[-1, 1]:
        C = C[::-1]
    return C


def arclen(C):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))]


def local_radius(m, C):
    """mean distance of the mesh's vertices to their nearest centreline point, per centreline point."""
    t = cKDTree(C)
    dd, ii = t.query(m["V"])
    r = np.array([dd[ii == k].mean() if (ii == k).any() else np.nan for k in range(len(C))])
    return r


class Scene:
    """muscles / bones / vessels of one page, for nearest-surface and ray queries."""

    def __init__(self, D, systems=("muscle", "bone")):
        self.D = D
        meta = getattr(D, "meta", None)
        if meta is not None:
            self.ids = [k for k, v in meta.items() if v["sys"] in systems]
            self.lo = np.array([meta[k]["lo"] for k in self.ids])
            self.hi = np.array([meta[k]["hi"] for k in self.ids])
        else:
            self.ids = [k for k, v in D.items() if v["sys"] in systems and len(v["F"])]
            self.lo = np.array([D[k]["V"].min(0) for k in self.ids])
            self.hi = np.array([D[k]["V"].max(0) for k in self.ids])
        self._kd = {}

    def near_ids(self, p, rad):
        p = np.asarray(p)
        ok = np.all((self.lo - rad <= p) & (p <= self.hi + rad), axis=1)
        return [self.ids[i] for i in np.where(ok)[0]]

    def kd(self, k):
        if k not in self._kd:
            self._kd[k] = cKDTree(self.D[k]["V"])
        return self._kd[k]

    def rays(self, p, dirs, rad=90.0, skip=()):
        """first mesh hit along each direction from p, and the set of meshes p lies inside (odd hit count on +z and -z).
        -> (list of (id, dist) or (None, None), inside_ids)"""
        ids = [k for k in self.near_ids(p, rad) if k not in skip]
        if not ids:
            return [(None, None)] * len(dirs), []
        Vs, Fs, lab, off = [], [], [], 0
        for j, k in enumerate(ids):
            Vs.append(self.D[k]["V"]); Fs.append(self.D[k]["F"] + off); lab.append(np.full(len(self.D[k]["F"]), j))
            off += len(self.D[k]["V"])
        M = trimesh.Trimesh(np.vstack(Vs), np.vstack(Fs), process=False)
        lab = np.concatenate(lab)
        I = trimesh.ray.ray_triangle.RayMeshIntersector(M)
        dirs = np.asarray(dirs, float)
        O = np.repeat(np.asarray(p, float)[None], len(dirs), 0)
        loc, ri, ti = I.intersects_location(O, dirs, multiple_hits=True)
        first = []
        for r in range(len(dirs)):
            s = ri == r
            if not s.any():
                first.append((None, None)); continue
            dist = np.linalg.norm(loc[s] - p, axis=1)
            j = np.argmin(dist)
            first.append((ids[lab[ti[s][j]]], float(dist[j])))
        inside = []
        for r in range(len(dirs)):
            s = ri == r
            cnt = np.bincount(lab[ti[s]], minlength=len(ids)) if s.any() else np.zeros(len(ids), int)
            inside.append(set(np.where(cnt % 2 == 1)[0]))
        both = set.intersection(*inside) if inside else set()
        return first, [ids[j] for j in sorted(both)]

    def min_dist(self, pts, k):
        dd, _ = self.kd(k).query(np.asarray(pts))
        return float(dd.min())


def slab(V, y, h=2.0):
    return V[np.abs(V[:, 1] - y) < h]


def winding(V, F, P):
    """generalised winding number of points P w.r.t. triangle soup (V, F): ~1 inside, ~0 outside, robust to small holes
    and multi-part meshes (van Oosterom-Strackee solid angle per triangle)."""
    V = np.asarray(V, float); P = np.atleast_2d(np.asarray(P, float))
    A, B, Cc = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    out = np.empty(len(P))
    step = max(1, int(4e6 // max(len(F), 1)))
    for s0 in range(0, len(P), step):
        p = P[s0:s0 + step, None, :]
        a, b, c = A[None] - p, B[None] - p, Cc[None] - p
        la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
        det = np.einsum("pij,pij->pi", a, np.cross(b, c))
        den = (la * lb * lc + np.einsum("pij,pij->pi", a, b) * lc + np.einsum("pij,pij->pi", b, c) * la
               + np.einsum("pij,pij->pi", c, a) * lb)
        out[s0:s0 + step] = np.arctan2(det, den).sum(1) * 2.0 / (4 * np.pi)
    return out


def inside_ids(sc, p, rad=60.0, thr=0.5, systems=None):
    """meshes of the scene whose winding number at p exceeds thr (sign-agnostic: some sources are inward-oriented)."""
    res = []
    for k in sc.near_ids(p, 1.0):
        if systems and sc.D[k]["sys"] not in systems:
            continue
        w = abs(winding(sc.D[k]["V"], sc.D[k]["F"], p)[0])
        if w > thr:
            res.append((k, round(float(w), 2)))
    return res


def slice_segments(V, F, y):
    """intersection segments of the triangle mesh with the plane y = const -> (n, 2, 2) array of (x, z) end points, each
    oriented by its triangle's normal (direction (-nz, nx), i.e. n x y_hat), so that a closed oriented surface gives
    oriented loops and the 2-D winding number (non-zero rule) is defined even where several bodies of one mesh overlap."""
    V = np.asarray(V, float); F = np.asarray(F)
    d = V[:, 1] - y
    dF = d[F]
    pos = dF > 0
    cross = pos.any(1) & ~pos.all(1)
    if not cross.any():
        return np.zeros((0, 2, 2))
    Fc, dc, pc = F[cross], dF[cross], pos[cross]
    P = V[Fc]                                   # (m, 3, 3)
    nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    out = np.zeros((len(Fc), 2, 2)); k = np.zeros(len(Fc), int)
    for a, b in ((0, 1), (1, 2), (2, 0)):
        m = pc[:, a] != pc[:, b]
        tt = dc[m, a] / (dc[m, a] - dc[m, b])
        q = P[m, a] + tt[:, None] * (P[m, b] - P[m, a])
        rows = np.where(m)[0]
        sl = np.minimum(k[rows], 1)
        out[rows, sl] = q[:, [0, 2]]
        k[rows] += 1
    ok = k == 2
    out, nrm = out[ok], nrm[ok]
    dirv = out[:, 1] - out[:, 0]
    flip = (dirv[:, 0] * -nrm[:, 2] + dirv[:, 1] * nrm[:, 0]) < 0
    out[flip] = out[flip][:, ::-1]
    return out


def inside_slice(segs, P2):
    """2-D winding number (non-zero rule) of the oriented slice segments along +x, -x, +z, -z rays; inside where at least
    3 of the 4 rays give |winding| >= 1 (tolerates small holes in a source mesh and overlapping bodies of one mesh;
    sign-agnostic, so inward-oriented sources work too)."""
    if not len(segs):
        return np.zeros(len(P2), bool)
    P2 = np.asarray(P2, float)
    a, b = segs[:, 0], segs[:, 1]
    votes = np.zeros(len(P2), int)
    for ax, sgn in ((0, 1), (0, -1), (1, 1), (1, -1)):
        o = 1 - ax
        lo = np.minimum(a[:, o], b[:, o]); hi = np.maximum(a[:, o], b[:, o])
        po = P2[:, o][:, None]
        straddle = (po >= lo[None]) & (po < hi[None])
        den = np.where(b[:, o] - a[:, o] == 0, 1, b[:, o] - a[:, o])
        t = (po - a[None, :, o]) / den[None]
        xc = a[None, :, ax] + t * (b[None, :, ax] - a[None, :, ax])
        hit = straddle & ((xc - P2[:, ax][:, None]) * sgn > 0)
        sgnseg = np.sign(b[:, o] - a[:, o])[None]
        w = (hit * sgnseg).sum(1)
        votes += (np.abs(w) >= 1)
    return votes >= 3
