#!/usr/bin/env python3
"""Q210 pack stage: the changed skin patches (and the left palmaris longus) are re-packed into the published Q208 male page (everything else byte for byte), every changed card carries its before -> after numbers.
    python3 scripts/zanatomy/q210_pack.py"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.zanatomy import q210_core as K  # noqa: E402
from scripts.zanatomy import q210_struct as ST  # noqa: E402

f2 = lambda x: f"{x[0]} -> {x[1]}"
SIDE = {"l": "left", "r": "right"}


def note_uro(i, m, g):
    k = i[-1]
    v0, v1, vs = g["volume_mm3"][k]
    xb, xa = g["across_midline_plane_mm_before"], g["across_midline_plane_mm_after"]
    fs = g["structures_final_state"]
    glans = fs["zan_glans_penis"]
    cav = fs["zan_corpus_cavernosum_of_penis"]
    b = g["structures"]
    return (f" Q210: urogenital skin follows the genital structures. After the Q207 refit this patch had been shrunk to the Z-source volume ({vs} mm3) while the person's fitted genital structures kept the fit scale "
            f"(testes volume x{g['structure_fit_scale']['zan_testis_l']['volume_ratio_fit_over_source']}, spongiosum x{g['structure_fit_scale']['zan_corpus_spongiosum_of_penis']['volume_ratio_fit_over_source']}, penis length "
            f"x{g['structure_fit_scale']['zan_corpus_cavernosum_of_penis']['axis_length_ratio_fit_over_source']}, all inside his own CT skin), so they lay OUTSIDE it (glans penis {b['zan_glans_penis']['before']['audit_gt3_pct']} % of its vertices > 3 mm outside the skin envelope, "
            f"up to {b['zan_glans_penis']['before']['audit_max_mm']} mm; corpus cavernosum {b['zan_corpus_cavernosum_of_penis']['before']['audit_gt3_pct']} %). Moving the structures with the Q207 skin warp would have shortened the penis by 8-37 % and shrunk the testes by about 20 %, "
            f"so the skin was refit instead: the Q207 refit (the Z source patch placed by ONE similarity transform shared by both halves plus a harmonic residual onto the fixed neighbours, seam vertices one node) was re-run with the volume target "
            f"{g['target_volume_mm3']} mm3 per half, the smallest on a 2000 mm3 grid at which every listed structure is enclosed, then the Q208 rim weld, and finally the outer sheet was clamped onto his own CT skin (0.3 mm inside it, both sheets of the slab together, welds kept; "
            f"vertices > 2 mm outside his own skin {g['refit']['own_clamp']['outside_own_skin_gt2mm_pct'][0]} -> {g['refit']['own_clamp']['outside_own_skin_gt2mm_pct'][1]} % before / after the clamp, this patch Q208 -> Q210 {f2(m['outside_own_skin_gt2mm_pct'])} %). Volume {v0} -> {v1} mm3 (source {vs}); "
            f"across the midline plane: left half {xb['l_reaches_into_r_side']} -> {xa['l_reaches_into_r_side']} mm, right half {xb['r_reaches_into_l_side']} -> {xa['r_reaches_into_l_side']} mm. "
            f"Now glans penis {glans['audit_gt3_pct']} % / corpus cavernosum {cav['audit_gt3_pct']} % of the vertices > 3 mm outside. Mean move {m['mean_move_mm']} mm, max {m['max_move_mm']} mm; largest border step to a neighbour {f2(m['seam_step_max_mm'])} mm. "
            f"No structure was moved. Rule-based, nothing invented.")


def note_genital_neighbour(i, m):
    return (f" Q210: neighbour weld of the urogenital refit. This patch moved only where it shares vertices with the refit urogenital patch (rim weld, sparse least squares): mean move {m['mean_move_mm']} mm, max {m['max_move_mm']} mm "
            f"({m['vertices_moved_gt0_3mm']} of {m['vertices']} vertices moved > 0.3 mm); largest border step to a neighbour {f2(m['seam_step_max_mm'])} mm. No structure was moved. Rule-based, nothing invented.")


def note_contact(i, m, c, who):
    side = SIDE[i[-1]]
    b, a = c["before"], c["after"]
    role = "forearm / wrist" if who == "F" else "trunk / thigh"
    margin = c["margins"][i]
    return (f" Q210: forearm | trunk skin contact relaxation (this {role} skin patch, {side} side). His arms rest on his body in the CT; the skin of the forearm and of the lateral abdomen / thigh / inguinal region crossed in {b['deep_gt2']} deep face pairs "
            f"(median {b['depth_mm_median_p90_max'][0]} mm, p90 {b['depth_mm_median_p90_max'][1]}, max {b['depth_mm_median_p90_max'][2]} mm) while the deep tissue of the two is clear (23-25 mm, 0 mm3 overlap). The gap between the forearm tissue and the trunk tissue was split between the two skins in proportion to their margins over their own tissue "
            f"(forearm share {c['rho'][i[-1]]:.2f}); a vertex moves toward its OWN deep tissue, both sheets of a slab together (thickness kept), tapering to 0 over 8 mm at the welds, never closer than 1 mm to its tissue (this patch: skin-to-tissue distance min {f2(margin['min_margin_mm'])} mm, 5th percentile {f2(margin['p5_margin_mm'])} mm). "
            f"Deep forearm | trunk face pairs {b['deep_gt2']} -> {a['deep_gt2']} (all depths: {b['forearm_trunk_pairs_gt0']} -> {a['forearm_trunk_pairs_gt0']}). This patch: mean move {m['mean_move_mm']} mm, max {m['max_move_mm']} mm "
            f"({m['vertices_moved_gt0_3mm']} of {m['vertices']} vertices > 0.3 mm), median slab thickness {f2(m['thickness_median_mm'])} mm, largest border step to a neighbour {f2(m['seam_step_max_mm'])} mm. No bone, muscle or vessel was moved. Rule-based, nothing invented.")


def note_palmaris(p):
    o, e = p["outside_own_skin"], p["max_outside_own_skin_mm"]
    return (f" Q210: the distal tendon end of this muscle (21 vertices, 1.2 %) lay up to {e[0]} mm outside his own CT skin (fit defect of the muscle). Those vertices were moved to the nearest point of his own skin, 1 mm inside, and the displacement was extended into the mesh as a harmonic field "
            f"that decays to 0 at 25 mm of mesh distance (everything further away keeps its place): vertices outside his own skin {o[0]} -> {o[1]}, vertices > 3 mm outside the displayed skin {p['outside_displayed_skin_gt3_pct'][0]} -> {p['outside_displayed_skin_gt3_pct'][1]} %, extent along the muscle axis "
            f"{p['extent_along_axis_mm'][0]} -> {p['extent_along_axis_mm'][1]} mm, edges stretched more than 2x {p['edges_gt2x']} of {p['edges']}. Rule-based, nothing invented.")


def run(out=None, log=print):
    cfg = K.PAGE
    out = Path(out or cfg["out"])
    pg, raw = K.load()
    rep = pickle.load(open(K.state_path("report"), "rb"))
    Vg = pickle.load(open(K.state_path("genital"), "rb"))[0]
    Vc, crep = pickle.load(open(K.state_path("contact"), "rb"))
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    gmoved = {i for i in Vg if np.linalg.norm(Vg[i] - V0[i], axis=1).max() > 0.05}
    cmoved = {i for i in Vc if np.linalg.norm(Vc[i] - Vg[i], axis=1).max() > 0.05}
    replace, stages = {}, {}
    for i in sorted(rep["moved"]):
        m = rep["moved"][i]
        rec = dict(pg.S[i]["m"].get("rec") or {})
        badge = rec.get("procedural_badge") or ""
        notes, st = [], []
        if i in gmoved:
            if i in K.UROS:
                notes.append(note_uro(i, m, rep["genital"]))
                st.append("urogenital refit to the structures' scale")
            else:
                notes.append(note_genital_neighbour(i, m))
                st.append("urogenital neighbour weld")
        if i in cmoved:
            who = "F" if i in crep["F"] else "T"
            notes.append(note_contact(i, m, rep["contact"], who))
            st.append("forearm | trunk contact relaxation (" + ("forearm" if who == "F" else "trunk / thigh") + ")")
        rec["procedural_badge"] = (badge + "".join(notes)).strip()
        replace[i] = (Vc[i], pg.f(i), rec)
        stages[i] = st
    if "palmaris" in rep:
        sv = pickle.load(open(K.state_path("struct"), "rb"))[0]
        rec = dict(pg.S[ST.ID]["m"].get("rec") or {})
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + note_palmaris(rep["palmaris"])).strip()
        replace[ST.ID] = (sv[ST.ID], pg.f(ST.ID), rec)
        stages[ST.ID] = ["structure: distal tendon end pulled inside his own skin"]
    man2, blob2 = P5.save_page(out, cfg["stem"], pg.man, pg.blob, replace=replace)
    r = SD.diff(cfg["src"], out, cfg["stem"], sorted(replace))
    r["listed_structures"] = len(replace)
    r["stages"] = stages
    for i, x in r["geometry_changed"].items():
        x["max_move_mm"] = rep["moved"][i]["max_move_mm"] if i in rep["moved"] else None
    (REPO / "data" / "derived" / "Q210_ship_diff_male.json").write_text(json.dumps(r, indent=1))
    log(f"page {out}: replaced {len(replace)} meshes; ship diff: " + str({k: (len(v) if hasattr(v, '__len__') else v) for k, v in r.items() if k != 'stages'}))
    return r


if __name__ == "__main__":
    run()
