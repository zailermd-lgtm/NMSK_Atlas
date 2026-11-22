"""Q286: two open TotalSegmentator tasks never run in this project, on the Visible Human bodies' own CT, meshed and gated.

    python3 scripts/anatomy/q286/ct_tasks_q286.py head  vhm|vhf SEG.nii.gz HEAD_CT.nii.gz
    python3 scripts/anatomy/q286/ct_tasks_q286.py spine vhm|vhf SEG.nii.gz TORSO_CT.nii.gz

head: `head_glands_cavities` (v2.18.0, Apache-2.0) on the body's head-and-neck grid (the grid of data/ct_sources/task_outputs/
<body>_craniofacial_structures.nii.gz, stacked from the same IDC series by scripts/stack_dicom_series.py).
spine: `vertebrae_body` (v2.18.0, Apache-2.0; classes vertebrae_body, intervertebral_discs) on the torso grid (= <body>_total.nii.gz).

Shipping policy (stated in the report, not tuned per class):
  * air spaces (nasopharynx, oropharynx, hypopharynx, nasal cavities, auditory canals) are not shipped: the project has never shipped an
    air-space label (larynx_air, the paranasal sinuses stayed out) -- they are the lumen, not a tissue;
  * hard palate is not shipped: it is part of the maxillae / palatine bones the page already carries in its skull (measured overlap reported);
  * vertebral bodies are not shipped: each is a part of a whole vertebra the page already carries from the same CT (`total` task);
  * intervertebral discs replace ONLY the levels the Q185c endplate rebuild held (old Q104 cylinders, or nothing); every other level keeps
    its Q185c mesh (equal source class: this body's own CT) and is compared, not replaced;
  * optic nerve: on the male page the shipped optic_n is TRANSFERRED from the female (xfer_vhf2vhm), so his own CT nerves replace it; on the
    female page optic_n is already from her own CT (ct_vhf_orbit) and is kept, compared.
Gates (a failing structure is held): largest connected piece >= 85 %; touches no edge of its grid; mesh volume within 3 % of the label;
0 % of vertices more than 1 mm outside the page's skin; <= 5 % of vertices more than 1 mm inside this body's CT bone labels (discs: 2 %,
the Q185c gate); soft-tissue HU: >= 90 % of voxels in [-200, 300] HU (no air, no bone); boundary contrast |median HU inside - median HU in a
2-voxel shell| >= 5 HU (below that the frozen CT shows no edge to segment); paired organs: left/right difference <= 50 % of their mean
(a 2-3x difference means one side was not found, not anatomy); where a cited adult value exists, the volume is within 0.5-2x of it
(sex-matched); eyeballs: within 0.8-1.25x of the same body's eyeball from the earlier `oculomotor_muscles` task (two models of the same
organ on the same CT must agree before either is believed). Discs also keep Q185c's size check against its own published
bands. Reported, not gated: volumes against cited adult values where a value was verified, left/right asymmetry, overlap with neighbouring labels.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
from engine import volume_ingest as vol  # noqa: E402
from scripts.ribs_from_ct_labels import ORIGIN, TASK, to_vox  # noqa: E402
from scripts.costal_cartilage_from_ct_labels import BONE  # noqa: E402
from scripts.viscera_from_ct_labels_q193 import largest, mesh_volume_preserving, drop_specks, edge_touch, closed_vol_vox  # noqa: E402

BUNDLE = {"vhm": "build/q286_pre/bundle_own_m", "vhf": "build/q285_pre/bundle_own_f"}
SUBJ = {("vhm", "head"): "ct_vhm_hgc", ("vhf", "head"): "ct_vhf_hgc", ("vhm", "spine"): "ct_vhm_disc_ts", ("vhf", "spine"): "ct_vhf_disc_ts"}
TA = "Terminologia Anatomica (FICAT 1998); Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell)"
# class -> (shipped id, name, latin, cat, folder, budget, cited reference or None)
PAROTID_REF = {"cite": "Brzoska T, Ittermann T, Ihler F, et al. Population Based Average Parotid Gland Volume and Prevalence of Incidental "
                       "Tumors in T1-MRI. Healthcare (Basel) 2022;10(11):2310 (SHIP, 1725 MRI scans)", "doi": "10.3390/healthcare10112310",
               "pmid": "36421635", "mean_cm3": {"m": 27.82, "f": 21.60}, "what": "mean single-side parotid volume"}
HEAD = {
    "parotid_gland_right": ("parotid_gland_r", "Parotid gland (right)", "Glandula parotidea dextra", "organ", "glands", 6000, PAROTID_REF),
    "parotid_gland_left": ("parotid_gland_l", "Parotid gland (left)", "Glandula parotidea sinistra", "organ", "glands", 6000, PAROTID_REF),
    "submandibular_gland_right": ("submandibular_gland_r", "Submandibular gland (right)", "Glandula submandibularis dextra", "organ", "glands", 4000, None),
    "submandibular_gland_left": ("submandibular_gland_l", "Submandibular gland (left)", "Glandula submandibularis sinistra", "organ", "glands", 4000, None),
    "eye_right": ("eyeball_r", "Eyeball (right)", "Bulbus oculi dexter", "organ", "eye", 4000, None),
    "eye_left": ("eyeball_l", "Eyeball (left)", "Bulbus oculi sinister", "organ", "eye", 4000, None),
    "eye_lens_right": ("lens_r", "Lens (right)", "Lens dextra", "organ", "eye", 1500, None),
    "eye_lens_left": ("lens_l", "Lens (left)", "Lens sinistra", "organ", "eye", 1500, None),
    "soft_palate": ("soft_palate", "Soft palate", "Palatum molle", "organ", "mouth", 4000, None),
    "optic_nerve_right": ("optic_n", "Optic nerve (CN II)", "Nervus opticus", "nerve", "nerves", 3000, None),
    "optic_nerve_left": ("optic_n", "Optic nerve (CN II)", "Nervus opticus", "nerve", "nerves", 3000, None),
}
AIR = ["nasopharynx", "oropharynx", "hypopharynx", "nasal_cavity_right", "nasal_cavity_left", "auditory_canal_right", "auditory_canal_left"]
GATE = {"min_largest_share": 0.85, "volume_tol": 0.03, "max_outside_skin_gt1mm_frac": 0.0, "max_in_bone_frac": 0.05, "max_in_bone_frac_disc": 0.02,
        "min_soft_hu_frac": 0.90, "min_boundary_contrast_hu": 5.0, "max_pair_asymmetry_pct": 50.0, "cited_ratio": [0.5, 2.0],
        "eye_vs_oculomotor_ratio": [0.8, 1.25]}
LEVELS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12", "L1", "L2", "L3",
          "L4", "L5", "S1"]


def names(task):
    from_ts = REPO / "mappings" / ("totalsegmentator_labels.json" if task == "total" else f"totalsegmentator_{task}_labels.json")
    return {int(k): v for k, v in json.loads(from_ts.read_text())["labels"].items()}


def load(p):
    import nibabel as nib
    im = nib.load(str(p)); return np.asarray(im.dataobj), im.affine


def skin_mesh(body):
    from scripts.transfer.q200_bundle import Bundle
    import trimesh
    s = Bundle(REPO / BUNDLE[body]).get("skin"); return trimesh.Trimesh(s["v"], s["f"], process=False)


def skin_distance(skin, pts):
    import trimesh
    inside = skin.contains(pts)
    d = trimesh.proximity.ProximityQuery(skin).on_surface(pts)[1]
    return np.where(inside, -d, d)


def depth_in(mask_full, A, O, v_atlas, sp, thr=1.0):
    """fraction of vertices more than thr mm inside mask_full (EDT, trilinear) -- same method as Q193's bone_depth_fraction"""
    from scipy import ndimage as ndi
    iv = to_vox(v_atlas, A, O)
    lo = np.maximum(np.floor(iv.min(0)).astype(int) - 8, 0)
    hi = np.minimum(np.ceil(iv.max(0)).astype(int) + 9, mask_full.shape)
    m = mask_full[tuple(slice(a, b) for a, b in zip(lo, hi))]
    if not m.any():
        return 0.0
    d = ndi.distance_transform_edt(m, sampling=sp) - 0.5 * float(min(sp))
    dv = ndi.map_coordinates(np.clip(d, 0, None), (iv - lo).T, order=1, mode="nearest")
    return float((dv > thr).mean())


def hu_stats(ct, m):
    from scipy import ndimage as ndi
    hu = ct[m]
    shell = ndi.binary_dilation(m, iterations=2) & ~m
    return {"median": float(np.median(hu)), "p10": float(np.percentile(hu, 10)), "p90": float(np.percentile(hu, 90)),
            "soft_frac_-200_300": round(float(((hu >= -200) & (hu <= 300)).mean()), 4),
            "shell_median": float(np.median(ct[shell])), "boundary_contrast": round(abs(float(np.median(hu)) - float(np.median(ct[shell]))), 1)}


def mesh_one(m, ct, A, O, vox_cm3, sp, skin, bone, budget, bone_gate):
    from scipy import ndimage as ndi
    from export_viewer_bundle import decimate_guarded
    r = {"label_voxel_cm3": round(float(m.sum()) * vox_cm3, 3)}
    k, others, share = largest(m)
    k = ndi.binary_fill_holes(k)
    r["largest_component_share"] = round(share, 4); r["pieces_dropped_cm3"] = [round(o * vox_cm3, 3) for o in others[:6]]
    r["kept_voxel_cm3"] = round(float(k.sum()) * vox_cm3, 3)
    r["edge_touch"] = edge_touch(k, k.shape)
    r["hu"] = hu_stats(ct, k)
    idx = np.argwhere(k); lo, hi = idx.min(0), idx.max(0)
    crop = tuple(slice(max(a - 4, 0), b + 5) for a, b in zip(lo, hi))
    v, f, level, mv = mesh_volume_preserving(k[crop], r["kept_voxel_cm3"], vox_cm3, sigma=1.0)
    v, f, specks = drop_specks(v, f)
    v = v + np.array([s.start for s in crop])
    va = vol.voxels_to_atlas(v, A) - O
    mvol = closed_vol_vox(v, f) * vox_cm3
    r.update(mesh_full_cm3=round(mvol, 3), mesh_vs_label=round(mvol / r["kept_voxel_cm3"], 4), full_triangles=int(len(f)))
    dec = decimate_guarded(va, f, budget)
    vd, fd = (dec if dec is not None else (va, f))
    r["shipped_triangles"] = int(len(fd))
    sd = skin_distance(skin, vd)
    r["outside_skin_gt1mm_frac"] = round(float((sd > 1.0).mean()), 4); r["outside_skin_max_mm"] = round(float(sd.max()), 2)
    r["in_bone_gt1mm_frac"] = round(depth_in(bone, A, O, vd, sp), 4)
    r["bbox_atlas_mm"] = [np.round(vd.min(0), 1).tolist(), np.round(vd.max(0), 1).tolist()]
    bad = []
    if share < GATE["min_largest_share"]:
        bad.append(f"fragmented (largest piece {100 * share:.0f} %)")
    if r["edge_touch"]:
        bad.append("touches the grid edge: " + ",".join(r["edge_touch"]))
    if abs(r["mesh_vs_label"] - 1) > GATE["volume_tol"]:
        bad.append(f"mesh volume {r['mesh_vs_label']:.3f}x the label")
    if r["outside_skin_gt1mm_frac"] > GATE["max_outside_skin_gt1mm_frac"]:
        bad.append(f"{100 * r['outside_skin_gt1mm_frac']:.1f} % of vertices > 1 mm outside the skin")
    if r["in_bone_gt1mm_frac"] > bone_gate:
        bad.append(f"{100 * r['in_bone_gt1mm_frac']:.1f} % of vertices > 1 mm inside bone")
    if r["hu"]["soft_frac_-200_300"] < GATE["min_soft_hu_frac"]:
        bad.append(f"only {100 * r['hu']['soft_frac_-200_300']:.0f} % of voxels in the soft-tissue HU range")
    if r["hu"]["boundary_contrast"] < GATE["min_boundary_contrast_hu"]:
        bad.append(f"boundary contrast {r['hu']['boundary_contrast']} HU (no visible edge)")
    return r, bad, (vd, fd)


def head(body, seg_p, ct_p):
    seg, A = load(seg_p); ct, A2 = load(ct_p)
    cf, A3 = load(TASK / f"{body}_craniofacial_structures.nii.gz")
    assert np.allclose(A, A2) and np.allclose(A, A3) and seg.shape == ct.shape == cf.shape, "not on the craniofacial grid"
    oc, _ = load(TASK / f"{body}_oculomotor_muscles.nii.gz"); hm, _ = load(TASK / f"{body}_head_muscles.nii.gz")
    N = names("head_glands_cavities"); inv = {v: k for k, v in N.items()}
    CF = names("craniofacial_structures"); OC = names("oculomotor_muscles"); HM = names("head_muscles")
    bone = np.isin(cf, [k for k, v in CF.items() if v in ("mandible", "skull", "teeth_lower", "teeth_upper")])
    vox = float(abs(np.linalg.det(A[:3, :3]))) / 1000.0; sp = tuple(float(x) for x in np.linalg.norm(A[:3, :3], axis=0))
    O = np.array([float(x) for x in ORIGIN[body].split(",")]); skin = skin_mesh(body)
    rep = {"_README": ["Q286 head_glands_cavities on this body's own head CT; see scripts/anatomy/q286/ct_tasks_q286.py for method, policy and gates."],
           "body": body, "grid": "head-and-neck grid of " + f"{body}_craniofacial_structures.nii.gz", "gates": GATE, "classes": {}, "shipped": [], "held": {},
           "not_shipped_by_policy": {}}
    meshes = {}
    for a in AIR:
        m = seg == inv[a]
        rep["not_shipped_by_policy"][a] = {"reason": "air space (lumen), not a tissue; the project ships no air-space label",
                                           "label_voxel_cm3": round(float(m.sum()) * vox, 2)}
    m = seg == inv["hard_palate"]
    rep["not_shipped_by_policy"]["hard_palate"] = {"reason": "part of the maxillae / palatine bones already in this body's skull mesh",
                                                   "label_voxel_cm3": round(float(m.sum()) * vox, 2),
                                                   "frac_inside_skull_label": round(float((m & bone).sum() / max(m.sum(), 1)), 3)}
    nerve_parts = []
    for cls, (sid, name, latin, cat, folder, budget, ref) in HEAD.items():
        m = seg == inv[cls]
        if not m.any():
            rep["held"][cls] = ["empty label"]; continue
        if cls.startswith("optic_nerve"):
            nerve_parts.append((cls, m)); continue
        r, bad, (vd, fd) = mesh_one(m, ct, A, O, vox, sp, skin, bone, budget, GATE["max_in_bone_frac"])
        ovl = {}
        for lab, nm in ((oc, OC), (hm, HM)):
            u, c = np.unique(lab[m & (lab > 0)], return_counts=True)
            ovl.update({nm[int(x)]: round(float(y) / m.sum(), 4) for x, y in zip(u, c)})
        r["overlap_existing_labels"] = ovl
        if cls in ("eye_right", "eye_left"):
            o = oc == {v: k for k, v in OC.items()}["eyeball_" + cls.split("_")[1]]
            r["oculomotor_task_eyeball_cm3"] = round(float(o.sum()) * vox, 3)
            r["ratio_to_oculomotor_eyeball"] = round(r["kept_voxel_cm3"] / max(r["oculomotor_task_eyeball_cm3"], 1e-6), 2)
            r["dice_vs_oculomotor_eyeball"] = round(2 * float((m & o).sum()) / max(float(m.sum() + o.sum()), 1.0), 3)
            lo_, hi_ = GATE["eye_vs_oculomotor_ratio"]
            if not (lo_ <= r["ratio_to_oculomotor_eyeball"] <= hi_):
                bad.append(f"{r['kept_voxel_cm3']:.1f} cm3 = {r['ratio_to_oculomotor_eyeball']:.2f}x the eyeball of the oculomotor_muscles task "
                           f"on the same CT (Dice {r['dice_vs_oculomotor_eyeball']:.2f}): the two models disagree")
        if ref:
            r["reference"] = ref
        rep["classes"][cls] = r
        if bad:
            rep["held"][sid] = bad
        else:
            rep["shipped"].append(sid); meshes[sid] = dict(v=vd, f=fd, name=name, latin=latin, cat=cat, folder=folder, cls=cls,
                                                            side=("right" if cls.endswith("right") else "left" if cls.endswith("left") else None))
    # optic nerve: both sides in ONE mesh (the atlas entity optic_n is unsided); male page only (his is transferred from her)
    if nerve_parts:
        m = np.zeros(seg.shape, bool)
        for _, p in nerve_parts:
            m |= p
        u, c = np.unique(oc[m & (oc > 0)], return_counts=True)
        per = {}
        for cls, p in nerve_parts:
            rr, bb, _ = mesh_one(p, ct, A, O, vox, sp, skin, bone, 1500, GATE["max_in_bone_frac"])
            per[cls] = {"r": rr, "bad": bb}
        old = (oc == {v: k for k, v in OC.items()}["optic_nerve_left"]) | (oc == {v: k for k, v in OC.items()}["optic_nerve_right"])
        dice = 2 * float((m & old).sum()) / max(float(m.sum() + old.sum()), 1.0)
        rep["optic_nerve"] = {"sides": {k: v["r"] for k, v in per.items()}, "side_gate_fails": {k: v["bad"] for k, v in per.items() if v["bad"]},
                              "dice_vs_oculomotor_task_optic_nerve": round(dice, 3), "oculomotor_task_cm3": round(float(old.sum()) * vox, 3)}
        if body == "vhm" and not any(v["bad"] for v in per.values()):
            vs, fs, off = [], [], 0
            for cls, p in nerve_parts:
                _, _, (vd, fd) = mesh_one(p, ct, A, O, vox, sp, skin, bone, 1500, GATE["max_in_bone_frac"])
                vs.append(vd); fs.append(fd + off); off += len(vd)
            meshes["optic_n"] = dict(v=np.vstack(vs), f=np.vstack(fs), name="Optic nerve (CN II)", latin="Nervus opticus", cat="nerve",
                                     folder="nerves", cls="optic_nerve_left+right", side="left", replace=True)
            rep["shipped"].append("optic_n (replaces the transferred xfer_vhf2vhm optic_n)")
        elif body == "vhf":
            rep["optic_nerve"]["kept_existing"] = "optic_n on Imaging F is already from her own CT (ct_vhf_orbit, TotalSegmentator oculomotor_muscles) -- kept"
        else:
            rep["held"]["optic_n"] = [f"{k}: {v}" for k, v in rep["optic_nerve"]["side_gate_fails"].items()]
    sex = "m" if body == "vhm" else "f"
    for a in ("parotid_gland", "submandibular_gland", "eye", "eye_lens"):
        rr, ll = rep["classes"].get(a + "_right"), rep["classes"].get(a + "_left")
        if rr and ll:
            x, y = rr["kept_voxel_cm3"], ll["kept_voxel_cm3"]
            asym = round(100 * abs(x - y) / (0.5 * (x + y)), 1)
            rep.setdefault("asymmetry_pct_of_mean", {})[a] = asym
            if asym > GATE["max_pair_asymmetry_pct"]:
                for side in ("right", "left"):
                    sid = HEAD[a + "_" + side][0]
                    rep["held"].setdefault(sid, []).append(f"left/right difference {asym:.0f} % of the mean (one side not found)")
        for side in ("right", "left"):
            r = rep["classes"].get(a + "_" + side); sid = HEAD[a + "_" + side][0]
            if r and r.get("reference"):
                ratio = r["kept_voxel_cm3"] / r["reference"]["mean_cm3"][sex]; r["ratio_to_cited_mean"] = round(ratio, 2)
                if not (GATE["cited_ratio"][0] <= ratio <= GATE["cited_ratio"][1]):
                    rep["held"].setdefault(sid, []).append(f"{r['kept_voxel_cm3']:.1f} cm3 = {ratio:.2f}x the cited sex-matched mean")
    for sid in list(meshes):
        if sid in rep["held"]:
            meshes.pop(sid); rep["shipped"] = [s for s in rep["shipped"] if s != sid]
    return rep, meshes


def spine(body, seg_p, ct_p):
    from scipy import ndimage as ndi
    seg, A = load(seg_p); ct, A2 = load(ct_p)
    tot_name = "vhf_total_q185k" if body == "vhf" else "vhm_total"
    tot, A3 = load(TASK / f"{tot_name}.nii.gz")
    assert np.allclose(A, A2) and np.allclose(A, A3) and seg.shape == tot.shape
    TS = names("total"); TS[118] = "vertebrae_L1B"
    vox = float(abs(np.linalg.det(A[:3, :3]))) / 1000.0; sp = tuple(float(x) for x in np.linalg.norm(A[:3, :3], axis=0))
    O = np.array([float(x) for x in ORIGIN[body].split(",")]); skin = skin_mesh(body)
    bone = np.isin(tot, BONE); lung = np.isin(tot, [k for k, v in TS.items() if v.startswith("lung")])
    q185c = json.loads((REPO / f"data/derived/Q185c_discs_{body}.json").read_text())
    held = [k for k, v in q185c["levels"].items() if v.get("status") != "pass"]
    vert = {v.replace("vertebrae_", ""): k for k, v in TS.items() if v.startswith("vertebrae_")}
    order = [l for l in LEVELS if l in vert and (tot == vert[l]).any()]
    if body == "vhf" and (tot == 118).any():           # her sixth rib-free presacral vertebra (Q185k), between L1 and L2
        order.insert(order.index("L1") + 1, "L1B"); vert["L1B"] = 118
    cz = {l: float(np.argwhere(tot == vert[l])[:, 2].mean()) for l in order}
    disc = seg == 2
    body_vox = seg == 1
    rep = {"_README": ["Q286 vertebrae_body on this body's own torso CT; see scripts/anatomy/q286/ct_tasks_q286.py."], "body": body, "gates": GATE,
           "q185c_held_levels": held, "levels": {}, "shipped": [], "held": {},
           "vertebral_bodies": {"label_cm3": round(float(body_vox.sum()) * vox, 1),
                                "frac_inside_existing_vertebra_labels": round(float((body_vox & bone).sum() / max(body_vox.sum(), 1)), 4),
                                "not_shipped": "each vertebral body is part of a whole vertebra the page already carries from the same CT (total task)"}}
    lab, n = ndi.label(disc)
    comps = ndi.find_objects(lab)
    meshes = {}
    by_level = {}
    for i, sl in enumerate(comps, 1):
        cm = lab[sl] == i
        if cm.sum() * vox < 0.05:
            continue
        zc = float(np.argwhere(cm)[:, 2].mean()) + sl[2].start
        for a, b in zip(order[:-1], order[1:]):
            lo_, hi_ = sorted((cz[a], cz[b]))
            if lo_ <= zc <= hi_:
                key = "intervertebral_disc_" + (a + "_" + b).lower()
                by_level.setdefault(key, []).append((i, sl)); break
    for key, parts in by_level.items():
        m = np.zeros(seg.shape, bool)
        for i, sl in parts:
            m[sl] |= lab[sl] == i
        r = {"label_voxel_cm3": round(float(m.sum()) * vox, 3), "q185c_status": q185c["levels"].get(key, {}).get("status", "absent"),
             "q185c_volume_cm3": q185c["levels"].get(key, {}).get("volume_cm3"), "q185c_shipped": q185c["levels"].get(key, {}).get("shipped")}
        if key in held:
            rr, bad, (vd, fd) = mesh_one(m, ct, A, O, vox, sp, skin, bone, 3000, GATE["max_in_bone_frac_disc"])
            r.update(rr)
            r["lung_gt1mm_frac"] = round(depth_in(lung, A, O, vd, sp), 4)
            if r["lung_gt1mm_frac"] > 0:
                bad.append(f"{100 * r['lung_gt1mm_frac']:.1f} % of vertices > 1 mm inside lung")
            idx = np.argwhere(m) * np.array(sp)
            r["width_mm"] = round(float(np.ptp(idx[:, 0])), 1); r["depth_mm"] = round(float(np.ptp(idx[:, 1])), 1)
            cols = m.sum(2); r["height_median_mm"] = round(float(np.median(cols[cols > 0])) * sp[2], 1)
            band = q185c["levels"][key].get("size_vs_published", {})
            sz = {}
            for dim, val in (("width", r["width_mm"]), ("depth", r["depth_mm"]), ("height", r["height_median_mm"])):
                if dim in band:
                    lo_, hi_ = band[dim]["ref"]; tol = q185c.get("reference_tolerance", 0.0)
                    if dim == "height":
                        tol_lo = q185c.get("reference_tolerance_height_low", tol)
                    else:
                        tol_lo = tol
                    ok = (lo_ * (1 - tol_lo)) <= val <= (hi_ * (1 + tol))
                    sz[dim] = {"mm": val, "ref": [lo_, hi_], "ok": bool(ok)}
                    if not ok:
                        bad.append(f"{dim} {val} mm outside the Q185c published band {lo_}-{hi_} mm (tolerance {tol})")
            r["size_vs_published"] = sz
            if bad:
                rep["held"][key] = bad
            else:
                rep["shipped"].append(key)
                a, b = key.replace("intervertebral_disc_", "").upper().split("_")
                meshes[key] = dict(v=vd, f=fd, name=f"{a}-{b} intervertebral disc", latin=f"Discus intervertebralis ({a}-{b})", cat="cartilage",
                                   folder="cartilage", cls="intervertebral_discs", side=None, replace=True)
        rep["levels"][key] = r
    for k in held:
        if k not in by_level:
            rep["held"][k] = ["the vertebrae_body task found no disc component at this level"]
    return rep, meshes


def badge(body, kind, sid, r, extra=""):
    who = "his" if body == "vhm" else "her"
    task = "head_glands_cavities" if kind == "head" else "vertebrae_body"
    s = (f"Q286: measured on this body by automatic segmentation (TotalSegmentator v2.18 `{task}` task on {who} own CT), not hand-drawn; "
         f"not checked by hand. Label volume {r['kept_voxel_cm3']:.2f} cm3; largest connected piece {100 * r['largest_component_share']:.0f} %; "
         f"surface at the level that keeps the label volume (mesh {r['mesh_vs_label']:.3f}x). HU median {r['hu']['median']:.0f}, boundary contrast "
         f"{r['hu']['boundary_contrast']:.0f} HU against a 2-voxel shell. Checked: {100 * r['outside_skin_gt1mm_frac']:.1f} % of vertices more than "
         f"1 mm outside the skin, {100 * r['in_bone_gt1mm_frac']:.1f} % more than 1 mm inside {who} CT bone labels.")
    if r.get("reference"):
        ref = r["reference"]; s += (f" For comparison (not a range for {who}): {ref['what']} {ref['mean_cm3']['m']:.1f} cm3 (men) / "
                                    f"{ref['mean_cm3']['f']:.1f} cm3 (women), {ref['cite'].split('.')[0]} et al., doi:{ref['doi']}.")
    if body == "vhm":
        s += " The male specimen was CT-scanned frozen: soft-tissue boundaries are weaker than in a living or fresh body."
    return s + extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["head", "spine"]); ap.add_argument("body", choices=["vhm", "vhf"])
    ap.add_argument("seg"); ap.add_argument("ct")
    a = ap.parse_args()
    rep, meshes = (head if a.kind == "head" else spine)(a.body, a.seg, a.ct)
    subj = SUBJ[(a.body, a.kind)]
    out = REPO / "build/vh" / subj; out.mkdir(parents=True, exist_ok=True)
    import trimesh
    items = []
    for sid, d in meshes.items():
        trimesh.Trimesh(d["v"], d["f"], process=False).export(out / f"{sid}.obj")
        if a.kind == "head" and sid != "optic_n":
            r = rep["classes"][d["cls"]]
        elif sid == "optic_n":
            sides = rep["optic_nerve"]["sides"]; r = dict(next(iter(sides.values())))
            r["kept_voxel_cm3"] = sum(v["kept_voxel_cm3"] for v in sides.values())
        else:
            r = rep["levels"][sid]
        extra = ""
        if sid == "optic_n":
            extra = (f" Both nerves in one mesh (the atlas entity is unsided); replaces the optic nerve transferred from the female. Dice with "
                     f"his own oculomotor-task optic nerve label {rep['optic_nerve']['dice_vs_oculomotor_task_optic_nerve']:.2f}.")
        if a.kind == "spine":
            sz = "; ".join(f"{d} {s['mm']} mm (published {s['ref'][0]}-{s['ref'][1]} mm)" for d, s in r.get("size_vs_published", {}).items())
            extra = ((" Replaces the procedural Q104 cylinder that stood here: the Q185c endplate rebuild held this level (its size fell outside "
                      "the published band)." if r.get("q185c_shipped") == "old_q104_held" else
                      " Fills a level that had no disc on this page: the Q185c endplate rebuild held it (its size fell outside the published band).")
                     + f" Size on this mesh: {sz}; {100 * r.get('lung_gt1mm_frac', 0):.0f} % of vertices inside lung.")
        rec = {"name": d["name"], "latin": d["latin"], "folder": d["folder"], "region": "head" if a.kind == "head" else "spine",
               "source": f"Own CT (NLM Visible Human Project, public domain), TotalSegmentator v2.18.0 `{'head_glands_cavities' if a.kind == 'head' else 'vertebrae_body'}` task (Apache-2.0); {TA}",
               "procedural_badge": badge(a.body, a.kind, sid, r, extra)}
        items.append({"id": sid, "cat": d["cat"], "side": d["side"], "rec": rec, "obj": f"{sid}.obj", "replace": bool(d.get("replace"))})
    (out / "items.json").write_text(json.dumps(items, indent=1))
    rp = REPO / "data/derived" / f"Q286_{a.body}_{a.kind}_report.json"
    rp.write_text(json.dumps(rep, indent=1))
    print("shipped", rep["shipped"]); print("held", json.dumps(rep["held"], indent=0)[:3000])


if __name__ == "__main__":
    main()
