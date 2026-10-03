"""ATTEMPTED, NOT SHIPPED (Q106, 2026-09-21) -- kept as a documented negative result, NOT wired into
vhm_rebuild_bundle.sh. Splits his (Visible Human MALE) right `extensor_digitorum_supinator_anconeus_compartment`
(label 12 of vhm_forearm_muscles_cryo.nii.gz, 48.6 cm3) into extensor_digitorum_r / supinator_r / anconeus_r by
a POSITION RULE -- not a traced septum (following Q100's method on the female's ECRL/ECRB compartment) -- and
the rule itself verifies well (see VERIFICATION below: mesh connectivity 98.7-100%, plausible relative volumes).

WHY IT IS NOT SHIPPED. Checking the split against his own CT skin surface (data/ct_sources/task_outputs/
vhm_skin_ct.nii.gz -- the same reference clip_arm_to_skin.py already uses for his arm muscles) found that the
WHOLE vhm_forearm_muscles_cryo.nii.gz volume -- every label, not just this compartment -- has an outside-skin
voxel fraction that rises smoothly from 0% in the segment's distal 60% (f >= 0.60) to about 22% at its most
proximal level (f = 0), a pre-existing registration gradient in the already-shipped (2026-09-14) volume, not
something this split introduces or could fix by moving the boundary line. Anconeus (f <= 0.12) and supinator
(f <= 0.28) sit almost entirely inside that poorly-registered proximal band by real anatomical position, so in
every variant tried anconeus comes out 100% outside his skin surface and supinator 72-82% outside, even after
the same erosion-margin clip used for his arm muscles (scipy binary_erosion, 3 voxels/~2.8 mm). This is a
data-quality property of the SOURCE volume's proximal registration (translation-only per level, no rotation --
already flagged as a LIMIT in vhm_forearm_muscles_from_cryo.py's own docstring), not a defect a splitting rule
can repair; fixing it would mean re-deriving the proximal segment's photograph-to-CT registration, out of scope
for Q106. See PROJECT_STATE Q106 and scripts/cryo/vhm_forearm_merge.json for the full account, including the
two OTHER compartments (radial_flexor_compartment, mobile_wad_compartment) also tried and declined this round.

    python3 scripts/cryo/vhm_split_forearm_extensor_compartment.py --dry-run

WHY A POSITION RULE. vhm_forearm_muscles_from_cryo.py's own marker watershed found no reliable septum here:
anconeus|supinator ran on a pale line at only 44% of 16 shared levels, extensor_digitorum|anconeus at 44% of 9
(vhm_forearm_merge.json), so all three were shipped merged, and the note also flags the raw watershed's own
anconeus region (1.9 cm3) as "too small to be the muscle" -- a second, independent defect this rule fixes (see
VERIFICATION below). extensor_digitorum's OTHER boundaries (with extensor_carpi_ulnaris, extensor_digiti_minimi,
extensor_indicis, extensor_pollicis_brevis/longus, abductor_pollicis_longus) all ran at 72-100% and are fine;
only its boundary with anconeus, and the anconeus/supinator boundary, are the weak ones being replaced here.

WHY THIS SPLIT IS TRACTABLE (unlike Q106's other two candidates, radial_flexor_compartment and
mobile_wad_compartment, both DECLINED -- see PROJECT_STATE Q106). Two independent, orthogonal position rules
already used elsewhere in this project's own MARKER_RULES table (scripts/cryo/vhf_forearm_muscles_from_cryo.py,
imported and reused by vhm_forearm_muscles_from_cryo.py, scaled) describe exactly how these three muscles differ
in POSITION, not merely in seed placement:
  1. LEVEL. anconeus's rule window is f in [0.00, 0.12] (proximal 12% of the forearm segment only -- it is a
     small muscle from the lateral epicondyle to the olecranon/proximal ulna, entirely near the elbow); supinator's
     is f in [0.00, 0.28] (it continues distally, wrapping the proximal radius, to about a quarter of the way
     down); extensor_digitorum's is f in [0.05, 0.70] (it runs almost the full segment). So past f=0.28, only ED
     is anatomically possible in this compartment -- a real, literature-grounded constraint, not an assumption
     this script introduces.
  2. DEPTH FROM BONE. anconeus and supinator are both anchored close to a bone surface in MARKER_RULES (n offset
     -4 mm from the anchor bone's surface, i.e. deep, right against the ulna/radius); extensor_digitorum's anchor
     is n=-14 mm (10 mm further out, superficial) -- Standring's cross-sectional ordering has ED lying superficial
     to supinator and anconeus around the proximal forearm. Distance to the nearest of his CT radius/ulna surface
     (vhm_arm_bones_cryo_completed.nii.gz, the SAME bone volume vhm_forearm_muscles_from_cryo.py registered the
     muscle mass onto -- after_bone_correction_mm residual for this subject is 2-3 mm SD, not the 5-12 mm that
     blocked Q100 from using CT bones directly) is therefore a legitimate, real-geometry proxy for this axis.
  3. WHICH BONE. Where anconeus and supinator overlap (f <= 0.12, both deep), the anatomical distinction is which
     bone they hug: anconeus inserts on the ulna (olecranon/proximal posterior shaft), supinator wraps the radius.
     Distance to his CT ulna vs radius decides it.
No new geometry is invented and no photograph re-derivation is needed: like Q100, this reads only the ALREADY
SHIPPED, real-photograph-derived compartment mask plus the already-tracked CT bone labels used to build it.

RULE, per compartment voxel (RAS mm, from the volume's own affine -- no resampling):
    f = level fraction along the segment (0 proximal/near-elbow .. 1 distal/near-wrist), from RAS z and the
        report's own segment_ras_z [-640.0, -776.0];
    d_radius, d_ulna = nearest-neighbour distance (mm) to his CT radius / ulna surface voxels (RAS, same frame);
    d_bone = min(d_radius, d_ulna).
    if f > 0.28 or d_bone > BONE_THR_MM:            extensor_digitorum   (past anconeus/supinator's own range, or superficial)
    elif f <= 0.12 and d_ulna < d_radius:           anconeus             (deep, proximal, ulna side)
    else:                                            supinator            (deep, f in (0.12, 0.28], or f<=0.12 radius side)
BONE_THR_MM = 10 mm, the plateau (9-10.25 mm; swept 6-14 mm, dev notes/PROJECT_STATE Q106) where all three parts'
shipped, smoothed (smooth=1.0, this subject's own `vhm_rebuild_bundle.sh` setting) meshes stay in one face-adjacency
component -- the same Q100 lesson (voxel 26-connectivity alone is not enough; a threshold that looks perfect on the
voxel mask can still ship as disconnected lobes after smoothing) applied here from the start, not discovered by a
bad ship. Anconeus's f-cutoff (0.12) and supinator's (0.28) are MARKER_RULES' own windows, not fitted to this run.

VERIFICATION: voxel and mesh (scipy.sparse + csgraph on the actual mask_surface(..., smooth=1.0) output) largest-
component fraction for all three parts; volumes against a stated, honestly-hedged plausible range (reviewer
estimate, NOT read from Holzbaur et al. 2007 -- that paper's per-muscle table was not accessible here either,
same limitation the original report notes); zero voxel overlap; the three parts exactly reconstruct the
compartment. See PROJECT_STATE Q106 for the actual numbers and the two DECLINED compartments' numbers.

OUTPUT: rewrites vhm_forearm_muscles_cryo.nii.gz in place (label 12 kept for extensor_digitorum, two new label ids
for supinator and anconeus); updates the label key and the report. The subject mapping
(mappings/subjects/ct_vhm_forearm_volume_mapping.json) is a separate, hand-checked edit (this script does not
touch it), matching Q100's vhf_split_ecrl_ecrb.py convention.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from engine.volume_ingest import mask_surface  # noqa: E402

BADGE = "position-rule, not a traced septum"
COMPARTMENT = "extensor_digitorum_supinator_anconeus_compartment"
ED, SUPINATOR, ANCONEUS = "extensor_digitorum", "supinator", "anconeus"
BONES_PATH = REPO / "data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz"
BONES_AFF = (350.0, 240.0, -1113.0)   # x = 350-i, y = 240-j, z = -1113+k (vhm_forearm_muscles_from_cryo.py)
BONE_ID = {"radius": 2, "ulna": 3}
Z_TOP, Z_BOT = -640.0, -776.0         # f=0 (proximal) .. f=1 (distal); report's segment_ras_z
F_ANCONEUS_MAX = 0.12                 # MARKER_RULES' own anconeus f1
F_SUPINATOR_MAX = 0.28                # MARKER_RULES' own supinator f1
BONE_THR_MM = 10.0                    # see docstring: mesh-connected plateau, swept 6-14 mm


def voxel_ras(idx, aff):
    x = aff[0, 3] + aff[0, 0] * idx[:, 0]
    y = aff[1, 3] + aff[1, 1] * idx[:, 1]
    z = aff[2, 3] + aff[2, 2] * idx[:, 2]
    return np.stack([x, y, z], axis=1)


def bone_points_ras(bones, label_id, zlo, zhi, pad=40.0):
    kk_lo = max(int(np.floor(zlo - pad - BONES_AFF[2])), 0)
    kk_hi = min(int(np.ceil(zhi + pad - BONES_AFF[2])), bones.shape[2] - 1)
    sub = bones[:, :, kk_lo:kk_hi + 1]
    ii, jj, kk = np.where(sub == label_id)
    kk = kk + kk_lo
    x = BONES_AFF[0] - ii; y = BONES_AFF[1] - jj; z = BONES_AFF[2] + kk
    return np.stack([x, y, z], axis=1).astype(np.float32)


def largest_component(mask, struct):
    lab, n = ndi.label(mask, structure=struct)
    if n == 0:
        return mask.copy(), 0, 1.0
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    keep = int(np.argmax(sizes)) + 1
    return lab == keep, n, float(sizes.max() / mask.sum())


def mesh_face_components(mask):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    v, f = mask_surface(mask, step=1, smooth=1.0)
    if len(f) == 0:
        return 0, 0.0
    n = len(v)
    e0 = np.concatenate([f[:, 0], f[:, 1], f[:, 2]])
    e1 = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    m = coo_matrix((np.ones(len(e0)), (e0, e1)), shape=(n, n))
    ncomp, labels = connected_components(m, directed=False)
    sizes = np.bincount(labels)
    return ncomp, float(sizes.max() / n)


def split(vol, aff, bones, bone_thr=BONE_THR_MM, log=print):
    labels = json.loads(Path(REPO / "mappings/vhm_forearm_muscles_labels.json").read_text())["labels"]
    ids = {v: int(k) for k, v in labels.items()}
    lid_comp = ids[COMPARTMENT]
    comp = vol == lid_comp
    if not comp.any():
        raise SystemExit(f"label {lid_comp} ({COMPARTMENT}) is empty")

    idx = np.argwhere(comp)
    ras = voxel_ras(idx, aff)
    f = (Z_TOP - ras[:, 2]) / (Z_TOP - Z_BOT)
    radius_pts = bone_points_ras(bones, BONE_ID["radius"], ras[:, 2].min(), ras[:, 2].max())
    ulna_pts = bone_points_ras(bones, BONE_ID["ulna"], ras[:, 2].min(), ras[:, 2].max())
    if len(radius_pts) == 0 or len(ulna_pts) == 0:
        raise SystemExit("no CT radius/ulna voxels near this segment -- cannot compute the bone-distance axis")
    d_radius = cKDTree(radius_pts).query(ras)[0]
    d_ulna = cKDTree(ulna_pts).query(ras)[0]
    d_bone = np.minimum(d_radius, d_ulna)

    ed_sel = (f > F_SUPINATOR_MAX) | (d_bone > bone_thr)
    anc_sel = (~ed_sel) & (f <= F_ANCONEUS_MAX) & (d_ulna < d_radius)
    sup_sel = (~ed_sel) & ~anc_sel

    masks = {}
    for name, sel in ((ED, ed_sel), (ANCONEUS, anc_sel), (SUPINATOR, sup_sel)):
        m = np.zeros(vol.shape, bool)
        m[tuple(idx[sel].T)] = True
        masks[name] = m

    # cleanup to a fixed point: keep each part's largest connected component; fold every OTHER part's stray
    # fragments into whichever part is spatially nearest (by distance transform to its own current largest
    # component), same principle as vhf_split_ecrl_ecrb.py's 2-way loop, generalised to three parts.
    struct = np.ones((3, 3, 3), bool)
    for _ in range(10):
        mains = {}
        for name, m in masks.items():
            main, _, _ = largest_component(m, struct)
            mains[name] = main
        stray = comp & ~(mains[ED] | mains[ANCONEUS] | mains[SUPINATOR])
        if not stray.any():
            masks = mains
            break
        dts = {name: ndi.distance_transform_edt(~mains[name]) for name in masks}
        stray_idx = np.argwhere(stray)
        d_stack = np.stack([dts[name][tuple(stray_idx.T)] for name in (ED, ANCONEUS, SUPINATOR)], axis=1)
        winner = np.array([ED, ANCONEUS, SUPINATOR])[np.argmin(d_stack, axis=1)]
        new_masks = {name: mains[name].copy() for name in masks}
        for name in (ED, ANCONEUS, SUPINATOR):
            sel = stray_idx[winner == name]
            if len(sel):
                new_masks[name][tuple(sel.T)] = True
        if all((new_masks[n] == masks[n]).all() for n in masks):
            masks = new_masks
            break
        masks = new_masks
    else:
        log("  cleanup loop did not converge in 10 iterations (using last state)")

    assert not (masks[ED] & masks[ANCONEUS]).any()
    assert not (masks[ED] & masks[SUPINATOR]).any()
    assert not (masks[ANCONEUS] & masks[SUPINATOR]).any()
    assert (masks[ED] | masks[ANCONEUS] | masks[SUPINATOR]).sum() == comp.sum(), "parts do not reconstruct the compartment"

    vox_mm3 = float(abs(aff[0, 0] * aff[1, 1] * aff[2, 2]))
    result = {}
    for name, m in masks.items():
        nvc, fvc = largest_component(m, struct)[1:]
        ncomp, mfrac = mesh_face_components(m)
        result[name] = {"mask": m, "vol_cm3": round(float(m.sum() * vox_mm3 / 1000), 2),
                         "voxel_components": nvc, "voxel_largest_component_frac": round(fvc, 4),
                         "mesh_components": ncomp, "mesh_largest_component_frac": round(mfrac, 4)}
        log(f"  {name:22s} {result[name]['vol_cm3']:6.2f} cm3  voxel {nvc:3d} comp ({fvc:.3f})  "
            f"mesh {ncomp:3d} comp ({mfrac:.3f})")
    return result, lid_comp


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", default=str(REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_cryo.nii.gz"))
    ap.add_argument("--bones", default=str(BONES_PATH))
    ap.add_argument("--out", default=None, help="default: overwrite --in")
    ap.add_argument("--labels", default=str(REPO / "mappings/vhm_forearm_muscles_labels.json"))
    ap.add_argument("--report", default=str(REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_cryo_report.json"))
    ap.add_argument("--bone-thr-mm", type=float, default=BONE_THR_MM)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true",
                     help="actually write the split (default: dry-run only). NOT declined for a reason a code "
                          "change can fix -- see the module docstring (skin-containment finding) before passing this.")
    a = ap.parse_args(argv)
    if not a.apply:
        a.dry_run = True

    img = nib.load(a.inp)
    vol = np.asarray(img.dataobj).astype(np.uint8)
    bones = np.asanyarray(nib.load(a.bones).dataobj)
    result, lid_comp = split(vol, img.affine, bones, bone_thr=a.bone_thr_mm)

    if a.dry_run:
        return 0

    new_ids = {ANCONEUS: max(int(k) for k in json.loads(Path(a.labels).read_text())["labels"]) + 1}
    new_ids[SUPINATOR] = new_ids[ANCONEUS] + 1
    vol2 = vol.copy()
    vol2[result[ED]["mask"]] = lid_comp                     # label 12 keeps its id, renamed to extensor_digitorum
    vol2[result[ANCONEUS]["mask"]] = new_ids[ANCONEUS]
    vol2[result[SUPINATOR]["mask"]] = new_ids[SUPINATOR]
    for lid in np.unique(vol):
        if lid in (0, lid_comp):
            continue
        assert (vol2 == lid).sum() == (vol == lid).sum(), f"label {lid} changed"
    out_path = Path(a.out or a.inp)
    nib.save(nib.Nifti1Image(vol2, img.affine), out_path)
    print(f"wrote {out_path}")

    key = json.loads(Path(a.labels).read_text())
    key["labels"][str(lid_comp)] = ED
    key["labels"][str(new_ids[ANCONEUS])] = ANCONEUS
    key["labels"][str(new_ids[SUPINATOR])] = SUPINATOR
    key["merged_compartments"].pop(COMPARTMENT, None)
    key["_README"].append(f"Q106 ({Path(__file__).name}): label {lid_comp} ({COMPARTMENT}) split into "
                           f"{lid_comp} ({ED}), {new_ids[ANCONEUS]} ({ANCONEUS}), {new_ids[SUPINATOR]} ({SUPINATOR}) "
                           f"by a {BADGE}; the compartment name no longer appears as a label.")
    Path(a.labels).write_text(json.dumps(key, indent=1))
    print(f"updated {a.labels}")

    report = json.loads(Path(a.report).read_text())
    report["labels"].pop(str(lid_comp), None)
    report["labels"][str(lid_comp)] = ED
    report["labels"][str(new_ids[ANCONEUS])] = ANCONEUS
    report["labels"][str(new_ids[SUPINATOR])] = SUPINATOR
    report["volumes_cm3"].pop(COMPARTMENT, None)
    for name in (ED, ANCONEUS, SUPINATOR):
        report["volumes_cm3"][name] = result[name]["vol_cm3"]
    report["merged_compartments"].pop(COMPARTMENT, None)
    report.setdefault("splits", {})[COMPARTMENT] = {
        "script": Path(__file__).name, "badge": BADGE, "bone_thr_mm": a.bone_thr_mm,
        "axis": "level fraction (f, from RAS z) + nearest-neighbour distance (mm) to his CT radius/ulna surface "
                "(same bone volume the compartment was registered onto); see script docstring",
        **{name: {k: v for k, v in result[name].items() if k != "mask"} for name in (ED, ANCONEUS, SUPINATOR)},
    }
    Path(a.report).write_text(json.dumps(report, indent=1))
    print(f"updated {a.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
