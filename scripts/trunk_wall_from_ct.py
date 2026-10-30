"""Diaphragm and intercostal sheets of BOTH Visible Human bodies, rule-based from each body's TotalSegmentator `total`
labels (Q62 step 6 of docs/MUSCLE_GAPS.md).

Usage: python3 scripts/trunk_wall_from_ct.py --body f|m   (the female "Normal" CT / the male frozen CT, torso grids
0.9375 x 0.9375 x 1 mm; writes data/ct_sources/task_outputs/vh{f,m}_trunk_wall.nii.gz (uint8, 1 diaphragm,
2 intercostals_right, 3 intercostals_left), _report.json, the three montage PNGs, mappings/vh{f,m}_trunk_wall_labels.json
and mappings/subjects/ct_vh{f,m}_twall_volume_mapping.json).

Rules (Gray's Anatomy 42nd ed., ch. 'Chest wall and breast' and 'Diaphragm and phrenic nerves'; Moore, Clinically
Oriented Anatomy 8th ed., ch. 'Thorax'):
  Diaphragm = the musculotendinous partition between the thoracic content T (lung lobes + heart) and the abdominal
  content A (liver, spleen, stomach, kidneys, adrenals, pancreas, duodenum, colon, small bowel, gallbladder, closed with
  a 15 mm ball so the peritoneal gaps BETWEEN viscera are not mistaken for it):
    D1 gap fill   : every voxel between T and closed-A where they are closer than 6 mm (the sheet is the whole gap);
    D2 apposition : a 4 mm shell on the surface of closed-A that FACES T (T within 20 mm) or FACES the rib cage (ribs,
                    costal cartilages, sternum within 10 mm; facing = the distance gradients point against each other)
                    -- the costal part / zone of apposition -- and never below the lowest rib of that column (costal margin);
    D3 lung base  : a 4 mm shell under downward-facing lung/heart surfaces that have no labelled viscus within 20 mm;
    D4 crura      : a shell (<= 6 mm) on the anterior 15 mm of the T12-L3 bodies (discs bridged) within 25 mm of the
                    aorta's centre, right of the aorta to L3, left of it to L2.
  Openings: the aorta (aortic hiatus, T12), oesophagus (T10) and IVC (T8) labels plus a 1.5 mm halo are punched out.
  Voxels inside any `total` label (organs, vessels, bones, psoas, autochthon) and inside the rib layer are never diaphragm.
  Thickness assumed: 4 mm total (Gray's: central tendon ~2 mm, muscular periphery 3-5 mm); where the labelled lung and
  liver are less than 6 mm apart the whole gap is taken.
  Intercostals = per side, the closing of that side's ribs + costal cartilages with a 40 mm ball minus the bone: the soft
  tissue between each pair of adjacent ribs from the rib neck to the costal cartilage, limited to the depth of the ribs
  (a 40 mm ball bridges a 20 mm space losing only ~1.3 mm of depth at mid-span; a 14 mm ball loses the whole band).
  External / internal / innermost layers (each 1-3 mm) cannot be separated on CT, so ONE sheet per side is shipped on
  external_intercostals_r/l and stands for all three layers (transversus thoracis and subcostales likewise unresolved,
  not shipped). Excluded: every other `total` label (lungs, vessels, organs), the erector columns and the shipped
  abdominal-wall muscle labels, the diaphragm, and on the FEMALE voxels outside the muscle window (-30..150 HU on the
  3x3x3-median CT, so the partial-volume rims at the ribs are not stripped); the
  male's frozen CT has shifted, overlapping HU (muscle median ~ -10, liver -11) so his sheets are geometric only.
Limits: rule-based textbook sheets, not segmentations; the frozen male has no left kidney / tiny right kidney and
adrenal labels, so his left posterior dome comes from D3 alone; the D2/D3 shells step by up to a few mm where the
labelled organs end; the intercostal band is the rib depth (5-10 mm) not the 3-6 mm of the three muscle layers.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parent.parent
SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
T_OUT = REPO / "data/ct_sources/task_outputs"


# ---------------------------------------------------------------- pure rule functions (unit-tested)
def dist_to(mask, spacing):
    """Euclidean distance (mm) of every voxel to the nearest True voxel of `mask` (inf-free: 0 inside the mask)."""
    if not mask.any():
        return np.full(mask.shape, np.inf, np.float32)
    return ndi.distance_transform_edt(~mask, sampling=spacing).astype(np.float32)


def closing(mask, spacing, r):
    """Morphological closing with a ball of radius r mm, by two distance transforms (padded so the array edge is open)."""
    pad = [int(np.ceil(r / s)) + 1 for s in spacing]
    m = np.pad(mask, [(p, p) for p in pad])
    dil = dist_to(m, spacing) <= r
    cl = dist_to(~dil, spacing) > r
    return cl[pad[0]:-pad[0], pad[1]:-pad[1], pad[2]:-pad[2]]


def _facing(d1, d2, spacing):
    """True where the two distance fields grow in opposite directions: the voxel lies BETWEEN the two feature sets."""
    dot = np.zeros(d1.shape, np.float32)
    for ax in range(3):
        dot += np.gradient(d1, spacing[ax], axis=ax).astype(np.float32) * np.gradient(d2, spacing[ax], axis=ax).astype(np.float32)
    return dot < 0


def diaphragm_dome(thoracic, abdominal, spacing, thickness=4.0, gap_fill=6.0, near_thorax=20.0,
                   cage=None, near_cage=10.0, close_r=15.0, floor=None):
    """The partition sheet between the thoracic and abdominal content (rules D1-D3 of the module docstring).
    floor: optional (nx, ny) array of the lowest z index allowed per column (the costal margin) for D2 and D3.
    Returns (mask, parts) with parts = {'gap_fill', 'apposition', 'lung_base'} masks; never inside either input."""
    abd_c = closing(abdominal, spacing, close_r) if close_r > 0 else abdominal
    d_t = dist_to(thoracic, spacing)
    d_a = dist_to(abd_c, spacing)
    free = ~thoracic & ~abd_c
    gap = free & (d_t + d_a <= gap_fill)
    shell = free & (d_a <= thickness)
    appo = shell & (d_t <= near_thorax) & _facing(d_a, d_t, spacing)
    if cage is not None and cage.any():
        d_c = dist_to(cage, spacing)
        appo |= shell & (d_c <= near_cage) & _facing(d_a, d_c, spacing)
        del d_c
    # downward-facing thoracic surface: d_t falls when moving up (gradient z-component below -0.5 = steeper than 30 deg)
    down = np.gradient(d_t, spacing[2], axis=2) < -0.5
    base = free & (d_t <= thickness) & (d_a > near_thorax) & down
    if floor is not None:
        above = np.arange(thoracic.shape[2])[None, None, :] >= floor[:, :, None]
        appo &= above
        base &= above
    parts = {"gap_fill": gap, "apposition": appo, "lung_base": base}
    return gap | appo | base, parts


def crura(vertebrae_by_level, aorta, spacing, ap_axis_sign, right_levels, left_levels, shell=6.0, half_width=25.0,
          anterior_depth=15.0):
    """Shell on the anterior `anterior_depth` mm of the vertebral bodies over the z range of the named levels (discs
    bridged by a z-closing), beside the aorta: right of it over right_levels, left of it over left_levels.
    vertebrae_by_level: {level: mask}; ap_axis_sign: -1 when the y index grows posteriorly. Returns a mask."""
    shape = aorta.shape
    vert = np.zeros(shape, bool)
    for m in vertebrae_by_level.values():
        vert |= m
    zr = {lv: np.where(m.any(axis=(0, 1)))[0] for lv, m in vertebrae_by_level.items() if m.any()}
    vert = ndi.binary_closing(vert, structure=np.ones((1, 1, int(round(16 / spacing[2])) | 1), bool))
    d_v = dist_to(vert, spacing)
    out = np.zeros(shape, bool)
    xs = np.arange(shape[0])[:, None]
    ys = np.arange(shape[1])[None, :]
    z_r = [zr[lv] for lv in right_levels if lv in zr]
    z_l = [zr[lv] for lv in left_levels if lv in zr]
    zr_lo, zr_hi = (min(z.min() for z in z_r), max(z.max() for z in z_r)) if z_r else (1, 0)
    zl_lo, zl_hi = (min(z.min() for z in z_l), max(z.max() for z in z_l)) if z_l else (1, 0)
    for k in range(min(zr_lo, zl_lo), max(zr_hi, zl_hi) + 1):
        sl = vert[:, :, k]
        if not sl.any():
            continue
        yy = np.where(sl)[1]
        y_front = yy.min() if ap_axis_sign < 0 else yy.max()
        ant = (ys < y_front + anterior_depth / spacing[1]) if ap_axis_sign < 0 else (ys > y_front - anterior_depth / spacing[1])
        ao = aorta[:, :, k]
        xa = np.where(ao)[0].mean() if ao.any() else np.where(sl)[0].mean()
        band = (d_v[:, :, k] > 0) & (d_v[:, :, k] <= shell) & ant
        lateral = np.abs(xs - xa) * spacing[0] <= half_width
        side_r = xs <= xa if ap_axis_sign < 0 else xs >= xa      # smaller x index = patient's right on this grid
        keep = np.zeros(sl.shape, bool)
        if zr_lo <= k <= zr_hi:
            keep |= side_r
        if zl_lo <= k <= zl_hi:
            keep |= ~side_r
        out[:, :, k] = band & lateral & keep
    return out


def intercostal_band(ribs_side, spacing, close_r=40.0):
    """Soft tissue between adjacent ribs (and costal cartilages) of one side, limited to the rib depth:
    closing of the bone with a `close_r` mm ball minus the bone itself (computed on the bone's bounding box)."""
    if not ribs_side.any():
        return np.zeros_like(ribs_side)
    sl = tuple(slice(int(w.min()), int(w.max()) + 1) for w in np.nonzero(ribs_side))
    out = np.zeros_like(ribs_side)
    out[sl] = closing(ribs_side[sl], spacing, close_r) & ~ribs_side[sl]
    return out


# ---------------------------------------------------------------- driver
def load_key(name):
    return {v: int(k) for k, v in json.load(open(REPO / f"mappings/{name}_labels.json"))["labels"].items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", choices=("f", "m"), required=True)
    args = ap.parse_args()
    import nibabel as nib
    b = args.body
    labs = load_key("totalsegmentator")
    im = nib.load(T_OUT / f"vh{b}_total.nii.gz")
    A = im.affine
    assert A[0, 0] < 0 and A[1, 1] < 0 and A[2, 2] > 0 and abs(A[0, 1]) + abs(A[1, 0]) < 1e-6, "expects the VH torso grid"
    sp = tuple(float(abs(A[i, i])) for i in range(3))
    vox_ml = float(np.prod(sp)) / 1000.0
    full = np.asarray(im.dataobj)
    ct_path = SCRATCH / f"vh_idc/nii/vh{b}_torso_0937.nii.gz"
    have_ct = ct_path.exists()
    ct = np.asarray(nib.load(ct_path).dataobj) if have_ct else None

    # crop: rib 1 top to L3 bottom, body bbox of the labels + margin
    def L(*names):
        return np.isin(full, [labs[n] for n in names if n in labs])
    zlo = int(np.where((full == labs["vertebrae_L3"]).any(axis=(0, 1)))[0].min()) - 5
    zhi = int(np.where((full == labs["rib_right_1"]).any(axis=(0, 1)))[0].max()) + 5
    cage_ids = [labs[n] for n in labs if n.startswith(("rib_", "vertebrae_", "costal_", "sternum"))]
    box = np.isin(full[:, :, zlo:zhi], cage_ids)
    xs = np.where(box.any(axis=(1, 2)))[0]; ys = np.where(box.any(axis=(0, 2)))[0]
    del box
    cx = slice(max(int(xs.min()) - 12, 0), int(xs.max()) + 13); cy = slice(max(int(ys.min()) - 12, 0), int(ys.max()) + 13)
    cz = slice(max(zlo, 0), min(zhi, full.shape[2]))
    t = full[cx, cy, cz].copy(); del full
    hu = ct[cx, cy, cz].astype(np.int16) if have_ct else None; del ct
    hu_s = ndi.median_filter(hu, size=3) if have_ct and b == "f" else hu
    shape = t.shape
    print("crop", shape, "spacing", sp, flush=True)

    def M(*names):
        return np.isin(t, [labs[n] for n in names if n in labs])
    lung_names = [n for n in labs if n.startswith("lung_")]
    thor = M(*lung_names, "heart")
    abd_names = ["liver", "spleen", "stomach", "kidney_right", "kidney_left", "adrenal_gland_right", "adrenal_gland_left",
                 "pancreas", "duodenum", "colon", "small_bowel", "gallbladder"]
    abd = M(*abd_names)
    rib_r = [f"rib_right_{i}" for i in range(1, 13)]; rib_l = [f"rib_left_{i}" for i in range(1, 13)]
    cart = M("costal_cartilages"); stern = M("sternum")
    x_mid = np.where(stern)[0].mean() if stern.any() else np.where(M("vertebrae_T8"))[0].mean()
    xs3 = np.arange(shape[0])[:, None, None]
    cart_r = cart & (xs3 < x_mid); cart_l = cart & (xs3 >= x_mid)          # x index grows to the patient's LEFT
    cage = M(*rib_r, *rib_l) | cart | stern

    # other muscle labels to keep out of the intercostal band
    other = np.zeros(shape, bool)
    extra = {"f": [("vhf_erector_columns", None), ("vhf_abdominal_muscles", None)],
             "m": [("vhm_erector_columns", None), ("vhm_hybrid_abdominal_muscles", [1, 2, 5, 6, 7, 8])]}[b]
    for fn, ids in extra:
        p = T_OUT / f"{fn}.nii.gz"
        if p.exists():
            v = np.asarray(nib.load(p).dataobj)[cx, cy, cz]
            other |= (v > 0) if ids is None else np.isin(v, ids)
            del v

    # ---- intercostal bands
    bands = {}
    for side, ribs, c in (("right", rib_r, cart_r), ("left", rib_l, cart_l)):
        bands[side] = intercostal_band(M(*ribs) | c, sp, 40.0)
    rib_layer = bands["right"] | bands["left"] | cage

    # ---- diaphragm
    # costal margin per column: the lowest cage voxel within 20 mm in-plane; columns with no cage are unrestricted
    zz = np.where(cage, np.arange(shape[2])[None, None, :], shape[2]).min(axis=2)
    zz[zz == shape[2]] = 0
    floor = ndi.minimum_filter(zz, size=int(round(40 / sp[0])) | 1)
    dome, parts = diaphragm_dome(thor, abd, sp, cage=cage, floor=floor)
    vert_levels = {n: M(n) for n in ("vertebrae_T12", "vertebrae_L1", "vertebrae_L2", "vertebrae_L3")}
    cr = crura(vert_levels, M("aorta"), sp, -1,
               right_levels={"vertebrae_T12", "vertebrae_L1", "vertebrae_L2", "vertebrae_L3"},
               left_levels={"vertebrae_T12", "vertebrae_L1", "vertebrae_L2"})
    if have_ct and b == "f":
        cr &= (hu_s >= -30) & (hu_s <= 150)
    dia = (dome | cr) & (t == 0) & ~rib_layer & ~other
    holes = dist_to(M("aorta", "esophagus", "inferior_vena_cava"), sp) <= 1.5
    dia &= ~holes
    if have_ct:
        dia &= hu > -500                                                   # never in air
    # keep the largest connected piece plus any piece over 2 cm3 (drops specks)
    lab, n = ndi.label(dia)
    if n > 1:
        sizes = ndi.sum(dia, lab, index=np.arange(1, n + 1)) * vox_ml
        dia = np.isin(lab, np.where(sizes >= 2.0)[0] + 1)
    del lab

    # ---- final bands: not bone/organ/other muscle, not diaphragm, (female) muscle window
    out = np.zeros(shape, np.uint8)
    out[dia] = 1
    for side, lid in (("right", 2), ("left", 3)):
        bd = bands[side] & (t == 0) & ~other & ~dia
        if have_ct and b == "f":
            bd &= (hu_s >= -30) & (hu_s <= 150)
        lab, n = ndi.label(bd)
        if n > 1:
            sizes = ndi.sum(bd, lab, index=np.arange(1, n + 1)) * vox_ml
            bd = np.isin(lab, np.where(sizes >= 0.5)[0] + 1)
        out[bd & (out == 0)] = lid

    vols = {name: round(float((out == i).sum()) * vox_ml, 1) for i, name in ((1, "diaphragm"), (2, "intercostals_right"), (3, "intercostals_left"))}
    partvol = {k: round(float((v & dia).sum()) * vox_ml, 1) for k, v in parts.items()}
    partvol["crura"] = round(float((cr & dia).sum()) * vox_ml, 1)
    # mean sheet thickness = volume / (boundary area / 2), boundary area from the voxel faces
    def mean_thickness(m):
        faces = sum(np.count_nonzero(np.diff(m, axis=ax)) * np.prod(sp) / sp[ax] for ax in range(3))
        return round(float(m.sum() * np.prod(sp) / (faces / 2.0)), 2) if faces else None
    col = dia.sum(axis=2)[thor.any(axis=2)]
    thick = {"mean_mm_volume_over_half_area": mean_thickness(dia), "intercostals_right_mean_mm": mean_thickness(out == 2),
             "intercostals_left_mean_mm": mean_thickness(out == 3),
             "columns_with_no_sheet_under_thorax_frac": round(float((col == 0).mean()), 3)}
    # crura reach
    zL = {n: int(np.where(m.any(axis=(0, 1)))[0].min()) for n, m in vert_levels.items() if m.any()}
    zcr = np.where((cr & dia).any(axis=(0, 1)))[0]
    reach = {"crura_lowest_slice": int(zcr.min()) if zcr.size else None, "L3_bottom_slice": zL.get("vertebrae_L3"),
             "L2_bottom_slice": zL.get("vertebrae_L2"), "L1_bottom_slice": zL.get("vertebrae_L1")}
    print("volumes cm3", vols, "parts", partvol, "thickness", thick, "crura", reach, flush=True)

    # ---- write volume on the full grid
    im2 = nib.load(T_OUT / f"vh{b}_total.nii.gz")
    fullout = np.zeros(im2.shape, np.uint8); fullout[cx, cy, cz] = out
    hdr = im2.header.copy(); hdr.set_data_dtype(np.uint8)
    nib.save(nib.Nifti1Image(fullout, im2.affine, hdr), T_OUT / f"vh{b}_trunk_wall.nii.gz")
    del fullout

    # ---- montages
    montage(b, t, hu, out, labs, sp, thor, cz)

    # ---- key, mapping, report
    body_name = {"f": "female fresh-cadaver 'Normal' CT", "m": "male frozen CT"}[b]
    src = ("U.S. National Library of Medicine, The Visible Human Project (public domain), " + body_name +
           " via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 `total` labels.")
    key = {"_README": [f"Label id -> structure name for the Visible Human {'FEMALE' if b == 'f' else 'MALE'} trunk-wall sheet "
                       "volume (scripts/trunk_wall_from_ct.py: diaphragm and intercostal sheets by geometric rules on the "
                       "`total` labels), plus the mapping onto atlas entities.",
                       "A KEY, not data. Rule-based: textbook sheets placed by distance rules, not segmentations; badge it. "
                       "The intercostal sheet stands for all three layers (external, internal, innermost) which CT cannot separate."],
           "source": src, "task": f"vh{b}_trunk_wall", "version": "2026-09-14",
           "labels": {"1": "diaphragm", "2": "intercostals_right", "3": "intercostals_left"},
           "atlas": {"diaphragm": {"atlas_id": "diaphragm", "relationship": "exact",
                                   "note": "4 mm sheet between the lung/heart and liver/spleen/stomach labels, costal part to the costal margin, crura on T12-L3; rule-based."},
                     "intercostals_right": {"atlas_id": "external_intercostals_r", "relationship": "part_of",
                                            "note": "ONE sheet for the external, internal and innermost intercostals of the right side (not separable on CT); rule-based."},
                     "intercostals_left": {"atlas_id": "external_intercostals_l", "relationship": "part_of",
                                           "note": "ONE sheet for the external, internal and innermost intercostals of the left side (not separable on CT); rule-based."}}}
    json.dump(key, open(REPO / f"mappings/vh{b}_trunk_wall_labels.json", "w"), indent=1)
    sub = f"ct_vh{b}_twall"
    entries = []
    for lid, name, side, aid, rel in ((1, "diaphragm", None, "diaphragm", "exact"),
                                      (2, "intercostals_right", "right", "external_intercostals_r", "part_of"),
                                      (3, "intercostals_left", "left", "external_intercostals_l", "part_of")):
        entries.append({"label": lid, "source_structure": name, "side": side, "status": "curated", "atlas_id": aid,
                        "relationship": rel, "note": f"{vols[name]} cm3; rule-based (see _README of the label key)" +
                        ("" if lid == 1 else "; one sheet standing for all three intercostal layers"), "candidates": []})
    json.dump({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                           "'status' is advisory; convert reads 'atlas_id' only."],
               "subject": sub, "source_volume": str(T_OUT / f"vh{b}_trunk_wall.nii.gz"), "label_map": f"vh{b}_trunk_wall",
               "entries": entries}, open(REPO / f"mappings/subjects/{sub}_volume_mapping.json", "w"), indent=1)
    dia_g = vols["diaphragm"] * 1.06; ic_g = (vols["intercostals_right"] + vols["intercostals_left"]) * 1.06
    report = {
        "_README": [f"Visible Human {'female' if b == 'f' else 'male'} diaphragm and intercostal sheets by geometric rules on the `total` labels "
                    "(scripts/trunk_wall_from_ct.py; rules and thicknesses in its docstring). Rule-based, derived data."],
        "source": src, "badge": "rule-based",
        "rules_source": "Gray's Anatomy 42nd ed., 'Chest wall and breast' and 'Diaphragm and phrenic nerves'; Moore, Clinically Oriented Anatomy 8th ed., 'Thorax'.",
        "thickness_assumed_mm": {"diaphragm": "4 (central tendon ~2, muscular periphery 3-5; whole gap taken where lung and liver labels are < 6 mm apart)",
                                 "intercostals": "the rib depth (closing of the ribs with a 40 mm ball), ~5-10 mm"},
        "thickness_measured_mm": thick,
        "hu_gating": ("female: intercostal band and crura kept only in the muscle window -30..150 HU" if b == "f" else
                      "none: the frozen male CT's HU are shifted and overlap (muscle median ~ -10 HU, liver -11), geometric rule only"),
        "volumes_cm3": vols, "diaphragm_parts_cm3": partvol, "crura_reach_slices": reach,
        "literature_comparison": {
            "diaphragm_mass_g_here": round(dia_g, 1), "diaphragm_mass_g_literature": "250-350 g adult total (task brief); 2-4 mm thick at end-expiration on ultrasound (Boon AJ et al., Muscle Nerve 2013;47:884-889, PMID 23625789)",
            "intercostal_mass_g_here": round(ic_g, 1), "intercostal_mass_g_literature": "200-300 g total (task brief)",
            "note": "A 4 mm sheet over a 300-400 cm2 dome gives 120-160 cm3 (130-170 g), below the 250-350 g autopsy mass, which weighs the thicker muscular periphery and crura; the sheet is thickness-faithful, not mass-faithful. Values differing from literature by more than 2x are explained in the report text."},
        "limits": ["Rule-based partition surfaces, not segmentations; steps of a few mm where labelled organs end.",
                   "One intercostal sheet per side stands for external+internal+innermost; transversus thoracis and subcostales not shipped.",
                   "Male: frozen CT, no left kidney and only fragments of the right kidney/adrenals labelled, so his posterior left dome rests on the lung-base rule alone; no HU gating."],
        "montages": [f"data/ct_sources/task_outputs/vh{b}_trunk_wall_{k}.png" for k in ("cor", "sag", "ax")],
    }
    json.dump(report, open(T_OUT / f"vh{b}_trunk_wall_report.json", "w"), indent=1)
    print("TW_DONE", flush=True)


def montage(b, t, hu, out, labs, sp, thor, cz):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([(0, 0, 0, 0), (1, 0.15, 0.15, 0.75), (0.2, 0.5, 1, 0.75), (0.2, 0.9, 0.3, 0.75)])
    win = (-250, 300)
    bg = hu if hu is not None else (t > 0).astype(np.int16) * 200

    def show(ax, img, lab, title, aspect):
        ax.imshow(img.T, cmap="gray", vmin=win[0], vmax=win[1], origin="lower", aspect=aspect)
        ax.imshow(lab.T, cmap=cmap, vmin=0, vmax=3, interpolation="nearest", origin="lower", aspect=aspect)
        ax.set_title(title, fontsize=9); ax.axis("off")

    def vz(name):
        m = t == labs[name]; z = np.where(m.any(axis=(0, 1)))[0]
        return int((z.min() + z.max()) // 2)
    # coronal through the lungs' centroid y, plus one 30 mm anterior and posterior
    yc = int(np.where(thor)[1].mean())
    fig, axs = plt.subplots(1, 3, figsize=(15, 6))
    for ax, y in zip(axs, (yc - int(30 / sp[1]), yc, yc + int(30 / sp[1]))):
        show(ax, bg[:, y, :][::-1], out[:, y, :][::-1], f"vh{b} coronal y={y} (viewer's left = patient's right)", sp[2] / sp[0])
    fig.tight_layout(); fig.savefig(T_OUT / f"vh{b}_trunk_wall_cor.png", dpi=110); plt.close(fig)
    # sagittal midline (vertebral x) and parasagittal +-70 mm
    xm = int(np.where(t == labs["vertebrae_T10"])[0].mean())
    fig, axs = plt.subplots(1, 3, figsize=(15, 6))
    for ax, x, name in zip(axs, (xm - int(70 / sp[0]), xm, xm + int(70 / sp[0])), ("right parasagittal", "midline", "left parasagittal")):
        show(ax, bg[x, :, :][::-1], out[x, :, :][::-1], f"vh{b} sagittal {name} x={x} (viewer's left = anterior)", sp[2] / sp[1])
    fig.tight_layout(); fig.savefig(T_OUT / f"vh{b}_trunk_wall_sag.png", dpi=110); plt.close(fig)
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.5))
    for ax, name in zip(axs, ("vertebrae_T8", "vertebrae_T10", "vertebrae_L1")):
        k = vz(name)
        show(ax, bg[:, :, k][:, ::-1], out[:, :, k][:, ::-1], f"vh{b} axial {name[10:]} slice {k + cz.start} (top = anterior, viewer's left = patient's right)", sp[1] / sp[0])
    fig.tight_layout(); fig.savefig(T_OUT / f"vh{b}_trunk_wall_ax.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
