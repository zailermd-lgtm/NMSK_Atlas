#!/usr/bin/env python3
"""Q250: a FEMALE CHEST ENVELOPE for the Base page. Z-Anatomy's chest skin is the male contour (flat), so the Q234 breast fit (HRA sculpted mammary glands) found room for only 5 % of the breast volume and held
the breasts. Here the skin over each breast footprint is raised anteriorly (smooth bump, tapering to nothing 30 mm outside the footprint) until it lies 3 mm in front of the UNCOMPRESSED HRA breast
(HRA thoracic vertebrae registered onto this page's thoracic vertebrae, the Q234 registration), so the breast model fits its skin. Nothing else is moved (muscles, ribs, fascia keep their place); the skin
pieces change only in the bump region. The breast SHAPE is the HRA reference model (sculpted from textbook atlases, not scanned): the bump copies its projection, it is NOT a measured soft-tissue contour.
    python3 scripts/zanatomy/q250_chest_skin.py [--src build/q250_pre/viewer_base_zonly] [--out build/q250_pre/viewer_base_zonly_chest]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np, trimesh
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.anatomy.q234 import place as PL, hra_q234 as Q  # noqa: E402

STEM = "atlas_viewer_base_female"
GAP_MM = 3.0         # skin thickness in front of the breast surface (Q234 uses a 2.5 mm skin margin)
TAPER_MM = 30.0
EDGE_MM = 3.0        # smoothing radius of the lift's zero-crossing (Q251: was a hard max(dz, 0), visible as a crease)


def run(src, out):
    np.random.seed(0)
    src, out = Path(src), Path(out)
    man, blob = P5.load_page(REPO / src, STEM); S = P5.decode(man, blob)
    M, anchor, info = Q.load()
    vert = np.vstack([trimesh.Trimesh(e["v"], e["f"], process=False).sample(30000) for i, e in S.items() if i.startswith("zan_vertebra_t") and len(e["f"])])
    T, reg = PL.thorax_register(anchor, vert)
    skin_ids = [i for i, e in S.items() if e["m"]["sys"] == "skin" and len(e["f"])]
    rep = dict(thorax_registration=reg, sides={})
    new = {i: S[i]["v"].copy() for i in skin_ids}
    P = 1.0
    for side in ("l", "r"):
        ids = [s for s in M if info[s]["region"] == "breast" and s.endswith("_" + side) and s.startswith(("breast_fat", "areola", "nipple"))]
        X = np.vstack([PL.H.apply(T, M[k][0]) for k in ids])
        lo = X.min(0) - TAPER_MM - 5; hi = X.max(0) + TAPER_MM + 5
        nx, ny = (np.ceil((hi[:2] - lo[:2]) / P).astype(int))
        zt = np.full((nx, ny), -np.inf)
        ix = np.floor((X[:, 0] - lo[0]) / P).astype(int); iy = np.floor((X[:, 1] - lo[1]) / P).astype(int)
        # dense: sample the surfaces so every column of the footprint has points
        for k in ids:
            m = trimesh.Trimesh(PL.H.apply(T, M[k][0]), M[k][1], process=False)
            pts = m.sample(int(m.area * 3) + 500)
            jx = np.floor((pts[:, 0] - lo[0]) / P).astype(int); jy = np.floor((pts[:, 1] - lo[1]) / P).astype(int)
            np.maximum.at(zt, (jx, jy), pts[:, 2])
        foot = np.isfinite(zt)
        foot = ndi.binary_closing(foot, iterations=3); foot = ndi.binary_fill_holes(foot)
        # fill missing columns of the footprint from the nearest known column
        zfill = zt.copy(); zfill[~np.isfinite(zfill)] = np.nan
        idx = ndi.distance_transform_edt(~np.isfinite(zt), return_distances=False, return_indices=True)
        zfull = zt[tuple(idx)]; zfull[~foot] = np.nan
        dist = ndi.distance_transform_edt(~foot) * P
        w = np.clip(1 - dist / TAPER_MM, 0, 1); w = w * w * (3 - 2 * w)
        moved, maxlift = 0, 0.0
        for i in skin_ids:
            V = S[i]["v"]
            jx = np.clip(np.floor((V[:, 0] - lo[0]) / P).astype(int), 0, nx - 1); jy = np.clip(np.floor((V[:, 1] - lo[1]) / P).astype(int), 0, ny - 1)
            inside = (V[:, 0] >= lo[0]) & (V[:, 0] < hi[0]) & (V[:, 1] >= lo[1]) & (V[:, 1] < hi[1])
            if not inside.any():
                continue
            zref = np.where(foot[jx, jy], zfull[jx, jy], np.nan)
            # nearest footprint column's top for the taper zone
            ztop = zfull[tuple(idx[:, jx, jy])]
            tgt = ztop + GAP_MM
            # smooth max(dz, 0) (dz = tgt - V[:,2]) instead of a hard clamp: the hard clamp is C0 but not C1 at dz = 0
            # -- exactly the visible skin surface where the bump begins -- so the lift's SLOPE jumps there, reading
            # as a crease / hard edge at the taper boundary; EDGE_MM softens that corner (small next to the ~30 mm
            # lateral taper and the >= 60 mm breast dimensions, so the envelope's volume / shape intent is unchanged)
            # while still matching max(dz, 0) exactly away from the crossing.
            dz = tgt - V[:, 2]
            smooth_lift = 0.5 * (dz + np.sqrt(dz ** 2 + EDGE_MM ** 2))
            lift = np.where(inside & np.isfinite(tgt) & (V[:, 2] > tgt - 60) & (V[:, 2] < tgt + 40), smooth_lift * w[jx, jy], 0.0)
            if (lift > 0.05).any():
                nv = new[i].copy(); nv[:, 2] += lift; new[i] = nv
                moved += int((lift > 0.05).sum()); maxlift = max(maxlift, float(lift.max()))
        rep["sides"][side] = dict(footprint_cm2=round(float(foot.sum()) * P * P / 100, 1), vertices_lifted=moved, max_lift_mm=round(maxlift, 1), breast_top_mm_max=round(float(np.nanmax(zfull)), 1))
        print(side, rep["sides"][side], flush=True)
    repl = {}
    for i in skin_ids:
        d = np.linalg.norm(new[i] - S[i]["v"], axis=1)
        if d.max() < 0.05:
            continue
        rec = dict(S[i]["m"].get("rec") or {"name": S[i]["m"]["name"]})
        rec["procedural_badge"] = ((rec.get("procedural_badge") + " || ") if rec.get("procedural_badge") else "") + (
            f"Q250 female chest envelope: this skin piece was raised anteriorly over the footprint of the HRA breast model (max {d.max():.1f} mm, {int((d > 0.05).sum())} vertices; tapering to nothing 30 mm outside the footprint) so that the "
            "breast model (HuBMAP HRA mammary gland, sculpted from textbook atlases, not scanned) fits under the skin; the contour copies the model's projection, it is not a measured soft-tissue contour.")
        repl[i] = (new[i], S[i]["f"], rec)
    m2 = dict(man); m2["attribution"] = (man.get("attribution") or "").rstrip() + " Q250: the skin over the breast footprints was raised to give the HRA breast models room (female chest envelope, see the skin cards)."
    P5.save_page(REPO / out, STEM, m2, blob, replace=repl)
    rep["skin_pieces_changed"] = sorted(repl)
    (REPO / "data/derived/Q250_chest_skin_report.json").write_text(json.dumps(rep, indent=1) + "\n")
    print("skin pieces changed", len(repl))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--src", default="build/q250_pre/viewer_base_zonly"); ap.add_argument("--out", default="build/q250_pre/viewer_base_zonly_chest")
    a = ap.parse_args(); run(a.src, a.out)
