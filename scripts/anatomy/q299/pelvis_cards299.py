"""Q299 Part A: the measured pelvic-proportion statements that go on the cards of the two female Z pages.

Nothing here changes geometry.  Q299 measured the pelvis of all six pages against (a) the 47 women of the Q250
reference set, segmented from CT with TotalSegmentator v2.0.1 (Zenodo 10047292, CC BY 4.0) and measured with the SAME
geometric rules, so the comparison carries no landmark-definition offset, and (b) published numbers where a rule-matched
cohort does not exist.  Two defects came out of it that are ours and not hers, and they are stated on the cards of the
structures they belong to.  The refits that would remove them are put to the owner in docs/OPEN_ITEMS_FOR_OWNER.md.

Literature used here:
  * the 47-women reference: bi-acetabular distance 176.0 +- 9.0 mm, greater sciatic notch hull angle 99.3 +- 5.6 deg,
    ischial length 80.4 +- 4.7 mm, intertuberous 106.3 +- 13.5 mm, bi-iliac breadth 280.8 +- 17.6 mm
    (data/derived/Q250_ts_women_pelvis_measures.json, n = 47, same rules as here).
  * subpubic angle female 87.4 +- 6.5 / male 68.6 +- 7.6 deg, PMID 32274246.
  * MR pelvimetry of a vaginal-delivery group, doi:10.1016/j.ejrad.2018.03.024 -- quoted only to say why it must NOT be
    compared with these numbers directly (different landmark definition; see the inlet note below).
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PELVIS = REPO / "data/derived/Q299_pelvis.json"
BONES = REPO / "data/derived/Q299_long_bones.json"

REF = {  # key: (mean, sd) of the 47 women, measured with the same rules
    "bi_acetabular": (176.0, 9.0), "sciatic_notch": (99.3, 5.6), "ischial_length": (80.4, 4.7),
    "intertuberous": (106.3, 13.5), "bi_iliac": (280.8, 17.6),
}


def notes():
    """{page_key: {structure_id: sentence}}"""
    P = json.loads(PELVIS.read_text())["pages"]
    global LB
    LB = json.loads(BONES.read_text())
    f, b, c = P["own_f"], P["base_f"], P["comb_f"]
    out = {"base_f": {}, "comb_f": {}}

    # ---- Combined F: the femora were never re-seated after Q250 deformed her pelvis ----
    cf = c["interfemoral_head_mm"]; hers = f["interfemoral_head_mm"]; bf = b["interfemoral_head_mm"]
    m, s = REF["bi_acetabular"]
    seat = (f" || Q299 pelvic proportions, measured on THIS page. Distance between the two femoral-head centres "
            f"(bi-acetabular distance) {cf:.1f} mm. Her own CT pelvis, on the Imaging-based Female page, gives "
            f"{hers:.1f} mm and the Base Female page {bf:.1f} mm; the reference is {m:.1f} +- {s:.1f} mm over 47 women "
            f"segmented from CT and measured with the SAME geometric rules (Q250, TotalSegmentator v2.0.1, Zenodo "
            f"10047292, CC BY 4.0). So this page is {cf - hers:+.1f} mm wider than HER OWN pelvis and {(cf - m) / s:+.2f} "
            f"standard deviations off the reference, while her own pelvis is {(hers - m) / s:+.2f} SD -- genuinely a wide "
            f"female pelvis, but not this wide. The cause is recorded in Q250: on this page the Z-Anatomy pelvic bones "
            f"were deformed onto HER pelvis while the femora were left rigidly fitted and were never re-seated, and "
            f"Q250's own joint check shows the left hip joint opening from 1.0 to 5.3 mm. Both femoral heads therefore "
            f"sit lateral to her acetabula and the thighs are splayed. Re-seating them means moving each femur and its "
            f"whole distal chain with the limb soft tissue, which Q299 did not attempt; see docs/OPEN_ITEMS_FOR_OWNER.md.")
    notch = (f" || Q299: the greater sciatic notch of this page measures {c['sciatic_notch_hull_angle_deg']:.1f} deg by the "
             f"convex-hull-defect rule, against {f['sciatic_notch_hull_angle_deg']:.1f} deg on her own CT pelvis, "
             f"{b['sciatic_notch_hull_angle_deg']:.1f} deg on the Base Female page (the same Z meshes under a different "
             f"deformation) and {REF['sciatic_notch'][0]:.1f} +- {REF['sciatic_notch'][1]:.1f} deg over the 47-women "
             f"reference measured with the same rule. This page is "
             f"{(c['sciatic_notch_hull_angle_deg'] - REF['sciatic_notch'][0]) / REF['sciatic_notch'][1]:+.2f} SD: the "
             f"Q250 pelvis deformation closed her notch by about "
             f"{f['sciatic_notch_hull_angle_deg'] - c['sciatic_notch_hull_angle_deg']:.0f} deg on this page. Every other "
             f"classical pelvimetry measure of this page is within 1 SD of that reference (inlet transverse, AP "
             f"conjugate, intertuberous, subpubic angle, bi-iliac breadth, pelvic height, sacral breadth and length).")
    for sid in ("femur_l", "femur_r"):
        out["comb_f"][sid] = seat
    for sid in ("hip_bone_l", "hip_bone_r"):
        out["comb_f"][sid] = seat + notch

    # ---- Base F: the ischium, and the shoulder-girdle proportion ----
    mi, si = REF["ischial_length"]; mt, st = REF["intertuberous"]
    isch = (f" || Q299 pelvic proportions, measured on THIS page. Ischial length (femoral-head centre to the furthest "
            f"postero-inferior point of the ischium) {b['ischial_length_r_mm']:.1f} mm right / {b['ischial_length_l_mm']:.1f} "
            f"left, against {f['ischial_length_r_mm']:.1f} / {f['ischial_length_l_mm']:.1f} mm on her own CT pelvis and "
            f"{mi:.1f} +- {si:.1f} mm over the 47-women reference measured with the same rule "
            f"({(b['ischial_length_r_mm'] - mi) / si:+.2f} SD). Intertuberous distance {b['intertuberous_mm']:.1f} mm "
            f"against her {f['intertuberous_mm']:.1f} mm and {mt:.1f} +- {st:.1f} mm "
            f"({(b['intertuberous_mm'] - mt) / st:+.2f} SD). So the inferior pelvis of this page is about "
            f"{b['intertuberous_mm'] - f['intertuberous_mm']:.0f} mm wider and {b['ischial_length_r_mm'] - f['ischial_length_r_mm']:.0f} mm "
            f"longer than HER OWN ischium: the Q250 non-rigid registration of the Z pelvis onto her CT hip bones did not "
            f"converge in its weakest region, which Q250 itself named. Everything else is within about 1.5 SD of the "
            f"reference: bi-iliac {b['bi_iliac_breadth_mm']:.1f} mm "
            f"({(b['bi_iliac_breadth_mm'] - REF['bi_iliac'][0]) / REF['bi_iliac'][1]:+.2f} SD), subpubic angle "
            f"{b['subpubic_angle_deg']:.1f} deg (literature female 87.4 +- 6.5, PMID 32274246), pelvic height "
            f"{b['pelvic_height_mm']:.1f} mm, sacral breadth {b['sacral_breadth_mm']:.1f} mm.")
    girdle = (f" || Q299 shoulder-to-hip proportion, measured on THIS page. Bicristal (iliac-crest) breadth "
              f"{b['bicristal_mm']:.1f} mm divided by biacromial breadth {b['biacromial_mm']:.1f} mm = "
              f"{b['bicristal_over_biacromial']:.3f}. On HER OWN body (Imaging-based Female, her CT bones) the same rule "
              f"gives {f['bicristal_mm']:.1f} / {f['biacromial_mm']:.1f} = {f['bicristal_over_biacromial']:.3f}, and on the "
              f"three male pages {P['own_m']['bicristal_over_biacromial']:.3f} / {P['base_m']['bicristal_over_biacromial']:.3f} "
              f"/ {P['comb_m']['bicristal_over_biacromial']:.3f}. Her pelvis really is wide for her shoulders; but this page "
              f"is {100 * (b['bicristal_over_biacromial'] / f['bicristal_over_biacromial'] - 1):.1f} % more hip-dominant "
              f"than her own body, and that part is ours. The reason is this girdle: Base Female keeps Z-Anatomy's clavicle "
              f"and scapula scaled by her segment factors rather than registered onto her own scapulae, so on this page the "
              f"clavicle is {LB['base_f']['clavicle_r']:.1f} mm where hers is {LB['own_f']['clavicle_r']:.1f}, the "
              f"scapula {LB['base_f']['scapula_r']:.1f} mm where hers is {LB['own_f']['scapula_l']:.1f} / "
              f"{LB['own_f']['scapula_r']:.1f}, and the two acromia sit "
              f"{f['biacromial_mm'] - b['biacromial_mm']:.1f} mm closer together than hers. No rule-matched cohort exists for "
              f"this ratio (the 47-women reference has no scapulae), so the comparison above is page against her own body, "
              f"which is the strongest available. Registering the girdle onto her scapulae is put to the owner in "
              f"docs/OPEN_ITEMS_FOR_OWNER.md.")
    for sid in ("hip_bone_l", "hip_bone_r"):
        out["base_f"][sid] = isch + girdle
    for sid in ("clavicle_l", "clavicle_r", "scapula_l", "scapula_r"):
        out["base_f"][sid] = girdle
    return out


if __name__ == "__main__":
    n = notes()
    for k, v in n.items():
        print("==", k)
        for sid, s in v.items():
            print(f"  {sid}: {len(s)} chars")
            print("   ", s[:400].replace("\n", " "), "...")
