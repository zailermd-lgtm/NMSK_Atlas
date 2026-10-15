#!/usr/bin/env python3
"""Q250: pelvis / skeleton surfaces of adult WOMEN from the TotalSegmentator CT dataset v2.0.1 (Wasserthal et al., Radiology: AI 2023, Zenodo 10047292, CC BY 4.0).
Only the segmentation masks of the skeleton are read (HTTP range requests into the 23.6 GB zip, see scripts/anatomy/q250/ts_fetch.py); no CT image is used or stored.
    python3 scripts/anatomy/q250/ts_pelvis.py meshes  CASE_DIR OUT_DIR      # masks -> surfaces (atlas frame mm, +X right +Y sup +Z ant), QC (complete, not cut by the field of view)
    python3 scripts/anatomy/q250/ts_pelvis.py measure OUT_DIR OUT.json      # the Q233 dimorphism measures on every case
Atlas frame from the NIfTI affine: canonical RAS (x right, y anterior, z superior) -> (X, Y, Z) = (x, z, y)."""
from __future__ import annotations
import json, sys, os
from pathlib import Path
import numpy as np, trimesh, nibabel as nib
from scipy import ndimage as ndi
from skimage import measure as skm

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))

LABELS = {"hip_bone_l": "hip_left", "hip_bone_r": "hip_right", "sacrum": "sacrum", "femur_l": "femur_left", "femur_r": "femur_right"}


def load_mask(path):
    im = nib.as_closest_canonical(nib.load(str(path)))
    a = np.asarray(im.dataobj) > 0
    return a, im.affine, a.shape


def mask_surface(path, smooth=2, target_faces=12000):
    a, aff, shp = load_mask(path)
    if a.sum() < 2000:
        return None
    idx = np.argwhere(a)
    touches = bool((idx.min(0) == 0).any() or (idx.max(0) == np.array(shp) - 1).any())
    lo = np.maximum(idx.min(0) - 2, 0); hi = np.minimum(idx.max(0) + 3, shp)
    sub = a[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    sub = ndi.binary_closing(sub, iterations=1)
    sub = ndi.binary_fill_holes(sub)
    lab, n = ndi.label(sub)
    if n > 1:
        sz = ndi.sum(sub, lab, range(1, n + 1)); sub = lab == (1 + int(np.argmax(sz)))
    vol = float(sub.sum() * abs(np.linalg.det(aff[:3, :3])))
    g = ndi.gaussian_filter(sub.astype(np.float32), 0.8)
    v, f, _, _ = skm.marching_cubes(g, 0.5)
    v = v + lo
    w = aff[:3, :3] @ v.T + aff[:3, 3:4]
    w = w.T                                      # canonical RAS mm
    V = np.stack([w[:, 0], w[:, 2], w[:, 1]], 1)  # atlas frame (X right, Y sup, Z ant)
    if np.linalg.det(np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])) < 0:
        f = f[:, ::-1]
    m = trimesh.Trimesh(V, f, process=True)
    trimesh.smoothing.filter_taubin(m, iterations=10)
    if len(m.faces) > target_faces:
        m = m.simplify_quadric_decimation(face_count=target_faces)
    return dict(v=np.asarray(m.vertices), f=np.asarray(m.faces), volume_mm3=vol, touches_fov=touches, voxel_mm=[round(float(x), 2) for x in np.sqrt((aff[:3, :3] ** 2).sum(0))])


def cmd_meshes(case_dir, out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    qc = {}
    for c in sorted(Path(case_dir).iterdir()):
        if not (c / ".done").exists():
            continue
        res, ok = {}, True
        for k, lab in LABELS.items():
            p = c / f"{lab}.nii.gz"
            if not p.exists():
                ok = False; break
            r = mask_surface(p)
            if r is None:
                ok = False; break
            res[k] = r
        if not ok:
            qc[c.name] = dict(ok=False, why="label missing or empty"); continue
        pel = [res[k] for k in ("hip_bone_l", "hip_bone_r", "sacrum")]
        cut = any(r["touches_fov"] for r in pel)
        vols = {k: round(r["volume_mm3"] / 1000, 1) for k, r in res.items()}
        qc[c.name] = dict(ok=not cut, why="pelvis touches the field-of-view border" if cut else "", volumes_cm3=vols, voxel_mm=res["sacrum"]["voxel_mm"],
                          femur_cut=[res["femur_l"]["touches_fov"], res["femur_r"]["touches_fov"]])
        if not cut:
            np.savez_compressed(out_dir / f"{c.name}.npz", **{f"{k}_v": r["v"] for k, r in res.items()}, **{f"{k}_f": r["f"] for k, r in res.items()})
        print(c.name, qc[c.name]["ok"], vols, flush=True)
    (out_dir / "qc.json").write_text(json.dumps(qc, indent=1))


def cmd_measure(out_dir, out_json):
    from scripts.anatomy.q250.measure import measure
    out = {}
    for p in sorted(Path(out_dir).glob("s*.npz")):
        z = np.load(p)
        S = [dict(id=k, sys="bone", v=z[f"{k}_v"], f=z[f"{k}_f"], name=k, side=None, src="ts", rec=None) for k in LABELS]
        try:
            m = measure(S)
            out[p.stem] = m
        except Exception as e:  # noqa: BLE001
            out[p.stem] = dict(error=str(e))
        print(p.stem, out[p.stem].get("subpubic_angle_deg"), flush=True)
    Path(out_json).write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    if sys.argv[1] == "meshes":
        cmd_meshes(sys.argv[2], sys.argv[3])
    else:
        cmd_measure(sys.argv[2], sys.argv[3])
