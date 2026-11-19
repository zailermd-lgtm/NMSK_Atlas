"""Male styloglossus (intralingual portion only) from his OWN CT tongue label -- no cryosections needed (Q92).

    python3 scripts/cryo/vhm_styloglossus_from_ct.py            # writes the volume, prints the report
    python3 scripts/cryo/vhm_styloglossus_from_ct.py --out data/ct_sources/task_outputs

BACKGROUND. Q91 recovered genioglossus_r/l from the male's own CT tongue label
(`vhm_head_muscles.nii.gz` label 9) using a purely positional rule ported from her
`vhf_hyoid_muscles_from_cryo.py`'s `tongue_rules()`, and flagged mylohyoid, geniohyoid, hyoglossus and
styloglossus -- currently shipped on him only via the cross-body transfer `xfer_vhf2vhm_neck` -- as
possibly similarly recoverable. This session (Q92) checked all four against the SAME bar (does the rule
need only CT-visible position, or does it need cryosection photograph texture/colour to separate the
muscle from a neighbour) and found the four split 1 (recoverable) / 3 (not):

  - mylohyoid, geniohyoid: her `floor_rules()` splits them INSIDE the "floor of mouth" compartment, and
    that compartment itself (`floor_compartment()`) is defined as `M["dark"]` (her cryo photograph's dark
    muscle CLASS, thresholded on brightness) intersected with a CT-geometric box (inside the mandibular
    arch, above the hyoid, below the tongue). Nothing in the male's CT labels (`total`, `head_muscles`,
    `headneck_bones_vessels`, `headneck_muscles_merged`, `craniofacial_structures`) segments the
    submandibular/sublingual glands or subcutaneous fat that also fill that space -- her own script's data
    docstring does not list a gland CT label either; her gland exclusion is ENTIRELY from the cryo
    photograph's pale colour class. So on CT alone there is no way to tell muscle from gland/fat inside the
    floor-of-mouth box: 0% of mylohyoid or geniohyoid lies inside the male's CT tongue label (both muscles
    are entirely extralingual, below the tongue), so neither has any CT-native "already a muscle" mask the
    way the tongue label gives genioglossus one. NOT ATTEMPTED; left on the transfer.
  - hyoglossus: her rule builds it from TWO sources -- `floor_rules()`'s "hg" sheet (needs the same
    cryo-dark floor compartment as mylohyoid/geniohyoid) AND `tongue_rules()`'s "hg" (purely positional,
    inside the CT tongue label). Probed her OWN CT tongue label with `tongue_rules()`'s exact hg formula
    (dxT >= 10 mm of the tongue's own centroid, gT > 0.5, zT < 0.4) and compared to her actual shipped
    hyoglossus_r/l (4.0 + 5.4 = 9.4 cm3): the tongue-only portion is only 1.98 cm3, ~21% of her real
    muscle. The other ~79% is the floor sheet, i.e. needs cryo texture. Shipping just the CT-tongue
    fragment for the male would be a small, unrepresentative sliver at the tongue's postero-lateral margin,
    not a recognizable hyoglossus (a flat quadrilateral sheet whose bulk sits BELOW the tongue). NOT
    ATTEMPTED; left on the transfer -- would degrade rather than improve on it.
  - styloglossus: same two-source structure -- a CORRIDOR from the styloid process (needs `M["dark"]`
    again, to keep the corridor on muscle and off parapharyngeal fat) PLUS a `tongue_rules()` "sg" portion
    (purely positional). Same probe: her tongue-only sg (dxT >= 15 mm, gT > 0.55, zT >= 0.5, below the
    dorsum) gives 3.53 cm3 vs her actual shipped total 3.3 cm3 (1.8 + 1.5) -- i.e. essentially ALL of her
    styloglossus volume is already inside the CT tongue label (the corridor segment between the styloid and
    the tongue is anatomically a slender cord that contributes little bulk; the muscle fans out and
    interdigitates with the tongue's intrinsic fibres over most of its length). This is the one of the four
    where the CT-only fraction is representative, not a sliver. ATTEMPTED here (his styloid process IS
    present in his own CT: `vhm_headneck_bones_vessels.nii.gz` carries labels 7/8, same ids as her file --
    but that landmark ended up NOT NEEDED, exactly as genioglossus's floor-of-mouth extension was not
    needed for Q91: this rule stays entirely inside the tongue label).

RULE (Standring, Gray's Anatomy 42nd ed., ch. 30 'Oral cavity'; replicated from her `tongue_rules()`,
precedence-matched against the ALREADY-SHIPPED genioglossus mask so there is zero overlap by construction):
per axial CT slice within the tongue label's own z-range, per L-R column, using the SAME per-column AP
fraction gT as `vhm_genioglossus_from_ct.py`, a height fraction zT (0 = the tongue label's most inferior
slice, 1 = its most superior, her convention) -- and, UNLIKE genioglossus, the lateral distance dxT is
measured from the TONGUE LABEL'S OWN per-slice centroid, not the mandibular midline. This matches her
original `tongue_rules()` exactly (dxT relative to cmT): tried the mandible-midline reference first (for
consistency with the shipped genioglossus) and it collapsed styloglossus to ~0 cm3, because the male's
tongue centroid sits measurably off the mandible's symmetry axis at these levels and 15 mm from the WRONG
axis leaves almost nothing inside the tongue label (its own max half-width from the mandible axis is only
16.8 mm). Genioglossus is anatomically paramedian to the mandibular symphysis specifically (its origin), so
the mandible reference was correct there; styloglossus/hyoglossus are positioned relative to how far they
sit from the BULK OF THE TONGUE, which is what her original tongue-centroid dxT measures, so it is kept
here as she used it:
  gg  = the already-shipped ct_vhm_ggl mask (loaded, not recomputed) -- guarantees zero overlap;
  hg  = tongue & ~gg & dxT >= 10 mm (of the tongue's own centroid) & gT > 0.5 & zT < 0.4   (computed only
        as an EXCLUSION zone -- not shipped; matches her precedence so styloglossus does not eat into it);
  sg  = tongue & ~gg & ~hg & below_dorsum & dxT >= 15 mm & gT > 0.55 & zT >= 0.5           (SHIPPED).
below_dorsum: at or below 8 mm under the dorsum (the tongue label's own top 8 mm, DORSUM_MM, matching her
value and Q91's genioglossus rule).

NOT attempted: the extralingual (styloid-to-tongue corridor) portion of styloglossus -- outside the CT
tongue label entirely, and (per the probe above) needs cryo photograph texture to build safely; this ships
only the intralingual fanning bulk, same style of partial-but-honest ship as Q91's genioglossus (which also
excludes its floor-of-mouth extension).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
TASK_DIR = REPO / "data/ct_sources/task_outputs"
HM_TONGUE = 9
CF_MANDIBLE = 1
HG_T_W_MM, SG_T_W_MM = 10.0, 15.0    # her HG_T_W_MM, SG_T_W_MM
HG_T_G, SG_T_G = 0.5, 0.55           # her HG_T_G, SG_T_G
HG_T_Z, SG_T_Z = 0.4, 0.5            # her HG_T_Z, SG_T_Z
DORSUM_MM = 8.0                       # her DORSUM_MM


def build(task_dir: Path):
    hm_img = nib.load(task_dir / "vhm_head_muscles.nii.gz")
    hm = np.asarray(hm_img.dataobj)
    aff = hm_img.affine
    cf = np.asarray(nib.load(task_dir / "vhm_craniofacial_structures.nii.gz").dataobj)
    gg_img = nib.load(task_dir / "vhm_genioglossus_ct.nii.gz")
    gg_lab = np.asarray(gg_img.dataobj)
    assert gg_img.shape == hm.shape and np.allclose(gg_img.affine, aff), "genioglossus grid must match head_muscles grid"

    tongue = hm == HM_TONGUE
    mand = cf == CF_MANDIBLE
    gg_r_shipped = gg_lab == 1
    gg_l_shipped = gg_lab == 2
    sx, sy, sz = aff[0, 0], aff[1, 1], aff[2, 2]
    tx, ty, tz = aff[0, 3], aff[1, 3], aff[2, 3]

    # mandibular midline anchor (x0, mm), same as vhm_genioglossus_from_ct.py
    i_m, j_m, k_m = np.where(mand)
    x0 = (tx + sx * i_m).mean()
    i0 = (x0 - tx) / sx

    kk = np.where(tongue.any(axis=(0, 1)))[0]
    k_min, k_max = int(kk.min()), int(kk.max())
    below_dorsum_kmax = k_max - DORSUM_MM / abs(sz)

    I, _ = np.indices(tongue.shape[:2])
    side = I - i0                              # >0 -> patient LEFT (sx<0), <0 -> patient RIGHT

    sg_r = np.zeros(tongue.shape, bool)
    sg_l = np.zeros(tongue.shape, bool)
    hg_r = np.zeros(tongue.shape, bool)        # exclusion-only, not shipped
    hg_l = np.zeros(tongue.shape, bool)
    for k in range(k_min, k_max + 1):
        T2 = tongue[:, :, k]
        if not T2.any():
            continue
        cmT = float(np.where(T2)[1].mean())    # the tongue label's OWN centroid at this level (her convention)
        dxT_mm = np.abs((I - cmT) * abs(sx))
        gT = np.full(T2.shape, -1.0)
        for c in np.where(T2.any(axis=1))[0]:
            js = np.where(T2[c])[0]
            j0, j1 = js.min(), js.max()
            gT[c, js] = (js - j0) / max(j1 - j0, 1)
        zT = (k - k_min) / max(k_max - k_min, 1)
        below_dorsum = k <= below_dorsum_kmax

        gg_here = gg_r_shipped[:, :, k] | gg_l_shipped[:, :, k]
        hg = T2 & ~gg_here & (dxT_mm >= HG_T_W_MM) & (gT > HG_T_G) & (zT < HG_T_Z)
        sg = T2 & ~gg_here & ~hg & below_dorsum & (dxT_mm >= SG_T_W_MM) & (gT > SG_T_G) & (zT >= SG_T_Z)

        hg_r[:, :, k] = hg & (side < 0); hg_l[:, :, k] = hg & (side > 0)
        sg_r[:, :, k] = sg & (side < 0); sg_l[:, :, k] = sg & (side > 0)

    def largest_component(mask):
        lbl, n = ndi.label(mask)
        if n <= 1:
            return mask
        sizes = ndi.sum(mask, lbl, range(1, n + 1))
        return lbl == (int(np.argmax(sizes)) + 1)

    sg_r = largest_component(sg_r)
    sg_l = largest_component(sg_l)

    vol_mm3 = abs(sx * sy * sz)
    report = {
        "styloglossus_r_cm3": round(sg_r.sum() * vol_mm3 / 1000, 2),
        "styloglossus_l_cm3": round(sg_l.sum() * vol_mm3 / 1000, 2),
        "hyoglossus_excl_zone_r_cm3": round(hg_r.sum() * vol_mm3 / 1000, 2),   # not shipped: sanity print only
        "hyoglossus_excl_zone_l_cm3": round(hg_l.sum() * vol_mm3 / 1000, 2),
        "tongue_total_cm3": round(tongue.sum() * vol_mm3 / 1000, 2),
        "genioglossus_shipped_overlap_check_r": int((sg_r & gg_r_shipped).sum()),
        "genioglossus_shipped_overlap_check_l": int((sg_l & gg_l_shipped).sum()),
        "mandible_midline_x0_mm": round(float(x0), 3),
    }
    for name, mask in (("styloglossus_r", sg_r), ("styloglossus_l", sg_l)):
        lbl, n = ndi.label(mask)
        sizes = ndi.sum(mask, lbl, range(1, n + 1)) if n else []
        report[f"{name}_components"] = int(n)
        report[f"{name}_largest_frac"] = round(float(max(sizes) / mask.sum()), 4) if n else None

    lab = np.zeros(tongue.shape, np.uint8)
    lab[sg_r] = 1
    lab[sg_l] = 2
    return nib.Nifti1Image(lab, aff), report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task-dir", default=str(TASK_DIR))
    ap.add_argument("--out", default=str(TASK_DIR))
    a = ap.parse_args()
    img, report = build(Path(a.task_dir))
    out = Path(a.out) / "vhm_styloglossus_ct.nii.gz"
    nib.save(img, out)
    print("wrote", out)
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
