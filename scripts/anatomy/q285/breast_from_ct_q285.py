"""Q285: the Visible Human female's own breasts, meshed from TotalSegmentator's open `breasts` task on her own CT.

    python3 scripts/anatomy/q285/breast_from_ct_q285.py build SEG.nii.gz CT.nii.gz [--bundle build/q263_pre/bundle_own_f]

SEG: `TotalSegmentator -ta breasts` (v2.18.0, Apache-2.0, class 1 `breast`) on her torso CT (IDC series
b9cf8e7a-2505-4137-9ae3-f8d0cf756c13, stacked on the 0.9375 mm grid by scripts/stack_dicom_series.py -- the same grid and
affine as data/ct_sources/task_outputs/vhf_total.nii.gz). CT: that stacked CT (HU), used only for the checks.

Method, the Q193 organ recipe (scripts/viscera_from_ct_labels_q193.py) with two breast-specific steps, both stated in the report:
the single bilateral label is cut at her own midline (engine.volume_ingest.midline_x on her `total` labels: the sternum), and each
side is clipped to her body silhouette (HU > -300, the definition her skin mesh was built from) eroded by one voxel (0.94 mm): the
label's outermost voxels reach into air by partial volume, and the outermost tissue layer over the breast is skin (about 1-2 mm thick),
not breast tissue, so the breast surface is kept beneath it. Then: largest connected piece per side, 3-D hole fill, marching cubes on a Gaussian(1 voxel) field at
the level that keeps the voxel volume, atlas frame with her hip-joint origin (the one every ct_vhf_ subject uses), quadric decimation
to the organ budget with the Q163 continuity guard.

Gates (a failing side is held, not shipped): 0 % of vertices outside her shipped skin mesh beyond 1 mm; <= 5 % of vertices > 1 mm
inside her CT bone labels; label touches no edge of the field of view; largest piece >= 85 % of the side; mesh volume within 3 % of
the label volume. Reported, not gated: overlap with her pectoralis major / serratus anterior labels (the expected posterior interface),
HU composition, left/right asymmetry, volume against published cohort means.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from engine import volume_ingest as vol  # noqa: E402
from scripts.ribs_from_ct_labels import ORIGIN, TASK, to_vox  # noqa: E402
from scripts.costal_cartilage_from_ct_labels import BONE  # noqa: E402
from scripts.viscera_from_ct_labels_q193 import (largest, mesh_volume_preserving, drop_specks, edge_touch,  # noqa: E402
                                                 bone_depth_fraction, closed_vol_vox)

SUBJECT = "ct_vhf_breast"
BUDGET = 8000                     # triangles per side: the organ budget her HRA breast and pectoralis major ship at
GATE = {"max_outside_skin_gt1mm_frac": 0.0, "max_in_bone_frac": 0.05, "min_largest_share": 0.85, "volume_tol": 0.03}
REFS = [
    {"what": "MRI volumetry, 22 women", "left_ml": 771.0, "right_ml": 763.9,
     "cite": "Behrens AS, Huebner H, Haeberle L, et al. Comparative assessment of breast volume using a smartphone device versus MRI. "
             "Breast Cancer 2025;32:166-176", "doi": "10.1007/s12282-024-01647-6", "pmid": "39546156"},
    {"what": "VECTRA 3-D surface imaging, 100 healthy participants; mean relative left/right difference 16.0 % (SD 12.7)",
     "left_ml": 636.8, "right_ml": 664.8, "asym_mean_pct": 16.0, "asym_sd_pct": 12.7,
     "cite": "Killaars RC, Janssen DGE, Piatkowski de Grzymala AA. Breast Volume Measurements and Objectivations for Determination "
             "of Symmetry. Aesthetic Plast Surg 2026", "doi": "10.1007/s00266-026-06058-w", "pmid": "42384061"},
]
TS_NAMES = {int(k): v for k, v in json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"].items()}
SIDES = {"right": ("breast_ct_r", "Breast (right), from her CT", "Mamma dextra"),
         "left": ("breast_ct_l", "Breast (left), from her CT", "Mamma sinistra")}


def body_silhouette(ct):
    from scipy import ndimage as ndi
    b = ct > -300
    lab, n = ndi.label(b)
    sz = np.bincount(lab.ravel())[1:]
    b = lab == int(sz.argmax()) + 1
    b = np.stack([ndi.binary_fill_holes(b[:, :, z]) for z in range(b.shape[2])], axis=2)
    return ndi.binary_erosion(b, iterations=1)


def skin_distance(skin, pts):
    """signed distance to her shipped skin mesh: > 0 outside"""
    import trimesh
    inside = skin.contains(pts)
    d = trimesh.proximity.ProximityQuery(skin).on_surface(pts)[1]
    return np.where(inside, -d, d)


def build(seg_path, ct_path, bundle_dir):
    import nibabel as nib
    from scipy import ndimage as ndi
    sys.path.insert(0, str(REPO / "scripts"))
    from export_viewer_bundle import decimate_guarded
    from scripts.transfer.q200_bundle import Bundle
    import trimesh

    img = nib.load(seg_path); A = img.affine
    seg = np.asarray(img.dataobj) > 0
    tot_img = nib.load(str(TASK / "vhf_total.nii.gz"))
    tot = np.asarray(tot_img.dataobj).astype(np.uint8)
    assert np.allclose(tot_img.affine, A) and tot.shape == seg.shape, "SEG is not on her vhf_total grid"
    ct = np.asarray(nib.load(ct_path).dataobj)
    assert ct.shape == seg.shape
    abd = np.asarray(nib.load(str(TASK / "vhf_abdominal_muscles.nii.gz")).dataobj)
    abd_names = {int(k): v for k, v in json.loads((REPO / "mappings" / "totalsegmentator_abdominal_muscles_labels.json").read_text())["labels"].items()}
    vox_cm3 = float(abs(np.linalg.det(A[:3, :3]))) / 1000.0
    sp = tuple(float(x) for x in np.linalg.norm(A[:3, :3], axis=0))
    O = np.array([float(x) for x in ORIGIN["vhf"].split(",")])
    mid, mid_src = vol.midline_x(tot, A, {v: k for k, v in TS_NAMES.items()})
    halves, notes = vol._split_at_x(seg, A, mid, mid_src)
    body = body_silhouette(ct)
    B = Bundle(REPO / bundle_dir)
    sk = B.get("skin"); skin = trimesh.Trimesh(sk["v"], sk["f"], process=False)
    rep = {"_README": ["Q285: her breasts from TotalSegmentator `breasts` on her own CT. Derived data; see the script docstring for the method and gates."],
           "source": {"segmentation": "TotalSegmentator v2.18.0 task `breasts` (Apache-2.0), class 1 `breast`, run on CPU in one z-chunk (z 450-680) by "
                                      "scripts/run_totalsegmentator_chunked.py; a first 3-chunk run showed an 11 % step in the per-slice area at the "
                                      "chunk stitch, so the single-chunk run is the one used",
                      "ct": "NLM Visible Human Project female CT (public domain), IDC series b9cf8e7a-2505-4137-9ae3-f8d0cf756c13, 0.9375 mm grid"},
           "midline": notes[0], "origin_atlas_mm": O.tolist(), "gates": GATE, "references": REFS, "sides": {}, "shipped": [], "held": {}}
    meshes = {}
    for side, raw in halves.items():
        sid, name, latin = SIDES[side]
        r = {"label_voxel_cm3": round(float(raw.sum()) * vox_cm3, 1)}
        m = raw & body
        r["clipped_to_silhouette_cm3"] = round(float((raw & ~body).sum()) * vox_cm3, 2)
        m, others, share = largest(m)
        m = ndi.binary_fill_holes(m)
        r["largest_component_share"] = round(share, 4)
        r["pieces_dropped_cm3"] = [round(o * vox_cm3, 2) for o in others[:6]]
        r["kept_voxel_cm3"] = round(float(m.sum()) * vox_cm3, 1)
        r["edge_touch"] = edge_touch(m, m.shape)
        idx = np.argwhere(m); lo, hi = idx.min(0), idx.max(0)
        r["voxel_extent_ijk"] = [lo.tolist(), hi.tolist()]
        hu = ct[m]
        r["hu"] = {"p01": float(np.percentile(hu, 1)), "median": float(np.median(hu)), "p99": float(np.percentile(hu, 99)),
                   "fat_frac_-190_-30": round(float(((hu >= -190) & (hu < -30)).mean()), 4),
                   "soft_frac_-30_100": round(float(((hu >= -30) & (hu <= 100)).mean()), 4)}
        ov = abd[m]; u, c = np.unique(ov[ov > 0], return_counts=True)
        r["overlap_muscle_labels"] = {abd_names.get(int(a), str(a)): round(float(b) / m.sum(), 4) for a, b in zip(u, c)}
        ot = tot[m]; r["overlap_total_labels_frac"] = round(float((ot > 0).mean()), 4)
        crop = tuple(slice(max(a - 4, 0), b + 5) for a, b in zip(lo, hi))
        res = mesh_volume_preserving(m[crop], r["kept_voxel_cm3"], vox_cm3, sigma=1.0)
        v, f, level, mv = res
        v, f, specks = drop_specks(v, f)
        v = v + np.array([s.start for s in crop])
        va = vol.voxels_to_atlas(v, A) - O
        mvol = closed_vol_vox(v, f) * vox_cm3
        r.update(iso_level=round(float(level), 3), mesh_full_cm3=round(mvol, 2), mesh_vs_label=round(mvol / r["kept_voxel_cm3"], 4),
                 specks_dropped_cm3=specks, full_triangles=int(len(f)))
        dec = decimate_guarded(va, f, BUDGET)
        vd, fd = (dec if dec is not None else (va, f))
        r["shipped_triangles"] = int(len(fd))
        r["shipped_vs_label"] = round(closed_vol_vox(vd, fd) / 1000.0 / r["kept_voxel_cm3"], 4)
        sd = skin_distance(skin, vd)
        r["outside_skin_frac"] = round(float((sd > 0).mean()), 4)
        r["outside_skin_gt1mm_frac"] = round(float((sd > 1.0).mean()), 4)
        r["outside_skin_max_mm"] = round(float(sd.max()), 2)
        b1, b0 = bone_depth_fraction(tot, A, O, vd, sp)
        r["in_bone_gt1mm_frac"] = round(b1, 4)
        r["bbox_atlas_mm"] = [np.round(vd.min(0), 1).tolist(), np.round(vd.max(0), 1).tolist()]
        bad = []
        if r["outside_skin_gt1mm_frac"] > GATE["max_outside_skin_gt1mm_frac"]:
            bad.append(f"{100 * r['outside_skin_gt1mm_frac']:.1f} % of vertices more than 1 mm outside the skin")
        if r["in_bone_gt1mm_frac"] > GATE["max_in_bone_frac"]:
            bad.append(f"{100 * r['in_bone_gt1mm_frac']:.1f} % of vertices > 1 mm inside bone")
        if r["edge_touch"]:
            bad.append("touches the field of view: " + ",".join(r["edge_touch"]))
        if share < GATE["min_largest_share"]:
            bad.append(f"fragmented (largest piece {100 * share:.0f} %)")
        if abs(r["mesh_vs_label"] - 1) > GATE["volume_tol"]:
            bad.append(f"mesh volume {r['mesh_vs_label']:.3f}x the label")
        rep["sides"][side] = r
        if bad:
            rep["held"][sid] = bad
        else:
            rep["shipped"].append(sid)
            meshes[sid] = (vd, fd, side, name, latin)
    rr, ll = rep["sides"]["right"]["kept_voxel_cm3"], rep["sides"]["left"]["kept_voxel_cm3"]
    rep["asymmetry_pct_of_mean"] = round(100 * abs(rr - ll) / (0.5 * (rr + ll)), 1)
    return rep, meshes


def badge(rep, side):
    r = rep["sides"][side]
    ref = "; ".join(f"{x['what']}: mean left {x['left_ml']:.0f} / right {x['right_ml']:.0f} mL ({x['cite'].split('.')[0]} et al., doi:{x['doi']})" for x in REFS)
    return (f"Q285: measured on this body by automatic segmentation (TotalSegmentator v2.18 `breasts` task on her own CT, class `breast`), "
            f"not hand-drawn; not checked by hand. The bilateral label is cut at her own midline ({rep['midline'].split(';')[0]}) and kept "
            f"one voxel (0.94 mm) beneath her body silhouette (HU > -300, as her skin mesh), the outermost layer being skin. Label volume {r['kept_voxel_cm3']:.0f} cm3 on this side; left/right "
            f"difference {rep['asymmetry_pct_of_mean']:.1f} % of the mean. HU: {100 * r['hu']['fat_frac_-190_-30']:.0f} % fat-range, "
            f"{100 * r['hu']['soft_frac_-30_100']:.0f} % soft-tissue range (fibroglandular). Largest connected piece "
            f"({100 * r['largest_component_share']:.0f} % of the side), holes filled, surface at the level that keeps the label volume "
            f"(mesh {r['mesh_vs_label']:.3f}x). Checked: {100 * r['outside_skin_gt1mm_frac']:.1f} % of vertices more than 1 mm outside her skin, "
            f"{100 * r['in_bone_gt1mm_frac']:.1f} % more than 1 mm inside her CT bone labels; it touches her pectoralis major / serratus "
            f"anterior labels only at their surface. Published cohort means for comparison (not a range for her): {ref}. The specimen is an "
            f"unfrozen 59-year-old cadaver (unenhanced CT, supine).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("seg"); ap.add_argument("ct")
    ap.add_argument("--bundle", default="build/q263_pre/bundle_own_f")
    ap.add_argument("--out", default="build/vh/ct_vhf_breast")
    a = ap.parse_args()
    rep, meshes = build(a.seg, a.ct, a.bundle)
    out = REPO / a.out; out.mkdir(parents=True, exist_ok=True)
    import trimesh
    items = []
    for sid, (v, f, side, name, latin) in meshes.items():
        trimesh.Trimesh(v, f, process=False).export(out / f"{sid}.obj")
        items.append({"id": sid, "side": side, "name": name, "latin": latin, "badge": badge(rep, side), "obj": f"{sid}.obj"})
    (out / "items.json").write_text(json.dumps(items, indent=1))
    (REPO / "data" / "derived" / "Q285_vhf_breast_report.json").write_text(json.dumps(rep, indent=1))
    for side, r in rep["sides"].items():
        print(side, json.dumps({k: r[k] for k in ("kept_voxel_cm3", "largest_component_share", "edge_touch", "mesh_vs_label", "shipped_triangles",
                                                   "outside_skin_frac", "outside_skin_gt1mm_frac", "outside_skin_max_mm", "in_bone_gt1mm_frac",
                                                   "overlap_muscle_labels", "overlap_total_labels_frac", "clipped_to_silhouette_cm3")}))
    print("asymmetry %", rep["asymmetry_pct_of_mean"], "shipped", rep["shipped"], "held", rep["held"])


if __name__ == "__main__":
    main()
