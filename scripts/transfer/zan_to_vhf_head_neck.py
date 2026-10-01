"""Q62 step 7: the VH FEMALE's missing head / neck / larynx muscles, TRANSFERRED from Z-Anatomy onto her own skull,
mandible, hyoid, cervical spine and (larynx) her own CT thyroid + cricoid cartilages.

Same route as Q62 step 5 (zan_to_vhf_foot_intrinsics.py, whose gate helpers this reuses): Z-Anatomy (CC BY-SA 4.0)
objects carried by the Q168 per-bone fits (`zan_to_vhf_whole_body.load_zan_to_vhf`), then measured and fixed:
  carrier  Q168 piece residuals of the Z-Anatomy bones each muscle rides on (rides_on, axial units) AND a LOCAL
           measured error: Z-Anatomy bone surface within LOCAL_MM of the muscle, carried by its own piece fit,
           distance to her CT bone surface. Larynx: Z-Anatomy thyroid + cricoid cartilages vs HER CT cartilage labels
           (TotalSegmentator headneck_bones_vessels 2/4), after one extra similarity refit of those two cartilages
           onto hers (LARYNX_REFIT; the refit carries the larynx group). Group held if its pooled local median > 3 mm;
           a single muscle held if its own local median > 3 mm.
  bone     vertices inside her cranium / mandible / hyoid / cervical+thoracic spine / sternum / clavicles /
           scapulae / ribs / thyroid + cricoid cartilage: bounded push-out (<= PUSH_BOUND_MM deep -> surface + 1 mm),
           > MAX_INSIDE_BONE still inside -> held.
  skin     her ct_vhf_skin: fraction outside before; pull_inside_skin (nearest skin point + 0.5 mm); 0 % after.
           Thin facial sheets: a muscle whose skin pull moves > MAX_SKIN_MOVED of its vertices, or whose volume
           after the fixes falls below MIN_VOL_KEPT of the transferred volume, is HELD (deformed, not fitted).
  airway   vertices inside her air lumen (larynx_air label + trachea label + CT air < -400 HU inside her body,
           slices above the lungs, lung labels excluded -- so also nasal cavity, sinuses, mastoid air cells; her
           cadaver pharynx is mostly collapsed on CT): > MAX_IN_AIRWAY -> held.
  overlap  vertices inside her existing bundle muscles (any subject) + her tongue / oesophagus / thyroid-gland labels,
           plus the EXCESS over Z-Anatomy's own overlap of vertices inside the other new muscles (facial muscles
           interdigitate in the source itself): > MAX_OVERLAP -> held.
Only ids with NO mesh in her bundle (Q62 step 7 coverage list, NOT_MAPPED gives why the rest are not built).
Output subject xfer_zan2vhf_head (xfer_: never counted as her own mesh), report data/derived/Q62s7_vhf_head_neck.json.
Q62 step 7b: `--target vhm` runs the same gates on the VH MALE (Q168 fits onto HIS skeleton,
data/derived/Q168_zan_to_vhm.json; his CT labels/HU) -> xfer_zan2vhm_head, data/derived/Q62s7b_vhm_head_neck.json;
platysma r/l is added for him (he has no platysma; she does). Texts say "his" for him; her output is unchanged.

    python3 scripts/transfer/zan_to_vhf_head_neck.py [--target vhm] [--out build/vh/xfer_zan2vhf_head] [--dry]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.transfer import zan_to_vhf_whole_body as Z  # noqa: E402
from scripts.transfer import zan_to_vhf_foot_intrinsics as FT  # noqa: E402

SUBJECT = "xfer_zan2vhf_head"
REPORT = REPO / "data" / "derived" / "Q62s7_vhf_head_neck.json"
TASK = REPO / "data" / "ct_sources" / "task_outputs"
CT_HU = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_idc/nii/"
             "vhf_torso_0937.nii.gz")   # her CT (same grid as vhf_total); optional: without it the airway = labels only
ORIGIN = "7.769,-885.229,14.137"        # vhf_rebuild_bundle.sh's $O (ingest_volume_geometry inspect vhf_total)
MAX_INSIDE_BONE = 0.05
MAX_OUTSIDE_SKIN_PRECLIP = 0.5
MAX_CARRIER_MM = 3.0
MAX_OVERLAP = 0.10
MAX_IN_AIRWAY = 0.05
MAX_SKIN_MOVED = 0.25        # thin-sheet rule: more than this share of vertices dragged by the skin pull -> held
MIN_VOL_KEPT = 0.75          # ... or the fixes leave less than this share of the transferred volume -> held
LOCAL_MM = 15.0
AIR_HU = -400
LARYNX_MAX_ROT_DEG, LARYNX_SCALE_TOL = 20.0, 0.25
# Q62 step 7b: his frozen CT (IDC 5d409385, mixed 0.94/0.78/0.53 mm FOV blocks) resampled onto his vhm_total grid
# (`--stack-ct DICOM_DIR` writes it); without it the airway = labels only
CT_HU_VHM = CT_HU.parent / "vhm_torso_0937.nii.gz"
TARGETS = {
    "vhf": {"subject": SUBJECT, "report": REPORT, "bundle": Z.FEMALE_BUNDLE_JSON, "q168": Z.DEFAULT_REPORT,
            "prefix": "vhf", "ct": CT_HU, "origin": ORIGIN, "air_z_min": 700, "extra": {}, "step": "7"},
    # his origin: vhm_rebuild_bundle.sh's torso-block origin (ct_vhm_neck, ct_vhm_abw); air_z_min: first slice above
    # his lung labels (vhm_total 10-14 end at slice 551)
    "vhm": {"subject": "xfer_zan2vhm_head", "report": REPO / "data" / "derived" / "Q62s7b_vhm_head_neck.json",
            "bundle": Z.MALE_BUNDLE_JSON, "q168": Z.MALE_REPORT, "prefix": "vhm", "ct": CT_HU_VHM,
            "origin": "-6.035,-895.476,4.787", "air_z_min": 552,
            "extra": {"facial_expression": ["platysma_r", "platysma_l"]}, "step": "7b",
            # his bundle's skull/mandible/spine/girdle/ribs are the meshes recovered from his published viewer
            # (decimated, NOT watertight: cranium 5.6 k vertices in 1405 pieces) -> containment is unreliable. The
            # gates and the local carrier error use the same bones re-meshed from his CT labels instead (TotalSegmentator
            # craniofacial_structures / total; bundle -> label surface 0.24-0.35 mm median, i.e. the same bone).
            # The Q168 fit itself stays on the bundle meshes. Hyoid: his bundle mesh is watertight, kept.
            "ct_bones": {"cranium": ("craniofacial_structures", [3]), "mandible": ("craniofacial_structures", [1]),
                         "cervical_vertebrae": ("total", list(range(44, 51))),
                         "thoracic_vertebrae": ("total", list(range(32, 44))), "sternum": ("total", [116]),
                         "clavicle_r": ("total", [74]), "clavicle_l": ("total", [73]),
                         "scapula_r": ("total", [72]), "scapula_l": ("total", [71]),
                         "ribs_r": ("total", list(range(104, 116))), "ribs_l": ("total", list(range(92, 104)))}},
}


def ct_bone_meshes(target: str, origin: np.ndarray) -> dict:
    """{atlas id: trimesh} re-meshed from the target's own CT labels (TARGETS[target]['ct_bones']; empty for her)"""
    import nibabel as nib
    from scripts.vhf_pelvic_viscera import mesh_mask
    cfg = TARGETS[target]; out, cache = {}, {}
    for aid, (task, labs) in cfg.get("ct_bones", {}).items():
        if task not in cache:
            img = nib.load(TASK / f"{cfg['prefix']}_{task}.nii.gz"); cache[task] = (img.affine, np.asarray(img.dataobj))
        A, arr = cache[task]
        v, f = mesh_mask(np.isin(arr, labs), A, origin, smooth=1.0)
        out[aid] = trimesh.Trimesh(v, f, process=False)
    return out


def pron(text, target: str = "vhf"):
    """her -> his for the male run (identity for her, so her subject/report text never changes)"""
    if target == "vhf" or text is None:
        return text
    for a, b in ((r"segmented from her\b", "segmented from him"), (r"\bher\b", "his"), (r"\bHER\b", "HIS"), (r"\bshe\b", "he"), (r"VH female", "VH male"),
                 (r"Q62 step 7:", "Q62 step 7b:"), (r"zanatomy -> vhf", "zanatomy -> vhm"),
                 (r"zan_to_vhf_whole_body\)", "zan_to_vhf_whole_body --target vhm)")):
        text = re.sub(a, b, text)
    return text

_S = "rl"
GROUPS = {
    "facial_expression": [f"{b}_{s}" for b in (
        "depressor_anguli_oris", "depressor_labii_inferioris", "depressor_septi_nasi", "frontalis",
        "levator_anguli_oris", "levator_labii_superioris", "mentalis", "nasalis", "orbicularis_oculi",
        "orbicularis_oris", "risorius", "zygomaticus_major", "zygomaticus_minor") for s in _S] + ["procerus"],
    "pharynx_palate": [f"{b}_{s}" for b in ("superior_pharyngeal_constrictor", "palatopharyngeus",
                                             "stylopharyngeus") for s in _S],
    "hyoid_strap": [f"{b}_{s}" for b in ("stylohyoid", "omohyoid", "sternohyoid") for s in _S],
    "larynx": [f"{b}_{s}" for b in ("cricothyroid", "lateral_cricoarytenoid", "posterior_cricoarytenoid",
                                     "thyroarytenoid", "oblique_arytenoid") for s in _S] + ["transverse_arytenoid"],
    "deep_neck": [f"{b}_{s}" for b in ("rectus_capitis_anterior", "rectus_capitis_lateralis", "splenius_capitis",
                                        "splenius_cervicis") for s in _S],
}
GROUP_OF = {a: g for g, ids in GROUPS.items() for a in ids}
# atlas id -> Z-Anatomy mesh ids (matched ids are the atlas id itself in the Z-Anatomy build; these come from its
# orphan pool, names given). Thyroarytenoid = TA's external + thyro-epiglottic parts (its internal part = vocalis
# has no Z-Anatomy object); oblique arytenoid = its aryepiglottic part only (the only Z-Anatomy object).
ORPHAN = {**{f"lateral_cricoarytenoid_{s}": [f"zan_lateral_crico_arytenoid_muscle_{s}"] for s in _S},
          **{f"posterior_cricoarytenoid_{s}": [f"zan_posterior_crico_arytenoid_muscle_{s}"] for s in _S},
          **{f"thyroarytenoid_{s}": [f"zan_external_part_of_thyro_arytenoid_muscle_{s}",
                                     f"zan_thyro_epiglottic_part_of_thyro_arytenoid_muscle_{s}"] for s in _S},
          **{f"oblique_arytenoid_{s}": [f"zan_ary_epiglottic_part_of_oblique_arytenoid_muscle_{s}"] for s in _S},
          **{f"splenius_cervicis_{s}": [f"zan_splenius_colli_muscle_{s}"] for s in _S}}
PARTIAL_NOTE = {**{f"oblique_arytenoid_{s}": "aryepiglottic part only (Z-Anatomy has no separate oblique belly)"
                   for s in _S},
                **{f"thyroarytenoid_{s}": "external + thyro-epiglottic parts; vocalis (internal part) not in Z-Anatomy"
                   for s in _S}}
LARYNX_CARTILAGES = ["zan_thyroid_cartilage", "zan_cricoid_cartilage"]
# head_and_neck ids missing from her bundle (2026-10-01) that are NOT built, and why
_NO_ZAN = "no CC BY-SA Z-Anatomy object of this name (inventory searched by name; not in the shipped source)"
NOT_MAPPED = {
    **{f"{b}_{s}": _NO_ZAN for s in _S for b in (
        "antitragicus", "auricularis_anterior", "auricularis_posterior", "auricularis_superior", "buccinator",
        "helicis_major", "helicis_minor", "levator_veli_palatini", "obliquus_auriculae", "palatoglossus",
        "salpingopharyngeus", "stapedius", "tensor_tympani", "tensor_veli_palatini", "tragicus",
        "transversus_auriculae", "vocalis")},
    "musculus_uvulae": _NO_ZAN + " ('Uvula of palate' is the organ, not the muscle)",
    **{f"depressor_supercilii_{s}": _NO_ZAN + " (Z-Anatomy has corrugator supercilii, a different muscle)"
       for s in _S},
    **{f"occipitofrontalis_{s}": "Z-Anatomy splits it: frontal belly ships as frontalis_<s>; the occipital belly "
       "(zan_occipitalis_muscle_<s>) alone is not the whole entity -- not built rather than mislabelled" for s in _S},
    **{f"{b}_{s}": "Z-Anatomy has one 'Tongue' organ object, no separate intrinsic tongue muscles"
       for s in _S for b in ("inferior_longitudinal_tongue", "transverse_tongue", "vertical_tongue")},
    "superior_longitudinal_tongue": "Z-Anatomy has one 'Tongue' organ object, no separate intrinsic tongue muscles",
}
# her bones the muscles may not sit inside (her ids; cartilages added from her CT labels at run time)
HER_BONES = ["cranium", "mandible", "hyoid", "cervical_vertebrae", "thoracic_vertebrae", "sternum", "clavicle_r",
             "clavicle_l", "scapula_r", "scapula_l", "ribs_r", "ribs_l"]
# published adult volumes (cm3), only where a value could be read; everything else: none found (report says so)
PUBLISHED = {
    "orbicularis_oculi": {"value_cm3": 2.992, "what": "MRI (3T, 1 mm) mean of both sides, healthy adults n=10, "
                          "23-43 y", "ref": "Volk GF et al. Plast Reconstr Surg Glob Open 2014;2(6):e173. "
                          "doi:10.1097/GOX.0000000000000128 (value from the text; its Table 1 could not be read)"},
    "procerus": {"value_cm3": 0.0808, "what": "MRI mean (identified in 4/10)", "ref": "Volk 2014, as above"},
    "splenius_capitis": {"value_cm3": None, "her_own_cm3": {"r": 79.0, "l": 68.1},
                         "what": "HER OWN cryosection compartment splenius capitis + cervicis (ct_vhf_dneck labels 1/11, "
                                 "not shipped: no septum between the two) -- compare with capitis + cervicis summed"},
    "sternohyoid": {"value_cm3": None, "her_own_cm3": {"r": 2.7},
                    "what": "HER OWN fragmented cryosection label (ct_vhf_hyoid label 1, 24 islands, not shipped)"},
    "omohyoid": {"value_cm3": None, "her_own_cm3": {"r": 3.8},
                 "what": "HER OWN fragmented cryosection label (ct_vhf_hyoid label 2, 13 islands, not shipped)"},
}
PUBLISHED_NOTE = ("Other facial muscle volumes: Volk 2014 Table 1 (not readable here). Intrinsic laryngeal muscle volumes: "
                  "Chen T et al. J Voice 2012;26(5):555-62 (doi:10.1016/j.jvoice.2011.03.012, micro-MRI of one 68-year-old "
                  "woman's larynx) report them, but only the abstract was readable -- no value. Pharyngeal / strap / "
                  "deep-neck: none found. Z-Anatomy meshes are generic and partly include aponeurosis.")


def groups_for(target: str = "vhf") -> dict:
    extra = TARGETS[target]["extra"]
    return {g: ids + extra.get(g, []) for g, ids in GROUPS.items()}


def targets(target: str = "vhf") -> list[str]:
    return [a for ids in groups_for(target).values() for a in ids]


def zan_parts(aid: str) -> list[str]:
    return ORPHAN.get(aid, [aid])


def to_vox(pts_atlas: np.ndarray, affine: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """inverse of engine.volume_ingest.voxels_to_atlas(.) - origin: atlas mm -> voxel index (float)"""
    p = np.asarray(pts_atlas, np.float64) + origin
    ras = np.stack([p[:, 0], p[:, 2], p[:, 1]], axis=1)
    return (np.linalg.inv(affine) @ np.c_[ras, np.ones(len(ras))].T)[:3].T


class MaskLookup:
    """point-in-voxel-mask test in her atlas frame (nearest voxel)"""

    def __init__(self, mask: np.ndarray, affine: np.ndarray, origin: np.ndarray):
        self.m, self.A, self.O = mask.astype(bool), affine, origin

    def __call__(self, pts: np.ndarray) -> np.ndarray:
        ijk = np.rint(to_vox(pts, self.A, self.O)).astype(int)
        ok = np.all((ijk >= 0) & (ijk < np.array(self.m.shape)), axis=1)
        out = np.zeros(len(pts), bool)
        out[ok] = self.m[ijk[ok, 0], ijk[ok, 1], ijk[ok, 2]]
        return out


def airway_mask(hb: np.ndarray, tot: np.ndarray, ct: np.ndarray | None, z_min: int = 700) -> np.ndarray:
    """larynx_air (headneck_bones_vessels 1) + trachea (total 16) + CT air (< AIR_HU) inside her body outline
    (per axial slice, holes filled) in slices >= z_min, lung labels (total 10-14) excluded."""
    from scipy import ndimage as ndi
    m = (hb == 1) | (tot == 16)
    if ct is not None:
        lung = (tot >= 10) & (tot <= 14)
        for z in range(z_min, ct.shape[2]):
            sl = ct[:, :, z]
            body = ndi.binary_fill_holes(sl > AIR_HU)
            m[:, :, z] |= (sl < AIR_HU) & body & ~lung[:, :, z]
    return m


def her_label_meshes(origin: np.ndarray, target: str = "vhf"):
    """her (his) CT thyroid + cricoid cartilage surfaces and the airway / organ lookups"""
    import nibabel as nib
    from scripts.vhf_pelvic_viscera import mesh_mask
    cfg = TARGETS[target]; px = cfg["prefix"]
    hbi = nib.load(TASK / f"{px}_headneck_bones_vessels.nii.gz"); hb = np.asarray(hbi.dataobj)
    toti = nib.load(TASK / f"{px}_total.nii.gz"); tot = np.asarray(toti.dataobj)
    hmi = nib.load(TASK / f"{px}_head_muscles.nii.gz"); hm = np.asarray(hmi.dataobj)
    ct = np.asarray(nib.load(cfg["ct"]).dataobj) if Path(cfg["ct"]).exists() else None
    cart = {}
    for name, lab in (("thyroid_cartilage", 2), ("cricoid_cartilage", 4)):
        v, f = mesh_mask(hb == lab, hbi.affine, origin, smooth=1.0)
        t = trimesh.Trimesh(v, f, process=True); t.fix_normals()
        cart[name] = t
    air = airway_mask(hb, tot, ct, z_min=cfg["air_z_min"])
    looks = {"airway": MaskLookup(air, toti.affine, origin),
             "tongue": MaskLookup(hm == 9, hmi.affine, origin),
             "oesophagus": MaskLookup(tot == 15, toti.affine, origin),
             "thyroid_gland": MaskLookup(tot == 17, toti.affine, origin)}
    vox_cm3 = float(abs(np.linalg.det(toti.affine[:3, :3]))) / 1000.0
    info = {"airway_voxels": int(air.sum()), "airway_cm3": round(air.sum() * vox_cm3, 1),
            "airway_ct_air_used": ct is not None,
            "cartilage_cm3": {k: round(abs(t.volume) / 1000, 2) for k, t in cart.items()}}
    return cart, looks, info


def larynx_refit(xf, items: dict, cart: dict) -> dict:
    """Z-Anatomy thyroid + cricoid cartilages carried by Q168, then one similarity refit onto HER CT cartilages.
    Returns {'A','t', before/after symmetric distances}; identity if the refit breaks the rotation/scale guard."""
    src = np.vstack([xf(c, "bone", items[c]["v"]) for c in LARYNX_CARTILAGES])
    hv = np.vstack([Z.sample_surface(t.vertices, t.faces, 6000, seed=3) for t in cart.values()])
    sv = Z._sub(src, 6000, 4)
    ht = cKDTree(hv)

    def sym(p):   # symmetric nearest-point distances, Z-Anatomy cartilage <-> hers
        return np.concatenate([ht.query(p)[0], cKDTree(p).query(hv)[0]])
    before = sym(sv)
    A, t = Z.trimmed_icp(sv, hv, np.eye(3), np.zeros(3), scale=True, corr="sym")
    s = Z.sim_scale(A); rot = Z.rot_angle_deg(A / s)
    ok = abs(s - 1) <= LARYNX_SCALE_TOL and rot <= LARYNX_MAX_ROT_DEG
    extra = {}
    if not ok and rot <= LARYNX_MAX_ROT_DEG:
        # Q62 step 7b: the similarity broke only the SCALE guard (his CT cartilage labels are 1.7-1.9x Z-Anatomy's
        # volume: TotalSegmentator cartilage is blobby) -> rigid refit at the carried scale, same rotation guard
        # (never reached for her: her similarity was accepted)
        Ar, tr = Z.trimmed_icp(sv, hv, np.eye(3), np.zeros(3), scale=False, corr="sym")
        rr = Z.rot_angle_deg(Ar)
        extra = {"mode": "rigid (similarity rejected: scale %.3f)" % s, "rigid_rot_deg": round(float(rr), 1)}
        if rr <= LARYNX_MAX_ROT_DEG:
            A, t, ok = Ar, tr, True
    if not ok:
        A, t = np.eye(3), np.zeros(3)
    after = sym(Z.apply_sim(A, t, sv))
    return {"A": A, "t": t, "accepted": bool(ok), "scale": round(float(s), 3), "rot_deg": round(float(rot), 1),
            "before": before, "after": after, **extra}


def local_carrier_error(xf, v_src: np.ndarray, her_tree: cKDTree, refit=None) -> dict:
    """Z-Anatomy axial bone surface within LOCAL_MM of the muscle (source frame), carried by its own piece fit,
    -> distance to her bone surface. The bone-fit error measured where this muscle attaches/lies."""
    mt = cKDTree(Z._sub(v_src, 3000, 5))
    d_all = []
    for name, pts in zip(xf.unit_names, xf.unit_pts):
        if Z.unit_group(name.split("/")[0]) != "axial":
            continue
        near = pts[mt.query(pts, distance_upper_bound=LOCAL_MM)[0] < np.inf]
        if not len(near):
            continue
        A, t = xf.piece_map[name.split("/")[-1]]
        q = Z.apply_sim(A, t, near)
        if refit is not None:
            q = Z.apply_sim(refit[0], refit[1], q)
        d_all.append(her_tree.query(q)[0])
    if not d_all:
        return {"n": 0, "median_mm": None, "p90_mm": None, "d": np.zeros(0)}
    d = np.concatenate(d_all)
    return {"n": int(len(d)), "median_mm": round(float(np.median(d)), 2),
            "p90_mm": round(float(np.percentile(d, 90)), 2), "d": d}


def stack_ct(dcm_dir: Path, ref_path: Path, out_path: Path) -> int:
    """Resample a mixed-FOV axial DICOM series (HFS, identity orientation) onto a reference NIfTI's grid (nearest
    slice in z, bilinear in-plane; outside a slice's FOV = -1024 HU). Q62 step 7b: his frozen CT 5d409385 onto
    vhm_total (the TotalSegmentator outputs' grid); checked: his trachea label reads -913 HU median."""
    import nibabel as nib
    import pydicom
    from scipy.ndimage import map_coordinates
    ref = nib.load(ref_path); A, sh = ref.affine, ref.shape
    sl = {}
    for f in sorted(Path(dcm_dir).glob("*.dcm")):
        d = pydicom.dcmread(f)
        sl[float(d.ImagePositionPatient[2])] = (
            d.pixel_array.astype(np.float32) * float(d.RescaleSlope) + float(d.RescaleIntercept),
            [float(x) for x in d.ImagePositionPatient[:2]], [float(x) for x in d.PixelSpacing])
    out = np.full(sh, -1024, np.int16)
    ii, jj = np.meshgrid(np.arange(sh[0]), np.arange(sh[1]), indexing="ij")
    x_lps, y_lps = -(A[0, 0] * ii + A[0, 3]), -(A[1, 1] * jj + A[1, 3])
    zs = np.array(sorted(sl))
    for k in range(sh[2]):
        img, ipp, ps = sl[zs[np.argmin(abs(zs - (A[2, 2] * k + A[2, 3])))]]
        out[:, :, k] = np.rint(map_coordinates(img, [(y_lps - ipp[1]) / ps[0], (x_lps - ipp[0]) / ps[1]],
                                               order=1, cval=-1024)).astype(np.int16)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(out, A), str(out_path))
    print(f"{out_path}: {sh}, {len(sl)} slices")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=sorted(TARGETS), default="vhf", help="vhf (her) or vhm (him, Q62 step 7b)")
    ap.add_argument("--out", default=None, help="default build/vh/xfer_zan2vhf_head / xfer_zan2vhm_head")
    ap.add_argument("--report", default=None)
    ap.add_argument("--dry", action="store_true", help="measure and report only; write no subject")
    ap.add_argument("--stack-ct", default=None, metavar="DICOM_DIR",
                    help="vhm only: resample his IDC frozen-CT series onto vhm_total's grid -> CT_HU_VHM, then exit")
    a = ap.parse_args(argv)
    T = a.target; cfg = TARGETS[T]; SUBJ = cfg["subject"]
    if a.stack_ct:
        return stack_ct(Path(a.stack_ct), TASK / f"{cfg['prefix']}_total.nii.gz", Path(cfg["ct"]))
    a.out = a.out or str(REPO / "build" / "vh" / SUBJ)
    a.report = a.report or str(cfg["report"])
    O = np.array([float(x) for x in cfg["origin"].split(",")])
    GROUPS_T = groups_for(T)
    GROUP_OF_T = {x: g for g, ids in GROUPS_T.items() for x in ids}
    published = PUBLISHED if T == "vhf" else {k: v for k, v in PUBLISHED.items() if v.get("value_cm3")}

    tg = targets(T)
    rep168 = json.loads(Path(cfg["q168"]).read_text())
    fits = Z.fits_from_json(rep168["bone_fits"])
    need = {p for fr in fits.values() if fr.get("status") == "fitted" for p in fr["pieces"]}
    zids = {z for t in tg for z in zan_parts(t)} | set(LARYNX_CARTILAGES)
    items = {it["mesh_id"]: it for it in Z.collect_zan(ids=zids | need)}
    xf = Z.load_zan_to_vhf(zan_meshes=items, report_path=cfg["q168"])
    bundle = json.loads(Path(cfg["bundle"]).read_text())
    order = [s for s in bundle["subject"].split("+") if s != SUBJ]
    her_all = Z.load_her_meshes(order=order, bundle_json=cfg["bundle"])
    own_ids = {e["id"] for e in bundle["structures"] if e["subject"] != SUBJ}
    skin = her_all["skin"]; skin_mesh = trimesh.Trimesh(skin["v"], skin["f"], process=False)
    cart, looks, label_info = her_label_meshes(O, T)
    bones = {b: trimesh.Trimesh(her_all[b]["v"], her_all[b]["f"], process=False) for b in HER_BONES if b in her_all}
    bones.update(ct_bone_meshes(T, O))
    bones.update(cart)
    her_bone_pts = np.vstack([Z.sample_surface(m.vertices, m.faces, 20000, seed=1) for b, m in bones.items()
                              if b not in cart])
    her_bone_tree = cKDTree(her_bone_pts)
    cart_pts = np.vstack([Z.sample_surface(m.vertices, m.faces, 8000, seed=2) for m in cart.values()])
    cart_tree = cKDTree(np.vstack([cart_pts, Z.sample_surface(bones["hyoid"].vertices, bones["hyoid"].faces,
                                                                4000, seed=2)]))
    lx = larynx_refit(xf, items, cart)
    refit = (lx["A"], lx["t"]) if lx["accepted"] else None
    larynx_info = {"accepted": lx["accepted"], "scale": lx["scale"], "rot_deg": lx["rot_deg"],
                   "before_median_mm": round(float(np.median(lx["before"])), 2),
                   "after_median_mm": round(float(np.median(lx["after"])), 2),
                   "before_p90_mm": round(float(np.percentile(lx["before"], 90)), 2),
                   "after_p90_mm": round(float(np.percentile(lx["after"], 90)), 2),
                   **{k: lx[k] for k in ("mode", "rigid_rot_deg") if k in lx}}
    # Z-Anatomy cartilage points (source frame) for the larynx group's local carrier error
    cart_src = np.vstack([items[c]["v"] for c in LARYNX_CARTILAGES])
    cart_dst = Z.apply_sim(lx["A"], lx["t"], np.vstack([xf(c, "bone", items[c]["v"]) for c in LARYNX_CARTILAGES]))

    rows, out_mesh, src_mesh, dropped, pooled = {}, {}, {}, {}, {g: [] for g in GROUPS_T}
    for aid in tg:
        g = GROUP_OF_T[aid]; side = aid[-1] if aid[-2:] in ("_r", "_l") else ""
        if aid in own_ids:
            dropped[aid] = pron("already in her bundle", T); continue
        parts = [z for z in zan_parts(aid) if z in items]
        if not parts:
            dropped[aid] = f"no Z-Anatomy object {zan_parts(aid)}"; continue
        vs, fs, off = [], [], 0
        for z in parts:
            nv_z = xf(z, items[z]["cat"], items[z]["v"])
            if g == "larynx" and refit is not None:
                nv_z = Z.apply_sim(refit[0], refit[1], nv_z)
            vs.append((items[z]["v"], nv_z)); fs.append(items[z]["f"] + off); off += len(nv_z)
        v_src = np.vstack([p[0] for p in vs]); nv = np.vstack([p[1] for p in vs]); f = np.vstack(fs)
        lo, hi = nv.min(0) - 5, nv.max(0) + 5
        near = {b: m for b, m in bones.items() if np.all(m.bounds[0] <= hi) and np.all(m.bounds[1] >= lo)}
        near_bones = list(near.values())
        in_bone = np.zeros(len(nv), bool); per_bone = {}
        for b, m in near.items():
            ins = m.contains(nv); in_bone |= ins
            if ins.any():
                per_bone[b] = int(ins.sum())
        frac_out = float((~skin_mesh.contains(nv)).mean()); od = FT.outside_depth(nv, skin_mesh)
        ride = FT.rides_on(xf, fits, v_src, side, groups=("axial",))
        if g == "larynx":
            cn = cart_dst[cKDTree(v_src).query(cart_src, distance_upper_bound=LOCAL_MM)[0] < np.inf]
            d = cart_tree.query(cn)[0] if len(cn) else np.zeros(0)
            loc = {"n": int(len(d)), "median_mm": round(float(np.median(d)), 2) if len(d) else None,
                   "p90_mm": round(float(np.percentile(d, 90)), 2) if len(d) else None, "d": d,
                   "against": pron("her CT thyroid + cricoid cartilage + hyoid", T)}
        else:
            loc = local_carrier_error(xf, v_src, her_bone_tree)
            loc["against"] = pron("her CT bones", T)
        pooled[g].append(loc.pop("d"))
        nv2, n_push, n_deep = FT.bounded_push_off_bones(nv, near_bones)
        in_bone_p = np.zeros(len(nv2), bool)
        for m in near_bones:
            in_bone_p |= m.contains(nv2)
        row = {"atlas_id": aid, "group": g, "zanatomy_objects": [items[z]["name"] for z in parts],
               "zanatomy_mesh_ids": parts, "partial": PARTIAL_NOTE.get(aid), "vertices": int(len(nv)),
               "triangles": int(len(f)), "inside_bone_frac_before": round(float(in_bone.mean()), 4),
               "inside_bone_by_bone": per_bone, "outside_skin_frac_before": round(frac_out, 4),
               "outside_skin_depth_mm": {"p95": round(float(np.percentile(od, 95)), 2) if len(od) else 0.0,
                                         "max": round(float(od.max()), 2) if len(od) else 0.0},
               "pushed_off_bone": n_push, "inside_bone_deeper_than_bound": n_deep,
               "inside_bone_frac_after_push": round(float(in_bone_p.mean()), 4), "rides_on": ride,
               "carrier_local": loc}
        nv3, n_clip = FT.pull_inside_skin(nv2, skin_mesh)
        skin_moved = float((np.linalg.norm(nv3 - nv2, axis=1) > 0).mean())
        in_bone2 = np.zeros(len(nv3), bool)
        for m in near_bones:
            in_bone2 |= m.contains(nv3)
        mv = np.linalg.norm(nv3 - nv, axis=1)
        vol_src = FT.voxel_volume_cm3(v_src, f); vol_x = FT.voxel_volume_cm3(nv, f); vol_out = FT.voxel_volume_cm3(nv3, f)
        org = {k: round(float(fn(nv3).mean()), 4) for k, fn in looks.items()}
        depth = skin_mesh.nearest.on_surface(Z._sub(nv3, 600, 6))[1]
        row.update({"clipped_to_skin": n_clip, "skin_moved_frac": round(skin_moved, 4),
                    "fix_move_mm": {"p95": round(float(np.percentile(mv, 95)), 2), "max": round(float(mv.max()), 2)},
                    "inside_bone_frac_after": round(float(in_bone2.mean()), 4),
                    "outside_skin_frac_after": round(float((~skin_mesh.contains(nv3)).mean()), 4),
                    "inside_label_frac": org, "inside_airway_frac": org["airway"],
                    "depth_under_skin_mm": {"min": round(float(depth.min()), 1), "median": round(float(np.median(depth)), 1)},
                    "volume_zanatomy_cm3": round(vol_src, 2), "volume_transferred_before_fix_cm3": round(vol_x, 2),
                    "volume_cm3": round(vol_out, 2), "volume_ratio_vs_zanatomy": round(vol_out / vol_src, 3),
                    "volume_kept_after_fix": round(vol_out / vol_x, 3) if vol_x else None})
        why = None
        if in_bone_p.mean() > MAX_INSIDE_BONE:
            why = (f"{in_bone_p.mean():.1%} of vertices still inside her bone/cartilage after the bounded push-out "
                   f"(> {MAX_INSIDE_BONE:.0%}; {in_bone.mean():.1%} before)")
        elif frac_out > MAX_OUTSIDE_SKIN_PRECLIP:
            why = f"{frac_out:.0%} of vertices outside her skin before the fix (failed fit)"
        elif skin_moved > MAX_SKIN_MOVED:
            why = (f"thin sheet: the skin pull drags {skin_moved:.0%} of its vertices (> {MAX_SKIN_MOVED:.0%}) -- "
                   f"would be flattened onto her skin, not fitted")
        elif vol_x and vol_out / vol_x < MIN_VOL_KEPT:
            why = f"the fixes leave {vol_out / vol_x:.0%} of its transferred volume (< {MIN_VOL_KEPT:.0%})"
        elif loc["median_mm"] is None or loc["median_mm"] > MAX_CARRIER_MM:
            why = f"bone around it fits her CT at {loc['median_mm']} mm median (> {MAX_CARRIER_MM} mm)"
        elif org["airway"] > MAX_IN_AIRWAY:
            why = f"{org['airway']:.1%} of vertices inside her air lumen (> {MAX_IN_AIRWAY:.0%})"
        if why:
            why = pron(why, T); row["dropped"] = why; dropped[aid] = why
        else:
            out_mesh[aid] = (nv3, f); src_mesh[aid] = (v_src, f)
        rows[aid] = row

    # carrier gate per group (pooled local distances)
    group_carrier = {}
    for g, ds in pooled.items():
        d = np.concatenate(ds) if ds else np.zeros(0)
        med = float(np.median(d)) if len(d) else None
        group_carrier[g] = {"median_mm": round(med, 2) if med is not None else None,
                            "p90_mm": round(float(np.percentile(d, 90)), 2) if len(d) else None,
                            "held": bool(med is None or med > MAX_CARRIER_MM)}
        if group_carrier[g]["held"]:
            for aid in GROUPS_T[g]:
                if aid in out_mesh:
                    why = f"group {g}: carrier median {med} mm > {MAX_CARRIER_MM} mm"
                    rows[aid]["dropped"] = why; dropped[aid] = why; del out_mesh[aid]

    # overlap: vertices inside her existing muscles (bundle, any subject) + her organ labels = conflicts with HER;
    # vertices inside the other new muscles are compared with the same pairs in the Z-Anatomy source (facial
    # muscles interdigitate at the modiolus in Z-Anatomy itself): only the excess over the source counts.
    exist = {k: m for k, m in her_all.items() if m.get("cat") == "muscle"}
    tm_new = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in out_mesh.items()}
    tm_src = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in src_mesh.items()}

    def hits(v, meshes):
        lo, hi = v.min(0), v.max(0); out = {}
        for k, m in meshes:
            if np.all(m.bounds[0] <= hi) and np.all(m.bounds[1] >= lo):
                n = int(m.contains(v).sum())
                if n:
                    out[k] = round(n / len(v), 4)
        return out
    for aid in list(out_mesh):
        v = out_mesh[aid][0]
        ov = hits(v, [(k, trimesh.Trimesh(m["v"], m["f"], process=False)) for k, m in exist.items()
                      if np.all(m["v"].min(0) <= v.max(0)) and np.all(m["v"].max(0) >= v.min(0))])
        for k in ("tongue", "oesophagus", "thyroid_gland"):
            if rows[aid]["inside_label_frac"][k]:
                ov[f"her_{k}_label"] = rows[aid]["inside_label_frac"][k]
        on = hits(v, [(k, m) for k, m in tm_new.items() if k != aid])
        os_ = hits(src_mesh[aid][0], [(k, m) for k, m in tm_src.items() if k != aid])
        her_t, new_t, src_t = sum(ov.values()), sum(on.values()), sum(os_.values())
        rows[aid].update({
            "overlap_her_structures": dict(sorted(ov.items(), key=lambda kv: -kv[1])),
            "overlap_new_muscles": dict(sorted(on.items(), key=lambda kv: -kv[1])),
            "overlap_new_muscles_in_zanatomy_source": dict(sorted(os_.items(), key=lambda kv: -kv[1])),
            "overlap_her_total": round(her_t, 4), "overlap_new_total": round(new_t, 4),
            "overlap_new_total_source": round(src_t, 4),
            "overlap_frac_total": round(her_t + max(0.0, new_t - src_t), 4)})
    for aid in list(out_mesh):
        r = rows[aid]
        if r["overlap_frac_total"] > MAX_OVERLAP:
            top = next(iter(r["overlap_her_structures"] or r["overlap_new_muscles"]))
            why = pron(f"{r['overlap_frac_total']:.1%} of vertices inside other muscles/organs (> {MAX_OVERLAP:.0%}; "
                       f"her structures {r['overlap_her_total']:.1%}, new muscles {r['overlap_new_total']:.1%} vs "
                       f"{r['overlap_new_total_source']:.1%} in Z-Anatomy itself; mostly {top})", T)
            r["dropped"] = why; dropped[aid] = why; del out_mesh[aid]

    for aid in out_mesh:
        r = rows[aid]; loc = r["carrier_local"]
        carrier = ("her own CT thyroid + cricoid cartilages (Z-Anatomy larynx refitted onto them)" if r["group"] == "larynx"
                   else "her own skull/mandible/hyoid/spine bones")
        r["badge"] = ("Q62 step 7: TRANSFERRED, not segmented from her. Z-Anatomy geometry (CC BY-SA 4.0; Z-Anatomy / "
                      f"BodyParts3D) fitted onto {carrier} (Q168 per-bone fits). Not measured on this muscle (she has "
                      f"no mesh of it); the bone surface within {LOCAL_MM:.0f} mm of it fits her CT at {loc['median_mm']:.1f} mm "
                      f"median (p90 {loc['p90_mm']:.1f} mm). Volume {r['volume_cm3']:.2f} cm3; {r['pushed_off_bone']} "
                      f"vertices pushed off her bones, {r['clipped_to_skin']} pulled inside her skin."
                      + (f" Partial: {r['partial']}." if r["partial"] else ""))
        r["badge"] = pron(r["badge"], T)
        pub = published.get(re.sub(r"_[rl]$", "", aid), {}).get("value_cm3")
        if pub and r["volume_cm3"] > 1.5 * pub:
            r["badge"] += (f" SIZE CAVEAT: {r['volume_cm3'] / pub:.1f}x the published adult MRI volume ({pub:.2f} cm3, "
                           "Volk 2014); the generic Z-Anatomy sheet is thicker than a real one, so treat its bulk as an "
                           "overestimate.")

    shipped = sorted(out_mesh)
    by_group = {g: {"shipped": [a for a in ids if a in out_mesh], "held": {a: dropped[a] for a in ids if a in dropped}}
                for g, ids in GROUPS_T.items()}
    summary = {"shipped": shipped, "n_shipped": len(shipped), "dropped": dropped, "by_group": by_group,
               "group_carrier": group_carrier, "larynx_refit": larynx_info, "her_labels": label_info,
               "not_mapped": NOT_MAPPED,
               **({"bones_from_ct_labels": {k: list(v) for k, v in cfg["ct_bones"].items()}} if cfg.get("ct_bones") else {})}
    doc = {"source": pron("Q62 step 7 (scripts/transfer/zan_to_vhf_head_neck.py): Z-Anatomy head/neck/larynx muscles "
                          "(CC BY-SA 4.0) carried onto the VH female's own skull/mandible/hyoid/spine (Q168 per-bone fits, "
                          f"{Path(cfg['q168']).relative_to(REPO)}) and her CT laryngeal cartilages.", T)
                     .replace("Q62 step 7b (", "Q62 step 7b (--target vhm; "),
           "gates": {"max_inside_bone_frac": MAX_INSIDE_BONE, "max_outside_skin_preclip_frac": MAX_OUTSIDE_SKIN_PRECLIP,
                     "max_carrier_mm": MAX_CARRIER_MM, "max_overlap_frac": MAX_OVERLAP, "max_in_airway_frac": MAX_IN_AIRWAY,
                     "max_skin_moved_frac": MAX_SKIN_MOVED, "min_volume_kept": MIN_VOL_KEPT,
                     "push_bound_mm": FT.PUSH_BOUND_MM, "local_mm": LOCAL_MM},
           "summary": summary, "published_volumes": published, "published_note": PUBLISHED_NOTE, "rows": rows}
    Path(a.report).write_text(json.dumps(doc, indent=1))
    print(f"report {a.report}: shipped {len(shipped)}, held {len(dropped)}")
    if a.dry or not shipped:
        return 0

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    verts, faces, structs, voff, foff = [], [], [], 0, 0
    for aid in shipped:
        v, f = out_mesh[aid]; v32 = v.astype(np.float32)
        side = "right" if aid.endswith("_r") else "left" if aid.endswith("_l") else "midline"
        structs.append({"atlas_id": aid, "source_structure": "+".join(rows[aid]["zanatomy_mesh_ids"]), "side": side,
                        "source_file": "zanatomy#" + "+".join(rows[aid]["zanatomy_objects"]),
                        "vertex_offset": voff, "face_offset": foff, "vertex_count": int(len(v32)),
                        "triangle_count": int(len(f)),
                        "bbox_min_mm": [round(float(x), 4) for x in v32.min(0)],
                        "bbox_max_mm": [round(float(x), 4) for x in v32.max(0)],
                        "procedural_badge": rows[aid]["badge"],
                        "transfer": {"from": "zanatomy", "method": pron("Q168 per-bone fit (zan_to_vhf_whole_body)", T)
                                     + (pron(" + larynx refit onto her CT cartilages", T) if rows[aid]["group"] == "larynx" else ""),
                                     "rides_on": rows[aid]["rides_on"]["bones"][:3]}})
        verts.append(v32); faces.append((f + voff).astype(np.uint32)); voff += len(v32); foff += len(f)
    V = np.concatenate(verts); F = np.concatenate(faces)
    V.tofile(out / "vertices.f32"); F.tofile(out / "faces.u32")
    attribution = [
        "GENERIC MODEL, NOT SEGMENTED FROM THIS SPECIMEN: head, neck and larynx muscles from Z-Anatomy (CC BY-SA 4.0), "
        "fitted onto this specimen's OWN skull, mandible, hyoid and spine one bone at a time (Q168 per-bone similarity "
        "fits) and, for the larynx, onto her own CT thyroid + cricoid cartilages; pushed off her bones and pulled inside "
        "her skin (scripts/transfer/zan_to_vhf_head_neck.py, Q62 step 7). Only ids she had no mesh for. Per-muscle "
        "badge gives the measured fit error of the bone around it; data/derived/Q62s7_vhf_head_neck.json has every "
        "gate number.",
        "Z-Anatomy: models by the Z-Anatomy project (BodyParts3D upstream credited in its own LICENSE), app by "
        "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. "
        "Licensed CC BY-SA 4.0; this registered derivative remains CC BY-SA 4.0 (ShareAlike)."]
    attribution = [pron(x, T) for x in attribution]
    if T == "vhm":
        attribution[0] = attribution[0].replace("Q62s7_vhf_head_neck.json", "Q62s7b_vhm_head_neck.json")
    man = {"subject": out.name, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
           "source_volume": None, "source_kind": pron("cross-subject transfer zanatomy -> vhf (Q168 per-bone fit)", T),
           "vertex_count": int(len(V)), "triangle_count": int(len(F)),
           "bbox_min_mm": [round(float(x), 4) for x in V.min(0)], "bbox_max_mm": [round(float(x), 4) for x in V.max(0)],
           "attribution": attribution, "license": "CC-BY-SA-4.0", "structures": structs}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"{out.name}: {len(structs)} structures, {len(V)} vertices, {len(F)} triangles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
