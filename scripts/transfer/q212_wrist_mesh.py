#!/usr/bin/env python3
"""Q212: meshes of the re-segmented wrist pieces of HIS CT (output of q212_wrist_seg.py).

    python3 scripts/transfer/q212_wrist_mesh.py --seg build/q212/wrist_seg_r.npz --side r --out build/q212/wrist_mesh_r.npz

Pieces (voxels of his OLD carpal label that the watershed gives to the radius / ulna / carpals; his radius / ulna labels and their meshes are not touched):
  radius_distal  = radius epiphysis (the distal articular plate that his carpal label had swallowed), abuts the cut face of his measured radius
  ulna_distal    = ulnar head, abuts the cut face of his measured ulna
  carpals        = the eight carpal bones without the epiphyses (replaces the grouped carpal mesh, which is kept in the bundle but hidden by default)
Each piece: voxel set -> 3-D hole fill -> small components dropped -> Gaussian-smoothed marching cubes (level 0.5, 0.5 mm grid) -> quadric decimation to the triangle density of his
other hand-bone meshes (about 240 triangles per cm3) -> Taubin-style light smoothing is NOT applied (the surface stays where the CT voxels put it)."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import marching_cubes
import trimesh

TRI_PER_CM3 = 240.0
MIN_COMP_VOX = 120        # 15 mm3 at 0.5 mm: smaller islands are segmentation specks


def mesh_of(mask, xs, ys, zs, tri_per_cm3=TRI_PER_CM3, min_vox=MIN_COMP_VOX):
    H = float(xs[1] - xs[0])
    m = ndi.binary_fill_holes(np.pad(mask, 2))
    lab, n = ndi.label(m, structure=np.ones((3, 3, 3)))
    if n:
        sz = np.bincount(lab.ravel()); keep = np.flatnonzero(sz >= min_vox); keep = keep[keep > 0]
        m = np.isin(lab, keep)
    f = ndi.gaussian_filter(m.astype(np.float32), 0.6)
    v, fa, _, _ = marching_cubes(f, 0.5, spacing=(H, H, H))
    v = v - 2 * H + np.array([xs[0], ys[0], zs[0]])
    tm = trimesh.Trimesh(v, fa, process=True)
    vol = float(m.sum()) * H ** 3 / 1000.0
    target = int(max(400, tri_per_cm3 * vol))
    if len(tm.faces) > target:
        tm = tm.simplify_quadric_decimation(face_count=target)
    tm.remove_unreferenced_vertices()
    return np.asarray(tm.vertices, float), np.asarray(tm.faces, np.int64), dict(volume_cm3=round(vol, 2), components=int(len(np.unique(lab[m])) - (1 if 0 in lab[m] else 0)) if n else 0,
                                                                                    n_vertices=int(len(tm.vertices)), n_triangles=int(len(tm.faces)))


def photo_agreement(mask, xs, ys, zs, cream):
    """share of the piece's voxel centres within 1.5 mm of his cryosection-photograph bone evidence (cream pixels, Q205), counted over the voxels inside the photographed box"""
    from scipy.spatial import cKDTree
    i, j, k = np.nonzero(mask)
    p = np.c_[xs[i], ys[j], zs[k]]
    inb = ((p >= cream.min(0) - 2) & (p <= cream.max(0) + 2)).all(1)
    if not inb.any():
        return dict(in_photo_box=0.0, within_1p5mm=None)
    d = cKDTree(cream).query(p[inb])[0]
    return dict(in_photo_box=round(float(inb.mean()), 2), within_1p5mm=round(float((d <= 1.5).mean()), 3), n_voxels_in_box=int(inb.sum()))


def pieces(seg):
    ws, Lc = seg["ws"], seg["Lc"]
    return {"radius_distal": Lc & (ws == 1), "ulna_distal": Lc & (ws == 2), "carpals": Lc & (ws == 3)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", required=True); ap.add_argument("--side", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    seg = np.load(a.seg)
    xs, ys, zs = seg["xs"], seg["ys"], seg["zs"]
    out, info = {}, {}
    cream = np.load(Path(__file__).resolve().parents[2] / "data/derived/Q205_his_hand_photo_evidence.npz")[f"cream_{a.side}"]
    for name, mask in pieces(seg).items():
        v, f, st = mesh_of(mask, xs, ys, zs)
        out[f"{name}_v"], out[f"{name}_f"] = v, f
        st["photo"] = photo_agreement(mask, xs, ys, zs, cream)
        st["bbox_min"], st["bbox_max"] = v.min(0).round(1).tolist(), v.max(0).round(1).tolist()
        info[name] = st
        print(a.side, name, st)
    np.savez_compressed(a.out, info=np.array(json.dumps(info)), **out)
