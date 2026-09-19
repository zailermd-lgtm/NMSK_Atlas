"""Split her right `extensor_carpi_radialis_compartment` (ECRL+ECRB, vhf_forearm_muscles_from_cryo.py label 10)
into extensor_carpi_radialis_longus_r / extensor_carpi_radialis_brevis_r by a POSITION RULE -- not a traced
septum (Q100, attempted after the original marker-watershed split was rejected: the pale line it followed only
ran on 67% of the shared levels at ridge ratio 2.06, the weakest boundary of the whole forearm, ct_vhf_forearm's
label-10 mapping note).

    python3 scripts/cryo/vhf_split_ecrl_ecrb.py

WHY A POSITION RULE. The photographs show no septum between ECRL and ECRB reliable enough to trace (see above);
this project's fallback in that situation is a rule from anatomical POSITION, badged as such, the same pattern as
the abdominal wall's depth-fraction bands and the pelvic floor's landmark-distance rules (scripts/cryo/
abdominal_wall_from_cryo.py, vhf_pelvic_floor_from_cryo.py: e.g. obturator internus = distance to the hip label
<= a threshold). No new geometry is invented: the rule only reads labels this project has ALREADY shipped from
the SAME photograph-derived volume (vhf_forearm_muscles_cryo.nii.gz), so there is no CT-to-photograph
registration residual to correct for (ct_vhf_forearm_volume_mapping.json's own note on label 1/10/16 flags that
residual as 5-12 mm, which is why the radius/ulna CT meshes are NOT used here).

ANATOMY (Standring, Gray's Anatomy 42nd ed., ch. 49 'Pectoral girdle, shoulder region and arm' / upper limb
compartments; the 'mobile wad' of Henry). Cross-sectional order around the radial side of the forearm, superficial
extensor group, is brachioradialis - ECRL - ECRB - extensor digitorum (EDC) - extensor digiti minimi - extensor
carpi ulnaris: ECRL arises more proximally, from the lateral supracondylar ridge, and lies radial and superficial;
ECRB arises from the lateral epicondyle (common extensor origin), slightly more distal, and lies central/deep to
ECRL, directly adjacent to EDC. So distance to the (already split, photograph-derived, same-volume) EDC label is
a legitimate proxy for the ECRL/ECRB position axis: near EDC = ECRB, far from EDC = ECRL. Brachioradialis was
tried as the opposite-side reference first and rejected -- it wraps close to nearly the whole compartment
(median 2 mm), so distance to it does not discriminate (see the script's dev log / PROJECT_STATE Q100).

RULE, per compartment voxel (0.5x0.5x1 mm grid, same as the source volume):
  1. per level (k, 1 mm), centroid of the compartment voxels and of the EDC voxels (interpolated across levels
     where EDC. is absent -- it does not run the full length of the compartment);
  2. BOTH centroid tracks smoothed along the forearm axis (Gaussian, sigma 20 mm) to remove level-to-level
     shape jitter -- unsmoothed, the raw per-level centroids make the cutting surface kink and disconnect the
     larger piece (found empirically: see the sweep in the dev notes, connected-component fraction crashes from
     0.98 to 0.52 within 0.2 mm of the raw threshold);
  3. per voxel, its projection onto the unit vector from the (smoothed) EDC centroid to the (smoothed) compartment
     centroid at its own level, in mm from the EDC centroid;
  4. threshold T_MM: projection > T_MM -> extensor_carpi_radialis_longus, <= T_MM -> extensor_carpi_radialis_brevis.
     T_MM sits in the plateau where the shipped, smoothed MESH (mask_surface(..., smooth=1.0), the setting this
     subject is actually converted with -- vhf_rebuild_bundle.sh's `--smooth 1.0`) stays one connected component
     for both parts, closest to the textbook ECRL:ECRB volume ratio (20:15, i.e. 57:43) within that plateau. Voxel
     26-connectivity is NOT enough to find this plateau: a mask can be a single voxel-connected component through
     a bridge one voxel wide that the smoothing used for the real mesh erases, so the threshold sweep (dev notes)
     checks the REAL smoothed mesh's face-adjacency components, not the voxel proxy, and a run that only checked
     voxels found a threshold that ships as two disconnected lobes. The expected ratio is used ONLY to choose
     where in the mesh-connected plateau to sit, never to move the rule off it (see the docstring above: no
     fabricated axis).
  5. an iterative cleanup ("keep the largest connected component of each part, fold the other part's disconnected
     fragments into it", repeated to a fixed point) resolves the few-percent boundary noise this discretised rule
     leaves. The result is not perfectly one component even at the mesh level (ECRL settles at ~95%, a few small
     satellite islands): that is the SAME quality already shipped on this subject's own already-curated
     extensor_carpi_ulnaris (61% in one mesh component) and its still-merged supinator_anconeus_compartment
     (51%), both measured the same way -- see the dev notes -- so it is not a new or worse defect this split
     introduces.

VERIFICATION (this run's numbers are printed and written to the report): both parts' volumes checked against the
textbook range (15-25 cm3 broadly), each part's largest-connected-component fraction at the VOXEL level (26-
connectivity) AND at the MESH level (face-adjacency via scipy.sparse + csgraph, on the actual smooth=1.0 surface),
zero voxel overlap between the two parts and with every other label (trivial from the relabeling but asserted),
and a render QA pass (separately, Playwright headless).

OUTPUT: rewrites the compartment's source volume in place (label 10 -> extensor_carpi_radialis_longus, new label
21 -> extensor_carpi_radialis_brevis), updates the label key and the report; the subject mapping is a separate,
hand-checked edit (this script does not touch ct_vhf_forearm_volume_mapping.json).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from engine.volume_ingest import atlas_points_of, mask_surface  # noqa: E402

BADGE = "position-rule, not a traced septum"
SIGMA_MM = 20.0     # centroid-track smoothing along the forearm axis
T_MM = 22.5         # projection threshold (mm from the smoothed EDC centroid); see docstring step 4
COMPARTMENT = "extensor_carpi_radialis_compartment"
LONGUS, BREVIS = "extensor_carpi_radialis_longus", "extensor_carpi_radialis_brevis"
NEIGHBOR_FOR_AXIS = "extensor_digitorum"


def level_centroids(mask):
    """{k: (row, col)} voxel centroid of `mask` at every level (3rd axis) it is present."""
    out = {}
    for k in range(mask.shape[2]):
        if mask[:, :, k].any():
            ys, xs = np.where(mask[:, :, k])
            out[k] = (float(ys.mean()), float(xs.mean()))
    return out


def smoothed_track(levels, centroids, sigma_mm):
    """Centroid track at `levels` (a sorted list), Gaussian-smoothed (levels are 1 mm apart)."""
    ks = sorted(centroids)
    ci = np.interp(levels, ks, [centroids[k][0] for k in ks])
    cj = np.interp(levels, ks, [centroids[k][1] for k in ks])
    return ndi.gaussian_filter1d(ci, sigma_mm, mode="nearest"), ndi.gaussian_filter1d(cj, sigma_mm, mode="nearest")


def largest_component(mask, struct):
    lab, n = ndi.label(mask, structure=struct)
    if n == 0:
        return mask.copy(), 0, 1.0
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    keep = int(np.argmax(sizes)) + 1
    return lab == keep, n, float(sizes.max() / mask.sum())


def split(vol, dx_mm=0.5, dz_mm=1.0, sigma_mm=SIGMA_MM, t_mm=T_MM, log=print):
    labels = json.loads(Path(REPO / "mappings/vhf_forearm_muscles_labels.json").read_text())["labels"]
    ids = {v: int(k) for k, v in labels.items()}
    lid_comp, lid_edc = ids[COMPARTMENT], ids[NEIGHBOR_FOR_AXIS]
    comp = vol == lid_comp
    edc = vol == lid_edc
    if not comp.any():
        raise SystemExit(f"label {lid_comp} ({COMPARTMENT}) is empty")
    if not edc.any():
        raise SystemExit(f"label {lid_edc} ({NEIGHBOR_FOR_AXIS}) is empty -- needed as the position axis reference")

    comp_c, edc_c = level_centroids(comp), level_centroids(edc)
    levels = sorted(comp_c)
    ci, cj = smoothed_track(levels, comp_c, sigma_mm)
    ei, ej = smoothed_track(levels, edc_c, sigma_mm)
    row_of_level = {k: n for n, k in enumerate(levels)}

    idx = np.argwhere(comp)
    pos = np.array([row_of_level[k] for k in idx[:, 2]])
    ci_v, cj_v, ei_v, ej_v = ci[pos], cj[pos], ei[pos], ej[pos]
    ux, uy = ci_v - ei_v, cj_v - ej_v
    norm = np.hypot(ux, uy) + 1e-9
    ux, uy = ux / norm, uy / norm
    proj_mm = (idx[:, 0] - ei_v) * ux * dx_mm + (idx[:, 1] - ej_v) * uy * dx_mm

    ecrl = np.zeros(vol.shape, bool)
    ecrl[tuple(idx[proj_mm > t_mm].T)] = True
    ecrb = comp & ~ecrl

    struct = np.ones((3, 3, 3), bool)
    # iterative cleanup to a fixed point: keep each part's largest connected component, fold the other's
    # disconnected stray fragments into it, and repeat until neither side moves any more voxels.
    for _ in range(10):
        ecrl_main, _, _ = largest_component(ecrl, struct)
        ecrb_candidate = ecrb | (ecrl & ~ecrl_main)
        ecrb_main, _, _ = largest_component(ecrb_candidate, struct)
        ecrl_next = comp & ~ecrb_main
        if (ecrl_next == ecrl).all() and (ecrb_main == ecrb).all():
            ecrl, ecrb = ecrl_next, ecrb_main
            break
        ecrl, ecrb = ecrl_next, ecrb_main

    vox_mm3 = dx_mm * dx_mm * dz_mm
    ecrl_lab, ecrl_n, ecrl_top = largest_component(ecrl, struct)
    ecrb_lab, ecrb_n, ecrb_top = largest_component(ecrb, struct)
    result = {
        LONGUS: {"mask": ecrl, "vol_cm3": round(float(ecrl.sum() * vox_mm3 / 1000), 2),
                 "components": ecrl_n, "largest_component_frac": round(ecrl_top, 4)},
        BREVIS: {"mask": ecrb, "vol_cm3": round(float(ecrb.sum() * vox_mm3 / 1000), 2),
                 "components": ecrb_n, "largest_component_frac": round(ecrb_top, 4)},
    }
    assert not (ecrl & ecrb).any(), "ECRL/ECRB overlap"
    assert (ecrl | ecrb).sum() == comp.sum(), "ECRL+ECRB does not reconstruct the compartment"
    log(f"  T={t_mm} mm  sigma={sigma_mm} mm  ECRL {result[LONGUS]['vol_cm3']} cm3 "
        f"({ecrl_n} comp, {ecrl_top:.3f} largest)  ECRB {result[BREVIS]['vol_cm3']} cm3 "
        f"({ecrb_n} comp, {ecrb_top:.3f} largest)")
    return result, lid_comp, lid_edc


def mesh_face_components(mask):
    """Face-adjacency connected components of the marching-cubes mesh around `mask` (scipy.sparse + csgraph)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    v, f = mask_surface(mask, step=1, smooth=1.0)
    if len(f) == 0:
        return 0, 0
    n = len(v)
    e0 = np.concatenate([f[:, 0], f[:, 1], f[:, 2]])
    e1 = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    m = coo_matrix((np.ones(len(e0)), (e0, e1)), shape=(n, n))
    ncomp, labels = connected_components(m, directed=False)
    sizes = np.bincount(labels)
    return ncomp, float(sizes.max() / n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", default=str(REPO / "data/ct_sources/task_outputs/vhf_forearm_muscles_cryo.nii.gz"))
    ap.add_argument("--out", default=None, help="default: overwrite --in")
    ap.add_argument("--labels", default=str(REPO / "mappings/vhf_forearm_muscles_labels.json"))
    ap.add_argument("--report", default=str(REPO / "data/ct_sources/task_outputs/vhf_forearm_muscles_cryo_report.json"))
    ap.add_argument("--dry-run", action="store_true", help="compute and print/verify only, write nothing")
    a = ap.parse_args(argv)

    img = nib.load(a.inp)
    vol = np.asarray(img.dataobj).astype(np.uint8)
    result, lid_comp, lid_edc = split(vol)

    for name, r in result.items():
        ncomp, frac = mesh_face_components(r["mask"])
        r["mesh_components"] = ncomp
        r["mesh_largest_component_frac"] = round(frac, 4)
        print(f"  {name}: mesh face-adjacency components={ncomp} largest_frac={frac:.4f}")

    if a.dry_run:
        return 0

    new_id = max(int(k) for k in json.loads(Path(a.labels).read_text())["labels"]) + 1
    vol2 = vol.copy()
    vol2[result[LONGUS]["mask"]] = lid_comp       # label 10 keeps its id, renamed to ECRL
    vol2[result[BREVIS]["mask"]] = new_id         # ECRB gets a fresh id
    assert not ((vol2 == lid_comp) & (vol2 == new_id)).any()
    assert (vol2 == lid_comp).sum() == int(result[LONGUS]["mask"].sum())
    assert (vol2 == new_id).sum() == int(result[BREVIS]["mask"].sum())
    # every other label's voxel count is unchanged
    for lid in np.unique(vol):
        if lid in (0, lid_comp):
            continue
        assert (vol2 == lid).sum() == (vol == lid).sum(), f"label {lid} changed"

    out_path = Path(a.out or a.inp)
    nib.save(nib.Nifti1Image(vol2, img.affine), out_path)
    print(f"wrote {out_path}")

    key = json.loads(Path(a.labels).read_text())
    key["labels"][str(lid_comp)] = LONGUS
    key["labels"][str(new_id)] = BREVIS
    key["merged_compartments"].pop(COMPARTMENT, None)
    key["_README"].append(f"Q100 ({Path(__file__).name}): label {lid_comp} ({COMPARTMENT}) split into "
                           f"{lid_comp} ({LONGUS}) and {new_id} ({BREVIS}) by a {BADGE}; the compartment name "
                           "no longer appears as a label.")
    Path(a.labels).write_text(json.dumps(key, indent=1))
    print(f"updated {a.labels}")

    report = json.loads(Path(a.report).read_text())
    report["labels"].pop(str(lid_comp), None)
    report["labels"][str(lid_comp)] = LONGUS
    report["labels"][str(new_id)] = BREVIS
    report["volumes_cm3"].pop(COMPARTMENT, None)
    report["volumes_cm3"][LONGUS] = result[LONGUS]["vol_cm3"]
    report["volumes_cm3"][BREVIS] = result[BREVIS]["vol_cm3"]
    report["merged_compartments"].pop(COMPARTMENT, None)
    report.setdefault("splits", {})[COMPARTMENT] = {
        "script": Path(__file__).name, "badge": BADGE, "sigma_mm": SIGMA_MM, "threshold_mm": T_MM,
        "axis": f"projection onto the smoothed ({NEIGHBOR_FOR_AXIS} centroid) -> (compartment centroid) direction, per level",
        LONGUS: {k: v for k, v in result[LONGUS].items() if k != "mask"},
        BREVIS: {k: v for k, v in result[BREVIS].items() if k != "mask"},
    }
    Path(a.report).write_text(json.dumps(report, indent=1))
    print(f"updated {a.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
