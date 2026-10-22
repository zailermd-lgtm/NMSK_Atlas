"""Q198 joint finder: per model, per side, junction centre / axis / bone sets from the bone meshes (contact patch of the two bone sets)."""
from __future__ import annotations
import re
import numpy as np
from scipy.spatial import cKDTree
from scripts.zanatomy.q198_core import pca, surf_points

CARPAL_RE = re.compile(r"(scaphoid|lunate|triquetrum|pisiform|trapez|capitate|hamate|carpals)")
TARSAL = ("talus", "calcaneus")


def _cat(bs):
    return np.concatenate([b["v"] for b in bs]) if bs else None


def bones_of(S):
    """dict name -> list of bone structs (by canonical key)"""
    B = {}
    for s in S:
        if s["sys"] != "bone":
            continue
        i = s["id"]; side = s["side"]
        key = None
        for nm in ("humerus", "radius", "ulna", "scapula", "clavicle", "femur", "tibia", "fibula", "patella", "hip_bone", "talus", "calcaneus"):
            if i == f"{nm}_{side}" or i == f"{nm}_{'l' if side=='l' else 'r'}":
                key = (nm, side)
        if key is None and CARPAL_RE.search(i) and not re.search(r"metacarp", i):
            key = ("carpals", side)
        if key is None and ("metacarp" in i) and side in ("l", "r"):
            key = ("metacarpals", side)
        if key is None and re.search(r"cranium|occipital|frontal|parietal|temporal|sphenoid", i):
            key = ("skull", "m")
        if key is None and (i in ("sternum",)):
            key = ("sternum", "m")
        if key:
            B.setdefault(key, []).append(s)
    # spine: vertebrae sorted by mean y
    vert = []
    for s in S:
        if s["sys"] == "bone" and re.search(r"vertebra|atlas_c1|axis_c2", s["id"]):
            vert.append(s)
    return B, vert


def spine_levels(vert):
    """own: cervical_vertebrae x7 / thoracic x12 / lumbar x5 (same id repeated); Z: zan_vertebra_c3.. + atlas/axis. -> dict 'C1'..'L5' -> struct"""
    out = {}
    own = [s for s in vert if s["id"].split("#")[0] in ("cervical_vertebrae", "thoracic_vertebrae", "lumbar_vertebrae")]
    if own:
        for grp, pre, n in (("cervical_vertebrae", "C", 7), ("thoracic_vertebrae", "T", 12), ("lumbar_vertebrae", "L", 5)):
            g = sorted([s for s in own if s["id"].split("#")[0] == grp], key=lambda s: -s["v"][:, 1].mean())
            for k, s in enumerate(g):
                out[f"{pre}{k+1}"] = s
        return out
    for s in vert:
        m = re.search(r"vertebra_([ctl])(\d+)", s["id"])
        if m:
            out[f"{m.group(1).upper()}{int(m.group(2))}"] = s
        elif "atlas_c1" in s["id"]:
            out["C1"] = s
        elif "axis_c2" in s["id"]:
            out["C2"] = s
    return out


def contact_center(A, B, band=10.0):
    """centre of the articulation of point sets A (proximal) and B (distal): mean of the A and B points within `band` mm of the closest approach"""
    ta, tb = cKDTree(A), cKDTree(B)
    da, _ = tb.query(A); db, _ = ta.query(B)
    dmin = float(min(da.min(), db.min()))
    pa = A[da < dmin + band]; pb = B[db < dmin + band]
    c = 0.5 * (pa.mean(0) + pb.mean(0))
    return c, dmin, len(pa), len(pb)


def find_joints(S):
    B, vert = bones_of(S)
    lev = spine_levels(vert)
    J = []
    MISS = []
    B['_missing'] = MISS

    def add(name, side, prox, dist, R, extra=None):
        if not prox or not dist:
            MISS.append({"name": name, "side": side, "proximal_bones_present": bool(prox), "distal_bones_present": bool(dist)})
            return
        A, D = _cat(prox), _cat(dist)
        c, dmin, na, nb = contact_center(A, D)
        ca, cd = A.mean(0), D.mean(0)
        ax = cd - ca; ax /= np.linalg.norm(ax)
        J.append(dict(name=name, side=side, centre=c, axis=ax, R=R, prox=[b["id"] for b in prox], dist=[b["id"] for b in dist], contact_min_mm=dmin,
                      prox_com=ca, dist_com=cd, **(extra or {})))

    for sd in ("l", "r"):
        g = lambda n: B.get((n, sd))
        add("shoulder", sd, g("scapula"), g("humerus"), 90)
        add("elbow", sd, g("humerus"), (g("radius") or []) + (g("ulna") or []), 85)
        add("wrist", sd, (g("radius") or []) + (g("ulna") or []), g("carpals"), 55)
        add("hip", sd, g("hip_bone"), g("femur"), 100)
        add("knee", sd, g("femur"), (g("tibia") or []) + (g("patella") or []), 85)
        add("ankle", sd, (g("tibia") or []) + (g("fibula") or []), (g("talus") or []), 60)
    add("cervico_thoracic", "m", [lev["C7"]] if "C7" in lev else None, [lev["T1"]] if "T1" in lev else None, 70)
    add("thoraco_lumbar", "m", [lev["T12"]] if "T12" in lev else None, [lev["L1"]] if "L1" in lev else None, 70)
    add("head_neck", "m", B.get(("skull", "m")), [lev["C1"]] if "C1" in lev else None, 60)
    return J, B, lev
