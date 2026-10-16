"""Q243 (3): the HRA (Visible Human FEMALE) vertebral column, intervertebral disks (nucleus pulposus) and spinal cord segments onto the page's own vertebral column: one rigid + uniform-scale
fit PER VERTEBRA (HRA vertebra -> the page's vertebra of the same rank: 7 cervical, 12 thoracic, 6 lumbar, counted from the top), then linear blending of the two neighbouring vertebral
transforms for everything between them (disk nucleus: halfway between the two vertebrae; cord segment: by height between the vertebrae). The HRA names six lumbar vertebrae L1-L6 (the object
description says: 'The Visible Human Female has 6 lumbar vertebrae'); the page has six lumbar bodies too (Q185k: the extra named L1B)."""
from __future__ import annotations
import re, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q243 import hra  # noqa: E402
from scripts.anatomy.q233 import hra_register as H  # noqa: E402

LEVELS = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 7)]
NODE = {**{f"C{i}": f"VH_F_cervical_vertebra_{i}" for i in range(1, 8)}, **{f"T{i}": f"VH_F_thoracic_vertebra_{i}" for i in range(1, 13)}, **{f"L{i}": f"VH_F_lumbar_vertebra_{i}" for i in range(1, 7)}}


def hra_vertebrae():
    N = hra.load_nodes("united-female", "|".join(v + "$" for v in NODE.values()))
    return {lv: N[NODE[lv]] for lv in LEVELS}


def page_vertebrae_own(B):
    """-> {level: Trimesh} the page's vertebrae by rank from the top (C1..C7, T1..T12, L1..L6): the bundle's `cervical_vertebrae` / `thoracic_vertebrae` / `lumbar_vertebrae` pieces sorted by height"""
    groups = {"cervical_vertebrae": [], "thoracic_vertebrae": [], "lumbar_vertebrae": []}
    for it in B.items:
        e = it["e"]
        if e["id"] in groups and "zfill" not in e["id"] and e["cat"] == "bone":
            v, f = B.mesh(it)
            groups[e["id"]].append((float(v[:, 1].mean()), v, f, e["id"]))
    out = {}
    for key, pre, n in (("cervical_vertebrae", "C", 7), ("thoracic_vertebrae", "T", 12), ("lumbar_vertebrae", "L", 6)):
        lst = sorted(groups[key], key=lambda t: -t[0])
        assert len(lst) == n, (key, len(lst))
        for k, (_, v, f, _) in enumerate(lst):
            out[f"{pre}{k + 1}"] = trimesh.Trimesh(v, f, process=False)
    return out


def _icp(src, dst_tree, dst_pts, s0=1.0, R0=None, t0=None, iters=60, trim=0.85, scale_lim=(0.8, 1.25)):
    s = s0
    R = np.eye(3) if R0 is None else R0
    t = (dst_pts.mean(0) - s * src.mean(0) @ R.T) if t0 is None else t0
    for _ in range(iters):
        P = s * src @ R.T + t
        d, i = dst_tree.query(P)
        keep = d <= np.quantile(d, trim)
        s, R, t = H.umeyama(src[keep], dst_pts[i[keep]], True)
        s = float(np.clip(s, *scale_lim))
        t = dst_pts[i[keep]].mean(0) - s * (src[keep] @ R.T).mean(0)
    P = s * src @ R.T + t
    d, _ = dst_tree.query(P)
    return s, R, t, d


def fit_levels(hv, pv, seed=0):
    """per-vertebra similarity HRA -> page. hv {lv: (V, F)}; pv {lv: Trimesh}. -> {lv: dict(T=(s,R,t), residual...)}, global fit"""
    rng = np.random.default_rng(seed); np.random.seed(seed)
    hs = {lv: trimesh.Trimesh(v, f, process=False).sample(6000) for lv, (v, f) in hv.items()}
    ps = {lv: trimesh.Trimesh(m.vertices, m.faces, process=False).sample(30000) for lv, m in pv.items()}
    # global fit on the whole column (lumbar + thoracic + cervical), initial scale 0.95 and the vertical offset of the column
    allh = np.vstack(list(hs.values())); allp = np.vstack(list(ps.values()))
    tree = cKDTree(allp)
    best = None
    for dy in (-20, 0, 20):
        s, R, t, d = _icp(allh, tree, allp, s0=0.95, t0=allp.mean(0) - 0.95 * allh.mean(0) + np.array([0, dy, 0.]), iters=80, trim=0.7)
        sc = float(np.median(d))
        if best is None or sc < best[0]:
            best = (sc, s, R, t)
    _, sG, RG, tG = best
    out = {}
    for lv in LEVELS:
        tr = cKDTree(ps[lv])
        s, R, t, d = _icp(hs[lv], tr, ps[lv], s0=sG, R0=RG, t0=tG, iters=60, trim=0.85)
        dd = tr.query(s * hs[lv] @ R.T + t)[0]
        # reverse direction (page -> HRA, same trimmed set)
        inv = cKDTree(hs[lv])
        back = inv.query(((ps[lv] - t) @ R) / s)[0] * s
        ang = float(np.degrees(np.arccos(np.clip((np.trace(R @ RG.T) - 1) / 2, -1, 1))))
        out[lv] = dict(T=(s, R, t), scale=round(float(s), 4), residual_median_mm=round(float(np.median(dd)), 2), residual_p90_mm=round(float(np.quantile(dd, .9)), 2),
                       residual_rms_mm=round(float(np.sqrt((dd ** 2).mean())), 2), reverse_median_mm=round(float(np.median(back)), 2), rotation_from_global_deg=round(ang, 2),
                       hra_centroid=np.asarray(hv[lv][0]).mean(0), page_centroid=pv[lv].vertices.mean(0))
    return out, dict(scale=round(float(sG), 4), R=RG, t=tG, median_mm=round(best[0], 2))


class Blend:
    """x' = (1 - w) T_a(x) + w T_b(x) with w from the height of x between the HRA centroids of vertebrae a and b"""
    def __init__(self, fits):
        self.lv = LEVELS
        self.fits = fits
        self.y = np.array([fits[l]["hra_centroid"][1] for l in self.lv])          # HRA heights, descending from C1 to L6
        self.T = [fits[l]["T"] for l in self.lv]

    def __call__(self, X, y_ref=None):
        X = np.asarray(X, float)
        y = X[:, 1] if y_ref is None else y_ref
        order = np.argsort(self.y)                                                # ascending
        ys = self.y[order]
        k = np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2)
        w = np.clip((y - ys[k]) / (ys[k + 1] - ys[k]), 0, 1)
        out = np.zeros_like(X)
        for kk in np.unique(k):
            m = k == kk
            Ta, Tb = self.T[order[kk]], self.T[order[kk + 1]]
            A = hra.to_world(Ta, X[m]); Bq = hra.to_world(Tb, X[m])
            out[m] = (1 - w[m])[:, None] * A + w[m][:, None] * Bq
        return out

    def disc(self, X, upper, lower):
        """a disk nucleus between vertebra `upper` and `lower` (levels): halfway blend of the two transforms"""
        A = hra.to_world(self.fits[upper]["T"], X); Bq = hra.to_world(self.fits[lower]["T"], X)
        return 0.5 * (A + Bq)


# ------------------------------------------------------------------------------------------------------------------------------ nucleus pulposus + spinal cord
ORD = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]
# disc k of the HRA = the disc BELOW vertebra k: (HRA node suffix, upper vertebra level, lower level)
DISCS = [("axis", "C2", "C3")] + [(f"{ORD[i - 1]}_cervical_vertebra", f"C{i}", f"C{i + 1}" if i < 7 else "T1") for i in range(3, 8)] \
    + [(f"{ORD[i - 1]}_thoracic_vertebra", f"T{i}", f"T{i + 1}" if i < 12 else "L1") for i in range(1, 13)] \
    + [(f"{ORD[i - 1]}_lumbar_vertebra", f"L{i}", f"L{i + 1}" if i < 6 else "S1") for i in range(1, 7)]
CORD = [(f"C{i}", f"VH_F_C{i}_segment_of_cervical_spinal_cord") for i in range(1, 9)] \
    + [(f"T{i}", f"VH_F_{('eigth' if i == 8 else ORD[i - 1])}_thoracic_spinal_cord_segment") for i in range(1, 13)] \
    + [(f"L{i}", f"VH_F_{ORD[i - 1]}_lumbar_spinal_cord_segment") for i in range(1, 6)] \
    + [(f"S{i}", f"VH_F_{ORD[i - 1]}_sacral_spinal_cord_segment") for i in range(1, 5)]


def hra_sacrum():
    N = hra.load_nodes("united-female", r"^VH_F_sacrum$")
    return N["VH_F_sacrum"]


def page_sacrum_own(B):
    best = None
    for it in B.items:
        e = it["e"]
        if e["id"] == "sacrum" and e["cat"] == "bone":
            v, f = B.mesh(it)
            if v[:, 1].min() < 40:                                   # the main sacrum (the second piece is the base fill)
                m = trimesh.Trimesh(v, f, process=False)
                cc = max(m.split(only_watertight=False), key=lambda c: len(c.vertices))
                best = cc
    return best


def fit_sacrum(fits, hs_v, hs_f, psac, seed=0):
    np.random.seed(seed)
    L6 = fits["L6"]
    src = trimesh.Trimesh(hs_v, hs_f, process=False).sample(8000)
    dst = psac.sample(40000)
    tr = cKDTree(dst)
    s, R, t, d = _icp(src, tr, dst, s0=L6["T"][0], R0=L6["T"][1], t0=L6["T"][2], iters=60, trim=0.8)
    dd = tr.query(s * src @ R.T + t)[0]
    return dict(T=(s, R, t), scale=round(float(s), 4), residual_median_mm=round(float(np.median(dd)), 2), residual_p90_mm=round(float(np.quantile(dd, .9)), 2),
                residual_rms_mm=round(float(np.sqrt((dd ** 2).mean())), 2), hra_centroid=np.asarray(hs_v).mean(0), page_centroid=psac.vertices.mean(0))


def decimated_closed(v, f, ntri):
    from scripts.anatomy.q234.hra_q234 import decimate
    V0, F0 = np.asarray(v, float), np.asarray(f)
    for k in (1.0, 1.05, .95, 1.1, .9, 1.2, .8):
        V, F = decimate(V0, F0, int(ntri * k))
        m = trimesh.Trimesh(V, F, process=True); trimesh.repair.fix_normals(m)
        cc = m.split(only_watertight=False)
        if len(cc) > 1:
            m = max(cc, key=lambda c: len(c.faces)); m.remove_unreferenced_vertices()
        if m.is_watertight:
            return np.asarray(m.vertices), np.asarray(m.faces), True
    return np.asarray(m.vertices), np.asarray(m.faces), False


def load_nucleus():
    pat = "|".join(f"^VH_F_nucleus_pulposus_of_intervertebral_disk_of_{s}$" for s, _, _ in DISCS)
    N = hra.load_nodes("united-female", pat)
    return {(u, l): N[f"VH_F_nucleus_pulposus_of_intervertebral_disk_of_{s}"] for s, u, l in DISCS}, {(u, l): f"VH_F_nucleus_pulposus_of_intervertebral_disk_of_{s}" for s, u, l in DISCS}


def load_cord():
    N = hra.load_nodes("united-female", "|".join(f"^{n}$" for _, n in CORD))
    return {lv: (N[n], n) for lv, n in CORD}


def canal_slices(pv, tangents, heights=(-4, -2, 0, 2, 4)):
    """{level: dict(c, t, poly, T3, h, area)}: the vertebral foramen of each page vertebra = the largest interior ring (hole) of the axial section (plane normal = the local spine axis) among the sections
    at `heights` mm from the vertebral centroid (the plane through the pedicles shows the ring closed; sections at the body level show body and arch as separate pieces). A vertebra with no ring borrows
    the polygon of the nearest vertebra that has one, shifted by the centroid difference (flag `borrowed`)."""
    from shapely.geometry import Polygon
    out = {}
    for lv, m in pv.items():
        c = m.vertices.mean(0); t = tangents[lv]
        best = None
        for h in heights:
            try:
                sec = m.section(plane_origin=c + t * h, plane_normal=t)
                if sec is None:
                    continue
                P2, T = sec.to_2D()
                for pg in P2.polygons_full:
                    for ring in pg.interiors:
                        a = Polygon(ring)
                        if 60 <= a.area <= 900 and (best is None or a.area > best["area"]):
                            best = dict(poly=a, T3=T, h=h, area=round(float(a.area), 1), borrowed=False)
            except Exception:
                continue
        out[lv] = dict(c=c, t=t, **(best or {}))
    have = [l for l in out if "poly" in out[l]]
    for lv in out:
        if "poly" in out[lv]:
            continue
        near = min(have, key=lambda l: np.linalg.norm(out[l]["c"] - out[lv]["c"]))
        o = out[near]
        shift = out[lv]["c"] - o["c"]
        from shapely import affinity
        # polygon coordinates are planar (x, y); the shift is applied in the borrowed plane's frame
        d = (np.linalg.inv(o["T3"])[:3, :3] @ shift)
        out[lv].update(poly=affinity.translate(o["poly"], xoff=float(d[0]), yoff=float(d[1])), T3=o["T3"], h=o["h"], area=o["area"], borrowed=True, borrowed_from=near)
    return out


def in_canal(P, canal, tol=0.5, reach=20.0):
    """P (n,3): each point is projected along the local spine axis onto the foramen plane of the nearest vertebra (by centroid distance) and tested against that vertebra's foramen polygon (+tol mm).
    -> (inside (n,), tested (n,)); a point farther than `reach` mm from that vertebra's centroid along the axis is not tested."""
    from shapely import contains_xy, prepare
    lv = list(canal)
    C = np.array([canal[l]["c"] for l in lv])
    near = np.linalg.norm(P[:, None, :] - C[None], axis=2).argmin(1)
    inside = np.zeros(len(P), bool); tested = np.zeros(len(P), bool)
    for k, l in enumerate(lv):
        m = near == k
        if not m.any():
            continue
        info = canal[l]
        h = (P[m] - info["c"]) @ info["t"]
        ok = np.abs(h) <= reach
        Q = np.c_[P[m], np.ones(m.sum())] @ np.linalg.inv(info["T3"]).T
        pg = info["poly"].buffer(tol); prepare(pg)
        inside[m] = contains_xy(pg, Q[:, 0], Q[:, 1]) & ok
        tested[m] = ok
    return inside, tested
