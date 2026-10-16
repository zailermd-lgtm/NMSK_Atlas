#!/usr/bin/env python3
"""Q224 (2): DUPLICATE tarsal / carpal bone meshes of the two OWN pages (Q223 top defect 6).

  her page   `tarsals_l` / `tarsals_r` (subject xfer_vhm2vhf = the MALE's composite tarsal mesh carried onto her) are displayed on top of her seven INDIVIDUAL tarsal bones (calcaneus, talus, cuboid, navicular,
             3 cuneiforms; subject ct_vhf_tarsal = her own CT tarsal label split into bones, scripts/vhf_split_tarsals.py).  Evidence: both are measured against her CT tarsal label (data/ct_sources/task_outputs/
             vhf_tarsals_split.nii.gz): IoU of the composite with the label vs IoU of the individuals' union, and the part of the composite that no individual covers.  The composite that does not match her label and is
             covered by the individuals is REMOVED.
  his page   `carpals_l` / `carpals_r` (hidden by default since Q212, 'kept for provenance': the grouped carpal mesh that also contained the distal radius and ulna) are superseded by `carpals_*_q212`
             (re-segmented from his CT) + `radius_*_distal_q212` + `ulna_*_distal_q212`.  Evidence: the part of the old mesh not covered by those new pieces (+ the radius / ulna shafts) is measured; REMOVED when it
             is redundant.  His left `cuneiform_medial_l` / `cuneiform_intermediate_l` (DU release shapes, subject vhm_both) lie 7.2 / 2.8 mm inside `metatarsals_l` (his CT label, subject ct_vhm_foot): the CT label wins, the
             cuneiform is trimmed by the metatarsal solid (exact 0.5 mm voxel boolean, re-meshed) when the guards hold.
Everything not listed stays byte for byte."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q216_common as C  # noqa: E402

FEMALE_TARSALS = ("calcaneus", "talus", "cuboid", "navicular", "cuneiform_medial", "cuneiform_intermediate", "cuneiform_lateral")
H = 0.5


def solid_of(B, sid, grid):
    g = B.get(sid)
    return C.VoxGrid.solid(grid, g["v"], g["f"])


def female_label_mask(grid, side):
    """her tarsal label of one side on the mesh grid (labels 1-7 right, 8-14 left of vhf_tarsals_split.nii.gz; atlas = (x - 7.769, z + 885.229, y - 14.137) of the label frame)"""
    import nibabel as nib
    im = nib.load(str(REPO / "data/ct_sources/task_outputs/vhf_tarsals_split.nii.gz"))
    d = np.asarray(im.dataobj)
    A = im.affine
    ox, oy, oz = 7.769, -885.229, 14.137
    ii = np.argwhere(np.ones(grid.shape, bool))
    P = grid.pos(ii)
    w = np.column_stack([P[:, 0] + ox, P[:, 2] + oz, P[:, 1] + oy])
    ijk = np.rint(np.linalg.solve(A[:3, :3], (w - A[:3, 3]).T).T).astype(int)
    ok = ((ijk >= 0) & (ijk < d.shape)).all(1)
    lab = np.zeros(len(P), d.dtype)
    lab[ok] = d[tuple(ijk[ok].T)]
    rng = (1, 7) if side == "r" else (8, 14)
    m = np.zeros(grid.shape, bool)
    sel = (lab >= rng[0]) & (lab <= rng[1])
    m[tuple(ii[sel].T)] = True
    return m


def female_composite(B, side, log=print):
    """-> dict(report) for tarsals_<side>: evidence against her CT label"""
    cid = f"tarsals_{side}"
    comp = B.get(cid)
    ids = [f"{n}_{side}" for n in FEMALE_TARSALS if B.find(f"{n}_{side}")]
    allv = np.vstack([comp["v"]] + [B.get(i)["v"] for i in ids])
    grid = C.VoxGrid(allv.min(0) - 3.0, allv.max(0) + 3.0, H)
    mc = C.VoxGrid.solid(grid, comp["v"], comp["f"])
    mi = np.zeros(grid.shape, bool)
    per = {}
    for i in ids:
        s = solid_of(B, i, grid)
        per[i] = round(float(s.sum()) * H ** 3 / 1000.0, 2)
        mi |= s
    lab = female_label_mask(grid, side)
    iou = lambda a, b: float((a & b).sum()) / max(float((a | b).sum()), 1.0)
    cov = ndi.binary_dilation(mi, iterations=int(round(1.5 / H)))
    unique = mc & ~cov
    rep = dict(id=cid, subject=B.items[B.find(cid)[0]]["e"]["subject"], individuals=ids, individual_volume_cm3=per,
               composite_volume_cm3=round(float(mc.sum()) * H ** 3 / 1000.0, 2), individuals_union_volume_cm3=round(float(mi.sum()) * H ** 3 / 1000.0, 2), label_volume_cm3=round(float(lab.sum()) * H ** 3 / 1000.0, 2),
               iou_composite_vs_her_label=round(iou(mc, lab), 3), iou_individuals_union_vs_her_label=round(iou(mi, lab), 3),
               composite_share_inside_her_label=round(float((mc & lab).sum()) / max(float(mc.sum()), 1), 3), individuals_share_inside_her_label=round(float((mi & lab).sum()) / max(float(mi.sum()), 1), 3),
               composite_volume_not_covered_by_individuals_cm3=round(float(unique.sum()) * H ** 3 / 1000.0, 2),
               composite_share_not_covered=round(float(unique.sum()) / max(float(mc.sum()), 1), 3))
    rep["remove"] = bool(rep["iou_individuals_union_vs_her_label"] > rep["iou_composite_vs_her_label"] + 0.10 and rep["composite_share_not_covered"] < 0.35 and len(ids) == 7)
    rep["reason"] = (f"the composite ({rep['subject']}) matches her CT tarsal label with IoU {rep['iou_composite_vs_her_label']} against {rep['iou_individuals_union_vs_her_label']} for the union of her seven individual bones "
                     f"(split of her own label); {100 * rep['composite_share_not_covered']:.0f} % of the composite volume is not covered by the individuals (within 1.5 mm)")
    return rep


def male_carpals(B, side, log=print):
    old = f"carpals_{side}"
    new = [f"carpals_{side}_q212", f"radius_{side}_distal_q212", f"ulna_{side}_distal_q212", f"radius_{side}", f"ulna_{side}"]
    new = [n for n in new if B.find(n)]
    g = B.get(old)
    allv = np.vstack([g["v"]] + [B.get(n)["v"] for n in new])
    grid = C.VoxGrid(g["v"].min(0) - 3.0, g["v"].max(0) + 3.0, H)
    mo = C.VoxGrid.solid(grid, g["v"], g["f"])
    mn = np.zeros(grid.shape, bool)
    for n in new:
        gg = B.get(n)
        lo, hi = grid.idx(gg["v"].min(0) - 1), grid.idx(gg["v"].max(0) + 1)
        if (hi < 0).any() or (lo >= np.asarray(grid.shape)).any():
            continue
        mn |= C.VoxGrid.solid(grid, gg["v"], gg["f"])
    cov = ndi.binary_dilation(mn, iterations=int(round(1.5 / H)))
    unc = mo & ~cov
    q212 = B.get(f"carpals_{side}_q212")
    rep = dict(id=old, subject=B.items[B.find(old)[0]]["e"]["subject"], hidden_default=bool(B.items[B.find(old)[0]]["e"].get("hidden_default")), superseded_by=new,
               old_volume_cm3=round(float(mo.sum()) * H ** 3 / 1000.0, 2), carpals_q212_volume_cm3=round(abs(float(trimesh.Trimesh(q212["v"], q212["f"], process=False).volume)) / 1000.0, 2),
               not_covered_by_new_cm3=round(float(unc.sum()) * H ** 3 / 1000.0, 2), not_covered_share=round(float(unc.sum()) / max(float(mo.sum()), 1), 3))
    rep["remove"] = bool(rep["hidden_default"] and rep["not_covered_share"] < 0.25)
    rep["reason"] = (f"hidden by default since Q212 and superseded: {100 * (1 - rep['not_covered_share']):.0f} % of its volume is covered (within 1.5 mm) by `{new[0]}` (his CT re-segmentation of the eight carpals) + the distal radius / ulna "
                     f"pieces + the radius / ulna meshes; the rest ({rep['not_covered_by_new_cm3']} cm3) is the smoothing margin of the old grouped label")
    return rep


def trim_by(B, sid, other, side_note="", log=print, min_vol=0.8):
    """sid minus the solid of `other` (+0.2 mm), re-meshed -> (v, f, info) or (None, None, info)"""
    g, o = B.get(sid), B.get(other)
    grid = C.VoxGrid(np.minimum(g["v"].min(0), o["v"].min(0)) - 3.0, np.maximum(g["v"].max(0), o["v"].max(0)) + 3.0, H)
    ms = C.VoxGrid.solid(grid, g["v"], g["f"])
    mo = C.VoxGrid.solid(grid, o["v"], o["f"])
    mo2 = ndi.binary_dilation(mo, iterations=1)
    over = ms & mo2
    new = ms & ~mo2
    new, dropped = C.largest_components(new)
    v1, f1 = C.mask_to_mesh(new, grid, sigma_vox=0.8, budget=int(B.items[B.find(sid)[0]]["e"]["nf"]))
    vol0, vol1 = C.mask_volume_cm3(ms, H), C.volume_cm3(v1, f1)
    info = dict(id=sid, trimmed_by=other, overlap_volume_cm3=round(C.mask_volume_cm3(over, H), 3), volume_cm3=[round(vol0, 2), round(vol1, 2)], volume_ratio=round(vol1 / max(vol0, 1e-6), 3), dropped_fragment_fraction=round(dropped, 4))
    why = []
    if vol1 / max(vol0, 1e-6) < min_vol:
        why.append(f"volume x{vol1 / vol0:.2f} (gate >= {min_vol})")
    if len(trimesh.Trimesh(v1, f1, process=False).split(only_watertight=False)) != 1:
        why.append("more than one piece")
    info["why"] = why
    return (v1, f1, info) if not why else (None, None, info)
