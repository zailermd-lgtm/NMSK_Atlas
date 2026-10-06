"""Q190 objective distortion measures of a fitted Z-Anatomy mesh against its own Z-Anatomy source mesh (and her CT label)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import body_ctx as _ctx
BODY_SCALE = _ctx.BODY_SCALE   # Q168 body scale; source edge lengths are multiplied by it so a perfectly carried mesh reads 1.0


def load_dump(path):
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    out = []
    for i, m in enumerate(meta):
        out.append({**m, "v": z[f"v{i}"].astype(np.float64), "r": z[f"r{i}"].astype(np.float64), "f": z[f"f{i}"].astype(np.int64)})
    return out


def _edges(f):
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e.sort(1)
    return np.unique(e, axis=0)


def tri_area(v, f):
    return 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)


def stretch_stats(v, r, f):
    """edge-length and triangle-area ratio of the fitted mesh vs the Z source (x BODY_SCALE); flipped-face fraction vs source normals.
    Faces with a degenerate source triangle are skipped."""
    if len(f) == 0:
        return None
    e = _edges(f)
    ls = np.linalg.norm(r[e[:, 0]] - r[e[:, 1]], axis=1) * BODY_SCALE
    ln = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    ok = ls > 1e-3
    er = ln[ok] / ls[ok]
    em0 = float(np.median(er))
    er_abs = er
    er = er / em0                                  # relative to the structure's own median: a uniform scale is not a distortion
    a_s = tri_area(r, f) * BODY_SCALE ** 2
    a_n = tri_area(v, f)
    okf = a_s > 1e-4
    ar = a_n[okf] / a_s[okf]
    am0 = float(np.median(ar))
    ar = ar / am0
    ns = np.cross(r[f[:, 1]] - r[f[:, 0]], r[f[:, 2]] - r[f[:, 0]])
    nn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    flip = float(((ns * nn).sum(1) < 0)[okf].mean())
    return {"scale_edge_med": em0, "scale_area_med": am0, "edge_p95": float(np.percentile(er, 95)), "edge_p05": float(np.percentile(er, 5)), "edge_max_p99": float(np.percentile(er, 99)),
            "edge_frac_gt1.5": float((er > 1.5).mean()), "edge_frac_lt0.67": float((er < 0.67).mean()),
            "area_p95": float(np.percentile(ar, 95)),
            "area_frac_gt1.5": float((ar > 1.5).mean()), "area_frac_lt0.67": float((ar < 0.67).mean()),
            "flipped": flip, "n_faces": int(len(f))}


def distortion_score(s):
    """one number per structure: share of faces with an area stretch outside [0.67, 1.5] plus flipped faces (both in %-of-faces)"""
    if s is None:
        return 0.0
    return 100.0 * (s["area_frac_gt1.5"] + s["area_frac_lt0.67"] + s["flipped"])


def surf_samples(v, f, n=8000, rng=None):
    rng = rng or np.random.default_rng(0)
    a = tri_area(v, f)
    if a.sum() <= 0:
        return v.copy()
    idx = rng.choice(len(f), n, p=a / a.sum())
    u = rng.random((n, 2)); m = u.sum(1) > 1; u[m] = 1 - u[m]
    t = v[f[idx]]
    return t[:, 0] + u[:, :1] * (t[:, 1] - t[:, 0]) + u[:, 1:] * (t[:, 2] - t[:, 0])


def two_way(vA, fA, vB, fB, n=6000):
    """median distance A->B and B->A (surface samples), mm"""
    pa, pb = surf_samples(vA, fA, n), surf_samples(vB, fB, n)
    return float(np.median(cKDTree(pb).query(pa)[0])), float(np.median(cKDTree(pa).query(pb)[0]))
