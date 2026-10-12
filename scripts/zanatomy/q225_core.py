"""Q225 core: page loading for the two Z-fitted pages (sources build/q221/viewer_zan_vhm, build/q222/viewer_zan_female), their unfitted bases, the persons' OWN bone meshes (evidence), and exact
(mesh-based, not voxel) bone-bone penetration / joint-space measures.  Everything works on the DECODED shipped geometry (q207_core.Page)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C7  # noqa: E402

PAGES = {
    "male": dict(src=REPO / "build/q221/viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted", out=REPO / "build/q225/fit_zan_vhm", final=REPO / "build/q225/viewer_zan_vhm",
                 base=REPO / "build/q222/viewer_zan_atlas", base_stem="atlas_viewer_zan_atlas", own="own_m", fit_key="z_male_fit", base_key="z_male", who="his"),
    "female": dict(src=REPO / "build/q222/viewer_zan_female", stem="atlas_viewer_zan_female", out=REPO / "build/q225/fit_zan_female", final=REPO / "build/q225/viewer_zan_female",
                   base=REPO / "build/q222/viewer_base_female", base_stem="atlas_viewer_base_female", own="own_f", fit_key="z_female_fit", base_key="z_base_f", who="her"),
}
BUILD = REPO / "build" / "q225"
C7.PAGES["male"]["src"], C7.PAGES["female"]["src"] = PAGES["male"]["src"], PAGES["female"]["src"]
ELBOW_L = ("humerus_l", "radius_l", "ulna_l")


def load(which, src=None, base=False):
    c = PAGES[which]
    if base:
        return C7.Page(which, src=c["base"], stem=c["base_stem"])
    return C7.Page(which, src=src or c["src"], stem=c["stem"])


def state_path(which, stage):
    BUILD.mkdir(parents=True, exist_ok=True)
    return BUILD / f"{which}_{stage}.pkl"


def own_bones(which):
    """the person's OWN bone meshes {id: (v, f)} (own CT / cryosection reconstruction pages, Q198 loader)"""
    import scripts.zanatomy.q223_paths  # noqa: F401
    from scripts.zanatomy.q198_load import load as L
    S = L(PAGES[which]["own"])
    return {s["id"]: (s["v"], s["f"]) for s in S if s["sys"] == "bone"}


_TM = {}


def tmesh(v, f):
    import trimesh
    return trimesh.Trimesh(np.asarray(v, float), np.asarray(f), process=False)


def depth_inside(v_pts, mesh_v, mesh_f):
    """signed depth (mm, > 0 = inside) of points v_pts in the closed mesh (exact: trimesh signed distance)"""
    import trimesh
    m = trimesh.Trimesh(np.asarray(mesh_v, float), np.asarray(mesh_f), process=False)
    from trimesh.proximity import signed_distance
    return signed_distance(m, np.asarray(v_pts, float))      # trimesh: positive inside


def pair_metrics(va, fa, vb, fb, nmax=4000):
    """exact penetration of the surfaces of a and b into each other + joint space: max depth of a's vertices in b and b's in a, share of vertices > 1 mm deep, min vertex-surface gap (when not interpenetrating)"""
    out = {}
    for nm, (x, y, fy) in (("a_in_b", (va, vb, fb)), ("b_in_a", (vb, va, fa))):
        sel = x
        if len(sel) > nmax:
            sel = sel[:: len(sel) // nmax + 1]
        d = depth_inside(sel, y, fy)
        out[nm] = dict(max_mm=round(float(max(d.max(), 0.0)), 2), pct_over_1mm=round(100 * float((d > 1).mean()), 1))
    gap = float(cKDTree(vb).query(va)[0].min())
    out["min_vertex_gap_mm"] = round(gap, 2)
    out["max_depth_mm"] = max(out["a_in_b"]["max_mm"], out["b_in_a"]["max_mm"])
    return out
