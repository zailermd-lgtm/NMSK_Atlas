#!/usr/bin/env python3
"""Q287: fibroglandular tissue inside her own CT breasts (Q285), by a stated HU rule on her own CT.

    python3 scripts/anatomy/q287/breast_fgt_q287.py build CT.nii.gz

CT: her stacked torso CT (IDC series b9cf8e7a-2505-4137-9ae3-f8d0cf756c13 on the 0.9375 mm grid, scripts/stack_dicom_series.py),
the same grid as data/ct_sources/task_outputs/vhf_breasts.nii.gz and vhf_total.nii.gz.

Method (rule-based, not a trained model, not hand-drawn): the breast mask of each side is rebuilt exactly as Q285 kept it (same
label, midline cut, silhouette clip, largest piece, holes filled; its volume is asserted against the Q285 report); inside it a voxel is
fibroglandular when HU >= -30 (adipose tissue lies at about -190..-30 HU on unenhanced CT, gland / fibrous stroma / vessels above;
the -30 HU boundary is the one the Q285 badge already reports), it is not in her pectoralis / serratus / any `total` label, and it is
deeper than 2 voxels (1.9 mm) below her body silhouette, so the skin and its partial-volume rim are not counted. Pieces under
SPECK_CM3 are dropped (reported). Mesh: Gaussian(SIGMA) field, marching cubes at the level that keeps the voxel volume, her atlas
frame (hip-joint origin), quadric decimation with the Q163 continuity guard.

Gates (held, not shipped, if failed): <= 1 % of vertices more than 1 mm outside her Q285 breast mesh of the same side; mesh volume
within 10 % of the voxel volume (a thin branching network loses more to smoothing than a solid organ: 10 % not 3 %); glandular
fraction (fibroglandular voxels / breast voxels) inside the published breast-CT range (Vedantham 2012: 0.012-0.719).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/anatomy/q285"))
from engine import volume_ingest as vol  # noqa: E402
from scripts.ribs_from_ct_labels import ORIGIN, TASK  # noqa: E402
from scripts.viscera_from_ct_labels_q193 import largest, mesh_volume_preserving, drop_specks, closed_vol_vox  # noqa: E402
import breast_from_ct_q285 as Q285  # noqa: E402

SUBJECT = "ct_vhf_breast_fgt"
HU_MIN = -30.0
SKIN_RIM_VOX = 2
SPECK_CM3 = 0.05
SIGMA = 0.7
BUDGET = 12000
GATE = {"max_outside_breast_gt1mm_frac": 0.01, "volume_tol": 0.10, "vgf_range": [0.012, 0.719]}
REFS = [
    {"what": "dedicated breast CT, 137 breasts of 136 women (BI-RADS 4/5 work-up): volumetric glandular fraction mean 0.172 +/- 0.142, "
             "range 0.012-0.719, falling with age and with breast volume",
     "cite": "Vedantham S, Shi L, Karellas A, O'Connell AM. Dedicated breast CT: fibroglandular volume measurements in a diagnostic "
             "population. Med Phys 2012;39:7317-28", "doi": "10.1118/1.4765050", "pmid": "23231281"},
    {"what": "breast CT + mammographic volumetry, 2831 women: mean fibroglandular share 19.3 % (13.7-25.6 % by group, skin included), "
             "80 % of women below 27 %",
     "cite": "Yaffe MJ, Boone JM, Packard N, et al. The myth of the 50-50 breast. Med Phys 2009;36:5437-43",
     "doi": "10.1118/1.3250863", "pmid": "20095256"},
]
SIDES = {"right": ("breast_fgt_ct_r", "Breast fibroglandular tissue (right), from her CT", "Parenchyma et stroma mammae dextrae"),
         "left": ("breast_fgt_ct_l", "Breast fibroglandular tissue (left), from her CT", "Parenchyma et stroma mammae sinistrae")}


def fgt_rule(breast, ct, excl, deep):
    """the HU rule, pure so it can be unit-tested: breast voxels at HU >= HU_MIN, outside the exclusion labels, deep to the skin rim"""
    return breast & (ct >= HU_MIN) & ~excl & deep


def drop_small(mask, vox_cm3):
    from scipy import ndimage as ndi
    lab, n = ndi.label(mask, structure=np.ones((3, 3, 3), bool))
    if n == 0:
        return mask, 0.0, 0
    sz = np.bincount(lab.ravel())[1:] * vox_cm3
    keep = np.zeros(n + 1, bool); keep[1:] = sz >= SPECK_CM3
    return keep[lab], float(sz[~keep[1:]].sum()), int(keep.sum())


def build(ct_path):
    import nibabel as nib
    import trimesh
    from scipy import ndimage as ndi
    from export_viewer_bundle import decimate_guarded
    img = nib.load(str(TASK / "vhf_breasts.nii.gz")); A = img.affine
    seg = np.asarray(img.dataobj) > 0
    tot = np.asarray(nib.load(str(TASK / "vhf_total.nii.gz")).dataobj).astype(np.uint8)
    abd = np.asarray(nib.load(str(TASK / "vhf_abdominal_muscles.nii.gz")).dataobj)
    cimg = nib.load(ct_path); assert np.allclose(cimg.affine, A) and cimg.shape == seg.shape, "CT not on her vhf_total grid"
    ct = np.asarray(cimg.dataobj).astype(np.float32)
    vox_cm3 = float(abs(np.linalg.det(A[:3, :3]))) / 1000.0
    O = np.array([float(x) for x in ORIGIN["vhf"].split(",")])
    mid, mid_src = vol.midline_x(tot, A, {v: k for k, v in Q285.TS_NAMES.items()})
    halves, _ = vol._split_at_x(seg, A, mid, mid_src)
    body = Q285.body_silhouette(ct)                     # already eroded by 1 voxel, as Q285
    deep = ndi.binary_erosion(body, iterations=SKIN_RIM_VOX)
    excl = (abd > 0) | (tot > 0)
    q285 = json.loads((REPO / "data/derived/Q285_vhf_breast_report.json").read_text())["sides"]
    rep = {"_README": ["Q287: fibroglandular tissue in her CT breasts by an HU rule; see scripts/anatomy/q287/breast_fgt_q287.py."],
           "rule": {"hu_min": HU_MIN, "skin_rim_voxels": SKIN_RIM_VOX, "speck_cm3": SPECK_CM3, "sigma_vox": SIGMA, "budget": BUDGET},
           "gates": GATE, "references": REFS, "sides": {}, "shipped": [], "held": {}}
    meshes = {}
    for side, raw in halves.items():
        sid, name, latin = SIDES[side]
        m, _, _ = largest(raw & body); m = ndi.binary_fill_holes(m)
        bcm3 = float(m.sum()) * vox_cm3
        assert abs(bcm3 - q285[side]["kept_voxel_cm3"]) < 0.2, (side, bcm3, q285[side]["kept_voxel_cm3"])
        hu = ct[m]
        r = {"breast_cm3": round(bcm3, 1), "hu_ge_min_in_breast_cm3": round(float((hu >= HU_MIN).sum()) * vox_cm3, 1)}
        g0 = fgt_rule(m, ct, np.zeros_like(m), np.ones_like(m))
        r["removed_skin_rim_cm3"] = round(float((g0 & ~deep).sum()) * vox_cm3, 2)
        r["removed_muscle_or_total_label_cm3"] = round(float((g0 & deep & excl).sum()) * vox_cm3, 2)
        g = fgt_rule(m, ct, excl, deep)
        g, dropped, npieces = drop_small(g, vox_cm3)
        r.update(specks_dropped_cm3=round(dropped, 2), pieces_kept=npieces)
        r["fgt_voxel_cm3"] = round(float(g.sum()) * vox_cm3, 2)
        r["glandular_fraction"] = round(float(g.sum()) / float(m.sum()), 4)
        r["fgt_hu_median"] = float(np.median(ct[g]))
        idx = np.argwhere(g); lo, hi = idx.min(0), idx.max(0)
        crop = tuple(slice(max(a - 4, 0), b + 5) for a, b in zip(lo, hi))
        v, f, level, _ = mesh_volume_preserving(g[crop], r["fgt_voxel_cm3"], vox_cm3, sigma=SIGMA)
        v, f, specks = drop_specks(v, f)
        v = v + np.array([s.start for s in crop])
        va = vol.voxels_to_atlas(v, A) - O
        r.update(iso_level=round(float(level), 3), mesh_full_cm3=round(closed_vol_vox(v, f) * vox_cm3, 2), mesh_specks_dropped_cm3=round(float(sum(specks)), 3), mesh_specks_dropped_n=len(specks))
        dec = decimate_guarded(va, f, BUDGET)
        vd, fd = dec if dec is not None else (va, f)
        r["shipped_triangles"] = int(len(fd))
        r["shipped_vs_voxels"] = round(closed_vol_vox(vd, fd) / 1000.0 / r["fgt_voxel_cm3"], 4)
        bm = trimesh.load(REPO / "build/vh/ct_vhf_breast" / f"breast_ct_{side[0]}.obj", process=False)
        sd = Q285.skin_distance(bm, vd)
        r["outside_breast_gt1mm_frac"] = round(float((sd > 1.0).mean()), 4)
        r["outside_breast_max_mm"] = round(float(sd.max()), 2)
        r["components"] = int(trimesh.Trimesh(vd, fd, process=False).body_count)
        bad = []
        if r["outside_breast_gt1mm_frac"] > GATE["max_outside_breast_gt1mm_frac"]:
            bad.append(f"{100 * r['outside_breast_gt1mm_frac']:.1f} % of vertices > 1 mm outside her breast")
        if abs(r["shipped_vs_voxels"] - 1) > GATE["volume_tol"]:
            bad.append(f"mesh volume {r['shipped_vs_voxels']:.3f}x the voxels")
        lo_, hi_ = GATE["vgf_range"]
        if not lo_ <= r["glandular_fraction"] <= hi_:
            bad.append(f"glandular fraction {r['glandular_fraction']:.3f} outside the published range")
        rep["sides"][side] = r
        if bad:
            rep["held"][sid] = bad
        else:
            rep["shipped"].append(sid); meshes[sid] = (vd, fd, side, name, latin)
    return rep, meshes


def badge(rep, side):
    r = rep["sides"][side]
    v, y = REFS
    return (f"Q287: rule-based on her own CT, not hand-drawn and not a trained model; not checked by hand. Inside her Q285 breast "
            f"(TotalSegmentator `breasts`, {r['breast_cm3']:.0f} cm3 this side) a voxel counts as fibroglandular (gland, ducts, fibrous "
            f"stroma and Cooper ligaments, small vessels -- unenhanced CT cannot tell these apart) when it reads HU >= {HU_MIN:.0f}; fat reads "
            f"about -190..-30. Voxels in her pectoralis / serratus labels and the outer {SKIN_RIM_VOX} voxels (1.9 mm) under her skin "
            f"surface are excluded, pieces under {SPECK_CM3} cm3 dropped, and in the mesh pieces under 1 % of the volume. Result: {r['fgt_voxel_cm3']:.0f} cm3, glandular fraction "
            f"{100 * r['glandular_fraction']:.1f} % of the breast: at the low end of the published range, in line with the reported fall "
            f"with age and breast volume (she was 59, postmenopausal, with large breasts; breast-CT cohort mean 17.2 +/- 14.2 %, range 1.2-71.9 %: Vedantham et al. 2012, "
            f"doi:{v['doi']}; mean 19.3 % in 2831 women: Yaffe et al. 2009, doi:{y['doi']}). The 0.94 mm voxels and partial volume make "
            f"thin strands thicker or break them: read it as where her dense tissue lies, not as a duct map. Checked: "
            f"{100 * r['outside_breast_gt1mm_frac']:.1f} % of vertices more than 1 mm outside her breast surface; mesh "
            f"{r['shipped_vs_voxels']:.3f}x the voxel volume. Fade or hide the breast to see it.")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build"]); ap.add_argument("ct")
    ap.add_argument("--out", default="build/vh/ct_vhf_breast_fgt")
    a = ap.parse_args()
    rep, meshes = build(a.ct)
    import trimesh
    out = REPO / a.out; out.mkdir(parents=True, exist_ok=True)
    items = []
    for sid, (v, f, side, name, latin) in meshes.items():
        trimesh.Trimesh(v, f, process=False).export(out / f"{sid}.obj")
        items.append({"id": sid, "side": side, "name": name, "latin": latin, "badge": badge(rep, side), "obj": f"{sid}.obj"})
    (out / "items.json").write_text(json.dumps(items, indent=1))
    (REPO / "data/derived/Q287_breast_fgt_report.json").write_text(json.dumps(rep, indent=1))
    for side, r in rep["sides"].items():
        print(side, json.dumps(r))
    print("shipped", rep["shipped"], "held", rep["held"])


if __name__ == "__main__":
    main()
