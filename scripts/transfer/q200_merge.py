"""Q200: the viewer shows a measured structure and its Z continuation as two entries; for the audits (and the tests) they are one structure:
the continuation's planar closure at the seam lies on the measured cap, so the measured cap faces it covers are dropped (interior), and the
rest (uncovered cap) stays a flat face the audit still reports."""
from __future__ import annotations
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from scripts.transfer.q200_continue import find_caps, AX


def merge_structure(mv, mf, pv, pf, covered, weld=False):
    """-> (v, f, info). covered: [{axis, pos, polys:[[[x,y],..],..]}] (from Q200_seams_<body>.json): the region of the cap plane the continuation
    starts on; the measured cap faces whose centroid lies in it are dropped (interior), the rest stay."""
    from shapely.geometry import Point
    keep = np.ones(len(mf), bool)
    info = dict(caps_joined=0, cap_faces_removed=0, cap_area_left=0.0)
    for cv in covered:
        k = AX[cv["axis"]]; kk = [i for i in range(3) if i != k]
        u = unary_union([Polygon(p).buffer(0.2) for p in cv["polys"] if len(p) >= 3])
        if u.is_empty:
            continue
        for cap in find_caps(mv, mf, minarea=20.0):
            if cap["axis"] != cv["axis"] or abs(cap["pos"] - cv["pos"]) > 1.5:
                continue
            info["caps_joined"] += 1
            for fi in cap["faces"]:
                if u.contains(Point(mv[mf[fi]][:, kk].mean(0))):
                    keep[fi] = False; info["cap_faces_removed"] += 1
    capleft = 0.0
    for cap in find_caps(mv, mf, minarea=20.0):
        rem = [fi for fi in cap["faces"] if keep[fi]]
        if rem:
            t = mv[mf[rem]]
            capleft += float(0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum())
    info["cap_area_left"] = capleft
    v = np.vstack([mv, pv])
    f = np.vstack([mf[keep], pf + len(mv)])
    if weld:
        # the continuation's ring 0 is the measured cap outline itself (same vertex positions): weld coincident vertices (audit only)
        key = np.round(v / 0.02).astype(np.int64)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        v, f = v[first], inv.reshape(-1)[f]
        f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    return v, f, info
