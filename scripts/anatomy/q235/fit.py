"""Q235: registration of the CVH pelvic set onto a page (evidence = dict of meshes of the page in the atlas frame), residuals per bone landmark region and per cross-check structure."""
from __future__ import annotations
import numpy as np, trimesh
from scipy.spatial import cKDTree
from scripts.anatomy.q235 import cvh, register as R


def largest(V, F):
    m = trimesh.Trimesh(V, F, process=False)
    cc = m.split(only_watertight=False)
    c = max(cc, key=lambda c: len(c.faces))
    return np.asarray(c.vertices), np.asarray(c.faces)


def sample(V, F, n, seed=0):
    np.random.seed(seed)
    return trimesh.Trimesh(V, F, process=False).sample(n)


def page_bone_points(ev, n=(30000, 30000, 20000, 8000)):
    """ev[key] = (V, F) of hip_bone_l/r, sacrum, optional sacrum_fill, coccyx -> (n,3) surface samples"""
    pts = []
    for key, k in (("hip_bone_l", n[0]), ("hip_bone_r", n[1]), ("sacrum", n[2]), ("sacrum_fill", n[3]), ("coccyx", n[3])):
        if key in ev:
            V, F = largest(*ev[key])
            pts.append(sample(V, F, k))
    return np.vstack(pts)


def cvh_bones(sx, n=6000):
    out = []
    for i in (44, 45):
        V, F = cvh.load_raw(i)
        W, G = cvh.to_atlas(V, sx, F)
        out.append(sample(W, G, n))
    return np.vstack(out)


def fit_bones(ev, sx, starts=((30, 0), (0, 0), (-30, 0)), iters=60):
    dst = page_bone_points(ev)
    src = cvh_bones(sx)
    best = None
    for pitch, yaw in starts:
        R0 = R.rot(pitch, yaw)
        t0 = dst[dst[:, 1] < dst[:, 1].min() + 80].mean(0) - R0 @ src.mean(0)
        T, dd = R.sym_icp(src, dst, (1.0, R0, t0), iters=iters)
        score = np.median(dd)
        if best is None or score < best[0]:
            best = (score, T, (pitch, yaw))
    return best[1], dict(start=best[2], dst=dst, src=src)


def regional_residuals(T, ev, sx, dst):
    """bone residual (CVH bone point -> page bone surface, mm) by landmark region of the CVH meshes (file frame): symphysis (|x-184|<8 mm), pubic rami / arch, ischial tuberosities (lowest 25 mm), acetabular region, sacrum (mesh 45
    above the coccyx), coccyx (the lowest 15 mm of mesh 45)."""
    tree = cKDTree(dst)
    out = {}
    V44, F44 = cvh.load_raw(44)
    V45, F45 = cvh.load_raw(45)
    P44 = R.apply(T, cvh.to_atlas(sample(V44, F44, 20000) if False else V44, sx))
    # use mesh vertices (dense enough) for the regions
    d44 = tree.query(P44)[0]
    x = V44[:, 0] - cvh.MID
    z = V44[:, 2]
    reg = {
        "pubic symphysis region (|x-184|<8)": np.abs(x) < 8,
        "ischial tuberosity region (lowest 25 mm of the hip bones)": z > z.max() - 25,
        "ischiopubic rami / pubic arch (z 120-150 mm, 8 < |x| < 45)": (np.abs(x) >= 8) & (np.abs(x) < 45) & (z < z.max() - 25),
        "acetabulum / upper hip bone (upper half of the mesh)": z < np.median(z),
    }
    for k, m in reg.items():
        if m.sum() > 20:
            out[k] = dict(n=int(m.sum()), median=round(float(np.median(d44[m])), 2), p90=round(float(np.quantile(d44[m], .9)), 2))
    P45 = R.apply(T, cvh.to_atlas(V45, sx))
    d45 = tree.query(P45)[0]
    z5 = V45[:, 2]
    for k, m in {"sacrum+coccyx (closed mesh), all": np.ones(len(V45), bool), "coccyx (lowest 15 mm of the closed mesh)": z5 > z5.max() - 15}.items():
        out[k] = dict(n=int(m.sum()), median=round(float(np.median(d45[m])), 2), p90=round(float(np.quantile(d45[m], .9)), 2))
    out["all CVH bone vertices"] = dict(n=int(len(P44) + len(P45)), median=round(float(np.median(np.r_[d44, d45])), 2), p90=round(float(np.quantile(np.r_[d44, d45], .9)), 2))
    return out


def nn_both(Pa, Pb):
    """symmetric nearest-neighbour distances between two point sets -> (median, p90) of the union of both directions"""
    d1 = cKDTree(Pb).query(Pa)[0]; d2 = cKDTree(Pa).query(Pb)[0]
    d = np.r_[d1, d2]
    return round(float(np.median(d)), 2), round(float(np.quantile(d, .9)), 2)
