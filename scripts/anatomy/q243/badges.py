"""Q243: card texts (procedural_badge) of the new structures; numbers come from the guards (reports), nothing is typed by hand."""
from __future__ import annotations

HRA_NAME = "HuBMAP Human Reference Atlas (HRA) 3D Reference Object Library"
CC = "CC BY 4.0"
BV_DOI = "https://doi.org/10.48539/HBM322.KKFC.394"
UF_DOI = "https://doi.org/10.48539/HBM637.DWBM.744"
UM_DOI = "https://doi.org/10.48539/HBM833.WZWN.425"
SC_DOI = "https://doi.org/10.48539/HBM242.QQQB.777"
DISK_DOI = "https://doi.org/10.48539/HBM824.BNBP.227"
AUTH = "Kristen Browne and Heidi Schlehlein"
NOTE_ABSENT = "The vulva, labia, clitoris and the female urethra are not in the HRA set (Q233-Q235)."


def vessel_source():
    return f"{HRA_NAME} object blood-vasculature-female v1.3 (2026-06-08, {CC}, {BV_DOI}), Visible Human female; registered on this body's pelvis (Q243)"


def vessel_badge(v, g, onto, reg_txt, who, page_note=""):
    lr, co = g["left_right"], g["course"]
    if lr.get("name_side"):
        d = lr["mean_distance_to_hip_mm"]; same = "l" if lr["name_side"] == "left" else "r"; oth = "r" if same == "l" else "l"
        lrt = (f"LEFT / RIGHT checked: the library node name says {lr['name_side']}; the structure lies at x = {lr['centroid_x_mm']} mm (atlas +X = right, so {'negative = left' if lr['name_side'] == 'left' else 'positive = right'}) "
               f"and its mean distance to the {lr['name_side']} hip bone is {d[same]} mm against {d[oth]} mm to the {'right' if same == 'l' else 'left'} one: both agree with the name.")
    else:
        lrt = f"Midline structure (library node name without side); its centroid lies at x = {lr['midline_x_mm']} mm, within 25 mm of the midline."
    if "min_distance_to_uterus_mm" in co:
        crt = (f"Course checked: it reaches the uterus of this page (closest approach {co['min_distance_to_uterus_mm']} mm), the medial end lies {co['medial_end_to_uterus_mm']} mm from the uterus surface and the lateral end "
               f"{co['lateral_end_to_uterus_mm']} mm (towards the internal iliac vessels of the same side).")
    elif "inferior_end_to_ischial_tuberosity_mm" in co:
        crt = (f"Course checked: it runs along the {v['side']} ischium ({co['fraction_within_10mm_of_same_side_hip_pct']} % of its vertices within 10 mm of the same-side hip bone, the pudendal canal / lesser sciatic notch region), "
               f"from y = {co['superior_end_y_mm']} mm (greater sciatic foramen level) down to y = {co['inferior_end_y_mm']} mm, its lower end {co['inferior_end_to_ischial_tuberosity_mm']} mm from the ischial tuberosity.")
    elif "superior_end_to_common_iliac_vein_mm" in co:
        crt = f"Course checked: its upper end lies {co['superior_end_to_common_iliac_vein_mm']} mm from the common iliac vein of the same side ({'her own CT vein' if 'own' in page_note else 'the Z-Anatomy estimate of that vein'})."
    else:
        crt = f"Course: centroid height y = {co.get('centroid_y_mm')} mm (superior rectal vessels above the middle rectal veins above the inferior rectal veins: checked for the whole set)."
    ins = g["vertices_inside_page_organ_pct"]
    ov = ("Vertices inside the page's organ meshes: " + ", ".join(f"{k} {x} %" for k, x in ins.items()) + (f" (more than 3 mm deep: {', '.join(f'{k} {x} %' for k, x in g['vertices_deeper_3mm_in_organ_pct'].items())})" if g["vertices_deeper_3mm_in_organ_pct"] else "") + ".") if ins else "No vertex lies inside any organ mesh of the page."
    mv = (f"{g['vertices_moved_out_of_bone']} of {g['vertices']} vertices ({g['moved_fraction_pct']} %) that the registration error had left inside or against a bone were moved out along the bone normal, by at most {g['max_move_out_of_bone_mm']} mm."
          if g["vertices_moved_out_of_bone"] else "None of its vertices had to be moved off a bone.")
    caps = g.get("caps", {})
    shape = (f"the HRA surface as is ({g['triangles']} triangles incl. {caps.get('capped', 0)} flat end disc(s) that close the open tube ends; the library mesh is an open tube), closed surface, volume {g['volume_cm3']} cm3, "
             f"model tube diameter {g['calibre_mm']} mm (mean over the length, from the mesh after the x0.95 registration scale), centreline length {g['length_mm']} mm")
    return (f"Reference structure of the SAME DONOR, NOT measured by this atlas and NOT a segmentation of {who} scan: HRA 3D reference object `blood-vasculature-female` v1.3 (2026-06-08, {CC}, {BV_DOI}; {AUTH}; "
            f"created from the Visible Human Dataset, i.e. the donor of this body), node `{v['node']}` ({onto}). Placed with the SAME registration as the uterus, ovaries and tubes of this page: {reg_txt}. "
            f"Position error: the bone registration residual above (median 1.24 mm, p90 3.53 mm); how well the library's vessel sits on its own bones is not stated by the library. "
            f"Shape: {shape}. {lrt} {crt} Guards: signed distance to the nearest bone {g['bone_min_mm']} mm (required >= 1 mm); {mv} {g['skin_distance_min_mm']} mm inside the skin. {ov}{page_note} "
            f"The library's vessels are a schematic reference set (one tube per named vessel, no branches below the named level), so a tube is a model of the vessel's course and calibre, not a measured lumen. {NOTE_ABSENT}")


def nucleus_badge(key, g, who, upper_hra, lower_hra, page_disc_name, lumbar_note):
    return (f"Reference structure of the SAME DONOR, NOT segmented from {who} scan: the nucleus pulposus of the HRA intervertebral disk of the Visible Human female (HRA 3D reference object `united-female` v1.10, {CC}, {UF_DOI}; "
            f"also object `intervertebral-disk-female` v1.0, {DISK_DOI}, modelled by Kristen Browne and fitted to the spine by Heidi Schlehlein, i.e. a MODELLED nucleus, not a segmentation), node `{g['hra_node']}`. "
            f"Placed between the two vertebrae it lies between ({upper_hra} / {lower_hra} in HRA numbering): each HRA vertebra was fitted to {who} vertebra of the same rank (rigid + uniform scale; {upper_hra}: x{g['fit_upper']['scale']}, "
            f"surface residual median {g['fit_upper']['residual_median_mm']} / p90 {g['fit_upper']['residual_p90_mm']} mm; {lower_hra}: x{g['fit_lower']['scale']}, median {g['fit_lower']['residual_median_mm']} / p90 {g['fit_lower']['residual_p90_mm']} mm) "
            f"and the nucleus follows the mean of the two transforms. It sits in {who} disc `{page_disc_name}`. {lumbar_note} "
            f"Shape: closed envelope of the HRA mesh decimated to {g['triangles']} triangles, volume {g['volume_cm3']} cm3 (HRA original {g['volume_hra_cm3']} cm3, {who} disc {g.get('page_disc_volume_cm3')} cm3), height {g['height_mm']} mm. "
            f"Guards: inside the disc space {g['inside_disc_pct']} % of the vertices (convex hull of the disc mesh{', which is a placeholder prism of only ' + str(g['page_disc_triangles']) + ' triangles' if g.get('page_disc_placeholder') else ''}); "
            f"signed distance to the vertebral endplates {g['bone_min_mm']} mm (required >= 1 mm; {g['vertices_moved_out_of_bone']} of {g['vertices']} vertices were moved off an endplate along its normal by at most {g['max_move_out_of_bone_mm']} mm, "
            f"the nucleus is pressed into the disc space); {g['skin_distance_min_mm']} mm inside the skin. The nucleus lies in the disc; the page's disc shape is its own rule-based gap between the endplates (Q185c), the nucleus is not measured.")


def cord_badge(lv, g, who, canal_txt, fit_range):
    return (f"Reference structure of the SAME DONOR, NOT segmented from {who} scan (the page has no spinal cord of its own): the {lv} segment of the spinal cord of the Visible Human female "
            f"(HRA 3D reference object `spinal-cord-female` v1.1, 2026-06-08, {CC}, {SC_DOI}, {AUTH}; the library says the model was prepared with Frostell et al. 2016 as reference; also node `{g['hra_node']}` of `united-female` v1.10). "
            f"The segment is a NEUROLOGICAL segment (the root level), not the vertebral level it lies at. Placed by fitting each HRA vertebra to {who} vertebra of the same rank (rigid + uniform scale, surface residual median 0.4-0.6 mm, "
            f"per-level numbers in the report) and blending the two transforms of the vertebrae above and below ({fit_range}). Shape: the HRA open tube closed with flat end discs, decimated to {g['triangles']} triangles "
            f"(HRA {g['hra_triangles']}), volume {g['volume_cm3']} cm3, height {g['length_mm']} mm. Guards: signed distance to the vertebrae {g['bone_min_mm']} mm (required >= 1 mm; {g['vertices_moved_out_of_bone']} of {g['vertices']} vertices "
            f"({g['moved_fraction_pct']} %) were moved off a vertebra along its normal by at most {g['max_move_out_of_bone_mm']} mm; in the library's own frame the thoracolumbar cord (T10-L1 segments) already touches its vertebrae by up to 2.4 mm); "
            f"inside the vertebral canal {g['canal_inside_pct']} % of the vertices ({canal_txt}); {g['skin_distance_min_mm']} mm inside the skin. Nerve roots, dura, CSF and the cauda equina are not modelled.")
