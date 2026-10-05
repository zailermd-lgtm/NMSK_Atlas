"""Q193: the organs of BOTH own models meshed from their own TotalSegmentator `total` CT labels.

    python3 scripts/viscera_from_ct_labels_q193.py build --body vhm|vhf     # -> build/vh/ct_v{m,f}_viscera (+ label volume + report)
    python3 scripts/viscera_from_ct_labels_q193.py audit --body vhm|vhf --bundle build/viewer_m_hr_q193   # gates on the SHIPPED meshes

`build`: per organ (table ORGANS) the label(s) of data/ct_sources/task_outputs/<body>_total.nii.gz -> one binary mask (lungs: the
lobes of a side merged), LARGEST connected component only (pieces dropped are listed), 3-D hole fill, then marching cubes on a
Gaussian(1 voxel) field of that mask at the iso-level that makes the closed mesh enclose the voxel volume (bisection; this is the
"light smoothing that preserves volume": the surface moves by a fraction of a voxel and the volume is held, not shrunk), shells under
1 % dropped, atlas frame (+X right, +Y superior, +Z anterior, mm, origin = the body's hip-joint origin, the same one every ct_v?_ subject
uses). Colon: the label minus the pelvic rectum / sigmoid of Q169 / Q170 (those stay in ct_v?_pelvis).

Holds BEFORE meshing: label fragmented (largest component < 85 % of the label), or label volume < 35 % of the published reference
(under-segmented: the mesh would claim an organ it does not show), or < 1 cm3. Gates AFTER meshing (a failing organ is held, not shipped):
0 % of vertices outside the skin mesh, <= 5 % of vertices > 1 mm inside the body's own CT bone labels, <= 10 % of the organ's volume inside
any one neighbouring organ's mesh, mesh volume within 3 % of the label volume. `audit` repeats the gates on the decimated meshes of a built bundle.
SIZE CAVEAT in the badge when the label volume is > 1.5x the published reference.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from engine import volume_ingest as vol  # noqa: E402
from scripts.ribs_from_ct_labels import ORIGIN, TASK, closed_volume_cm3, load_skin, to_vox  # noqa: E402
from scripts.costal_cartilage_from_ct_labels import BONE  # noqa: E402

TS = json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"]
SPECK = 0.01
GATE = {"max_outside_skin_frac": 0.0, "max_in_bone_frac": 0.05, "max_overlap_frac": 0.10, "volume_tol": 0.03,
        "min_largest_share": 0.85, "min_ratio_to_reference": 0.35, "size_caveat_ratio": 1.5}
BODY = {"vhm": {"sex": "male", "who": "his", "Who": "His", "title": "Visible Human male", "frozen": True,
                "pelvic": TASK / "vhm_pelvic_viscera.nii.gz"},
        "vhf": {"sex": "female", "who": "her", "Who": "Her", "title": "Visible Human female", "frozen": False,
                "pelvic": TASK / "vhf_pelvic_viscera.nii.gz"}}

# id, TS labels, name, side, region
ORGANS = [
    ("liver", [5], "Liver", None, "trunk"),
    ("spleen", [1], "Spleen", None, "trunk"),
    ("stomach", [6], "Stomach (wall and contents)", None, "trunk"),
    ("pancreas", [7], "Pancreas", None, "trunk"),
    ("gallbladder", [4], "Gallbladder", None, "trunk"),
    ("duodenum", [19], "Duodenum", None, "trunk"),
    ("small_bowel", [18], "Small bowel (jejunum and ileum)", None, "trunk"),
    ("colon", [20], "Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures)", None, "trunk"),
    ("kidney_r", [2], "Right kidney", "right", "trunk"),
    ("kidney_l", [3], "Left kidney", "left", "trunk"),
    ("suprarenal_gland_r", [8], "Right suprarenal (adrenal) gland", "right", "trunk"),
    ("suprarenal_gland_l", [9], "Left suprarenal (adrenal) gland", "left", "trunk"),
    ("lung_r", [12, 13, 14], "Right lung", "right", "trunk"),
    ("lung_l", [10, 11], "Left lung", "left", "trunk"),
    ("heart", [51], "Heart (four chambers and myocardium, blood-filled)", None, "trunk"),
    ("esophagus", [15], "Oesophagus", None, "trunk"),
    ("trachea", [16], "Trachea", None, "trunk"),
    ("thyroid_gland", [17], "Thyroid gland", None, "neck"),
    ("brain", [90], "Brain", None, "head"),
]
SRC_STRUCT = {"kidney_r": "kidney_right", "kidney_l": "kidney_left", "suprarenal_gland_r": "adrenal_gland_right",
              "suprarenal_gland_l": "adrenal_gland_left", "lung_r": "lung_{upper,middle,lower}_lobe_right",
              "lung_l": "lung_{upper,lower}_lobe_left"}

# Published reference volumes (cm3). kind: 'published' = a verified PubMed article; 'icrp' = ICRP Publication 89 (2002) reference
# organ mass / tissue density (numbers recalled, NOT re-checked against the document in this session); 'window' = no per-organ
# norm found, a plausibility window only (ratio not computed, no SIZE CAVEAT).
ICRP = "ICRP Publication 89 (2002), Ann ICRP 32(3-4), doi:10.1016/S0146-6453(03)00002-2, Table 2.8 reference adult organ masses / density"
REFS = {
    "liver": {"male": 1614.0, "female": 1360.0, "kind": "published",
              "src": "Vauthey 2002, Liver Transpl 8:233, doi:10.1053/jlts.2002.31654 (PMID 11910568): CT total liver volume = -794.41 + 1267.28 x BSA; "
                     "evaluated at BSA 1.9 (male) / 1.7 (female) m2 -- the specimens' height/weight were NOT looked up, so the reference is for a typical adult "
                     "of that sex (BSA 1.6-2.2 m2 spans 1,233-1,994 cm3)"},
    "spleen": {"male": 214.6, "female": 214.6, "kind": "published",
               "src": "Prassopoulos 1997, Eur Radiol 7:246, doi:10.1007/s003300050145 (PMID 9038125): CT splenic volume mean 214.6 cm3, range 107.2-314.5 (n=140; no sex/age dependence)"},
    "kidney_r": {"male": 148.0, "female": 131.0, "kind": "icrp", "src": ICRP + " (kidneys 310 g male / 275 g female, both, 1.05 g/cm3, halved); "
                 "method validated for CT volume in Heymsfield 1979, Ann Intern Med 90:185, doi:10.7326/0003-4819-90-2-185"},
    "pancreas": {"male": 133.0, "female": 113.0, "kind": "icrp", "src": ICRP + " (140 g / 120 g, 1.05)"},
    "suprarenal_gland_r": {"male": 6.7, "female": 6.2, "kind": "icrp", "src": ICRP + " (both 14 g / 13 g, 1.05, halved)"},
    "thyroid_gland": {"male": 19.0, "female": 16.0, "kind": "icrp", "src": ICRP + " (20 g / 17 g, 1.05)"},
    "brain": {"male": 1394.0, "female": 1250.0, "kind": "icrp", "src": ICRP + " (1450 g / 1300 g, 1.04)"},
    "heart": {"male": 800.0, "female": 650.0, "kind": "window",
              "src": "no verified whole-heart (myocardium + blood-filled chambers) volume norm found; ICRP 89 myocardium 330 g / 250 g plus chamber blood "
                     "gives a window of about 500-1100 cm3 -- ratio against 800 / 650 is indicative only"},
    "stomach": {"male": None, "female": None, "kind": "window", "window": [50.0, 1600.0],
                "src": "wall plus contents; volume is set by what was eaten (empty ~50 cm3 to ~1.5 L distended); plausibility window only"},
    "gallbladder": {"male": None, "female": None, "kind": "window", "window": [3.0, 80.0],
                    "src": "fasting contents 20-50 cm3, contracted a few cm3; plausibility window only"},
    "duodenum": {"male": None, "female": None, "kind": "window", "window": [15.0, 150.0], "src": "plausibility window (length ~25 cm, lumen 2-4 cm); no published norm used"},
    "small_bowel": {"male": None, "female": None, "kind": "window", "window": [300.0, 2500.0], "src": "plausibility window (content-dependent); no published norm used"},
    "colon": {"male": None, "female": None, "kind": "window", "window": [200.0, 2500.0],
              "src": "Pritchard 2014, Neurogastroenterol Motil 26:124, doi:10.1111/nmo.12243 (fasting MRI colon segments summing ~560 mL in volunteers); here the pelvic part is excluded; window only"},
    "lung_r": {"male": None, "female": None, "kind": "window", "window": [600.0, 4000.0],
               "src": "no verified CT lung-volume norm found; living total lung capacity is 4.5-7 L and CT volume varies by ~25 % of TLC with inspiration "
                      "(Vikgren 2003, Eur Radiol 13:1235, doi:10.1007/s00330-002-1643-4); a cadaver's lungs are collapsed -- window only"},
    "esophagus": {"male": None, "female": None, "kind": "window", "window": [15.0, 90.0], "src": "plausibility window (length ~25 cm, wall + lumen, ICRP 89 wall mass 40 g male); no published norm used"},
    "trachea": {"male": None, "female": None, "kind": "window", "window": [15.0, 80.0], "src": "plausibility window (length 10-12 cm, lumen 15-20 mm + wall); no published norm used"},
}
for a, b in (("kidney_l", "kidney_r"), ("suprarenal_gland_l", "suprarenal_gland_r"), ("lung_l", "lung_r")):
    REFS[a] = REFS[b]

ARTEFACT = {
    "lung_r": "post-mortem lung: the segmented air-containing lung of a cadaver, not a living inspiratory volume; the mediastinal pleura is not separated from the lobes",
    "lung_l": "post-mortem lung: the segmented air-containing lung of a cadaver, not a living inspiratory volume; the mediastinal pleura is not separated from the lobes",
    "stomach": "wall plus whatever the stomach held at death (food, fluid, gas)",
    "small_bowel": "loops, contents and gas as found at death; adjacent loops touch and are one label, individual loops are not separated",
    "colon": "the segments the model leaves unjoined are kept as separate pieces (each at least 5 % of the label); contents and gas as found at death; cut flat where the pelvic sigmoid starts (that part is the separate pelvic structure)",
    "duodenum": "contents as found at death",
    "heart": "label includes the blood-filled chambers and myocardium; the great vessels are not part of it",
    "esophagus": "collapsed tube, a few voxels across at the CT resolution",
    "trachea": "air lumen plus wall at the CT resolution",
    "brain": "post-mortem brain inside the skull, grey/white matter not separated",
    "gallbladder": "wall plus bile as found at death",
}


def sex_ref(rid, sex):
    r = REFS[rid]
    return r.get(sex), r


def load_total(body):
    import nibabel as nib
    img = nib.load(str(TASK / f"{body}_total.nii.gz"))
    return np.asarray(img.dataobj).astype(np.uint8), img.affine


def largest(mask, min_frac=None):
    """largest connected component (share of the label, pieces dropped); min_frac: keep EVERY piece of at least that share instead
    (the colon, whose segments the model leaves unjoined)"""
    from scipy import ndimage as ndi
    lab, n = ndi.label(mask)
    if n <= 1:
        return mask, [], 1.0
    sz = np.bincount(lab.ravel())[1:]
    k = int(sz.argmax()) + 1
    if min_frac:
        keep = [i + 1 for i, s in enumerate(sz) if s >= min_frac * sz.sum()]
        others = sorted((float(s) for i, s in enumerate(sz) if i + 1 not in keep), reverse=True)
        return np.isin(lab, keep), others, float(sz[np.array(keep) - 1].sum() / sz.sum())
    others = sorted((float(s) for i, s in enumerate(sz) if i + 1 != k), reverse=True)
    return lab == k, others, float(sz.max() / sz.sum())


def mc_at(field, level, pad):
    from skimage import measure
    v, f, _n, _v = measure.marching_cubes(field, level=level, step_size=1)
    return v - pad, f.astype(np.int64)


def mesh_volume_preserving(mask, target_cm3, vox_cm3, sigma=1.0):
    """marching cubes of Gaussian(sigma) field; level bisected so the closed mesh volume == voxel volume. Returns v (crop voxel coords), f, level."""
    from scipy.ndimage import gaussian_filter
    pad = int(np.ceil(3 * sigma)) + 1
    p = np.pad(mask.astype(np.float32), pad)
    fld = gaussian_filter(p, sigma)
    lo, hi = 0.12, 0.72
    best = None
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        if fld.max() <= mid:
            hi = mid
            continue
        v, f = mc_at(fld, mid, pad)
        mv = closed_vol_vox(v, f) * vox_cm3
        best = (v, f, mid, mv)
        if abs(mv - target_cm3) < 0.002 * target_cm3:
            break
        if mv > target_cm3:
            lo = mid
        else:
            hi = mid
    return best


def closed_vol_vox(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def drop_specks(v, f):
    import trimesh
    t = trimesh.Trimesh(v, f, process=False)
    lab = trimesh.graph.connected_component_labels(t.face_adjacency, node_count=len(f))
    if lab.max() == 0:
        return v, f, []
    vols = np.array([abs(trimesh.Trimesh(v, f[lab == i], process=False).volume) for i in range(lab.max() + 1)])
    keep = vols >= SPECK * vols.sum()
    f2 = f[keep[lab]]
    used = np.unique(f2)
    rm = np.full(len(v), -1, np.int64)
    rm[used] = np.arange(len(used))
    return v[used], rm[f2], [round(float(x) / 1000, 3) for x in vols[~keep]]


def edge_touch(kept, shape):
    idx = np.argwhere(kept)
    lo, hi = idx.min(0), idx.max(0)
    out = []
    for ax, nm in enumerate(("x", "y", "z")):
        if lo[ax] == 0:
            out.append(nm + ("_low" if ax < 2 else "_bottom"))
        if hi[ax] == shape[ax] - 1:
            out.append(nm + ("_high" if ax < 2 else "_top"))
    return out


def bone_depth_fraction(V, A, O, v_atlas, sp, thr=1.0):
    """fraction of vertices more than thr mm inside the body's own CT bone labels (EDT of the label mask, trilinear)"""
    from scipy import ndimage as ndi
    iv = to_vox(v_atlas, A, O)
    lo = np.maximum(np.floor(iv.min(0)).astype(int) - 8, 0)
    hi = np.minimum(np.ceil(iv.max(0)).astype(int) + 9, V.shape)
    m = np.isin(V[tuple(slice(a, b) for a, b in zip(lo, hi))], BONE)
    if not m.any():
        return 0.0, 0.0
    d = ndi.distance_transform_edt(m, sampling=sp) - 0.5 * float(min(sp))
    dv = ndi.map_coordinates(np.clip(d, 0, None), (iv - lo).T, order=1, mode="nearest")
    return float((dv > thr).mean()), float((dv > 0.0).mean())


def build(body, only=None):
    import nibabel as nib
    from scipy import ndimage as ndi
    cfg = BODY[body]
    sex = cfg["sex"]
    V, A = load_total(body)
    sp = np.sqrt((A[:3, :3] ** 2).sum(0))
    vox = float(abs(np.linalg.det(A[:3, :3]))) / 1000.0
    O = np.array([float(x) for x in ORIGIN[body].split(",")])
    skin = load_skin(body)
    pel = None
    if cfg["pelvic"].exists():
        P = np.asarray(nib.load(str(cfg["pelvic"])).dataobj)
        off = P.shape[2] - V.shape[2]
        pel = P[:, :, off:] if off > 0 else P
        assert pel.shape == V.shape, (pel.shape, V.shape)
    lab_out = np.zeros(V.shape, np.uint8)
    rows, meshes, regions = {}, {}, {}
    for k, (rid, labs, name, side, region) in enumerate(ORGANS, 1):
        if only and rid not in only:
            continue
        raw = np.isin(V, labs)
        r = {"labels": labs, "label_names": [TS[str(x)] for x in labs], "name": name, "side": side}
        if rid == "colon" and pel is not None:
            raw &= ~np.isin(pel, (2, 3))
            r["pelvic_part_removed"] = "TS colon minus the Q169/Q170 rectum + pelvic sigmoid voxels"
        n_raw = int(raw.sum())
        r["label_voxel_cm3"] = round(n_raw * vox, 2)
        if n_raw == 0:
            r.update(held=True, hold_reason="label empty in this body's `total` volume")
            rows[rid] = r
            continue
        idx = np.argwhere(raw)
        lo = np.maximum(idx.min(0) - 8, 0)
        hi = np.minimum(idx.max(0) + 9, V.shape)
        sl = tuple(slice(a, b) for a, b in zip(lo, hi))
        crop = raw[sl]
        kept, others, share = largest(crop, 0.05 if rid == "colon" else None)
        r["pieces_kept"] = int(ndi.label(kept)[1])
        kept = ndi.binary_fill_holes(kept)
        full_kept = np.zeros(V.shape, bool)
        full_kept[sl] = kept
        r["components_in_label"] = int(ndi.label(crop)[1])
        r["largest_component_share"] = round(share, 3)
        r["pieces_dropped_cm3"] = [round(x * vox, 3) for x in others[:8]]
        r["pieces_dropped_total_cm3"] = round(sum(others) * vox, 2)
        r["touches_array_edge"] = edge_touch(full_kept, V.shape)
        vcm = float(kept.sum()) * vox
        r["kept_voxel_cm3"] = round(vcm, 2)
        ref, rinfo = sex_ref(rid, sex)
        r["reference"] = {"kind": rinfo["kind"], "source": rinfo["src"], "value_cm3": ref, "window_cm3": rinfo.get("window")}
        if ref:
            ratio = vcm / ref
            r["ratio_to_reference"] = round(ratio, 2)
        else:
            ratio = None
            w = rinfo["window"]
            r["inside_window"] = bool(w[0] <= vcm <= w[1])
        hold = []
        if vcm < 1.0:
            hold.append("kept component under 1 cm3")
        if share < GATE["min_largest_share"]:
            hold.append(f"label fragmented: largest component is {share:.0%} of it (< {GATE['min_largest_share']:.0%})")
        if ratio is not None and ratio < GATE["min_ratio_to_reference"]:
            hold.append(f"under-segmented: {ratio:.2f}x the published reference (< {GATE['min_ratio_to_reference']}x)")
        if ratio is None and not r["inside_window"]:
            hold.append(f"volume {vcm:.0f} cm3 outside the plausibility window {rinfo['window']}")
        if hold:
            r.update(held=True, hold_reason="; ".join(hold))
            rows[rid] = r
            continue
        res = mesh_volume_preserving(kept, vcm, vox)
        v, f, level, mv = res
        v, f, specks = drop_specks(v, f)
        va = vol.voxels_to_atlas(v + lo, A) - O
        mvol = closed_volume_cm3(va, f)
        r.update(iso_level=round(level, 3), mesh_full_cm3=round(mvol, 2), mesh_vs_label=round(mvol / vcm, 4),
                 mesh_specks_dropped_cm3=specks, full_res_triangles=int(len(f)))
        r["position"] = {"bbox_min_mm": va.min(0).round(1).tolist(), "bbox_max_mm": va.max(0).round(1).tolist()}
        sub = np.arange(0, len(va), max(1, len(va) // 6000))
        r["outside_skin_frac"] = round(float((~skin.contains(va[sub])).mean()), 4)
        b1, b0 = bone_depth_fraction(V, A, O, va[sub], sp)
        r["in_bone_gt1mm_frac"], r["in_bone_any_frac"] = round(b1, 4), round(b0, 4)
        lab_out[full_kept] = k
        meshes[rid] = (va, f)
        regions[rid] = (lo, kept)
        rows[rid] = r
    # overlap between organ meshes' voxel interiors (the field regions are the label masks; compare the filled masks)
    ids = list(regions)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            (la, ka), (lb, kb) = regions[a], regions[b]
            lo_ = np.maximum(la, lb)
            hi_ = np.minimum(la + ka.shape, lb + kb.shape)
            if (hi_ <= lo_).any():
                continue
            sa = tuple(slice(x - o, y - o) for x, y, o in zip(lo_, hi_, la))
            sb = tuple(slice(x - o, y - o) for x, y, o in zip(lo_, hi_, lb))
            n = int((ka[sa] & kb[sb]).sum())
            if n:
                for x, y, kx in ((a, b, ka), (b, a, kb)):
                    fr = n / float(kx.sum())
                    cur = rows[x].setdefault("overlap_with_neighbours", {})
                    cur[y] = round(fr, 4)
    for rid, r in rows.items():
        if r.get("held"):
            continue
        ov = r.get("overlap_with_neighbours", {})
        r["max_overlap_frac"] = max(ov.values()) if ov else 0.0
        bad = []
        if r["outside_skin_frac"] > GATE["max_outside_skin_frac"]:
            bad.append(f"{100 * r['outside_skin_frac']:.1f} % of vertices outside the skin")
        if r["in_bone_gt1mm_frac"] > GATE["max_in_bone_frac"]:
            bad.append(f"{100 * r['in_bone_gt1mm_frac']:.1f} % of vertices > 1 mm inside bone labels (> 5 %)")
        if r["max_overlap_frac"] > GATE["max_overlap_frac"]:
            bad.append(f"overlaps a neighbouring organ by {100 * r['max_overlap_frac']:.1f} % (> 10 %)")
        if abs(r["mesh_vs_label"] - 1) > GATE["volume_tol"]:
            bad.append(f"mesh volume {r['mesh_vs_label']:.3f}x the label (> 3 %)")
        if bad:
            r.update(held=True, hold_reason="; ".join(bad))
            meshes.pop(rid, None)
        else:
            r["held"] = False
    write_subject(body, rows, meshes, lab_out, A)
    return rows


def badge(body, rid, r):
    cfg = BODY[body]
    labs = "+".join(str(x) for x in r["labels"])
    ratio = r.get("ratio_to_reference")
    ref = r["reference"]
    s = (f"Q193: measured on this body by automatic segmentation (TotalSegmentator v2.18 `total` task on {cfg['who']} CT, label {labs} "
         f"{'/'.join(r['label_names'])}), not hand-drawn; not checked by hand. Label volume {r['kept_voxel_cm3']} cm3")
    if ratio is not None:
        s += f" = {ratio:.2f}x the reference {ref['value_cm3']:g} cm3 ({ref['kind']}: {ref['source'].split(':')[0].split(' (')[0]})"
    else:
        s += f" (plausibility window {ref['window_cm3'][0]:g}-{ref['window_cm3'][1]:g} cm3, no published norm used)"
    s += (f". Largest connected piece of the label ({100 * r['largest_component_share']:.0f} % of it), holes filled, surface at the level that keeps "
          f"the label volume (mesh {r['mesh_vs_label']:.3f}x). Checked: {100 * r['outside_skin_frac']:.1f} % of vertices outside the skin, "
          f"{100 * r['in_bone_gt1mm_frac']:.1f} % more than 1 mm inside the CT bone labels, largest overlap with a neighbouring organ "
          f"{100 * r['max_overlap_frac']:.1f} %.")
    if rid in ARTEFACT:
        s += " Artefact: " + ARTEFACT[rid] + "."
    if cfg["frozen"]:
        s += " The specimen is a frozen cadaver (unenhanced CT)."
    else:
        s += " The specimen is an unfrozen cadaver (unenhanced CT)."
    if r["touches_array_edge"]:
        s += f" Clipped: the label touches the CT volume edge ({', '.join(r['touches_array_edge'])})."
    if ratio is not None and ratio > GATE["size_caveat_ratio"]:
        s += f" SIZE CAVEAT: {ratio:.1f}x the published reference volume ({ref['value_cm3']:g} cm3)."
    return s


def write_subject(body, rows, meshes, lab_out, A):
    import nibabel as nib
    cfg = BODY[body]
    sub = f"ct_{body}_viscera"
    d = REPO / "build" / "vh" / sub
    d.mkdir(parents=True, exist_ok=True)
    shipped = [o for o in ORGANS if o[0] in meshes]
    vb, fb, structs = [], [], []
    vbase = fbase = 0
    for rid, labs, name, side, region in shipped:
        v, f = meshes[rid]
        r = rows[rid]
        structs.append({"atlas_id": rid, "category": "organ", "name": name, "region": region,
                        "source_structure": SRC_STRUCT.get(rid, TS[str(labs[0])]), "side": side,
                        "source_file": f"{body}_viscera_q193.nii.gz#{[o[0] for o in ORGANS].index(rid) + 1}",
                        "vertex_offset": vbase, "face_offset": fbase, "vertex_count": int(len(v)), "triangle_count": int(len(f)),
                        "bbox_min_mm": v.min(0).round(2).tolist(), "bbox_max_mm": v.max(0).round(2).tolist(),
                        "procedural_badge": badge(body, rid, r)})
        vb.append(v.astype(np.float32))
        fb.append((f + vbase).astype(np.uint32))
        vbase += len(v)
        fbase += len(f)
    if not shipped:
        raise SystemExit("nothing passed")
    allv, allf = np.concatenate(vb), np.concatenate(fb)
    (d / "vertices.f32").write_bytes(allv.tobytes())
    (d / "faces.u32").write_bytes(allf.tobytes())
    out_nii = TASK / f"{body}_viscera_q193.nii.gz"
    img = nib.Nifti1Image(lab_out, A)
    img.set_data_dtype(np.uint8)
    nib.save(img, str(out_nii))
    (d / "manifest.json").write_text(json.dumps({
        "subject": sub, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
        "source_volume": str(out_nii.relative_to(REPO)), "source_kind": "labelled volume (NIfTI)",
        "label_map": f"{body}_viscera_q193 (label k = index in scripts/viscera_from_ct_labels_q193.py ORGANS; one per shipped organ)",
        "marching_cubes_step": 1, "surface_smoothing_sigma_voxels": 1.0, "vertex_count": int(len(allv)), "triangle_count": int(len(allf)),
        "bbox_min_mm": allv.min(0).round(4).tolist(), "bbox_max_mm": allv.max(0).round(4).tolist(),
        "attribution": [f"{cfg['title']} CT (U.S. National Library of Medicine, public domain, via the NCI Imaging Data Commons); "
                        "TotalSegmentator v2.18 `total` task labels (Apache-2.0); meshed by scripts/viscera_from_ct_labels_q193.py (Q193)."],
        "structures": structs}, indent=2))
    rep = {"task": "Q193", "body": body, "subject": sub, "script": "scripts/viscera_from_ct_labels_q193.py",
           "label_volume": str(out_nii.relative_to(REPO)), "origin_atlas_mm": [float(x) for x in ORIGIN[body].split(",")],
           "gates": GATE, "shipped": [o[0] for o in shipped], "held": {k: v["hold_reason"] for k, v in rows.items() if v.get("held")},
           "organs": rows}
    p = REPO / "data" / "derived" / f"Q193_viscera_{body}.json"
    p.write_text(json.dumps(rep, indent=1))
    print(f"wrote {d} and {p.relative_to(REPO)}")
    for k, v in rows.items():
        if v.get("held"):
            print(f"  HELD {k:20s} {v.get('kept_voxel_cm3', v['label_voxel_cm3']):8.1f} cm3: {v['hold_reason']}")
        else:
            print(f"  ship {k:20s} {v['kept_voxel_cm3']:8.1f} cm3  ratio {v.get('ratio_to_reference')}  skin {v['outside_skin_frac']}  bone {v['in_bone_gt1mm_frac']}  ov {v['max_overlap_frac']}")


def audit(body, bundle):
    """the same gates on the decimated meshes a bundle ships; also overlap with every other organ/vessel mesh of the bundle"""
    import trimesh
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    O = np.array([float(x) for x in ORIGIN[body].split(",")])
    V, A = load_total(body)
    sp = np.sqrt((A[:3, :3] ** 2).sum(0))
    vox = float(abs(np.linalg.det(A[:3, :3]))) / 1000.0
    skin = load_skin(body)
    rep = json.loads((REPO / "data" / "derived" / f"Q193_viscera_{body}.json").read_text())
    M = meshes_by_id(*read_bundle_dir(Path(bundle)))
    bj = json.loads((Path(bundle) / "bundle.json").read_text())
    subj = {e["id"]: e["subject"] for e in bj["structures"]}
    out = {}
    others = {i: m for i, m in M.items() if i not in rep["shipped"] and subj.get(i) not in (None, "ct_vhm_skin", "ct_vhf_skin")
             and i != "skin" and any(e["id"] == i and e["cat"] in ("organ", "vessel") for e in bj["structures"])}
    for rid in rep["shipped"]:
        if rid not in M:
            out[rid] = {"error": "not in bundle"}
            continue
        v, f = M[rid]["v"].astype(float), M[rid]["f"]
        t = trimesh.Trimesh(v, f, process=False)
        mv = closed_volume_cm3(v, f)
        b1, b0 = bone_depth_fraction(V, A, O, v, sp)
        lab = rep["organs"][rid]["kept_voxel_cm3"]
        row = {"triangles": int(len(f)), "mesh_cm3": round(mv, 2), "label_cm3": lab, "mesh_vs_label": round(mv / lab, 4),
               "outside_skin_frac": round(float((~skin.contains(v)).mean()), 4), "in_bone_gt1mm_frac": round(b1, 4),
               "watertight": bool(t.is_watertight), "components": int(len(t.split(only_watertight=False)))}
        ov = {}
        smp = v[:: max(1, len(v) // 3000)]
        for i, m in list(M.items()):
            if i == rid or i not in rep["shipped"] and i not in others:
                continue
            o = trimesh.Trimesh(m["v"].astype(float), m["f"], process=False)
            if not o.is_watertight:
                continue
            if (smp.min(0) > o.bounds[1]).any() or (smp.max(0) < o.bounds[0]).any():
                continue
            ins = o.contains(smp)
            if ins.any():
                dd = trimesh.proximity.closest_point(o, smp[ins])[1]
                ov[i] = (round(float(ins.mean()), 4), round(float((dd > 1.0).sum() / len(smp)), 4))
        ov = {k: x for k, x in ov.items() if x[0] > 0}
        # raw = surface vertices inside the neighbour at all (touching surfaces always give some); gate = more than 1 mm inside it
        row["vertices_inside_other_mesh_raw_and_gt1mm"] = ov
        row["max_overlap_frac"] = max([x[1] for x in ov.values()], default=0.0)
        row["pass"] = bool(row["outside_skin_frac"] <= GATE["max_outside_skin_frac"] and row["in_bone_gt1mm_frac"] <= GATE["max_in_bone_frac"]
                           and row["max_overlap_frac"] <= GATE["max_overlap_frac"] and abs(row["mesh_vs_label"] - 1) <= GATE["volume_tol"])
        out[rid] = row
        print(f"{rid:20s} tris {row['triangles']:6d} vol {row['mesh_vs_label']:.3f} skin {row['outside_skin_frac']} bone {row['in_bone_gt1mm_frac']} "
              f"ov>1mm {row['max_overlap_frac']} {ov} {'PASS' if row['pass'] else 'FAIL'}")
    rep["shipped_audit"] = {"bundle": str(bundle), "rows": out}
    (REPO / "data" / "derived" / f"Q193_viscera_{body}.json").write_text(json.dumps(rep, indent=1))
    return 0 if all(r.get("pass") for r in out.values()) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "audit"])
    ap.add_argument("--body", choices=sorted(BODY), required=True)
    ap.add_argument("--bundle")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.body, set(a.only) if a.only else None)
        return 0
    return audit(a.body, a.bundle)


if __name__ == "__main__":
    raise SystemExit(main())
