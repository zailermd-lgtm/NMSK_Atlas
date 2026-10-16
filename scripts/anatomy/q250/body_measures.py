"""Q250: whole-body proportions measured on the meshes of a page (list of Q233-loader structures {id, sys, v, f}): stature, head height / stature, thorax width, clavicle length, biacromial /
bi-iliac, femur length / stature, waist-to-hip ratio of the skin (torso skin slices).  Landmark rules are simple geometric extremes (documented in each function), comparable across pages only."""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree

TORSO_KEYS = ("epigastric", "hypochondriac", "hypogastric", "lateral_region_of_abdomen", "lateral_region_of_thorax", "umbilical", "lumbar", "sacral", "gluteal_region", "hip_region", "inguinal",
              "mammary", "pectoral", "presternal", "inframammary", "infrascapular", "interscapular", "scapular", "vertebral", "perineal", "anal", "gluteal_fold", "posterior_region_of_thigh", "anterior_region_of_thigh")


def _bone(S, base):
    for x in S:
        if x["id"].split("#")[0] == base and x["sys"] == "bone" and len(x["v"]):
            return np.asarray(x["v"])
    return None


def slice_perimeter(P, y0, half=4.0, nb=90):
    """perimeter (mm) of the outer boundary of the points with |y - y0| < half: polar max radius per angle bin around the centroid (convex-ish, fine for a torso slice)"""
    q = P[np.abs(P[:, 1] - y0) < half][:, [0, 2]]
    if len(q) < 30:
        return None
    c = q.mean(0); d = q - c
    ang = np.arctan2(d[:, 1], d[:, 0]); r = np.hypot(d[:, 0], d[:, 1])
    bins = np.linspace(-np.pi, np.pi, nb + 1); idx = np.clip(np.digitize(ang, bins) - 1, 0, nb - 1)
    rr = np.array([r[idx == i].max() if (idx == i).any() else np.nan for i in range(nb)])
    if np.isnan(rr).any():
        rr = np.where(np.isnan(rr), np.nanmean(rr), rr)
    th = 0.5 * (bins[:-1] + bins[1:])
    pts = np.c_[rr * np.cos(th), rr * np.sin(th)]
    return float(np.linalg.norm(np.roll(pts, -1, 0) - pts, axis=1).sum())


def measure_body(S):
    out = {}
    skin = np.vstack([np.asarray(x["v"]) for x in S if x["sys"] == "skin" and len(x["v"])] or [np.zeros((1, 3))])
    stature = float(skin[:, 1].max() - skin[:, 1].min())
    if stature < 100:                                    # no skin mesh on this page object list: stature from the skeleton extent instead
        allb = np.vstack([np.asarray(x["v"]) for x in S if x["sys"] == "bone" and len(x["v"])]); stature = float(allb[:, 1].max() - allb[:, 1].min()) + 60.0
        out["stature_note"] = "skeleton extent + 60 mm (no skin structure found)"
    out["stature_mm"] = round(stature, 0)
    skull = [b for b in (_bone(S, k) for k in ("frontal", "occipital", "parietal_l", "parietal_r", "mandible")) if b is not None]
    if skull:
        sv = np.vstack(skull); out["head_height_mm"] = round(float(sv[:, 1].max() - sv[:, 1].min()), 0); out["head_height_over_stature_pct"] = round(100 * out["head_height_mm"] / stature, 2)
    rib = [np.asarray(x["v"]) for x in S if x["sys"] == "bone" and ("_rib_" in x["id"] or x["id"].endswith("_rib_l") or x["id"].endswith("_rib_r"))]
    if rib:
        rv = np.vstack(rib); out["thorax_width_mm"] = round(float(np.ptp(rv[:, 0])), 0); out["thorax_depth_mm"] = round(float(np.ptp(rv[:, 2])), 0)
    for sd in "lr":
        c = _bone(S, f"clavicle_{sd}")
        if c is not None:
            ax = np.linalg.svd(c - c.mean(0), full_matrices=False)[2][0]; out[f"clavicle_length_{sd}_mm"] = round(float(np.ptp((c - c.mean(0)) @ ax)), 1)
        f = _bone(S, f"femur_{sd}")
        if f is not None:
            ax = np.linalg.svd(f - f.mean(0), full_matrices=False)[2][0]; out[f"femur_length_{sd}_mm"] = round(float(np.ptp((f - f.mean(0)) @ ax)), 1)
    if "femur_length_r_mm" in out:
        out["femur_length_over_stature_pct"] = round(100 * out["femur_length_r_mm"] / stature, 2)
    # torso skin breadths (own pages have one skin mesh: not measured): width (x extent) of the torso skin pieces in 8 mm slices relative to the top of the hip bones (iliac crest):
    # waist = narrowest slice from the crest to 160 mm above it, hip = widest slice from 140 to 20 mm below it
    TORSO = ("epigastric", "hypochondriac", "hypogastric", "lateral_region_of_abdomen", "umbilical", "lumbar", "lateral_region_of_thorax", "mammary", "pectoral", "sacral", "gluteal_region", "hip_region")
    st_ = [np.asarray(x["v"]) for x in S if x["sys"] == "skin" and x["id"] != "skin" and any(k in x["id"] for k in TORSO)]
    hips = [h for h in (_bone(S, "hip_bone_l"), _bone(S, "hip_bone_r")) if h is not None]
    if st_ and hips:
        T = np.vstack(st_); crest = max(h[:, 1].max() for h in hips)
        def width(y0, half=8.0):
            q = T[np.abs(T[:, 1] - y0) < half]
            return float(np.ptp(q[:, 0])) if len(q) > 20 else None
        ww = [w for w in (width(crest + dy) for dy in range(0, 161, 20)) if w]; hw = [w for w in (width(crest - dy) for dy in range(20, 141, 20)) if w]
        if ww and hw:
            out["waist_skin_breadth_mm"] = round(min(ww), 0); out["hip_skin_breadth_mm"] = round(max(hw), 0); out["waist_to_hip_breadth_ratio"] = round(min(ww) / max(hw), 3)
    return out
