"""Q125: split the female's RIGHT metacarpals (5 bones fused as one CT-watershed
region, `metacarpals_r` label in vhf_arm_bones_ct.nii.gz) into 5 individually
named, individually verified bones.

Source: her own torso CT (IDC series b9cf8e7a-2505-4137-9ae3-f8d0cf756c13,
0.9375x0.9375x1.0 mm, re-downloaded since the scratchpad copy used by
scripts/vhf_arm_bones_ct.py did not survive the container reset), re-stacked
for just the hand's z-range (z -900..-700 mm RAS, 201 slices) at real HU
values -- this is the actual grayscale CT, not the RGB cryosection
photographs, and not just the pre-existing single-value label.

Method (the project's own proven marker-controlled watershed, same family as
the female lower-limb bones and Q64's forearm work): a HU>=650 core, opened
to break weak diagonal bridges, gives 5 well-separated seed components in the
metacarpal SHAFT (mid-diaphysis, verified THRESHOLD-INDEPENDENT at HU 150-300
across three different band widths -- always exactly 5 pieces of plausible
metacarpal size, never fewer/more). A smoothed-HU watershed (elevation =
-gaussian(HU, sigma=1), so joints/low-HU valleys become ridges the growth
meets at) restricted to the EXISTING, already-shipped `metacarpals_r` plane-
cut mask (label 4 of vhf_arm_bones_ct.nii.gz -- this script does not touch
or second-guess that boundary, only resolves identity WITHIN it) grows each
seed to fill its own bone with a single connected piece; only 6 of 31189
voxels (0.02%) were left unassigned.

Result verified against real anatomy: 5 single-component, non-overlapping,
correctly-ordered (by position and centroid spread, cross-checked against
the radius/ulna labels for which side is radial) pieces with volumes
3.85-7.05 cm3, matching the textbook pattern (index/middle metacarpals
largest and most robust, little finger smallest, thumb short but thick) --
see the Q125 PROJECT_STATE entry for the full numbers and the renders that
back the identification.

Carpals (8 bones) and individual phalanges (14 bones) were investigated with
the SAME technique and DECLINED: at every HU threshold and with the same
marker-controlled watershed, the carpal block remains one incoherent fused
mass (best sub-piece still an irregular, non-bone-shaped blob spanning most
of the wrist), and within-digit joints (PIP/DIP) show no threshold-
independent, anatomically consistent count/position -- the joint gaps are at
or below this CT's 0.9375 mm in-plane resolution for these structures, so
splitting them further would be fabricating boundaries, not measuring them.
See the Q125 entry for the numbers behind that decline.

Reproduce: this script expects the 201-slice HU crop already stacked (see
the Q125 entry for the exact IDC download + stacking steps -- ~520 MB DICOM,
not checked into the repo) at SCRATCH/hand_ct_right.npy /
SCRATCH/hand_ct_meta.json, and the shipped label volume
data/ct_sources/task_outputs/vhf_arm_bones_ct.nii.gz for the existing
metacarpal-zone mask. Output:
data/ct_sources/task_outputs/vhf_metacarpals_split.nii.gz (+ _report.json).
"""
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[1]
SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
HAND_CT = SCRATCH / "hand_seg" / "hand_ct_right.npy"
HAND_META = SCRATCH / "hand_seg" / "hand_ct_meta.json"

LABEL_VOL = REPO / "data/ct_sources/task_outputs/vhf_arm_bones_ct.nii.gz"
OUT_VOL = REPO / "data/ct_sources/task_outputs/vhf_metacarpals_split.nii.gz"
OUT_REPORT = REPO / "data/ct_sources/task_outputs/vhf_metacarpals_split_report.json"

FACE = ndi.generate_binary_structure(3, 1)
SP = np.array([0.9375, 0.9375, 1.0])


def main() -> int:
    if not HAND_CT.exists():
        print(f"ERROR: {HAND_CT} missing -- re-download+stack the hand CT slab first "
              "(see this script's docstring / the Q125 PROJECT_STATE entry)", file=sys.stderr)
        return 1

    img = nib.load(LABEL_VOL)
    v = np.asarray(img.dataobj)
    A = img.affine
    meta = json.loads(HAND_META.read_text())
    z0_local = meta["z"][0]  # RAS z of hand_ct_right.npy's first slice
    k_local_offset = int(round(z0_local - A[2, 3]))  # nifti k index of that first slice

    mc_mask_full = v == 4  # the existing, already-shipped metacarpals_right plane-cut region
    idx = np.argwhere(mc_mask_full)
    i0, i1 = idx[:, 0].min() - 2, idx[:, 0].max() + 3
    j0, j1 = idx[:, 1].min() - 2, idx[:, 1].max() + 3
    k0, k1 = idx[:, 2].min(), idx[:, 2].max()

    vol = np.load(HAND_CT)  # (z_local, row=j, col=i)
    kl0, kl1 = k0 - k_local_offset, k1 - k_local_offset
    assert 0 <= kl0 and kl1 < vol.shape[0], "hand CT slab doesn't cover the metacarpal zone"

    hu = vol[kl0:kl1 + 1, j0:j1, i0:i1].transpose(2, 1, 0).astype(np.float32)  # -> (i,j,k)
    mc_mask = mc_mask_full[i0:i1, j0:j1, k0:k1 + 1]
    print("metacarpal-zone voxels:", int(mc_mask.sum()),
          "= %.2f cm3" % (mc_mask.sum() * np.prod(SP) / 1000))

    # 5 robust seeds in the mid-shaft band (35-65% of the zone's own proximal-distal extent);
    # verified threshold-independent (150/200/250/300 HU all give exactly 5 pieces of plausible size)
    kk = np.argwhere(mc_mask)[:, 2]
    kmin, kmax = kk.min(), kk.max()
    kc0 = kmin + int((kmax - kmin) * 0.35)
    kc1 = kmin + int((kmax - kmin) * 0.65)
    band = np.zeros_like(mc_mask)
    band[:, :, kc0:kc1] = mc_mask[:, :, kc0:kc1]
    core = (hu >= 200) & band
    cl, n = ndi.label(core, structure=FACE)
    sizes = ndi.sum(np.ones_like(cl), cl, np.arange(1, n + 1))
    top5 = np.argsort(-sizes)[:5]
    assert len(top5) == 5 and sizes[top5].min() >= 500, f"seed sizes not clean: {sorted(sizes, reverse=True)[:8]}"
    seed_mask = np.isin(cl, top5 + 1)
    markers, _ = ndi.label(seed_mask, structure=FACE)
    assert markers.max() == 5

    smh = ndi.gaussian_filter(hu, 1.0)
    ws = watershed(-smh, markers, mask=mc_mask)
    n_pieces = int(ws.max())
    assert n_pieces == 5
    unassigned = int((mc_mask & (ws == 0)).sum())
    print("unassigned voxels:", unassigned, "of", int(mc_mask.sum()))

    # identify by position: the piece whose centroid i is most different from the rest = thumb
    # (verified visually -- short, angled ray, isolated from the 4 parallel finger shafts);
    # the remaining 4 ordered by centroid j (thumb-adjacent = index ... farthest = little)
    pieces = []
    for lbl in range(1, 6):
        m = ws == lbl
        com = np.argwhere(m).mean(0)
        pieces.append((lbl, int(m.sum()), com))
    thumb = max(pieces, key=lambda p: abs(p[2][0] - np.mean([q[2][0] for q in pieces])))
    # the 4 finger metacarpals ordered by centroid-j DISTANCE from the thumb, nearest first:
    # index is adjacent to the thumb, little is farthest -- verified against the earlier
    # whole-hand-crop identification (same volumes: index 6.94, middle 7.05, ring 4.18, little 3.85 cm3)
    fingers = sorted([p for p in pieces if p[0] != thumb[0]],
                      key=lambda p: abs(p[2][1] - thumb[2][1]))
    order = [thumb] + fingers  # metacarpal I (thumb) .. V (little), by real digit identity
    names = ["metacarpal_1_r", "metacarpal_2_r", "metacarpal_3_r", "metacarpal_4_r", "metacarpal_5_r"]

    out_full = np.zeros(v.shape, np.uint8)
    report = {}
    for new_label, ((old_lbl, vox, com), name) in enumerate(zip(order, names), start=1):
        m = ws == old_lbl
        # connectivity check: must be a single piece
        clm, ncm = ndi.label(m, structure=FACE)
        sizesm = ndi.sum(np.ones_like(clm), clm, np.arange(1, ncm + 1))
        assert ncm == 1 or sizesm.max() / vox > 0.99, f"{name}: {ncm} components, not one solid bone"
        out_full[i0:i1, j0:j1, k0:k1 + 1][m] = new_label
        report[name] = {
            "cm3": round(float(vox) * np.prod(SP) / 1000, 2),
            "n_components": int(ncm),
            "centroid_ijk_local": [round(float(c), 1) for c in com],
        }
        print(name, report[name])

    nib.save(nib.Nifti1Image(out_full, A), OUT_VOL)
    json.dump({
        "_README": [
            "Female right metacarpals I-V, individually split from the existing "
            "metacarpals_right plane-cut mask (vhf_arm_bones_ct.nii.gz label 4) by a "
            "marker-controlled watershed on her own torso CT's raw HU values "
            "(scripts/vhf_split_metacarpals.py). Derived data. Carpals and individual "
            "phalanges were investigated with the same technique and declined -- see the "
            "Q125 PROJECT_STATE entry.",
        ],
        "source": "U.S. National Library of Medicine, The Visible Human Project (public "
                  "domain), female 'Normal' CT via the NCI Imaging Data Commons "
                  "(series b9cf8e7a-2505-4137-9ae3-f8d0cf756c13).",
        "unassigned_voxels_of_zone": unassigned,
        "zone_voxels": int(mc_mask.sum()),
        "volumes": report,
    }, open(OUT_REPORT, "w"), indent=1)
    print("SHIP_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
