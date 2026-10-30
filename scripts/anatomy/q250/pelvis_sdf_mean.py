#!/usr/bin/env python3
"""Q250: MEAN FEMALE PELVIS (hip bones, sacrum) of n adult women from CT (TotalSegmentator v2.0.1 masks, CC BY 4.0), by generalised Procrustes (similarity, size removed) + signed-distance averaging of the aligned masks
(no point correspondences needed). The mean surface is a blurred "average shape" (detail finer than the between-woman variation is averaged out); it is used only as a TARGET for the Z-Anatomy pelvic bones
(pelvis_reg.py), which keep their own anatomy.
    python3 scripts/anatomy/q250/pelvis_sdf_mean.py build CASES_DIR MESH_DIR OUT.npz      (CASES_DIR: <case>/<label>.nii.gz masks; MESH_DIR: ts_pelvis.py meshes output with qc.json)
OUT.npz: hip_bone_l / hip_bone_r / sacrum vertices + faces of the mean (atlas frame, arbitrary pose, mean size of the cases), scale / similarity of every case, case ids."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, trimesh, nibabel as nib
from scipy import ndimage as ndi
from skimage import measure as skm
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q250 import lib as L  # noqa: E402

BONES = {"hip_bone_l": "hip_left", "hip_bone_r": "hip_right", "sacrum": "sacrum"}
STEP = 1.5


def load_mask(path):
    im = nib.as_closest_canonical(nib.load(str(path)))
    a = (np.asarray(im.dataobj) > 0).astype(np.float32)
    return a, im.affine


def case_sdf(case_dir, sim, grid_pts, shape):
    """signed distance (mm, negative inside) of each bone mask resampled on the reference grid through the case -> reference similarity (s, R, t)"""
    s, R, t = sim
    xc = (grid_pts - t) @ R / s                       # case atlas coordinates (row-vector form of R^T (x - t) / s)
    w = np.stack([xc[:, 0], xc[:, 2], xc[:, 1]], 1)  # atlas (X, Y, Z) -> canonical RAS world (x, y, z) = (X, Z, Y)
    out = {}
    for k, lab in BONES.items():
        a, aff = load_mask(Path(case_dir) / f"{lab}.nii.gz")
        idx = (np.linalg.inv(aff[:3, :3]) @ (w - aff[:3, 3]).T)
        m = ndi.map_coordinates(a, idx, order=1, mode="constant", cval=0.0).reshape(shape) > 0.5
        m = ndi.binary_fill_holes(m)
        out[k] = ((ndi.distance_transform_edt(~m) - ndi.distance_transform_edt(m)) * STEP).astype(np.float32)
    return out


def mean_meshes(acc, n, lo):
    res = {}
    for k in BONES:
        m = ndi.gaussian_filter(acc[k] / n, 0.8)
        v, f, _, _ = skm.marching_cubes(m, 0.0)
        mesh = trimesh.Trimesh(v * STEP + lo, f, process=True)
        cc = mesh.split(only_watertight=False)
        mesh = max(cc, key=lambda c: len(c.vertices))
        trimesh.smoothing.filter_taubin(mesh, iterations=8)
        if len(mesh.faces) > 20000:
            mesh = mesh.simplify_quadric_decimation(face_count=20000)
        res[k] = (np.asarray(mesh.vertices), np.asarray(mesh.faces))
    return res


def build(cases_dir, mesh_dir, out):
    qc = json.loads((Path(mesh_dir) / "qc.json").read_text())
    cases = sorted(c for c, v in qc.items() if v["ok"])
    clouds = {}
    for c in cases:
        z = np.load(Path(mesh_dir) / f"{c}.npz")
        clouds[c] = np.vstack([L.sample(z[f"{k}_v"], z[f"{k}_f"], 9000)[0] for k in BONES])
    ref_cloud = clouds[cases[0]]
    sims = {c: (1.0, np.eye(3), np.zeros(3)) for c in cases}
    for it in range(2):
        for c in cases:
            if it == 0 and c == cases[0]:
                continue
            s, R, t, d = L.icp_sim(clouds[c], ref_cloud, iters=70, trim=0.9)
            sims[c] = (s, R, t)
        al = np.vstack([sims[c][0] * clouds[c][::6] @ sims[c][1].T + sims[c][2] for c in cases])
        lo = al.min(0) - 14; hi = al.max(0) + 14
        shape = tuple(np.ceil((hi - lo) / STEP).astype(int))
        gx = [lo[i] + np.arange(shape[i]) * STEP for i in range(3)]
        grid = np.stack(np.meshgrid(*gx, indexing="ij"), -1).reshape(-1, 3)
        acc = {k: np.zeros(shape, np.float32) for k in BONES}
        for c in cases:
            d = case_sdf(Path(cases_dir) / c, sims[c], grid, shape)
            for k in BONES:
                acc[k] += d[k]
        mean = mean_meshes(acc, len(cases), lo)
        ref_cloud = np.vstack([L.sample(v, f, 9000)[0] for v, f in mean.values()])
        print("iteration", it, "grid", shape, "mean vertices", {k: len(v) for k, (v, f) in mean.items()}, flush=True)
        del acc
    sizes = np.array([sims[c][0] for c in cases])
    np.savez_compressed(out, cases=np.array(cases), scales=sizes, rotations=np.array([sims[c][1] for c in cases]), translations=np.array([sims[c][2] for c in cases]),
                        **{f"{k}_v": v for k, (v, f) in mean.items()}, **{f"{k}_f": f for k, (v, f) in mean.items()})
    print("mean pelvis of", len(cases), "women; case-to-mean scale mean", round(float(sizes.mean()), 3), "sd", round(float(sizes.std()), 3))


if __name__ == "__main__":
    build(sys.argv[2], sys.argv[3], sys.argv[4])
